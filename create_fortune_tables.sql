-- Fortune System Database Migration
-- 실행 방법: psql $DATABASE_URL -f create_fortune_tables.sql

BEGIN;

-- 1. users 테이블에 fortune 관련 컬럼 추가 (이미 있으면 무시)
DO $$ 
BEGIN 
    BEGIN
        ALTER TABLE users ADD COLUMN zodiac_sign VARCHAR(10);
    EXCEPTION
        WHEN duplicate_column THEN RAISE NOTICE 'column zodiac_sign already exists in users.';
    END;
    
    BEGIN
        ALTER TABLE users ADD COLUMN fortune_enabled BOOLEAN NOT NULL DEFAULT true;
    EXCEPTION
        WHEN duplicate_column THEN RAISE NOTICE 'column fortune_enabled already exists in users.';
    END;
END $$;

-- 2. daily_fortunes 테이블 생성
CREATE TABLE IF NOT EXISTS daily_fortunes (
    id SERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fortune_date DATE NOT NULL,
    overall_luck INTEGER NOT NULL,
    wealth_luck INTEGER NOT NULL,
    lottery_luck INTEGER NOT NULL,
    lucky_numbers INTEGER[] NOT NULL,
    lucky_color VARCHAR(20),
    lucky_direction VARCHAR(10),
    fortune_message TEXT,
    advice TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, fortune_date)
);

-- 3. fortune_messages 테이블 생성
CREATE TABLE IF NOT EXISTS fortune_messages (
    id SERIAL PRIMARY KEY,
    luck_range VARCHAR(20) NOT NULL,
    category VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. zodiac_daily_stats 테이블 생성
CREATE TABLE IF NOT EXISTS zodiac_daily_stats (
    id SERIAL PRIMARY KEY,
    stats_date DATE NOT NULL,
    zodiac_sign VARCHAR(10) NOT NULL,
    avg_overall_luck DECIMAL(5,2),
    avg_lottery_luck DECIMAL(5,2),
    active_users INTEGER DEFAULT 0,
    predictions_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(stats_date, zodiac_sign)
);

-- 5. 샘플 운세 메시지 데이터 삽입
INSERT INTO fortune_messages (luck_range, category, message) VALUES
-- High luck messages
('high', 'general', '오늘은 특히 행운이 가득한 날입니다! ✨'),
('high', 'general', '모든 일이 순조롭게 풀릴 것 같습니다! 🍀'),
('high', 'general', '놀라운 행운이 당신을 기다리고 있어요! 🌟'),
('high', 'timing', '오전 시간대가 특히 좋으니 중요한 일은 오전에 해보세요!'),
('high', 'timing', '오늘 밤 늦은 시간이 행운의 시간입니다! 🌙'),

-- Medium luck messages  
('medium', 'general', '안정적인 하루가 될 것 같습니다.'),
('medium', 'general', '꾸준함이 좋은 결과를 가져다줄 거예요.'),
('medium', 'general', '평범하지만 소소한 기쁨이 있는 하루입니다.'),
('medium', 'timing', '오후 시간대에 좋은 기회가 있을 것 같습니다.'),
('medium', 'timing', '점심시간 전후가 좋은 타이밍이에요!'),

-- Low luck messages
('low', 'general', '조금 더 신중하게 행동하세요.'),
('low', 'general', '오늘은 휴식을 취하며 충전하는 날로 보내세요.'),
('low', 'general', '차분하게 하루를 보내는 것이 좋겠습니다.'),
('low', 'timing', '서두르지 말고 차근차근 진행하세요.'),
('low', 'timing', '늦은 오후나 저녁 시간이 더 나을 것 같습니다.')

ON CONFLICT DO NOTHING;

-- 6. 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_daily_fortunes_user_date ON daily_fortunes(user_id, fortune_date);
CREATE INDEX IF NOT EXISTS idx_zodiac_daily_stats_date ON zodiac_daily_stats(stats_date);
CREATE INDEX IF NOT EXISTS idx_fortune_messages_range_category ON fortune_messages(luck_range, category);

-- 트리거 생성 (updated_at 자동 업데이트)
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_zodiac_daily_stats_updated_at 
    BEFORE UPDATE ON zodiac_daily_stats 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

COMMIT;

-- 확인 쿼리
SELECT 'Fortune tables created successfully!' as result;
SELECT table_name FROM information_schema.tables 
WHERE table_name IN ('daily_fortunes', 'fortune_messages', 'zodiac_daily_stats')
AND table_schema = 'public';

SELECT COUNT(*) as sample_messages_count FROM fortune_messages;