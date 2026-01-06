from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.routers import auth, predictions, lotto, credits, admin, fortune, payments
from app.services.scheduler import startup_event, shutdown_event
import logging
import sys
import os
from pathlib import Path

# 로깅 설정
def setup_logging():
    # 환경변수에서 로그 레벨 가져오기, 기본값은 INFO
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    
    # Railway 환경에서는 DEBUG로 일시적 설정
    if os.getenv("RAILWAY_ENVIRONMENT"):
        log_level = "DEBUG"
    
    # 로그 포맷 설정
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # Railway에서는 stdout으로만 로그를 출력해야 함
    # 기존 핸들러들 제거
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    # 커스텀 핸들러로 즉시 flush 보장
    class FlushingStreamHandler(logging.StreamHandler):
        def emit(self, record):
            super().emit(record)
            self.flush()
    
    # 버퍼링 없는 스트림 핸들러 생성
    handler = FlushingStreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, log_level))
    handler.setFormatter(logging.Formatter(log_format))
    
    # stdout 버퍼링 해제
    sys.stdout.reconfigure(line_buffering=True)
    sys.stderr.reconfigure(line_buffering=True)
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # 기존 핸들러들 모두 제거
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)
    
    # 새 핸들러 추가
    root_logger.addHandler(handler)
    
    # basicConfig도 설정 (확실하게 하기 위해)
    logging.basicConfig(
        level=getattr(logging, log_level),
        format=log_format,
        handlers=[handler],
        force=True  # 기존 설정 강제 재설정
    )
    
    # 외부 라이브러리 로그 레벨 조정
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # 앱 모듈들의 로거 레벨 명시적 설정
    app_loggers = [
        "app.routers.admin",
        "app.routers.lotto", 
        "app.routers.auth",
        "app.routers.predictions",
        "app.routers.credits",
        "app.services.scheduler",
        "app.services.sms_service",
        "app.core.config",
        "app.core.security"
    ]
    
    target_level = getattr(logging, log_level)
    for logger_name in app_loggers:
        app_logger = logging.getLogger(logger_name)
        app_logger.setLevel(target_level)
        app_logger.propagate = True  # 부모 로거로 전파
        # 핸들러가 없으면 루트 핸들러 추가
        if not app_logger.handlers:
            app_logger.addHandler(handler)
        app_logger.info(f"🔧 {logger_name} logger level set to {log_level}")
    
    # 'app' 네임스페이스 로거도 설정
    app_root_logger = logging.getLogger("app")
    app_root_logger.setLevel(target_level)
    app_root_logger.propagate = True
    
    # 모든 로거가 루트 로거를 상속받도록 강제 설정
    logging.Logger.manager.loggerDict.clear()
    
    logger = logging.getLogger(__name__)
    logger.info(f"🚀 Logging initialized with level: {log_level}")
    logger.info(f"🌍 Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"📝 App loggers configured: {len(app_loggers)} modules")
    logger.info(f"🔍 Root logger level: {logging.getLogger().getEffectiveLevel()}")
    logger.info(f"🔍 Root logger handlers: {len(logging.getLogger().handlers)}")
    
    # 모든 app 로거들이 제대로 설정되었는지 확인
    for logger_name in app_loggers:
        test_logger = logging.getLogger(logger_name)
        logger.info(f"📊 {logger_name}: level={test_logger.getEffectiveLevel()}, handlers={len(test_logger.handlers)}")

# 로깅 초기화
setup_logging()

app = FastAPI(
    title="LottoChat AI Backend",
    description="AI-powered lotto prediction service",
    version="1.0.0"
)

# Custom exception handler for UTF-8 decode errors in request validation
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle request validation errors, especially those involving binary data
    that can't be decoded as UTF-8
    """
    logger = logging.getLogger(__name__)
    
    # 상세한 디버깅 로그
    logger.error(f"Validation error occurred on {request.url}")
    logger.error(f"Method: {request.method}")
    logger.error(f"Headers: {dict(request.headers)}")
    
    try:
        # 요청 본문 읽기 시도
        body = await request.body()
        logger.error(f"Raw body: {body}")
        if body:
            try:
                body_str = body.decode('utf-8')
                logger.error(f"Body as string: {body_str}")
            except UnicodeDecodeError as e:
                logger.error(f"Body decode error: {e}")
                logger.error(f"Body as bytes: {body[:100]}...")  # 처음 100바이트만
    except Exception as e:
        logger.error(f"Error reading request body: {e}")
    
    try:
        # Try to get the original error details
        errors = exc.errors()
        logger.error(f"Original validation errors: {errors}")
        
        # Filter out any binary data that might cause encoding issues
        filtered_errors = []
        for error in errors:
            try:
                # Try to serialize the error to check for encoding issues
                import json
                json.dumps(error)
                filtered_errors.append(error)
            except (UnicodeDecodeError, TypeError):
                # Replace problematic binary data with a safe message
                safe_error = {
                    "loc": error.get("loc", []),
                    "msg": "Invalid data format - binary data detected",
                    "type": "value_error"
                }
                filtered_errors.append(safe_error)
        
        return JSONResponse(
            status_code=422,
            content={"detail": filtered_errors}
        )
    except Exception:
        # Fallback for any other encoding-related errors
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "loc": ["body"],
                        "msg": "Request validation failed - invalid data format",
                        "type": "value_error"
                    }
                ]
            }
        )

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 헬스 체크 엔드포인트
@app.get("/health")
async def health():
    logger = logging.getLogger(__name__)
    logger.info("Health check requested")
    
    # 다른 모듈 로거들도 테스트
    admin_logger = logging.getLogger("app.routers.admin")
    admin_logger.info("Health check - testing admin logger")
    
    scheduler_logger = logging.getLogger("app.services.scheduler") 
    scheduler_logger.info("Health check - testing scheduler logger")
    
    return {"status": "healthy", "message": "LottoChat AI Backend is running"}

# 로깅 테스트 엔드포인트
@app.get("/test-logging")
async def test_logging():
    logger = logging.getLogger(__name__)
    
    # 다양한 레벨의 로그 메시지 테스트
    logger.debug("🐛 DEBUG: This is a debug message")
    logger.info("ℹ️ INFO: This is an info message")
    logger.warning("⚠️ WARNING: This is a warning message")
    logger.error("❌ ERROR: This is an error message")
    
    # 명시적으로 flush
    sys.stdout.flush()
    sys.stderr.flush()
    
    return {
        "message": "Logging test completed",
        "log_level": os.getenv("LOG_LEVEL", "INFO"),
        "environment": os.getenv("ENVIRONMENT", "development"),
        "pythonunbuffered": os.getenv("PYTHONUNBUFFERED", "0")
    }

# 정적 파일 서빙 설정
# 업로드 디렉터리 생성
upload_dir = Path("upload")
upload_dir.mkdir(exist_ok=True)
(upload_dir / "profile").mkdir(exist_ok=True)

app.mount("/upload", StaticFiles(directory="upload"), name="upload")

# 라우터 등록
app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(predictions.router, prefix=settings.api_prefix)
app.include_router(lotto.router, prefix=settings.api_prefix)
app.include_router(credits.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(fortune.router, prefix=settings.api_prefix)
app.include_router(payments.router, prefix=settings.api_prefix)

# 스케줄러 이벤트 등록
app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", shutdown_event)

# 루트 엔드포인트
@app.get("/")
async def root():
    return {
        "message": "Welcome to LottoChat AI Backend",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }