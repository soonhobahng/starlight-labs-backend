# app/schemas/fortune.py

from pydantic import BaseModel, Field
from datetime import date
from typing import List, Optional

class LuckScores(BaseModel):
    overall: int = Field(..., ge=1, le=100)
    wealth: int = Field(..., ge=1, le=100)
    lottery: int = Field(..., ge=1, le=100)
    love: Optional[int] = Field(None, ge=1, le=100)
    career: Optional[int] = Field(None, ge=1, le=100)
    health: Optional[int] = Field(None, ge=1, le=100)


class CategoryFortune(BaseModel):
    """카테고리별 운세 상세 정보"""
    score: int = Field(..., ge=1, le=100)
    title: str
    description: str


class CategoryFortunes(BaseModel):
    """모든 카테고리 운세"""
    wealth: CategoryFortune
    love: CategoryFortune
    career: CategoryFortune
    health: CategoryFortune
    lottery: CategoryFortune


class LuckyElements(BaseModel):
    numbers: List[int] = Field(..., min_items=7, max_items=7)
    color: str
    color_hex: Optional[str] = None
    direction: str
    time: Optional[str] = None  # 행운의 시간
    item: Optional[str] = None  # 행운의 아이템


class FortuneMessages(BaseModel):
    fortune: str
    advice: str
    warning: Optional[str] = None
    summary: Optional[str] = None


class TimeFortune(BaseModel):
    """시간대별 운세"""
    period: str
    score: int = Field(..., ge=1, le=100)
    message: str


class TimeFortunes(BaseModel):
    """시간대별 운세 모음"""
    morning: TimeFortune
    afternoon: TimeFortune
    evening: TimeFortune


class RankInfo(BaseModel):
    zodiac_rank: int
    total_zodiacs: int = 12
    percentile: int
    best_zodiac: Optional[str] = None
    best_match: Optional[str] = None


class DailyFortuneResponse(BaseModel):
    user_id: str
    fortune_date: date
    birth_year: int
    birth_date: Optional[date] = None
    zodiac_sign: Optional[str] = None  # 띠 (예: "말띠")
    constellation: Optional[str] = None  # 별자리 (예: "사자자리")
    mbti: Optional[str] = None  # MBTI (예: "INTJ")

    luck_scores: LuckScores
    category_fortunes: Optional[CategoryFortunes] = None  # 카테고리별 상세 정보
    lucky_elements: LuckyElements
    messages: FortuneMessages
    time_fortunes: Optional[TimeFortunes] = None  # 시간대별 운세
    rank_info: RankInfo

    class Config:
        orm_mode = True


class ZodiacRanking(BaseModel):
    rank: int
    zodiac_sign: str
    avg_luck: float
    active_users: int
    message: Optional[str] = None


class ZodiacStatsResponse(BaseModel):
    stats_date: date
    zodiac_rankings: List[ZodiacRanking]
    my_zodiac: dict


class TrendingResponse(BaseModel):
    timestamp: str
    popular_numbers: dict
    popular_strategy: dict
    community_stats: dict
    lucky_zodiacs_today: List[dict]


class GenerateWithLuckyRequest(BaseModel):
    use_lucky_numbers: bool = True
    strategy: str = "ai_ensemble"
    count: int = Field(default=5, ge=1, le=10)


class UserProfileUpdate(BaseModel):
    birth_year: int = Field(..., ge=1900, le=2100)
    fortune_enabled: bool = True


# 띠별 오늘의 운세 API 응답 스키마
class CategoryScore(BaseModel):
    """카테고리별 점수 및 설명"""
    score: int = Field(..., ge=1, le=100)
    description: str


class FortuneCategories(BaseModel):
    """운세 카테고리 모음"""
    wealth: CategoryScore
    love: CategoryScore
    health: CategoryScore
    work: CategoryScore


class LuckyInfo(BaseModel):
    """행운 정보"""
    color: str
    number: int = Field(..., ge=1, le=45)
    direction: str


class ZodiacTodayFortuneResponse(BaseModel):
    """띠별 오늘의 운세 응답"""
    date: date
    zodiac: str  # "용", "쥐" 등 (띠 없이)
    overall_score: int = Field(..., ge=1, le=100)
    message: str
    categories: FortuneCategories
    lucky: LuckyInfo
    advice: str