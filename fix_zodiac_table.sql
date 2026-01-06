-- Fix zodiac_daily_stats table by adding missing updated_at column
-- Run this script to add the missing column

-- Add updated_at column to zodiac_daily_stats table
ALTER TABLE zodiac_daily_stats 
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE;

-- Set default value for existing rows
UPDATE zodiac_daily_stats 
SET updated_at = created_at 
WHERE updated_at IS NULL;

-- Verify the table structure
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'zodiac_daily_stats' 
ORDER BY ordinal_position;