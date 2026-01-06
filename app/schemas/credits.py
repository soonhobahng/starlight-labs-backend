from pydantic import BaseModel, validator
from datetime import datetime
from typing import List, Dict, Optional, Any
import uuid
from enum import Enum

from app.models.models import TransactionType


class CreditBalance(BaseModel):
    current_balance: int
    tier: str
    unlimited: bool = False
    
    class Config:
        from_attributes = True


class CreditTransactionResponse(BaseModel):
    id: uuid.UUID
    type: TransactionType
    amount: int
    balance_after: int
    description: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class CreditTransactionHistory(BaseModel):
    total: int
    transactions: List[CreditTransactionResponse]
    current_page: int
    total_pages: int


class AdRewardRequest(BaseModel):
    ad_id: str
    ad_type: str = "banner"  # banner, video, interstitial
    duration: Optional[int] = None  # 광고 시청 시간 (초)
    
    @validator('ad_id')
    def validate_ad_id(cls, v):
        if not v or len(v) < 5:
            raise ValueError('Invalid ad ID')
        return v


class AdRewardResponse(BaseModel):
    success: bool
    credits_earned: int
    new_balance: int
    transaction_id: uuid.UUID
    daily_remaining: int


class DailyBonusRequest(BaseModel):
    claim_date: Optional[str] = None  # YYYY-MM-DD format


class DailyBonusResponse(BaseModel):
    success: bool
    credits_earned: int
    new_balance: int
    transaction_id: Optional[uuid.UUID] = None
    next_bonus_available: str  # ISO datetime


class CreditPurchaseRequest(BaseModel):
    package_id: str
    payment_method: str = "card"  # card, paypal, applepay, googlepay
    
    @validator('package_id')
    def validate_package_id(cls, v):
        valid_packages = ["basic_10", "standard_50", "premium_100", "deluxe_250", "ultimate_500"]
        if v not in valid_packages:
            raise ValueError(f'Invalid package ID. Must be one of: {", ".join(valid_packages)}')
        return v


class CreditPurchaseResponse(BaseModel):
    success: bool
    package_id: str
    credits_purchased: int
    bonus_credits: int
    total_credits: int
    amount_paid: int
    new_balance: int
    transaction_id: uuid.UUID
    payment_id: str


class CreditRefundRequest(BaseModel):
    transaction_id: str
    reason: str
    
    @validator('reason')
    def validate_reason(cls, v):
        if not v or len(v) < 10:
            raise ValueError('Refund reason must be at least 10 characters')
        return v


class CreditRefundResponse(BaseModel):
    success: bool
    refund_amount: int
    new_balance: int
    transaction_id: uuid.UUID
    refund_reason: str


class CreditUsageRequest(BaseModel):
    amount: int
    description: str
    metadata_json: Optional[Dict[str, Any]] = None
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        return v


class CreditUsageResponse(BaseModel):
    success: bool
    credits_used: int
    new_balance: int
    transaction_id: uuid.UUID
    unlimited_tier: bool = False


class CreditStatsResponse(BaseModel):
    current_balance: int
    total_charged: int
    total_used: int
    monthly_used: int
    net_credits: int
    transaction_count: int
    type_statistics: Dict[str, Dict[str, int]]
    recent_transactions: List[Dict[str, Any]]


class DailyLimitsResponse(BaseModel):
    ad_rewards: Dict[str, Any]  # int나 str을 포함할 수 있도록 Any로 변경
    predictions: Dict[str, Any]
    daily_bonus: Dict[str, bool]


class CreditPackageInfo(BaseModel):
    id: str
    name: str
    credits: int
    bonus_credits: int
    total_credits: int
    price: int
    discount_percentage: Optional[float] = None
    popular: bool = False


class CreditPackagesResponse(BaseModel):
    packages: List[CreditPackageInfo]
    user_tier: str
    current_balance: int


class TransferCreditsRequest(BaseModel):
    recipient_email: str
    amount: int
    message: Optional[str] = None
    
    @validator('amount')
    def validate_amount(cls, v):
        if v <= 0:
            raise ValueError('Amount must be positive')
        if v > 100:  # 한번에 최대 100 크레딧까지만 선물 가능
            raise ValueError('Maximum transfer amount is 100 credits')
        return v
    
    @validator('recipient_email')
    def validate_email(cls, v):
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        return v


class TransferCreditsResponse(BaseModel):
    success: bool
    amount_transferred: int
    recipient_email: str
    new_balance: int
    transaction_id: uuid.UUID
    transfer_fee: int = 0


# Toss Payments 스키마
class TossPaymentOrderRequest(BaseModel):
    """토스 결제 주문 생성 요청"""
    package_id: str
    
    @validator('package_id')
    def validate_package_id(cls, v):
        valid_packages = ["basic_10", "standard_50", "premium_100", "deluxe_250", "ultimate_500"]
        if v not in valid_packages:
            raise ValueError(f'Invalid package ID. Must be one of: {", ".join(valid_packages)}')
        return v


class TossPaymentOrderResponse(BaseModel):
    """토스 결제 주문 생성 응답"""
    order_id: str
    amount: int
    order_name: str
    customer_name: str
    package_info: Dict[str, Any]


class TossPaymentConfirmRequest(BaseModel):
    """토스 결제 승인 요청"""
    payment_key: str
    order_id: str
    amount: int


class TossPaymentConfirmResponse(BaseModel):
    """토스 결제 승인 응답"""
    success: bool
    payment_id: str
    order_id: str
    credits_purchased: int
    bonus_credits: int
    total_credits: int
    new_balance: int
    transaction_id: uuid.UUID


class TossPaymentWebhookData(BaseModel):
    """토스 웹훅 데이터"""
    eventType: str
    data: Dict[str, Any]
    createdAt: str


class TossPaymentCancelRequest(BaseModel):
    """토스 결제 취소 요청"""
    payment_key: str
    cancel_reason: str


class TossPaymentCancelResponse(BaseModel):
    """토스 결제 취소 응답"""
    success: bool
    cancel_amount: int
    refund_amount: int
    new_balance: int
    transaction_id: uuid.UUID
    already_cancelled_in_gateway: bool = False  # 토스에서 이미 취소되었는지 여부


class UserCancelPaymentRequest(BaseModel):
    """사용자용 결제 취소 요청"""
    cancel_reason: str = "사용자 요청"
    
    @validator('cancel_reason')
    def validate_reason(cls, v):
        if not v or len(v.strip()) < 3:
            raise ValueError('취소 사유는 3자 이상 입력해주세요')
        return v.strip()


# Payple Payments 스키마
class PayplePaymentOrderRequest(BaseModel):
    """페이플 결제 주문 생성 요청"""
    package_id: str
    
    @validator('package_id')
    def validate_package_id(cls, v):
        valid_packages = ["basic_10", "standard_50", "premium_100", "deluxe_250", "ultimate_500"]
        if v not in valid_packages:
            raise ValueError(f'Invalid package ID. Must be one of: {", ".join(valid_packages)}')
        return v


class PayplePaymentOrderResponse(BaseModel):
    """페이플 결제 주문 생성 응답"""
    order_id: str
    amount: int
    order_name: str
    customer_name: str
    package_info: Dict[str, Any]
    payple_url: str
    payple_data: Dict[str, Any]


class PayplePaymentConfirmRequest(BaseModel):
    """페이플 결제 승인 요청"""
    order_id: str
    payple_pcd_pay_reqkey: str  # 페이플에서 제공하는 결제 요청키


class PayplePaymentConfirmResponse(BaseModel):
    """페이플 결제 승인 응답"""
    success: bool
    payment_id: str
    order_id: str
    credits_purchased: int
    bonus_credits: int
    total_credits: int
    new_balance: int
    transaction_id: uuid.UUID


class PayplePaymentWebhookData(BaseModel):
    """페이플 웹훅 데이터"""
    PCD_PAY_RST: str
    PCD_PAY_OID: str
    PCD_PAY_TYPE: str
    PCD_PAY_WORK: str
    PCD_PAYER_ID: Optional[str] = None
    PCD_PAY_GOODS: Optional[str] = None
    PCD_PAY_TOTAL: Optional[int] = None
    AuthHash: Optional[str] = None


class PayplePaymentCancelRequest(BaseModel):
    """페이플 결제 취소 요청"""
    order_id: str
    cancel_reason: str


class PayplePaymentCancelResponse(BaseModel):
    """페이플 결제 취소 응답"""
    success: bool
    cancel_amount: int
    refund_amount: int
    new_balance: int
    transaction_id: uuid.UUID
    already_cancelled_in_gateway: bool = False