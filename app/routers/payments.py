# app/routers/payments.py

from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict, Any
import json
import uuid
from datetime import datetime
import logging

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, Payment, PaymentStatus, TransactionType
from app.schemas.credits import (
    TossPaymentOrderRequest, TossPaymentOrderResponse,
    TossPaymentConfirmRequest, TossPaymentConfirmResponse,
    TossPaymentWebhookData, TossPaymentCancelRequest, TossPaymentCancelResponse,
    UserCancelPaymentRequest,
    PayplePaymentOrderRequest, PayplePaymentOrderResponse,
    PayplePaymentConfirmRequest, PayplePaymentConfirmResponse,
    PayplePaymentWebhookData, PayplePaymentCancelRequest, PayplePaymentCancelResponse
)
from app.services.toss_payment_service import toss_payment_service, TossPaymentError
from app.services.payple_payment_service import payple_payment_service, PayplePaymentError
from app.services.credit_service import CreditService, CreditPackage

router = APIRouter(prefix="/payments", tags=["payments"])
logger = logging.getLogger(__name__)


@router.post("/toss/order", response_model=TossPaymentOrderResponse)
async def create_toss_order(
    request: TossPaymentOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    토스 결제 주문 생성
    - 프론트엔드에서 결제 위젯 초기화 전에 호출
    """
    try:
        # 주문 정보 생성
        order_data = toss_payment_service.create_order(
            user_id=str(current_user.id),
            package_id=request.package_id,
            user_name=current_user.nickname or "고객"
        )
        
        # DB에 결제 레코드 생성 (pending 상태)
        payment = Payment(
            id=uuid.uuid4(),
            user_id=current_user.id,
            payment_type="credit_purchase",
            amount=order_data["amount"],
            credits_purchased=order_data["package_info"]["total_credits"],
            payment_method="toss",
            order_id=order_data["order_id"],
            status=PaymentStatus.pending
        )
        
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        logger.info(f"Created order for user {current_user.id}: {order_data['order_id']}")
        
        return TossPaymentOrderResponse(
            order_id=order_data["order_id"],
            amount=order_data["amount"],
            order_name=order_data["order_name"],
            customer_name=order_data["customer_name"],
            package_info=order_data["package_info"]
        )
        
    except TossPaymentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment order creation failed: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating payment order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment order"
        )


@router.post("/toss/confirm", response_model=TossPaymentConfirmResponse)
async def confirm_toss_payment(
    request: TossPaymentConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    토스 결제 승인 및 크레딧 지급
    - 프론트엔드에서 결제 성공 후 호출
    """
    try:
        # 1. 주문 정보 조회
        payment = db.query(Payment).filter(
            Payment.order_id == request.order_id,
            Payment.user_id == current_user.id,
            Payment.status == PaymentStatus.pending
        ).first()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment order not found"
            )
        
        # 2. 금액 검증
        if payment.amount != request.amount:
            logger.error(f"Amount mismatch: expected {payment.amount}, got {request.amount}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Payment amount mismatch"
            )
        
        # 3. 토스에 결제 승인 요청
        toss_response = toss_payment_service.confirm_payment(
            payment_key=request.payment_key,
            order_id=request.order_id,
            amount=request.amount
        )
        
        # 4. 결제 정보 업데이트
        payment.payment_key = request.payment_key
        payment.toss_order_id = toss_response.get("orderId")
        payment.transaction_id = toss_response.get("transactionKey")
        payment.status = PaymentStatus.completed
        payment.completed_at = datetime.utcnow()
        
        # 5. 크레딧 지급
        package = CreditPackage.get_package_by_credits(payment.credits_purchased)
        if package:
            transaction = CreditService.add_credits(
                db=db,
                user=current_user,
                amount=payment.credits_purchased,
                transaction_type=TransactionType.purchase,
                description=f"크레딧 구매 ({package['name']})",
                metadata_json={
                    "payment_id": str(payment.id),
                    "package_id": package["id"],
                    "toss_payment_key": request.payment_key
                }
            )
        
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"Payment confirmed for user {current_user.id}: {request.payment_key}")
        
        return TossPaymentConfirmResponse(
            success=True,
            payment_id=str(payment.id),
            order_id=request.order_id,
            credits_purchased=package["credits"] if package else payment.credits_purchased,
            bonus_credits=package["bonus"] if package else 0,
            total_credits=payment.credits_purchased,
            new_balance=current_user.credits,
            transaction_id=transaction.id if package else uuid.uuid4()
        )
        
    except TossPaymentError as e:
        # 토스 결제 오류 시 결제 상태를 실패로 변경
        payment.status = PaymentStatus.failed
        payment.failure_code = e.error_code
        payment.failure_message = str(e)
        db.commit()
        
        logger.error(f"Toss payment confirmation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment confirmation failed: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error confirming payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to confirm payment"
        )


@router.post("/toss/webhook")
async def handle_toss_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    토스 페이먼츠 웹훅 처리
    - 결제 상태 변경 시 토스에서 호출
    """
    try:
        # 요청 본문 읽기
        body = await request.body()
        signature = request.headers.get("toss-signature", "")
        
        # 서명 검증
        if not toss_payment_service.verify_webhook_signature(body.decode(), signature):
            logger.warning("Invalid webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature"
            )
        
        # 웹훅 데이터 파싱
        webhook_data = json.loads(body.decode())
        event_type = webhook_data.get("eventType")
        data = webhook_data.get("data", {})
        
        logger.info(f"Received webhook: {event_type}")
        
        # 백그라운드 태스크로 처리
        background_tasks.add_task(process_webhook_event, event_type, data, db)
        
        return {"success": True}
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid webhook JSON: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON"
        )
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


@router.post("/toss/cancel", response_model=TossPaymentCancelResponse)
async def cancel_toss_payment(
    request: TossPaymentCancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    토스 결제 취소 및 크레딧 환불
    """
    try:
        # 결제 정보 조회
        payment = db.query(Payment).filter(
            Payment.payment_key == request.payment_key,
            Payment.user_id == current_user.id,
            Payment.status == PaymentStatus.completed
        ).first()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found or cannot be cancelled"
            )
        
        # 토스에 취소 요청
        toss_response = toss_payment_service.cancel_payment(
            payment_key=request.payment_key,
            cancel_reason=request.cancel_reason
        )
        
        # 크레딧 환불 처리
        refund_transaction = CreditService.add_credits(
            db=db,
            user=current_user,
            amount=-payment.credits_purchased,  # 음수로 차감
            transaction_type=TransactionType.refund,
            description=f"결제 취소 환불: {request.cancel_reason}",
            metadata_json={
                "payment_id": str(payment.id),
                "toss_payment_key": request.payment_key,
                "cancel_reason": request.cancel_reason
            }
        )
        
        # 결제 상태 변경
        payment.status = PaymentStatus.refunded
        
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"Payment cancelled for user {current_user.id}: {request.payment_key}")
        
        return TossPaymentCancelResponse(
            success=True,
            cancel_amount=payment.amount,
            refund_amount=payment.credits_purchased,
            new_balance=current_user.credits,
            transaction_id=refund_transaction.id
        )
        
    except TossPaymentError as e:
        logger.error(f"Toss payment cancellation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment cancellation failed: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel payment"
        )


async def process_webhook_event(event_type: str, data: Dict[str, Any], db: Session):
    """웹훅 이벤트 백그라운드 처리"""
    try:
        # 웹훅 이벤트 처리
        success = toss_payment_service.process_webhook_event(event_type, data)
        
        if success:
            logger.info(f"Webhook event processed successfully: {event_type}")
        else:
            logger.error(f"Failed to process webhook event: {event_type}")
            
    except Exception as e:
        logger.error(f"Error in webhook background task: {e}")


@router.post("/user/cancel/{payment_id}", response_model=TossPaymentCancelResponse)
async def cancel_payment_user(
    payment_id: str,
    request: UserCancelPaymentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    사용자 결제 취소 요청
    - 24시간 이내 결제만 취소 가능
    - 완료된 결제 상태만 취소 가능
    """
    
    try:
        import uuid
        payment_uuid = uuid.UUID(payment_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payment ID format"
        )
    
    # 본인 결제인지 확인
    payment = db.query(Payment).filter(
        Payment.id == payment_uuid,
        Payment.user_id == current_user.id
    ).first()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found"
        )
    
    # 취소 가능한 상태 확인
    if payment.status != PaymentStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot cancel payment with status: {payment.status.value}"
        )
    
    # 24시간 이내 결제인지 확인
    if payment.completed_at:
        time_diff = datetime.utcnow() - payment.completed_at
        if time_diff.total_seconds() > 24 * 3600:  # 24시간
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel payment older than 24 hours"
            )
    else:
        # completed_at이 없으면 created_at 기준
        time_diff = datetime.utcnow() - payment.created_at
        if time_diff.total_seconds() > 24 * 3600:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel payment older than 24 hours"
            )
    
    # 사용자 크레딧 확인 (환불할 만큼 크레딧이 있는지)
    refund_credits = payment.credits_purchased or 0
    if current_user.credits < refund_credits:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Insufficient credits for refund. Current: {current_user.credits}, Required: {refund_credits}"
        )
    
    try:
        # 토스 결제 취소 요청
        toss_already_cancelled = False
        if payment.payment_method == "toss" and hasattr(payment, 'payment_key') and payment.payment_key:
            toss_response = toss_payment_service.cancel_payment(
                payment_key=payment.payment_key,
                cancel_reason=request.cancel_reason
            )
            
            # 이미 취소된 경우 확인
            if toss_response.get("alreadyCancelled"):
                toss_already_cancelled = True
                logger.info(f"Toss payment was already cancelled: {payment.payment_key}")
        
        # 크레딧 차감 처리
        if refund_credits > 0:
            refund_transaction = CreditService.add_credits(
                db=db,
                user=current_user,
                amount=-refund_credits,  # 음수로 차감
                transaction_type=TransactionType.refund,
                description=f"결제 취소 환불: {request.cancel_reason}",
                metadata_json={
                    "payment_id": str(payment.id),
                    "cancel_reason": request.cancel_reason,
                    "user_requested": True
                }
            )
        
        # 결제 상태 변경
        payment.status = PaymentStatus.refunded
        if hasattr(payment, 'failure_message'):
            if toss_already_cancelled:
                payment.failure_message = f"사용자 취소 (토스에서 이미 취소됨): {request.cancel_reason}"
            else:
                payment.failure_message = f"사용자 취소: {request.cancel_reason}"
        
        db.commit()
        db.refresh(current_user)
        
        if toss_already_cancelled:
            logger.info(f"Payment {payment_id} cancelled by user {current_user.id} (already cancelled in Toss): {request.cancel_reason}")
        else:
            logger.info(f"Payment {payment_id} cancelled by user {current_user.id}: {request.cancel_reason}")
        
        return TossPaymentCancelResponse(
            success=True,
            cancel_amount=payment.amount,
            refund_amount=refund_credits,
            new_balance=current_user.credits,
            transaction_id=refund_transaction.id if refund_credits > 0 else uuid.uuid4(),
            already_cancelled_in_gateway=toss_already_cancelled
        )
        
    except TossPaymentError as e:
        logger.error(f"Toss payment cancellation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment cancellation failed: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling user payment {payment_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel payment"
        )


# ============================================================================
# Payple 결제 엔드포인트
# ============================================================================

@router.post("/payple/order", response_model=PayplePaymentOrderResponse)
async def create_payple_order(
    request: PayplePaymentOrderRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    페이플 결제 주문 생성
    - 프론트엔드에서 결제 위젯 초기화 전에 호출
    """
    try:
        # 주문 정보 생성
        order_data = payple_payment_service.create_order(
            user_id=str(current_user.id),
            package_id=request.package_id,
            user_name=current_user.nickname or "고객"
        )
        
        # DB에 결제 레코드 생성 (pending 상태)
        payment = Payment(
            id=uuid.uuid4(),
            user_id=current_user.id,
            payment_type="credit_purchase",
            amount=order_data["amount"],
            credits_purchased=order_data["package_info"]["total_credits"],
            payment_method="payple",
            order_id=order_data["order_id"],
            status=PaymentStatus.pending
        )
        
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        logger.info(f"Created Payple order for user {current_user.id}: {order_data['order_id']}")
        
        return PayplePaymentOrderResponse(
            order_id=order_data["order_id"],
            amount=order_data["amount"],
            order_name=order_data["order_name"],
            customer_name=order_data["customer_name"],
            package_info=order_data["package_info"],
            payple_url=order_data["payple_url"],
            payple_data=order_data["payple_data"]
        )
        
    except PayplePaymentError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment order creation failed: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating Payple payment order: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create payment order"
        )


@router.post("/payple/confirm", response_model=PayplePaymentConfirmResponse)
async def confirm_payple_payment(
    request: PayplePaymentConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    페이플 결제 승인 및 크레딧 지급
    - 프론트엔드에서 결제 성공 후 호출
    """
    try:
        # 1. 주문 정보 조회
        payment = db.query(Payment).filter(
            Payment.order_id == request.order_id,
            Payment.user_id == current_user.id,
            Payment.status == PaymentStatus.pending
        ).first()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment order not found"
            )
        
        # 2. 페이플에 결제 승인 확인 요청
        payple_response = payple_payment_service.confirm_payment(
            order_id=request.order_id,
            payple_pcd_pay_reqkey=request.payple_pcd_pay_reqkey
        )
        
        # 3. 결제 정보 업데이트
        payment.payment_key = request.payple_pcd_pay_reqkey
        payment.transaction_id = payple_response.get("PCD_PAY_REQKEY")
        payment.status = PaymentStatus.completed
        payment.completed_at = datetime.utcnow()
        
        # 4. 크레딧 지급
        package = CreditPackage.get_package_by_credits(payment.credits_purchased)
        if package:
            transaction = CreditService.add_credits(
                db=db,
                user=current_user,
                amount=payment.credits_purchased,
                transaction_type=TransactionType.purchase,
                description=f"크레딧 구매 ({package['name']})",
                metadata_json={
                    "payment_id": str(payment.id),
                    "package_id": package["id"],
                    "payple_payment_key": request.payple_pcd_pay_reqkey
                }
            )
        
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"Payple payment confirmed for user {current_user.id}: {request.payple_pcd_pay_reqkey}")
        
        return PayplePaymentConfirmResponse(
            success=True,
            payment_id=str(payment.id),
            order_id=request.order_id,
            credits_purchased=package["credits"] if package else payment.credits_purchased,
            bonus_credits=package["bonus"] if package else 0,
            total_credits=payment.credits_purchased,
            new_balance=current_user.credits,
            transaction_id=transaction.id if package else uuid.uuid4()
        )
        
    except PayplePaymentError as e:
        # 페이플 결제 오류 시 결제 상태를 실패로 변경
        payment.status = PaymentStatus.failed
        payment.failure_code = e.error_code
        payment.failure_message = str(e)
        db.commit()
        
        logger.error(f"Payple payment confirmation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment confirmation failed: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error confirming Payple payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to confirm payment"
        )


@router.post("/payple/webhook")
async def handle_payple_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    페이플 웹훅 처리
    - 결제 상태 변경 시 페이플에서 호출
    """
    try:
        # 요청 본문 읽기
        body = await request.body()
        webhook_data = json.loads(body.decode())
        
        logger.info(f"Received Payple webhook: {webhook_data.get('PCD_PAY_RST')}")
        
        # 백그라운드 태스크로 처리
        background_tasks.add_task(process_payple_webhook_event, webhook_data, db)
        
        return {"result": "success"}
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid Payple webhook JSON: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON"
        )
    except Exception as e:
        logger.error(f"Error handling Payple webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook processing failed"
        )


@router.post("/payple/cancel", response_model=PayplePaymentCancelResponse)
async def cancel_payple_payment(
    request: PayplePaymentCancelRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    페이플 결제 취소 및 크레딧 환불
    """
    try:
        # 결제 정보 조회
        payment = db.query(Payment).filter(
            Payment.order_id == request.order_id,
            Payment.user_id == current_user.id,
            Payment.status == PaymentStatus.completed
        ).first()
        
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Payment not found or cannot be cancelled"
            )
        
        # 페이플에 취소 요청
        payple_response = payple_payment_service.cancel_payment(
            order_id=request.order_id,
            cancel_reason=request.cancel_reason
        )
        
        # 크레딧 환불 처리
        refund_transaction = CreditService.add_credits(
            db=db,
            user=current_user,
            amount=-payment.credits_purchased,  # 음수로 차감
            transaction_type=TransactionType.refund,
            description=f"결제 취소 환불: {request.cancel_reason}",
            metadata_json={
                "payment_id": str(payment.id),
                "payple_order_id": request.order_id,
                "cancel_reason": request.cancel_reason
            }
        )
        
        # 결제 상태 변경
        payment.status = PaymentStatus.refunded
        
        db.commit()
        db.refresh(current_user)
        
        logger.info(f"Payple payment cancelled for user {current_user.id}: {request.order_id}")
        
        return PayplePaymentCancelResponse(
            success=True,
            cancel_amount=payment.amount,
            refund_amount=payment.credits_purchased,
            new_balance=current_user.credits,
            transaction_id=refund_transaction.id
        )
        
    except PayplePaymentError as e:
        logger.error(f"Payple payment cancellation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Payment cancellation failed: {str(e)}"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error cancelling Payple payment: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel payment"
        )


async def process_payple_webhook_event(webhook_data: Dict[str, Any], db: Session):
    """페이플 웹훅 이벤트 백그라운드 처리"""
    try:
        # 웹훅 이벤트 처리
        success = payple_payment_service.process_webhook(webhook_data)
        
        if success:
            logger.info(f"Payple webhook event processed successfully")
        else:
            logger.error(f"Failed to process Payple webhook event")
            
    except Exception as e:
        logger.error(f"Error in Payple webhook background task: {e}")