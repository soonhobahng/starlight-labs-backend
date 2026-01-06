from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from typing import List, Optional
import math
from collections import Counter
from datetime import datetime, timedelta
import logging

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import (
    User, Prediction, LottoDraw, CreditTransaction, TransactionType, UserTier
)
from app.schemas.predictions import (
    PredictionRequest, PredictionResponse, PredictionHistoryResponse, 
    PredictionHistoryItem, PredictionDetailResponse, StrategyStats, 
    StrategyStatsResponse, UserStats, WeeklyPredictionStats,
    UserDashboardResponse, UserDashboardStats, BestPredictionInfo, UserRecentActivity,
    BestResultResponse, SimilarResultsResponse, SimilarWinningResult
)
from app.services.strategies import (
    STRATEGY_MAP, get_strategy_confidence, STRATEGY_INFO,
    validate_strategy, calculate_strategy_cost, get_available_strategies
)
from app.services.credit_service import CreditService, InsufficientCreditsError
from app.utils.draw_utils import get_next_draw_number, get_current_week_prediction_range

router = APIRouter(prefix="/predictions", tags=["predictions"])

# Logger 설정
logger = logging.getLogger(__name__)


@router.post("/", response_model=PredictionResponse, status_code=201)
async def create_prediction(
    request: PredictionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    예측 번호 생성
    
    1. 사용자 크레딧 확인 (VIP는 무제한)
    2. 전략에 맞는 함수 호출
    3. DB에서 최근 당첨번호 가져오기
    4. 예측 실행
    5. 결과를 predictions 테이블에 저장
    6. 크레딧 차감 (credit_transactions에 기록)
    7. 결과 반환
    """
    
    # 디버깅을 위한 상세 로깅
    logger.info(f"create_prediction called with request: strategy={request.strategy}, count={request.count}, draw_number={request.draw_number}")
    logger.info(f"User: id={current_user.id}, birth_year={current_user.birth_year}, fortune_enabled={current_user.fortune_enabled}")
    
    # 전략 유효성 검사
    is_valid, error_msg = validate_strategy(request.strategy, current_user.tier)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST if "Invalid" in error_msg 
            else status.HTTP_403_FORBIDDEN,
            detail=error_msg
        )
    
    # fortune_based 전략 추가 검증
    if request.strategy == "fortune_based":
        if not current_user.birth_year or not current_user.fortune_enabled:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="운세 기반 예측을 사용하려면 생년월일 등록과 운세 기능 활성화가 필요합니다."
            )
    
    # 크레딧 비용 계산
    credit_cost = calculate_strategy_cost(request.strategy, request.count)
    
    # 크레딧 확인
    if not CreditService.check_credits(current_user, credit_cost):
        # 사용자 티어에 따라 다른 메시지 제공
        if current_user.tier == UserTier.free:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"크레딧이 부족합니다. 필요: {credit_cost}개, 보유: {current_user.credits}개. 광고를 시청하거나 크레딧을 구매해주세요."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"크레딧이 부족합니다. 필요: {credit_cost}개, 보유: {current_user.credits}개. 크레딧을 구매해주세요."
            )
    
    # 최근 로또 데이터 조회 (최근 50회차)
    recent_draws = db.query(LottoDraw).order_by(desc(LottoDraw.round)).limit(50).all()
    recent_numbers = [
        [draw.num1, draw.num2, draw.num3, draw.num4, draw.num5, draw.num6] 
        for draw in recent_draws
    ]
    
    # 다음 회차 번호 계산
    if request.draw_number and request.draw_number > 0:
        next_round = request.draw_number
    else:
        next_round = get_next_draw_number()
    
    # 전략 실행
    try:
        strategy_func = STRATEGY_MAP[request.strategy]
        
        # 전략에 따라 파라미터 전달
        if request.strategy == "fortune_based":
            # 운세 기반 전략: 사용자 ID와 DB 세션 전달
            predictions = strategy_func(str(current_user.id), db, request.count)
        elif request.strategy in ["frequency_balance", "pattern_similarity", "machine_learning", 
                               "consecutive_absence", "winner_pattern", "ai_custom"]:
            predictions = strategy_func(recent_numbers, request.count)
        else:
            predictions = strategy_func(request.count)
        
        # 신뢰도 점수 계산
        confidence_score = get_strategy_confidence(request.strategy, recent_numbers)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Strategy execution failed: {str(e)}"
        )
    
    # 예측 결과 검증
    for prediction in predictions:
        if len(prediction) != 6 or not all(1 <= num <= 45 for num in prediction):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid prediction numbers generated"
            )
    
    # 예측 저장
    prediction_records = []
    try:
        for pred_numbers in predictions:
            prediction_record = Prediction(
                user_id=current_user.id,
                draw_number=next_round,
                strategy_name=request.strategy,
                num1=pred_numbers[0], num2=pred_numbers[1], num3=pred_numbers[2],
                num4=pred_numbers[3], num5=pred_numbers[4], num6=pred_numbers[5],
                confidence_score=confidence_score
            )
            db.add(prediction_record)
            prediction_records.append(prediction_record)
        
        # 크레딧 사용 처리
        credit_transaction = CreditService.use_credits(
            db=db,
            user=current_user,
            amount=credit_cost,
            description=f"{request.strategy} 전략으로 {request.count}개 예측",
            metadata_json={
                "strategy": request.strategy,
                "count": request.count,
                "draw_number": next_round,
                "prediction_ids": [str(record.id) for record in prediction_records]
            }
        )
        
        db.commit()
        
        # 생성된 레코드들을 새로고침
        for record in prediction_records:
            db.refresh(record)
            logger.info(f"Saved prediction - ID: {record.id}, User: {record.user_id}, Created: {record.created_at}, Draw: {record.draw_number}")
            
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    
    return PredictionResponse(
        id=prediction_records[0].id,
        strategy=request.strategy,
        predictions=predictions,
        confidence_score=confidence_score,
        credits_used=abs(credit_transaction.amount) if credit_transaction else 0,
        remaining_credits=current_user.credits,
        draw_number=next_round,
        created_at=prediction_records[0].created_at
    )


@router.get("/history", response_model=PredictionHistoryResponse)
async def get_prediction_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    strategy: Optional[str] = Query(None, description="Filter by strategy"),
    draw_number: Optional[int] = Query(None, description="Filter by draw number"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자의 예측 히스토리 조회
    - 페이지네이션 지원
    - 전략별 필터링 지원
    - 당첨 결과 포함 (is_winner, matched_count)
    """
    
    # 기본 쿼리 (soft delete 적용)
    base_query = db.query(Prediction).filter(
        Prediction.user_id == current_user.id,
        Prediction.deleted_at.is_(None)
    )
    
    # 필터링
    if strategy:
        if strategy not in STRATEGY_MAP:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid strategy"
            )
        base_query = base_query.filter(Prediction.strategy_name == strategy)
    
    if draw_number:
        base_query = base_query.filter(Prediction.draw_number == draw_number)
    
    # 총 개수 조회
    total = base_query.count()
    
    # 페이지네이션
    offset = (page - 1) * limit
    predictions = base_query.order_by(desc(Prediction.created_at)).offset(offset).limit(limit).all()
    
    # 응답 데이터 구성
    prediction_items = []
    for pred in predictions:
        numbers = [pred.num1, pred.num2, pred.num3, pred.num4, pred.num5, pred.num6]
        prediction_items.append(
            PredictionHistoryItem(
                id=pred.id,
                draw_number=pred.draw_number,
                strategy_name=pred.strategy_name,
                numbers=numbers,
                confidence_score=pred.confidence_score,
                matched_count=pred.matched_count,
                is_winner=pred.is_winner,
                created_at=pred.created_at
            )
        )
    
    total_pages = math.ceil(total / limit)
    
    return PredictionHistoryResponse(
        total=total,
        page=page,
        limit=limit,
        total_pages=total_pages,
        predictions=prediction_items
    )


@router.get("/weekly-stats", response_model=WeeklyPredictionStats)
async def get_weekly_prediction_stats(
    draw_number: Optional[int] = Query(None, description="회차 번호 (없으면 현재 주간)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    주간 예측 생성 개수 통계
    - 추첨일 기준 일주일간 생성된 번호조합 개수
    - 전체 사용자 평균과의 차이
    """
    
    # 회차 번호가 없으면 현재 주간 사용
    if draw_number is None:
        draw_number = get_next_draw_number()
    
    # 주간 범위 계산
    from app.utils.draw_utils import get_weekly_prediction_range
    week_start, week_end = get_current_week_prediction_range() if draw_number == get_next_draw_number() else get_weekly_prediction_range(draw_number)
    
    # 현재 사용자의 해당 주간 예측 개수 (soft delete 적용)
    user_count_query = db.query(Prediction).filter(
        Prediction.user_id == current_user.id,
        Prediction.created_at >= week_start,
        Prediction.created_at <= week_end,
        Prediction.deleted_at.is_(None)
    )
    
    user_count = user_count_query.count()
    
    # 디버깅용 로그
    logger.info(f"Weekly stats debug - User ID: {current_user.id}")
    logger.info(f"Week range: {week_start} to {week_end}")
    logger.info(f"User prediction count: {user_count}")
    
    # 사용자의 모든 예측 기록도 확인 (soft delete 적용)
    all_user_predictions = db.query(Prediction).filter(
        Prediction.user_id == current_user.id,
        Prediction.deleted_at.is_(None)
    ).order_by(Prediction.created_at.desc()).limit(10).all()
    
    logger.info(f"User's recent predictions:")
    for pred in all_user_predictions:
        logger.info(f"  - ID: {pred.id}, Created: {pred.created_at}, Draw: {pred.draw_number}")
    
    # 전체 사용자의 해당 주간 예측 개수 (사용자별 평균, soft delete 적용)
    user_prediction_counts = db.query(
        Prediction.user_id,
        func.count(Prediction.id).label('prediction_count')
    ).filter(
        Prediction.created_at >= week_start,
        Prediction.created_at <= week_end,
        Prediction.deleted_at.is_(None)
    ).group_by(Prediction.user_id).all()
    
    if user_prediction_counts:
        total_average = sum(count.prediction_count for count in user_prediction_counts) / len(user_prediction_counts)
    else:
        total_average = 0.0
    
    # 차이값 계산
    difference_from_average = user_count - int(total_average)
    is_above_average = user_count > total_average
    
    return WeeklyPredictionStats(
        draw_number=draw_number,
        week_start=week_start,
        week_end=week_end,
        user_count=user_count,
        total_average=round(total_average, 2),
        difference_from_average=difference_from_average,
        is_above_average=is_above_average
    )



@router.get("/stats/strategies", response_model=StrategyStatsResponse)
async def get_strategy_stats(
    limit: int = Query(10, ge=1, le=50, description="Number of strategies to return"),
    db: Session = Depends(get_db)
):
    """
    전략별 통계 조회
    - 총 예측 수
    - 평균 일치 개수
    - 당첨률 (3개 이상 일치)
    """
    
    # 전략별 통계 계산
    strategy_stats = []
    total_predictions = 0
    total_winners = 0
    
    for strategy_name, strategy_info in STRATEGY_INFO.items():
        # 해당 전략의 모든 예측 조회 (soft delete 적용)
        predictions = db.query(Prediction).filter(
            Prediction.strategy_name == strategy_name,
            Prediction.deleted_at.is_(None)
        ).all()
        
        if not predictions:
            continue
        
        strategy_predictions = len(predictions)
        strategy_winners = sum(1 for p in predictions if p.is_winner)
        avg_matched = sum(p.matched_count for p in predictions) / strategy_predictions
        win_rate = strategy_winners / strategy_predictions if strategy_predictions > 0 else 0
        confidence_avg = sum(p.confidence_score for p in predictions) / strategy_predictions
        
        strategy_stats.append(StrategyStats(
            strategy=strategy_name,
            display_name=strategy_info["display_name"],
            total_predictions=strategy_predictions,
            avg_matched_count=round(avg_matched, 2),
            win_rate=round(win_rate * 100, 2),
            total_winners=strategy_winners,
            confidence_avg=round(confidence_avg, 3)
        ))
        
        total_predictions += strategy_predictions
        total_winners += strategy_winners
    
    # 당첨률 기준으로 정렬
    strategy_stats.sort(key=lambda x: x.win_rate, reverse=True)
    
    overall_win_rate = total_winners / total_predictions if total_predictions > 0 else 0
    
    return StrategyStatsResponse(
        strategies=strategy_stats[:limit],
        total_predictions=total_predictions,
        overall_win_rate=round(overall_win_rate * 100, 2)
    )


@router.get("/stats/user", response_model=UserStats)
async def get_user_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    현재 사용자의 예측 통계
    """
    
    # 사용자의 모든 예측 조회 (soft delete 적용)
    predictions = db.query(Prediction).filter(
        Prediction.user_id == current_user.id,
        Prediction.deleted_at.is_(None)
    ).all()
    
    if not predictions:
        return UserStats(
            total_predictions=0,
            total_credits_used=0,
            best_matched_count=0,
            total_winners=0,
            win_rate=0,
            favorite_strategy="",
            total_matches={"3": 0, "4": 0, "5": 0, "6": 0}
        )
    
    # 크레딧 사용 내역 조회
    total_credits_used = db.query(func.sum(-CreditTransaction.amount)).filter(
        CreditTransaction.user_id == current_user.id,
        CreditTransaction.type == TransactionType.prediction,
        CreditTransaction.amount < 0
    ).scalar() or 0
    
    # 통계 계산
    total_predictions = len(predictions)
    total_winners = sum(1 for p in predictions if p.is_winner)
    best_matched_count = max(p.matched_count for p in predictions)
    win_rate = total_winners / total_predictions if total_predictions > 0 else 0
    
    # 전략별 사용 횟수
    strategy_counter = Counter(p.strategy_name for p in predictions)
    favorite_strategy = strategy_counter.most_common(1)[0][0] if strategy_counter else ""
    
    # 일치 개수별 통계
    match_counter = Counter(str(p.matched_count) for p in predictions if p.matched_count >= 3)
    total_matches = {
        "3": match_counter.get("3", 0),
        "4": match_counter.get("4", 0),
        "5": match_counter.get("5", 0),
        "6": match_counter.get("6", 0)
    }
    
    return UserStats(
        total_predictions=total_predictions,
        total_credits_used=total_credits_used,
        best_matched_count=best_matched_count,
        total_winners=total_winners,
        win_rate=round(win_rate * 100, 2),
        favorite_strategy=STRATEGY_INFO.get(favorite_strategy, {}).get("display_name", favorite_strategy),
        total_matches=total_matches
    )




@router.post("/batch", response_model=List[PredictionResponse])
async def create_batch_predictions(
    requests: List[PredictionRequest],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    여러 전략으로 동시 예측 생성
    """
    
    if len(requests) > 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 5 strategies per batch"
        )
    
    # 총 비용 계산
    total_cost = 0
    for request in requests:
        is_valid, error_msg = validate_strategy(request.strategy, current_user.tier)
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Strategy '{request.strategy}': {error_msg}"
            )
        total_cost += calculate_strategy_cost(request.strategy, request.count)
    
    # 크레딧 확인
    if current_user.tier != UserTier.vip and current_user.credits < total_cost:
        if current_user.tier == UserTier.free:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"크레딧이 부족합니다. 필요: {total_cost}개, 보유: {current_user.credits}개. 광고를 시청하거나 크레딧을 구매해주세요."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail=f"크레딧이 부족합니다. 필요: {total_cost}개, 보유: {current_user.credits}개. 크레딧을 구매해주세요."
            )
    
    responses = []
    used_credits = 0
    
    try:
        for request in requests:
            # 각 요청을 개별적으로 처리
            response = await create_prediction(request, current_user, db)
            responses.append(response)
            used_credits += response.credits_used
            
    except Exception as e:
        # 실패 시 롤백
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch prediction failed: {str(e)}"
        )
    
    return responses


def update_prediction_results():
    """
    추첨 결과 발표 후 예측 결과 업데이트
    (별도 스케줄러에서 호출)
    """
    from app.core.database import SessionLocal
    
    db = SessionLocal()
    try:
        # 아직 결과가 업데이트되지 않은 예측들 조회 (soft delete 적용)
        pending_predictions = db.query(Prediction).filter(
            Prediction.matched_count == 0,
            Prediction.is_winner == False,
            Prediction.deleted_at.is_(None)
        ).all()
        
        for prediction in pending_predictions:
            # 해당 회차 당첨번호 조회
            actual_draw = db.query(LottoDraw).filter(
                LottoDraw.round == prediction.draw_number
            ).first()
            
            if actual_draw:
                # 일치 개수 계산
                pred_numbers = {prediction.num1, prediction.num2, prediction.num3,
                              prediction.num4, prediction.num5, prediction.num6}
                actual_numbers = {actual_draw.num1, actual_draw.num2, actual_draw.num3,
                                actual_draw.num4, actual_draw.num5, actual_draw.num6}
                
                matched_count = len(pred_numbers & actual_numbers)
                is_winner = matched_count >= 3
                
                # 업데이트
                prediction.matched_count = matched_count
                prediction.is_winner = is_winner
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update prediction results: {e}")
    finally:
        db.close()


@router.get("/best-result", response_model=BestResultResponse)
async def get_user_best_result(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자 최고 성과 조회
    - 최고 일치 수, 해당 회차, 날짜 등 반환
    """
    
    user_id = current_user.id
    
    # 총 예측 수 (soft delete 적용)
    total_predictions = db.query(Prediction).filter(
        Prediction.user_id == user_id,
        Prediction.deleted_at.is_(None)
    ).count()
    
    # 총 당첨 수 (soft delete 적용)
    total_winners = db.query(Prediction).filter(
        Prediction.user_id == user_id,
        Prediction.is_winner == True,
        Prediction.deleted_at.is_(None)
    ).count()
    
    # 예측 기록이 없는 경우
    if total_predictions == 0:
        return BestResultResponse(
            has_predictions=False,
            best_matched_count=0,
            best_prediction=None,
            total_predictions=0,
            total_winners=0,
            user_tier=current_user.tier
        )
    
    # 최고 성과 예측 찾기 (checked_at이 있는 것만, 즉 결과가 확인된 것만, soft delete 적용)
    best_prediction = db.query(Prediction).filter(
        Prediction.user_id == user_id,
        Prediction.checked_at.is_not(None),
        Prediction.deleted_at.is_(None)
    ).order_by(desc(Prediction.matched_count)).first()
    
    # 결과가 확인된 예측이 없는 경우
    if not best_prediction:
        return BestResultResponse(
            has_predictions=True,
            best_matched_count=0,
            best_prediction=None,
            total_predictions=total_predictions,
            total_winners=total_winners,
            user_tier=current_user.tier
        )
    
    # 해당 회차의 로또 정보 가져오기
    lotto_draw = db.query(LottoDraw).filter(
        LottoDraw.round == best_prediction.draw_number
    ).first()
    
    # 예측 번호들 구성
    predicted_numbers = [
        getattr(best_prediction, f'num{i}') 
        for i in range(1, 7) 
        if getattr(best_prediction, f'num{i}') is not None
    ]
    
    # 최고 성과 정보 구성
    best_prediction_info = BestPredictionInfo(
        prediction_id=str(best_prediction.id),
        draw_number=best_prediction.draw_number,
        draw_date=lotto_draw.draw_date if lotto_draw else date.today(),
        predicted_numbers=predicted_numbers,
        matched_count=best_prediction.matched_count,
        prize_rank=best_prediction.prize_rank,
        prize_amount=best_prediction.prize_amount,
        strategy_name=best_prediction.strategy_name,
        created_at=best_prediction.created_at
    )
    
    return BestResultResponse(
        has_predictions=True,
        best_matched_count=best_prediction.matched_count,
        best_prediction=best_prediction_info,
        total_predictions=total_predictions,
        total_winners=total_winners,
        user_tier=current_user.tier
    )


@router.get("/dashboard", response_model=UserDashboardResponse)
async def get_user_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자 대시보드 데이터 조회
    - 최고 일치 수, 해당 회차, 날짜
    - 전체 통계 및 최근 활동
    """
    
    user_id = current_user.id
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    
    # 기본 정보 (soft delete 적용)
    total_predictions = db.query(Prediction).filter(
        Prediction.user_id == user_id,
        Prediction.deleted_at.is_(None)
    ).count()
    
    # 크레딧 사용량 계산
    total_credits_used = db.query(func.sum(CreditTransaction.amount)).filter(
        CreditTransaction.user_id == user_id,
        CreditTransaction.amount < 0
    ).scalar() or 0
    total_credits_used = abs(total_credits_used)
    
    # 최고 성과 예측 찾기 (soft delete 적용)
    best_prediction = db.query(Prediction).filter(
        Prediction.user_id == user_id,
        Prediction.checked_at.is_not(None),
        Prediction.deleted_at.is_(None)
    ).order_by(desc(Prediction.matched_count)).first()
    
    best_matched_count = best_prediction.matched_count if best_prediction else 0
    
    # 최고 성과 예측 상세 정보
    best_prediction_info = None
    if best_prediction:
        # 해당 회차의 로또 정보 가져오기
        lotto_draw = db.query(LottoDraw).filter(
            LottoDraw.round == best_prediction.draw_number
        ).first()
        
        predicted_numbers = [
            getattr(best_prediction, f'num{i}') 
            for i in range(1, 7) 
            if getattr(best_prediction, f'num{i}') is not None
        ]
        
        best_prediction_info = BestPredictionInfo(
            prediction_id=str(best_prediction.id),
            draw_number=best_prediction.draw_number,
            draw_date=lotto_draw.draw_date if lotto_draw else date.today(),
            predicted_numbers=predicted_numbers,
            matched_count=best_prediction.matched_count,
            prize_rank=best_prediction.prize_rank,
            prize_amount=best_prediction.prize_amount,
            strategy_name=best_prediction.strategy_name,
            created_at=best_prediction.created_at
        )
    
    # 일치 수별 통계
    total_matches_by_count = {}
    for i in range(3, 7):  # 3등부터 1등까지
        count = db.query(Prediction).filter(
            Prediction.user_id == user_id,
            Prediction.matched_count == i,
            Prediction.deleted_at.is_(None)
        ).count()
        total_matches_by_count[str(i)] = count
    
    # 당첨 통계 (soft delete 적용)
    total_winners = db.query(Prediction).filter(
        Prediction.user_id == user_id,
        Prediction.is_winner == True,
        Prediction.deleted_at.is_(None)
    ).count()
    
    total_prize_amount = db.query(func.sum(Prediction.prize_amount)).filter(
        Prediction.user_id == user_id,
        Prediction.is_winner == True,
        Prediction.deleted_at.is_(None)
    ).scalar() or 0
    
    win_rate = (total_winners / total_predictions * 100) if total_predictions > 0 else 0
    
    # 최근 30일 예측 수 (soft delete 적용)
    recent_predictions_count = db.query(Prediction).filter(
        Prediction.user_id == user_id,
        Prediction.created_at >= thirty_days_ago,
        Prediction.deleted_at.is_(None)
    ).count()
    
    # 이번 달 예측 수 (soft delete 적용)
    month_start = datetime(now.year, now.month, 1)
    predictions_this_month = db.query(Prediction).filter(
        Prediction.user_id == user_id,
        Prediction.created_at >= month_start,
        Prediction.deleted_at.is_(None)
    ).count()
    
    # 가장 자주 사용한 전략 (soft delete 적용)
    favorite_strategy_result = db.query(
        Prediction.strategy_name,
        func.count(Prediction.strategy_name).label('count')
    ).filter(
        Prediction.user_id == user_id,
        Prediction.deleted_at.is_(None)
    ).group_by(Prediction.strategy_name).order_by(desc('count')).first()
    
    favorite_strategy = favorite_strategy_result[0] if favorite_strategy_result else None
    
    # 대시보드 통계 구성
    dashboard_stats = UserDashboardStats(
        total_predictions=total_predictions,
        total_credits_used=total_credits_used,
        current_credits=current_user.credits,
        member_since=current_user.created_at.date(),
        best_matched_count=best_matched_count,
        best_prediction=best_prediction_info,
        total_matches_by_count=total_matches_by_count,
        total_prize_amount=total_prize_amount,
        total_winners=total_winners,
        win_rate=round(win_rate, 2),
        recent_predictions_count=recent_predictions_count,
        favorite_strategy=favorite_strategy,
        user_tier=current_user.tier,
        predictions_this_month=predictions_this_month
    )
    
    # 최근 활동 조회 (최근 10개, soft delete 적용)
    recent_predictions = db.query(Prediction).filter(
        Prediction.user_id == user_id,
        Prediction.deleted_at.is_(None)
    ).order_by(desc(Prediction.created_at)).limit(10).all()
    
    recent_activities = []
    for pred in recent_predictions:
        predicted_numbers = [
            getattr(pred, f'num{i}') 
            for i in range(1, 7) 
            if getattr(pred, f'num{i}') is not None
        ]
        
        recent_activities.append(UserRecentActivity(
            prediction_id=str(pred.id),
            draw_number=pred.draw_number,
            predicted_numbers=predicted_numbers,
            matched_count=pred.matched_count,
            is_winner=pred.is_winner,
            prize_amount=pred.prize_amount,
            strategy_name=pred.strategy_name,
            created_at=pred.created_at
        ))
    
    return UserDashboardResponse(
        stats=dashboard_stats,
        recent_activities=recent_activities
    )


# 이 엔드포인트는 가장 마지막에 위치해야 함 (/{prediction_id} 패턴이 다른 경로와 충돌 방지)
@router.get("/{prediction_id}", response_model=PredictionDetailResponse)
async def get_prediction(
    prediction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    특정 예측 상세 조회
    - 예측 번호
    - 실제 당첨 번호 (추첨 후)
    - 일치 개수
    """
    
    # 예측 조회 (soft delete 적용)
    prediction = db.query(Prediction).filter(
        Prediction.id == prediction_id,
        Prediction.user_id == current_user.id,
        Prediction.deleted_at.is_(None)
    ).first()
    
    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found"
        )
    
    # 실제 당첨번호 조회
    actual_draw = db.query(LottoDraw).filter(
        LottoDraw.round == prediction.draw_number
    ).first()
    
    numbers = [prediction.num1, prediction.num2, prediction.num3, 
               prediction.num4, prediction.num5, prediction.num6]
    
    actual_numbers = None
    actual_bonus = None
    if actual_draw:
        actual_numbers = [actual_draw.num1, actual_draw.num2, actual_draw.num3,
                         actual_draw.num4, actual_draw.num5, actual_draw.num6]
        actual_bonus = actual_draw.bonus
    
    return PredictionDetailResponse(
        id=prediction.id,
        draw_number=prediction.draw_number,
        strategy_name=prediction.strategy_name,
        numbers=numbers,
        confidence_score=prediction.confidence_score,
        matched_count=prediction.matched_count,
        is_winner=prediction.is_winner,
        actual_draw=actual_numbers,
        actual_bonus=actual_bonus,
        created_at=prediction.created_at
    )


@router.get("/strategies/available")
async def get_available_prediction_strategies(
    current_user: User = Depends(get_current_user)
):
    """
    사용자가 사용할 수 있는 예측 전략 목록 조회
    
    - VIP 전략 필터링
    - 운세 기반 전략 필터링 (생년월일 + 운세 활성화 필요)
    """
    
    # 사용자 운세 설정 확인
    has_fortune = bool(current_user.birth_year and current_user.fortune_enabled)
    
    available_strategies = get_available_strategies(
        user_tier=current_user.tier,
        has_fortune=has_fortune
    )
    
    return {
        "strategies": available_strategies,
        "user_info": {
            "tier": current_user.tier,
            "has_fortune": has_fortune,
            "birth_year": current_user.birth_year,
            "fortune_enabled": current_user.fortune_enabled
        }
    }


@router.delete("/{prediction_id}", status_code=204)
async def delete_prediction(
    prediction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    예측 삭제 (추첨 전에만 가능)
    """
    
    # 예측 조회 (soft delete 적용)
    prediction = db.query(Prediction).filter(
        Prediction.id == prediction_id,
        Prediction.user_id == current_user.id,
        Prediction.deleted_at.is_(None)
    ).first()
    
    if not prediction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Prediction not found"
        )
    
    # 이미 추첨이 완료된 경우 삭제 불가
    actual_draw = db.query(LottoDraw).filter(
        LottoDraw.round == prediction.draw_number
    ).first()
    
    if actual_draw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete prediction after draw is completed"
        )
    
    # 24시간 이내에 생성된 예측만 삭제 가능
    if datetime.utcnow() - prediction.created_at > timedelta(hours=24):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete prediction older than 24 hours"
        )
    
    try:
        # soft delete: deleted_at 설정
        prediction.deleted_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete prediction: {str(e)}"
        )


@router.post("/similar-results", response_model=SimilarResultsResponse)
async def find_similar_winning_results(
    numbers: List[int],
    limit: int = Query(10, ge=1, le=50, description="결과 개수 제한"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    입력된 번호 조합과 유사한 과거 당첨 결과 찾기
    
    - 6개 번호 조합과 가장 유사한 과거 당첨 번호들을 반환
    - 유사도는 일치하는 번호 개수와 번호 패턴으로 계산
    """
    
    # 입력 검증
    if len(numbers) != 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="6개의 번호가 필요합니다."
        )
    
    if any(n < 1 or n > 45 for n in numbers):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="번호는 1-45 범위여야 합니다."
        )
    
    # 번호가 정렬되어 있는지 확인하고 정렬
    query_numbers = sorted(numbers)
    
    try:
        # 모든 과거 당첨 결과 조회 (최신순)
        historical_draws = db.query(LottoDraw).order_by(LottoDraw.round.desc()).all()
        
        if not historical_draws:
            return SimilarResultsResponse(
                query_numbers=query_numbers,
                total_historical_draws=0,
                similar_results=[]
            )
        
        similar_results = []
        
        for draw in historical_draws:
            # 당첨 번호 배열
            winning_numbers = sorted([
                draw.num1, draw.num2, draw.num3, 
                draw.num4, draw.num5, draw.num6
            ])
            
            # 일치하는 번호 개수 계산
            matched_count = len(set(query_numbers) & set(winning_numbers))
            
            # 유사도 계산 (일치 개수 기반 + 번호 범위 유사성)
            similarity_score = calculate_similarity_score(query_numbers, winning_numbers)
            
            similar_results.append({
                'draw': draw,
                'winning_numbers': winning_numbers,
                'matched_count': matched_count,
                'similarity_score': similarity_score
            })
        
        # 유사도 순으로 정렬 (일치 개수 우선, 그 다음 유사도 점수)
        similar_results.sort(key=lambda x: (x['matched_count'], x['similarity_score']), reverse=True)
        
        # 상위 결과만 선택
        top_results = similar_results[:limit]
        
        # 응답 형식으로 변환
        results = []
        for result in top_results:
            draw = result['draw']
            results.append(SimilarWinningResult(
                round=draw.round,
                draw_date=draw.draw_date,
                winning_numbers=result['winning_numbers'],
                bonus_number=draw.bonus,
                matched_count=result['matched_count'],
                similarity_score=round(result['similarity_score'], 3),
                jackpot_amount=draw.jackpot_amount,
                jackpot_winners=draw.jackpot_winners
            ))
        
        return SimilarResultsResponse(
            query_numbers=query_numbers,
            total_historical_draws=len(historical_draws),
            similar_results=results
        )
        
    except Exception as e:
        logger.error(f"Error finding similar results: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="유사한 결과 검색 중 오류가 발생했습니다."
        )


def calculate_similarity_score(query_numbers: List[int], winning_numbers: List[int]) -> float:
    """
    두 번호 조합의 유사도 점수 계산
    
    Args:
        query_numbers: 질의 번호 (6개)
        winning_numbers: 당첨 번호 (6개)
    
    Returns:
        float: 유사도 점수 (0-100)
    """
    
    # 1. 직접 일치하는 번호 개수 (가중치 70%)
    direct_matches = len(set(query_numbers) & set(winning_numbers))
    direct_score = (direct_matches / 6) * 70
    
    # 2. 번호 범위 유사성 (가중치 20%)
    # 각 번호가 얼마나 가까운 위치에 있는지 계산
    range_similarity = 0
    for q_num in query_numbers:
        min_distance = min(abs(q_num - w_num) for w_num in winning_numbers)
        # 거리가 가까울수록 높은 점수 (최대 5점 차이까지 점수 부여)
        range_similarity += max(0, (5 - min_distance) / 5)
    
    range_score = (range_similarity / 6) * 20
    
    # 3. 패턴 유사성 (가중치 10%)
    # 연속 번호, 간격 패턴 등
    pattern_score = 0
    
    # 연속 번호 개수 비교
    query_consecutive = count_consecutive_numbers(query_numbers)
    winning_consecutive = count_consecutive_numbers(winning_numbers)
    consecutive_similarity = 1 - abs(query_consecutive - winning_consecutive) / 6
    
    # 홀짝 분포 비교
    query_odd_count = sum(1 for n in query_numbers if n % 2 == 1)
    winning_odd_count = sum(1 for n in winning_numbers if n % 2 == 1)
    odd_even_similarity = 1 - abs(query_odd_count - winning_odd_count) / 6
    
    pattern_score = ((consecutive_similarity + odd_even_similarity) / 2) * 10
    
    total_score = direct_score + range_score + pattern_score
    return min(100, total_score)  # 최대 100점


def count_consecutive_numbers(numbers: List[int]) -> int:
    """연속 번호 개수 계산"""
    if len(numbers) < 2:
        return 0
    
    consecutive_count = 0
    for i in range(len(numbers) - 1):
        if numbers[i + 1] - numbers[i] == 1:
            consecutive_count += 1
    
    return consecutive_count