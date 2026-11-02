from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database import Base


class FoodSource(Base):
    """Nguồn dữ liệu thực phẩm. Mỗi dòng foods trích dẫn đúng nguồn của chính nó.

    id cố định (migration nạp sẵn): 1 = VN2007, 2 = USDA SR Legacy 2018.
    """
    __tablename__ = "food_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, comment="Mã ngắn")
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    authors_org: Mapped[str | None] = mapped_column(String(255), nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    license: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    fiber_type: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="Loại xơ trong cột fiber_g")
    carb_basis: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="Cơ sở của carb gốc")
