"""로깅 유틸리티"""
import os
import logging
from datetime import datetime
import pytz
from logging.handlers import RotatingFileHandler
from config.settings import LOG_FORMAT, LOG_DATE_FORMAT, LOG_MAX_BYTES, LOG_BACKUP_COUNT

def setup_logger(name: str) -> logging.Logger:
    """로거 설정"""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # 이미 핸들러가 있다면 추가하지 않음
    if logger.handlers:
        return logger
    
    # 로그 디렉토리 생성
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 로그 파일 경로
    log_file = os.path.join(log_dir, get_log_file_name())
    
    # 포맷터 생성
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    
    # 파일 핸들러 생성
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=LOG_MAX_BYTES,
        backupCount=LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    
    # 콘솔 핸들러 생성
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    
    # 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger 

def get_log_file_name() -> str:
    """오늘 날짜 기준 로그 파일명 반환"""
    kst = pytz.timezone('Asia/Seoul')
    today = datetime.now(kst).strftime('%Y%m%d')
    return f'vi_monitor_{today}.log' 