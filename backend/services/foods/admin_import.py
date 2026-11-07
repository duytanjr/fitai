"""Nạp thực phẩm từ CSV vào nguồn ADMIN_MANUAL (scripts/import_admin_foods.py).

Dùng LẠI quy tắc của /admin/foods: AdminFoodCreate (biên từng cột, ghi chú nguồn bắt buộc, cắt khoảng trắng),
check_mass_sum (≤ 100,5 g), normalize_search; ghi qua create_food / update_food nên có cùng source_ref ADM-xxxxx,
cờ Atwater, bắt trùng tên ở DB và audit log như form / PATCH.

Hai bước: `parse_file` (thuần, không DB) rồi `run_import` — kiểm tra TOÀN BỘ trước (kể cả gộp với dòng đã có
khi --update-existing); chỉ cần một lỗi là không ghi gì. Người gọi quyết định commit / rollback.
"""
from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.admin import AdminFoodCreate
from models.food import Food
from models.user import User, UserRole
from services.foods import admin as admin_foods
from services.foods.normalize import normalize_search
from services.foods.preparation import FoodPreparation
from services.foods.sources import ADMIN_MANUAL_ID
from services.training.seed import CsvFormatError, is_example, read_csv

REQUIRED_COLUMNS = ("name_vi", "energy_kcal", "protein_g", "fat_g", "carb_g", "source_note")
OPTIONAL_COLUMNS = ("fiber_g", "water_g", "refuse_pct", "group_name", "preparation", "name_original")
NUMERIC_COLUMNS = ("energy_kcal", "protein_g", "fat_g", "carb_g", "fiber_g", "water_g", "refuse_pct")
PREPARATION_VALUES = ", ".join(p.value for p in FoodPreparation)


class ImportAdminError(Exception):
    """Tài khoản ghi audit không hợp lệ (không có / không phải admin / bị khoá)."""


@dataclass
class ImportRow:
    line: int
    data: dict[str, Any]          # đã qua AdminFoodCreate; chỉ gồm cột có trong file (ô trống tuỳ chọn = None)
    name_search: str

    @property
    def name(self) -> str:
        return self.data["name_vi"]


@dataclass
class ImportPlan:
    file: str
    rows: list[ImportRow] = field(default_factory=list)
    examples: list[tuple[int, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class ImportReport:
    created: list[tuple[int, str]] = field(default_factory=list)
    updated: list[tuple[int, str]] = field(default_factory=list)
    unchanged: list[tuple[int, str]] = field(default_factory=list)
    skipped_existing: list[tuple[int, str]] = field(default_factory=list)
    flags: list[tuple[str, str]] = field(default_factory=list)       # (tên món, chi tiết lệch Atwater)
    errors: list[str] = field(default_factory=list)


# ── Đọc và kiểm tra file (thuần) ─────────────────────────────────────────────

def parse_number(value: str) -> float:
    """Nhận '1,5' và '1.5'; từ chối dấu phân cách hàng nghìn (có cả ',' và '.')."""
    v = value.replace(" ", "")
    if "," in v and "." in v:
        raise ValueError("không dùng dấu phân cách hàng nghìn; ghi dạng 1234,5 hoặc 1234.5")
    try:
        return float(v.replace(",", "."))
    except ValueError:
        raise ValueError(f"'{value}' không phải số") from None


def _pydantic_message(err: dict) -> str:
    ctx = err.get("ctx") or {}
    kind = err["type"]
    if kind == "missing":
        return "bắt buộc, không được để trống"
    if kind in ("greater_than_equal", "less_than_equal"):
        bound = ctx.get("ge", ctx.get("le"))
        return f"phải {'≥' if kind == 'greater_than_equal' else '≤'} {bound:g}"
    if kind == "finite_number":
        return "phải là số hữu hạn"
    if kind == "string_too_long":
        return f"dài quá {ctx.get('max_length')} ký tự"
    if kind == "enum":
        return f"phải là một trong: {PREPARATION_VALUES}"
    return err["msg"]


def _parse_row(line: int, cells: dict[str, str], columns: set[str]) -> tuple[ImportRow | None, list[str]]:
    errors: list[str] = []
    raw: dict[str, Any] = {}
    for col in (*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS):
        if col not in columns:
            continue
        value = cells.get(col, "")
        if value == "":
            if col in OPTIONAL_COLUMNS:
                raw[col] = None
            continue                                  # cột bắt buộc trống → báo "missing" từ schema
        if col in NUMERIC_COLUMNS:
            try:
                raw[col] = parse_number(value)
            except ValueError as exc:
                errors.append(f"dòng {line}, cột {col}: {exc}")
        elif col == "preparation":
            raw[col] = value.lower()
        else:
            raw[col] = value
    if errors:
        return None, errors
    try:
        model = AdminFoodCreate(**raw)
    except ValidationError as exc:
        return None, [f"dòng {line}, cột {e['loc'][0] if e['loc'] else '?'}: {_pydantic_message(e)}"
                      for e in exc.errors()]
    data = {k: v for k, v in model.model_dump().items() if k in columns}
    try:
        admin_foods.check_mass_sum(data)
    except admin_foods.AdminFoodInvalidError as exc:
        return None, [f"dòng {line}: {exc}"]
    name_search = normalize_search(data["name_vi"])
    if not name_search:
        return None, [f"dòng {line}, cột name_vi: tên phải có chữ hoặc số"]
    return ImportRow(line=line, data=data, name_search=name_search), []


def parse_file(path: Path) -> ImportPlan:
    plan = ImportPlan(file=str(path))
    try:
        csv_data = read_csv(path, [*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS], set(OPTIONAL_COLUMNS))
    except CsvFormatError as exc:
        plan.errors.append(str(exc))
        return plan
    header = _header(path, csv_data.delimiter)
    columns = {c for c in (*REQUIRED_COLUMNS, *OPTIONAL_COLUMNS) if c in header}
    if csv_data.extra_columns:
        plan.warnings.append(f"bỏ qua cột không dùng: {', '.join(csv_data.extra_columns)}")
    seen: dict[str, int] = {}
    for line, cells in csv_data.rows:
        if is_example(cells.get("name_vi")):
            plan.examples.append((line, cells["name_vi"]))
            continue
        row, errors = _parse_row(line, cells, columns)
        plan.errors.extend(errors)
        if row is None:
            continue
        if row.name_search in seen:
            plan.errors.append(f"dòng {line}, cột name_vi: trùng tên (không phân biệt dấu) với dòng {seen[row.name_search]}")
            continue
        seen[row.name_search] = line
        plan.rows.append(row)
    if not plan.rows and not plan.errors and not plan.examples:
        plan.warnings.append("file không có dòng dữ liệu nào")
    return plan


def _header(path: Path, delimiter: str) -> set[str]:
    """Tên cột có trong file (read_csv điền "" cho cột tuỳ chọn vắng mặt nên không phân biệt được)."""
    text = path.read_text(encoding="utf-8-sig")
    return {h.strip().lower() for h in next(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter))}


# ── Ghi DB ───────────────────────────────────────────────────────────────────

async def find_admin(db: AsyncSession, email: str) -> User:
    user = await db.scalar(select(User).where(func.lower(User.email) == email.strip().lower()))
    if user is None:
        raise ImportAdminError(f"Không có tài khoản với email {email.strip()}")
    if user.role != UserRole.ADMIN:
        raise ImportAdminError(f"Tài khoản {email.strip()} không có quyền admin (cấp bằng scripts/make_admin.py)")
    if not user.is_active:
        raise ImportAdminError(f"Tài khoản {email.strip()} đang bị khoá")
    return user


def _merged(food: Food, data: dict[str, Any]) -> dict[str, Any]:
    after = {**admin_foods.food_values(food), **data}
    after["group_name"] = after.get("group_name") or admin_foods.DEFAULT_GROUP_NAME
    after["preparation"] = after.get("preparation") or FoodPreparation.UNKNOWN
    return after


async def run_import(db: AsyncSession, plan: ImportPlan, admin_id: uuid.UUID, *, update_existing: bool,
                     dry_run: bool) -> ImportReport:
    """Kiểm tra toàn bộ (đọc DB) rồi mới ghi; có lỗi → không ghi gì. dry_run → chỉ phân loại."""
    report = ImportReport(errors=list(plan.errors))
    existing = {f.name_search: f for f in (await db.scalars(select(Food).where(
        Food.source_id == ADMIN_MANUAL_ID,
        Food.name_search.in_([r.name_search for r in plan.rows])))).all()} if plan.rows else {}

    actions: list[tuple[str, ImportRow, Food | None]] = []
    for row in plan.rows:
        food = existing.get(row.name_search)
        if food is None:
            actions.append(("create", row, None))
        elif not update_existing:
            report.skipped_existing.append((row.line, row.name))
        else:
            after = _merged(food, row.data)
            if after == admin_foods.food_values(food):
                report.unchanged.append((row.line, row.name))
                continue
            try:
                admin_foods.check_mass_sum(after)
            except admin_foods.AdminFoodInvalidError as exc:
                report.errors.append(f"dòng {row.line} (gộp với món đã có): {exc}")
                continue
            actions.append(("update", row, food))
    if report.errors:
        return report

    for kind, row, food in actions:
        if dry_run:
            flags = admin_foods.atwater_flags(row.data if food is None else _merged(food, row.data))
        else:
            try:
                if food is None:
                    food = await admin_foods.create_food(db, admin_id, row.data)
                else:
                    food = await admin_foods.update_food(db, admin_id, food.id, row.data)
            except admin_foods.AdminFoodError as exc:      # vd. trùng tên do nhập đồng thời
                report.errors.append(f"dòng {row.line}: {exc}")
                return report
            flags = food.quality_flags
        (report.created if kind == "create" else report.updated).append((row.line, row.name))
        if flags and admin_foods.FLAG_ATWATER_15PCT in flags:
            report.flags.append((row.name, flags[admin_foods.FLAG_ATWATER_15PCT]))
    return report
