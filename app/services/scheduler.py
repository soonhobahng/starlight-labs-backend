import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
import logging

from app.core.database import get_db
from app.core.config import settings
from app.models.models import User
from app.utils.draw_utils import get_next_draw_number, get_draw_date

# Logger 설정
logger = logging.getLogger(__name__)


class LottoScheduler:
    """로또 관련 작업 스케줄러"""
    
    def __init__(self):
        self.settings = settings
        self.admin_user_id: Optional[str] = None
        self.running = False
    
    async def start(self):
        """스케줄러 시작"""
        self.running = True
        logger.info("LottoScheduler started")
        
        # 관리자 사용자 찾기
        await self._find_admin_user()
        
        # 메인 루프 시작
        await self._run_scheduler()
    
    async def stop(self):
        """스케줄러 중지"""
        self.running = False
        logger.info("LottoScheduler stopped")
    
    async def _find_admin_user(self):
        """관리자 사용자 ID 찾기"""
        try:
            db = next(get_db())
            admin_user = db.query(User).filter(User.role == 'admin').first()
            if admin_user:
                self.admin_user_id = str(admin_user.id)
                logger.info(f"Found admin user: {self.admin_user_id}")
            else:
                logger.warning("Warning: No admin user found. Auto-sync will not work.")
            db.close()
        except Exception as e:
            logger.error(f"Error finding admin user: {e}")
    
    async def _run_scheduler(self):
        """메인 스케줄러 루프"""
        while self.running:
            try:
                await self._check_and_sync_lotto()
                # 1시간마다 체크
                await asyncio.sleep(3600)  # 3600초 = 1시간
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                await asyncio.sleep(60)  # 에러 시 1분 후 재시도
    
    async def _check_and_sync_lotto(self):
        """로또 데이터 동기화 필요 여부 확인 및 실행"""
        now = datetime.now()
        
        # 토요일 오후 8시 30분 이후인지 확인 (추첨 완료 후)
        if now.weekday() != 5:  # 토요일이 아니면 스킵
            return
        
        if now.hour < 20 or (now.hour == 20 and now.minute < 30):
            return  # 추첨 완료 전이면 스킵
        
        # 이미 오늘 동기화했는지 확인 (간단한 로직)
        last_sync_file = "/tmp/lotto_last_sync.txt"
        today_str = now.strftime("%Y-%m-%d")
        
        try:
            with open(last_sync_file, 'r') as f:
                last_sync_date = f.read().strip()
                if last_sync_date == today_str:
                    return  # 이미 오늘 동기화했음
        except FileNotFoundError:
            pass  # 파일이 없으면 첫 실행
        
        # 동기화 실행
        success = await self._execute_lotto_sync()
        
        if success:
            # 성공 시 마지막 동기화 날짜 기록
            with open(last_sync_file, 'w') as f:
                f.write(today_str)
            logger.info(f"Lotto data synced successfully at {now}")
        else:
            logger.error(f"Lotto data sync failed at {now}")
    
    async def _execute_lotto_sync(self) -> bool:
        """로또 동기화 API 실행"""
        if not self.admin_user_id:
            logger.warning("No admin user available for auto-sync")
            return False
        
        try:
            # 내부 API 호출을 위한 토큰 생성 (여기서는 간단히 처리)
            # 실제로는 JWT 토큰을 생성해야 함
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                # 관리자로 로그인하여 sync API 호출
                response = await client.post(
                    f"http://localhost:8000{self.settings.api_prefix}/lotto/sync",
                    headers={
                        "Content-Type": "application/json",
                        # "Authorization": f"Bearer {admin_token}"  # 실제 구현 시 필요
                    },
                    json={}
                )
                
                if response.status_code == 200:
                    return True
                else:
                    logger.error(f"Sync API failed: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error calling sync API: {e}")
            return False
    
    async def schedule_next_draw_reminder(self):
        """다음 추첨일 알림 스케줄링 (확장 기능)"""
        next_draw = get_next_draw_number()
        draw_date = get_draw_date(next_draw)
        
        # 추첨일 1시간 전 알림 등의 기능 구현 가능
        logger.info(f"Next draw {next_draw} scheduled for {draw_date}")


# 전역 스케줄러 인스턴스
scheduler = LottoScheduler()


async def start_scheduler():
    """스케줄러 시작 함수"""
    await scheduler.start()


async def stop_scheduler():
    """스케줄러 중지 함수"""
    await scheduler.stop()


# FastAPI 이벤트에서 사용할 함수들
async def startup_event():
    """앱 시작 시 스케줄러 시작"""
    asyncio.create_task(start_scheduler())


async def shutdown_event():
    """앱 종료 시 스케줄러 중지"""
    await stop_scheduler()