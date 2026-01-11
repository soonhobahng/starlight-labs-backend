from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid
from datetime import datetime, date
import math

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.models import User, CreditTransaction, TransactionType, UserTier
from app.schemas.credits import (
    CreditBalance, CreditTransactionHistory, CreditTransactionResponse,
    AdRewardRequest, AdRewardResponse, DailyBonusRequest, DailyBonusResponse,
    CreditPurchaseRequest, CreditPurchaseResponse, CreditRefundRequest, 
    CreditRefundResponse, CreditUsageRequest, CreditUsageResponse,
    CreditStatsResponse, DailyLimitsResponse, CreditPackageInfo,
    CreditPackagesResponse, TransferCreditsRequest, TransferCreditsResponse
)
from app.services.credit_service import (
    CreditService, CreditError, InsufficientCreditsError, CreditPackage
)

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("/balance", response_model=CreditBalance)
async def get_credit_balance(
    current_user: User = Depends(get_current_user)
):
    """현재 크레딧 잔액 조회"""

    return CreditBalance(
        current_balance=current_user.credits,
        tier=current_user.tier,
        unlimited=current_user.tier == UserTier.vip
    )


@router.get("/history", response_model=CreditTransactionHistory)
async def get_credit_history(
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    transaction_type: Optional[TransactionType] = Query(None, description="Filter by transaction type"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """크레딧 거래 내역 조회"""
    
    offset = (page - 1) * limit
    
    try:
        transactions = CreditService.get_transactions(
            db=db,
            user_id=str(current_user.id),
            limit=limit,
            offset=offset,
            transaction_type=transaction_type
        )
        
        # 총 개수 조회
        total_query = db.query(CreditTransaction).filter(
            CreditTransaction.user_id == current_user.id
        )
        if transaction_type:
            total_query = total_query.filter(CreditTransaction.type == transaction_type)
        
        total = total_query.count()
        total_pages = math.ceil(total / limit)
        
        transaction_responses = [
            CreditTransactionResponse(
                id=tx.id,
                type=tx.type,
                amount=tx.amount,
                balance_after=tx.balance_after,
                description=tx.description,
                metadata_json=tx.metadata_json,
                created_at=tx.created_at
            ) for tx in transactions
        ]
        
        return CreditTransactionHistory(
            total=total,
            transactions=transaction_responses,
            current_page=page,
            total_pages=total_pages
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve credit history: {str(e)}"
        )


@router.post("/daily-bonus", response_model=DailyBonusResponse)
async def claim_daily_bonus(
    request: DailyBonusRequest = DailyBonusRequest(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """일일 무료 크레딧 수령"""
    
    try:
        transaction = CreditService.give_daily_bonus(db, current_user)
        
        if transaction:
            # 다음 보너스 시간 계산 (다음날 00:00)
            tomorrow = datetime.utcnow().date() + datetime.timedelta(days=1)
            next_bonus = datetime.combine(tomorrow, datetime.min.time())
            
            return DailyBonusResponse(
                success=True,
                credits_earned=transaction.amount,
                new_balance=current_user.credits,
                transaction_id=transaction.id,
                next_bonus_available=next_bonus.isoformat()
            )
        else:
            # VIP 사용자 또는 이미 수령한 경우
            tomorrow = datetime.utcnow().date() + datetime.timedelta(days=1)
            next_bonus = datetime.combine(tomorrow, datetime.min.time())
            
            return DailyBonusResponse(
                success=False,
                credits_earned=0,
                new_balance=current_user.credits,
                next_bonus_available=next_bonus.isoformat()
            )
            
    except CreditError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to claim daily bonus: {str(e)}"
        )


@router.post("/ad-reward", response_model=AdRewardResponse)
async def claim_ad_reward(
    request: AdRewardRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """광고 시청 보상 수령"""
    
    try:
        transaction = CreditService.reward_ad_viewing(
            db=db,
            user=current_user,
            ad_id=request.ad_id
        )
        
        # 남은 일일 광고 시청 횟수 계산
        limits = CreditService.check_daily_limits(db, current_user)
        daily_remaining = limits["ad_rewards"]["remaining"]
        
        return AdRewardResponse(
            success=True,
            credits_earned=transaction.amount,
            new_balance=current_user.credits,
            transaction_id=transaction.id,
            daily_remaining=daily_remaining
        )
        
    except CreditError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to claim ad reward: {str(e)}"
        )


@router.get("/packages", response_model=CreditPackagesResponse)
async def get_credit_packages(
    current_user: User = Depends(get_current_user)
):
    """구매 가능한 크레딧 패키지 조회"""
    
    if current_user.tier == UserTier.vip:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="VIP users have unlimited credits"
        )
    
    packages = []
    for i, package in enumerate(CreditPackage.PACKAGES):
        total_credits = package["credits"] + package["bonus"]
        discount = 0
        if package["bonus"] > 0:
            discount = round((package["bonus"] / total_credits) * 100, 1)
        
        packages.append(CreditPackageInfo(
            id=package["id"],
            name=f'{package["credits"]} 크레딧{"" if package["bonus"] == 0 else f" (+{package['bonus']} 보너스)"}',
            credits=package["credits"],
            bonus_credits=package["bonus"],
            total_credits=total_credits,
            price=package["price"],
            discount_percentage=discount if discount > 0 else None,
            popular=(i == 2)  # 3번째 패키지를 인기상품으로 설정
        ))
    
    return CreditPackagesResponse(
        packages=packages,
        user_tier=current_user.tier,
        current_balance=current_user.credits
    )


@router.post("/purchase", response_model=CreditPurchaseResponse)
async def purchase_credits(
    request: CreditPurchaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """크레딧 구매"""
    
    try:
        # 패키지 정보 조회
        package = CreditPackage.get_package(request.package_id)
        if not package:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid package ID"
            )
        
        # 실제 결제 처리 (여기서는 Mock)
        payment_id = f"pay_{uuid.uuid4().hex[:12]}"
        
        # 결제 성공 후 크레딧 지급
        total_credits = package["credits"] + package["bonus"]
        transaction = CreditService.process_purchase(
            db=db,
            user=current_user,
            amount=total_credits,
            payment_id=payment_id,
            order_id=f"order_{uuid.uuid4().hex[:8]}"
        )
        
        # DB 커밋 후 최신 잔액 조회
        db.refresh(current_user)
        
        return CreditPurchaseResponse(
            success=True,
            package_id=package["id"],
            credits_purchased=package["credits"],
            bonus_credits=package["bonus"],
            total_credits=total_credits,
            amount_paid=package["price"],
            new_balance=current_user.credits,
            transaction_id=transaction.id,
            payment_id=payment_id
        )
        
    except CreditError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to purchase credits: {str(e)}"
        )


@router.post("/use", response_model=CreditUsageResponse)
async def use_credits(
    request: CreditUsageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """크레딧 사용 (내부 API용)"""
    
    try:
        transaction = CreditService.use_credits(
            db=db,
            user=current_user,
            amount=request.amount,
            description=request.description,
            metadata_json=request.metadata_json
        )
        
        return CreditUsageResponse(
            success=True,
            credits_used=request.amount if current_user.tier != UserTier.vip else 0,
            new_balance=current_user.credits,
            transaction_id=transaction.id,
            unlimited_tier=current_user.tier == UserTier.vip
        )
        
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e)
        )
    except CreditError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to use credits: {str(e)}"
        )


@router.post("/refund", response_model=CreditRefundResponse)
async def refund_credits(
    request: CreditRefundRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """크레딧 환불"""
    
    try:
        transaction = CreditService.process_refund(
            db=db,
            user=current_user,
            original_transaction_id=request.transaction_id,
            reason=request.reason
        )
        
        return CreditRefundResponse(
            success=True,
            refund_amount=transaction.amount,
            new_balance=current_user.credits,
            transaction_id=transaction.id,
            refund_reason=request.reason
        )
        
    except CreditError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process refund: {str(e)}"
        )


@router.get("/stats", response_model=CreditStatsResponse)
async def get_credit_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """크레딧 사용 통계"""
    
    try:
        stats = CreditService.get_credit_stats(db, str(current_user.id))
        
        return CreditStatsResponse(
            current_balance=current_user.credits,
            **stats
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve credit stats: {str(e)}"
        )


@router.get("/limits", response_model=DailyLimitsResponse)
async def get_daily_limits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """일일 한도 조회"""
    
    try:
        limits = CreditService.check_daily_limits(db, current_user)
        
        return DailyLimitsResponse(
            ad_rewards=limits["ad_rewards"],
            predictions=limits["predictions"],
            daily_bonus=limits["daily_bonus"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve daily limits: {str(e)}"
        )


@router.post("/transfer", response_model=TransferCreditsResponse)
async def transfer_credits(
    request: TransferCreditsRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """크레딧 선물하기 (다른 사용자에게 전송)"""
    
    try:
        # 받는 사람 찾기
        recipient = db.query(User).filter(User.email == request.recipient_email).first()
        if not recipient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Recipient user not found"
            )
        
        if recipient.id == current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot transfer credits to yourself"
            )
        
        # VIP는 크레딧 선물 불가
        if current_user.tier == UserTier.vip:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="VIP users cannot transfer credits"
            )
        
        # 전송 수수료 (10% 또는 최소 1크레딧)
        transfer_fee = max(1, int(request.amount * 0.1))
        total_cost = request.amount + transfer_fee
        
        # 크레딧 확인
        if not CreditService.check_credits(current_user, total_cost):
            raise InsufficientCreditsError(
                f"Insufficient credits. Required: {total_cost} (amount: {request.amount} + fee: {transfer_fee}), Available: {current_user.credits}"
            )
        
        # 발신자 크레딧 차감
        sender_transaction = CreditService.use_credits(
            db=db,
            user=current_user,
            amount=total_cost,
            description=f"크레딧 선물 to {request.recipient_email} (수수료 {transfer_fee} 포함)",
            metadata_json={
                "transfer_type": "sender",
                "recipient_email": request.recipient_email,
                "recipient_id": str(recipient.id),
                "transfer_amount": request.amount,
                "transfer_fee": transfer_fee,
                "message": request.message
            }
        )
        
        # 수신자 크레딧 추가
        CreditService.add_credits(
            db=db,
            user=recipient,
            amount=request.amount,
            transaction_type=TransactionType.referral,
            description=f"크레딧 선물 from {current_user.email}",
            metadata_json={
                "transfer_type": "recipient",
                "sender_email": current_user.email,
                "sender_id": str(current_user.id),
                "message": request.message,
                "sender_transaction_id": str(sender_transaction.id)
            }
        )
        
        return TransferCreditsResponse(
            success=True,
            amount_transferred=request.amount,
            recipient_email=request.recipient_email,
            new_balance=current_user.credits,
            transaction_id=sender_transaction.id,
            transfer_fee=transfer_fee
        )
        
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=str(e)
        )
    except CreditError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transfer credits: {str(e)}"
        )


@router.delete("/transaction/{transaction_id}")
async def cancel_transaction(
    transaction_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """거래 취소 (구매 후 일정 시간 내에만 가능)"""
    
    try:
        # 거래 조회
        transaction = db.query(CreditTransaction).filter(
            CreditTransaction.id == transaction_id,
            CreditTransaction.user_id == current_user.id,
            CreditTransaction.type == TransactionType.purchase
        ).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Transaction not found or not cancellable"
            )
        
        # 구매 후 1시간 이내에만 취소 가능
        if (datetime.utcnow() - transaction.created_at).total_seconds() > 3600:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction cancellation period has expired (1 hour limit)"
            )
        
        # 환불 처리
        refund_transaction = CreditService.process_refund(
            db=db,
            user=current_user,
            original_transaction_id=transaction_id,
            reason="구매 취소 (사용자 요청)"
        )
        
        return {
            "success": True,
            "message": "Transaction cancelled successfully",
            "refund_amount": refund_transaction.amount,
            "new_balance": current_user.credits
        }
        
    except CreditError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel transaction: {str(e)}"
        )