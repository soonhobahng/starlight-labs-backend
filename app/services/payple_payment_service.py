# app/services/payple_payment_service.py

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


class PayplePaymentError(Exception):
    """페이플 결제 관련 에러"""
    def __init__(self, message: str, error_code: str = None, error_data: Dict = None):
        super().__init__(message)
        self.error_code = error_code
        self.error_data = error_data


class PayplePaymentService:
    """페이플 결제 서비스"""
    
    # Payple API URLs
    BASE_URL = "https://democpay.payple.kr"
    PROD_URL = "https://cpay.payple.kr"
    
    def __init__(self):
        self.cst_id = settings.payple_cst_id
        self.cust_key = settings.payple_cust_key
        self.auth_key = settings.payple_auth_key
        
        # 환경에 따른 URL 설정
        if settings.debug:
            self.api_url = self.BASE_URL
        else:
            self.api_url = self.PROD_URL
            
        if not self.cst_id:
            logger.warning("Payple CST ID not configured")
    
    def _generate_auth_hash(self, data: Dict[str, Any]) -> str:
        """인증 해시 생성"""
        try:
            # Payple 요구사항에 따른 해시 생성
            cst_id = data.get('cst_id', self.cst_id)
            custKey = data.get('custKey', self.cust_key)
            
            # 파라미터를 알파벳 순으로 정렬하여 문자열 생성
            sorted_params = sorted(data.items())
            param_string = '&'.join([f"{k}={v}" for k, v in sorted_params])
            
            # 인증키와 함께 해시 생성
            hash_string = f"{param_string}&authKey={self.auth_key}"
            return hashlib.md5(hash_string.encode('utf-8')).hexdigest()
            
        except Exception as e:
            logger.error(f"Error generating auth hash: {e}")
            raise PayplePaymentError(f"Failed to generate auth hash: {str(e)}")
    
    def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """페이플 API 요청"""
        url = f"{self.api_url}/{endpoint}"
        
        # 공통 파라미터 추가
        data.update({
            'cst_id': self.cst_id,
            'custKey': self.cust_key,
        })
        
        # 인증 해시 추가
        data['AuthHash'] = self._generate_auth_hash(data)
        
        headers = {
            'Content-Type': 'application/json',
            'Referer': settings.frontend_url
        }
        
        try:
            logger.info(f"Making Payple API request to {endpoint}")
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            response_data = response.json()
            
            # Payple 응답 확인
            if response_data.get('result') != 'success':
                error_message = response_data.get('result_msg', 'Unknown error occurred')
                error_code = response_data.get('result_code', 'UNKNOWN_ERROR')
                logger.error(f"Payple API error: {error_code} - {error_message}")
                raise PayplePaymentError(error_message, error_code, response_data)
            
            return response_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error calling Payple API: {e}")
            raise PayplePaymentError(f"Network error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Payple API: {e}")
            raise PayplePaymentError("Invalid response from payment gateway")
        except PayplePaymentError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling Payple API: {e}")
            raise PayplePaymentError(f"Unexpected error: {str(e)}")
    
    def create_order(self, user_id: str, package_id: str, user_name: str = "고객") -> Dict[str, Any]:
        """주문 생성"""
        try:
            # 패키지 정보 조회
            package = CreditPackage.get_package(package_id)
            if not package:
                raise PayplePaymentError(f"Invalid package: {package_id}")
            
            # 주문 ID 생성 (페이플 요구사항: 영문, 숫자, 특수문자(-,_) 조합, 최대 50자)
            order_id = f"order_{uuid.uuid4().hex[:12]}_{int(datetime.now().timestamp())}"
            
            # 총 크레딧 계산
            total_credits = package["credits"] + package["bonus"]
            
            # 페이플 결제 준비 요청
            payment_data = {
                'PCD_PAYCANCEL_FLAG': 'N',  # 취소 가능 여부
                'PCD_PAY_TYPE': 'card',     # 결제 방법
                'PCD_PAY_WORK': 'PAY',      # 결제 작업 구분
                'PCD_CARD_VER': '01',       # 카드 버전
                'PCD_PAY_GOODS': f"크레딧 {total_credits}개",
                'PCD_PAY_TOTAL': package["price"],
                'PCD_PAY_OID': order_id,
                'PCD_PAYER_NAME': user_name,
                'PCD_PAYER_HP': '',         # 휴대폰 번호 (선택)
                'PCD_PAYER_EMAIL': '',      # 이메일 (선택)
                'PCD_PAY_BANKNAME': '',     # 입금자명 (계좌이체시)
                'PCD_REGULER_FLAG': 'N',    # 정기결제 여부
            }
            
            # 페이플 결제 준비 API 호출
            response = self._make_request('php/pay.php', payment_data)
            
            # 패키지 정보에 total_credits 추가
            enhanced_package = package.copy()
            enhanced_package["total_credits"] = total_credits
            enhanced_package["name"] = f"크레딧 {total_credits}개"
            
            return {
                "order_id": order_id,
                "amount": package["price"],
                "order_name": f"크레딧 {total_credits}개",
                "customer_name": user_name,
                "package_info": enhanced_package,
                "payple_data": response,  # 페이플 응답 데이터
                "payple_url": response.get('payple_url', ''),  # 결제 페이지 URL
            }
            
        except PayplePaymentError:
            raise
        except Exception as e:
            logger.error(f"Error creating Payple order: {e}")
            raise PayplePaymentError(f"Failed to create order: {str(e)}")
    
    def confirm_payment(self, order_id: str, payple_pcd_pay_reqkey: str) -> Dict[str, Any]:
        """결제 승인 확인"""
        try:
            # 결제 승인 확인 요청
            confirm_data = {
                'PCD_PAYCANCEL_FLAG': 'N',
                'PCD_PAY_TYPE': 'card',
                'PCD_PAY_WORK': 'CONFIRM',
                'PCD_PAY_OID': order_id,
                'PCD_PAY_REQKEY': payple_pcd_pay_reqkey,
            }
            
            logger.info(f"Confirming Payple payment: order {order_id}")
            
            result = self._make_request('php/auth.php', confirm_data)
            
            logger.info(f"Payple payment confirmed successfully: {order_id}")
            return result
            
        except PayplePaymentError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error confirming Payple payment: {e}")
            raise PayplePaymentError(f"Failed to confirm payment: {str(e)}")
    
    def get_payment_status(self, order_id: str) -> Dict[str, Any]:
        """결제 상태 조회"""
        try:
            status_data = {
                'PCD_PAY_TYPE': 'card',
                'PCD_PAY_WORK': 'PAYLIST',
                'PCD_PAY_OID': order_id,
            }
            
            return self._make_request('php/paylist.php', status_data)
            
        except Exception as e:
            logger.error(f"Error getting Payple payment status: {e}")
            raise PayplePaymentError(f"Failed to get payment status: {str(e)}")
    
    def cancel_payment(self, order_id: str, cancel_reason: str, 
                      cancel_amount: Optional[int] = None) -> Dict[str, Any]:
        """결제 취소"""
        try:
            cancel_data = {
                'PCD_PAYCANCEL_FLAG': 'Y',
                'PCD_PAY_TYPE': 'card',
                'PCD_PAY_WORK': 'PAYCANCEL',
                'PCD_PAY_OID': order_id,
                'PCD_PAYCANCEL_NOTE': cancel_reason,
            }
            
            if cancel_amount:
                cancel_data['PCD_PAY_TOTAL'] = cancel_amount
            
            logger.info(f"Cancelling Payple payment: {order_id}, reason: {cancel_reason}")
            
            result = self._make_request('php/cancel.php', cancel_data)
            
            logger.info(f"Payple payment cancelled successfully: {order_id}")
            return result
            
        except PayplePaymentError as e:
            # 이미 취소된 결제인 경우 처리
            if "이미 취소" in str(e) or "already" in str(e).lower():
                logger.info(f"Payple payment already cancelled: {order_id}")
                return {
                    "result": "success",
                    "result_msg": "Payment already cancelled",
                    "PCD_PAY_OID": order_id,
                    "alreadyCancelled": True
                }
            else:
                raise
        except Exception as e:
            logger.error(f"Error cancelling Payple payment: {e}")
            raise PayplePaymentError(f"Failed to cancel payment: {str(e)}")
    
    def verify_webhook(self, data: Dict[str, Any]) -> bool:
        """웹훅 검증"""
        try:
            # 페이플 웹훅 데이터 검증
            received_hash = data.get('AuthHash', '')
            
            # 해시 재생성하여 검증
            data_copy = data.copy()
            data_copy.pop('AuthHash', None)
            
            expected_hash = self._generate_auth_hash(data_copy)
            
            return received_hash == expected_hash
            
        except Exception as e:
            logger.error(f"Error verifying Payple webhook: {e}")
            return False
    
    def process_webhook(self, webhook_data: Dict[str, Any]) -> bool:
        """웹훅 처리"""
        try:
            logger.info(f"Processing Payple webhook")
            
            # 웹훅 검증
            if not self.verify_webhook(webhook_data):
                logger.warning("Invalid Payple webhook signature")
                return False
            
            # 결제 상태 확인
            pay_result = webhook_data.get('PCD_PAY_RST', '')
            order_id = webhook_data.get('PCD_PAY_OID', '')
            
            logger.info(f"Payple webhook - Order: {order_id}, Result: {pay_result}")
            
            if pay_result == 'success':
                logger.info(f"Payple payment success via webhook: {order_id}")
            elif pay_result == 'cancel':
                logger.info(f"Payple payment cancelled via webhook: {order_id}")
            else:
                logger.info(f"Payple payment failed via webhook: {order_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing Payple webhook: {e}")
            return False


# 전역 서비스 인스턴스
payple_payment_service = PayplePaymentService()