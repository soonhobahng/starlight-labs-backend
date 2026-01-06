from pydantic import BaseModel, Field
from datetime import date
from typing import List, Optional


class LastDrawInfo(BaseModel):
    """최신 추첨 정보"""
    draw_number: int = Field(..., description="회차 번호")
    draw_date: str = Field(..., description="추첨 날짜 (YYYY-MM-DD)")
    numbers: List[int] = Field(..., description="당첨 번호 6개 (오름차순)")
    bonus: int = Field(..., description="보너스 번호")


class PrizeInfo(BaseModel):
    """등급별 당첨 정보"""
    rank: int = Field(..., description="등수 (1~5)")
    prize_amount: int = Field(..., description="당첨금 (원)")
    winners: int = Field(..., description="당첨자 수")


class MemberWinner(BaseModel):
    """회원 당첨자 정보"""
    user_nickname: str = Field(..., description="사용자 닉네임")
    numbers: List[int] = Field(..., description="예측한 번호 6개")
    matched_count: int = Field(..., description="일치한 번호 개수")
    rank: int = Field(..., description="당첨 등수")
    prize_amount: int = Field(..., description="당첨금 (원)")
    draw_number: int = Field(..., description="당첨된 회차 번호")


class WinningInfoResponse(BaseModel):
    """당첨 정보 응답"""
    last_draw: LastDrawInfo = Field(..., description="최신 추첨 정보")
    prizes: List[PrizeInfo] = Field(..., description="등급별 당첨 정보")
    member_winners: List[MemberWinner] = Field(..., description="회원 당첨자 정보")
    
    class Config:
        json_schema_extra = {
            "example": {
                "last_draw": {
                    "draw_number": 1145,
                    "draw_date": "2024-01-06",
                    "numbers": [7, 14, 23, 28, 35, 42],
                    "bonus": 16
                },
                "prizes": [
                    {
                        "rank": 1,
                        "prize_amount": 2500000000,
                        "winners": 5
                    },
                    {
                        "rank": 2,
                        "prize_amount": 62000000,
                        "winners": 23
                    }
                ],
                "member_winners": [
                    {
                        "user_nickname": "행운이",
                        "numbers": [7, 14, 23, 28, 35, 42],
                        "matched_count": 5,
                        "rank": 3,
                        "prize_amount": 1500000,
                        "draw_number": 1145
                    }
                ]
            }
        }