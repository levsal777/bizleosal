from __future__ import annotations
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, SmallInteger, Numeric
from sqlalchemy.dialects.postgresql import ENUM, ARRAY, JSONB

Base = declarative_base()
SWOT_TYPE = ENUM("strength","weakness","opportunity","threat", name="swot_type", create_type=False)

class SWOTItem(Base):
    __tablename__ = "swot_items"
    id = Column(Integer, primary_key=True)
    company_id = Column(Integer, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(SWOT_TYPE, nullable=False)
    title = Column(String(300), nullable=False)
    description = Column(Text)
    impact = Column(SmallInteger)           # 1..5
    confidence = Column(Numeric(4,3))       # 0..1
    tags = Column(ARRAY(String))
    meta = Column(JSONB)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
