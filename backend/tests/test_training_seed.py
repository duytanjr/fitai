"""Tests trình nạp chương trình tập luyện (services/training/seed.py, lát 9a).

CSV tạo trong tmp_path (link giả chỉ tồn tại trong test, không đưa vào data/training). Phần ghi DB dùng Postgres
thật trong transaction rollback. Không gọi Gemini hay embedding.
"""
import csv
import io
import shutil
from pathlib import Path

import pytest
from sqlalchemy import func, select

from models.training import ProgramDay, ProgramDayItem, TrainingProgram, TrainingStatus, WorkoutVideo
from services.training.seed import apply_plan, is_example, load_dir, plan_summary
from services.training.youtube import parse_youtube_url
from tests.test_meals_api import require_postgres  # noqa: F401

PROGRAM_HEAD = ["slug", "title", "description", "goal_tag", "level", "duration_days", "intensity_label", "publish"]
SCHEDULE_HEAD = ["program_slug", "day_number", "is_rest", "position", "label", "required", "url", "title", "channel",
                 "duration_min", "category", "intensity", "impact", "equipment", "level", "notes", "checked_on"]
ID_A, ID_B, ID_C = "zqTestVid01", "zqTestVid02", "zqTestVid03"


def url(youtube_id: str) -> str:
    return f"https://youtu.be/{youtube_id}"


def program(slug="zq-ba-ngay", title="Zq ba ngày", description="Chương trình thử", goal="weight_loss",
            level="beginner", days="3", label="Nhẹ", publish="true") -> list[str]:
    return [slug, title, description, goal, level, days, label, publish]


def item(day, position, youtube_id=ID_A, *, slug="zq-ba-ngay", label="", required="true", title=None,
         channel="Zq kênh", duration="10", category="strength", intensity="moderate", impact="low",
         equipment="không", level="beginner", notes="", checked_on="2026-11-01", link=None) -> list[str]:
    return [slug, str(day), "false", str(position), label, required,
            url(youtube_id) if link is None and youtube_id else (link or ""),
            title or f"Zq video {youtube_id}", channel, duration, category, intensity, impact, equipment, level,
            notes, checked_on]


def rest(day, slug="zq-ba-ngay", notes="") -> list[str]:
    row = [""] * len(SCHEDULE_HEAD)
    row[0], row[1], row[2], row[15] = slug, str(day), "true", notes
    return row


def full_schedule() -> list[list[str]]:
    return [
        item(1, 1, ID_A, label="Khởi động", required="false", duration="5", category="warmup"),
        item(1, 2, ID_B, label="Bài chính", duration="20"),
        item(1, 3, ID_C, required="false", duration="7", category="cooldown"),
        rest(2, notes="Đi bộ nhẹ"),
        item(3, 1, ID_B, duration="20"),
    ]


def write(directory: Path, programs: list[list[str]], schedule: list[list[str]], delimiter: str = ",",
          bom: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    enc = "utf-8-sig" if bom else "utf-8"

    def dump(head, rows):
        return "\n".join(delimiter.join(r) for r in [head, *rows]) + "\n"

    (directory / "programs.csv").write_text(dump(PROGRAM_HEAD, programs), encoding=enc)
    (directory / "schedule.csv").write_text(dump(SCHEDULE_HEAD, schedule), encoding=enc)
    return directory


def plan_for(tmp_path, programs=None, schedule=None, **kw):
    return load_dir(write(tmp_path, programs or [program()], full_schedule() if schedule is None else schedule, **kw))


def errors_text(plan) -> str:
    return "\n".join(plan.errors)


# ── Đọc CSV ──────────────────────────────────────────────────────────────────

def test_valid_plan_published_with_minutes(tmp_path):
    plan = plan_for(tmp_path)
    assert plan.ok, plan.errors
    p = plan.programs["zq-ba-ngay"]
    assert p.status == TrainingStatus.PUBLISHED and p.draft_reasons == []
    assert {v.youtube_id for v in plan.videos.values()} == {ID_A, ID_B, ID_C}
    assert all(v.url == f"https://www.youtube.com/watch?v={v.youtube_id}" for v in plan.videos.values())
    assert plan.minutes(p.days[1]) == (32, 20) and plan.minutes(p.days[3]) == (20, 20)
    assert p.days[2].is_rest and p.days[2].note == "Đi bộ nhẹ" and p.days[2].items == []
    summary = "\n".join(plan_summary(plan))
    assert "Ngày 1: 3 mục, tổng 32 phút, bắt buộc 20 phút" in summary and "Ngày 2: nghỉ" in summary
    assert "Video: 3 (3 published) | chương trình: 1 | ngày: 3 | mục: 4" in summary
    assert "Chưa có chương trình nào published" not in summary


@pytest.mark.parametrize("delimiter,name", [(";", "dấu chấm phẩy ';'"), ("\t", "tab"), (",", "dấu phẩy ','")])
def test_delimiter_detected_and_reported(tmp_path, delimiter, name):
    plan = plan_for(tmp_path, delimiter=delimiter)
    assert plan.ok, plan.errors
    assert plan.delimiters == {"programs.csv": name, "schedule.csv": name}
    assert plan.programs["zq-ba-ngay"].status == TrainingStatus.PUBLISHED


def test_semicolon_with_bom(tmp_path):
    plan = plan_for(tmp_path, delimiter=";", bom=True)
    assert (tmp_path / "programs.csv").read_bytes().startswith(b"\xef\xbb\xbf")
    assert plan.ok, plan.errors
    assert plan.delimiters["programs.csv"] == "dấu chấm phẩy ';'"
    assert "zq-ba-ngay" in plan.programs and plan.programs["zq-ba-ngay"].status == TrainingStatus.PUBLISHED


def test_ambiguous_delimiter_is_error(tmp_path):
    write(tmp_path, [program()], full_schedule())
    (tmp_path / "programs.csv").write_text("slug;title,description\nx;y,z\n", encoding="utf-8")
    plan = load_dir(tmp_path)
    assert not plan.ok and "programs.csv dòng 1" in errors_text(plan) and "mơ hồ" in errors_text(plan)


def test_missing_column_is_error(tmp_path):
    write(tmp_path, [program()], full_schedule())
    (tmp_path / "schedule.csv").write_text("program_slug,day_number,is_rest\nzq-ba-ngay,1,true\n", encoding="utf-8")
    plan = load_dir(tmp_path)
    assert not plan.ok and "schedule.csv dòng 1: thiếu cột" in errors_text(plan)


def test_bool_variants_and_whitespace_trim(tmp_path):
    rows = full_schedule()
    rows[0][5] = " FALSE "          # required
    rows[1][5] = "1"
    rows[3][2] = "TRUE"             # is_rest
    rows[4][5] = " True"
    rows[1][4] = "  Bài chính  "
    plan = plan_for(tmp_path, programs=[program(publish=" TRUE ")], schedule=rows)
    assert plan.ok, plan.errors
    day1 = plan.programs["zq-ba-ngay"].days[1]
    assert [i.required for i in day1.items] == [False, True, False] and day1.items[1].label == "Bài chính"
    assert plan.programs["zq-ba-ngay"].publish is True and plan.programs["zq-ba-ngay"].days[2].is_rest


def test_bad_bool_reports_line(tmp_path):
    rows = full_schedule()
    rows[1][5] = "yes"
    plan = plan_for(tmp_path, schedule=rows)
    assert "schedule.csv dòng 3: cột required phải là true/false" in errors_text(plan)


# ── Từng điều kiện lỗi ───────────────────────────────────────────────────────

def test_invalid_url_reports_line(tmp_path):
    rows = full_schedule()
    rows[2][6] = "https://youtube.com@evil.com/watch?v=zqTestVid03"
    plan = plan_for(tmp_path, schedule=rows)
    assert not plan.ok and "schedule.csv dòng 4: cột url không hợp lệ" in errors_text(plan)


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "http://youtu.be/zqTestVid03", "https://evil.com/x"])
def test_invalid_url_variants(tmp_path, bad):
    rows = full_schedule()
    rows[2][6] = bad
    assert "cột url không hợp lệ" in errors_text(plan_for(tmp_path, schedule=rows))


def test_rest_day_with_item_fields_is_error(tmp_path):
    rows = full_schedule()
    rows[3][6] = url(ID_A)
    rows[3][7] = "Zq video"
    plan = plan_for(tmp_path, schedule=rows)
    assert "schedule.csv dòng 5: ngày nghỉ không được có mục" in errors_text(plan)


def test_rest_and_training_rows_same_day_is_error(tmp_path):
    rows = full_schedule() + [item(2, 1, ID_A)]
    plan = plan_for(tmp_path, schedule=rows)
    assert "schedule.csv dòng 7: ngày 2 của 'zq-ba-ngay' đã là ngày nghỉ ở dòng 5" in errors_text(plan)


def test_training_day_without_required_item_is_error(tmp_path):
    rows = full_schedule()
    rows[4][5] = "false"
    plan = plan_for(tmp_path, schedule=rows)
    assert "ngày 3 của 'zq-ba-ngay' không có mục nào required=true" in errors_text(plan)


def test_missing_days_warning_when_not_published(tmp_path):
    plan = plan_for(tmp_path, programs=[program(days="5", publish="false")])
    assert plan.ok, plan.errors
    assert any("'zq-ba-ngay' thiếu 2/5 ngày trong lịch: 4–5" in w for w in plan.warnings)
    p = plan.programs["zq-ba-ngay"]
    assert p.status == TrainingStatus.DRAFT and "thiếu 2 ngày" in p.draft_reasons


def test_missing_days_error_when_publish_true(tmp_path):
    plan = plan_for(tmp_path, programs=[program(days="5", publish="true")])
    assert not plan.ok and "programs.csv dòng 2: 'zq-ba-ngay' thiếu 2/5 ngày" in errors_text(plan)


def test_program_without_schedule_rows(tmp_path):
    plan = plan_for(tmp_path, programs=[program(), program(slug="zq-trong", publish="false")])
    assert plan.ok, plan.errors
    p = plan.programs["zq-trong"]
    assert p.status == TrainingStatus.DRAFT and "chưa có mục nào" in p.draft_reasons
    plan = plan_for(tmp_path, programs=[program(), program(slug="zq-trong", publish="true")])
    assert "'zq-trong' thiếu 3/3 ngày" in errors_text(plan)


def test_day_beyond_duration_is_error(tmp_path):
    rows = full_schedule() + [item(4, 1, ID_A)]
    assert "schedule.csv dòng 7: day_number 4 lớn hơn duration_days 3" in errors_text(plan_for(tmp_path, schedule=rows))


@pytest.mark.parametrize("duration", ["0", "181", "abc", "10.5", "-3"])
def test_duration_min_out_of_range(tmp_path, duration):
    rows = full_schedule()
    rows[2][9] = duration
    assert "schedule.csv dòng 4: cột duration_min" in errors_text(plan_for(tmp_path, schedule=rows))


@pytest.mark.parametrize("col,value", [(10, "yoga"), (11, "extreme"), (12, "medium"), (14, "advanced"),
                                       (16, "31/02/2026")])
def test_bad_enum_or_date(tmp_path, col, value):
    rows = full_schedule()
    rows[2][col] = value
    assert f"schedule.csv dòng 4: cột {SCHEDULE_HEAD[col]}" in errors_text(plan_for(tmp_path, schedule=rows))


def test_bad_program_fields(tmp_path):
    plan = plan_for(tmp_path, programs=[program(slug="Zq Sai", goal="giam_can", days="0")])
    text = errors_text(plan)
    assert "programs.csv dòng 2: cột slug" in text and "cột goal_tag" in text and "cột duration_days" in text


def test_duplicate_slug_and_position(tmp_path):
    plan = plan_for(tmp_path, programs=[program(), program()])
    assert "programs.csv dòng 3: slug 'zq-ba-ngay' bị lặp (đã có ở dòng 2)" in errors_text(plan)
    rows = full_schedule() + [item(1, 2, ID_C, required="false", duration="7", category="cooldown")]
    assert "schedule.csv dòng 7: position 2 của ngày 1 'zq-ba-ngay' bị lặp (dòng 3)" in errors_text(
        plan_for(tmp_path, schedule=rows))


def test_unknown_program_slug(tmp_path):
    rows = full_schedule() + [item(1, 1, ID_A, slug="zq-khong-co")]
    assert "schedule.csv dòng 7: program_slug 'zq-khong-co' không có trong programs.csv" in errors_text(
        plan_for(tmp_path, schedule=rows))


def test_same_youtube_id_different_info_names_both_lines(tmp_path):
    rows = full_schedule()
    rows[4][9] = "25"                       # ID_B ở dòng 3 là 20 phút
    rows[4][8] = "Zq kênh khác"
    plan = plan_for(tmp_path, schedule=rows)
    assert ("schedule.csv dòng 6: cùng youtube_id zqTestVid02 nhưng khác thông tin đã điền ở cột "
            "channel (dòng 3), duration_min (dòng 3)") in errors_text(plan)


def test_same_youtube_id_same_info_is_merged(tmp_path):
    plan = plan_for(tmp_path)
    assert len(plan.videos) == 3     # ID_B dùng ở ngày 1 và ngày 3 → một video


def test_same_title_without_url_different_info(tmp_path):
    rows = [item(1, 1, None, title="Zq chưa có link", link=""), rest(2),
            item(3, 1, None, title="Zq chưa có link", link="", duration="12")]
    plan = plan_for(tmp_path, programs=[program(publish="false")], schedule=rows)
    assert ("cùng title 'Zq chưa có link' (chưa có url) nhưng khác thông tin đã điền ở cột duration_min "
            "(dòng 2)") in errors_text(plan)


def test_any_error_blocks_whole_plan(tmp_path):
    rows = full_schedule()
    rows[4][9] = "999"
    plan = plan_for(tmp_path, programs=[program(), program(slug="zq-khac", publish="false")], schedule=rows)
    assert not plan.ok and len(plan.errors) == 1


# ── Quy tắc trạng thái ───────────────────────────────────────────────────────

@pytest.mark.parametrize("text,expected", [("(VÍ DỤ) video", True), ("(ví dụ) x", True), ("(VI DU) x", True),
                                           ("  (VÍ DỤ)", True), ("Ví dụ thật", False), ("Video (VÍ DỤ)", False),
                                           ("", False), (None, False)])
def test_is_example(text, expected):
    assert is_example(text) is expected


def test_example_title_always_draft_even_with_url(tmp_path):
    rows = full_schedule()
    rows[1][7] = "(VÍ DỤ) bài chính"
    rows[4][7] = "(VÍ DỤ) bài chính"
    plan = plan_for(tmp_path, schedule=rows)
    assert plan.ok, plan.errors
    video = next(v for v in plan.videos.values() if v.youtube_id == ID_B)
    assert video.status == TrainingStatus.DRAFT and "title bắt đầu bằng (VÍ DỤ)" in video.draft_reasons
    p = plan.programs["zq-ba-ngay"]
    assert p.status == TrainingStatus.DRAFT and any("2/4 mục trỏ tới video draft" in r for r in p.draft_reasons)


def test_example_label_makes_video_draft(tmp_path):
    rows = full_schedule()
    rows[0][4] = "(VÍ DỤ) khởi động"
    plan = plan_for(tmp_path, schedule=rows)
    video = next(v for v in plan.videos.values() if v.youtube_id == ID_A)
    assert video.status == TrainingStatus.DRAFT and plan.programs["zq-ba-ngay"].status == TrainingStatus.DRAFT


def test_video_without_url_draft_and_program_draft_with_reason(tmp_path):
    rows = full_schedule()
    rows[2][6] = ""
    plan = plan_for(tmp_path, schedule=rows)
    assert plan.ok, plan.errors
    v = next(v for v in plan.videos.values() if v.youtube_id is None)
    assert v.status == TrainingStatus.DRAFT and v.draft_reasons == ["chưa có url"]
    p = plan.programs["zq-ba-ngay"]
    assert p.publish and p.status == TrainingStatus.DRAFT
    assert p.draft_reasons == ["1/4 mục trỏ tới video draft (dòng 4)"]
    assert "Chưa có chương trình nào published" in "\n".join(plan_summary(plan))


def test_publish_false_keeps_draft(tmp_path):
    plan = plan_for(tmp_path, programs=[program(publish="false")])
    p = plan.programs["zq-ba-ngay"]
    assert p.status == TrainingStatus.DRAFT and p.draft_reasons == ["publish=false"]
    assert all(v.status == TrainingStatus.PUBLISHED for v in plan.videos.values())


def test_example_program_description_draft(tmp_path):
    plan = plan_for(tmp_path, programs=[program(description="(VÍ DỤ) điền mô tả")])
    assert plan.programs["zq-ba-ngay"].status == TrainingStatus.DRAFT


def test_checked_on_empty_is_only_warning(tmp_path):
    rows = full_schedule()
    rows[0][16] = ""
    plan = plan_for(tmp_path, schedule=rows)
    assert plan.ok and plan.programs["zq-ba-ngay"].status == TrainingStatus.PUBLISHED
    assert any("zqTestVid01 chưa có checked_on" in w for w in plan.warnings)


REPO_TRAINING = Path(__file__).resolve().parents[1] / "data" / "training"   # trong container: /app/data/training


@pytest.fixture
def repo_plan():
    if not (REPO_TRAINING / "programs.csv").exists():
        pytest.skip("không thấy data/training")
    return load_dir(REPO_TRAINING)


def test_repo_data_loads_without_errors(repo_plan):
    """Dữ liệu thật trong repo: chỉ chạy bước kiểm tra của trình nạp, không ghi DB."""
    assert repo_plan.ok, repo_plan.errors
    assert {"nguoi-moi-14", "toan-than-28"} <= set(repo_plan.programs)


def test_repo_published_programs_are_complete_with_valid_links(repo_plan):
    published = [p for p in repo_plan.programs.values() if p.publish]
    assert published
    for prog in published:
        assert prog.status == TrainingStatus.PUBLISHED, prog.slug
        assert set(prog.days) == set(range(1, prog.duration_days + 1)), prog.slug
        for day in prog.days.values():
            assert day.is_rest or day.items, (prog.slug, day.day_number)
            for it in day.items:
                video = repo_plan.videos[it.video_key]
                assert video.url is not None, (prog.slug, day.day_number, it.position)
                assert parse_youtube_url(video.url) == (video.youtube_id, video.url)
                assert video.status == TrainingStatus.PUBLISHED, (prog.slug, day.day_number, it.position)


def test_repo_example_rows_never_published(repo_plan):
    for prog in repo_plan.programs.values():
        if is_example(prog.title) or is_example(prog.description):
            assert prog.status == TrainingStatus.DRAFT, prog.slug
    for video in repo_plan.videos.values():
        if is_example(video.title) or video.url is None:
            assert video.status == TrainingStatus.DRAFT, video.title


def test_example_title_in_copy_of_repo_data_stays_draft(repo_plan, tmp_path):
    """Bản sao dữ liệu repo (không sửa file gốc): đổi title một chương trình thành mẫu (VÍ DỤ) → draft dù publish=true."""
    text = (REPO_TRAINING / "programs.csv").read_text(encoding="utf-8-sig")
    rows = list(csv.reader(io.StringIO(text, newline="")))
    slug_col, title_col = rows[0].index("slug"), rows[0].index("title")
    target = next(r for r in rows[1:] if r[slug_col] == "nguoi-moi-14")
    target[title_col] = f"(VÍ DỤ) {target[title_col]}"
    with (tmp_path / "programs.csv").open("w", encoding="utf-8", newline="") as f:
        csv.writer(f).writerows(rows)
    shutil.copy(REPO_TRAINING / "schedule.csv", tmp_path / "schedule.csv")
    plan = load_dir(tmp_path)
    assert plan.ok, plan.errors
    assert plan.programs["nguoi-moi-14"].publish and plan.programs["nguoi-moi-14"].status == TrainingStatus.DRAFT
    assert plan.programs["toan-than-28"].status == TrainingStatus.PUBLISHED


# ── Ghi DB ───────────────────────────────────────────────────────────────────

async def counts(db) -> dict:
    out = {}
    for name, model in (("video", WorkoutVideo), ("program", TrainingProgram), ("day", ProgramDay),
                        ("item", ProgramDayItem)):
        out[name] = await db.scalar(select(func.count()).select_from(model))
    return out


async def test_apply_is_idempotent(require_postgres, db_session, tmp_path):
    plan = plan_for(tmp_path)
    before = await counts(db_session)
    first = await apply_plan(db_session, plan)
    assert first.created == {"video": 3, "chương trình": 1, "ngày": 3, "mục": 4}
    after = await counts(db_session)
    assert {k: after[k] - before[k] for k in after} == {"video": 3, "program": 1, "day": 3, "item": 4}
    second = await apply_plan(db_session, load_dir(tmp_path))
    assert second.changes == 0 and await counts(db_session) == after
    program = await db_session.scalar(select(TrainingProgram).where(TrainingProgram.slug == "zq-ba-ngay"))
    assert program.status == TrainingStatus.PUBLISHED
    video = await db_session.scalar(select(WorkoutVideo).where(WorkoutVideo.youtube_id == ID_B))
    assert video.url == f"https://www.youtube.com/watch?v={ID_B}" and video.status == TrainingStatus.PUBLISHED


async def test_reapply_removes_items_days_and_unpublishes(require_postgres, db_session, tmp_path):
    await apply_plan(db_session, plan_for(tmp_path))
    rows = [item(1, 1, ID_B, duration="20"), rest(2, notes="Đi bộ nhẹ"), rest(3)]
    report = await apply_plan(db_session, plan_for(tmp_path, programs=[program(publish="false")], schedule=rows))
    assert report.deleted == {"ngày": 0, "mục": 3} and report.updated["ngày"] == 1
    assert report.unused_videos >= 2          # ID_A, ID_C không bị xoá, chỉ được báo
    program_row = await db_session.scalar(select(TrainingProgram).where(TrainingProgram.slug == "zq-ba-ngay"))
    assert program_row.status == TrainingStatus.DRAFT
    days = (await db_session.scalars(select(ProgramDay).where(ProgramDay.program_id == program_row.id)
                                     .order_by(ProgramDay.day_number))).all()
    assert [(d.day_number, d.is_rest) for d in days] == [(1, False), (2, True), (3, True)]
    assert await db_session.scalar(select(func.count()).select_from(WorkoutVideo)
                                   .where(WorkoutVideo.youtube_id.in_([ID_A, ID_C]))) == 2

    await apply_plan(db_session, plan_for(tmp_path, programs=[program(days="1", publish="false")],
                                          schedule=[item(1, 1, ID_B, duration="20")]))
    assert await db_session.scalar(select(func.count()).select_from(ProgramDay)
                                   .where(ProgramDay.program_id == program_row.id)) == 1


async def test_url_added_later_updates_same_video_row(require_postgres, db_session, tmp_path):
    rows = full_schedule()
    rows[2][6] = ""
    rows[2][7] = "Zq giãn cơ chưa có link"
    await apply_plan(db_session, plan_for(tmp_path, schedule=rows))
    draft = await db_session.scalar(select(WorkoutVideo).where(WorkoutVideo.title == "Zq giãn cơ chưa có link"))
    assert draft.youtube_id is None and draft.status == TrainingStatus.DRAFT
    program_row = await db_session.scalar(select(TrainingProgram).where(TrainingProgram.slug == "zq-ba-ngay"))
    assert program_row.status == TrainingStatus.DRAFT

    rows[2][6] = url(ID_C)
    report = await apply_plan(db_session, plan_for(tmp_path, schedule=rows))
    assert report.created["video"] == 0 and report.updated["video"] == 1
    await db_session.refresh(draft)
    await db_session.refresh(program_row)
    assert draft.youtube_id == ID_C and draft.status == TrainingStatus.PUBLISHED
    assert program_row.status == TrainingStatus.PUBLISHED


async def test_apply_refuses_plan_with_errors(require_postgres, db_session, tmp_path):
    rows = full_schedule()
    rows[0][9] = "0"
    plan = plan_for(tmp_path, schedule=rows)
    before = await counts(db_session)
    with pytest.raises(ValueError):
        await apply_plan(db_session, plan)
    assert await counts(db_session) == before


# ── Dữ liệu tối giản: chỉ cột bắt buộc ──────────────────────────────────────

MIN_PROGRAM_HEAD = ["slug", "title", "description", "goal_tag", "level", "duration_days", "publish"]
MIN_SCHEDULE_HEAD = ["program_slug", "day_number", "is_rest", "position", "label", "required", "url"]


def write_minimal(directory: Path, programs: list[list[str]], schedule: list[list[str]],
                  program_head=MIN_PROGRAM_HEAD, schedule_head=MIN_SCHEDULE_HEAD) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    for name, head, rows in (("programs.csv", program_head, programs), ("schedule.csv", schedule_head, schedule)):
        (directory / name).write_text("\n".join(",".join(r) for r in [head, *rows]) + "\n", encoding="utf-8")
    return directory


def minimal_rows() -> tuple[list[list[str]], list[list[str]]]:
    programs = [["zq-toi-gian", "Zq tối giản", "Chỉ cột bắt buộc", "general", "beginner", "2", "true"]]
    schedule = [["zq-toi-gian", "1", "false", "1", "Khởi động", "false", url(ID_A)],
                ["zq-toi-gian", "1", "false", "2", "Bài chính", "true", url(ID_B)],
                ["zq-toi-gian", "2", "true", "", "", "", ""]]
    return programs, schedule


def test_minimal_columns_publish(tmp_path):
    plan = load_dir(write_minimal(tmp_path, *minimal_rows()))
    assert plan.ok, plan.errors
    p = plan.programs["zq-toi-gian"]
    assert p.status == TrainingStatus.PUBLISHED and p.intensity_label == ""
    video = plan.videos[("yt", ID_B)]
    assert video.title == "Bài chính"                    # title mặc định bằng label
    assert (video.channel, video.duration_min, video.category, video.level, video.equipment) == (None,) * 5
    assert video.status == TrainingStatus.PUBLISHED
    assert plan.minutes(p.days[1]) == (None, None)
    assert any(f"{ID_B} chưa có duration_min, channel, checked_on" in w for w in plan.warnings)
    summary = "\n".join(plan_summary(plan))
    assert "Ngày 1: 2 mục (2 mục chưa có thời lượng)" in summary


def test_partial_durations_sum_only_known(tmp_path):
    programs, schedule = minimal_rows()
    head = MIN_SCHEDULE_HEAD + ["duration_min"]
    schedule = [schedule[0] + ["5"], schedule[1] + [""], schedule[2] + [""]]
    plan = load_dir(write_minimal(tmp_path, programs, schedule, schedule_head=head))
    assert plan.ok, plan.errors
    # mục bắt buộc duy nhất không có thời lượng → required None; tổng chỉ tính mục có
    assert plan.minutes(plan.programs["zq-toi-gian"].days[1]) == (5, None)


def test_required_columns_still_enforced(tmp_path):
    programs, schedule = minimal_rows()
    for col in ("description", "publish"):
        head = [h for h in MIN_PROGRAM_HEAD if h != col]
        rows = [[v for h, v in zip(MIN_PROGRAM_HEAD, programs[0]) if h != col]]
        plan = load_dir(write_minimal(tmp_path, rows, schedule, program_head=head))
        assert f"programs.csv dòng 1: thiếu cột {col}" in errors_text(plan)
    for col in ("url", "label", "required", "position"):
        head = [h for h in MIN_SCHEDULE_HEAD if h != col]
        rows = [[v for h, v in zip(MIN_SCHEDULE_HEAD, r) if h != col] for r in schedule]
        plan = load_dir(write_minimal(tmp_path, programs, rows, schedule_head=head))
        assert f"schedule.csv dòng 1: thiếu cột {col}" in errors_text(plan)


def test_label_or_title_needed(tmp_path):
    programs, schedule = minimal_rows()
    schedule[1][4] = ""
    plan = load_dir(write_minimal(tmp_path, programs, schedule))
    assert "schedule.csv dòng 3: cần điền label hoặc title" in errors_text(plan)


def test_same_youtube_id_blank_cells_are_not_conflicts(tmp_path):
    rows = full_schedule()
    rows[4][8] = ""            # ID_B dòng 6: channel trống
    rows[4][10] = ""           # category trống
    rows[4][16] = ""           # checked_on trống
    rows[1][9] = ""            # ID_B dòng 3: duration_min trống, dòng 6 điền 20
    plan = plan_for(tmp_path, schedule=rows)
    assert plan.ok, plan.errors
    video = plan.videos[("yt", ID_B)]
    assert (video.channel, video.duration_min, video.category) == ("Zq kênh", 20, "strength")


def test_same_youtube_id_default_title_from_different_labels_ok(tmp_path):
    """title trống ở cả hai dòng → mặc định theo label; label khác nhau không phải mâu thuẫn."""
    programs, schedule = minimal_rows()
    programs[0][5] = "3"
    schedule = schedule + [["zq-toi-gian", "3", "false", "1", "Cardio nhẹ", "true", url(ID_B)]]
    plan = load_dir(write_minimal(tmp_path, programs, schedule))
    assert plan.ok, plan.errors
    assert plan.videos[("yt", ID_B)].title == "Bài chính"


def test_same_youtube_id_filled_title_differs_is_error(tmp_path):
    rows = full_schedule()
    rows[4][7] = "Zq tên khác"
    assert "cùng youtube_id zqTestVid02 nhưng khác thông tin đã điền ở cột title (dòng 3)" in errors_text(
        plan_for(tmp_path, schedule=rows))


async def test_minimal_apply_stores_nulls(require_postgres, db_session, tmp_path):
    await apply_plan(db_session, load_dir(write_minimal(tmp_path, *minimal_rows())))
    video = await db_session.scalar(select(WorkoutVideo).where(WorkoutVideo.youtube_id == ID_A))
    assert video.title == "Khởi động" and video.status == TrainingStatus.PUBLISHED
    assert (video.channel, video.duration_min, video.category, video.intensity, video.impact, video.equipment,
            video.level, video.checked_on) == (None,) * 8
