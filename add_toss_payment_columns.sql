-- 토스 결제 연동을 위한 payments 테이블 컬럼 추가
-- 이 SQL을 데이터베이스에 직접 실행하세요

-- payments 테이블에 토스 관련 컬럼 추가
ALTER TABLE payments 
ADD COLUMN IF NOT EXISTS order_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS payment_key VARCHAR(255),
ADD COLUMN IF NOT EXISTS toss_order_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS failure_code VARCHAR(50),
ADD COLUMN IF NOT EXISTS failure_message TEXT;

-- 인덱스 추가 (성능 최적화)
CREATE INDEX IF NOT EXISTS idx_payments_order_id ON payments (order_id);
CREATE INDEX IF NOT EXISTS idx_payments_payment_key ON payments (payment_key);

-- 컬럼 추가 확인
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'payments' 
ORDER BY ordinal_position;