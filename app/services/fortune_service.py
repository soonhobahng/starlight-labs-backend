# app/services/fortune_service.py

import hashlib
import random
from datetime import date, datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.fortune import DailyFortune, FortuneMessage, ZodiacDailyStat
from app.models.models import User
from app.core.constants import LUCKY_COLORS, LUCKY_DIRECTIONS, LUCK_RANGE_HIGH, LUCK_RANGE_MEDIUM

class FortuneService:
    """운세 계산 및 관리 서비스"""
    
    @staticmethod
    def _generate_deterministic_seed(user_id: str, fortune_date: date, suffix: str = "") -> int:
        """날짜 + 사용자 ID로 일관성 있는 시드 생성"""
        seed_string = f"{user_id}_{fortune_date.isoformat()}_{suffix}"
        seed_hash = hashlib.md5(seed_string.encode()).hexdigest()
        return int(seed_hash, 16)
    
    @staticmethod
    def calculate_fortune_scores(user_id: str, fortune_date: date) -> dict:
        """운세 점수 계산 (같은 날은 같은 결과)
        
        Returns:
            {
                "overall": 87,
                "wealth": 75,
                "lottery": 92
            }
        """
        seed = FortuneService._generate_deterministic_seed(user_id, fortune_date)
        random.seed(seed)
        
        # 점수 범위: 60-95 (너무 낮거나 높지 않게)
        overall_luck = random.randint(60, 95)
        wealth_luck = random.randint(50, 90)
        lottery_luck = random.randint(55, 100)
        
        return {
            "overall": overall_luck,
            "wealth": wealth_luck,
            "lottery": lottery_luck
        }
    
    @staticmethod
    def generate_lucky_numbers(user_id: str, fortune_date: date) -> List[int]:
        """개인별 행운의 번호 7개 생성 (1-45, 중복 없음)"""
        seed = FortuneService._generate_deterministic_seed(user_id, fortune_date, "numbers")
        random.seed(seed)
        
        lucky_numbers = sorted(random.sample(range(1, 46), 7))
        return lucky_numbers
    
    @staticmethod
    def get_lucky_color(fortune_date: date) -> str:
        """날짜 기반 행운의 색상"""
        seed = int(hashlib.md5(fortune_date.isoformat().encode()).hexdigest(), 16)
        random.seed(seed)
        return random.choice(LUCKY_COLORS)
    
    @staticmethod
    def get_lucky_direction(user_id: str, fortune_date: date) -> str:
        """사용자별 행운의 방향"""
        seed = FortuneService._generate_deterministic_seed(user_id, fortune_date, "direction")
        random.seed(seed)
        return random.choice(LUCKY_DIRECTIONS)
    
    @staticmethod
    def get_fortune_message(db: Session, lottery_luck: int, category: str = 'general') -> str:
        """점수 범위에 따른 운세 메시지 선택"""
        if lottery_luck >= LUCK_RANGE_HIGH:
            luck_range = 'high'
        elif lottery_luck >= LUCK_RANGE_MEDIUM:
            luck_range = 'medium'
        else:
            luck_range = 'low'
        
        try:
            # 첫번째 시도: is_active 포함하여 조회
            try:
                messages = db.query(FortuneMessage).filter(
                    FortuneMessage.luck_range == luck_range,
                    FortuneMessage.category == category,
                    FortuneMessage.is_active == True
                ).all()
            except Exception:
                # 두번째 시도: is_active 없이 조회 (컬럼이 없는 경우)
                messages = db.query(FortuneMessage).filter(
                    FortuneMessage.luck_range == luck_range,
                    FortuneMessage.category == category
                ).all()
            
            if messages:
                # 랜덤 선택 (하지만 같은 조건이면 같은 메시지)
                seed = lottery_luck + len(messages)
                random.seed(seed)
                return random.choice(messages).message
        except Exception as e:
            # DB 에러 발생 시 트랜잭션 롤백
            try:
                db.rollback()
            except:
                pass
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Fortune message DB query failed: {e}")
        
        # 기본 메시지 반환 (DB 없어도 동작)
        default_messages = {
            'high': {
                'general': "오늘은 특히 행운이 가득한 날입니다! ✨",
                'timing': "오전 시간대가 특히 좋으니 중요한 일은 오전에 해보세요!"
            },
            'medium': {
                'general': "안정적인 하루가 될 것 같습니다.",
                'timing': "오후 시간대에 좋은 기회가 있을 것 같습니다."
            },
            'low': {
                'general': "조금 더 신중하게 행동하세요.",
                'timing': "서두르지 말고 차근차근 진행하세요."
            }
        }
        
        return default_messages.get(luck_range, {}).get(category, "오늘도 행운을 빕니다!")
    
    @staticmethod
    def get_or_create_daily_fortune(
        db: Session,
        user_id: str,
        birth_year: int,
        fortune_date: date
    ) -> DailyFortune:
        """오늘의 운세 조회 또는 생성 (캐싱)"""
        
        try:
            # 캐시 조회
            fortune = db.query(DailyFortune).filter(
                DailyFortune.user_id == user_id,
                DailyFortune.fortune_date == fortune_date
            ).first()
            
            if fortune:
                return fortune
        except Exception as e:
            # DB 에러 발생 시 트랜잭션 롤백
            try:
                db.rollback()
            except:
                pass
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"DailyFortune query failed, creating in-memory fortune: {e}")
        
        # 새로 생성
        scores = FortuneService.calculate_fortune_scores(user_id, fortune_date)
        lucky_numbers = FortuneService.generate_lucky_numbers(user_id, fortune_date)
        
        fortune_message = FortuneService.get_fortune_message(db, scores['lottery'], 'general')
        advice_message = FortuneService.get_fortune_message(db, scores['lottery'], 'timing')
        
        try:
            # DB에 저장 시도
            fortune = DailyFortune(
                user_id=user_id,
                fortune_date=fortune_date,
                overall_luck=scores['overall'],
                wealth_luck=scores['wealth'],
                lottery_luck=scores['lottery'],
                lucky_numbers=lucky_numbers,
                lucky_color=FortuneService.get_lucky_color(fortune_date),
                lucky_direction=FortuneService.get_lucky_direction(user_id, fortune_date),
                fortune_message=fortune_message,
                advice=advice_message
            )
            
            db.add(fortune)
            db.commit()
            db.refresh(fortune)
            
            return fortune
        except Exception as e:
            # DB 에러 발생 시 트랜잭션 롤백
            try:
                db.rollback()
            except:
                pass
                
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"DailyFortune save failed, returning temp object: {e}")
            
            # 임시 객체 생성 (DB 저장 없이)
            class TempFortune:
                def __init__(self):
                    self.user_id = user_id
                    self.fortune_date = fortune_date
                    self.overall_luck = scores['overall']
                    self.wealth_luck = scores['wealth']
                    self.lottery_luck = scores['lottery']
                    self.lucky_numbers = lucky_numbers
                    self.lucky_color = FortuneService.get_lucky_color(fortune_date)
                    self.lucky_direction = FortuneService.get_lucky_direction(user_id, fortune_date)
                    self.fortune_message = fortune_message
                    self.advice = advice_message
            
            return TempFortune()
    
    @staticmethod
    def calculate_zodiac_rank(db: Session, zodiac_sign: str, fortune_date: date) -> dict:
        """띠별 순위 계산"""
        
        try:
            # 오늘 날짜의 모든 띠 통계
            stats = db.query(ZodiacDailyStat).filter(
                ZodiacDailyStat.stats_date == fortune_date
            ).order_by(ZodiacDailyStat.avg_lottery_luck.desc()).all()
            
            if stats:
                # 내 띠 순위 찾기
                rank = 1
                for stat in stats:
                    if stat.zodiac_sign == zodiac_sign:
                        break
                    rank += 1
                
                percentile = int((1 - rank / len(stats)) * 100)
                
                return {
                    "zodiac_rank": rank,
                    "total_zodiacs": len(stats),
                    "percentile": percentile
                }
        except Exception as e:
            # DB 에러 발생 시 트랜잭션 롤백
            try:
                db.rollback()
            except:
                pass
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Zodiac stats query failed: {e}")
        
        # 기본값 반환 (DB 없어도 동작)
        return {"zodiac_rank": 6, "total_zodiacs": 12, "percentile": 50}