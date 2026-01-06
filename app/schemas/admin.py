from pydantic import BaseModel, Field, validator
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from app.schemas.auth import UserResponse


class AdminUserResponse(UserResponse):
    """관리자용 사용자 정보 (추가 필드 포함)"""
    provider_id: str
    role: str
    birth_year: Optional[int] = None
    adult_verify_method: Optional[str] = None
    verified_at: Optional[datetime] = None
    terms_agreed_at: datetime
    privacy_agreed_at: datetime
    marketing_agreed: bool
    updated_at: datetime


class UserListResponse(BaseModel):
    """사용자 목록 응답"""
    total: int
    page: int
    limit: int
    total_pages: int
    users: List[AdminUserResponse]


class SystemStatsResponse(BaseModel):
    """시스템 통계 응답"""
    total_users: int
    active_users: int
    total_predictions: int
    total_credits_used: int
    daily_active_users: int
    weekly_active_users: int
    monthly_active_users: int
    user_tier_distribution: Dict[str, int]
    daily_registrations: int
    weekly_registrations: int


class UserManagementRequest(BaseModel):
    """사용자 관리 요청"""
    tier: Optional[str] = Field(None, pattern="^(free|premium|vip)$")
    credits: Optional[int] = Field(None, ge=0)
    role: Optional[str] = Field(None, pattern="^(user|admin)$")
    status: Optional[str] = Field(None, pattern="^(active|dormant|withdrawn)$")
    reason: Optional[str] = None


class StrategyStats(BaseModel):
    """전략별 성과 통계"""
    strategy: str              # 전략 코드 (예: "frequency", "ml_ensemble")
    display_name: str          # 전략 한글명 (예: "빈도 분석", "앙상블 ML")
    total_predictions: int     # 총 예측 수
    avg_matched_count: float   # 평균 일치 수
    win_rate: float            # 당첨률 (3개 이상 일치 비율, 0~1 소수점)
    total_winners: int         # 총 당첨자 수 (3개 이상 일치)
    confidence_avg: float      # 평균 신뢰도 (0~1)


class PredictionStatsResponse(BaseModel):
    """예측 통계 응답"""
    total_predictions: int                      # 총 예측 수
    daily_predictions: int                      # 오늘 예측
    weekly_predictions: int                     # 주간 예측
    monthly_predictions: int                    # 월간 예측
    average_predictions_per_user: float         # 사용자당 평균
    predictions_by_strategy: Dict[str, int]     # 전략별 예측 수 분포 (차트용)
    top_strategies: List[StrategyStats]         # 전략별 성과 (테이블용)


class CreditStatsResponse(BaseModel):
    """크레딧 통계 응답"""
    total_credits_issued: int
    total_credits_used: int
    total_credits_purchased: int
    daily_credit_usage: int
    weekly_credit_usage: int
    monthly_credit_usage: int
    average_credits_per_user: float
    credit_transactions_by_type: Dict[str, int]


class LottoSyncAdminRequest(BaseModel):
    """관리자용 로또 동기화 요청"""
    start_round: Optional[int] = Field(None, description="시작 회차")
    end_round: Optional[int] = Field(None, description="종료 회차")
    force_update: bool = Field(False, description="강제 업데이트 여부")


class LottoSyncAdminResponse(BaseModel):
    """관리자용 로또 동기화 응답"""
    success: bool
    message: str
    synced_rounds: List[int]
    total_synced: int
    failed_rounds: List[int]


# 결제 관련 스키마
class AdminPaymentInfo(BaseModel):
    """관리자용 결제 정보"""
    id: str
    user_id: str
    user_nickname: Optional[str] = None
    user_email: Optional[str] = None
    payment_type: str
    amount: int
    credits_purchased: Optional[int] = None
    payment_method: Optional[str] = None
    transaction_id: Optional[str] = None
    order_id: Optional[str] = None
    payment_key: Optional[str] = None
    toss_order_id: Optional[str] = None
    failure_code: Optional[str] = None
    failure_message: Optional[str] = None
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PaymentListResponse(BaseModel):
    """결제 내역 목록 응답"""
    total: int
    page: int
    limit: int
    total_pages: int
    payments: List[AdminPaymentInfo]


class DailyRevenueChart(BaseModel):
    """일별 매출 차트 데이터"""
    date: str  # YYYY-MM-DD 형식
    revenue: int


class PaymentStatsResponse(BaseModel):
    """결제 통계 응답"""
    total_revenue: int
    today_revenue: int
    weekly_revenue: int
    monthly_revenue: int
    total_payments: int
    successful_payments: int
    failed_payments: int
    cancelled_payments: int
    success_rate: float  # 0-100 퍼센트 값
    average_payment_amount: float
    
    # 차트용 데이터
    daily_revenue_chart: List[DailyRevenueChart]  # 프론트엔드 차트용
    payment_count_by_status: Dict[str, int]  # 프론트엔드 차트용
    
    # 기존 데이터 (하위 호환)
    revenue_by_date: Dict[str, int]  # 날짜별 매출
    payments_by_status: Dict[str, int]  # 상태별 결제 건수
    payments_by_method: Dict[str, int]  # 결제 수단별 건수


class AdminCancelPaymentRequest(BaseModel):
    """관리자용 결제 취소 요청"""
    cancel_reason: str
    refund_amount: Optional[int] = None  # None이면 전액 환불
    
    @validator('cancel_reason')
    def validate_reason(cls, v):
        if not v or len(v.strip()) < 5:
            raise ValueError('취소 사유는 5자 이상 입력해주세요')
        return v.strip()


class CancelPaymentResponse(BaseModel):
    """결제 취소 응답"""
    success: bool
    payment_id: str
    cancelled_amount: int
    refunded_credits: int
    new_balance: int
    cancel_reason: str
    cancelled_at: datetime
    already_cancelled_in_gateway: bool = False  # 토스에서 이미 취소되었는지 여부


class AdminLottoDrawResponse(BaseModel):
    """관리자용 로또 회차 정보"""
    round: int
    draw_date: date
    numbers: List[int]
    bonus: int
    jackpot_amount: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AdminLottoDrawsResponse(BaseModel):
    """관리자용 로또 회차 목록 응답"""
    total: int
    page: int
    limit: int
    total_pages: int
    draws: List[AdminLottoDrawResponse]
    from_round: Optional[int] = None
    to_round: Optional[int] = None


class DailySignupPoint(BaseModel):
    """일별 가입자 데이터 포인트"""
    date: str  # YYYY-MM-DD 형식
    count: int
    cumulative: int  # 누적 가입자 수


class DailySignupsResponse(BaseModel):
    """일별 가입자 추이 응답"""
    period: str  # "last_7_days", "last_30_days"
    total_new_users: int  # 기간 내 총 신규 가입자
    data: List[DailySignupPoint]


class DailyPredictionPoint(BaseModel):
    """일별 예측 데이터 포인트"""
    date: str  # YYYY-MM-DD 형식
    count: int  # 생성된 예측 번호조합 수
    unique_users: int  # 예측을 생성한 고유 사용자 수


class DailyPredictionsResponse(BaseModel):
    """일별 예측 추이 응답"""
    period: str
    total_predictions: int  # 기간 내 총 예측 수
    total_unique_users: int  # 기간 내 예측을 생성한 총 고유 사용자 수
    data: List[DailyPredictionPoint]


class DailyCreditPoint(BaseModel):
    """일별 크레딧 데이터 포인트"""
    date: str  # YYYY-MM-DD 형식
    credits_used: int  # 사용된 크레딧 (음수 거래의 절대값 합)
    credits_earned: int  # 획득한 크레딧 (양수 거래의 합)
    net_credits: int  # 순 크레딧 변화 (earned - used)
    purchase_count: int  # 구매 건수
    prediction_usage: int  # 예측 사용 크레딧
    ad_reward: int  # 광고 보상 크레딧


class DailyCreditUsageResponse(BaseModel):
    """일별 크레딧 사용 추이 응답"""
    period: str
    total_credits_used: int  # 기간 내 총 사용 크레딧
    total_credits_earned: int  # 기간 내 총 획득 크레딧
    net_change: int  # 순 변화량
    data: List[DailyCreditPoint]


# 명세서에 맞는 간소화된 일별 통계 스키마
class SimpleDailyDataPoint(BaseModel):
    """간소화된 일별 데이터 포인트"""
    date: str  # YYYY-MM-DD 형식
    count: int


class SimpleDailyStatsResponse(BaseModel):
    """간소화된 일별 통계 응답 (명세서 형식)"""
    period: str  # "7days", "14days", "30days"
    data: List[SimpleDailyDataPoint]
    total: int