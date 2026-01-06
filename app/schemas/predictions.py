from pydantic import BaseModel, validator
from datetime import datetime, date
from typing import List, Optional, Dict, Any
import uuid


class PredictionRequest(BaseModel):
    strategy: str
    count: int = 1
    draw_number: Optional[int] = None

    @validator('count')
    def validate_count(cls, v):
        if v < 1 or v > 10:
            raise ValueError('Count must be between 1 and 10')
        return v

    @validator('draw_number')
    def validate_draw_number(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Draw number must be a positive integer')
        return v

    @validator('strategy')
    def validate_strategy(cls, v):
        valid_strategies = [
            "frequency_balance", "random", "zone_distribution", "pattern_similarity",
            "machine_learning", "consecutive_absence", "winner_pattern", 
            "golden_ratio", "sum_range", "ai_custom", "fortune_based"
        ]
        if v not in valid_strategies:
            raise ValueError(f'Strategy must be one of: {", ".join(valid_strategies)}')
        return v


class PredictionNumbers(BaseModel):
    num1: int
    num2: int
    num3: int
    num4: int
    num5: int
    num6: int

    @validator('num1', 'num2', 'num3', 'num4', 'num5', 'num6')
    def validate_number_range(cls, v):
        if v < 1 or v > 45:
            raise ValueError('Numbers must be between 1 and 45')
        return v

    @validator('num6')
    def validate_sorted_numbers(cls, v, values):
        nums = [values.get('num1'), values.get('num2'), values.get('num3'), 
                values.get('num4'), values.get('num5'), v]
        if sorted(nums) != nums:
            raise ValueError('Numbers must be sorted in ascending order')
        return v


class PredictionResponse(BaseModel):
    id: uuid.UUID
    strategy: str
    predictions: List[List[int]]
    confidence_score: float
    credits_used: int
    remaining_credits: int
    draw_number: int
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionDetailResponse(BaseModel):
    id: uuid.UUID
    draw_number: int
    strategy_name: str
    numbers: List[int]
    confidence_score: float
    matched_count: int
    is_winner: bool
    actual_draw: Optional[List[int]] = None
    actual_bonus: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionHistoryItem(BaseModel):
    id: uuid.UUID
    draw_number: int
    strategy_name: str
    numbers: List[int]
    confidence_score: float
    matched_count: int
    is_winner: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionHistoryResponse(BaseModel):
    total: int
    page: int
    limit: int
    total_pages: int
    predictions: List[PredictionHistoryItem]


class StrategyStats(BaseModel):
    strategy: str
    display_name: str
    total_predictions: int
    avg_matched_count: float
    win_rate: float
    total_winners: int
    confidence_avg: float


class StrategyStatsResponse(BaseModel):
    strategies: List[StrategyStats]
    total_predictions: int
    overall_win_rate: float


class UserStats(BaseModel):
    total_predictions: int
    total_credits_used: int
    best_matched_count: int
    total_winners: int
    win_rate: float
    favorite_strategy: str
    total_matches: Dict[str, int]  # "3": 5, "4": 2, "5": 1, "6": 0


class WeeklyPredictionStats(BaseModel):
    """주간 예측 생성 통계"""
    draw_number: int
    week_start: datetime
    week_end: datetime
    user_count: int
    total_average: float
    difference_from_average: int
    is_above_average: bool


class BestPredictionInfo(BaseModel):
    """최고 성과 예측 정보"""
    prediction_id: str
    draw_number: int
    draw_date: date
    predicted_numbers: List[int]
    matched_count: int
    prize_rank: Optional[int] = None
    prize_amount: int
    strategy_name: str
    created_at: datetime


class UserDashboardStats(BaseModel):
    """사용자 대시보드 통계"""
    # 기본 정보
    total_predictions: int
    total_credits_used: int
    current_credits: int
    member_since: date
    
    # 최고 성과
    best_matched_count: int
    best_prediction: Optional[BestPredictionInfo] = None
    
    # 전체 통계
    total_matches_by_count: Dict[str, int]  # "3": 5, "4": 2, "5": 1, "6": 0
    total_prize_amount: int
    total_winners: int
    win_rate: float
    
    # 최근 활동
    recent_predictions_count: int  # 최근 30일
    favorite_strategy: Optional[str] = None
    
    # 등급 및 순위 정보
    user_tier: str
    predictions_this_month: int


class UserRecentActivity(BaseModel):
    """최근 활동"""
    prediction_id: str
    draw_number: int
    predicted_numbers: List[int]
    matched_count: int
    is_winner: bool
    prize_amount: int
    strategy_name: str
    created_at: datetime


class UserDashboardResponse(BaseModel):
    """사용자 대시보드 전체 응답"""
    stats: UserDashboardStats
    recent_activities: List[UserRecentActivity]


class BestResultResponse(BaseModel):
    """사용자 최고 성과 응답"""
    has_predictions: bool
    best_matched_count: int
    best_prediction: Optional[BestPredictionInfo] = None
    total_predictions: int
    total_winners: int
    user_tier: str


class SimilarWinningResult(BaseModel):
    """유사한 당첨 결과"""
    round: int
    draw_date: date
    winning_numbers: List[int]
    bonus_number: int
    matched_count: int
    similarity_score: float
    jackpot_amount: int
    jackpot_winners: int


class SimilarResultsResponse(BaseModel):
    """유사한 당첨 결과 응답"""
    query_numbers: List[int]
    total_historical_draws: int
    similar_results: List[SimilarWinningResult]