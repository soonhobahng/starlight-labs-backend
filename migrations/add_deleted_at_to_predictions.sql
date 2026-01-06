-- Add deleted_at column to predictions table for soft delete functionality
-- This allows keeping prediction records for credit usage tracking even when "deleted"

ALTER TABLE predictions ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

-- Add index for better query performance on soft delete queries
CREATE INDEX idx_predictions_deleted_at ON predictions (deleted_at);

-- Add index for user_id + deleted_at combination for better performance
CREATE INDEX idx_predictions_user_id_deleted_at ON predictions (user_id, deleted_at);

COMMENT ON COLUMN predictions.deleted_at IS 'Timestamp when the prediction was soft deleted. NULL means not deleted.';