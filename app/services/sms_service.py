import random
import re
from typing import Optional
import logging
try:
    import redis
except ImportError:
    redis = None

from app.core.config import settings

# Logger 설정
logger = logging.getLogger(__name__)

# Redis 클라이언트 설정
if redis and hasattr(settings, 'REDIS_URL'):
    try:
        redis_client = redis.from_url(settings.REDIS_URL)
        # 연결 테스트
        redis_client.ping()
    except Exception:
        redis_client = None
else:
    redis_client = None

# 메모리 저장소 (Redis 없을 때 대안)
_memory_store = {}


class SMSService:
    """SMS 인증 서비스"""
    
    CODE_EXPIRE_SECONDS = 300  # 5분
    
    @staticmethod
    def normalize_phone(phone: str) -> str:
        """전화번호 정규화 (하이픈, 공백 제거)"""
        return re.sub(r'[^0-9]', '', phone)
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """한국 휴대폰 번호 유효성 검사"""
        normalized = SMSService.normalize_phone(phone)
        # 010, 011, 016, 017, 018, 019로 시작하고 총 10~11자리
        return re.match(r'^01[0-9]{8,9}$', normalized) is not None
    
    @staticmethod
    def generate_code() -> str:
        """6자리 인증번호 생성"""
        return str(random.randint(100000, 999999))
    
    @staticmethod
    def _store_code(phone: str, code: str) -> None:
        """인증번호 저장 (Redis 또는 메모리)"""
        key = f"sms_code:{phone}"
        
        if redis_client:
            # Redis에 저장
            redis_client.setex(key, SMSService.CODE_EXPIRE_SECONDS, code)
        else:
            # 메모리에 저장
            import time
            expire_time = time.time() + SMSService.CODE_EXPIRE_SECONDS
            _memory_store[key] = {"code": code, "expire_time": expire_time}
    
    @staticmethod
    def _get_code(phone: str) -> Optional[str]:
        """저장된 인증번호 조회"""
        key = f"sms_code:{phone}"
        
        if redis_client:
            # Redis에서 조회
            stored_code = redis_client.get(key)
            return stored_code.decode() if stored_code else None
        else:
            # 메모리에서 조회
            import time
            data = _memory_store.get(key)
            if data and time.time() < data["expire_time"]:
                return data["code"]
            elif data:
                # 만료된 코드 삭제
                del _memory_store[key]
            return None
    
    @staticmethod
    def _delete_code(phone: str) -> None:
        """인증번호 삭제"""
        key = f"sms_code:{phone}"
        
        if redis_client:
            redis_client.delete(key)
        else:
            _memory_store.pop(key, None)
    
    @staticmethod
    def send_code(phone: str) -> dict:
        """
        SMS 인증번호 발송
        실제 환경에서는 NHN Cloud SMS, CoolSMS, AWS SNS 등을 사용
        개발 환경에서는 콘솔에 출력
        """
        # 전화번호 검증
        if not SMSService.validate_phone(phone):
            return {
                "success": False, 
                "message": "올바른 휴대폰 번호를 입력해주세요"
            }
        
        # 번호 정규화
        normalized_phone = SMSService.normalize_phone(phone)
        
        # 인증번호 생성
        code = SMSService.generate_code()
        
        # 저장
        SMSService._store_code(normalized_phone, code)
        
        # 실제 SMS 발송 로직
        success = SMSService._send_actual_sms(normalized_phone, code)
        
        if success:
            return {
                "success": True, 
                "message": "인증번호가 발송되었습니다"
            }
        else:
            return {
                "success": False, 
                "message": "SMS 발송에 실패했습니다. 잠시 후 다시 시도해주세요"
            }
    
    @staticmethod
    def _send_actual_sms(phone: str, code: str) -> bool:
        """
        실제 SMS 발송
        운영 환경에서는 실제 SMS 서비스를 연동하고,
        개발/테스트 환경에서는 콘솔에 출력
        """
        try:
            # 개발 환경에서는 콘솔에 출력
            if settings.DEBUG if hasattr(settings, 'DEBUG') else True:
                logger.info(f"📱 SMS 발송: {phone}")
                logger.info(f"인증번호: {code}")
                logger.info(f"[LottoChat] 인증번호는 [{code}]입니다.")
                return True
            
            # 운영 환경에서는 실제 SMS 서비스 연동
            # 예시: CoolSMS, NHN Cloud SMS 등
            """
            # CoolSMS 예시
            from coolsms_python_sdk.messaging import Messaging
            messaging = Messaging(settings.SMS_API_KEY, settings.SMS_API_SECRET)
            
            message = f"[LottoChat] 인증번호는 [{code}]입니다."
            result = messaging.send({
                "from": settings.SMS_SENDER_NUMBER,
                "to": phone,
                "text": message
            })
            
            return result.get("success", False)
            """
            
            # 지금은 성공으로 처리
            return True
            
        except Exception as e:
            logger.error(f"SMS 발송 오류: {e}")
            return False
    
    @staticmethod
    def verify_code(phone: str, code: str) -> bool:
        """인증번호 확인"""
        if not code or len(code) != 6 or not code.isdigit():
            return False
        
        normalized_phone = SMSService.normalize_phone(phone)
        stored_code = SMSService._get_code(normalized_phone)
        
        if stored_code is None:
            return False
        
        if stored_code == code:
            # 인증 성공 시 코드 삭제
            SMSService._delete_code(normalized_phone)
            return True
        
        return False
    
    @staticmethod
    def cleanup_expired_codes() -> None:
        """만료된 인증번호 정리 (메모리 저장소용)"""
        if redis_client:
            return  # Redis는 자동으로 만료됨
        
        import time
        current_time = time.time()
        expired_keys = [
            key for key, data in _memory_store.items()
            if data["expire_time"] < current_time
        ]
        
        for key in expired_keys:
            del _memory_store[key]