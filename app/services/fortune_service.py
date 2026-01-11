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
                "lottery": 92,
                "love": 65,
                "career": 72,
                "health": 80
            }
        """
        seed = FortuneService._generate_deterministic_seed(user_id, fortune_date)
        random.seed(seed)

        # 점수 범위: 50-95 (너무 낮거나 높지 않게)
        overall_luck = random.randint(60, 95)
        wealth_luck = random.randint(50, 90)
        lottery_luck = random.randint(55, 100)
        love_luck = random.randint(50, 95)
        career_luck = random.randint(55, 95)
        health_luck = random.randint(60, 95)

        return {
            "overall": overall_luck,
            "wealth": wealth_luck,
            "lottery": lottery_luck,
            "love": love_luck,
            "career": career_luck,
            "health": health_luck
        }
    
    @staticmethod
    def generate_lucky_numbers(user_id: str, fortune_date: date) -> List[int]:
        """개인별 행운의 번호 7개 생성 (1-45, 중복 없음)"""
        seed = FortuneService._generate_deterministic_seed(user_id, fortune_date, "numbers")
        random.seed(seed)
        
        lucky_numbers = sorted(random.sample(range(1, 46), 7))
        return lucky_numbers
    
    # 색상 hex 코드 매핑
    COLOR_HEX_MAP = {
        "빨간색": "#EF4444", "주황색": "#F97316", "노란색": "#EAB308",
        "초록색": "#22C55E", "파란색": "#3B82F6", "남색": "#4F46E5",
        "보라색": "#A855F7", "분홍색": "#EC4899", "흰색": "#FFFFFF",
        "검은색": "#1F2937", "금색": "#F59E0B", "은색": "#9CA3AF"
    }

    # 행운 아이템 목록
    LUCKY_ITEMS = [
        "파란색 소품", "동전 열쇠고리", "사탕", "손수건",
        "작은 거울", "향수", "책", "꽃", "열쇠", "반지",
        "팔찌", "시계", "펜", "노트", "사진"
    ]

    # 행운의 시간대
    LUCKY_TIMES = [
        "오전 6시 ~ 8시", "오전 8시 ~ 10시", "오전 10시 ~ 12시",
        "오후 12시 ~ 2시", "오후 2시 ~ 4시", "오후 4시 ~ 6시",
        "오후 6시 ~ 8시", "오후 8시 ~ 10시"
    ]

    # 경고 메시지
    WARNING_MESSAGES = {
        'high': ["과신은 금물입니다", "기대가 크면 실망도 클 수 있어요", "겸손함을 유지하세요"],
        'medium': ["무리한 욕심은 금물입니다", "급한 결정은 피하세요", "컨디션 관리에 신경쓰세요"],
        'low': ["과로에 주의하세요", "큰 지출을 피하세요", "중요한 결정은 미루세요", "건강 관리에 신경쓰세요"]
    }

    # 카테고리별 메시지
    CATEGORY_MESSAGES = {
        'wealth': {
            'high': ["금전운이 좋습니다! 투자에 좋은 시기예요.", "예상치 못한 수입이 있을 수 있어요.", "재테크에 관심을 가져보세요."],
            'medium': ["안정적인 재물운입니다.", "계획적인 소비가 좋습니다.", "작은 저축이 큰 도움이 됩니다."],
            'low': ["불필요한 지출을 조심하세요.", "큰 투자는 피하는 것이 좋습니다.", "충동구매를 조심하세요."]
        },
        'love': {
            'high': ["로맨틱한 하루가 될 거예요!", "연인과의 관계가 더욱 깊어집니다.", "새로운 인연을 만날 수 있어요."],
            'medium': ["솔직한 대화가 관계를 발전시켜요.", "상대방의 말에 귀 기울여보세요.", "작은 배려가 큰 감동을 줍니다."],
            'low': ["오해가 생길 수 있으니 신중하게 대화하세요.", "감정적인 대응은 피하세요.", "혼자만의 시간도 필요해요."]
        },
        'career': {
            'high': ["업무 성과가 빛나는 날입니다!", "승진이나 좋은 기회가 올 수 있어요.", "창의적인 아이디어가 인정받습니다."],
            'medium': ["동료와의 협력이 좋은 결과를 만들어요.", "팀워크에 집중하세요.", "꾸준한 노력이 결실을 맺습니다."],
            'low': ["업무 실수를 조심하세요.", "중요한 발표나 회의는 신중하게.", "스트레스 관리가 필요해요."]
        },
        'health': {
            'high': ["활력이 넘치는 하루!", "운동을 시작하기 좋은 날입니다.", "에너지가 충만해요."],
            'medium': ["가벼운 운동으로 컨디션을 유지하세요.", "규칙적인 생활이 건강의 비결.", "충분한 수면이 필요합니다."],
            'low': ["무리하지 마세요.", "휴식이 필요한 시기입니다.", "건강 검진을 미루지 마세요."]
        },
        'lottery': {
            'high': ["오늘은 행운이 따르는 날!", "직감을 믿어보세요.", "도전하기 좋은 날입니다."],
            'medium': ["적당한 도전이 좋습니다.", "무리한 베팅은 피하세요.", "작은 행운에 감사하세요."],
            'low': ["신중한 선택이 필요해요.", "오늘은 보수적으로 접근하세요.", "다음 기회를 노려보세요."]
        }
    }

    @staticmethod
    def get_lucky_color(fortune_date: date) -> str:
        """날짜 기반 행운의 색상"""
        seed = int(hashlib.md5(fortune_date.isoformat().encode()).hexdigest(), 16)
        random.seed(seed)
        return random.choice(LUCKY_COLORS)

    @staticmethod
    def get_color_hex(color: str) -> str:
        """색상명을 hex 코드로 변환"""
        return FortuneService.COLOR_HEX_MAP.get(color, "#3B82F6")

    @staticmethod
    def get_lucky_direction(user_id: str, fortune_date: date) -> str:
        """사용자별 행운의 방향"""
        seed = FortuneService._generate_deterministic_seed(user_id, fortune_date, "direction")
        random.seed(seed)
        return random.choice(LUCKY_DIRECTIONS)

    @staticmethod
    def get_lucky_time(user_id: str, fortune_date: date) -> str:
        """사용자별 행운의 시간"""
        seed = FortuneService._generate_deterministic_seed(user_id, fortune_date, "time")
        random.seed(seed)
        return random.choice(FortuneService.LUCKY_TIMES)

    @staticmethod
    def get_lucky_item(user_id: str, fortune_date: date, color: str) -> str:
        """사용자별 행운의 아이템"""
        seed = FortuneService._generate_deterministic_seed(user_id, fortune_date, "item")
        random.seed(seed)
        item = random.choice(FortuneService.LUCKY_ITEMS)
        # 색상이 포함된 아이템이면 그대로, 아니면 색상 붙이기
        if "색" in item:
            return item
        return f"{color} {item}" if random.random() > 0.5 else item

    @staticmethod
    def get_category_message(category: str, score: int, seed: int) -> str:
        """카테고리별 운세 메시지"""
        if score >= 80:
            luck_range = 'high'
        elif score >= 60:
            luck_range = 'medium'
        else:
            luck_range = 'low'

        messages = FortuneService.CATEGORY_MESSAGES.get(category, {}).get(luck_range, [])
        if not messages:
            return "오늘도 좋은 하루 되세요."

        random.seed(seed + hash(category))
        return random.choice(messages)

    @staticmethod
    def get_warning_message(overall_score: int, seed: int) -> str:
        """점수에 따른 경고 메시지"""
        if overall_score >= 80:
            luck_range = 'high'
        elif overall_score >= 60:
            luck_range = 'medium'
        else:
            luck_range = 'low'

        messages = FortuneService.WARNING_MESSAGES.get(luck_range, [])
        random.seed(seed + hash('warning'))
        return random.choice(messages) if messages else "컨디션 관리에 신경쓰세요"

    @staticmethod
    def get_summary_message(scores: dict) -> str:
        """전체 요약 메시지 생성"""
        overall = scores.get('overall', 70)
        parts = []

        if overall >= 80:
            parts.append("오늘은 전반적으로 행운이 가득한 하루입니다.")
        elif overall >= 60:
            parts.append("오늘은 전반적으로 안정적인 하루입니다.")
        else:
            parts.append("오늘은 조금 신중하게 행동하는 것이 좋겠습니다.")

        # 가장 높은 점수 카테고리
        category_scores = {k: v for k, v in scores.items() if k != 'overall'}
        if category_scores:
            best = max(category_scores, key=category_scores.get)
            worst = min(category_scores, key=category_scores.get)

            category_names = {'wealth': '재물운', 'lottery': '행운운', 'love': '애정운', 'career': '직장운', 'health': '건강운'}
            if category_scores[best] >= 80:
                parts.append(f"{category_names.get(best, best)}이 특히 좋으니 적극적으로 활용해보세요.")
            if category_scores[worst] < 60:
                parts.append(f"{category_names.get(worst, worst)}은 다소 약하니 주의하세요.")

        return " ".join(parts)

    @staticmethod
    def get_time_fortunes(user_id: str, fortune_date: date, overall_score: int) -> dict:
        """시간대별 운세"""
        seed = FortuneService._generate_deterministic_seed(user_id, fortune_date, "time_fortune")
        random.seed(seed)

        # 기본 점수에서 시간대별 변동
        base = overall_score
        morning_score = max(40, min(100, base + random.randint(-15, 15)))
        afternoon_score = max(40, min(100, base + random.randint(-15, 15)))
        evening_score = max(40, min(100, base + random.randint(-15, 15)))

        morning_msgs = ["차분하게 하루를 시작하세요", "아침 운동이 도움이 됩니다", "중요한 결정은 오전에"]
        afternoon_msgs = ["가장 좋은 시간대! 중요한 일은 이 시간에", "점심 후 집중력이 올라갑니다", "오후 미팅이 좋은 결과를 가져옵니다"]
        evening_msgs = ["편안한 휴식이 필요한 시간", "저녁 산책이 좋습니다", "가까운 사람과 시간을 보내세요"]

        return {
            "morning": {
                "period": "오전 6시 ~ 12시",
                "score": morning_score,
                "message": random.choice(morning_msgs)
            },
            "afternoon": {
                "period": "오후 12시 ~ 6시",
                "score": afternoon_score,
                "message": random.choice(afternoon_msgs)
            },
            "evening": {
                "period": "오후 6시 ~ 12시",
                "score": evening_score,
                "message": random.choice(evening_msgs)
            }
        }

    @staticmethod
    def get_best_zodiac_and_match(fortune_date: date, my_zodiac: str) -> tuple:
        """오늘의 최고 띠와 최고 궁합"""
        seed = int(hashlib.md5(fortune_date.isoformat().encode()).hexdigest(), 16)
        random.seed(seed)

        zodiacs = ["쥐띠", "소띠", "호랑이띠", "토끼띠", "용띠", "뱀띠",
                   "말띠", "양띠", "원숭이띠", "닭띠", "개띠", "돼지띠"]

        # 오늘의 최고 띠 (랜덤)
        best_zodiac = random.choice(zodiacs)

        # 궁합 띠 (내 띠와 다른 띠 중에서 선택)
        compatible = [z for z in zodiacs if z != my_zodiac]
        best_match = random.choice(compatible) if compatible else zodiacs[0]

        return best_zodiac, best_match
    
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