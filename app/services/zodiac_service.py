# app/services/zodiac_service.py

from app.core.constants import ZODIAC_ANIMALS, ZODIAC_BASE_YEAR

class ZodiacService:
    """12띠 관련 유틸리티"""
    
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
    def get_all_zodiacs() -> list[str]:
        """모든 12띠 목록 반환"""
        return ZODIAC_ANIMALS.copy()