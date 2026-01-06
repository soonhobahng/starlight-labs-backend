# app/tasks/zodiac_stats_aggregator.py

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

from app.models.fortune import DailyFortune, ZodiacDailyStat
from app.models.models import User
from app.services.zodiac_service import ZodiacService
from app.core.database import SessionLocal
import logging

# Logger 설정
logger = logging.getLogger(__name__)

def aggregate_zodiac_stats(stats_date: date = None):
    """띠별 통계 집계 (배치 작업)
    
    매일 자정에 실행하여 전날 데이터 집계
    """
    
    if stats_date is None:
        stats_date = date.today()
    
    db: Session = SessionLocal()
    
    try:
        logger.info(f"Starting zodiac stats aggregation for {stats_date}")
        
        all_zodiacs = ZodiacService.get_all_zodiacs()
        
        for zodiac in all_zodiacs:
            # 해당 띠의 오늘 운세 통계 계산
            stats = db.query(
                func.avg(DailyFortune.overall_luck).label('avg_overall'),
                func.avg(DailyFortune.lottery_luck).label('avg_lottery'),
                func.count(DailyFortune.id).label('active_users')
            ).join(
                User, DailyFortune.user_id == User.id
            ).filter(
                User.zodiac_sign == zodiac,
                DailyFortune.fortune_date == stats_date
            ).first()
            
            if not stats or stats.active_users == 0:
                logger.info(f"No fortune data for {zodiac} on {stats_date}")
                continue
            
            # Upsert: 기존 데이터 업데이트 또는 새로 생성
            zodiac_stat = db.query(ZodiacDailyStat).filter(
                ZodiacDailyStat.stats_date == stats_date,
                ZodiacDailyStat.zodiac_sign == zodiac
            ).first()
            
            if zodiac_stat:
                # 기존 데이터 업데이트
                zodiac_stat.avg_overall_luck = stats.avg_overall
                zodiac_stat.avg_lottery_luck = stats.avg_lottery
                zodiac_stat.active_users = stats.active_users
                logger.info(f"Updated {zodiac}: avg_luck={stats.avg_lottery:.2f}, users={stats.active_users}")
            else:
                # 새 데이터 생성
                zodiac_stat = ZodiacDailyStat(
                    stats_date=stats_date,
                    zodiac_sign=zodiac,
                    avg_overall_luck=stats.avg_overall,
                    avg_lottery_luck=stats.avg_lottery,
                    active_users=stats.active_users,
                    predictions_count=0  # TODO: 예측 수 집계 추가
                )
                db.add(zodiac_stat)
                logger.info(f"Created new stats for {zodiac}: avg_luck={stats.avg_lottery:.2f}, users={stats.active_users}")
        
        db.commit()
        logger.info(f"✅ Zodiac stats aggregation completed for {stats_date}")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to aggregate zodiac stats for {stats_date}: {e}")
        raise e
    finally:
        db.close()


def cleanup_old_stats(days_to_keep: int = 30):
    """오래된 통계 데이터 정리 (선택사항)"""
    
    db: Session = SessionLocal()
    
    try:
        from datetime import timedelta
        cutoff_date = date.today() - timedelta(days=days_to_keep)
        
        # 오래된 데이터 삭제
        deleted_count = db.query(ZodiacDailyStat).filter(
            ZodiacDailyStat.stats_date < cutoff_date
        ).delete()
        
        db.commit()
        
        if deleted_count > 0:
            logger.info(f"🗑️ Cleaned up {deleted_count} old zodiac stats records (older than {cutoff_date})")
        
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Failed to cleanup old stats: {e}")
    finally:
        db.close()


# 실행 방법:
# python -m app.tasks.zodiac_stats_aggregator

if __name__ == "__main__":
    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    logger.info("🚀 Starting zodiac stats aggregation batch job...")
    
    try:
        # 오늘의 통계 집계
        aggregate_zodiac_stats()
        
        # 오래된 데이터 정리 (30일 이상된 것)
        cleanup_old_stats(30)
        
        logger.info("✅ Zodiac stats aggregation batch job completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Zodiac stats aggregation batch job failed: {e}")
        exit(1)