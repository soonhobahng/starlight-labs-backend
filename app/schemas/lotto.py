from pydantic import BaseModel, validator
from datetime import date, datetime
from typing import List, Dict, Optional


class LottoDrawResponse(BaseModel):
    round: int
    draw_date: date
    numbers: List[int]
    bonus: int
    jackpot_amount: int
    jackpot_winners: Optional[int] = None

    @validator('numbers')
    def validate_numbers(cls, v):
        if len(v) != 6:
            raise ValueError('Numbers must contain exactly 6 items')
        if not all(1 <= num <= 45 for num in v):
            raise ValueError('All numbers must be between 1 and 45')
        if len(set(v)) != 6:
            raise ValueError('Numbers must be unique')
        if v != sorted(v):
            raise ValueError('Numbers must be sorted')
        return v

    @validator('bonus')
    def validate_bonus(cls, v):
        if not 1 <= v <= 45:
            raise ValueError('Bonus number must be between 1 and 45')
        return v

    class Config:
        from_attributes = True


class LottoDrawsResponse(BaseModel):
    total: int
    draws: List[LottoDrawResponse]
    from_round: Optional[int] = None
    to_round: Optional[int] = None


class NumberFrequency(BaseModel):
    number: int
    count: int
    percentage: float


class ZoneStats(BaseModel):
    zone: str
    range: str
    count: int
    percentage: float


class ConsecutiveAnalysis(BaseModel):
    avg_consecutive: float
    max_consecutive: int
    consecutive_frequency: Dict[str, int]  # "0": 10, "1": 25, "2": 15, ...


class SumRangeAnalysis(BaseModel):
    avg_sum: float
    min_sum: int
    max_sum: int
    sum_distribution: Dict[str, int]  # "100-110": 5, "111-120": 8, ...


class RecentTrends(BaseModel):
    hot_numbers: List[int]  # 최근 자주 나온 번호
    cold_numbers: List[int]  # 최근 안 나온 번호
    trending_up: List[int]   # 증가 추세
    trending_down: List[int] # 감소 추세


class LottoStatistics(BaseModel):
    total_draws: int
    analysis_period: str
    most_frequent: List[NumberFrequency]
    least_frequent: List[NumberFrequency]
    odd_even_ratio: Dict[str, float]
    zone_distribution: List[ZoneStats]
    recent_trends: RecentTrends
    consecutive_analysis: ConsecutiveAnalysis
    sum_range_analysis: SumRangeAnalysis
    bonus_stats: Dict[str, float]
    updated_at: datetime


class LottoSyncRequest(BaseModel):
    start_round: Optional[int] = None
    end_round: Optional[int] = None
    force_update: bool = False


class LottoSyncResponse(BaseModel):
    success: bool
    message: str
    synced_rounds: List[int]
    total_synced: int
    failed_rounds: List[int]
    sync_time: datetime


class LottoSearchRequest(BaseModel):
    numbers: List[int]
    include_bonus: bool = False

    @validator('numbers')
    def validate_numbers(cls, v):
        if len(v) < 1 or len(v) > 6:
            raise ValueError('Numbers must contain 1-6 items')
        if not all(1 <= num <= 45 for num in v):
            raise ValueError('All numbers must be between 1 and 45')
        if len(set(v)) != len(v):
            raise ValueError('Numbers must be unique')
        return v


class LottoSearchResponse(BaseModel):
    search_numbers: List[int]
    total_matches: int
    matches: List[Dict]  # round, numbers, bonus, matched_count, date