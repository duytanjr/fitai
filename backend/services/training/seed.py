"""Nạp chương trình tập luyện từ programs.csv + schedule.csv (lát 9a).

Hai bước:
1. `load_dir(dir)` — đọc CSV (tự nhận dấu phân cách từ dòng tiêu đề), kiểm tra, tính trạng thái. Hàm thuần.
   Lỗi cấu trúc gom vào `SeedPlan.errors` → không ghi gì ("tất cả hoặc không"). Thiếu ngày của chương trình
   publish=false chỉ là cảnh báo (chương trình giữ draft); publish=true thì là lỗi.
2. `apply_plan(db, plan)` — upsert theo khoá tự nhiên (youtube_id hoặc title khi chưa có link; slug;
   (chương trình, day_number); (ngày, position)). Chỉ flush, người gọi commit. Ngày/mục không còn trong CSV
   bị xoá; video và chương trình không còn trong CSV được giữ nguyên và chỉ được nêu trong báo cáo.

Cột bắt buộc: programs.csv — slug, title, description, goal_tag, level, duration_days, publish;
schedule.csv — program_slug, day_number, is_rest, position, label, required, url. Mọi cột khác tuỳ chọn (có thể
vắng cả cột hoặc để trống). title video mặc định bằng label; ô được điền thì vẫn phải hợp lệ.

Quy tắc trạng thái:
- Video luôn draft nếu thiếu url, hoặc title / label của bất kỳ mục nào trỏ tới nó bắt đầu bằng "(VÍ DỤ)".
  Thiếu thời lượng, kênh, ngày kiểm tra chỉ cảnh báo.
- Chương trình chỉ published khi publish=true, đủ ngày, mọi mục trỏ tới video published, có ít nhất một mục,
  và title/description không bắt đầu bằng "(VÍ DỤ)". Không thì draft kèm lý do.
"""
import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.training import (
    MAX_VIDEO_MIN, MIN_VIDEO_MIN, ProgramDay, ProgramDayItem, ProgramGoal, TrainingLevel, TrainingProgram,
    TrainingStatus, WorkoutCategory, WorkoutImpact, WorkoutIntensity, WorkoutVideo,
)
from services.foods.normalize import normalize_search
from services.training.catalog import sum_known
from services.knowledge.documents import clean_text
from services.training.youtube import InvalidVideoUrl, parse_youtube_url

PROGRAMS_FILE = "programs.csv"
SCHEDULE_FILE = "schedule.csv"
PROGRAM_COLUMNS = ["slug", "title", "description", "goal_tag", "level", "duration_days", "intensity_label",
                   "publish"]
SCHEDULE_COLUMNS = ["program_slug", "day_number", "is_rest", "position", "label", "required", "url", "title",
                    "channel", "duration_min", "category", "intensity", "impact", "equipment", "level", "notes",
                    "checked_on"]
# Cột được phép có giá trị ở dòng ngày nghỉ (notes → ghi chú của ngày)
REST_ALLOWED = {"program_slug", "day_number", "is_rest", "notes"}
OPTIONAL_PROGRAM_COLUMNS = {"intensity_label"}
OPTIONAL_SCHEDULE_COLUMNS = {"title", "channel", "duration_min", "category", "intensity", "impact", "equipment",
                             "level", "notes", "checked_on"}
# Cảnh báo (không chặn) khi video published thiếu các cột này
RECOMMENDED_VIDEO_FIELDS = ("duration_min", "channel", "checked_on")

DELIMITERS = {",": "dấu phẩy ','", ";": "dấu chấm phẩy ';'", "\t": "tab"}
TRUE_VALUES, FALSE_VALUES = {"true", "1"}, {"false", "0"}
SLUG_RE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
MAX_SLUG, MAX_TITLE, MAX_DESCRIPTION, MAX_LABEL = 60, 200, 2000, 200
MAX_CHANNEL, MAX_EQUIPMENT, MAX_INTENSITY_LABEL, MAX_NOTES = 100, 100, 60, 1000
MAX_DURATION_DAYS = 365
EXAMPLE_PREFIX = "vi du"


class CsvFormatError(ValueError):
    pass


def is_example(text: str | None) -> bool:
    """'(VÍ DỤ) ...' (không phân biệt hoa thường / dấu) → True."""
    t = (text or "").strip()
    return t.startswith("(") and normalize_search(t[1:12]).startswith(EXAMPLE_PREFIX)


# ── Đọc CSV ──────────────────────────────────────────────────────────────────

@dataclass
class CsvData:
    name: str
    delimiter: str
    rows: list[tuple[int, dict[str, str]]]      # (số dòng trong file, ô đã cắt khoảng trắng)
    extra_columns: list[str]


def detect_delimiter(header_line: str, name: str) -> str:
    found = [d for d in DELIMITERS if d in header_line]
    if not found:
        raise CsvFormatError(f"{name} dòng 1: không nhận ra dấu phân cách (cần ',', ';' hoặc tab ở dòng tiêu đề)")
    if len(found) > 1:
        names = ", ".join(DELIMITERS[d] for d in found)
        raise CsvFormatError(f"{name} dòng 1: dấu phân cách mơ hồ (dòng tiêu đề có cả {names})")
    return found[0]


def read_csv(path: Path, columns: list[str], optional: set[str]) -> CsvData:
    """utf-8-sig (bỏ BOM), tự nhận dấu phân cách, cắt khoảng trắng mỗi ô, bỏ dòng trống hoàn toàn."""
    name = path.name
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError as exc:
        raise CsvFormatError(f"không tìm thấy {name} trong {path.parent}") from exc
    except UnicodeDecodeError as exc:
        raise CsvFormatError(f"{name}: không đọc được bằng UTF-8 (hãy lưu file dạng CSV UTF-8)") from exc
    header_line = text.splitlines()[0] if text.strip() else ""
    if not header_line.strip():
        raise CsvFormatError(f"{name} dòng 1: thiếu dòng tiêu đề")
    delimiter = detect_delimiter(header_line, name)

    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    header = [h.strip().lower() for h in next(reader)]
    missing = [c for c in columns if c not in header and c not in optional]
    if missing:
        raise CsvFormatError(f"{name} dòng 1: thiếu cột {', '.join(missing)} (đã dùng {DELIMITERS[delimiter]})")
    dupes = sorted({h for h in header if header.count(h) > 1})
    if dupes:
        raise CsvFormatError(f"{name} dòng 1: cột bị lặp {', '.join(dupes)}")
    rows = []
    for cells in reader:
        line = reader.line_num
        if not any(c.strip() for c in cells):
            continue
        if len(cells) > len(header) and any(c.strip() for c in cells[len(header):]):
            raise CsvFormatError(f"{name} dòng {line}: nhiều ô hơn số cột tiêu đề ({len(cells)} > {len(header)})")
        values = {h: (cells[i].strip() if i < len(cells) else "") for i, h in enumerate(header)}
        rows.append((line, {c: values.get(c, "") for c in columns}))
    extra = [h for h in header if h not in columns and h]
    return CsvData(name=name, delimiter=delimiter, rows=rows, extra_columns=extra)


# ── Kiểm tra từng ô ──────────────────────────────────────────────────────────

class CellError(ValueError):
    pass


def parse_bool(value: str, default: bool | None = None) -> bool:
    v = value.strip().lower()
    if v == "" and default is not None:
        return default
    if v in TRUE_VALUES:
        return True
    if v in FALSE_VALUES:
        return False
    raise CellError("phải là true/false (hoặc 1/0)")


def parse_int(value: str, lo: int, hi: int | None = None) -> int:
    if not re.fullmatch(r"\d+", value or ""):
        raise CellError("phải là số nguyên")
    n = int(value)
    if n < lo or (hi is not None and n > hi):
        raise CellError(f"phải trong khoảng {lo}–{hi}" if hi is not None else f"phải >= {lo}")
    return n


def parse_enum(value: str, enum_cls):
    allowed = [m.value for m in enum_cls]
    if value.lower() not in allowed:
        raise CellError(f"phải là một trong {', '.join(allowed)}")
    return enum_cls(value.lower())


def optional(fn):
    """Ô trống → None; có giá trị thì vẫn kiểm bằng fn."""
    def parse(value: str, *args):
        return None if value == "" else fn(value, *args)
    return parse


def parse_date(value: str) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    raise CellError("phải có dạng YYYY-MM-DD hoặc DD/MM/YYYY")


def parse_text(value: str, limit: int, required: bool = False) -> str:
    text = clean_text(value)
    if required and not text:
        raise CellError("không được để trống")
    if len(text) > limit:
        raise CellError(f"dài quá {limit} ký tự")
    return text


# ── Kế hoạch nạp ─────────────────────────────────────────────────────────────

@dataclass
class VideoSpec:
    key: tuple[str, str]                    # ("yt", youtube_id) hoặc ("title", title)
    youtube_id: str | None
    url: str | None
    title: str                              # ô title, hoặc label của dòng đầu tiên nếu không dòng nào điền title
    first_line: int
    channel: str | None = None
    duration_min: int | None = None
    category: WorkoutCategory | None = None
    intensity: WorkoutIntensity | None = None
    impact: WorkoutImpact | None = None
    equipment: str | None = None
    level: TrainingLevel | None = None
    notes: str | None = None
    checked_on: date | None = None
    # Giá trị ĐƯỢC ĐIỀN của từng cột và dòng điền đầu tiên — để so giữa các dòng (ô trống không tính là khác)
    filled: dict[str, tuple[object, int]] = field(default_factory=dict)
    status: TrainingStatus = TrainingStatus.DRAFT
    draft_reasons: list[str] = field(default_factory=list)

    def merge(self, values: dict[str, object], line: int) -> list[str]:
        """Gộp các ô được điền của một dòng khác cùng video; trả các cột mâu thuẫn kèm dòng đã điền trước."""
        conflicts = []
        for name, value in values.items():
            if name in self.filled:
                if self.filled[name][0] != value:
                    conflicts.append(f"{name} (dòng {self.filled[name][1]})")
                continue
            self.filled[name] = (value, line)
            setattr(self, name, value)
        return conflicts


INFO_FIELDS = ("title", "channel", "duration_min", "category", "intensity", "impact", "equipment", "level",
               "notes", "checked_on")


@dataclass
class ItemSpec:
    position: int
    video_key: tuple[str, str]
    label: str | None
    required: bool
    line: int


@dataclass
class DaySpec:
    day_number: int
    is_rest: bool
    note: str | None
    items: list[ItemSpec]
    line: int


@dataclass
class ProgramSpec:
    slug: str
    title: str
    description: str
    goal_tag: ProgramGoal
    level: TrainingLevel
    duration_days: int
    intensity_label: str
    publish: bool
    line: int
    days: dict[int, DaySpec] = field(default_factory=dict)
    has_row_errors: bool = False        # có dòng lịch lỗi → bỏ qua kiểm tra đủ ngày (tránh báo lỗi kéo theo)
    status: TrainingStatus = TrainingStatus.DRAFT
    draft_reasons: list[str] = field(default_factory=list)


@dataclass
class SeedPlan:
    delimiters: dict[str, str] = field(default_factory=dict)
    programs: dict[str, ProgramSpec] = field(default_factory=dict)
    videos: dict[tuple[str, str], VideoSpec] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def minutes(self, day: DaySpec) -> tuple[int | None, int | None]:
        """(tổng, bắt buộc) chỉ cộng mục có duration_min; None khi không mục nào có thời lượng."""
        total = sum_known(self.videos[i.video_key].duration_min for i in day.items)
        required = sum_known(self.videos[i.video_key].duration_min for i in day.items if i.required)
        return total, required


def _parse_programs(data: CsvData, plan: SeedPlan) -> None:
    for line, row in data.rows:
        where = f"{data.name} dòng {line}"
        errs = []

        def cell(col, fn, *args):
            try:
                return fn(row[col], *args)
            except CellError as exc:
                errs.append(f"{where}: cột {col} {exc}")
                return None

        slug = row["slug"].lower()
        if not SLUG_RE.fullmatch(slug) or len(slug) > MAX_SLUG:
            errs.append(f"{where}: cột slug phải gồm chữ thường không dấu, số và '-', tối đa {MAX_SLUG} ký tự")
        elif slug in plan.programs:
            errs.append(f"{where}: slug '{slug}' bị lặp (đã có ở dòng {plan.programs[slug].line})")
        spec = ProgramSpec(
            slug=slug,
            title=cell("title", parse_text, MAX_TITLE, True),
            description=cell("description", parse_text, MAX_DESCRIPTION),
            goal_tag=cell("goal_tag", parse_enum, ProgramGoal),
            level=cell("level", parse_enum, TrainingLevel),
            duration_days=cell("duration_days", parse_int, 1, MAX_DURATION_DAYS),
            intensity_label=cell("intensity_label", parse_text, MAX_INTENSITY_LABEL),
            publish=cell("publish", parse_bool, False),
            line=line,
        )
        plan.errors.extend(errs)
        if not errs:
            plan.programs[slug] = spec


def _parse_schedule(data: CsvData, plan: SeedPlan) -> None:
    for line, row in data.rows:
        where = f"{data.name} dòng {line}"
        program = plan.programs.get(row["program_slug"].lower())
        if program is None:
            plan.errors.append(f"{where}: program_slug '{row['program_slug']}' không có trong {PROGRAMS_FILE}")
            continue
        errors = _parse_schedule_row(plan, program, line, row, where)
        if errors:
            plan.errors.extend(errors)
            program.has_row_errors = True


def _parse_schedule_row(plan: SeedPlan, program: ProgramSpec, line: int, row: dict, where: str) -> list[str]:
    """Thêm một dòng lịch vào kế hoạch; trả danh sách lỗi (rỗng nếu hợp lệ)."""
    slug = program.slug
    errs: list[str] = []

    def cell(col, fn, *args):
        try:
            return fn(row[col], *args)
        except CellError as exc:
            errs.append(f"{where}: cột {col} {exc}")
            return None

    day_number = cell("day_number", parse_int, 1)
    is_rest = cell("is_rest", parse_bool, False)
    if errs:
        return errs
    if day_number > program.duration_days:
        return [f"{where}: day_number {day_number} lớn hơn duration_days {program.duration_days} của '{slug}'"]
    day = program.days.get(day_number)

    if is_rest:
        filled = [c for c in SCHEDULE_COLUMNS if c not in REST_ALLOWED and row[c]]
        if filled:
            return [f"{where}: ngày nghỉ không được có mục (bỏ trống các cột {', '.join(filled)})"]
        if day is not None:
            kind = "ngày nghỉ" if day.is_rest else "ngày tập"
            return [f"{where}: ngày {day_number} của '{slug}' đã khai báo là {kind} ở dòng {day.line}"]
        note = cell("notes", parse_text, MAX_NOTES)
        if not errs:
            program.days[day_number] = DaySpec(day_number, True, note or None, [], line)
        return errs

    if day is not None and day.is_rest:
        return [f"{where}: ngày {day_number} của '{slug}' đã là ngày nghỉ ở dòng {day.line}; ngày nghỉ không có mục"]
    position = cell("position", parse_int, 1)
    label = cell("label", parse_text, MAX_LABEL)
    required = cell("required", parse_bool, True)
    youtube_id = url = None
    if row["url"]:                          # trống → chưa có link, video draft
        try:
            youtube_id, url = parse_youtube_url(row["url"])
        except InvalidVideoUrl as exc:
            errs.append(f"{where}: cột url không hợp lệ ({exc})")
    values = {
        "title": cell("title", parse_text, MAX_TITLE),
        "channel": cell("channel", parse_text, MAX_CHANNEL),
        "duration_min": cell("duration_min", optional(parse_int), MIN_VIDEO_MIN, MAX_VIDEO_MIN),
        "category": cell("category", optional(parse_enum), WorkoutCategory),
        "intensity": cell("intensity", optional(parse_enum), WorkoutIntensity),
        "impact": cell("impact", optional(parse_enum), WorkoutImpact),
        "equipment": cell("equipment", parse_text, MAX_EQUIPMENT),
        "level": cell("level", optional(parse_enum), TrainingLevel),
        "notes": cell("notes", parse_text, MAX_NOTES),
        "checked_on": cell("checked_on", parse_date),
    }
    values = {k: v for k, v in values.items() if v not in (None, "")}       # chỉ ô được điền
    title = values.get("title") or label
    if not errs and not title:
        errs.append(f"{where}: cần điền label hoặc title")
    if day is not None and position is not None:
        other = next((i for i in day.items if i.position == position), None)
        if other is not None:
            errs.append(f"{where}: position {position} của ngày {day_number} '{slug}' bị lặp (dòng {other.line})")
    if errs:
        return errs

    key = ("yt", youtube_id) if youtube_id else ("title", title)
    video = plan.videos.get(key)
    if video is None:
        video = plan.videos[key] = VideoSpec(key=key, youtube_id=youtube_id, url=url, title=title, first_line=line)
    conflicts = video.merge(values, line)
    if conflicts:
        ident = f"youtube_id {youtube_id}" if youtube_id else f"title '{title}' (chưa có url)"
        return [f"{where}: cùng {ident} nhưng khác thông tin đã điền ở cột {', '.join(conflicts)}"]
    if day is None:
        day = program.days[day_number] = DaySpec(day_number, False, None, [], line)
    day.items.append(ItemSpec(position, key, label or None, required, line))
    if is_example(label):
        video.draft_reasons.append(f"label bắt đầu bằng (VÍ DỤ) (dòng {line})")
    return []


def _decide_status(plan: SeedPlan) -> None:
    for v in plan.videos.values():
        if not v.url:
            v.draft_reasons.insert(0, "chưa có url")
        if is_example(v.title):
            v.draft_reasons.insert(0, "title bắt đầu bằng (VÍ DỤ)")
        missing = [f for f in RECOMMENDED_VIDEO_FIELDS if getattr(v, f) is None]
        if missing and v.url:
            plan.warnings.append(f"{SCHEDULE_FILE} dòng {v.first_line}: video {v.youtube_id} chưa có "
                                 f"{', '.join(missing)}")
        v.status = TrainingStatus.DRAFT if v.draft_reasons else TrainingStatus.PUBLISHED

    for p in plan.programs.values():
        where = f"'{p.slug}'"
        for day in p.days.values():
            if not day.is_rest:
                day.items.sort(key=lambda i: i.position)
                if not any(i.required for i in day.items) and not p.has_row_errors:
                    plan.errors.append(f"{SCHEDULE_FILE} dòng {day.line}: ngày {day.day_number} của {where} "
                                       "không có mục nào required=true")
        missing = [n for n in range(1, p.duration_days + 1) if n not in p.days]
        if missing and p.has_row_errors:
            p.draft_reasons.append(f"thiếu {len(missing)} ngày")      # lỗi dòng đã được báo; không báo kéo theo
        elif missing:
            msg = (f"{where} thiếu {len(missing)}/{p.duration_days} ngày trong lịch: {_ranges(missing)}")
            if p.publish:
                plan.errors.append(f"{PROGRAMS_FILE} dòng {p.line}: {msg} (publish=true cần đủ ngày)")
            else:
                plan.warnings.append(f"{msg} — chương trình giữ draft")
                p.draft_reasons.append(f"thiếu {len(missing)} ngày")
        if not p.publish:
            p.draft_reasons.insert(0, "publish=false")
        if is_example(p.title) or is_example(p.description):
            p.draft_reasons.append("title/description bắt đầu bằng (VÍ DỤ)")
        items = [i for d in p.days.values() for i in d.items]
        if not items:
            p.draft_reasons.append("chưa có mục nào")
        draft_items = [i for i in items if plan.videos[i.video_key].status != TrainingStatus.PUBLISHED]
        if draft_items:
            lines = ", ".join(str(i.line) for i in draft_items[:10]) + (" …" if len(draft_items) > 10 else "")
            p.draft_reasons.append(f"{len(draft_items)}/{len(items)} mục trỏ tới video draft (dòng {lines})")
        p.status = TrainingStatus.DRAFT if p.draft_reasons else TrainingStatus.PUBLISHED


def _ranges(numbers: list[int]) -> str:
    out, start, prev = [], numbers[0], numbers[0]
    for n in numbers[1:] + [None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        out.append(str(start) if start == prev else f"{start}–{prev}")
        if n is not None:
            start = prev = n
    return ", ".join(out)


def load_dir(directory: Path) -> SeedPlan:
    """Đọc và kiểm tra cả hai file; không chạm DB."""
    plan = SeedPlan()
    try:
        programs = read_csv(directory / PROGRAMS_FILE, PROGRAM_COLUMNS, OPTIONAL_PROGRAM_COLUMNS)
        schedule = read_csv(directory / SCHEDULE_FILE, SCHEDULE_COLUMNS, OPTIONAL_SCHEDULE_COLUMNS)
    except CsvFormatError as exc:
        plan.errors.append(str(exc))
        return plan
    for data in (programs, schedule):
        plan.delimiters[data.name] = DELIMITERS[data.delimiter]
        if data.extra_columns:
            plan.warnings.append(f"{data.name}: bỏ qua cột không dùng {', '.join(data.extra_columns)}")
    _parse_programs(programs, plan)
    _parse_schedule(schedule, plan)
    _decide_status(plan)
    return plan


# ── Ghi DB ───────────────────────────────────────────────────────────────────

@dataclass
class ApplyReport:
    created: dict[str, int] = field(default_factory=lambda: {"video": 0, "chương trình": 0, "ngày": 0, "mục": 0})
    updated: dict[str, int] = field(default_factory=lambda: {"video": 0, "chương trình": 0, "ngày": 0, "mục": 0})
    deleted: dict[str, int] = field(default_factory=lambda: {"ngày": 0, "mục": 0})
    programs_not_in_csv: list[str] = field(default_factory=list)
    unused_videos: int = 0
    published_programs_total: int = 0

    @property
    def changes(self) -> int:
        return sum(self.created.values()) + sum(self.updated.values()) + sum(self.deleted.values())


def _assign(obj, values: dict) -> bool:
    changed = False
    for k, v in values.items():
        if getattr(obj, k) != v:
            setattr(obj, k, v)
            changed = True
    return changed


async def _upsert_video(db: AsyncSession, spec: VideoSpec, report: ApplyReport,
                        titles_without_url: set[str]) -> WorkoutVideo:
    row = None
    if spec.youtube_id:
        row = await db.scalar(select(WorkoutVideo).where(WorkoutVideo.youtube_id == spec.youtube_id))
    if row is None and (spec.youtube_id is None or spec.title not in titles_without_url):
        # Bản draft chưa có link cùng title → gắn link vào chính dòng đó thay vì tạo dòng mới
        row = await db.scalar(select(WorkoutVideo).where(WorkoutVideo.youtube_id.is_(None),
                                                         WorkoutVideo.title == spec.title))
    values = {"youtube_id": spec.youtube_id, "url": spec.url, "status": spec.status,
              **{f: getattr(spec, f) for f in INFO_FIELDS}}
    if row is None:
        row = WorkoutVideo(**values)
        db.add(row)
        report.created["video"] += 1
    elif _assign(row, values):
        report.updated["video"] += 1
    return row


async def apply_plan(db: AsyncSession, plan: SeedPlan) -> ApplyReport:
    if not plan.ok:
        raise ValueError("kế hoạch nạp còn lỗi — không ghi DB")
    report = ApplyReport()
    video_ids: dict[tuple[str, str], int] = {}
    titles_without_url = {v.title for v in plan.videos.values() if v.youtube_id is None}
    for key, spec in plan.videos.items():
        row = await _upsert_video(db, spec, report, titles_without_url)
        await db.flush()
        video_ids[key] = row.id

    for spec in plan.programs.values():
        program = await db.scalar(select(TrainingProgram).where(TrainingProgram.slug == spec.slug))
        values = {"title": spec.title, "description": spec.description, "goal_tag": spec.goal_tag,
                  "level": spec.level, "duration_days": spec.duration_days, "intensity_label": spec.intensity_label,
                  "status": spec.status}
        if program is None:
            program = TrainingProgram(slug=spec.slug, **values)
            db.add(program)
            report.created["chương trình"] += 1
        elif _assign(program, values):
            report.updated["chương trình"] += 1
        await db.flush()

        existing = {d.day_number: d for d in (await db.scalars(
            select(ProgramDay).where(ProgramDay.program_id == program.id))).all()}
        for number, day_row in existing.items():
            if number not in spec.days:
                await db.delete(day_row)
                report.deleted["ngày"] += 1
        await db.flush()
        for number, day_spec in sorted(spec.days.items()):
            day_row = existing.get(number)
            values = {"is_rest": day_spec.is_rest, "note": day_spec.note}
            if day_row is None:
                day_row = ProgramDay(program_id=program.id, day_number=number, **values)
                db.add(day_row)
                report.created["ngày"] += 1
                await db.flush()
            elif _assign(day_row, values):
                report.updated["ngày"] += 1
            await _sync_items(db, day_row.id, day_spec, video_ids, report)

    await db.flush()
    csv_slugs = set(plan.programs)
    report.programs_not_in_csv = sorted(
        s for s in (await db.scalars(select(TrainingProgram.slug))).all() if s not in csv_slugs)
    used = select(ProgramDayItem.workout_video_id)
    report.unused_videos = await db.scalar(
        select(func.count()).select_from(WorkoutVideo).where(WorkoutVideo.id.not_in(used))) or 0
    report.published_programs_total = await db.scalar(
        select(func.count()).select_from(TrainingProgram).where(
            TrainingProgram.status == TrainingStatus.PUBLISHED)) or 0
    return report


async def _sync_items(db: AsyncSession, day_id: int, spec: DaySpec, video_ids: dict, report: ApplyReport) -> None:
    existing = {i.position: i for i in (await db.scalars(
        select(ProgramDayItem).where(ProgramDayItem.program_day_id == day_id))).all()}
    wanted = {i.position: i for i in spec.items}
    for position, row in existing.items():
        if position not in wanted:
            await db.delete(row)
            report.deleted["mục"] += 1
    await db.flush()
    for position, item in sorted(wanted.items()):
        values = {"workout_video_id": video_ids[item.video_key], "label": item.label, "required": item.required}
        row = existing.get(position)
        if row is None:
            db.add(ProgramDayItem(program_day_id=day_id, position=position, **values))
            report.created["mục"] += 1
        elif _assign(row, values):
            report.updated["mục"] += 1
    await db.flush()


# ── Báo cáo ──────────────────────────────────────────────────────────────────

def plan_summary(plan: SeedPlan) -> list[str]:
    """Thống kê theo kế hoạch (dùng cho cả --dry-run). Chỉ tên chương trình, số liệu và lý do trạng thái."""
    lines = ["Dấu phân cách: " + "; ".join(f"{n}: {d}" for n, d in plan.delimiters.items())]
    published_videos = sum(v.status == TrainingStatus.PUBLISHED for v in plan.videos.values())
    days = sum(len(p.days) for p in plan.programs.values())
    items = sum(len(d.items) for p in plan.programs.values() for d in p.days.values())
    lines.append(f"Video: {len(plan.videos)} ({published_videos} published) | chương trình: {len(plan.programs)} "
                 f"| ngày: {days} | mục: {items}")
    for v in plan.videos.values():
        if v.status == TrainingStatus.DRAFT:
            ident = v.youtube_id or "chưa có url"
            lines.append(f"  video draft (dòng {v.first_line}, {ident}): {'; '.join(v.draft_reasons)}")
    for p in plan.programs.values():
        rest = sum(d.is_rest for d in p.days.values())
        lines.append(f"Chương trình '{p.slug}': {p.status.value} | {len(p.days)}/{p.duration_days} ngày "
                     f"({rest} ngày nghỉ)")
        if p.draft_reasons:
            lines.append(f"  lý do draft: {'; '.join(p.draft_reasons)}")
        for n, d in sorted(p.days.items()):
            if d.is_rest:
                lines.append(f"  Ngày {n}: nghỉ")
            else:
                total, required = plan.minutes(d)
                no_time = sum(plan.videos[i.video_key].duration_min is None for i in d.items)
                text = f"  Ngày {n}: {len(d.items)} mục"
                if total is not None:
                    text += f", tổng {total} phút, " + (f"bắt buộc {required} phút" if required is not None
                                                        else "mục bắt buộc chưa có thời lượng")
                if no_time:
                    text += f" ({no_time} mục chưa có thời lượng)"
                lines.append(text)
    if not any(p.status == TrainingStatus.PUBLISHED for p in plan.programs.values()):
        lines.append("Chưa có chương trình nào published trong bộ dữ liệu này.")
    return lines
