# app/schemas/fortune.py

from pydantic import BaseModel, Field
from datetime import date
from typing import List, Optional

class LuckScores(BaseModel):
    overall: int = Field(..., ge=1, le=100)
    wealth: int = Field(..., ge=1, le=100)
    lottery: int = Field(..., ge=1, le=100)


class LuckyElements(BaseModel):
    numbers: List[int] = Field(..., min_items=7, max_items=7)
    color: str
    direction: str


class FortuneMessages(BaseModel):
    fortune: str
    advice: str


class RankInfo(BaseModel):
    zodiac_rank: int
    total_zodiacs: int = 12
    percentile: int


class DailyFortuneResponse(BaseModel):
    user_id: str
    fortune_date: date
    zodiac_sign: str
    birth_year: int
    
    luck_scores: LuckScores
    lucky_elements: LuckyElements
    messages: FortuneMessages
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