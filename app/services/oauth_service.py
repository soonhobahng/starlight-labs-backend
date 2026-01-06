import httpx
from datetime import date
from app.core.config import settings


class OAuthService:
    """소셜 로그인 OAuth 서비스"""
    
    # ========== 카카오 ==========
    @staticmethod
    async def get_kakao_token(code: str) -> dict:
        """카카오 액세스 토큰 발급"""
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://kauth.kakao.com/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.KAKAO_CLIENT_ID,
                    "client_secret": settings.KAKAO_CLIENT_SECRET,
                    "redirect_uri": settings.KAKAO_REDIRECT_URI,
                    "code": code
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            return res.json()
    
    @staticmethod
    async def get_kakao_user(access_token: str) -> dict:
        """카카오 사용자 정보 조회"""
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://kapi.kakao.com/v2/user/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            return res.json()
    
    # ========== 네이버 ==========
    @staticmethod
    async def get_naver_token(code: str, state: str) -> dict:
        """네이버 액세스 토큰 발급"""
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://nid.naver.com/oauth2.0/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.NAVER_CLIENT_ID,
                    "client_secret": settings.NAVER_CLIENT_SECRET,
                    "code": code,
                    "state": state
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            return res.json()
    
    @staticmethod
    async def get_naver_user(access_token: str) -> dict:
        """네이버 사용자 정보 조회"""
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://openapi.naver.com/v1/nid/me",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            return res.json()
    
    # ========== 구글 ==========
    @staticmethod
    async def get_google_token(code: str) -> dict:
        """구글 액세스 토큰 발급"""
        # 테스트 계정용 mock 처리
        if code == "test_auth_code_lottolabs":
            return {
                "access_token": "test_access_token_lottolabs",
                "token_type": "Bearer",
                "expires_in": 3600
            }
        
        async with httpx.AsyncClient() as client:
            res = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "authorization_code",
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "code": code
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            return res.json()
    
    @staticmethod
    async def get_google_user(access_token: str) -> dict:
        """구글 사용자 정보 조회"""
        # 테스트 계정용 mock 처리
        if access_token == "test_access_token_lottolabs":
            return {
                "id": "test_provider_id_lottolabs",
                "email": "test@lottolabs.ai.kr",
                "name": "테스트계정",
                "picture": "https://res.cloudinary.com/dklbvuxtb/image/upload/v1735130894/profile_images/test_account.png",
                "verified_email": True
            }
        
        async with httpx.AsyncClient() as client:
            res = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            return res.json()


class AdultVerificationService:
    """성인 인증 서비스"""
    
    @staticmethod
    def verify_from_naver(user_data: dict) -> dict:
        """네이버 생년월일로 성인 확인"""
        response = user_data.get("response", {})
        birthyear = response.get("birthyear")
        birthday = response.get("birthday")  # "MM-DD"
        
        if not birthyear:
            return {"verified": False, "reason": "생년월일 정보 없음"}
        
        try:
            birth_year = int(birthyear)
            today = date.today()
            age = today.year - birth_year
            
            # 생일 지났는지 확인
            if birthday:
                month, day = map(int, birthday.split("-"))
                if (today.month, today.day) < (month, day):
                    age -= 1
            
            if age >= 19:
                return {
                    "verified": True,
                    "method": "naver_birth",
                    "birth_year": birth_year,
                    "birth_date": f"{birth_year}-{birthday}" if birthday else None
                }
            else:
                return {"verified": False, "reason": "만 19세 미만"}
        except (ValueError, TypeError):
            return {"verified": False, "reason": "생년월일 정보 오류"}
    
    @staticmethod
    def verify_from_kakao(user_data: dict) -> dict:
        """카카오 연령대/생년으로 성인 확인"""
        account = user_data.get("kakao_account", {})
        
        # 1. 생년이 있으면 정확한 계산
        birthyear = account.get("birthyear")
        if birthyear:
            try:
                birth_year = int(birthyear)
                age = date.today().year - birth_year
                if age >= 19:
                    return {
                        "verified": True,
                        "method": "kakao_birth",
                        "birth_year": birth_year
                    }
                else:
                    return {"verified": False, "reason": "만 19세 미만"}
            except (ValueError, TypeError):
                pass
        
        # 2. 연령대로 확인
        age_range = account.get("age_range")
        if age_range:
            minor_ranges = ["1~9", "10~14", "15~19"]
            if age_range not in minor_ranges:
                return {
                    "verified": True,
                    "method": "kakao_age",
                    "age_range": age_range
                }
            else:
                return {"verified": False, "reason": "만 19세 미만"}
        
        return {"verified": False, "reason": "연령 정보 없음"}
    
    @staticmethod
    def verify_from_google(user_data: dict) -> dict:
        """구글은 나이 정보 없음 - 별도 인증 필요"""
        return {
            "verified": False,
            "reason": "추가 인증 필요",
            "require_phone_verification": True
        }
    
    @staticmethod
    def verify_from_phone(birth_year: int) -> dict:
        """휴대폰 인증으로 성인 확인"""
        try:
            age = date.today().year - birth_year
            if age >= 19:
                return {
                    "verified": True,
                    "method": "phone",
                    "birth_year": birth_year
                }
            else:
                return {"verified": False, "reason": "만 19세 미만"}
        except (ValueError, TypeError):
            return {"verified": False, "reason": "생년 정보 오류"}