from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime
import secrets
import uuid
import logging

from app.core.database import get_db
from app.core.security import create_access_token, get_current_user
from app.core.config import settings
from app.models.models import User
from app.services.oauth_service import OAuthService, AdultVerificationService
from app.services.sms_service import SMSService
from app.services.upload_service import UploadService
from app.schemas.auth import (
    UserResponse, LoginResponse, UserProfile, ProfileUpdateRequest,
    SendCodeRequest, SendCodeResponse,
    VerifyAdultRequest, VerifyAdultResponse,
    AccountDeactivateRequest, TestLoginRequest
)

router = APIRouter(prefix="/auth", tags=["인증"])

# Logger 설정
logger = logging.getLogger(__name__)


# ========== 테스트 계정 처리 함수 ==========

async def _handle_test_account(db: Session, email: str) -> User:
    """테스트 계정 생성/조회 공통 함수"""
    test_provider_id = "test_account_lottolabs"
    user = db.query(User).filter(
        User.provider == "google",
        User.provider_id == test_provider_id
    ).first()
    
    if not user:
        logger.info(f"테스트 계정 생성 - Email: {email}")
        user = User(
            provider="google",
            provider_id=test_provider_id,
            nickname="테스트계정",
            email=email,
            profile_image_url="https://res.cloudinary.com/dklbvuxtb/image/upload/v1735130894/profile_images/test_account.png",
            is_adult_verified=True,
            adult_verify_method="test_account",
            verified_at=datetime.utcnow(),
            terms_agreed_at=datetime.utcnow(),
            privacy_agreed_at=datetime.utcnow(),
            role="user",
            tier="free",
            credits=100
        )
        user.last_login_at = datetime.utcnow()
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info(f"테스트 계정 생성 완료 - User ID: {user.id}")
    else:
        logger.info(f"기존 테스트 계정 로그인 - User ID: {user.id}")
        user.last_login_at = datetime.utcnow()
        db.commit()
    
    return user


# ========== OAuth 로그인 URL ==========

@router.get("/kakao/login")
async def kakao_login():
    """카카오 로그인 페이지로 리다이렉트"""
    url = (
        f"https://kauth.kakao.com/oauth/authorize"
        f"?client_id={settings.KAKAO_CLIENT_ID}"
        f"&redirect_uri={settings.KAKAO_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=profile_nickname,profile_image,account_email"
    )
    return RedirectResponse(url)


@router.get("/naver/login")
async def naver_login():
    """네이버 로그인 페이지로 리다이렉트"""
    state = secrets.token_urlsafe(16)
    url = (
        f"https://nid.naver.com/oauth2.0/authorize"
        f"?client_id={settings.NAVER_CLIENT_ID}"
        f"&redirect_uri={settings.NAVER_REDIRECT_URI}"
        f"&response_type=code"
        f"&state={state}"
    )
    return RedirectResponse(url)


@router.get("/google/login")
async def google_login():
    """구글 로그인 페이지로 리다이렉트"""
    logger.info("========== 구글 로그인 요청 시작 ==========")
    logger.info(f"GOOGLE_CLIENT_ID: {settings.GOOGLE_CLIENT_ID[:20]}..." if settings.GOOGLE_CLIENT_ID else "GOOGLE_CLIENT_ID: None")
    logger.info(f"GOOGLE_REDIRECT_URI: {settings.GOOGLE_REDIRECT_URI}")

    url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=email profile"
    )
    logger.info(f"구글 OAuth URL 생성 완료: {url}")
    logger.info("========== 구글 로그인 리다이렉트 ==========")
    return RedirectResponse(url)


@router.post("/test/login")
async def test_login(request: TestLoginRequest, db: Session = Depends(get_db)):
    """테스트 계정 로그인"""
    try:
        email = request.email
        password = request.password
        
        # 테스트 계정 검증
        if email != "test@lottolabs.ai.kr" or password != "lottolabs4%6&":
            raise HTTPException(
                status_code=401, 
                detail="테스트 계정 정보가 올바르지 않습니다"
            )
        
        # 테스트 계정 조회/생성
        user = await _handle_test_account(db, email)
        
        # JWT 발급
        token = create_access_token(data={"sub": str(user.id)})
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "email": user.email,
                "nickname": user.nickname,
                "role": user.role
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"테스트 로그인 처리 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"테스트 로그인 처리 중 오류: {str(e)}")


# ========== OAuth 콜백 ==========

@router.get("/kakao/callback")
async def kakao_callback(code: str, db: Session = Depends(get_db)):
    """카카오 로그인 콜백"""
    try:
        # 1. 토큰 발급
        token_data = await OAuthService.get_kakao_token(code)
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="카카오 로그인 실패")
        
        # 2. 사용자 정보
        user_data = await OAuthService.get_kakao_user(access_token)
        provider_id = str(user_data["id"])
        account = user_data.get("kakao_account", {})
        profile = account.get("profile", {})
        
        logger.info(f"카카오 로그인 시도 - Provider ID: {provider_id}")
        logger.info(f"카카오 사용자 데이터: {account}")
        
        # 3. 사용자 조회/생성
        user = db.query(User).filter(
            User.provider == "kakao",
            User.provider_id == provider_id
        ).first()
        
        if not user:
            # 신규 사용자 - 이메일, 닉네임, 프로필 사진만 설정
            user = User(
                provider="kakao",
                provider_id=provider_id,
                nickname=profile.get("nickname"),
                email=account.get("email"),
                profile_image_url=profile.get("profile_image_url"),
                is_adult_verified=True,
                adult_verify_method="social_login",
                verified_at=datetime.utcnow(),
                terms_agreed_at=datetime.utcnow(),
                privacy_agreed_at=datetime.utcnow()
            )
            user.last_login_at = datetime.utcnow()  # 로그인 시간 설정
            db.add(user)  # 데이터베이스에 사용자 추가
            db.commit()   # 커밋해서 ID 생성
            db.refresh(user)  # 객체 새로고침으로 ID 확보
            logger.info(f"신규 카카오 사용자 생성 완료 - User ID: {user.id}")
        else:
            # 기존 사용자 - 이메일과 닉네임만 업데이트 (프로필 이미지는 유지)
            logger.info(f"기존 카카오 사용자 로그인 - User ID: {user.id}")
            if account.get("email"):
                user.email = account.get("email")
            # if profile.get("nickname"):
            #     user.nickname = profile.get("nickname")

            user.last_login_at = datetime.utcnow()
            db.commit()
        
        # User ID 확인
        if user.id is None:
            logger.error("사용자 ID가 None입니다. 데이터베이스 저장 실패")
            raise HTTPException(status_code=500, detail="사용자 정보 저장 실패")
        
        logger.info(f"카카오 로그인 처리 완료 - User ID: {user.id}")
        
        # 4. JWT 발급
        token = create_access_token(data={"sub": str(user.id)})
        # 프론트엔드로 리다이렉트 (토큰 전달)
        return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?token={token}")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"카카오 로그인 처리 중 오류: {str(e)}")


@router.get("/naver/callback")
async def naver_callback(code: str, state: str, db: Session = Depends(get_db)):
    """네이버 로그인 콜백"""
    try:
        # 1. 토큰 발급
        token_data = await OAuthService.get_naver_token(code, state)
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="네이버 로그인 실패")
        
        # 2. 사용자 정보
        user_data = await OAuthService.get_naver_user(access_token)
        response = user_data.get("response", {})
        provider_id = response.get("id")
        
        logger.info(f"네이버 로그인 시도 - Provider ID: {provider_id}")
        logger.info(f"네이버 사용자 데이터: {response}")
        
        # 3. 사용자 조회/생성
        user = db.query(User).filter(
            User.provider == "naver",
            User.provider_id == provider_id
        ).first()
        
        if not user:
            # 신규 사용자 - 이메일, 닉네임, 프로필 사진만 설정
            logger.info(f"신규 네이버 사용자 생성 - Provider ID: {provider_id}")
            user = User(
                provider="naver",
                provider_id=provider_id,
                nickname=response.get("nickname") or response.get("name"),
                email=response.get("email"),
                profile_image_url=response.get("profile_image"),
                is_adult_verified=True,
                adult_verify_method="social_login",
                verified_at=datetime.utcnow(),
                terms_agreed_at=datetime.utcnow(),
                privacy_agreed_at=datetime.utcnow()
            )
            user.last_login_at = datetime.utcnow()  # 로그인 시간 설정
            db.add(user)  # 데이터베이스에 사용자 추가
            db.commit()   # 커밋해서 ID 생성
            db.refresh(user)  # 객체 새로고침으로 ID 확보
            logger.info(f"신규 사용자 생성 완료 - User ID: {user.id}")
        else:
            # 기존 사용자 - 이메일과 닉네임만 업데이트 (프로필 이미지는 유지)
            logger.info(f"기존 네이버 사용자 로그인 - User ID: {user.id}")
            if response.get("email"):
                user.email = response.get("email")
            # if response.get("nickname") or response.get("name"):
            #     user.nickname = response.get("nickname") or response.get("name")
            
            user.last_login_at = datetime.utcnow()
            db.commit()
        
        # User ID 확인
        if user.id is None:
            logger.error("사용자 ID가 None입니다. 데이터베이스 저장 실패")
            raise HTTPException(status_code=500, detail="사용자 정보 저장 실패")
        
        logger.info(f"네이버 로그인 처리 완료 - User ID: {user.id}")
        
        # 5. JWT 발급
        token = create_access_token(data={"sub": str(user.id)})
        return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?token={token}")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"네이버 로그인 처리 중 오류: {str(e)}")


@router.get("/google/callback")
async def google_callback(code: str = None, error: str = None, db: Session = Depends(get_db)):
    """구글 로그인 콜백"""
    try:
        # OAuth error 처리
        if error:
            logger.error(f"구글 OAuth 오류: {error}")
            return RedirectResponse(f"{settings.FRONTEND_URL}/auth/error?error=oauth_error&message={error}")
        
        # code 파라미터 검증
        if not code:
            logger.error("구글 OAuth callback에서 code 파라미터 누락")
            return RedirectResponse(f"{settings.FRONTEND_URL}/auth/error?error=missing_code&message=인증코드가 누락되었습니다")
        
        # 1. 토큰 발급
        token_data = await OAuthService.get_google_token(code)
        access_token = token_data.get("access_token")
        
        if not access_token:
            raise HTTPException(status_code=400, detail="구글 로그인 실패")
        
        # 2. 사용자 정보
        user_data = await OAuthService.get_google_user(access_token)
        provider_id = user_data.get("id")
        email = user_data.get("email")
        
        logger.info(f"구글 로그인 시도 - Provider ID: {provider_id}")
        logger.info(f"구글 사용자 데이터: {user_data}")
        
        # 3. 테스트 계정 처리  
        if email == "test@lottolabs.ai.kr":
            user = await _handle_test_account(db, email)
            token = create_access_token(data={"sub": str(user.id)})
            return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?token={token}")
        
        # 4. 일반 사용자 처리
        user = db.query(User).filter(
            User.provider == "google",
            User.provider_id == provider_id
        ).first()
        
        if not user:
            # 신규 사용자 - 이메일, 닉네임, 프로필 사진만 설정
            logger.info(f"신규 구글 사용자 생성 - Provider ID: {provider_id}")
            user = User(
                provider="google",
                provider_id=provider_id,
                nickname=user_data.get("name"),
                email=user_data.get("email"),
                profile_image_url=user_data.get("picture"),
                is_adult_verified=True,
                adult_verify_method="social_login",
                verified_at=datetime.utcnow(),
                terms_agreed_at=datetime.utcnow(),
                privacy_agreed_at=datetime.utcnow()
            )
            user.last_login_at = datetime.utcnow()  # 로그인 시간 설정
            db.add(user)  # 데이터베이스에 사용자 추가
            db.commit()   # 커밋해서 ID 생성
            db.refresh(user)  # 객체 새로고침으로 ID 확보
            logger.info(f"신규 구글 사용자 생성 완료 - User ID: {user.id}")
        else:
            # 기존 사용자 - 이메일과 닉네임만 업데이트 (프로필 이미지는 유지)
            logger.info(f"기존 구글 사용자 로그인 - User ID: {user.id}")
            if user_data.get("email"):
                user.email = user_data.get("email")
            # if user_data.get("name"):
            #     user.nickname = user_data.get("name")
            
            user.last_login_at = datetime.utcnow()
            db.commit()
        
        # User ID 확인
        if user.id is None:
            logger.error("사용자 ID가 None입니다. 데이터베이스 저장 실패")
            raise HTTPException(status_code=500, detail="사용자 정보 저장 실패")
        
        logger.info(f"구글 로그인 처리 완료 - User ID: {user.id}")
        
        # 5. JWT 발급
        token = create_access_token(data={"sub": str(user.id)})
        return RedirectResponse(f"{settings.FRONTEND_URL}/auth/callback?token={token}")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"구글 로그인 처리 중 오류: {str(e)}")


# ========== 추가 성인 인증 (구글 사용자용) ==========

@router.post("/verify-adult/send-code", response_model=SendCodeResponse)
async def send_verification_code(
    request: SendCodeRequest,
    current_user: User = Depends(get_current_user)
):
    """휴대폰 인증번호 발송"""
    if current_user.is_adult_verified:
        raise HTTPException(status_code=400, detail="이미 성인 인증이 완료되었습니다")
    
    if current_user.provider != "google":
        raise HTTPException(status_code=400, detail="구글 로그인 사용자만 휴대폰 인증을 사용할 수 있습니다")
    
    try:
        result = SMSService.send_code(request.phone)
        return SendCodeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"인증번호 발송 실패: {str(e)}")


@router.post("/verify-adult/confirm", response_model=VerifyAdultResponse)
async def confirm_adult_verification(
    request: VerifyAdultRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """휴대폰 인증 확인 및 성인 인증 완료"""
    if current_user.is_adult_verified:
        raise HTTPException(status_code=400, detail="이미 성인 인증이 완료되었습니다")
    
    if current_user.provider != "google":
        raise HTTPException(status_code=400, detail="구글 로그인 사용자만 휴대폰 인증을 사용할 수 있습니다")
    
    try:
        # 인증번호 확인
        if not SMSService.verify_code(request.phone, request.code):
            raise HTTPException(status_code=400, detail="인증번호가 올바르지 않습니다")
        
        # 나이 확인
        adult_result = AdultVerificationService.verify_from_phone(request.birth_year)
        if not adult_result["verified"]:
            raise HTTPException(status_code=403, detail=adult_result["reason"])
        
        # 인증 완료
        current_user.phone = SMSService.normalize_phone(request.phone)
        current_user.birth_year = request.birth_year
        current_user.is_adult_verified = True
        current_user.adult_verify_method = "phone"
        current_user.verified_at = datetime.utcnow()
        db.commit()
        
        return VerifyAdultResponse(success=True, message="성인 인증이 완료되었습니다")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"성인 인증 처리 중 오류: {str(e)}")


# ========== 사용자 정보 관리 ==========

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """현재 로그인한 사용자 정보"""
    return UserResponse(
        id=str(current_user.id),
        provider=current_user.provider,
        nickname=current_user.nickname,
        email=current_user.email,
        phone=current_user.phone,
        profile_image_url=current_user.profile_image_url,
        tier=current_user.tier,
        role=current_user.role,
        credits=current_user.credits,
        is_adult_verified=current_user.is_adult_verified,
        status=current_user.status,
        birth_year=current_user.birth_year,
        birth_date=current_user.birth_date,
        zodiac_sign=current_user.zodiac_sign,
        fortune_enabled=current_user.fortune_enabled,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at
    )


@router.put("/me", response_model=UserResponse)
async def update_my_profile(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    # Form data parameters (for multipart/form-data)
    file: UploadFile = File(None),
    nickname: str = Form(None),
    profile_image_url: str = Form(None),
    birth_date: str = Form(None)
):
    """사용자 프로필 업데이트 - JSON과 multipart/form-data 모두 지원"""
    try:
        updated = False
        content_type = request.headers.get("content-type", "")
        
        # Content-Type에 따른 데이터 처리
        if "multipart/form-data" in content_type:
            # Form 데이터 사용
            nickname_to_update = nickname
            profile_image_url_to_update = profile_image_url
            birth_date_to_update = birth_date
        elif "application/json" in content_type:
            # JSON 데이터 파싱
            try:
                import json
                body = await request.body()
                if body:
                    json_data = json.loads(body)
                    nickname_to_update = json_data.get("nickname")
                    profile_image_url_to_update = json_data.get("profile_image_url")
                    birth_date_to_update = json_data.get("birth_date")
                else:
                    nickname_to_update = None
                    profile_image_url_to_update = None
                    birth_date_to_update = None
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise HTTPException(
                    status_code=400,
                    detail="잘못된 JSON 형식입니다"
                )
        else:
            raise HTTPException(
                status_code=400,
                detail="지원하지 않는 Content-Type입니다. application/json 또는 multipart/form-data를 사용해주세요."
            )
        
        # 닉네임 업데이트
        if nickname_to_update is not None and nickname_to_update.strip():
            # 닉네임 길이 검증
            if len(nickname_to_update) < 2 or len(nickname_to_update) > 50:
                raise HTTPException(
                    status_code=400,
                    detail="닉네임은 2~50자 사이여야 합니다"
                )
            
            # 닉네임 형식 검증
            import re
            if not re.match(r'^[가-힣a-zA-Z0-9_\s]+$', nickname_to_update):
                raise HTTPException(
                    status_code=400,
                    detail="닉네임은 한글, 영문, 숫자, 밑줄, 공백만 사용 가능합니다"
                )
            
            # 닉네임 중복 확인
            existing_user = db.query(User).filter(
                User.nickname == nickname_to_update,
                User.id != current_user.id
            ).first()
            if existing_user:
                raise HTTPException(
                    status_code=400,
                    detail="이미 사용 중인 닉네임입니다"
                )
            
            current_user.nickname = nickname_to_update
            updated = True
        
        # 프로필 이미지 처리
        if file is not None and file.filename:
            # 파일 업로드를 통한 이미지 업데이트 (Cloudinary)
            try:
                cloudinary_url = await UploadService.upload_profile_image(file, current_user.id)
                current_user.profile_image_url = cloudinary_url
                updated = True
                logger.info(f"프로필 이미지 업로드 완료: User {current_user.id}, URL: {cloudinary_url}")
            except Exception as e:
                logger.error(f"프로필 이미지 업로드 실패: User {current_user.id}, Error: {str(e)}")
                raise
                
        elif profile_image_url_to_update is not None:
            # URL을 통한 이미지 업데이트
            if len(profile_image_url_to_update) > 1000:
                raise HTTPException(
                    status_code=400,
                    detail="이미지 URL이 너무 깁니다 (최대 1000자)"
                )
            
            # Cloudinary URL 또는 일반 이미지 URL 형식 검증
            import re
            if profile_image_url_to_update and not (
                re.match(r'^https://res\.cloudinary\.com/.+', profile_image_url_to_update, re.IGNORECASE) or
                re.match(r'^https?://.+\.(jpg|jpeg|png|gif|webp)$', profile_image_url_to_update, re.IGNORECASE)
            ):
                raise HTTPException(
                    status_code=400,
                    detail="올바른 이미지 URL을 입력해주세요 (Cloudinary URL 또는 jpg, jpeg, png, gif, webp 확장자 URL)"
                )
            
            current_user.profile_image_url = profile_image_url_to_update
            updated = True
        
        # 생년월일 처리 (yyyy-mm-dd 형태)
        if birth_date_to_update is not None and birth_date_to_update.strip():
            try:
                from datetime import datetime
                from app.services.zodiac_service import ZodiacService
                
                # yyyy-mm-dd 형태를 파싱
                birth_date_obj = datetime.strptime(birth_date_to_update.strip(), "%Y-%m-%d").date()
                birth_year = birth_date_obj.year
                
                # 생년 범위 검증
                if not (1900 <= birth_year <= 2100):
                    raise HTTPException(
                        status_code=400,
                        detail="생년월일은 1900년~2100년 사이여야 합니다"
                    )
                
                # 사용자 정보 업데이트
                current_user.birth_date = birth_date_obj
                current_user.birth_year = birth_year
                current_user.zodiac_sign = ZodiacService.calculate_zodiac_sign(birth_year)
                updated = True
                
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="생년월일 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요 (예: 2000-01-15)"
                )
        
        if not updated:
            raise HTTPException(
                status_code=400,
                detail="수정할 정보를 입력해주세요"
            )
        
        db.commit()
        db.refresh(current_user)
        
        return UserResponse(
            id=str(current_user.id),
            provider=current_user.provider,
            nickname=current_user.nickname,
            email=current_user.email,
            phone=current_user.phone,
            profile_image_url=current_user.profile_image_url,
            tier=current_user.tier,
            role=current_user.role,
            credits=current_user.credits,
            is_adult_verified=current_user.is_adult_verified,
            status=current_user.status,
            birth_year=current_user.birth_year,
            zodiac_sign=current_user.zodiac_sign,
            fortune_enabled=current_user.fortune_enabled,
            created_at=current_user.created_at,
            last_login_at=current_user.last_login_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"프로필 업데이트 중 오류: {str(e)}"
        )


# ========== 새로운 프로필 관리 API ==========

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    current_user: User = Depends(get_current_user)
):
    """사용자 프로필 조회 (React Native용)"""
    return UserResponse(
        id=str(current_user.id),
        provider=current_user.provider,
        nickname=current_user.nickname,
        name=current_user.nickname,  # React Native에서 name 필드 사용
        email=current_user.email,
        phone=current_user.phone,
        profile_image_url=current_user.profile_image_url,
        tier=current_user.tier,
        role=current_user.role,
        credits=current_user.credits,
        is_adult_verified=current_user.is_adult_verified,
        status=current_user.status,
        birth_year=current_user.birth_year,
        birth_date=current_user.birth_date,
        zodiac_sign=current_user.zodiac_sign,
        zodiac=current_user.zodiac_sign,  # React Native에서 zodiac 필드 사용
        mbti=None,  # MBTI 정보는 별도 API로 관리
        fortune_enabled=current_user.fortune_enabled,
        created_at=current_user.created_at,
        last_login_at=current_user.last_login_at
    )


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    profile_data: UserProfile,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """사용자 프로필 업데이트"""
    try:
        if profile_data.nickname is not None:
            # 닉네임 중복 확인
            existing_user = db.query(User).filter(
                User.nickname == profile_data.nickname,
                User.id != current_user.id
            ).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="이미 사용 중인 닉네임입니다"
                )
            current_user.nickname = profile_data.nickname
        
        if profile_data.phone is not None:
            normalized_phone = SMSService.normalize_phone(profile_data.phone)
            current_user.phone = normalized_phone
        
        if profile_data.marketing_agreed is not None:
            current_user.marketing_agreed = profile_data.marketing_agreed
        
        if profile_data.birth_year is not None:
            from app.services.zodiac_service import ZodiacService
            current_user.birth_year = profile_data.birth_year
            current_user.zodiac_sign = ZodiacService.calculate_zodiac_sign(profile_data.birth_year)
        
        if profile_data.fortune_enabled is not None:
            current_user.fortune_enabled = profile_data.fortune_enabled
        
        db.commit()
        db.refresh(current_user)
        
        return UserResponse(
            id=str(current_user.id),
            provider=current_user.provider,
            nickname=current_user.nickname,
            email=current_user.email,
            phone=current_user.phone,
            profile_image_url=current_user.profile_image_url,
            tier=current_user.tier,
            role=current_user.role,
            credits=current_user.credits,
            is_adult_verified=current_user.is_adult_verified,
            status=current_user.status,
            birth_year=current_user.birth_year,
            zodiac_sign=current_user.zodiac_sign,
            fortune_enabled=current_user.fortune_enabled,
            created_at=current_user.created_at,
            last_login_at=current_user.last_login_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"프로필 업데이트 중 오류: {str(e)}")


@router.post("/account/deactivate")
async def deactivate_account(
    deactivate_data: AccountDeactivateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """계정 비활성화"""
    try:
        current_user.status = 'withdrawn'
        db.commit()
        
        # TODO: 탈퇴 사유 로깅 등 추가 처리
        if deactivate_data.reason:
            logger.info(f"계정 탈퇴 사유 - User ID: {current_user.id}, Reason: {deactivate_data.reason}")
        
        return {"message": "계정이 비활성화되었습니다"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"계정 비활성화 처리 중 오류: {str(e)}")




# ========== 성인 인증 확인 미들웨어용 엔드포인트 ==========

@router.get("/check-adult-verification")
async def check_adult_verification(
    current_user: User = Depends(get_current_user)
):
    """성인 인증 상태 확인"""
    return {
        "is_adult_verified": current_user.is_adult_verified,
        "provider": current_user.provider,
        "require_phone_verification": current_user.provider == "google" and not current_user.is_adult_verified
    }