-- ============================================================================
-- LottoChat AI Database Initialization Script
-- PostgreSQL 15+
-- ============================================================================
-- 작성일: 2024-11-21
-- 버전: 1.0 FINAL
-- 설명: Notion 문서 기반 최종 확정 스키마
-- ============================================================================

-- 경고 메시지
DO $$
BEGIN
    RAISE NOTICE '⚠️  WARNING: This script will DROP ALL EXISTING TABLES!';
    RAISE NOTICE '⚠️  All data will be PERMANENTLY DELETED!';
    RAISE NOTICE '⚠️  Press Ctrl+C within 3 seconds to cancel...';
    PERFORM pg_sleep(3);
    RAISE NOTICE '✅ Starting database initialization...';
END $$;

-- ============================================================================
-- Step 1: 기존 테이블 삭제 (의존성 역순)
-- ============================================================================

DROP TABLE IF EXISTS chat_history CASCADE;
DROP TABLE IF EXISTS analysis_cache CASCADE;
DROP TABLE IF EXISTS success_stories CASCADE;
DROP TABLE IF EXISTS user_subscriptions CASCADE;
DROP TABLE IF EXISTS payments CASCADE;
DROP TABLE IF EXISTS credit_transactions CASCADE;
DROP TABLE IF EXISTS predictions CASCADE;
DROP TABLE IF EXISTS strategies CASCADE;
DROP TABLE IF EXISTS lotto_draws CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- ENUM 타입 삭제
DROP TYPE IF EXISTS transaction_type CASCADE;
DROP TYPE IF EXISTS payment_status CASCADE;

RAISE NOTICE '✅ Step 1/5: Dropped existing tables';

-- ============================================================================
-- Step 2: ENUM 타입 생성
-- ============================================================================

CREATE TYPE transaction_type AS ENUM (
    'purchase',
    'prediction',
    'ad_reward',
    'referral',
    'refund'
);

CREATE TYPE payment_status AS ENUM (
    'pending',
    'completed',
    'failed',
    'refunded'
);

RAISE NOTICE '✅ Step 2/5: Created ENUM types';

-- ============================================================================
-- Step 3: 테이블 생성 (의존성 순서)
-- ============================================================================

-- 1️⃣ users (소셜 로그인 사용자)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- 소셜 로그인 정보 (필수)
    provider VARCHAR(20) NOT NULL CHECK (provider IN ('kakao', 'naver', 'google')),
    provider_id VARCHAR(100) NOT NULL,
    
    -- 기본 정보
    nickname VARCHAR(50),
    email VARCHAR(255),
    phone VARCHAR(20),
    
    -- 성인 인증
    is_adult_verified BOOLEAN NOT NULL DEFAULT FALSE,
    birth_year INTEGER CHECK (birth_year IS NULL OR birth_year BETWEEN 1900 AND 2010),
    birth_date DATE,
    adult_verify_method VARCHAR(20), -- 'naver_birth', 'kakao_birth', 'kakao_age', 'phone'
    verified_at TIMESTAMP,
    
    -- 회원 등급
    tier VARCHAR(20) DEFAULT 'free' CHECK (tier IN ('free', 'premium', 'vip')),
    credits INTEGER DEFAULT 3 CHECK (credits >= 0),
    
    -- VIP 전용
    ai_chat_count INTEGER DEFAULT 0,
    monthly_ai_tokens_used INTEGER DEFAULT 0,
    
    -- 동의
    terms_agreed_at TIMESTAMP NOT NULL,
    privacy_agreed_at TIMESTAMP NOT NULL,
    marketing_agreed BOOLEAN DEFAULT FALSE,
    
    -- 상태
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'dormant', 'withdrawn')),
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 유니크 제약조건
    CONSTRAINT uq_provider_user UNIQUE (provider, provider_id)
);

CREATE INDEX idx_users_provider_id ON users(provider, provider_id);
CREATE INDEX idx_users_email ON users(email) WHERE email IS NOT NULL;
CREATE INDEX idx_users_tier ON users(tier);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_adult_verified ON users(is_adult_verified);

COMMENT ON TABLE users IS '사용자 계정 및 인증 정보';

-- 2️⃣ lotto_draws (로또 당첨번호)
CREATE TABLE lotto_draws (
    round INTEGER PRIMARY KEY,
    draw_date DATE NOT NULL UNIQUE,

    -- 당첨 번호
    num1 INTEGER NOT NULL CHECK (num1 BETWEEN 1 AND 45),
    num2 INTEGER NOT NULL CHECK (num2 BETWEEN 1 AND 45),
    num3 INTEGER NOT NULL CHECK (num3 BETWEEN 1 AND 45),
    num4 INTEGER NOT NULL CHECK (num4 BETWEEN 1 AND 45),
    num5 INTEGER NOT NULL CHECK (num5 BETWEEN 1 AND 45),
    num6 INTEGER NOT NULL CHECK (num6 BETWEEN 1 AND 45),
    bonus INTEGER NOT NULL CHECK (bonus BETWEEN 1 AND 45),

    -- 당첨 정보
    jackpot_winners INTEGER DEFAULT 0,
    jackpot_amount BIGINT DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT lotto_numbers_sorted CHECK (
        num1 < num2 AND num2 < num3 AND
        num3 < num4 AND num4 < num5 AND num5 < num6
    ),
    CONSTRAINT bonus_unique CHECK (
        bonus NOT IN (num1, num2, num3, num4, num5, num6)
    )
);

CREATE INDEX idx_lotto_draws_date ON lotto_draws(draw_date DESC);
CREATE INDEX idx_lotto_draws_round ON lotto_draws(round DESC);

COMMENT ON TABLE lotto_draws IS '로또 회차별 당첨번호 및 상금 정보';

-- 3️⃣ strategies (예측 전략)
CREATE TABLE strategies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(20),

    -- 통계 정보
    total_predictions INTEGER DEFAULT 0,
    total_wins INTEGER DEFAULT 0,
    win_rate FLOAT DEFAULT 0.0,
    avg_matched FLOAT DEFAULT 0.0,
    best_rank INTEGER,

    is_active BOOLEAN DEFAULT TRUE,
    requires_vip BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE strategies IS '10가지 예측 전략 정보 및 통계';

-- 4️⃣ predictions (예측 기록)
CREATE TABLE predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    -- 예측 정보
    draw_number INTEGER NOT NULL,
    strategy_id INTEGER REFERENCES strategies(id),
    strategy_name VARCHAR(50) NOT NULL,
    prediction_type VARCHAR(20) DEFAULT 'standard',

    -- 예측 번호
    num1 INTEGER CHECK (num1 BETWEEN 1 AND 45),
    num2 INTEGER CHECK (num2 BETWEEN 1 AND 45),
    num3 INTEGER CHECK (num3 BETWEEN 1 AND 45),
    num4 INTEGER CHECK (num4 BETWEEN 1 AND 45),
    num5 INTEGER CHECK (num5 BETWEEN 1 AND 45),
    num6 INTEGER CHECK (num6 BETWEEN 1 AND 45),

    -- 분석 결과
    confidence_score FLOAT CHECK (confidence_score BETWEEN 0 AND 1),

    -- 당첨 결과
    matched_count INTEGER CHECK (matched_count BETWEEN 0 AND 6),
    prize_rank INTEGER CHECK (prize_rank BETWEEN 1 AND 5),
    is_winner BOOLEAN DEFAULT FALSE,
    prize_amount BIGINT DEFAULT 0,

    -- 타임스탬프
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checked_at TIMESTAMP,

    CONSTRAINT predictions_numbers_sorted CHECK (
        num1 < num2 AND num2 < num3 AND
        num3 < num4 AND num4 < num5 AND num5 < num6
    )
);

CREATE INDEX idx_predictions_user ON predictions(user_id, created_at DESC);
CREATE INDEX idx_predictions_draw ON predictions(draw_number);
CREATE INDEX idx_predictions_strategy ON predictions(strategy_name);
CREATE INDEX idx_predictions_winner ON predictions(is_winner) WHERE is_winner = TRUE;

COMMENT ON TABLE predictions IS '사용자별 번호 예측 기록 및 결과';

-- 5️⃣ credit_transactions (크레딧 거래)
CREATE TABLE credit_transactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    type transaction_type NOT NULL,
    amount INTEGER NOT NULL,
    balance_after INTEGER NOT NULL,
    description TEXT,
    metadata JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT transactions_amount_check CHECK (
        (type IN ('purchase', 'ad_reward', 'referral') AND amount > 0) OR
        (type = 'prediction' AND amount < 0) OR
        (type = 'refund')
    )
);

CREATE INDEX idx_transactions_user ON credit_transactions(user_id, created_at DESC);
CREATE INDEX idx_transactions_type ON credit_transactions(type);

COMMENT ON TABLE credit_transactions IS '크레딧 충전/사용/환불 거래 내역';

-- 6️⃣ payments (결제 기록)
CREATE TABLE payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    payment_type VARCHAR(30) NOT NULL,
    amount INTEGER NOT NULL,
    credits_purchased INTEGER,

    payment_method VARCHAR(30),
    transaction_id VARCHAR(255),

    status payment_status DEFAULT 'pending',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,

    CONSTRAINT payments_amount_check CHECK (amount > 0)
);

CREATE INDEX idx_payments_user ON payments(user_id, created_at DESC);
CREATE INDEX idx_payments_status ON payments(status);
CREATE INDEX idx_payments_transaction ON payments(transaction_id);

COMMENT ON TABLE payments IS '결제 거래 기록 (Toss, Kakao Pay 등)';

-- 7️⃣ user_subscriptions (구독 정보)
CREATE TABLE user_subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    tier VARCHAR(20) NOT NULL CHECK (tier IN ('premium', 'vip')),

    started_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    auto_renewal BOOLEAN DEFAULT FALSE,

    payment_id UUID REFERENCES payments(id),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    cancelled_at TIMESTAMP,

    CONSTRAINT subscription_dates_check CHECK (expires_at > started_at)
);

CREATE INDEX idx_subscriptions_user ON user_subscriptions(user_id);
CREATE INDEX idx_subscriptions_active ON user_subscriptions(is_active) WHERE is_active = TRUE;
CREATE INDEX idx_subscriptions_expires ON user_subscriptions(expires_at);

COMMENT ON TABLE user_subscriptions IS 'Premium/VIP 구독 정보';

-- 8️⃣ success_stories (성공 사례)
CREATE TABLE success_stories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prediction_id UUID NOT NULL REFERENCES predictions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    matched_numbers INTEGER NOT NULL CHECK (matched_numbers BETWEEN 3 AND 6),
    prize_rank INTEGER NOT NULL CHECK (prize_rank BETWEEN 1 AND 5),
    prize_amount BIGINT NOT NULL,

    is_anonymous BOOLEAN DEFAULT TRUE,
    is_public BOOLEAN DEFAULT FALSE,
    testimonial TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_success_stories_public ON success_stories(is_public) WHERE is_public = TRUE;
CREATE INDEX idx_success_stories_rank ON success_stories(prize_rank);

COMMENT ON TABLE success_stories IS '당첨 성공 사례 (마케팅용)';

-- 9️⃣ chat_history (AI 채팅 기록)
CREATE TABLE chat_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    session_id UUID NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,

    tokens_used INTEGER DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_chat_history_session ON chat_history(session_id, created_at);
CREATE INDEX idx_chat_history_user ON chat_history(user_id, created_at DESC);

COMMENT ON TABLE chat_history IS 'VIP 사용자 AI 채팅 대화 기록';

-- 🔟 analysis_cache (분석 결과 캐싱)
CREATE TABLE analysis_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    cache_key VARCHAR(255) UNIQUE NOT NULL,
    analysis_type VARCHAR(50) NOT NULL,

    data JSONB NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_cache_key ON analysis_cache(cache_key);
CREATE INDEX idx_cache_expires ON analysis_cache(expires_at);

COMMENT ON TABLE analysis_cache IS '통계 분석 결과 캐시 (성능 최적화)';

RAISE NOTICE '✅ Step 3/5: Created all tables';

-- ============================================================================
-- Step 4: 초기 데이터 삽입
-- ============================================================================

-- 10가지 예측 전략
INSERT INTO strategies (name, display_name, description, category, requires_vip) VALUES
('frequency_balance', '📊 빈도 균형', '자주 나온 번호와 안 나온 번호를 균형있게 조합', 'statistical', FALSE),
('random', '🎲 무작위 생성', '완전한 랜덤 번호 생성', 'statistical', FALSE),
('zone_distribution', '📍 구간 분산', '5개 구간에서 균등하게 선택', 'statistical', FALSE),
('pattern_similarity', '🔍 패턴 유사도', '최근 회차 패턴 분석', 'statistical', FALSE),
('machine_learning', '🤖 머신러닝', 'Random Forest 모델 예측', 'ml', FALSE),
('consecutive_absence', '⏱️ 연속 미출현', '오랫동안 안 나온 번호 중심', 'statistical', FALSE),
('winner_pattern', '🏆 당첨자 패턴', '1등 당첨 번호 패턴 분석', 'statistical', FALSE),
('golden_ratio', '✨ 황금 비율', '피보나치 수열 활용', 'statistical', FALSE),
('sum_range', '💰 합계 범위', '100-150 범위 최적화', 'statistical', FALSE),
('ai_custom', '🧠 AI 맞춤형', 'Claude AI 대화형 추천', 'hybrid', TRUE);

RAISE NOTICE '✅ Step 4/5: Inserted initial data (10 strategies)';

-- ============================================================================
-- Step 5: 트리거 및 함수 생성
-- ============================================================================

-- updated_at 자동 업데이트
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_strategies_updated_at
    BEFORE UPDATE ON strategies
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 전략 통계 자동 업데이트
CREATE OR REPLACE FUNCTION update_strategy_stats()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE strategies
    SET
        total_predictions = (
            SELECT COUNT(*)
            FROM predictions
            WHERE strategy_name = NEW.strategy_name
        ),
        total_wins = (
            SELECT COUNT(*)
            FROM predictions
            WHERE strategy_name = NEW.strategy_name AND is_winner = TRUE
        ),
        avg_matched = (
            SELECT COALESCE(AVG(matched_count), 0)
            FROM predictions
            WHERE strategy_name = NEW.strategy_name
        ),
        best_rank = (
            SELECT MIN(prize_rank)
            FROM predictions
            WHERE strategy_name = NEW.strategy_name AND is_winner = TRUE
        )
    WHERE name = NEW.strategy_name;

    -- win_rate 계산
    UPDATE strategies
    SET win_rate = CASE
        WHEN total_predictions > 0 THEN total_wins::FLOAT / total_predictions
        ELSE 0.0
    END
    WHERE name = NEW.strategy_name;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_strategy_stats
    AFTER INSERT OR UPDATE ON predictions
    FOR EACH ROW
    EXECUTE FUNCTION update_strategy_stats();

-- 만료된 캐시 자동 삭제
CREATE OR REPLACE FUNCTION delete_expired_cache()
RETURNS TRIGGER AS $$
BEGIN
    DELETE FROM analysis_cache WHERE expires_at < NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_delete_expired_cache
    AFTER INSERT ON analysis_cache
    EXECUTE FUNCTION delete_expired_cache();

RAISE NOTICE '✅ Step 5/5: Created triggers and functions';

-- ============================================================================
-- 완료 메시지 및 통계
-- ============================================================================

DO $$
DECLARE
    table_count INTEGER;
    index_count INTEGER;
    trigger_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO table_count
    FROM information_schema.tables
    WHERE table_schema = 'public' AND table_type = 'BASE TABLE';

    SELECT COUNT(*) INTO index_count
    FROM pg_indexes
    WHERE schemaname = 'public';

    SELECT COUNT(*) INTO trigger_count
    FROM information_schema.triggers
    WHERE trigger_schema = 'public';

    RAISE NOTICE '';
    RAISE NOTICE '=========================================';
    RAISE NOTICE '✅ Database initialization completed!';
    RAISE NOTICE '=========================================';
    RAISE NOTICE 'Tables created: %', table_count;
    RAISE NOTICE 'Indexes created: %', index_count;
    RAISE NOTICE 'Triggers created: %', trigger_count;
    RAISE NOTICE '';
    RAISE NOTICE '📊 Ready to use!';
    RAISE NOTICE '=========================================';
END $$;