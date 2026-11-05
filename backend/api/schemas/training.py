from typing import Optional

from pydantic import BaseModel


class ProgramSummaryOut(BaseModel):
    slug: str
    title: str
    description: str
    goal_tag: str
    level: str
    intensity_label: str
    duration_days: int
    training_days: int
    total_minutes: Optional[int]          # None khi không mục nào có thời lượng
    required_minutes: Optional[int]
    items_without_duration: int


class ProgramDaySummaryOut(BaseModel):
    day_number: int
    is_rest: bool
    note: Optional[str]
    items_count: int
    total_minutes: Optional[int]
    required_minutes: Optional[int]
    items_without_duration: int


class ProgramDetailOut(ProgramSummaryOut):
    days: list[ProgramDaySummaryOut]


class DayItemOut(BaseModel):
    position: int
    label: str
    video_title: str
    channel: Optional[str]
    category: Optional[str]
    duration_min: Optional[int]
    required: bool
    url: str
    youtube_id: str


class ProgramDayOut(BaseModel):
    program_slug: str
    program_title: str
    goal_tag: str
    duration_days: int
    day_number: int
    is_rest: bool
    note: Optional[str]
    total_minutes: Optional[int]
    required_minutes: Optional[int]
    items_without_duration: int
    items: list[DayItemOut]
