-- Fortune Messages 테이블에 is_active 컬럼이 없을 때 추가하는 스크립트
-- 실행 방법: psql $DATABASE_URL -f fix_fortune_messages.sql

BEGIN;

-- is_active 컬럼이 없으면 추가
DO $$ 
BEGIN 
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'fortune_messages' 
        AND column_name = 'is_active'
    ) THEN
        ALTER TABLE fortune_messages ADD COLUMN is_active BOOLEAN DEFAULT true;
        UPDATE fortune_messages SET is_active = true WHERE is_active IS NULL;
        RAISE NOTICE 'Added is_active column to fortune_messages table';
    ELSE
        RAISE NOTICE 'is_active column already exists in fortune_messages table';
    END IF;
END $$;

COMMIT;

-- 확인
SELECT column_name, data_type, is_nullable, column_default 
FROM information_schema.columns 
WHERE table_name = 'fortune_messages' 
ORDER BY ordinal_position;