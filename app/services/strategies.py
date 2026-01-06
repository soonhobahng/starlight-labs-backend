import random
from collections import Counter
from typing import List, Dict, Any, Tuple
import numpy as np
from datetime import datetime, timedelta, date


class PredictionStrategies:
    @staticmethod
    def frequency_balance(recent_draws: List[List[int]], num_sets: int = 5) -> List[List[int]]:
        """
        Hot 번호 3개 + Cold 번호 3개 조합
        
        Args:
            recent_draws: [[1,2,3,4,5,6], [7,8,9,10,11,12], ...] 형태의 최근 당첨번호
            num_sets: 생성할 조합 개수
        
        Returns:
            [[1,2,3,4,5,6], ...] 형태의 예측 번호 리스트
        """
        if not recent_draws:
            return PredictionStrategies.random_strategy(num_sets)
            
        all_numbers = [num for draw in recent_draws for num in draw]
        frequency = Counter(all_numbers)
        
        # 모든 번호에 대한 빈도 계산 (0으로 나오지 않은 번호도 포함)
        full_frequency = {i: frequency.get(i, 0) for i in range(1, 46)}
        sorted_by_freq = sorted(full_frequency.items(), key=lambda x: x[1], reverse=True)
        
        hot_numbers = [num for num, _ in sorted_by_freq[:14]]
        cold_numbers = [num for num, _ in sorted_by_freq[-14:]]
        
        predictions = []
        for _ in range(num_sets):
            hot_pick = random.sample(hot_numbers, 3)
            cold_pick = random.sample(cold_numbers, 3)
            predictions.append(sorted(hot_pick + cold_pick))
        
        return predictions
    
    @staticmethod
    def random_strategy(num_sets: int = 5) -> List[List[int]]:
        """완전 무작위 6개 번호"""
        return [sorted(random.sample(range(1, 46), 6)) for _ in range(num_sets)]
    
    @staticmethod
    def zone_distribution(num_sets: int = 5) -> List[List[int]]:
        """5개 구간(1-9, 10-18, 19-27, 28-36, 37-45)에서 균등 선택"""
        zones = [
            list(range(1, 10)),   # 1-9
            list(range(10, 19)),  # 10-18
            list(range(19, 28)),  # 19-27
            list(range(28, 37)),  # 28-36
            list(range(37, 46))   # 37-45
        ]
        
        predictions = []
        for _ in range(num_sets):
            numbers = [random.choice(zone) for zone in zones]
            remaining = [n for n in range(1, 46) if n not in numbers]
            if remaining:
                numbers.append(random.choice(remaining))
            else:
                # 중복이 발생한 경우 다시 선택
                numbers = random.sample(range(1, 46), 6)
            predictions.append(sorted(numbers[:6]))
        
        return predictions
    
    @staticmethod
    def pattern_similarity(recent_draws: List[List[int]], num_sets: int = 5) -> List[List[int]]:
        """최근 20회차 홀짝 비율 반영"""
        if not recent_draws:
            return PredictionStrategies.random_strategy(num_sets)
        
        recent_20 = recent_draws[:min(20, len(recent_draws))]
        odd_counts = [sum(1 for num in draw if num % 2 == 1) for draw in recent_20]
        avg_odd = int(np.mean(odd_counts)) if odd_counts else 3
        avg_odd = max(0, min(6, avg_odd))  # 0-6 범위로 제한
        
        predictions = []
        for _ in range(num_sets):
            odds = [n for n in range(1, 46, 2)]
            evens = [n for n in range(2, 46, 2)]
            
            actual_odd_count = min(avg_odd + random.randint(-1, 1), 6)
            actual_odd_count = max(0, actual_odd_count)
            actual_even_count = 6 - actual_odd_count
            
            odd_pick = random.sample(odds, min(actual_odd_count, len(odds)))
            even_pick = random.sample(evens, min(actual_even_count, len(evens)))
            
            prediction = odd_pick + even_pick
            if len(prediction) < 6:
                remaining = [n for n in range(1, 46) if n not in prediction]
                prediction.extend(random.sample(remaining, 6 - len(prediction)))
            
            predictions.append(sorted(prediction[:6]))
        
        return predictions
    
    @staticmethod
    def machine_learning(recent_draws: List[List[int]], num_sets: int = 5) -> List[List[int]]:
        """
        간단한 ML 기반 예측 (빈도 + 패턴 가중치)
        실제로는 RandomForest 등 사용 가능
        """
        if len(recent_draws) < 10:
            return PredictionStrategies.frequency_balance(recent_draws, num_sets)
        
        # 빈도 분석 (최근 30회차)
        recent_data = recent_draws[:min(30, len(recent_draws))]
        all_numbers = [num for draw in recent_data for num in draw]
        freq = Counter(all_numbers)
        
        # 가중치 계산 (빈도가 높을수록 높은 가중치)
        weights = []
        for i in range(1, 46):
            weights.append(freq.get(i, 0) + 1)  # +1 smoothing
        
        weights = np.array(weights)
        weights = weights / weights.sum()
        
        predictions = []
        for _ in range(num_sets):
            numbers = []
            available_indices = list(range(45))  # 0-44 (번호 1-45에 대응)
            available_weights = weights.copy()
            
            for _ in range(6):
                if available_weights.sum() == 0:
                    break
                available_weights_norm = available_weights / available_weights.sum()
                idx = np.random.choice(len(available_indices), p=available_weights_norm)
                numbers.append(available_indices[idx] + 1)  # 1-45로 변환
                
                # 선택된 인덱스 제거
                available_weights = np.delete(available_weights, idx)
                available_indices.pop(idx)
            
            if len(numbers) < 6:
                remaining = [n for n in range(1, 46) if n not in numbers]
                numbers.extend(random.sample(remaining, 6 - len(numbers)))
            
            predictions.append(sorted(numbers[:6]))
        
        return predictions
    
    @staticmethod
    def consecutive_absence(recent_draws: List[List[int]], num_sets: int = 5) -> List[List[int]]:
        """오래 안 나온 번호 중심 선택"""
        if not recent_draws:
            return PredictionStrategies.random_strategy(num_sets)
        
        # 최근 출현 위치 계산
        last_appearance = {}
        for round_idx, draw in enumerate(recent_draws):
            for num in draw:
                if num not in last_appearance:
                    last_appearance[num] = round_idx
        
        # 미출현 횟수 계산 (최근일수록 작은 값)
        absence_count = {}
        for num in range(1, 46):
            absence_count[num] = last_appearance.get(num, len(recent_draws))
        
        # 오래 안 나온 순 정렬
        sorted_absence = sorted(absence_count.items(), key=lambda x: x[1], reverse=True)
        candidates = [num for num, _ in sorted_absence[:20]]
        
        predictions = []
        for _ in range(num_sets):
            if len(candidates) >= 6:
                prediction = random.sample(candidates, 6)
            else:
                remaining = [n for n in range(1, 46) if n not in candidates]
                prediction = candidates + random.sample(remaining, 6 - len(candidates))
            predictions.append(sorted(prediction))
        
        return predictions
    
    @staticmethod
    def winner_pattern(recent_draws: List[List[int]], num_sets: int = 5) -> List[List[int]]:
        """당첨 번호 합계/범위 패턴 분석"""
        if len(recent_draws) < 5:
            return PredictionStrategies.frequency_balance(recent_draws, num_sets)
        
        # 최근 당첨번호들의 패턴 분석
        recent_data = recent_draws[:min(20, len(recent_draws))]
        sums = [sum(draw) for draw in recent_data]
        avg_sum = np.mean(sums)
        std_sum = np.std(sums)
        
        # 저구간/고구간 분석
        patterns = []
        for draw in recent_data:
            low_count = sum(1 for num in draw if num <= 22)
            high_count = 6 - low_count
            patterns.append({'sum': sum(draw), 'low': low_count, 'high': high_count})
        
        avg_low = np.mean([p['low'] for p in patterns])
        
        predictions = []
        for _ in range(num_sets):
            attempts = 0
            while attempts < 100:
                # 저구간/고구간 비율 맞추기
                target_low = max(1, min(5, int(avg_low + random.randint(-1, 1))))
                target_high = 6 - target_low
                
                low_nums = random.sample(range(1, 23), target_low)
                high_nums = random.sample(range(23, 46), target_high)
                numbers = sorted(low_nums + high_nums)
                
                # 합계 범위 체크
                if avg_sum - std_sum <= sum(numbers) <= avg_sum + std_sum:
                    predictions.append(numbers)
                    break
                attempts += 1
            else:
                # 실패시 기본 생성
                predictions.append(sorted(random.sample(range(1, 46), 6)))
        
        return predictions
    
    @staticmethod
    def golden_ratio(num_sets: int = 5) -> List[List[int]]:
        """피보나치 수열 기반"""
        fibonacci = [1, 2, 3, 5, 8, 13, 21, 34]
        valid_fibonacci = [f for f in fibonacci if f <= 45]
        
        # 황금비 적용 (1.618)
        golden_nums = []
        for f in valid_fibonacci:
            golden = int(f * 1.618)
            if 1 <= golden <= 45:
                golden_nums.append(golden)
        
        predictions = []
        for _ in range(num_sets):
            numbers = []
            
            # 피보나치 수에서 2-3개 선택
            if valid_fibonacci:
                fib_count = min(3, len(valid_fibonacci))
                fib_pick = random.sample(valid_fibonacci, fib_count)
                numbers.extend(fib_pick)
            
            # 황금비 수에서 1-2개 선택
            available_golden = [g for g in golden_nums if g not in numbers]
            if available_golden:
                golden_count = min(2, len(available_golden))
                golden_pick = random.sample(available_golden, golden_count)
                numbers.extend(golden_pick)
            
            # 나머지 번호로 6개 채우기
            remaining = [n for n in range(1, 46) if n not in numbers]
            if remaining:
                needed = 6 - len(numbers)
                numbers.extend(random.sample(remaining, min(needed, len(remaining))))
            
            # 6개가 안 되면 랜덤으로 채우기
            while len(numbers) < 6:
                num = random.randint(1, 45)
                if num not in numbers:
                    numbers.append(num)
            
            predictions.append(sorted(numbers[:6]))
        
        return predictions
    
    @staticmethod
    def sum_range(num_sets: int = 5, target_min: int = 100, target_max: int = 150) -> List[List[int]]:
        """합계가 100-150 범위인 조합"""
        predictions = []
        
        for _ in range(num_sets):
            attempts = 0
            while attempts < 1000:
                numbers = sorted(random.sample(range(1, 46), 6))
                if target_min <= sum(numbers) <= target_max:
                    predictions.append(numbers)
                    break
                attempts += 1
            else:
                # 실패시 강제로 범위에 맞추기
                # 평균값 근처에서 시작
                target_avg = (target_min + target_max) // 2
                base = target_avg // 6
                numbers = []
                remaining_sum = target_avg
                
                for i in range(5):
                    num = random.randint(max(1, base - 5), min(45, base + 5))
                    while num in numbers:
                        num = random.randint(1, 45)
                    numbers.append(num)
                    remaining_sum -= num
                
                # 마지막 숫자 계산
                last_num = max(1, min(45, remaining_sum))
                while last_num in numbers:
                    last_num = random.randint(1, 45)
                numbers.append(last_num)
                
                predictions.append(sorted(numbers))
        
        return predictions
    
    @staticmethod
    def ai_custom(recent_draws: List[List[int]], num_sets: int = 5) -> List[List[int]]:
        """VIP 전용 AI 커스텀 전략 - 복합 분석"""
        if len(recent_draws) < 20:
            return PredictionStrategies.machine_learning(recent_draws, num_sets)
        
        # 시간 가중 빈도 분석
        all_numbers = []
        recent_30 = recent_draws[:min(30, len(recent_draws))]
        
        for i, draw in enumerate(recent_30):
            weight = (len(recent_30) - i) / len(recent_30)  # 최근일수록 높은 가중치
            for num in draw:
                all_numbers.extend([num] * int(weight * 10 + 1))
        
        frequency = Counter(all_numbers)
        top_candidates = [num for num, _ in frequency.most_common(20)]
        
        # 패턴 분석
        patterns = {
            'consecutive': self._analyze_consecutive_patterns(recent_30),
            'sum_patterns': self._analyze_sum_patterns(recent_30),
            'odd_even': self._analyze_odd_even_patterns(recent_30)
        }
        
        predictions = []
        for _ in range(num_sets):
            # 고빈도 번호에서 4개 선택
            base_nums = random.sample(top_candidates, 4)
            
            # 패턴 기반으로 나머지 2개 선택
            remaining = [n for n in range(1, 46) if n not in base_nums]
            
            # 연속 번호 패턴 고려
            pattern_nums = []
            for num in base_nums:
                for offset in [-1, 1]:
                    candidate = num + offset
                    if 1 <= candidate <= 45 and candidate in remaining:
                        pattern_nums.append(candidate)
            
            if pattern_nums:
                surprise_nums = random.sample(pattern_nums, min(1, len(pattern_nums)))
            else:
                surprise_nums = []
            
            # 나머지 번호 랜덤 선택
            remaining = [n for n in remaining if n not in surprise_nums]
            if remaining and len(surprise_nums) < 2:
                surprise_nums.extend(random.sample(remaining, 2 - len(surprise_nums)))
            
            prediction = base_nums + surprise_nums
            predictions.append(sorted(prediction[:6]))
        
        return predictions
    
    @staticmethod
    def fortune_based(user_id: str, db_session, num_sets: int = 1) -> List[List[int]]:
        """
        운세 기반 전략 - 사용자의 오늘 행운 번호를 사용
        
        Args:
            user_id: 사용자 ID
            db_session: DB 세션 (DailyFortune 조회용)
            num_sets: 생성할 조합 개수 (보통 1개)
        
        Returns:
            [[1,2,3,4,5,6]] 형태의 예측 번호 리스트 (7개 행운 번호에서 6개 선택)
        """
        from app.models.fortune import DailyFortune
        
        try:
            # 오늘 날짜의 사용자 운세 조회
            today = date.today()
            fortune = db_session.query(DailyFortune).filter(
                DailyFortune.user_id == user_id,
                DailyFortune.fortune_date == today
            ).first()
            
            if fortune and fortune.lucky_numbers and len(fortune.lucky_numbers) >= 6:
                # 행운 번호 7개에서 6개 선택 (가장 좋은 6개)
                lucky_numbers = sorted(fortune.lucky_numbers)
                predictions = []
                
                for _ in range(num_sets):
                    # 7개 중에서 6개를 선택하는 다양한 조합
                    if len(lucky_numbers) == 7:
                        # 7개 중 하나씩 제외하여 다양한 조합 생성
                        exclude_idx = random.randint(0, 6)
                        selected = [num for i, num in enumerate(lucky_numbers) if i != exclude_idx]
                    else:
                        # 6개 이상이면 처음 6개 선택
                        selected = lucky_numbers[:6]
                    
                    predictions.append(sorted(selected))
                
                return predictions
            
        except Exception as e:
            # DB 에러나 운세 정보가 없는 경우 fallback
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Fortune-based strategy failed for user {user_id}: {e}")
        
        # Fallback: 운세 정보가 없으면 오늘의 운세를 기반으로 한 의사 행운 번호 생성
        try:
            from app.services.fortune_service import FortuneService
            
            # 임시로 행운 번호 생성 (DB에 저장하지 않음)
            lucky_numbers = FortuneService.generate_lucky_numbers(user_id, today)
            predictions = []
            
            for _ in range(num_sets):
                # 7개 중에서 6개 선택
                if len(lucky_numbers) >= 6:
                    if len(lucky_numbers) == 7:
                        exclude_idx = random.randint(0, 6)
                        selected = [num for i, num in enumerate(lucky_numbers) if i != exclude_idx]
                    else:
                        selected = lucky_numbers[:6]
                else:
                    # 6개 미만이면 나머지를 랜덤으로 채움
                    remaining = [n for n in range(1, 46) if n not in lucky_numbers]
                    selected = lucky_numbers + random.sample(remaining, 6 - len(lucky_numbers))
                
                predictions.append(sorted(selected))
            
            return predictions
            
        except Exception as e:
            # 최후의 수단: 완전 랜덤
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Fortune-based strategy completely failed for user {user_id}: {e}")
            return PredictionStrategies.random_strategy(num_sets)
    
    @staticmethod
    def _analyze_consecutive_patterns(draws: List[List[int]]) -> Dict[str, Any]:
        """연속 번호 패턴 분석"""
        consecutive_counts = []
        for draw in draws:
            count = 0
            for i in range(len(draw) - 1):
                if draw[i + 1] - draw[i] == 1:
                    count += 1
            consecutive_counts.append(count)
        
        return {
            'avg_consecutive': np.mean(consecutive_counts),
            'max_consecutive': max(consecutive_counts),
            'min_consecutive': min(consecutive_counts)
        }
    
    @staticmethod
    def _analyze_sum_patterns(draws: List[List[int]]) -> Dict[str, Any]:
        """합계 패턴 분석"""
        sums = [sum(draw) for draw in draws]
        return {
            'avg_sum': np.mean(sums),
            'std_sum': np.std(sums),
            'min_sum': min(sums),
            'max_sum': max(sums)
        }
    
    @staticmethod
    def _analyze_odd_even_patterns(draws: List[List[int]]) -> Dict[str, Any]:
        """홀짝 패턴 분석"""
        odd_counts = [sum(1 for num in draw if num % 2 == 1) for draw in draws]
        return {
            'avg_odd': np.mean(odd_counts),
            'most_common_odd': max(set(odd_counts), key=odd_counts.count)
        }


# 전략 매핑
STRATEGY_MAP = {
    "frequency_balance": PredictionStrategies.frequency_balance,
    "random": PredictionStrategies.random_strategy,
    "zone_distribution": PredictionStrategies.zone_distribution,
    "pattern_similarity": PredictionStrategies.pattern_similarity,
    "machine_learning": PredictionStrategies.machine_learning,
    "consecutive_absence": PredictionStrategies.consecutive_absence,
    "winner_pattern": PredictionStrategies.winner_pattern,
    "golden_ratio": PredictionStrategies.golden_ratio,
    "sum_range": PredictionStrategies.sum_range,
    "ai_custom": PredictionStrategies.ai_custom,
    "fortune_based": PredictionStrategies.fortune_based,
}

# 전략 정보
STRATEGY_INFO = {
    "frequency_balance": {
        "name": "빈도 균형",
        "display_name": "Hot/Cold 번호 조합",
        "description": "자주 나온 번호 3개와 적게 나온 번호 3개를 조합",
        "cost": 1,
        "category": "statistical",
        "confidence_base": 0.70
    },
    "random": {
        "name": "랜덤 생성",
        "display_name": "완전 무작위",
        "description": "1-45 중에서 완전 무작위로 6개 번호 선택",
        "cost": 1,
        "category": "random",
        "confidence_base": 0.50
    },
    "zone_distribution": {
        "name": "구간 분산",
        "display_name": "5구간 균등 분산",
        "description": "1-45를 5개 구간으로 나누어 각 구간에서 균등 선택",
        "cost": 1,
        "category": "statistical",
        "confidence_base": 0.60
    },
    "pattern_similarity": {
        "name": "패턴 유사도",
        "display_name": "홀짝 패턴 분석",
        "description": "최근 당첨번호의 홀짝 비율을 분석하여 유사한 패턴 생성",
        "cost": 1,
        "category": "pattern",
        "confidence_base": 0.65
    },
    "machine_learning": {
        "name": "머신러닝",
        "display_name": "AI 빈도 분석",
        "description": "과거 데이터 기반 가중치를 적용한 확률적 선택",
        "cost": 2,
        "category": "ml",
        "confidence_base": 0.75
    },
    "consecutive_absence": {
        "name": "미출현 분석",
        "display_name": "오랜 미출현 번호",
        "description": "최근 오랫동안 나오지 않은 번호들을 중심으로 선택",
        "cost": 1,
        "category": "statistical",
        "confidence_base": 0.62
    },
    "winner_pattern": {
        "name": "당첨 패턴",
        "display_name": "당첨자 패턴 분석",
        "description": "과거 당첨번호의 합계와 분포 패턴을 분석하여 생성",
        "cost": 1,
        "category": "pattern",
        "confidence_base": 0.68
    },
    "golden_ratio": {
        "name": "황금 비율",
        "display_name": "피보나치/황금비",
        "description": "피보나치 수열과 황금비를 활용한 수학적 접근",
        "cost": 1,
        "category": "mathematical",
        "confidence_base": 0.58
    },
    "sum_range": {
        "name": "합계 범위",
        "display_name": "최적 합계 범위",
        "description": "통계적으로 가장 많이 나오는 합계 범위(100-150) 내에서 생성",
        "cost": 1,
        "category": "statistical",
        "confidence_base": 0.64
    },
    "ai_custom": {
        "name": "AI 맞춤",
        "display_name": "VIP AI 커스텀",
        "description": "다중 패턴 분석과 시간 가중치를 적용한 고급 AI 분석",
        "cost": 0,
        "category": "ai",
        "vip_only": True,
        "confidence_base": 0.85
    },
    "fortune_based": {
        "name": "운세 기반",
        "display_name": "오늘의 행운 번호",
        "description": "개인별 12띠 운세를 기반으로 한 행운의 번호 조합",
        "cost": 1,
        "category": "fortune",
        "confidence_base": 0.72
    },
}


def get_strategy_confidence(strategy_name: str, recent_draws: List[List[int]]) -> float:
    """전략별 신뢰도 점수 계산"""
    if strategy_name not in STRATEGY_INFO:
        return 0.50
    
    base_confidence = STRATEGY_INFO[strategy_name]["confidence_base"]
    
    # 데이터 양에 따른 조정
    if recent_draws:
        data_factor = min(len(recent_draws) / 50, 1.0) * 0.1
        base_confidence += data_factor
    
    # 랜덤 변동
    variation = random.uniform(-0.05, 0.05)
    final_confidence = max(0.1, min(0.95, base_confidence + variation))
    
    return round(final_confidence, 3)


def get_all_strategies() -> Dict[str, Dict[str, Any]]:
    """모든 전략 정보 반환"""
    return STRATEGY_INFO


def get_available_strategies(user_tier: str = "free", has_fortune: bool = False) -> Dict[str, Dict[str, Any]]:
    """사용자에게 사용 가능한 전략 목록 반환"""
    available_strategies = {}
    
    for strategy_name, strategy_info in STRATEGY_INFO.items():
        # VIP 전략 필터링
        if strategy_info.get("vip_only", False) and user_tier != "vip":
            continue
            
        # 운세 기반 전략 필터링
        if strategy_name == "fortune_based" and not has_fortune:
            continue
            
        available_strategies[strategy_name] = strategy_info
    
    return available_strategies


def validate_strategy(strategy_name: str, user_tier: str = "free") -> Tuple[bool, str]:
    """전략 사용 가능 여부 검증"""
    if strategy_name not in STRATEGY_MAP:
        return False, "Invalid strategy"
    
    strategy_info = STRATEGY_INFO[strategy_name]
    
    if strategy_info.get("vip_only", False) and user_tier != "vip":
        return False, "VIP subscription required"
    
    return True, "OK"


def calculate_strategy_cost(strategy_name: str, count: int = 1) -> int:
    """전략 사용 비용 계산"""
    if strategy_name not in STRATEGY_INFO:
        return 1
    
    base_cost = STRATEGY_INFO[strategy_name]["cost"]
    return base_cost * count


def get_strategy_by_category(category: str) -> List[str]:
    """카테고리별 전략 리스트 반환"""
    return [
        name for name, info in STRATEGY_INFO.items()
        if info["category"] == category
    ]