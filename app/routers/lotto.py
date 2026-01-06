from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_, or_
from typing import List, Optional, Dict, Any
import requests
from collections import Counter
from datetime import datetime, date, timedelta
import asyncio
import time
from bs4 import BeautifulSoup
import re
import logging

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import LottoDraw, User, UserTier, Prediction
from app.schemas.lotto import (
    LottoDrawResponse, LottoDrawsResponse, LottoStatistics,
    NumberFrequency, ZoneStats, ConsecutiveAnalysis, SumRangeAnalysis,
    RecentTrends, LottoSyncRequest, LottoSyncResponse,
    LottoSearchRequest, LottoSearchResponse
)
from app.schemas.winning import WinningInfoResponse, LastDrawInfo, PrizeInfo, MemberWinner

router = APIRouter(prefix="/lotto", tags=["lotto"])

# Logger 설정
logger = logging.getLogger(__name__)


# /latest 엔드포인트는 admin API로 이동됨


@router.get("/draws", response_model=LottoDrawsResponse)
async def get_draws(
    from_round: Optional[int] = Query(None, description="Starting round number"),
    to_round: Optional[int] = Query(None, description="Ending round number"),
    limit: int = Query(10, ge=1, le=100, description="Maximum number of draws to return"),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    db: Session = Depends(get_db)
):
    """
    회차 범위 지정하여 당첨번호 조회
    - from_round ~ to_round
    - limit 개수만큼
    - 페이지네이션 지원
    """
    
    # 기본 쿼리
    query = db.query(LottoDraw)
    
    # 범위 필터링
    if from_round and to_round:
        if from_round > to_round:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="from_round must be less than or equal to to_round"
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
    
    # 페이지네이션
    offset = (page - 1) * limit
    draws = query.order_by(desc(LottoDraw.round)).offset(offset).limit(limit).all()
    
    # 응답 데이터 구성
    draw_responses = []
    for draw in draws:
        numbers = [draw.num1, draw.num2, draw.num3, draw.num4, draw.num5, draw.num6]
        draw_responses.append(LottoDrawResponse(
            round=draw.round,
            draw_date=draw.draw_date,
            numbers=numbers,
            bonus=draw.bonus,
            jackpot_amount=draw.jackpot_amount
        ))
    
    return LottoDrawsResponse(
        total=total,
        draws=draw_responses,
        from_round=from_round,
        to_round=to_round
    )


@router.get("/statistics", response_model=LottoStatistics)
async def get_statistics(
    recent_weeks: int = Query(12, ge=4, le=52, description="Number of recent weeks to analyze"),
    db: Session = Depends(get_db)
):
    """
    전체 통계 정보
    
    Response:
    {
        "total_draws": 1199,
        "most_frequent": [
            {"number": 34, "count": 187, "percentage": 15.6},
            {"number": 27, "count": 182, "percentage": 15.2},
            ...
        ],
        "least_frequent": [...],
        "odd_even_ratio": {"odd": 0.52, "even": 0.48},
        "zone_distribution": [
            {"zone": "Zone 1", "range": "1-9", "count": 245, "percentage": 18.2},
            ...
        ]
    }
    """
    
    # 모든 당첨 데이터 조회
    all_draws = db.query(LottoDraw).order_by(desc(LottoDraw.round)).all()
    
    if not all_draws:
        # 빈 데이터 반환
        return LottoStatistics(
            total_draws=0,
            analysis_period=f"Last {recent_weeks} weeks",
            most_frequent=[],
            least_frequent=[],
            odd_even_ratio={"odd": 0.0, "even": 0.0},
            zone_distribution=[],
            recent_trends=RecentTrends(hot_numbers=[], cold_numbers=[], 
                                     trending_up=[], trending_down=[]),
            consecutive_analysis=ConsecutiveAnalysis(avg_consecutive=0.0, max_consecutive=0,
                                                   consecutive_frequency={}),
            sum_range_analysis=SumRangeAnalysis(avg_sum=0.0, min_sum=0, max_sum=0,
                                              sum_distribution={}),
            bonus_stats={},
            updated_at=datetime.utcnow()
        )
    
    total_draws = len(all_draws)
    
    # 모든 번호 수집
    all_numbers = []
    all_bonus = []
    all_sums = []
    consecutive_counts = []
    
    for draw in all_draws:
        numbers = [draw.num1, draw.num2, draw.num3, draw.num4, draw.num5, draw.num6]
        all_numbers.extend(numbers)
        all_bonus.append(draw.bonus)
        all_sums.append(sum(numbers))
        
        # 연속 번호 계산
        consecutive = 0
        for i in range(len(numbers) - 1):
            if numbers[i + 1] - numbers[i] == 1:
                consecutive += 1
        consecutive_counts.append(consecutive)
    
    # 최근 트렌드 분석 (최근 몇 주)
    recent_cutoff_date = datetime.utcnow().date() - timedelta(weeks=recent_weeks)
    recent_draws = [draw for draw in all_draws 
                   if draw.draw_date >= recent_cutoff_date]
    
    recent_numbers = []
    for draw in recent_draws:
        recent_numbers.extend([draw.num1, draw.num2, draw.num3, 
                              draw.num4, draw.num5, draw.num6])
    
    # 번호별 빈도 분석
    frequency = Counter(all_numbers)
    recent_frequency = Counter(recent_numbers)
    
    # 가장 자주/적게 나온 번호
    most_frequent = [
        NumberFrequency(
            number=num, 
            count=count, 
            percentage=round(count * 100 / (total_draws * 6), 2)
        )
        for num, count in frequency.most_common(10)
    ]
    
    least_frequent = [
        NumberFrequency(
            number=num, 
            count=count, 
            percentage=round(count * 100 / (total_draws * 6), 2)
        )
        for num, count in frequency.most_common()[-10:]
    ]
    
    # 홀짝 비율
    odd_count = sum(1 for num in all_numbers if num % 2 == 1)
    total_numbers = len(all_numbers)
    odd_ratio = odd_count / total_numbers if total_numbers > 0 else 0
    even_ratio = 1 - odd_ratio
    
    # 구간별 분포 (5개 구간)
    zones = [
        ("Zone 1", "1-9", list(range(1, 10))),
        ("Zone 2", "10-18", list(range(10, 19))),
        ("Zone 3", "19-27", list(range(19, 28))),
        ("Zone 4", "28-36", list(range(28, 37))),
        ("Zone 5", "37-45", list(range(37, 46)))
    ]
    
    zone_distribution = []
    for zone_name, zone_range, zone_numbers in zones:
        zone_count = sum(frequency[num] for num in zone_numbers)
        zone_percentage = round(zone_count * 100 / total_numbers, 2) if total_numbers > 0 else 0
        zone_distribution.append(ZoneStats(
            zone=zone_name,
            range=zone_range,
            count=zone_count,
            percentage=zone_percentage
        ))
    
    # 최근 트렌드
    hot_numbers = [num for num, _ in recent_frequency.most_common(10)]
    cold_numbers = [num for num in range(1, 46) 
                   if num not in dict(recent_frequency.most_common(35))][:10]
    
    # 추세 분석 (증가/감소)
    if len(all_draws) >= 20:
        # 최근 10회와 그 이전 10회 비교
        very_recent = all_draws[:10]
        somewhat_recent = all_draws[10:20]
        
        very_recent_numbers = []
        somewhat_recent_numbers = []
        
        for draw in very_recent:
            very_recent_numbers.extend([draw.num1, draw.num2, draw.num3,
                                      draw.num4, draw.num5, draw.num6])
        
        for draw in somewhat_recent:
            somewhat_recent_numbers.extend([draw.num1, draw.num2, draw.num3,
                                          draw.num4, draw.num5, draw.num6])
        
        very_recent_freq = Counter(very_recent_numbers)
        somewhat_recent_freq = Counter(somewhat_recent_numbers)
        
        trending_up = []
        trending_down = []
        
        for num in range(1, 46):
            recent_count = very_recent_freq.get(num, 0)
            past_count = somewhat_recent_freq.get(num, 0)
            
            if recent_count > past_count:
                trending_up.append(num)
            elif recent_count < past_count:
                trending_down.append(num)
        
        trending_up = trending_up[:5]
        trending_down = trending_down[:5]
    else:
        trending_up = []
        trending_down = []
    
    recent_trends = RecentTrends(
        hot_numbers=hot_numbers,
        cold_numbers=cold_numbers,
        trending_up=trending_up,
        trending_down=trending_down
    )
    
    # 연속 번호 분석
    consecutive_freq = Counter(consecutive_counts)
    consecutive_analysis = ConsecutiveAnalysis(
        avg_consecutive=round(sum(consecutive_counts) / len(consecutive_counts), 2),
        max_consecutive=max(consecutive_counts) if consecutive_counts else 0,
        consecutive_frequency={str(k): v for k, v in consecutive_freq.items()}
    )
    
    # 합계 분석
    sum_ranges = [
        (60, 90), (91, 120), (121, 150), (151, 180), (181, 210), (211, 240)
    ]
    sum_distribution = {}
    for start, end in sum_ranges:
        count = sum(1 for s in all_sums if start <= s <= end)
        sum_distribution[f"{start}-{end}"] = count
    
    sum_range_analysis = SumRangeAnalysis(
        avg_sum=round(sum(all_sums) / len(all_sums), 2) if all_sums else 0,
        min_sum=min(all_sums) if all_sums else 0,
        max_sum=max(all_sums) if all_sums else 0,
        sum_distribution=sum_distribution
    )
    
    # 보너스 번호 통계
    bonus_frequency = Counter(all_bonus)
    most_common_bonus = bonus_frequency.most_common(1)[0] if all_bonus else (0, 0)
    bonus_stats = {
        "most_frequent_bonus": most_common_bonus[0],
        "most_frequent_count": most_common_bonus[1],
        "avg_bonus": round(sum(all_bonus) / len(all_bonus), 2) if all_bonus else 0
    }
    
    return LottoStatistics(
        total_draws=total_draws,
        analysis_period=f"All time (Last {recent_weeks} weeks for trends)",
        most_frequent=most_frequent,
        least_frequent=least_frequent,
        odd_even_ratio={"odd": round(odd_ratio, 3), "even": round(even_ratio, 3)},
        zone_distribution=zone_distribution,
        recent_trends=recent_trends,
        consecutive_analysis=consecutive_analysis,
        sum_range_analysis=sum_range_analysis,
        bonus_stats=bonus_stats,
        updated_at=datetime.utcnow()
    )


@router.post("/sync", response_model=LottoSyncResponse)
async def sync_lotto_data(
    request: LottoSyncRequest = LottoSyncRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    최신 로또 데이터 동기화 (관리자 전용)
    - 동행복권 API 또는 웹 스크래핑
    """
    
    # 관리자 권한 확인
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    
    sync_start_time = datetime.utcnow()
    synced_rounds = []
    failed_rounds = []
    
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
                            jackpot_amount=draw_data['jackpot_amount']
                        )
                        db.add(new_draw)
                    
                    synced_rounds.append(round_num)
                else:
                    failed_rounds.append(round_num)
                
                # API 호출 제한 고려
                await asyncio.sleep(0.5)
                
            except Exception as e:
                logger.error(f"Failed to sync round {round_num}: {e}")
                failed_rounds.append(round_num)
        
        db.commit()
        
        return LottoSyncResponse(
            success=True,
            message=f"Successfully synced {len(synced_rounds)} rounds",
            synced_rounds=synced_rounds,
            total_synced=len(synced_rounds),
            failed_rounds=failed_rounds,
            sync_time=sync_start_time
        )
        
    except Exception as e:
        db.rollback()
        return LottoSyncResponse(
            success=False,
            message=f"Sync failed: {str(e)}",
            synced_rounds=synced_rounds,
            total_synced=len(synced_rounds),
            failed_rounds=failed_rounds,
            sync_time=sync_start_time
        )


@router.post("/search", response_model=LottoSearchResponse)
async def search_numbers(
    request: LottoSearchRequest,
    db: Session = Depends(get_db)
):
    """
    특정 번호 조합이 나온 회차 검색
    """
    
    search_numbers = set(request.numbers)
    all_draws = db.query(LottoDraw).order_by(desc(LottoDraw.round)).all()
    
    matches = []
    
    for draw in all_draws:
        draw_numbers = {draw.num1, draw.num2, draw.num3, draw.num4, draw.num5, draw.num6}
        
        # 보너스 포함 여부
        if request.include_bonus:
            draw_numbers.add(draw.bonus)
        
        # 일치하는 번호 개수
        matched_count = len(search_numbers & draw_numbers)
        
        if matched_count > 0:
            matches.append({
                "round": draw.round,
                "draw_date": draw.draw_date.isoformat(),
                "numbers": [draw.num1, draw.num2, draw.num3, draw.num4, draw.num5, draw.num6],
                "bonus": draw.bonus,
                "matched_count": matched_count,
                "matched_numbers": list(search_numbers & draw_numbers)
            })
    
    return LottoSearchResponse(
        search_numbers=request.numbers,
        total_matches=len(matches),
        matches=matches
    )


@router.get("/round/{round_number}", response_model=LottoDrawResponse)
async def get_draw_by_round(
    round_number: int,
    db: Session = Depends(get_db)
):
    """
    특정 회차 당첨번호 조회
    """
    
    if round_number < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Round number must be positive"
        )
    
    draw = db.query(LottoDraw).filter(LottoDraw.round == round_number).first()
    
    if not draw:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draw for round {round_number} not found"
        )
    
    numbers = [draw.num1, draw.num2, draw.num3, draw.num4, draw.num5, draw.num6]
    
    return LottoDrawResponse(
        round=draw.round,
        draw_date=draw.draw_date,
        numbers=numbers,
        bonus=draw.bonus,
        jackpot_amount=draw.jackpot_amount
    )


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
                    'jackpot_amount': data.get('firstAccumamnt', 0)
                }
        
        return None
        
    except Exception as e:
        logger.error(f"Error fetching lotto data for round {round_number}: {e}")
        return None


def get_current_user_optional() -> Optional[User]:
    """선택적 사용자 인증 - 로그인하지 않은 사용자도 접근 가능"""
    # 현재는 간단히 None 반환 (나중에 토큰이 있으면 검증하도록 구현)
    return None


@router.get("/winning-info", response_model=WinningInfoResponse)
async def get_winning_info(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """최신 로또 당첨 번호, 당첨금 정보, 그리고 회원들의 당첨 내역을 반환"""
    try:
        # 1. 최신 추첨 정보 조회
        latest_draw = db.query(LottoDraw).order_by(desc(LottoDraw.round)).first()
        
        if not latest_draw:
            raise HTTPException(status_code=404, detail="최신 추첨 정보를 찾을 수 없습니다")
        
        last_draw = LastDrawInfo(
            draw_number=latest_draw.round,
            draw_date=latest_draw.draw_date.strftime("%Y-%m-%d"),
            numbers=[latest_draw.num1, latest_draw.num2, latest_draw.num3, 
                    latest_draw.num4, latest_draw.num5, latest_draw.num6],
            bonus=latest_draw.bonus
        )
        
        # 2. 1등 당첨 정보만 (lotto_draws 테이블에서 조회)
        prizes = [
            PrizeInfo(
                rank=1, 
                prize_amount=latest_draw.jackpot_amount,
                winners=latest_draw.jackpot_winners
            )
        ]
        
        # 3. 회원 당첨자 정보 (3등 이하, 최근 4주, 개인정보 보호)
        four_weeks_ago = datetime.utcnow() - timedelta(weeks=4)
        
        member_winners_query = (
            db.query(Prediction, User.nickname)
            .join(User, Prediction.user_id == User.id)
            .filter(
                and_(
                    Prediction.prize_rank.isnot(None),
                    Prediction.prize_rank >= 3,  # 3등 이하만
                    Prediction.is_winner == True,
                    Prediction.created_at >= four_weeks_ago
                )
            )
            .order_by(Prediction.prize_rank.asc(), Prediction.prize_amount.desc())
            .limit(10)
            .all()
        )
        
        def mask_nickname(nickname: str) -> str:
            """닉네임을 개인정보 보호를 위해 첫글자만 표시하고 나머지는 *로 치환"""
            if not nickname or len(nickname) == 0:
                return "익*"
            elif len(nickname) == 1:
                return nickname + "*"
            else:
                return nickname[0] + "*" * (len(nickname) - 1)
        
        member_winners = []
        for prediction, nickname in member_winners_query:
            member_winners.append(MemberWinner(
                user_nickname=mask_nickname(nickname),
                numbers=[prediction.num1, prediction.num2, prediction.num3,
                        prediction.num4, prediction.num5, prediction.num6],
                matched_count=prediction.matched_count,
                rank=prediction.prize_rank,
                prize_amount=prediction.prize_amount,
                draw_number=prediction.draw_number
            ))
        
        return WinningInfoResponse(
            last_draw=last_draw,
            prizes=prizes,
            member_winners=member_winners
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"당첨 정보 조회 중 오류: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="당첨 정보를 불러올 수 없습니다."
        )


@router.get("/health")
async def health_check():
    """로또 API 서비스 상태 확인"""
    try:
        latest_round = await _get_latest_round_number()
        return {
            "status": "healthy",
            "latest_round": latest_round,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }