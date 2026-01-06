from pydantic_settings import BaseSettings
from typing import List, Optional
import os
import logging


def _get_env_file() -> str:
    """환경에 따라 적절한 .env 파일을 반환"""
    environment = os.getenv("ENVIRONMENT", "development")
    
    if environment == "production":
        return ".env.production"
    elif environment == "development":
        return ".env.development"
    else:
        # 기본값으로 .env 파일 사용 (기존 방식)
        return ".env"


class Settings(BaseSettings):
    # Application
    app_name: str = "LottoChat AI"
    api_prefix: str = "/api/v1"
    debug: bool = False
    
    # Database
    database_url: str
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # Security
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24 hours
    
    # OAuth - Kakao
    kakao_client_id: str
    kakao_client_secret: str
    kakao_redirect_uri: str = "http://localhost:8000/api/v1/auth/kakao/callback"
    
    # OAuth - Naver
    naver_client_id: str
    naver_client_secret: str
    naver_redirect_uri: str = "http://localhost:8000/api/v1/auth/naver/callback"
    
    # OAuth - Google
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    
    # Frontend
    frontend_url: str = "http://localhost:3000"
    
    # CORS
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"
    
    # Anthropic
    anthropic_api_key: str = ""
    
    # SMS (for production)
    sms_api_key: Optional[str] = None
    sms_api_secret: Optional[str] = None
    sms_sender_number: Optional[str] = None
    
    # Cloudinary
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""
    
    # Toss Payments
    toss_client_key: str = ""
    toss_secret_key: str = ""
    toss_webhook_secret: str = ""
    
    # Payple Payments
    payple_cst_id: str = ""
    payple_cust_key: str = ""
    payple_auth_key: str = ""
    
    def __init__(self, **kwargs):
        # 환경변수에 따라 동적으로 env_file 설정
        environment = os.getenv("ENVIRONMENT", "development")
        
        if environment == "production":
            env_file = ".env.production"
        elif environment == "development":
            env_file = ".env.development"
        else:
            env_file = ".env"
        
        logger = logging.getLogger(__name__)
        logger.info(f"🔧 Loading environment: {environment}")
        logger.info(f"📁 Using config file: {env_file}")
        
        super().__init__(_env_file=env_file, **kwargs)

    class Config:
        case_sensitive = False


    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    # Uppercase property getters for compatibility
    @property
    def KAKAO_CLIENT_ID(self) -> str:
        return self.kakao_client_id
    
    @property
    def KAKAO_CLIENT_SECRET(self) -> str:
        return self.kakao_client_secret
    
    @property
    def KAKAO_REDIRECT_URI(self) -> str:
        return self.kakao_redirect_uri
    
    @property
    def NAVER_CLIENT_ID(self) -> str:
        return self.naver_client_id
    
    @property
    def NAVER_CLIENT_SECRET(self) -> str:
        return self.naver_client_secret
    
    @property
    def NAVER_REDIRECT_URI(self) -> str:
        return self.naver_redirect_uri
    
    @property
    def GOOGLE_CLIENT_ID(self) -> str:
        return self.google_client_id
    
    @property
    def GOOGLE_CLIENT_SECRET(self) -> str:
        return self.google_client_secret
    
    @property
    def GOOGLE_REDIRECT_URI(self) -> str:
        return self.google_redirect_uri
    
    @property
    def FRONTEND_URL(self) -> str:
        return self.frontend_url
    
    @property
    def REDIS_URL(self) -> str:
        return self.redis_url
    
    @property
    def DEBUG(self) -> bool:
        return self.debug
    
    @property
    def CLOUDINARY_CLOUD_NAME(self) -> str:
        return self.cloudinary_cloud_name
    
    @property
    def CLOUDINARY_API_KEY(self) -> str:
        return self.cloudinary_api_key
    
    @property
    def CLOUDINARY_API_SECRET(self) -> str:
        return self.cloudinary_api_secret


settings = Settings()

# Cloudinary 초기화 (설정값이 있을 때만)
import cloudinary
if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True
    )