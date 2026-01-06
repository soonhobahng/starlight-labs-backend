import uuid
import enum
from datetime import datetime, date
from sqlalchemy import Column, String, Integer, DateTime, Date, Float, Boolean, ForeignKey, BigInteger, CheckConstraint, Enum, Text, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class UserTier(str, enum.Enum):
    free = "free"
    premium = "premium"
    vip = "vip"


class TransactionType(str, enum.Enum):
    purchase = "purchase"
    prediction = "prediction"
    ad_reward = "ad_reward"
    referral = "referral"
    refund = "refund"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"


class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    # 소셜 로그인 정보
    provider = Column(String(20), nullable=False)  # 'kakao', 'naver', 'google'
    provider_id = Column(String(100), nullable=False)
    
    # 기본 정보
    nickname = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)  # 본인인증 시
    
    # 성인 인증
    is_adult_verified = Column(Boolean, default=False, nullable=False)
    birth_year = Column(Integer, nullable=True)
    birth_date = Column(Date, nullable=True)  # 네이버는 월일도 제공
    adult_verify_method = Column(String(20), nullable=True)  # 'naver_birth', 'kakao_birth', 'kakao_age', 'phone'
    verified_at = Column(DateTime, nullable=True)
    
    # 회원 등급
    tier = Column(String(20), default='free', nullable=False)  # 'free', 'premium', 'vip'
    credits = Column(Integer, default=3, nullable=False)
    
    # 사용자 역할
    role = Column(String(20), default='user', nullable=False)  # 'user', 'admin'
    
    # 프로필 이미지
    profile_image_url = Column(String(500), nullable=True)  # SNS에서 가져온 프로필 이미지 URL
    
    # VIP 전용
    ai_chat_count = Column(Integer, default=0, nullable=False)
    monthly_ai_tokens_used = Column(Integer, default=0, nullable=False)
    
    # 운세 관련
    zodiac_sign = Column(String(10), nullable=True)  # 12띠 (예: "용띠")
    fortune_enabled = Column(Boolean, default=True, nullable=False)  # 운세 기능 활성화
    
    # 동의
    terms_agreed_at = Column(DateTime, nullable=False)
    privacy_agreed_at = Column(DateTime, nullable=False)
    marketing_agreed = Column(Boolean, default=False, nullable=False)
    
    # 상태
    status = Column(String(20), default='active', nullable=False)  # 'active', 'dormant', 'withdrawn'
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # 제약조건
    __table_args__ = (
        CheckConstraint("provider IN ('kakao', 'naver', 'google')", name='users_provider_check'),
        CheckConstraint("tier IN ('free', 'premium', 'vip')", name='users_tier_check'),
        CheckConstraint("role IN ('user', 'admin')", name='users_role_check'),
        CheckConstraint("credits >= 0", name='users_credits_check'),
        CheckConstraint("status IN ('active', 'dormant', 'withdrawn')", name='users_status_check'),
        CheckConstraint("nickname IS NULL OR length(nickname) BETWEEN 2 AND 50", name='users_nickname_length_check'),
        CheckConstraint("birth_year IS NULL OR birth_year BETWEEN 1900 AND 2010", name='users_birth_year_check'),
        UniqueConstraint('provider', 'provider_id', name='uq_provider_user'),
    )
    
    predictions = relationship("Prediction", back_populates="user")
    credit_transactions = relationship("CreditTransaction", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    subscriptions = relationship("UserSubscription", back_populates="user")
    chat_history = relationship("ChatHistory", back_populates="user")
    success_stories = relationship("SuccessStory", back_populates="user")


class LottoDraw(Base):
    __tablename__ = "lotto_draws"
    
    round = Column(Integer, primary_key=True)
    draw_date = Column(Date, unique=True, nullable=False, index=True)
    
    # 당첨 번호
    num1 = Column(Integer, nullable=False)
    num2 = Column(Integer, nullable=False)
    num3 = Column(Integer, nullable=False)
    num4 = Column(Integer, nullable=False)
    num5 = Column(Integer, nullable=False)
    num6 = Column(Integer, nullable=False)
    bonus = Column(Integer, nullable=False)
    
    # 당첨 정보
    jackpot_winners = Column(Integer, default=0, nullable=False)
    jackpot_amount = Column(BigInteger, default=0, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint('num1 BETWEEN 1 AND 45', name='check_num1_range'),
        CheckConstraint('num2 BETWEEN 1 AND 45', name='check_num2_range'),
        CheckConstraint('num3 BETWEEN 1 AND 45', name='check_num3_range'),
        CheckConstraint('num4 BETWEEN 1 AND 45', name='check_num4_range'),
        CheckConstraint('num5 BETWEEN 1 AND 45', name='check_num5_range'),
        CheckConstraint('num6 BETWEEN 1 AND 45', name='check_num6_range'),
        CheckConstraint('bonus BETWEEN 1 AND 45', name='check_bonus_range'),
        CheckConstraint('num1 < num2 AND num2 < num3 AND num3 < num4 AND num4 < num5 AND num5 < num6', name='lotto_numbers_sorted'),
        CheckConstraint('bonus NOT IN (num1, num2, num3, num4, num5, num6)', name='bonus_unique'),
    )


class Prediction(Base):
    __tablename__ = "predictions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # 예측 정보
    draw_number = Column(Integer, nullable=False)
    strategy_id = Column(Integer, ForeignKey("strategies.id"), nullable=True)
    strategy_name = Column(String(50), nullable=False)
    prediction_type = Column(String(20), default="standard", nullable=False)
    
    # 예측 번호
    num1 = Column(Integer, nullable=True)
    num2 = Column(Integer, nullable=True)
    num3 = Column(Integer, nullable=True)
    num4 = Column(Integer, nullable=True)
    num5 = Column(Integer, nullable=True)
    num6 = Column(Integer, nullable=True)
    
    # 분석 결과
    confidence_score = Column(Float, nullable=True)
    
    # 당첨 결과
    matched_count = Column(Integer, default=0, nullable=False)
    prize_rank = Column(Integer, nullable=True)
    is_winner = Column(Boolean, default=False, nullable=False)
    prize_amount = Column(BigInteger, default=0, nullable=False)
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    checked_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True)  # soft delete
    
    user = relationship("User", back_populates="predictions")
    strategy = relationship("Strategy", back_populates="predictions")
    success_stories = relationship("SuccessStory", back_populates="prediction")
    
    __table_args__ = (
        CheckConstraint('num1 BETWEEN 1 AND 45', name='pred_check_num1_range'),
        CheckConstraint('num2 BETWEEN 1 AND 45', name='pred_check_num2_range'),
        CheckConstraint('num3 BETWEEN 1 AND 45', name='pred_check_num3_range'),
        CheckConstraint('num4 BETWEEN 1 AND 45', name='pred_check_num4_range'),
        CheckConstraint('num5 BETWEEN 1 AND 45', name='pred_check_num5_range'),
        CheckConstraint('num6 BETWEEN 1 AND 45', name='pred_check_num6_range'),
        CheckConstraint('num1 < num2 AND num2 < num3 AND num3 < num4 AND num4 < num5 AND num5 < num6', name='predictions_numbers_sorted'),
        CheckConstraint('confidence_score BETWEEN 0 AND 1', name='check_confidence_range'),
        CheckConstraint('matched_count BETWEEN 0 AND 6', name='check_matched_count_range'),
        CheckConstraint('prize_rank BETWEEN 1 AND 5', name='check_prize_rank_range'),
    )


class Strategy(Base):
    __tablename__ = "strategies"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(20), nullable=True)
    
    # 통계 정보
    total_predictions = Column(Integer, default=0, nullable=False)
    total_wins = Column(Integer, default=0, nullable=False)
    win_rate = Column(Float, default=0.0, nullable=False)
    avg_matched = Column(Float, default=0.0, nullable=False)
    best_rank = Column(Integer, nullable=True)
    
    is_active = Column(Boolean, default=True, nullable=False)
    requires_vip = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    predictions = relationship("Prediction", back_populates="strategy")


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Integer, nullable=False)  # 양수: 충전, 음수: 사용
    balance_after = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)  # {"prediction_id": "...", "strategy": "...", "order_id": "..."}
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint(
            "(type IN ('purchase', 'ad_reward', 'referral') AND amount > 0) OR "
            "(type = 'prediction' AND amount < 0) OR "
            "(type = 'refund')", 
            name='transactions_amount_check'
        ),
    )
    
    user = relationship("User", back_populates="credit_transactions")


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    payment_type = Column(String(30), nullable=False)
    amount = Column(Integer, nullable=False)
    credits_purchased = Column(Integer, nullable=True)
    
    payment_method = Column(String(30), nullable=True)
    transaction_id = Column(String(255), nullable=True)
    
    # Toss Payments 관련 필드
    order_id = Column(String(100), nullable=True)  # 주문 ID
    payment_key = Column(String(255), nullable=True)  # 토스 결제 키
    toss_order_id = Column(String(100), nullable=True)  # 토스 주문 ID
    failure_code = Column(String(50), nullable=True)  # 실패 코드
    failure_message = Column(Text, nullable=True)  # 실패 메시지
    
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        CheckConstraint('amount > 0', name='payments_amount_check'),
    )
    
    user = relationship("User", back_populates="payments")
    subscriptions = relationship("UserSubscription", back_populates="payment")


class UserSubscription(Base):
    __tablename__ = "user_subscriptions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    tier = Column(String(20), nullable=False)
    
    started_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    auto_renewal = Column(Boolean, default=False, nullable=False)
    
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    cancelled_at = Column(DateTime, nullable=True)
    
    __table_args__ = (
        CheckConstraint("tier IN ('premium', 'vip')", name='subscription_tier_check'),
        CheckConstraint('expires_at > started_at', name='subscription_dates_check'),
    )
    
    user = relationship("User", back_populates="subscriptions")
    payment = relationship("Payment", back_populates="subscriptions")


class SuccessStory(Base):
    __tablename__ = "success_stories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prediction_id = Column(UUID(as_uuid=True), ForeignKey("predictions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    matched_numbers = Column(Integer, nullable=False)
    prize_rank = Column(Integer, nullable=False)
    prize_amount = Column(BigInteger, nullable=False)
    
    is_anonymous = Column(Boolean, default=True, nullable=False)
    is_public = Column(Boolean, default=False, nullable=False)
    testimonial = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint('matched_numbers BETWEEN 3 AND 6', name='success_matched_numbers_check'),
        CheckConstraint('prize_rank BETWEEN 1 AND 5', name='success_prize_rank_check'),
    )
    
    prediction = relationship("Prediction", back_populates="success_stories")
    user = relationship("User", back_populates="success_stories")


class ChatHistory(Base):
    __tablename__ = "chat_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    session_id = Column(UUID(as_uuid=True), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    
    tokens_used = Column(Integer, default=0, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name='chat_role_check'),
    )
    
    user = relationship("User", back_populates="chat_history")


class AnalysisCache(Base):
    __tablename__ = "analysis_cache"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    cache_key = Column(String(255), unique=True, nullable=False, index=True)
    analysis_type = Column(String(50), nullable=False)
    
    data = Column(JSON, nullable=False)  # JSONB in PostgreSQL
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)