import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class KeywordStatus(str, enum.Enum):
    RAW = "raw"
    EXPANDED = "expanded"
    ANALYZED = "analyzed"
    SELECTED = "selected"


class Keyword(Base):
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    keyword: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[KeywordStatus] = mapped_column(
        Enum(KeywordStatus, name="keyword_status"),
        nullable=False,
        default=KeywordStatus.RAW,
    )
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
