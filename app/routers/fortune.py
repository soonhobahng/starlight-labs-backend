# app/routers/fortune.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import date, datetime
from typing import List
import logging

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User
from app.models.fortune import ZodiacDailyStat
from app.schemas.fortune import (
    DailyFortuneResponse,
    ZodiacStatsResponse,
    TrendingResponse,
    GenerateWithLuckyRequest,
    ZodiacTodayFortuneResponse
)
from app.services.fortune_service import FortuneService
from app.services.zodiac_service import ZodiacService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fortune", tags=["운세"])


@router.get("/daily", response_model=DailyFortuneResponse)
def get_daily_fortune(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    오늘의 운세 조회

    - 인증 필요
    - 생년월일 미등록 시 400 에러
    - 같은 날짜는 캐싱됨
    """
    logger.info("========== /fortune/daily 요청 시작 ==========")
    logger.info(f"User ID: {current_user.id}, Email: {current_user.email}")
    logger.info(f"birth_year: {current_user.birth_year}, zodiac_sign: {current_user.zodiac_sign}")
    logger.info(f"fortune_enabled: {current_user.fortune_enabled}")

    if not current_user.birth_year:
        logger.warning(f"생년월일 미등록 - User ID: {current_user.id}")
        raise HTTPException(
            status_code=400,
            detail="생년월일을 먼저 등록해주세요."
        )

    if not current_user.fortune_enabled:
        logger.warning(f"운세 기능 비활성화 - User ID: {current_user.id}")
        raise HTTPException(
            status_code=403,
            detail="운세 기능이 비활성화되어 있습니다."
        )

    today = date.today()
    logger.info(f"오늘 날짜: {today}")

    # 운세 조회/생성
    logger.info("FortuneService.get_or_create_daily_fortune 호출...")
    fortune = FortuneService.get_or_create_daily_fortune(
        db=db,
        user_id=str(current_user.id),
        birth_year=current_user.birth_year,
        fortune_date=today
    )
    logger.info(f"운세 조회 완료 - fortune_date: {fortune.fortune_date}, overall_luck: {fortune.overall_luck}")

    # 띠별 순위 계산
    logger.info("FortuneService.calculate_zodiac_rank 호출...")
    rank_info = FortuneService.calculate_zodiac_rank(
        db=db,
        zodiac_sign=current_user.zodiac_sign,
        fortune_date=today
    )
    logger.info(f"순위 계산 완료 - rank_info: {rank_info}")

    response = DailyFortuneResponse(
        user_id=str(current_user.id),
        fortune_date=fortune.fortune_date,
        zodiac_sign=current_user.zodiac_sign,
        birth_year=current_user.birth_year,
        luck_scores={
            "overall": fortune.overall_luck,
            "wealth": fortune.wealth_luck,
            "lottery": fortune.lottery_luck
        },
        lucky_elements={
            "numbers": fortune.lucky_numbers,
            "color": fortune.lucky_color,
            "direction": fortune.lucky_direction
        },
        messages={
            "fortune": fortune.fortune_message,
            "advice": fortune.advice
        },
        rank_info=rank_info
    )

    logger.info(f"========== /fortune/daily 응답 완료 ==========")
    logger.info(f"Response: luck_scores={response.luck_scores}, lucky_numbers={fortune.lucky_numbers}")

    return response


@router.get("/zodiac-stats", response_model=ZodiacStatsResponse)
def get_zodiac_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    띠별 통계 및 리더보드
    
    - 오늘 날짜 기준 12띠 순위
    - 내 띠 정보 포함
    """
    
    today = date.today()
    
    try:
        # 띠별 통계 조회 - 필수 컬럼만 선택하여 missing column 오류 방지
        stats = db.query(
            ZodiacDailyStat.id,
            ZodiacDailyStat.stats_date, 
            ZodiacDailyStat.zodiac_sign,
            ZodiacDailyStat.avg_overall_luck,
            ZodiacDailyStat.avg_lottery_luck,
            ZodiacDailyStat.active_users,
            ZodiacDailyStat.predictions_count
        ).filter(
            ZodiacDailyStat.stats_date == today
        ).order_by(ZodiacDailyStat.avg_lottery_luck.desc()).all()
        
        # 결과를 객체 형태로 변환
        class StatResult:
            def __init__(self, row):
                self.id = row[0]
                self.stats_date = row[1] 
                self.zodiac_sign = row[2]
                self.avg_overall_luck = row[3]
                self.avg_lottery_luck = row[4] 
                self.active_users = row[5]
                self.predictions_count = row[6]
        
        stats = [StatResult(row) for row in stats]
    except Exception as e:
        # DB 에러 발생 시 트랜잭션 롤백
        try:
            db.rollback()
        except:
            pass
            
        # DB 테이블이 없는 경우 기본 데이터 반환
        from app.services.zodiac_service import ZodiacService
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"ZodiacDailyStat query failed: {e}")
        
        # 기본 띠별 순위 (임의 순서)
        all_zodiacs = ZodiacService.get_all_zodiacs()
        import random
        random.seed(today.day)  # 날짜 기반으로 순서 결정
        shuffled_zodiacs = all_zodiacs.copy()
        random.shuffle(shuffled_zodiacs)
        
        stats = []
        for i, zodiac in enumerate(shuffled_zodiacs):
            # 모의 통계 데이터 생성
            class MockStat:
                def __init__(self, zodiac_sign, avg_lottery_luck, active_users):
                    self.zodiac_sign = zodiac_sign
                    self.avg_lottery_luck = avg_lottery_luck
                    self.active_users = active_users
            
            avg_luck = 90 - (i * 5) + random.randint(-3, 3)  # 90점부터 점차 감소
            users = max(1, 50 - (i * 2) + random.randint(-5, 5))  # 50명부터 점차 감소
            stats.append(MockStat(zodiac, avg_luck, users))
    
    # 순위 생성
    zodiac_rankings = []
    for rank, stat in enumerate(stats, start=1):
        message = None
        if rank == 1:
            message = f"오늘은 {stat.zodiac_sign}의 날!"
        
        zodiac_rankings.append({
            "rank": rank,
            "zodiac_sign": stat.zodiac_sign,
            "avg_luck": float(stat.avg_lottery_luck),
            "active_users": stat.active_users,
            "message": message
        })
    
    # 내 띠 정보
    my_zodiac_stat = next((s for s in stats if s.zodiac_sign == current_user.zodiac_sign), None)
    my_rank = next((i for i, r in enumerate(zodiac_rankings, 1) 
                    if r["zodiac_sign"] == current_user.zodiac_sign), 6)
    
    return ZodiacStatsResponse(
        stats_date=today,
        zodiac_rankings=zodiac_rankings,
        my_zodiac={
            "sign": current_user.zodiac_sign or "용띠",  # 기본값 설정
            "rank": my_rank,
            "avg_luck": float(my_zodiac_stat.avg_lottery_luck) if my_zodiac_stat else 75.0
        }
    )


@router.get("/trending", response_model=TrendingResponse)
def get_trending(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    실시간 트렌드 정보
    
    - 인기 번호
    - 인기 전략
    - 커뮤니티 통계
    """
    
    # TODO: Redis 캐싱 추가
    # TODO: 실제 통계 계산 로직 구현
    
    return TrendingResponse(
        timestamp=datetime.now().isoformat(),
        popular_numbers={
            "today": [7, 14, 23, 31, 42],
            "this_week": [3, 7, 12, 23, 38]
        },
        popular_strategy={
            "name": "빈도 분석",
            "usage_count": 3421,
            "percentage": 32.5
        },
        community_stats={
            "total_predictions_today": 12456,
            "active_users_now": 1247,
            "weekly_winners": 32
        },
        lucky_zodiacs_today=[
            {"sign": "용띠", "luck": 87},
            {"sign": "호랑이띠", "luck": 82},
            {"sign": "토끼띠", "luck": 79}
        ]
    )


@router.post("/generate-with-lucky")
def generate_with_lucky_numbers(
    request: GenerateWithLuckyRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    행운의 번호 기반 예측 생성
    
    - 오늘의 행운 번호를 활용한 조합 생성
    - 기존 예측 API와 통합
    """
    
    # 오늘의 운세 조회
    today = date.today()
    fortune = FortuneService.get_or_create_daily_fortune(
        db=db,
        user_id=str(current_user.id),
        birth_year=current_user.birth_year,
        fortune_date=today
    )
    
    # TODO: 기존 prediction 서비스와 통합
    # lucky_numbers를 시드로 사용하여 예측 생성
    
    return {
        "predictions": [
            {
                "numbers": fortune.lucky_numbers[:6],
                "lucky_match_count": 6,
                "is_lucky_based": True
            }
        ],
        "lucky_numbers_used": fortune.lucky_numbers,
        "message": "행운의 번호를 기반으로 생성했습니다! 🍀"
    }


@router.get("/zodiac/today", response_model=ZodiacTodayFortuneResponse)
def get_zodiac_today_fortune(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    띠별 오늘의 운세 조회

    - Bearer Token 인증 필요
    - 로그인한 유저의 zodiac_sign 기준으로 오늘의 운세 반환
    - zodiac_sign 미설정 시 400 에러

    Returns:
        ZodiacTodayFortuneResponse: 띠별 오늘의 운세 정보
    """
    import logging
    logger = logging.getLogger(__name__)

    # 1. zodiac_sign 확인
    if not current_user.zodiac_sign:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="띠 정보가 없습니다. 프로필에서 생년을 설정해주세요."
        )

    today = date.today()

    # 2. 운세 조회 또는 생성
    fortune_data = FortuneService.get_or_create_zodiac_fortune(
        db=db,
        user_id=str(current_user.id),
        zodiac_sign=current_user.zodiac_sign,
        fortune_date=today
    )

    logger.info(f"Zodiac fortune retrieved for user {current_user.id}, zodiac: {current_user.zodiac_sign}")

    # 3. 응답 반환
    return ZodiacTodayFortuneResponse(**fortune_data)