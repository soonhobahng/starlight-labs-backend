# app/services/fortune_service.py

import hashlib
import random
from datetime import date, datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.fortune import DailyFortune, FortuneMessage, ZodiacDailyStat
from app.models.models import User
from app.core.constants import (
    LUCKY_COLORS, LUCKY_DIRECTIONS, LUCK_RANGE_HIGH, LUCK_RANGE_MEDIUM,
    ZODIAC_LUCKY_COLORS, ZODIAC_LUCKY_DIRECTIONS, ZODIAC_FORTUNE_MESSAGES, ZODIAC_NAMES
)

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
            # 캐시 조회 (personal 타입만)
            fortune = db.query(DailyFortune).filter(
                DailyFortune.user_id == user_id,
                DailyFortune.fortune_date == fortune_date,
                DailyFortune.fortune_type.in_(['personal', None])  # 기존 NULL 데이터 호환
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
                fortune_type='personal',
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

    # ========== 띠별 운세 API 관련 메서드 ==========

    @staticmethod
    def _generate_zodiac_seed(zodiac: str, target_date: date) -> int:
        """같은 날 같은 띠는 같은 시드값 생성"""
        seed_string = f"{zodiac}_{target_date.isoformat()}"
        hash_value = hashlib.md5(seed_string.encode()).hexdigest()
        return int(hash_value[:8], 16)

    @staticmethod
    def _generate_zodiac_score(seed: int, category: str) -> int:
        """카테고리별 점수 생성 (40-100 범위)"""
        random.seed(seed + hash(category))
        return random.randint(40, 100)

    @staticmethod
    def _get_zodiac_message(score: int, category: str, seed: int) -> str:
        """점수 범위에 맞는 메시지 선택 (상수에서)"""
        if score >= 80:
            luck_range = 'high'
        elif score >= 60:
            luck_range = 'medium'
        else:
            luck_range = 'low'

        messages = ZODIAC_FORTUNE_MESSAGES.get(category, {}).get(luck_range, [])
        if not messages:
            return "오늘도 행운을 빕니다."

        # 시드 기반 메시지 선택 (일관성 유지)
        random.seed(seed + hash(category) + score)
        return random.choice(messages)

    @staticmethod
    def _convert_zodiac_sign_to_name(zodiac_sign: str) -> str:
        """'용띠' -> '용' 변환"""
        if zodiac_sign and zodiac_sign.endswith('띠'):
            return zodiac_sign[:-1]
        return zodiac_sign

    @staticmethod
    def get_or_create_zodiac_fortune(
        db: Session,
        user_id: str,
        zodiac_sign: str,
        fortune_date: date
    ) -> dict:
        """띠별 오늘의 운세 조회 또는 생성

        Args:
            db: 데이터베이스 세션
            user_id: 사용자 ID
            zodiac_sign: 띠 (예: "용띠")
            fortune_date: 운세 날짜

        Returns:
            ZodiacTodayFortuneResponse 형식의 dict
        """
        import logging
        logger = logging.getLogger(__name__)

        # 시드 생성 (같은 날 같은 띠는 같은 결과)
        seed = FortuneService._generate_zodiac_seed(zodiac_sign, fortune_date)

        try:
            # 캐시 조회 (user_id + fortune_type='zodiac' + fortune_date)
            fortune = db.query(DailyFortune).filter(
                DailyFortune.user_id == user_id,
                DailyFortune.fortune_date == fortune_date,
                DailyFortune.fortune_type == 'zodiac'
            ).first()

            if fortune:
                # 캐시된 데이터 반환
                return FortuneService._build_zodiac_response(fortune, zodiac_sign, fortune_date)
        except Exception as e:
            try:
                db.rollback()
            except:
                pass
            logger.warning(f"Zodiac fortune query failed: {e}")

        # 새로 생성
        scores = {
            'overall': FortuneService._generate_zodiac_score(seed, 'overall'),
            'wealth': FortuneService._generate_zodiac_score(seed, 'wealth'),
            'love': FortuneService._generate_zodiac_score(seed, 'love'),
            'health': FortuneService._generate_zodiac_score(seed, 'health'),
            'work': FortuneService._generate_zodiac_score(seed, 'work'),
        }

        # 행운 요소 생성
        random.seed(seed + hash('color'))
        lucky_color = random.choice(ZODIAC_LUCKY_COLORS)

        random.seed(seed + hash('number'))
        lucky_number = random.randint(1, 45)

        random.seed(seed + hash('direction'))
        lucky_direction = random.choice(ZODIAC_LUCKY_DIRECTIONS)

        # 메시지 생성
        overall_message = FortuneService._get_zodiac_message(scores['overall'], 'overall', seed)
        advice_message = FortuneService._get_zodiac_message(scores['overall'], 'advice', seed)

        # 카테고리별 설명
        wealth_desc = FortuneService._get_zodiac_message(scores['wealth'], 'wealth', seed)
        love_desc = FortuneService._get_zodiac_message(scores['love'], 'love', seed)
        health_desc = FortuneService._get_zodiac_message(scores['health'], 'health', seed)
        work_desc = FortuneService._get_zodiac_message(scores['work'], 'work', seed)

        # 행운의 번호 7개 (기존 필드 호환)
        random.seed(seed + hash('numbers'))
        lucky_numbers = sorted(random.sample(range(1, 46), 7))

        try:
            # DB에 저장
            fortune = DailyFortune(
                user_id=user_id,
                fortune_date=fortune_date,
                fortune_type='zodiac',
                overall_luck=scores['overall'],
                wealth_luck=scores['wealth'],
                lottery_luck=scores['wealth'],  # 기존 필드 호환
                love_luck=scores['love'],
                health_luck=scores['health'],
                work_luck=scores['work'],
                lucky_numbers=lucky_numbers,
                lucky_number=lucky_number,
                lucky_color=lucky_color,
                lucky_direction=lucky_direction,
                fortune_message=overall_message,
                advice=advice_message,
                wealth_description=wealth_desc,
                love_description=love_desc,
                health_description=health_desc,
                work_description=work_desc,
            )

            db.add(fortune)
            db.commit()
            db.refresh(fortune)

            return FortuneService._build_zodiac_response(fortune, zodiac_sign, fortune_date)

        except Exception as e:
            try:
                db.rollback()
            except:
                pass
            logger.warning(f"Zodiac fortune save failed, returning temp data: {e}")

            # DB 저장 실패 시 임시 응답 반환
            zodiac_name = FortuneService._convert_zodiac_sign_to_name(zodiac_sign)
            return {
                "date": fortune_date,
                "zodiac": zodiac_name,
                "overall_score": scores['overall'],
                "message": overall_message,
                "categories": {
                    "wealth": {"score": scores['wealth'], "description": wealth_desc},
                    "love": {"score": scores['love'], "description": love_desc},
                    "health": {"score": scores['health'], "description": health_desc},
                    "work": {"score": scores['work'], "description": work_desc},
                },
                "lucky": {
                    "color": lucky_color,
                    "number": lucky_number,
                    "direction": lucky_direction,
                },
                "advice": advice_message,
            }

    @staticmethod
    def _build_zodiac_response(fortune: DailyFortune, zodiac_sign: str, fortune_date: date) -> dict:
        """DailyFortune 모델을 ZodiacTodayFortuneResponse 형식으로 변환"""
        zodiac_name = FortuneService._convert_zodiac_sign_to_name(zodiac_sign)

        return {
            "date": fortune_date,
            "zodiac": zodiac_name,
            "overall_score": fortune.overall_luck,
            "message": fortune.fortune_message or "오늘도 행운을 빕니다.",
            "categories": {
                "wealth": {
                    "score": fortune.wealth_luck,
                    "description": fortune.wealth_description or "재물운을 확인해보세요."
                },
                "love": {
                    "score": fortune.love_luck or fortune.wealth_luck,
                    "description": fortune.love_description or "연애운을 확인해보세요."
                },
                "health": {
                    "score": fortune.health_luck or fortune.overall_luck,
                    "description": fortune.health_description or "건강운을 확인해보세요."
                },
                "work": {
                    "score": fortune.work_luck or fortune.overall_luck,
                    "description": fortune.work_description or "직장운을 확인해보세요."
                },
            },
            "lucky": {
                "color": fortune.lucky_color or "노란색",
                "number": fortune.lucky_number or 7,
                "direction": fortune.lucky_direction or "동쪽",
            },
            "advice": fortune.advice or "오늘도 좋은 하루 되세요.",
        }