import cloudinary
import cloudinary.uploader
from fastapi import UploadFile, HTTPException
from typing import Optional
import os

class UploadService:
    
    ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    
    @staticmethod
    def validate_image_file(file: UploadFile) -> None:
        """이미지 파일 검증"""
        # 파일 확장자 확인
        if not file.filename:
            raise HTTPException(status_code=400, detail="파일명이 없습니다")
        
        ext = file.filename.split('.')[-1].lower()
        if ext not in UploadService.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400, 
                detail=f"지원하지 않는 파일 형식입니다. (지원: {', '.join(UploadService.ALLOWED_EXTENSIONS)})"
            )
        
        # Content-Type 확인
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="이미지 파일만 업로드 가능합니다")
    
    @staticmethod
    async def upload_profile_image(file: UploadFile, user_id: int) -> str:
        """
        프로필 이미지를 Cloudinary에 업로드
        
        Args:
            file: 업로드할 이미지 파일
            user_id: 사용자 ID
            
        Returns:
            str: Cloudinary URL
        """
        # 파일 검증
        UploadService.validate_image_file(file)
        
        # 파일 크기 확인
        contents = await file.read()
        if len(contents) > UploadService.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400, 
                detail=f"파일 크기는 {UploadService.MAX_FILE_SIZE / 1024 / 1024}MB 이하여야 합니다"
            )
        
        # 파일 포인터 초기화
        await file.seek(0)
        
        try:
            # Cloudinary에 업로드
            result = cloudinary.uploader.upload(
                file.file,
                folder="lottolabs/profiles",
                public_id=f"user_{user_id}",
                overwrite=True,  # 기존 이미지 덮어쓰기
                transformation=[
                    {
                        "width": 200,
                        "height": 200,
                        "crop": "fill",
                        "gravity": "face"  # 얼굴 중심으로 크롭
                    },
                    {"quality": "auto"},
                    {"fetch_format": "auto"}  # WebP 자동 변환
                ]
            )
            
            return result["secure_url"]
            
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"이미지 업로드 중 오류가 발생했습니다: {str(e)}"
            )
    
    @staticmethod
    def delete_profile_image(user_id: int) -> bool:
        """Cloudinary에서 프로필 이미지 삭제"""
        try:
            cloudinary.uploader.destroy(f"lottolabs/profiles/user_{user_id}")
            return True
        except Exception:
            return False