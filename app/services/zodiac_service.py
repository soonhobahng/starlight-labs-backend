# app/services/zodiac_service.py

from datetime import date
from app.core.constants import ZODIAC_ANIMALS, ZODIAC_BASE_YEAR

# 별자리 정보 (월, 일 범위)
CONSTELLATIONS = [
    ("염소자리", (1, 1), (1, 19)),
    ("물병자리", (1, 20), (2, 18)),
    ("물고기자리", (2, 19), (3, 20)),
    ("양자리", (3, 21), (4, 19)),
    ("황소자리", (4, 20), (5, 20)),
    ("쌍둥이자리", (5, 21), (6, 20)),
    ("게자리", (6, 21), (7, 22)),
    ("사자자리", (7, 23), (8, 22)),
    ("처녀자리", (8, 23), (9, 22)),
    ("천칭자리", (9, 23), (10, 22)),
    ("전갈자리", (10, 23), (11, 21)),
    ("사수자리", (11, 22), (12, 21)),
    ("염소자리", (12, 22), (12, 31)),  # 12월 염소자리
]

CONSTELLATION_LIST = [
    "양자리", "황소자리", "쌍둥이자리", "게자리",
    "사자자리", "처녀자리", "천칭자리", "전갈자리",
    "사수자리", "염소자리", "물병자리", "물고기자리"
]


class ZodiacService:
    """12띠 및 별자리 관련 유틸리티"""

    @staticmethod
    def calculate_zodiac_sign(birth_year: int) -> str:
        """출생년도로 12띠 계산

        Args:
            birth_year: 출생년도 (예: 2000)

        Returns:
            12띠 문자열 (예: "용띠")
        """
        if not (1900 <= birth_year <= 2100):
            raise ValueError(f"Invalid birth year: {birth_year}")

        # 1984년 = 쥐띠 (인덱스 0)
        index = (birth_year - ZODIAC_BASE_YEAR) % 12
        return ZODIAC_ANIMALS[index]

    @staticmethod
    def calculate_constellation(birth_date: date) -> str:
        """생년월일로 별자리 계산

        Args:
            birth_date: 생년월일 (date 객체)

        Returns:
            별자리 문자열 (예: "사자자리")
        """
        month = birth_date.month
        day = birth_date.day

        for constellation, (start_month, start_day), (end_month, end_day) in CONSTELLATIONS:
            if start_month == end_month:
                # 같은 달 내 범위
                if month == start_month and start_day <= day <= end_day:
                    return constellation
            else:
                # 다른 달에 걸친 범위 (12월 -> 1월 염소자리 처리)
                if month == start_month and day >= start_day:
                    return constellation
                if month == end_month and day <= end_day:
                    return constellation

        return "알 수 없음"

    @staticmethod
    def get_all_zodiacs() -> list[str]:
        """모든 12띠 목록 반환"""
        return ZODIAC_ANIMALS.copy()

    @staticmethod
    def get_all_constellations() -> list[str]:
        """모든 12별자리 목록 반환"""
        return CONSTELLATION_LIST.copy()