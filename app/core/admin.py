from functools import wraps
from fastapi import HTTPException, status, Depends
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.models.models import User


def require_admin(current_user: User = Depends(get_current_user)):
    """관리자 권한 확인 데코레이터"""
    if current_user.role != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="관리자 권한이 필요합니다"
        )
    return current_user


def require_admin_or_self(target_user_id: str):
    """관리자이거나 본인인 경우만 허용"""
    def decorator(current_user: User = Depends(get_current_user)):
        if current_user.role != 'admin' and str(current_user.id) != target_user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="접근 권한이 없습니다"
            )
        return current_user
    return decorator


class AdminPermissions:
    """관리자 권한 관리 클래스"""
    
    @staticmethod
    def can_manage_users(user: User) -> bool:
        """사용자 관리 권한 확인"""
        return user.role == 'admin'
    
    @staticmethod
    def can_view_analytics(user: User) -> bool:
        """분석 데이터 조회 권한 확인"""
        return user.role == 'admin'
    
    @staticmethod
    def can_manage_system(user: User) -> bool:
        """시스템 관리 권한 확인"""
        return user.role == 'admin'
    
    @staticmethod
    def can_access_logs(user: User) -> bool:
        """로그 조회 권한 확인"""
        return user.role == 'admin'


def is_admin(user: User) -> bool:
    """사용자가 관리자인지 확인"""
    return user.role == 'admin'