# app/services/toss_payment_service.py

import base64
import json
import requests
import hashlib
import hmac
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
import logging

from app.core.config import settings
from app.services.credit_service import CreditPackage

logger = logging.getLogger(__name__)


class TossPaymentError(Exception):
    """토스 결제 관련 에러"""
    def __init__(self, message: str, error_code: str = None, error_data: Dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.error_data = error_data


class TossPaymentService:
    """토스 페이먼츠 서비스"""
    
    BASE_URL = "https://api.tosspayments.com/v1"
    TEST_URL = "https://api.tosspayments.com/v1"  # 실제로는 동일
    
    def __init__(self):
        self.secret_key = settings.toss_secret_key
        self.client_key = settings.toss_client_key
        self.webhook_secret = settings.toss_webhook_secret
        
        if not self.secret_key:
            logger.warning("Toss secret key not configured")
    
    def _get_auth_header(self) -> str:
        """인증 헤더 생성"""
        credentials = f"{self.secret_key}:"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded_credentials}"
    
    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict[str, Any]:
        """토스 API 요청"""
        url = f"{self.BASE_URL}/{endpoint}"
        headers = {
            "Authorization": self._get_auth_header(),
            "Content-Type": "application/json"
        }
        
        try:
            if method.upper() == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=30)
            elif method.upper() == "GET":
                response = requests.get(url, headers=headers, timeout=30)
            else:
                raise TossPaymentError(f"Unsupported HTTP method: {method}")
            
            response_data = response.json()
            
            if not response.ok:
                error_code = response_data.get("code", "UNKNOWN_ERROR")
                error_message = response_data.get("message", "Unknown error occurred")
                logger.error(f"Toss API error: {error_code} - {error_message}")
                raise TossPaymentError(error_message, error_code, response_data)
            
            return response_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling Toss API: {e}")
            raise TossPaymentError(f"Network error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Toss API: {e}")
            raise TossPaymentError("Invalid response from payment gateway")
    
    def create_order(self, user_id: str, package_id: str, user_name: str = "고객") -> Dict[str, Any]:
        """주문 생성 (로컬에서만 처리)"""
        try:
            # 패키지 정보 조회
            package = CreditPackage.get_package(package_id)
            if not package:
                raise TossPaymentError(f"Invalid package: {package_id}")
            
            # 주문 ID 생성
            order_id = f"order_{uuid.uuid4().hex[:12]}_{int(datetime.now().timestamp())}"
            
            # 총 크레딧 계산 (기본 크레딧 + 보너스)
            total_credits = package["credits"] + package["bonus"]
            
            # 패키지 정보에 total_credits 추가
            enhanced_package = package.copy()
            enhanced_package["total_credits"] = total_credits
            enhanced_package["name"] = f"크레딧 {total_credits}개"
            
            return {
                "order_id": order_id,
                "amount": package["price"],
                "order_name": f"크레딧 {total_credits}개",
                "customer_name": user_name,
                "package_info": enhanced_package
            }
            
        except Exception as e:
            logger.error(f"Error creating order: {e}")
            raise TossPaymentError(f"Failed to create order: {str(e)}")
    
    def confirm_payment(self, payment_key: str, order_id: str, amount: int) -> Dict[str, Any]:
        """결제 승인"""
        try:
            data = {
                "paymentKey": payment_key,
                "orderId": order_id,
                "amount": amount
            }
            
            logger.info(f"Confirming payment: {payment_key}, order: {order_id}, amount: {amount}")
            
            result = self._make_request("POST", "payments/confirm", data)
            
            logger.info(f"Payment confirmed successfully: {result.get('orderId')}")
            return result
            
        except TossPaymentError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error confirming payment: {e}")
            raise TossPaymentError(f"Failed to confirm payment: {str(e)}")
    
    def get_payment(self, payment_key: str) -> Dict[str, Any]:
        """결제 정보 조회"""
        try:
            return self._make_request("GET", f"payments/{payment_key}")
        except Exception as e:
            logger.error(f"Error getting payment info: {e}")
            raise TossPaymentError(f"Failed to get payment info: {str(e)}")
    
    def cancel_payment(self, payment_key: str, cancel_reason: str, 
                      cancel_amount: Optional[int] = None) -> Dict[str, Any]:
        """결제 취소"""
        try:
            data = {
                "cancelReason": cancel_reason
            }
            
            if cancel_amount:
                data["cancelAmount"] = cancel_amount
            
            logger.info(f"Cancelling payment: {payment_key}, reason: {cancel_reason}")
            
            result = self._make_request("POST", f"payments/{payment_key}/cancel", data)
            
            logger.info(f"Payment cancelled successfully: {payment_key}")
            return result
            
        except TossPaymentError as e:
            # 이미 취소된 결제인 경우 처리
            if e.error_code in ["ALREADY_CANCELED_PAYMENT", "PAYMENT_ALREADY_CANCELED", "CANCELED_PAYMENT"]:
                logger.info(f"Payment already cancelled in Toss: {payment_key}")
                # 토스에서는 이미 취소됨을 나타내는 가상의 응답 반환
                return {
                    "status": "CANCELED",
                    "paymentKey": payment_key,
                    "message": "Payment already cancelled in Toss payment gateway",
                    "alreadyCancelled": True
                }
            else:
                # 다른 오류는 그대로 전파
                raise
        except Exception as e:
            logger.error(f"Error cancelling payment: {e}")
            raise TossPaymentError(f"Failed to cancel payment: {str(e)}")
    
    def verify_webhook_signature(self, body: str, signature: str) -> bool:
        """웹훅 서명 검증"""
        try:
            if not self.webhook_secret:
                logger.warning("Webhook secret not configured, skipping verification")
                return True  # 개발 환경에서는 검증 스킵
            
            expected_signature = hmac.new(
                self.webhook_secret.encode(),
                body.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
            
        except Exception as e:
            logger.error(f"Error verifying webhook signature: {e}")
            return False
    
    def process_webhook_event(self, event_type: str, data: Dict[str, Any]) -> bool:
        """웹훅 이벤트 처리"""
        try:
            logger.info(f"Processing webhook event: {event_type}")
            
            # 이벤트 타입별 처리
            if event_type == "PAYMENT_CONFIRMED":
                # 결제 승인 완료
                payment_key = data.get("paymentKey")
                logger.info(f"Payment confirmed via webhook: {payment_key}")
                return True
                
            elif event_type == "PAYMENT_FAILED":
                # 결제 실패
                payment_key = data.get("paymentKey")
                failure_code = data.get("failure", {}).get("code")
                failure_message = data.get("failure", {}).get("message")
                logger.info(f"Payment failed via webhook: {payment_key}, {failure_code}")
                return True
                
            elif event_type == "PAYMENT_CANCELLED":
                # 결제 취소
                payment_key = data.get("paymentKey")
                logger.info(f"Payment cancelled via webhook: {payment_key}")
                return True
                
            else:
                logger.info(f"Unhandled webhook event type: {event_type}")
                return True
                
        except Exception as e:
            logger.error(f"Error processing webhook event: {e}")
            return False


# 전역 서비스 인스턴스
toss_payment_service = TossPaymentService()