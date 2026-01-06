# tests/services/test_zodiac_service.py

import pytest
from app.services.zodiac_service import ZodiacService

def test_zodiac_calculation():
    """12띠 계산 정확성"""
    assert ZodiacService.calculate_zodiac_sign(1984) == "쥐띠"
    assert ZodiacService.calculate_zodiac_sign(2000) == "용띠"
    assert ZodiacService.calculate_zodiac_sign(2024) == "용띠"
    assert ZodiacService.calculate_zodiac_sign(1985) == "소띠"
    assert ZodiacService.calculate_zodiac_sign(1986) == "호랑이띠"


def test_zodiac_cycle():
    """12년 주기 확인"""
    zodiac_1984 = ZodiacService.calculate_zodiac_sign(1984)
    zodiac_1996 = ZodiacService.calculate_zodiac_sign(1996)  # 1984 + 12
    zodiac_2008 = ZodiacService.calculate_zodiac_sign(2008)  # 1996 + 12
    zodiac_2020 = ZodiacService.calculate_zodiac_sign(2020)  # 2008 + 12
    
    assert zodiac_1984 == zodiac_1996 == zodiac_2008 == zodiac_2020 == "쥐띠"


def test_zodiac_full_cycle():
    """전체 12띠 사이클 확인"""
    expected_zodiacs = [
        "쥐띠", "소띠", "호랑이띠", "토끼띠", "용띠", "뱀띠",
        "말띠", "양띠", "원숭이띠", "닭띠", "개띠", "돼지띠"
    ]
    
    for i, expected in enumerate(expected_zodiacs):
        year = 1984 + i
        actual = ZodiacService.calculate_zodiac_sign(year)
        assert actual == expected, f"Year {year}: expected {expected}, got {actual}"


def test_zodiac_invalid_years():
    """잘못된 연도에 대한 예외 처리"""
    with pytest.raises(ValueError):
        ZodiacService.calculate_zodiac_sign(1899)  # 너무 이른 연도
    
    with pytest.raises(ValueError):
        ZodiacService.calculate_zodiac_sign(2101)  # 너무 늦은 연도


def test_get_all_zodiacs():
    """모든 12띠 목록 반환"""
    all_zodiacs = ZodiacService.get_all_zodiacs()
    
    expected = [
        "쥐띠", "소띠", "호랑이띠", "토끼띠", "용띠", "뱀띠",
        "말띠", "양띠", "원숭이띠", "닭띠", "개띠", "돼지띠"
    ]
    
    assert len(all_zodiacs) == 12
    assert all_zodiacs == expected
    
    # 리턴된 리스트가 원본과 독립적인지 확인 (복사본인지)
    all_zodiacs[0] = "modified"
    fresh_list = ZodiacService.get_all_zodiacs()
    assert fresh_list[0] == "쥐띠"  # 원본이 변경되지 않았어야 함


def test_zodiac_edge_cases():
    """경계값 테스트"""
    assert ZodiacService.calculate_zodiac_sign(1900) == "쥐띠"
    assert ZodiacService.calculate_zodiac_sign(2100) == "용띠"
    
    # 2000년대 주요 연도들
    assert ZodiacService.calculate_zodiac_sign(2000) == "용띠"
    assert ZodiacService.calculate_zodiac_sign(2012) == "용띠"  # 2000 + 12
    assert ZodiacService.calculate_zodiac_sign(1988) == "용띠"  # 2000 - 12


def test_zodiac_recent_years():
    """최근 연도들 테스트"""
    test_cases = {
        2020: "쥐띠",
        2021: "소띠", 
        2022: "호랑이띠",
        2023: "토끼띠",
        2024: "용띠",
        2025: "뱀띠",
    }
    
    for year, expected in test_cases.items():
        actual = ZodiacService.calculate_zodiac_sign(year)
        assert actual == expected, f"Year {year}: expected {expected}, got {actual}"