from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_, text
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, date, timezone
import math
import asyncio
import requests
from bs4 import BeautifulSoup
import logging

from app.core.database import get_db
from app.core.admin import require_admin, AdminPermissions
from app.models.models import User, Prediction, CreditTransaction, TransactionType, UserTier, LottoDraw, Strategy, Payment, PaymentStatus
from app.services.credit_service import CreditService
from app.schemas.admin import (
    AdminUserResponse, UserListResponse, SystemStatsResponse,
    UserManagementRequest, PredictionStatsResponse, StrategyStats, CreditStatsResponse,
    LottoSyncAdminRequest, LottoSyncAdminResponse, AdminLottoDrawResponse,
    AdminLottoDrawsResponse, DailySignupsResponse, DailySignupPoint,
    DailyPredictionsResponse, DailyPredictionPoint, DailyCreditUsageResponse, DailyCreditPoint,
    SimpleDailyStatsResponse, SimpleDailyDataPoint, AdminPaymentInfo, PaymentListResponse, PaymentStatsResponse,
    AdminCancelPaymentRequest, CancelPaymentResponse, DailyRevenueChart
)
from app.schemas.lotto import LottoDrawResponse

# Logger 설정 - 직접 핸들러 추가 (맨 위에 위치)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 루트 핸들러가 없으면 직접 추가
if not logger.handlers:
    import sys
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.propagate = False  # 중복 방지

# 모듈 로드 시 테스트 로그
logger.info("🔧 Admin module loaded successfully")
print("🔧 Admin module loaded - print test")  # 비교용

router = APIRouter(prefix="/admin", tags=["관리자"])


@router.get("/test-admin-logging")
async def test_admin_logging():
    """Admin 로깅 테스트"""
    logger.debug("🐛 ADMIN DEBUG: This is a debug message")
    logger.info("ℹ️ ADMIN INFO: This is an info message")
    logger.warning("⚠️ ADMIN WARNING: This is a warning message")
    logger.error("❌ ADMIN ERROR: This is an error message")
    
    print("🔧 ADMIN PRINT: This is a print message")
    
    import sys
    sys.stdout.flush()
    sys.stderr.flush()
    
    return {
        "message": "Admin logging test completed",
        "logger_name": logger.name,
        "logger_level": logger.level,
        "logger_effective_level": logger.getEffectiveLevel(),
        "logger_handlers": len(logger.handlers)
    }


@router.get("/users", response_model=UserListResponse)
async def get_users(
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    search: Optional[str] = Query(None, description="닉네임/이메일 검색"),
    tier: Optional[str] = Query(None, description="등급 필터"),
    role: Optional[str] = Query(None, description="역할 필터"),
    status: Optional[str] = Query(None, description="상태 필터"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """사용자 목록 조회 (관리자 전용)"""
    
    # 기본 쿼리
    base_query = db.query(User)
    
    # 검색 필터
    if search:
        base_query = base_query.filter(
            or_(
                User.nickname.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
        )
    
    # 등급 필터
    if tier:
        base_query = base_query.filter(User.tier == tier)
    
    # 역할 필터
    if role:
        base_query = base_query.filter(User.role == role)
    
    # 상태 필터
    if status:
        base_query = base_query.filter(User.status == status)
    
    # 총 개수
    total = base_query.count()
    
    # 페이지네이션
    offset = (page - 1) * limit
    users = base_query.order_by(desc(User.created_at)).offset(offset).limit(limit).all()
    
    # 응답 데이터 구성
    user_items = [
        AdminUserResponse(
            id=str(user.id),
            provider=user.provider,
            provider_id=user.provider_id,
            nickname=user.nickname,
            email=user.email,
            phone=user.phone,
            profile_image_url=user.profile_image_url,
            tier=user.tier,
            credits=user.credits,
            role=user.role,
            is_adult_verified=user.is_adult_verified,
            status=user.status,
            birth_year=user.birth_year,
            adult_verify_method=user.adult_verify_method,
            verified_at=user.verified_at,
            terms_agreed_at=user.terms_agreed_at,
            privacy_agreed_at=user.privacy_agreed_at,
            marketing_agreed=user.marketing_agreed,
            created_at=user.created_at,
            last_login_at=user.last_login_at,
            updated_at=user.updated_at
        )
        for user in users
    ]
    
    total_pages = math.ceil(total / limit)
    
    return UserListResponse(
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        users=user_items
    )


@router.put("/users/{user_id}")
async def manage_user(
    user_id: str,
    request: UserManagementRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """사용자 관리 (등급, 크레딧, 역할, 상태 변경)"""
    
    # 대상 사용자 조회
    target_user = db.query(User).filter(User.id == user_id).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다"
        )
    
    # 변경사항 적용
    if request.tier is not None:
        target_user.tier = request.tier
    
    if request.credits is not None:
        target_user.credits = request.credits
    
    if request.role is not None:
        target_user.role = request.role
    
    if request.status is not None:
        target_user.status = request.status
    
    db.commit()
    db.refresh(target_user)
    
    return {"message": "사용자 정보가 성공적으로 업데이트되었습니다"}


@router.get("/stats", response_model=SystemStatsResponse)
async def get_system_stats(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """시스템 전체 통계"""
    
    now = datetime.utcnow()
    today = now.date()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    
    # 사용자 통계
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.status == 'active').count()
    
    # 일간/주간/월간 활성 사용자
    daily_active = db.query(User).filter(
        func.date(User.last_login_at) == today
    ).count()
    
    weekly_active = db.query(User).filter(
        User.last_login_at >= week_ago
    ).count()
    
    monthly_active = db.query(User).filter(
        User.last_login_at >= month_ago
    ).count()
    
    # 등급별 분포
    tier_stats = db.query(
        User.tier,
        func.count(User.id)
    ).group_by(User.tier).all()
    
    tier_distribution = {tier: count for tier, count in tier_stats}
    
    # 가입자 통계
    daily_registrations = db.query(User).filter(
        func.date(User.created_at) == today
    ).count()
    
    weekly_registrations = db.query(User).filter(
        User.created_at >= week_ago
    ).count()
    
    # 예측 통계
    total_predictions = db.query(Prediction).count()
    
    # 크레딧 사용 통계
    total_credits_used = db.query(
        func.sum(CreditTransaction.amount)
    ).filter(
        CreditTransaction.type == TransactionType.prediction
    ).scalar() or 0
    
    return SystemStatsResponse(
        total_users=total_users,
        active_users=active_users,
        total_predictions=total_predictions,
        total_credits_used=abs(total_credits_used),
        daily_active_users=daily_active,
        weekly_active_users=weekly_active,
        monthly_active_users=monthly_active,
        user_tier_distribution=tier_distribution,
        daily_registrations=daily_registrations,
        weekly_registrations=weekly_registrations
    )


@router.get("/stats/predictions", response_model=PredictionStatsResponse)
async def get_prediction_stats(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """예측 관련 상세 통계"""
    
    # 전략명 한글 매핑
    STRATEGY_DISPLAY_NAMES = {
        "frequency_balance": "빈도 분석",
        "random": "랜덤",
        "zone_distribution": "구간 분석",
        "pattern_similarity": "패턴 분석",
        "machine_learning": "머신러닝",
        "consecutive_absence": "연속 미출현",
        "winner_pattern": "당첨 패턴",
        "golden_ratio": "황금비율",
        "sum_range": "합계 범위",
        "ai_custom": "AI 커스텀",
        "hot_cold": "핫/콜드 번호",
        "zone_balance": "구간 밸런스",
        "number_sum": "번호 합계 분석"
    }
    
    now = datetime.utcnow()
    today = now.date()
    
    # 이번 주 월요일 00:00 UTC 계산
    days_since_monday = now.weekday()  # 월요일=0, 일요일=6
    monday_this_week = now - timedelta(days=days_since_monday)
    monday_this_week = monday_this_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 이번 달 1일 00:00 UTC 계산  
    first_day_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # 전체 예측 수
    total_predictions = db.query(Prediction).count()
    
    # 전략별 예측 수 분포 (차트용)
    strategy_counts = db.query(
        Prediction.strategy_name,
        func.count(Prediction.id)
    ).group_by(Prediction.strategy_name).all()
    
    predictions_by_strategy = {strategy: count for strategy, count in strategy_counts}
    
    # 일간/주간/월간 예측 수
    daily_predictions = db.query(Prediction).filter(
        func.date(Prediction.created_at) == today
    ).count()
    
    weekly_predictions = db.query(Prediction).filter(
        Prediction.created_at >= monday_this_week
    ).count()
    
    monthly_predictions = db.query(Prediction).filter(
        Prediction.created_at >= first_day_this_month
    ).count()
    
    # 사용자당 평균 예측 수 (활성 사용자 기준)
    total_active_users = db.query(User).filter(User.status == 'active').count()
    average_predictions_per_user = total_predictions / total_active_users if total_active_users > 0 else 0
    
    # 전략별 성과 통계 (모든 예측 포함, 성과 계산은 확인된 것만)
    from sqlalchemy import case
    
    strategy_performance_stats = db.query(
        Prediction.strategy_name,
        Strategy.display_name,
        func.count(Prediction.id).label('total_predictions'),
        func.avg(case((Prediction.checked_at.is_not(None), Prediction.matched_count))).label('avg_matched_count'),
        func.sum(case((and_(Prediction.checked_at.is_not(None), Prediction.matched_count >= 3), 1), else_=0)).label('total_winners'),
        func.avg(case((Prediction.checked_at.is_not(None), Prediction.confidence_score))).label('confidence_avg'),
        func.count(case((Prediction.checked_at.is_not(None), Prediction.id))).label('checked_predictions')
    ).outerjoin(
        Strategy, Strategy.name == Prediction.strategy_name
    ).group_by(
        Prediction.strategy_name, Strategy.display_name
    ).order_by(
        desc('total_predictions')
    ).all()
    
    # StrategyStats 객체 생성
    top_strategies = []
    for stat in strategy_performance_stats:
        strategy_name = stat.strategy_name
        display_name = stat.display_name or STRATEGY_DISPLAY_NAMES.get(strategy_name, strategy_name)
        total_preds = stat.total_predictions
        avg_matched = stat.avg_matched_count or 0
        total_winners = stat.total_winners or 0
        confidence_avg = stat.confidence_avg or 0
        checked_preds = stat.checked_predictions or 0
        win_rate = (total_winners / checked_preds) if checked_preds > 0 else 0
        
        top_strategies.append(StrategyStats(
            strategy=strategy_name,
            display_name=display_name,
            total_predictions=total_preds,
            avg_matched_count=round(avg_matched, 2),
            win_rate=round(win_rate, 3),
            total_winners=total_winners,
            confidence_avg=round(confidence_avg, 3)
        ))
    
    return PredictionStatsResponse(
        total_predictions=total_predictions,
        daily_predictions=daily_predictions,
        weekly_predictions=weekly_predictions,
        monthly_predictions=monthly_predictions,
        average_predictions_per_user=round(average_predictions_per_user, 2),
        predictions_by_strategy=predictions_by_strategy,
        top_strategies=top_strategies
    )


@router.get("/stats/credits", response_model=CreditStatsResponse)
async def get_credit_stats(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """크레딧 관련 통계"""
    
    now = datetime.utcnow()
    today = now.date()
    
    # 이번 주 월요일 00:00 UTC 계산
    days_since_monday = now.weekday()  # 월요일=0, 일요일=6
    monday_this_week = now - timedelta(days=days_since_monday)
    monday_this_week = monday_this_week.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # 이번 달 1일 00:00 UTC 계산  
    first_day_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # 전체 크레딧 발급/사용량
    total_credits_issued = db.query(
        func.sum(CreditTransaction.amount)
    ).filter(
        CreditTransaction.amount > 0
    ).scalar() or 0
    
    total_credits_used = db.query(
        func.sum(CreditTransaction.amount)
    ).filter(
        CreditTransaction.amount < 0
    ).scalar() or 0
    
    # 구매를 통한 크레딧 발급
    total_credits_purchased = db.query(
        func.sum(CreditTransaction.amount)
    ).filter(
        CreditTransaction.type == TransactionType.purchase
    ).scalar() or 0
    
    # 일간/주간/월간 크레딧 사용량
    daily_credit_usage = db.query(
        func.sum(CreditTransaction.amount)
    ).filter(
        func.date(CreditTransaction.created_at) == today,
        CreditTransaction.amount < 0
    ).scalar() or 0
    
    weekly_credit_usage = db.query(
        func.sum(CreditTransaction.amount)
    ).filter(
        CreditTransaction.created_at >= monday_this_week,
        CreditTransaction.amount < 0
    ).scalar() or 0
    
    monthly_credit_usage = db.query(
        func.sum(CreditTransaction.amount)
    ).filter(
        CreditTransaction.created_at >= first_day_this_month,
        CreditTransaction.amount < 0
    ).scalar() or 0
    
    # 사용자당 평균 크레딧 (활성 사용자 기준)
    average_credits_per_user = db.query(func.avg(User.credits)).filter(
        User.status == 'active'
    ).scalar() or 0
    
    # 거래 유형별 금액 통계 (절대값 합계)
    transaction_stats = db.query(
        CreditTransaction.type,
        func.sum(func.abs(CreditTransaction.amount))
    ).group_by(CreditTransaction.type).all()
    
    credit_transactions_by_type = {
        transaction_type.value: int(amount_sum) if amount_sum else 0
        for transaction_type, amount_sum in transaction_stats
    }
    
    return CreditStatsResponse(
        total_credits_issued=total_credits_issued,
        total_credits_used=abs(total_credits_used),
        total_credits_purchased=total_credits_purchased,
        daily_credit_usage=abs(daily_credit_usage),
        weekly_credit_usage=abs(weekly_credit_usage),
        monthly_credit_usage=abs(monthly_credit_usage),
        average_credits_per_user=round(average_credits_per_user, 2),
        credit_transactions_by_type=credit_transactions_by_type
    )


@router.get("/stats/daily-signups", response_model=DailySignupsResponse)
async def get_daily_signups(
    days: int = Query(7, ge=1, le=30, description="조회 기간 (일)"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    일별 신규 가입자 추이 조회
    
    - 지정된 기간 동안의 일별 가입자 수
    - 데이터가 없는 날짜는 0으로 채움
    - 누적 가입자 수 포함
    """
    
    # 1. 날짜 범위 계산 (한국시간 기준)
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)
    
    # 2. 일별 가입자 수 조회 (한국시간으로 변환)
    query = text("""
        SELECT 
            DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul') as date,
            COUNT(*) as count
        FROM users
        WHERE created_at >= :start_date
          AND created_at < :end_date + INTERVAL '1 day'
        GROUP BY DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul')
        ORDER BY date ASC
    """)
    
    result = db.execute(query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()
    
    # 3. 날짜별 데이터 딕셔너리 생성
    signup_dict = {str(row.date): row.count for row in result}
    
    # 4. 모든 날짜 채우기 (데이터 없는 날은 0)
    data = []
    cumulative = 0
    current_date = start_date
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        count = signup_dict.get(date_str, 0)
        cumulative += count
        
        data.append(DailySignupPoint(
            date=date_str,
            count=count,
            cumulative=cumulative
        ))
        current_date += timedelta(days=1)
    
    return DailySignupsResponse(
        period=f"last_{days}_days",
        total_new_users=cumulative,
        data=data
    )


# 명세서에 맞는 간소화된 일별 가입자 통계 (호환성)
@router.get("/stats/daily-signups-simple", response_model=SimpleDailyStatsResponse)
async def get_daily_signups_simple(
    days: int = Query(7, ge=1, le=30, description="조회 기간 (일)"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    일별 신규 가입자 추이 조회 (명세서 형식)
    """
    
    # 1. 날짜 범위 계산
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)
    
    # 2. 일별 가입자 수 조회
    query = text("""
        SELECT 
            DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul') as date,
            COUNT(*) as count
        FROM users
        WHERE created_at >= :start_date
          AND created_at < :end_date + INTERVAL '1 day'
        GROUP BY DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul')
        ORDER BY date ASC
    """)
    
    result = db.execute(query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()
    
    # 3. 날짜별 데이터 딕셔너리 생성
    signup_dict = {str(row.date): row.count for row in result}
    
    # 4. 모든 날짜 채우기 (데이터 없는 날은 0)
    data = []
    total = 0
    current_date = start_date
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        count = signup_dict.get(date_str, 0)
        total += count
        
        data.append(SimpleDailyDataPoint(
            date=date_str,
            count=count
        ))
        current_date += timedelta(days=1)
    
    return SimpleDailyStatsResponse(
        period=f"{days}days",
        data=data,
        total=total
    )


@router.get("/stats/daily-predictions", response_model=DailyPredictionsResponse)
async def get_daily_predictions(
    days: int = Query(7, ge=1, le=30, description="조회 기간 (일)"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    일별 예측 생성량 추이 조회
    
    - 지정된 기간 동안의 일별 예측 생성 수
    - 예측을 생성한 고유 사용자 수 포함
    - 데이터가 없는 날짜는 0으로 채움
    """
    
    # 1. 날짜 범위 계산 (한국시간 기준)
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)
    
    # 2. 일별 예측 생성 수 및 고유 사용자 수 조회 (한국시간으로 변환)
    query = text("""
        SELECT 
            DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul') as date,
            COUNT(*) as count,
            COUNT(DISTINCT user_id) as unique_users
        FROM predictions
        WHERE created_at >= :start_date
          AND created_at < :end_date + INTERVAL '1 day'
        GROUP BY DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul')
        ORDER BY date ASC
    """)
    
    result = db.execute(query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()
    
    # 3. 날짜별 데이터 딕셔너리 생성
    prediction_dict = {
        str(row.date): {"count": row.count, "unique_users": row.unique_users}
        for row in result
    }
    
    # 4. 모든 날짜 채우기
    data = []
    total_predictions = 0
    current_date = start_date
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        day_data = prediction_dict.get(date_str, {"count": 0, "unique_users": 0})
        
        total_predictions += day_data["count"]
        
        data.append(DailyPredictionPoint(
            date=date_str,
            count=day_data["count"],
            unique_users=day_data["unique_users"]
        ))
        current_date += timedelta(days=1)
    
    # 5. 전체 기간의 고유 사용자 수 계산
    total_unique_query = text("""
        SELECT COUNT(DISTINCT user_id) as unique_users
        FROM predictions
        WHERE created_at >= :start_date
          AND created_at < :end_date + INTERVAL '1 day'
    """)
    
    total_unique_result = db.execute(total_unique_query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchone()
    
    return DailyPredictionsResponse(
        period=f"last_{days}_days",
        total_predictions=total_predictions,
        total_unique_users=total_unique_result.unique_users if total_unique_result else 0,
        data=data
    )


# 명세서에 맞는 간소화된 일별 예측 통계 (호환성)
@router.get("/stats/daily-predictions-simple", response_model=SimpleDailyStatsResponse)
async def get_daily_predictions_simple(
    days: int = Query(7, ge=1, le=30, description="조회 기간 (일)"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    일별 예측 생성량 추이 조회 (명세서 형식)
    """
    
    # 1. 날짜 범위 계산
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)
    
    # 2. 일별 예측 생성 수 조회
    query = text("""
        SELECT 
            DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul') as date,
            COUNT(*) as count
        FROM predictions
        WHERE created_at >= :start_date
          AND created_at < :end_date + INTERVAL '1 day'
        GROUP BY DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul')
        ORDER BY date ASC
    """)
    
    result = db.execute(query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()
    
    # 3. 날짜별 데이터 딕셔너리 생성
    prediction_dict = {str(row.date): row.count for row in result}
    
    # 4. 모든 날짜 채우기
    data = []
    total = 0
    current_date = start_date
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        count = prediction_dict.get(date_str, 0)
        total += count
        
        data.append(SimpleDailyDataPoint(
            date=date_str,
            count=count
        ))
        current_date += timedelta(days=1)
    
    return SimpleDailyStatsResponse(
        period=f"{days}days",
        data=data,
        total=total
    )


@router.get("/stats/daily-credit-usage", response_model=DailyCreditUsageResponse)
async def get_daily_credit_usage(
    days: int = Query(7, ge=1, le=30, description="조회 기간 (일)"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    일별 크레딧 사용량 추이 조회
    
    - 지정된 기간 동안의 일별 크레딧 사용/획득량
    - 거래 유형별 세부 분류
    - 데이터가 없는 날짜는 0으로 채움
    """
    
    # 1. 날짜 범위 계산 (한국시간 기준)
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)
    
    # 2. 일별 크레딧 거래 집계 (한국시간으로 변환)
    query = text("""
        SELECT 
            DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul') as date,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as credits_used,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) as credits_earned,
            COUNT(CASE WHEN type = 'purchase' THEN 1 END) as purchase_count,
            SUM(CASE WHEN type = 'prediction' THEN ABS(amount) ELSE 0 END) as prediction_usage,
            SUM(CASE WHEN type = 'ad_reward' THEN amount ELSE 0 END) as ad_reward
        FROM credit_transactions
        WHERE created_at >= :start_date
          AND created_at < :end_date + INTERVAL '1 day'
        GROUP BY DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul')
        ORDER BY date ASC
    """)
    
    result = db.execute(query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()
    
    # 3. 날짜별 데이터 딕셔너리 생성
    credit_dict = {
        str(row.date): {
            "credits_used": int(row.credits_used or 0),
            "credits_earned": int(row.credits_earned or 0),
            "purchase_count": int(row.purchase_count or 0),
            "prediction_usage": int(row.prediction_usage or 0),
            "ad_reward": int(row.ad_reward or 0)
        }
        for row in result
    }
    
    # 4. 모든 날짜 채우기
    data = []
    total_used = 0
    total_earned = 0
    current_date = start_date
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        day_data = credit_dict.get(date_str, {
            "credits_used": 0,
            "credits_earned": 0,
            "purchase_count": 0,
            "prediction_usage": 0,
            "ad_reward": 0
        })
        
        total_used += day_data["credits_used"]
        total_earned += day_data["credits_earned"]
        
        data.append(DailyCreditPoint(
            date=date_str,
            credits_used=day_data["credits_used"],
            credits_earned=day_data["credits_earned"],
            net_credits=day_data["credits_earned"] - day_data["credits_used"],
            purchase_count=day_data["purchase_count"],
            prediction_usage=day_data["prediction_usage"],
            ad_reward=day_data["ad_reward"]
        ))
        current_date += timedelta(days=1)
    
    return DailyCreditUsageResponse(
        period=f"last_{days}_days",
        total_credits_used=total_used,
        total_credits_earned=total_earned,
        net_change=total_earned - total_used,
        data=data
    )


# 명세서에 맞는 간소화된 일별 크레딧 사용량 통계 (호환성)
@router.get("/stats/daily-credit-usage-simple", response_model=SimpleDailyStatsResponse)
async def get_daily_credit_usage_simple(
    days: int = Query(7, ge=1, le=30, description="조회 기간 (일)"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    일별 크레딧 사용량 추이 조회 (명세서 형식)
    """
    
    # 1. 날짜 범위 계산
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=days - 1)
    
    # 2. 일별 크레딧 사용량 조회 (사용된 크레딧만)
    query = text("""
        SELECT 
            DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul') as date,
            SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END) as count
        FROM credit_transactions
        WHERE created_at >= :start_date
          AND created_at < :end_date + INTERVAL '1 day'
        GROUP BY DATE(created_at AT TIME ZONE 'UTC' AT TIME ZONE 'Asia/Seoul')
        ORDER BY date ASC
    """)
    
    result = db.execute(query, {
        "start_date": start_date,
        "end_date": end_date
    }).fetchall()
    
    # 3. 날짜별 데이터 딕셔너리 생성
    credit_dict = {str(row.date): int(row.count or 0) for row in result}
    
    # 4. 모든 날짜 채우기
    data = []
    total = 0
    current_date = start_date
    
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        count = credit_dict.get(date_str, 0)
        total += count
        
        data.append(SimpleDailyDataPoint(
            date=date_str,
            count=count
        ))
        current_date += timedelta(days=1)
    
    return SimpleDailyStatsResponse(
        period=f"{days}days",
        data=data,
        total=total
    )


@router.post("/lotto/sync", response_model=LottoSyncAdminResponse)
async def sync_lotto_data_admin(
    request: LottoSyncAdminRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    관리자용 로또 데이터 동기화
    - 관리자 페이지에서 버튼 클릭으로 실행 가능
    - 동행복권 API/웹스크래핑을 통한 최신 데이터 수집
    """
    
    sync_start_time = datetime.utcnow()
    synced_rounds = []
    failed_rounds = []
    total_predictions_updated = 0
    
    try:
        # 동기화할 범위 결정
        if request.start_round and request.end_round:
            start_round = request.start_round
            end_round = request.end_round
        else:
            # 최신 회차부터 역순으로 10회차
            latest_draw = db.query(LottoDraw).order_by(desc(LottoDraw.round)).first()
            if latest_draw:
                start_round = latest_draw.round + 1
                end_round = start_round + 9
            else:
                # DB가 비어있으면 최근 회차부터
                start_round = await _get_latest_round_number()
                end_round = start_round
        
        # 각 회차별로 데이터 가져오기
        for round_num in range(start_round, end_round + 1):
            try:
                # 이미 존재하는지 확인
                existing = db.query(LottoDraw).filter(LottoDraw.round == round_num).first()
                if existing and not request.force_update:
                    continue
                
                # 데이터 가져오기 (웹 스크래핑)
                draw_data = await _fetch_lotto_data(round_num)
                
                if draw_data:
                    if existing:
                        # 업데이트
                        existing.draw_date = draw_data['draw_date']
                        existing.num1 = draw_data['numbers'][0]
                        existing.num2 = draw_data['numbers'][1]
                        existing.num3 = draw_data['numbers'][2]
                        existing.num4 = draw_data['numbers'][3]
                        existing.num5 = draw_data['numbers'][4]
                        existing.num6 = draw_data['numbers'][5]
                        existing.bonus = draw_data['bonus']
                        existing.jackpot_winners = draw_data['jackpot_winners']
                        existing.jackpot_amount = draw_data['jackpot_amount']
                    else:
                        # 새로 생성
                        new_draw = LottoDraw(
                            round=round_num,
                            draw_date=draw_data['draw_date'],
                            num1=draw_data['numbers'][0],
                            num2=draw_data['numbers'][1],
                            num3=draw_data['numbers'][2],
                            num4=draw_data['numbers'][3],
                            num5=draw_data['numbers'][4],
                            num6=draw_data['numbers'][5],
                            bonus=draw_data['bonus'],
                            jackpot_winners=draw_data['jackpot_winners'],
                            jackpot_amount=draw_data['jackpot_amount']
                        )
                        db.add(new_draw)
                    
                    synced_rounds.append(round_num)
                    
                    # 해당 회차의 예측들 당첨 여부 업데이트
                    try:
                        # 로또 데이터 먼저 커밋
                        db.commit()
                        
                        prediction_updated_count = await _update_predictions_for_draw(
                            db, round_num, draw_data['numbers'], draw_data['bonus']
                        )
                        
                        # 예측 업데이트도 별도 커밋
                        if prediction_updated_count > 0:
                            db.flush()  # 먼저 flush
                            db.commit()
                            logger.info(f"Round {round_num}: Updated and committed {prediction_updated_count} predictions")
                            print(f"[ADMIN] Round {round_num}: Updated and committed {prediction_updated_count} predictions")
                            
                            # 커밋 후 실제 업데이트 확인
                            verify_count = db.query(Prediction).filter(
                                Prediction.draw_number == round_num,
                                Prediction.checked_at.is_not(None)
                            ).count()
                            logger.info(f"Round {round_num}: Verification - {verify_count} predictions now have checked_at")
                        else:
                            logger.warning(f"Round {round_num}: No predictions to update")
                            
                        total_predictions_updated += prediction_updated_count
                    except Exception as pred_error:
                        logger.error(f"Failed to update predictions for round {round_num}: {pred_error}")
                        print(f"[ADMIN ERROR] Failed to update predictions for round {round_num}: {pred_error}")
                        db.rollback()
                else:
                    failed_rounds.append(round_num)
                
                # API 호출 제한 고려
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Failed to sync round {round_num}: {e}")
                failed_rounds.append(round_num)
        
        # 개별 커밋으로 처리하므로 여기서는 커밋하지 않음
        
        sync_end_time = datetime.utcnow()
        sync_duration = (sync_end_time - sync_start_time).total_seconds()
        
        if len(failed_rounds) == 0:
            success = True
            message = f"동기화 완료: {len(synced_rounds)}개 회차, {total_predictions_updated}개 예측 업데이트"
        else:
            success = False
            message = f"일부 실패: {len(synced_rounds)}개 성공, {len(failed_rounds)}개 실패, {total_predictions_updated}개 예측 업데이트"
        
        return LottoSyncAdminResponse(
            success=success,
            message=message,
            synced_rounds=synced_rounds,
            total_synced=len(synced_rounds),
            failed_rounds=failed_rounds,
            total_predictions_updated=total_predictions_updated,
            sync_duration_seconds=round(sync_duration, 2),
            sync_time=sync_end_time
        )
        
    except Exception as e:
        db.rollback()
        sync_end_time = datetime.utcnow()
        sync_duration = (sync_end_time - sync_start_time).total_seconds()
        
        return LottoSyncAdminResponse(
            success=False,
            message=f"동기화 실패: {str(e)}",
            synced_rounds=synced_rounds,
            total_synced=len(synced_rounds),
            failed_rounds=failed_rounds,
            total_predictions_updated=total_predictions_updated,
            sync_duration_seconds=round(sync_duration, 2),
            sync_time=sync_end_time
        )


@router.get("/lotto/draws", response_model=AdminLottoDrawsResponse)
async def get_lotto_draws_admin(
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    from_round: Optional[int] = Query(None, description="시작 회차"),
    to_round: Optional[int] = Query(None, description="종료 회차"),
    search_round: Optional[int] = Query(None, description="특정 회차 검색"),
    sort_order: str = Query("desc", description="정렬 순서 (desc: 최신순, asc: 오래된순)"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    관리자용 로또 회차 전체 목록 조회 (페이징)
    - 전체 회차 정보를 페이징으로 조회
    - 회차 범위 필터링 가능
    - 특정 회차 검색 가능
    - 정렬 순서 변경 가능
    """
    
    # 기본 쿼리
    query = db.query(LottoDraw)
    
    # 특정 회차 검색
    if search_round:
        query = query.filter(LottoDraw.round == search_round)
    
    # 범위 필터링
    elif from_round and to_round:
        if from_round > to_round:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="from_round는 to_round보다 작거나 같아야 합니다"
            )
        query = query.filter(and_(
            LottoDraw.round >= from_round,
            LottoDraw.round <= to_round
        ))
    elif from_round:
        query = query.filter(LottoDraw.round >= from_round)
    elif to_round:
        query = query.filter(LottoDraw.round <= to_round)
    
    # 총 개수
    total = query.count()
    
    # 정렬
    if sort_order == "asc":
        query = query.order_by(LottoDraw.round.asc())
    else:  # desc
        query = query.order_by(LottoDraw.round.desc())
    
    # 페이지네이션
    offset = (page - 1) * limit
    draws = query.offset(offset).limit(limit).all()
    
    # 응답 데이터 구성
    draw_responses = []
    for draw in draws:
        numbers = [draw.num1, draw.num2, draw.num3, draw.num4, draw.num5, draw.num6]
        draw_responses.append(AdminLottoDrawResponse(
            round=draw.round,
            draw_date=draw.draw_date,
            numbers=numbers,
            bonus=draw.bonus,
            jackpot_amount=draw.jackpot_amount,
            created_at=draw.created_at,
            updated_at=draw.updated_at
        ))
    
    total_pages = math.ceil(total / limit) if total > 0 else 0
    
    return AdminLottoDrawsResponse(
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        draws=draw_responses,
        from_round=from_round,
        to_round=to_round
    )


@router.delete("/lotto/draws/{round_number}")
async def delete_lotto_draw_admin(
    round_number: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    관리자용 특정 회차 삭제
    - 잘못된 데이터나 테스트 데이터 삭제시 사용
    """
    
    if round_number < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="회차 번호는 1 이상이어야 합니다"
        )
    
    draw = db.query(LottoDraw).filter(LottoDraw.round == round_number).first()
    
    if not draw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{round_number}회차 데이터를 찾을 수 없습니다"
        )
    
    db.delete(draw)
    db.commit()
    
    return {"message": f"{round_number}회차 데이터가 성공적으로 삭제되었습니다"}


@router.get("/predictions/status/{round_number}")
async def check_predictions_status(
    round_number: int,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    특정 회차의 예측 상태 확인 (관리자용)
    """
    
    # 해당 회차의 모든 예측 수
    total_predictions = db.query(Prediction).filter(
        Prediction.draw_number == round_number
    ).count()
    
    # 체크된 예측 수
    checked_predictions = db.query(Prediction).filter(
        Prediction.draw_number == round_number,
        Prediction.checked_at.is_not(None)
    ).count()
    
    # 당첨 예측 수
    winning_predictions = db.query(Prediction).filter(
        Prediction.draw_number == round_number,
        Prediction.is_winner == True
    ).count()
    
    # 최근 몇 개 예측 예시
    sample_predictions = db.query(Prediction).filter(
        Prediction.draw_number == round_number
    ).order_by(desc(Prediction.created_at)).limit(5).all()
    
    samples = []
    for pred in sample_predictions:
        numbers = [getattr(pred, f'num{i}') for i in range(1, 7) if getattr(pred, f'num{i}') is not None]
        samples.append({
            'id': str(pred.id),
            'numbers': numbers,
            'matched_count': pred.matched_count,
            'is_winner': pred.is_winner,
            'checked_at': pred.checked_at.isoformat() if pred.checked_at else None
        })
    
    return {
        'round_number': round_number,
        'total_predictions': total_predictions,
        'checked_predictions': checked_predictions,
        'unchecked_predictions': total_predictions - checked_predictions,
        'winning_predictions': winning_predictions,
        'sample_predictions': samples
    }


async def _get_latest_round_number() -> int:
    """최신 회차 번호를 가져오는 헬퍼 함수"""
    try:
        # 동행복권 홈페이지에서 최신 회차 정보 가져오기
        url = "https://www.dhlottery.co.kr/common.do?method=main"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # 최신 회차 번호 추출 로직
            round_element = soup.find('strong', {'id': 'lottoDrwNo'})
            if round_element:
                return int(round_element.text.strip())
        
        # 실패시 현재 날짜 기준 추정
        base_date = date(2002, 12, 7)  # 로또 1회차 날짜
        today = date.today()
        weeks_passed = (today - base_date).days // 7
        return min(weeks_passed, 1200)  # 최대 1200회차로 제한
        
    except Exception:
        # 모든 실패시 1100 반환
        return 1100


async def _fetch_lotto_data(round_number: int) -> Optional[Dict[str, Any]]:
    """특정 회차의 로또 데이터를 가져오는 헬퍼 함수"""
    try:
        # 동행복권 API 호출
        url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={round_number}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.dhlottery.co.kr/'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # API 응답 확인
            if data.get('returnValue') == 'success':
                numbers = [
                    data['drwtNo1'], data['drwtNo2'], data['drwtNo3'],
                    data['drwtNo4'], data['drwtNo5'], data['drwtNo6']
                ]
                
                # 날짜 파싱
                draw_date_str = data.get('drwNoDate')
                draw_date = datetime.strptime(draw_date_str, '%Y-%m-%d').date() if draw_date_str else date.today()
                
                return {
                    'round': round_number,
                    'draw_date': draw_date,
                    'numbers': sorted(numbers),
                    'bonus': data['bnusNo'],
                    'jackpot_winners': data.get('firstPrzwnerCo', 0),
                    'jackpot_amount': data.get('firstAccumamnt', 0)
                }
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching lotto data for round {round_number}: {e}")
        return None


def _calculate_prize_info(matched_count: int, bonus_matched: bool = False) -> tuple[int, int, bool]:
    """
    매칭된 번호 개수에 따라 등수, 상금, 당첨여부 계산
    """
    # 로또 등수별 상금 (대략적인 금액, 실제로는 당첨자 수에 따라 변동)
    if matched_count == 6:
        return 1, 2000000000, True  # 1등 - 20억원 (예시)
    elif matched_count == 5 and bonus_matched:
        return 2, 50000000, True    # 2등 - 5000만원 (예시)
    elif matched_count == 5:
        return 3, 1000000, True     # 3등 - 100만원 (예시)
    elif matched_count == 4:
        return 4, 50000, True       # 4등 - 5만원 (예시)
    elif matched_count == 3:
        return 5, 5000, True        # 5등 - 5천원 (예시)
    else:
        return None, 0, False       # 낙첨


async def _update_predictions_for_draw(db: Session, round_number: int, winning_numbers: list[int], bonus_number: int) -> int:
    """
    특정 회차에 대한 예측들의 당첨 여부를 업데이트하는 헬퍼 함수
    """
    updated_count = 0
    
    logger.info(f"Starting prediction update for round {round_number}")
    print(f"[ADMIN] Starting prediction update for round {round_number}")
    logger.info(f"Winning numbers: {winning_numbers}, Bonus: {bonus_number}")
    
    # 해당 회차의 모든 예측들 조회 (디버깅용)
    all_predictions = db.query(Prediction).filter(Prediction.draw_number == round_number).all()
    logger.info(f"Total predictions for round {round_number}: {len(all_predictions)}")
    
    # 아직 체크되지 않은 예측들만 조회
    predictions = db.query(Prediction).filter(
        Prediction.draw_number == round_number,
        Prediction.checked_at.is_(None)
    ).all()
    
    logger.info(f"Unchecked predictions for round {round_number}: {len(predictions)}")
    print(f"[ADMIN] Unchecked predictions for round {round_number}: {len(predictions)}")
    
    if not predictions:
        logger.warning(f"No unchecked predictions found for round {round_number}")
        return 0
    
    winning_set = set(winning_numbers)
    
    for prediction in predictions:
        try:
            # 예측 번호들 수집
            prediction_numbers = []
            for i in range(1, 7):
                num = getattr(prediction, f'num{i}')
                if num is not None:
                    prediction_numbers.append(num)
            
            logger.info(f"Processing prediction {prediction.id}: numbers={prediction_numbers}")
            
            if not prediction_numbers:
                logger.warning(f"Prediction {prediction.id} has no numbers, skipping")
                continue
                
            prediction_set = set(prediction_numbers)
            
            # 매칭된 번호 개수 계산
            matched_count = len(winning_set & prediction_set)
            
            # 보너스 번호 매칭 여부 확인
            bonus_matched = bonus_number in prediction_set
            
            # 등수, 상금, 당첨여부 계산
            prize_rank, prize_amount, is_winner = _calculate_prize_info(matched_count, bonus_matched)
            
            logger.info(f"Prediction {prediction.id}: matched={matched_count}, bonus={bonus_matched}, rank={prize_rank}, winner={is_winner}")
            
            # 예측 결과 업데이트
            old_values = {
                'matched_count': prediction.matched_count,
                'prize_rank': prediction.prize_rank,
                'is_winner': prediction.is_winner,
                'prize_amount': prediction.prize_amount,
                'checked_at': prediction.checked_at
            }
            
            prediction.matched_count = matched_count
            prediction.prize_rank = prize_rank
            prediction.is_winner = is_winner
            prediction.prize_amount = prize_amount
            prediction.checked_at = datetime.utcnow()
            
            logger.info(f"Updated prediction {prediction.id}: {old_values} -> new values set")
            updated_count += 1
            
        except Exception as e:
            logger.error(f"Error processing prediction {prediction.id}: {e}")
            continue
    
    logger.info(f"Completed prediction update for round {round_number}: {updated_count} predictions updated")
    print(f"[ADMIN] Completed prediction update for round {round_number}: {updated_count} predictions updated")
    return updated_count


@router.get("/lotto/latest", response_model=LottoDrawResponse)
async def get_latest_draw_admin(
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    관리자용 최신 로또 회차 조회
    - 가장 최근 회차 당첨번호 반환
    - 관리자만 접근 가능
    """
    from datetime import date
    
    latest_draw = db.query(LottoDraw).order_by(desc(LottoDraw.round)).first()
    
    if not latest_draw:
        # 샘플 데이터 반환 (DB가 비어있는 경우)
        return LottoDrawResponse(
            round=1100,
            draw_date=date.today(),
            numbers=[1, 7, 15, 23, 32, 43],
            bonus=25,
            jackpot_amount=20000000000,
            jackpot_winners=0
        )
    
    numbers = [latest_draw.num1, latest_draw.num2, latest_draw.num3,
              latest_draw.num4, latest_draw.num5, latest_draw.num6]
    
    return LottoDrawResponse(
        round=latest_draw.round,
        draw_date=latest_draw.draw_date,
        numbers=numbers,
        bonus=latest_draw.bonus,
        jackpot_amount=latest_draw.jackpot_amount,
        jackpot_winners=None  # 당첨자 수는 별도 테이블에서 관리
    )


# ============================================================================
# 결제 관리 API
# ============================================================================

@router.get("/payments", response_model=PaymentListResponse)
async def get_payments(
    page: int = Query(1, ge=1, description="페이지 번호"),
    limit: int = Query(20, ge=1, le=100, description="페이지당 항목 수"),
    status: Optional[str] = Query(None, description="결제 상태 필터 (pending, completed, failed, refunded)"),
    payment_method: Optional[str] = Query(None, description="결제 방법 필터"),
    start_date: Optional[date] = Query(None, description="시작 날짜 (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="종료 날짜 (YYYY-MM-DD)"),
    user_id: Optional[str] = Query(None, description="사용자 ID 필터"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    결제 내역 조회 (관리자 전용)
    - 승인, 취소, 실패 내역 포함
    - 사용자 정보와 함께 조회
    """
    
    offset = (page - 1) * limit
    
    # 기본 쿼리
    query = db.query(Payment, User.nickname, User.email).join(
        User, Payment.user_id == User.id
    )
    
    # 필터 적용
    if status:
        query = query.filter(Payment.status == status)
    
    if payment_method:
        query = query.filter(Payment.payment_method == payment_method)
    
    if start_date:
        query = query.filter(Payment.created_at >= start_date)
    
    if end_date:
        # 종료 날짜는 해당 날짜 23:59:59까지 포함
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.filter(Payment.created_at <= end_datetime)
    
    if user_id:
        try:
            import uuid
            user_uuid = uuid.UUID(user_id)
            query = query.filter(Payment.user_id == user_uuid)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user ID format"
            )
    
    # 총 개수 조회
    total = query.count()
    
    # 페이징 적용 및 정렬 (최신순)
    results = query.order_by(desc(Payment.created_at)).offset(offset).limit(limit).all()
    
    # 결과 변환
    payments = []
    for payment, user_nickname, user_email in results:
        payments.append(AdminPaymentInfo(
            id=str(payment.id),
            user_id=str(payment.user_id),
            user_nickname=user_nickname,
            user_email=user_email,
            payment_type=payment.payment_type,
            amount=payment.amount,
            credits_purchased=payment.credits_purchased,
            payment_method=payment.payment_method,
            transaction_id=payment.transaction_id,
            order_id=payment.order_id if hasattr(payment, 'order_id') else None,
            payment_key=payment.payment_key if hasattr(payment, 'payment_key') else None,
            toss_order_id=payment.toss_order_id if hasattr(payment, 'toss_order_id') else None,
            failure_code=payment.failure_code if hasattr(payment, 'failure_code') else None,
            failure_message=payment.failure_message if hasattr(payment, 'failure_message') else None,
            status=payment.status.value,
            created_at=payment.created_at,
            completed_at=payment.completed_at
        ))
    
    return PaymentListResponse(
        total=total,
        page=page,
        limit=limit,
        total_pages=math.ceil(total / limit),
        payments=payments
    )


@router.get("/payments/stats", response_model=PaymentStatsResponse)
async def get_payment_stats(
    days: int = Query(30, ge=1, le=365, description="조회 기간 (일)"),
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    결제 통계 조회 (관리자 전용)
    - 매출 현황, 성공률, 결제 수단별 통계
    """
    
    # 기간 설정
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = end_date - timedelta(days=7)
    month_start = end_date - timedelta(days=30)
    
    # 전체 통계
    total_revenue_query = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.completed
    )
    total_revenue = total_revenue_query.scalar() or 0
    
    # 오늘 매출
    today_revenue = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.completed,
        Payment.completed_at >= today_start
    ).scalar() or 0
    
    # 주간 매출
    weekly_revenue = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.completed,
        Payment.completed_at >= week_start
    ).scalar() or 0
    
    # 월간 매출
    monthly_revenue = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.completed,
        Payment.completed_at >= month_start
    ).scalar() or 0
    
    # 결제 건수 통계
    total_payments = db.query(func.count(Payment.id)).scalar() or 0
    successful_payments = db.query(func.count(Payment.id)).filter(
        Payment.status == PaymentStatus.completed
    ).scalar() or 0
    failed_payments = db.query(func.count(Payment.id)).filter(
        Payment.status == PaymentStatus.failed
    ).scalar() or 0
    cancelled_payments = db.query(func.count(Payment.id)).filter(
        Payment.status == PaymentStatus.refunded
    ).scalar() or 0
    
    # 성공률 계산
    success_rate = (successful_payments / total_payments * 100) if total_payments > 0 else 0
    
    # 평균 결제 금액
    avg_payment = db.query(func.avg(Payment.amount)).filter(
        Payment.status == PaymentStatus.completed
    ).scalar() or 0
    
    # 날짜별 매출 (최근 기간)
    daily_revenue = db.query(
        func.date(Payment.completed_at).label('date'),
        func.sum(Payment.amount).label('amount')
    ).filter(
        Payment.status == PaymentStatus.completed,
        Payment.completed_at >= start_date
    ).group_by(func.date(Payment.completed_at)).all()
    
    revenue_by_date = {str(row.date): int(row.amount) for row in daily_revenue}
    
    # 프론트엔드 차트용 일별 매출 데이터 생성 (빈 날짜도 포함)
    daily_revenue_chart = []
    current_date = start_date.date()
    end_date_only = end_date.date()
    
    while current_date <= end_date_only:
        date_str = current_date.strftime("%Y-%m-%d")
        revenue = revenue_by_date.get(date_str, 0)
        daily_revenue_chart.append(DailyRevenueChart(
            date=date_str,
            revenue=revenue
        ))
        current_date += timedelta(days=1)
    
    # 상태별 결제 건수
    status_stats = db.query(
        Payment.status,
        func.count(Payment.id).label('count')
    ).group_by(Payment.status).all()
    
    payments_by_status = {row.status.value: row.count for row in status_stats}
    
    # 프론트엔드 차트용 상태별 데이터 (모든 상태 포함)
    payment_count_by_status = {
        "completed": 0,
        "pending": 0, 
        "failed": 0,
        "refunded": 0
    }
    payment_count_by_status.update(payments_by_status)
    
    # 결제 수단별 건수
    method_stats = db.query(
        Payment.payment_method,
        func.count(Payment.id).label('count')
    ).filter(Payment.payment_method.isnot(None)).group_by(Payment.payment_method).all()
    
    payments_by_method = {row.payment_method: row.count for row in method_stats}
    
    return PaymentStatsResponse(
        total_revenue=int(total_revenue),
        today_revenue=int(today_revenue),
        weekly_revenue=int(weekly_revenue),
        monthly_revenue=int(monthly_revenue),
        total_payments=total_payments,
        successful_payments=successful_payments,
        failed_payments=failed_payments,
        cancelled_payments=cancelled_payments,
        success_rate=round(success_rate, 2),  # 이미 0-100 퍼센트 값
        average_payment_amount=float(avg_payment),
        
        # 프론트엔드 차트용 데이터
        daily_revenue_chart=daily_revenue_chart,
        payment_count_by_status=payment_count_by_status,
        
        # 기존 데이터 (하위 호환)
        revenue_by_date=revenue_by_date,
        payments_by_status=payments_by_status,
        payments_by_method=payments_by_method
    )


@router.get("/payments/{payment_id}", response_model=AdminPaymentInfo)
async def get_payment_detail(
    payment_id: str,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    개별 결제 상세 조회 (관리자 전용)
    """
    
    try:
        import uuid
        payment_uuid = uuid.UUID(payment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment ID format"
        )
    
    # 결제 정보와 사용자 정보 조회
    result = db.query(Payment, User.nickname, User.email).join(
        User, Payment.user_id == User.id
    ).filter(Payment.id == payment_uuid).first()
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    payment, user_nickname, user_email = result
    
    return AdminPaymentInfo(
        id=str(payment.id),
        user_id=str(payment.user_id),
        user_nickname=user_nickname,
        user_email=user_email,
        payment_type=payment.payment_type,
        amount=payment.amount,
        credits_purchased=payment.credits_purchased,
        payment_method=payment.payment_method,
        transaction_id=payment.transaction_id,
        order_id=payment.order_id if hasattr(payment, 'order_id') else None,
        payment_key=payment.payment_key if hasattr(payment, 'payment_key') else None,
        toss_order_id=payment.toss_order_id if hasattr(payment, 'toss_order_id') else None,
        failure_code=payment.failure_code if hasattr(payment, 'failure_code') else None,
        failure_message=payment.failure_message if hasattr(payment, 'failure_message') else None,
        status=payment.status.value,
        created_at=payment.created_at,
        completed_at=payment.completed_at
    )


@router.post("/payments/{payment_id}/cancel", response_model=CancelPaymentResponse)
async def cancel_payment_admin(
    payment_id: str,
    request: AdminCancelPaymentRequest,
    admin_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    결제 취소 (관리자 전용)
    - 완료된 결제를 취소하고 크레딧 환불
    - 토스 결제의 경우 토스 API 호출
    """
    
    try:
        import uuid
        payment_uuid = uuid.UUID(payment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment ID format"
        )
    
    # 결제 정보 조회
    payment = db.query(Payment).filter(Payment.id == payment_uuid).first()
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # 취소 가능한 상태 확인
    if payment.status != PaymentStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel payment with status: {payment.status.value}"
        )
    
    # 사용자 조회
    user = db.query(User).filter(User.id == payment.user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    try:
        # 환불 금액 결정
        refund_amount = request.refund_amount or payment.amount
        refund_credits = payment.credits_purchased or 0
        
        # 부분 환불인 경우 크레딧도 비례해서 계산
        if request.refund_amount and request.refund_amount < payment.amount:
            refund_ratio = request.refund_amount / payment.amount
            refund_credits = int(refund_credits * refund_ratio)
        
        # 토스 결제인 경우 토스 API 호출
        toss_already_cancelled = False
        if payment.payment_method == "toss" and hasattr(payment, 'payment_key') and payment.payment_key:
            try:
                from app.services.toss_payment_service import toss_payment_service
                
                # 토스 결제 취소 요청
                toss_response = toss_payment_service.cancel_payment(
                    payment_key=payment.payment_key,
                    cancel_reason=request.cancel_reason,
                    cancel_amount=refund_amount if request.refund_amount else None
                )
                
                # 이미 취소된 경우 확인
                if toss_response.get("alreadyCancelled"):
                    toss_already_cancelled = True
                    logger.info(f"Toss payment was already cancelled: {payment.payment_key}")
                else:
                    logger.info(f"Toss payment cancelled: {payment.payment_key}")
                
            except Exception as e:
                logger.error(f"Failed to cancel Toss payment: {e}")
                # 토스 취소 실패해도 사이트 내 취소는 진행할지 결정
                # 일단 오류로 처리하고, 필요시 정책 변경 가능
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to cancel payment with Toss: {str(e)}"
                )
        
        # 크레딧 환불 처리 (차감)
        if refund_credits > 0:
            # 사용자 현재 크레딧이 환불할 크레딧보다 적은 경우 확인
            if user.credits < refund_credits:
                logger.warning(f"User {user.id} has insufficient credits for refund: {user.credits} < {refund_credits}")
                # 보유 크레딧만큼만 환불
                refund_credits = user.credits
            
            if refund_credits > 0:
                refund_transaction = CreditService.add_credits(
                    db=db,
                    user=user,
                    amount=-refund_credits,  # 음수로 차감
                    transaction_type=TransactionType.refund,
                    description=f"관리자 결제 취소 환불: {request.cancel_reason}",
                    metadata_json={
                        "payment_id": str(payment.id),
                        "admin_user_id": str(admin_user.id),
                        "cancel_reason": request.cancel_reason,
                        "refund_amount": refund_amount
                    }
                )
        
        # 결제 상태 변경
        payment.status = PaymentStatus.refunded
        if hasattr(payment, 'failure_message'):
            if toss_already_cancelled:
                payment.failure_message = f"관리자 취소 (토스에서 이미 취소됨): {request.cancel_reason}"
            else:
                payment.failure_message = f"관리자 취소: {request.cancel_reason}"
        
        db.commit()
        db.refresh(user)
        
        if toss_already_cancelled:
            logger.info(f"Payment {payment_id} cancelled by admin {admin_user.id} (already cancelled in Toss): {request.cancel_reason}")
        else:
            logger.info(f"Payment {payment_id} cancelled by admin {admin_user.id}: {request.cancel_reason}")
        
        return CancelPaymentResponse(
            success=True,
            payment_id=payment_id,
            cancelled_amount=refund_amount,
            refunded_credits=refund_credits,
            new_balance=user.credits,
            cancel_reason=request.cancel_reason,
            cancelled_at=datetime.utcnow(),
            already_cancelled_in_gateway=toss_already_cancelled
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling payment {payment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel payment"
        )