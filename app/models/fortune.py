# app/models/fortune.py

import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, String, Date, Text, Boolean, ForeignKey, DECIMAL, DateTime
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.core.database import Base

class DailyFortune(Base):
    __tablename__ = "daily_fortunes"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    fortune_date = Column(Date, nullable=False)
    
    # 운세 점수
    overall_luck = Column(Integer, nullable=False)
    wealth_luck = Column(Integer, nullable=False)
    lottery_luck = Column(Integer, nullable=False)
    
    # 행운 요소
    lucky_numbers = Column(ARRAY(Integer), nullable=False)
    lucky_color = Column(String(20))
    lucky_direction = Column(String(10))
    
    # 메시지
    fortune_message = Column(Text)
    advice = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FortuneMessage(Base):
    __tablename__ = "fortune_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    luck_range = Column(String(20), nullable=False)  # 'high', 'medium', 'low'
    category = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    is_active = Column(Boolean, default=True, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ZodiacDailyStat(Base):
    __tablename__ = "zodiac_daily_stats"
    
    id = Column(Integer, primary_key=True, index=True)
    stats_date = Column(Date, nullable=False)
    zodiac_sign = Column(String(10), nullable=False)
    
    avg_overall_luck = Column(DECIMAL(5, 2))
    avg_lottery_luck = Column(DECIMAL(5, 2))
    active_users = Column(Integer, default=0)
    predictions_count = Column(Integer, default=0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)