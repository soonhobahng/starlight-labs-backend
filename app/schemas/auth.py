from pydantic import BaseModel, EmailStr, validator, Field
from datetime import datetime, date
from typing import Optional
import uuid
import re


class UserResponse(BaseModel):
    id: str
    provider: str
    nickname: Optional[str] = None
    name: Optional[str] = None  # React Native용 (nickname alias)
    email: Optional[str] = None
    phone: Optional[str] = None
    profile_image_url: Optional[str] = None
    tier: str
    role: str
    credits: int
    is_adult_verified: bool
    status: str
    birth_year: Optional[int] = None
    birth_date: Optional[date] = None
    zodiac_sign: Optional[str] = None  # 띠 (예: "용띠")
    zodiac: Optional[str] = None  # React Native용 (zodiac_sign alias)
    constellation: Optional[str] = None  # 별자리 (예: "사자자리")
    mbti: Optional[str] = None  # MBTI (예: "INTJ")
    fortune_enabled: bool = True
    created_at: datetime
    last_login_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class SendCodeRequest(BaseModel):
    phone: str = Field(..., pattern=r'^01[0-9]{8,9}$', description="휴대폰 번호 (010으로 시작하는 10-11자리)")


class SendCodeResponse(BaseModel):
    success: bool
    message: str


class VerifyAdultRequest(BaseModel):
    phone: str = Field(..., pattern=r'^01[0-9]{8,9}$')
    code: str = Field(..., min_length=6, max_length=6, description="6자리 인증번호")
    birth_year: int = Field(..., ge=1900, le=2010, description="출생년도")
    
    @validator('code')
    def validate_code(cls, v):
        if not v.isdigit():
            raise ValueError('인증번호는 숫자만 입력해주세요')
        return v


class VerifyAdultResponse(BaseModel):
    success: bool
    message: str


# Legacy schemas for backward compatibility
class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TestLoginRequest(BaseModel):
    email: str
    password: str


VALID_MBTI_TYPES = [
    "INTJ", "INTP", "ENTJ", "ENTP",
    "INFJ", "INFP", "ENFJ", "ENFP",
    "ISTJ", "ISFJ", "ESTJ", "ESFJ",
    "ISTP", "ISFP", "ESTP", "ESFP"
]


class UserProfile(BaseModel):
    nickname: Optional[str] = None
    phone: Optional[str] = None
    marketing_agreed: Optional[bool] = None
    birth_year: Optional[int] = Field(None, ge=1900, le=2100, description="출생년도")
    birth_date: Optional[date] = Field(None, description="생년월일 (YYYY-MM-DD)")
    mbti: Optional[str] = Field(None, description="MBTI (예: INTJ)")
    fortune_enabled: Optional[bool] = None

    @validator('phone')
    def validate_phone(cls, v):
        if v and not re.match(r'^01[0-9]{8,9}$', v.replace('-', '').replace(' ', '')):
            raise ValueError('올바른 휴대폰 번호를 입력해주세요')
        return v

    @validator('nickname')
    def validate_nickname(cls, v):
        if v is not None:
            if len(v) < 2 or len(v) > 50:
                raise ValueError('닉네임은 2~50자 사이여야 합니다')
            if not re.match(r'^[가-힣a-zA-Z0-9_\s]+$', v):
                raise ValueError('닉네임은 한글, 영문, 숫자, 밑줄, 공백만 사용 가능합니다')
        return v

    @validator('mbti')
    def validate_mbti(cls, v):
        if v is not None:
            v = v.upper()
            if v not in VALID_MBTI_TYPES:
                raise ValueError(f'올바른 MBTI 유형을 입력해주세요 (예: INTJ, ENFP 등)')
        return v


class ProfileUpdateRequest(BaseModel):
    """사용자 프로필 업데이트 요청"""
    nickname: Optional[str] = Field(None, description="닉네임 (2~50자)")
    profile_image_url: Optional[str] = Field(None, description="프로필 이미지 URL")
    
    @validator('nickname')
    def validate_nickname(cls, v):
        if v is not None:
            if len(v) < 2 or len(v) > 50:
                raise ValueError('닉네임은 2~50자 사이여야 합니다')
            if not re.match(r'^[가-힣a-zA-Z0-9_\s]+$', v):
                raise ValueError('닉네임은 한글, 영문, 숫자, 밑줄, 공백만 사용 가능합니다')
        return v
    
    @validator('profile_image_url')
    def validate_profile_image_url(cls, v):
        if v is not None:
            if len(v) > 1000:
                raise ValueError('이미지 URL이 너무 깁니다 (최대 1000자)')
            # Cloudinary URL 또는 일반 이미지 URL 형식 검증
            if not (
                re.match(r'^https://res\.cloudinary\.com/.+', v, re.IGNORECASE) or
                re.match(r'^https?://.+\.(jpg|jpeg|png|gif|webp)$', v, re.IGNORECASE)
            ):
                raise ValueError('올바른 이미지 URL을 입력해주세요 (Cloudinary URL 또는 jpg, jpeg, png, gif, webp 확장자 URL)')
        return v


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[str] = None


# Legacy password schemas (not used in social login)
class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str




class AccountDeactivateRequest(BaseModel):
    reason: Optional[str] = None


class UserStatsResponse(BaseModel):
    """사용자 통계 응답"""
    total_predictions: int
    total_wins: int
    win_rate: float
    credits_used_total: int
    favorite_strategy: Optional[str] = None
    account_age_days: int
    last_prediction_date: Optional[datetime] = None


class AdminUserResponse(UserResponse):
    """관리자용 사용자 정보 (추가 필드 포함)"""
    provider_id: str
    birth_year: Optional[int] = None
    adult_verify_method: Optional[str] = None
    verified_at: Optional[datetime] = None
    terms_agreed_at: datetime
    privacy_agreed_at: datetime
    marketing_agreed: bool
    updated_at: datetime