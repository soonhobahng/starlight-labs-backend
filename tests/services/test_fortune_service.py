# tests/services/test_fortune_service.py

import pytest
from datetime import date
from app.services.fortune_service import FortuneService

def test_fortune_scores_consistency():
    """같은 날짜는 같은 운세 점수 반환"""
    user_id = "test_user_123"
    test_date = date(2025, 12, 16)
    
    scores1 = FortuneService.calculate_fortune_scores(user_id, test_date)
    scores2 = FortuneService.calculate_fortune_scores(user_id, test_date)
    
    assert scores1 == scores2
    assert scores1["overall"] >= 60 and scores1["overall"] <= 95
    assert scores1["wealth"] >= 50 and scores1["wealth"] <= 90
    assert scores1["lottery"] >= 55 and scores1["lottery"] <= 100


def test_lucky_numbers_count():
    """행운 번호는 항상 7개"""
    user_id = "test_user_123"
    test_date = date(2025, 12, 16)
    
    numbers = FortuneService.generate_lucky_numbers(user_id, test_date)
    
    assert len(numbers) == 7
    assert len(set(numbers)) == 7  # 중복 없음
    assert all(1 <= n <= 45 for n in numbers)
    assert numbers == sorted(numbers)  # 정렬되어 있음


def test_lucky_numbers_consistency():
    """같은 사용자/날짜는 같은 행운 번호"""
    user_id = "test_user_123"
    test_date = date(2025, 12, 16)
    
    numbers1 = FortuneService.generate_lucky_numbers(user_id, test_date)
    numbers2 = FortuneService.generate_lucky_numbers(user_id, test_date)
    
    assert numbers1 == numbers2


def test_different_users_different_fortunes():
    """다른 사용자는 다른 운세"""
    test_date = date(2025, 12, 16)
    
    scores_user1 = FortuneService.calculate_fortune_scores("user1", test_date)
    scores_user2 = FortuneService.calculate_fortune_scores("user2", test_date)
    
    # 확률적으로 다를 가능성이 매우 높음
    assert scores_user1 != scores_user2


def test_different_dates_different_fortunes():
    """다른 날짜는 다른 운세"""
    user_id = "test_user_123"
    date1 = date(2025, 12, 16)
    date2 = date(2025, 12, 17)
    
    scores1 = FortuneService.calculate_fortune_scores(user_id, date1)
    scores2 = FortuneService.calculate_fortune_scores(user_id, date2)
    
    # 확률적으로 다를 가능성이 매우 높음
    assert scores1 != scores2


def test_lucky_color_consistency():
    """같은 날짜는 같은 행운 색상"""
    test_date = date(2025, 12, 16)
    
    color1 = FortuneService.get_lucky_color(test_date)
    color2 = FortuneService.get_lucky_color(test_date)
    
    assert color1 == color2
    from app.core.constants import LUCKY_COLORS
    assert color1 in LUCKY_COLORS


def test_lucky_direction_consistency():
    """같은 사용자/날짜는 같은 행운 방향"""
    user_id = "test_user_123"
    test_date = date(2025, 12, 16)
    
    direction1 = FortuneService.get_lucky_direction(user_id, test_date)
    direction2 = FortuneService.get_lucky_direction(user_id, test_date)
    
    assert direction1 == direction2
    from app.core.constants import LUCKY_DIRECTIONS
    assert direction1 in LUCKY_DIRECTIONS


def test_deterministic_seed_generation():
    """시드 생성이 일관성있게 동작"""
    user_id = "test_user_123"
    test_date = date(2025, 12, 16)
    
    seed1 = FortuneService._generate_deterministic_seed(user_id, test_date)
    seed2 = FortuneService._generate_deterministic_seed(user_id, test_date)
    
    assert seed1 == seed2
    assert isinstance(seed1, int)
    
    # 다른 사용자는 다른 시드
    seed3 = FortuneService._generate_deterministic_seed("other_user", test_date)
    assert seed1 != seed3


def test_fortune_score_ranges():
    """운세 점수가 올바른 범위 내에 있음"""
    user_id = "test_user_123"
    test_date = date(2025, 12, 16)
    
    # 여러 사용자로 테스트
    for i in range(10):
        scores = FortuneService.calculate_fortune_scores(f"user_{i}", test_date)
        
        assert 60 <= scores["overall"] <= 95
        assert 50 <= scores["wealth"] <= 90
        assert 55 <= scores["lottery"] <= 100