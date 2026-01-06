from sqlalchemy.orm import Session
from sqlalchemy import func, desc, and_
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta, date
import uuid

from app.models.models import User, CreditTransaction, TransactionType, UserTier
from app.core.database import get_db


class CreditError(Exception):
    """크레딧 관련 예외"""
    pass


class InsufficientCreditsError(CreditError):
    """크레딧 부족 예외"""
    pass


class CreditService:
    """크레딧 관리 서비스"""
    
    # 티어별 정책
    TIER_POLICIES = {
        UserTier.free: {
            "daily_free_credits": 3,
            "max_credits": 100,
            "can_purchase": True,
            "ad_reward_credits": 1,
            "max_ad_rewards_per_day": 3
        },
        UserTier.premium: {
            "daily_free_credits": 0,
            "max_credits": 1000,
            "can_purchase": True,
            "ad_reward_credits": 1,
            "max_ad_rewards_per_day": 3,
            "ad_reward_min_credits": 10  # 크레딧이 10개 이하일 때만 광고 보상 가능
        },
        UserTier.vip: {
            "daily_free_credits": 0,
            "max_credits": float('inf'),
            "unlimited": True,
            "can_purchase": False,
            "ad_reward_credits": 0,
            "max_ad_rewards_per_day": 0
        }
    }
    
    @staticmethod
    def check_credits(user: User, required: int) -> bool:
        """크레딧 충분한지 확인 (VIP는 항상 True)"""
        if user.tier == UserTier.vip:
            return True
        return user.credits >= required
    
    @staticmethod
    def use_credits(
        db: Session, 
        user: User, 
        amount: int, 
        description: str, 
        metadata_json: Dict[str, Any] = None
    ) -> CreditTransaction:
        """
        크레딧 사용
        1. users 테이블에서 credits 차감
        2. credit_transactions에 기록
        """
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        # VIP는 크레딧 차감하지 않음
        if user.tier == UserTier.vip:
            # VIP는 거래 기록만 남김 (amount=0)
            transaction = CreditTransaction(
                user_id=user.id,
                type=TransactionType.prediction,
                amount=0,
                balance_after=user.credits,
                description=f"VIP 무제한 사용: {description}",
                metadata_json=metadata_json or {}
            )
            db.add(transaction)
            db.commit()
            db.refresh(transaction)
            return transaction
        
        # 크레딧 확인
        if not CreditService.check_credits(user, amount):
            raise InsufficientCreditsError(
                f"Insufficient credits. Required: {amount}, Available: {user.credits}"
            )
        
        # 크레딧 차감
        user.credits -= amount
        
        # 거래 기록
        transaction = CreditTransaction(
            user_id=user.id,
            type=TransactionType.prediction,
            amount=-amount,
            balance_after=user.credits,
            description=description,
            metadata_json=metadata_json or {}
        )
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        return transaction
    
    @staticmethod
    def add_credits(
        db: Session, 
        user: User, 
        amount: int, 
        transaction_type: TransactionType, 
        description: str, 
        metadata_json: Dict[str, Any] = None
    ) -> CreditTransaction:
        """
        크레딧 추가/차감 (구매, 광고 보상, 추천, 환불 등)
        1. users 테이블에서 credits 증가/감소
        2. credit_transactions에 기록
        """
        # 환불 타입의 경우 음수 허용 (크레딧 차감)
        if transaction_type == TransactionType.refund:
            if amount >= 0:
                raise ValueError("Refund amount must be negative")
        else:
            if amount <= 0:
                raise ValueError("Amount must be positive")
        
        # VIP는 크레딧 추가 불필요 (무제한)
        if user.tier == UserTier.vip and transaction_type in [
            TransactionType.ad_reward, TransactionType.daily_bonus
        ]:
            return None
        
        # 최대 크레딧 한도 확인
        max_credits = CreditService.TIER_POLICIES[user.tier]["max_credits"]
        if user.credits + amount > max_credits:
            amount = max_credits - user.credits
            if amount <= 0:
                raise CreditError("Credit limit exceeded")
        
        # 크레딧 추가
        user.credits += amount
        
        # 거래 기록
        transaction = CreditTransaction(
            user_id=user.id,
            type=transaction_type,
            amount=amount,
            balance_after=user.credits,
            description=description,
            metadata_json=metadata_json or {}
        )
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        return transaction
    
    @staticmethod
    def get_balance(user: User) -> int:
        """현재 크레딧 잔액"""
        return user.credits
    
    @staticmethod
    def get_transactions(
        db: Session, 
        user_id: str, 
        limit: int = 20,
        offset: int = 0,
        transaction_type: Optional[TransactionType] = None
    ) -> List[CreditTransaction]:
        """크레딧 거래 내역 조회"""
        query = db.query(CreditTransaction).filter(CreditTransaction.user_id == user_id)
        
        if transaction_type:
            query = query.filter(CreditTransaction.type == transaction_type)
        
        transactions = query.order_by(desc(CreditTransaction.created_at))\
                          .offset(offset)\
                          .limit(limit)\
                          .all()
        
        return transactions
    
    @staticmethod
    def give_daily_bonus(db: Session, user: User) -> Optional[CreditTransaction]:
        """일일 무료 크레딧 지급"""
        if user.tier == UserTier.vip:
            return None  # VIP는 일일 보너스 불필요
        
        # 오늘 이미 받았는지 확인
        today = date.today()
        existing_bonus = db.query(CreditTransaction).filter(
            and_(
                CreditTransaction.user_id == user.id,
                CreditTransaction.type == TransactionType.daily_bonus,
                func.date(CreditTransaction.created_at) == today
            )
        ).first()
        
        if existing_bonus:
            raise CreditError("Daily bonus already claimed today")
        
        # 일일 보너스 지급
        daily_credits = CreditService.TIER_POLICIES[user.tier]["daily_free_credits"]
        if daily_credits > 0:
            return CreditService.add_credits(
                db=db,
                user=user,
                amount=daily_credits,
                transaction_type=TransactionType.daily_bonus,
                description=f"일일 무료 크레딧 {daily_credits}개",
                metadata_json={"bonus_date": today.isoformat()}
            )
        
        return None
    
    @staticmethod
    def reward_ad_viewing(db: Session, user: User, ad_id: str) -> CreditTransaction:
        """광고 시청 보상"""
        if user.tier == UserTier.vip:
            raise CreditError("VIP users don't need ad rewards")
        
        # Premium 사용자는 크레딧이 충분하면 광고 보상 불가
        policy = CreditService.TIER_POLICIES[user.tier]
        if user.tier == UserTier.premium:
            min_credits = policy.get("ad_reward_min_credits", 0)
            if user.credits > min_credits:
                raise CreditError(f"Premium users with more than {min_credits} credits don't need ad rewards")
        
        # 오늘 광고 시청 횟수 확인
        today = date.today()
        today_ad_count = db.query(func.count(CreditTransaction.id)).filter(
            and_(
                CreditTransaction.user_id == user.id,
                CreditTransaction.type == TransactionType.ad_reward,
                func.date(CreditTransaction.created_at) == today
            )
        ).scalar()
        
        max_ads = CreditService.TIER_POLICIES[user.tier]["max_ad_rewards_per_day"]
        if today_ad_count >= max_ads:
            raise CreditError(f"Daily ad viewing limit exceeded ({max_ads})")
        
        # 같은 광고 중복 시청 방지 (오늘)
        duplicate_ad = db.query(CreditTransaction).filter(
            and_(
                CreditTransaction.user_id == user.id,
                CreditTransaction.type == TransactionType.ad_reward,
                CreditTransaction.metadata_json['ad_id'].astext == ad_id,
                func.date(CreditTransaction.created_at) == today
            )
        ).first()
        
        if duplicate_ad:
            raise CreditError("This ad was already viewed today")
        
        # 광고 보상 지급
        reward_credits = CreditService.TIER_POLICIES[user.tier]["ad_reward_credits"]
        return CreditService.add_credits(
            db=db,
            user=user,
            amount=reward_credits,
            transaction_type=TransactionType.ad_reward,
            description=f"광고 시청 보상 {reward_credits}개",
            metadata_json={"ad_id": ad_id, "view_date": today.isoformat()}
        )
    
    @staticmethod
    def process_purchase(
        db: Session, 
        user: User, 
        amount: int, 
        payment_id: str,
        order_id: str = None
    ) -> CreditTransaction:
        """크레딧 구매 처리"""
        if user.tier == UserTier.vip:
            raise CreditError("VIP users have unlimited credits")
        
        if not CreditService.TIER_POLICIES[user.tier]["can_purchase"]:
            raise CreditError("Credit purchase not allowed for this tier")
        
        # Free 유저가 크레딧 구매 시 Premium으로 업그레이드
        if user.tier == UserTier.free:
            user.tier = UserTier.premium
            db.add(user)
        
        return CreditService.add_credits(
            db=db,
            user=user,
            amount=amount,
            transaction_type=TransactionType.purchase,
            description=f"크레딧 {amount}개 구매",
            metadata_json={
                "payment_id": payment_id,
                "order_id": order_id or str(uuid.uuid4()),
                "purchase_date": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def process_refund(
        db: Session, 
        user: User, 
        original_transaction_id: str, 
        reason: str
    ) -> CreditTransaction:
        """환불 처리"""
        # 원본 거래 조회
        original_transaction = db.query(CreditTransaction).filter(
            and_(
                CreditTransaction.id == original_transaction_id,
                CreditTransaction.user_id == user.id,
                CreditTransaction.amount < 0  # 사용 거래만 환불 가능
            )
        ).first()
        
        if not original_transaction:
            raise CreditError("Original transaction not found or not refundable")
        
        # 이미 환불된 거래인지 확인
        existing_refund = db.query(CreditTransaction).filter(
            and_(
                CreditTransaction.user_id == user.id,
                CreditTransaction.type == TransactionType.refund,
                CreditTransaction.metadata_json['original_transaction_id'].astext == original_transaction_id
            )
        ).first()
        
        if existing_refund:
            raise CreditError("Transaction already refunded")
        
        # 환불 금액 (원래 사용량의 절대값)
        refund_amount = abs(original_transaction.amount)
        
        return CreditService.add_credits(
            db=db,
            user=user,
            amount=refund_amount,
            transaction_type=TransactionType.refund,
            description=f"환불: {reason}",
            metadata_json={
                "original_transaction_id": original_transaction_id,
                "refund_reason": reason,
                "refund_date": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def get_credit_stats(db: Session, user_id: str) -> Dict[str, Any]:
        """사용자 크레딧 통계"""
        # 총 충전/사용 금액
        total_charged = db.query(func.sum(CreditTransaction.amount)).filter(
            and_(
                CreditTransaction.user_id == user_id,
                CreditTransaction.amount > 0
            )
        ).scalar() or 0
        
        total_used = db.query(func.sum(-CreditTransaction.amount)).filter(
            and_(
                CreditTransaction.user_id == user_id,
                CreditTransaction.amount < 0
            )
        ).scalar() or 0
        
        # 이번 달 사용량
        this_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        monthly_used = db.query(func.sum(-CreditTransaction.amount)).filter(
            and_(
                CreditTransaction.user_id == user_id,
                CreditTransaction.amount < 0,
                CreditTransaction.created_at >= this_month
            )
        ).scalar() or 0
        
        # 거래 유형별 통계
        type_stats = {}
        for transaction_type in TransactionType:
            count = db.query(func.count(CreditTransaction.id)).filter(
                and_(
                    CreditTransaction.user_id == user_id,
                    CreditTransaction.type == transaction_type
                )
            ).scalar()
            
            amount = db.query(func.sum(CreditTransaction.amount)).filter(
                and_(
                    CreditTransaction.user_id == user_id,
                    CreditTransaction.type == transaction_type
                )
            ).scalar() or 0
            
            type_stats[transaction_type.value] = {
                "count": count,
                "total_amount": amount
            }
        
        # 최근 거래
        recent_transactions = CreditService.get_transactions(db, user_id, limit=5)
        
        return {
            "total_charged": total_charged,
            "total_used": total_used,
            "monthly_used": monthly_used,
            "net_credits": total_charged - total_used,
            "transaction_count": len(recent_transactions),
            "type_statistics": type_stats,
            "recent_transactions": [
                {
                    "id": str(tx.id),
                    "type": tx.type.value,
                    "amount": tx.amount,
                    "description": tx.description,
                    "created_at": tx.created_at.isoformat()
                } for tx in recent_transactions
            ]
        }
    
    @staticmethod
    def check_daily_limits(db: Session, user: User) -> Dict[str, Any]:
        """일일 한도 확인"""
        today = date.today()
        
        # 오늘 광고 시청 횟수
        ad_count = db.query(func.count(CreditTransaction.id)).filter(
            and_(
                CreditTransaction.user_id == user.id,
                CreditTransaction.type == TransactionType.ad_reward,
                func.date(CreditTransaction.created_at) == today
            )
        ).scalar()
        
        # 오늘 예측 사용 횟수
        prediction_count = db.query(func.count(CreditTransaction.id)).filter(
            and_(
                CreditTransaction.user_id == user.id,
                CreditTransaction.type == TransactionType.prediction,
                func.date(CreditTransaction.created_at) == today
            )
        ).scalar()
        
        # 일일 보너스 수령 여부
        daily_bonus_received = db.query(CreditTransaction).filter(
            and_(
                CreditTransaction.user_id == user.id,
                CreditTransaction.type == TransactionType.daily_bonus,
                func.date(CreditTransaction.created_at) == today
            )
        ).first() is not None
        
        policy = CreditService.TIER_POLICIES[user.tier]
        
        # Premium 사용자 광고 한도 계산 (크레딧이 충분하면 0으로 제한)
        ad_limit = policy["max_ad_rewards_per_day"]
        if user.tier == UserTier.premium:
            min_credits = policy.get("ad_reward_min_credits", 0)
            if user.credits > min_credits:
                ad_limit = 0  # 크레딧이 충분하면 광고 불가
        
        return {
            "ad_rewards": {
                "used": ad_count,
                "limit": ad_limit,
                "remaining": max(0, ad_limit - ad_count),
                "blocked_reason": "Premium users with sufficient credits don't need ads" if user.tier == UserTier.premium and user.credits > policy.get("ad_reward_min_credits", 0) else None
            },
            "predictions": {
                "used": prediction_count,
                "unlimited": user.tier == UserTier.vip
            },
            "daily_bonus": {
                "received": daily_bonus_received,
                "available": policy["daily_free_credits"] > 0 and not daily_bonus_received
            }
        }
    
    @staticmethod
    def validate_transaction_metadata_json(
        transaction_type: TransactionType,
        metadata_json: Dict[str, Any]
    ) -> bool:
        """거래 메타데이터 유효성 검사"""
        required_fields = {
            TransactionType.prediction: ["strategy"],
            TransactionType.purchase: ["payment_id"],
            TransactionType.ad_reward: ["ad_id"],
            TransactionType.refund: ["original_transaction_id", "refund_reason"],
            TransactionType.referral: ["referred_user_id"],
        }
        
        if transaction_type in required_fields:
            for field in required_fields[transaction_type]:
                if field not in metadata_json:
                    return False
        
        return True


class CreditPackage:
    """크레딧 패키지 정의"""
    
    PACKAGES = [
        {"id": "basic_10", "credits": 10, "price": 1000, "bonus": 0},
        {"id": "standard_50", "credits": 50, "price": 4500, "bonus": 5},
        {"id": "premium_100", "credits": 100, "price": 8000, "bonus": 15},
        {"id": "deluxe_250", "credits": 250, "price": 18000, "bonus": 50},
        {"id": "ultimate_500", "credits": 500, "price": 30000, "bonus": 150},
    ]
    
    @staticmethod
    def get_package(package_id: str) -> Optional[Dict[str, Any]]:
        """패키지 정보 조회"""
        for package in CreditPackage.PACKAGES:
            if package["id"] == package_id:
                return package
        return None
    
    @staticmethod
    def calculate_total_credits(package_id: str) -> int:
        """보너스 포함 총 크레딧 계산"""
        package = CreditPackage.get_package(package_id)
        if package:
            return package["credits"] + package["bonus"]
        return 0
    
    @staticmethod
    def get_package_by_credits(total_credits: int) -> Optional[Dict[str, Any]]:
        """총 크레딧 수로 패키지 조회"""
        for package in CreditPackage.PACKAGES:
            package_total = package["credits"] + package["bonus"]
            if package_total == total_credits:
                # 패키지 정보에 총 크레딧과 이름 추가
                result = package.copy()
                result["total_credits"] = package_total
                result["name"] = f"크레딧 {package_total}개"
                return result
        return None
    
    @staticmethod
    def get_all_packages() -> List[Dict[str, Any]]:
        """모든 패키지 정보 조회 (with calculated fields)"""
        packages = []
        for package in CreditPackage.PACKAGES:
            result = package.copy()
            result["total_credits"] = package["credits"] + package["bonus"]
            result["name"] = f"크레딧 {result['total_credits']}개"
            packages.append(result)
        return packages