"""Add fortune tables

Revision ID: fortune_001
Revises: 
Create Date: 2025-12-16

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'fortune_001'
down_revision = None  # Replace with latest revision ID
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. users 테이블에 fortune 관련 컬럼 추가
    op.add_column('users', sa.Column('zodiac_sign', sa.String(10), nullable=True))
    op.add_column('users', sa.Column('fortune_enabled', sa.Boolean(), nullable=False, server_default='true'))

    # 2. daily_fortunes 테이블 생성
    op.create_table('daily_fortunes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('fortune_date', sa.Date(), nullable=False),
        sa.Column('overall_luck', sa.Integer(), nullable=False),
        sa.Column('wealth_luck', sa.Integer(), nullable=False),
        sa.Column('lottery_luck', sa.Integer(), nullable=False),
        sa.Column('lucky_numbers', postgresql.ARRAY(sa.Integer()), nullable=False),
        sa.Column('lucky_color', sa.String(20), nullable=True),
        sa.Column('lucky_direction', sa.String(10), nullable=True),
        sa.Column('fortune_message', sa.Text(), nullable=True),
        sa.Column('advice', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_daily_fortunes_id'), 'daily_fortunes', ['id'], unique=False)

    # 3. fortune_messages 테이블 생성
    op.create_table('fortune_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('luck_range', sa.String(20), nullable=False),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_fortune_messages_id'), 'fortune_messages', ['id'], unique=False)

    # 4. zodiac_daily_stats 테이블 생성
    op.create_table('zodiac_daily_stats',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('stats_date', sa.Date(), nullable=False),
        sa.Column('zodiac_sign', sa.String(10), nullable=False),
        sa.Column('avg_overall_luck', sa.DECIMAL(5, 2), nullable=True),
        sa.Column('avg_lottery_luck', sa.DECIMAL(5, 2), nullable=True),
        sa.Column('active_users', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('predictions_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), onupdate=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_zodiac_daily_stats_id'), 'zodiac_daily_stats', ['id'], unique=False)

    # 5. 샘플 운세 메시지 데이터 삽입
    fortune_messages_table = sa.table('fortune_messages',
        sa.column('luck_range', sa.String),
        sa.column('category', sa.String),
        sa.column('message', sa.Text)
    )
    
    op.bulk_insert(fortune_messages_table, [
        # High luck messages
        {'luck_range': 'high', 'category': 'general', 'message': '오늘은 특히 행운이 가득한 날입니다! ✨'},
        {'luck_range': 'high', 'category': 'general', 'message': '모든 일이 순조롭게 풀릴 것 같습니다! 🍀'},
        {'luck_range': 'high', 'category': 'timing', 'message': '오전 시간대가 특히 좋으니 중요한 일은 오전에 해보세요!'},
        {'luck_range': 'high', 'category': 'timing', 'message': '오늘 밤 늦은 시간이 행운의 시간입니다! 🌙'},
        
        # Medium luck messages
        {'luck_range': 'medium', 'category': 'general', 'message': '안정적인 하루가 될 것 같습니다.'},
        {'luck_range': 'medium', 'category': 'general', 'message': '꾸준함이 좋은 결과를 가져다줄 거예요.'},
        {'luck_range': 'medium', 'category': 'timing', 'message': '오후 시간대에 좋은 기회가 있을 것 같습니다.'},
        {'luck_range': 'medium', 'category': 'timing', 'message': '점심시간 전후가 좋은 타이밍이에요!'},
        
        # Low luck messages
        {'luck_range': 'low', 'category': 'general', 'message': '조금 더 신중하게 행동하세요.'},
        {'luck_range': 'low', 'category': 'general', 'message': '오늘은 휴식을 취하며 충전하는 날로 보내세요.'},
        {'luck_range': 'low', 'category': 'timing', 'message': '서두르지 말고 차근차근 진행하세요.'},
        {'luck_range': 'low', 'category': 'timing', 'message': '늦은 오후나 저녁 시간이 더 나을 것 같습니다.'},
    ])


def downgrade() -> None:
    # 테이블 삭제 (역순)
    op.drop_table('zodiac_daily_stats')
    op.drop_table('fortune_messages')
    op.drop_table('daily_fortunes')
    
    # users 테이블에서 컬럼 제거
    op.drop_column('users', 'fortune_enabled')
    op.drop_column('users', 'zodiac_sign')