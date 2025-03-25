"""기본 핸들러 모듈"""
import pytz
from abc import ABC, abstractmethod
from src.utils.logger import setup_logger

class BaseHandler(ABC):
    """기본 핸들러 클래스"""
    _logger = None  # 클래스 변수로 로거 객체 저장
    
    def __init__(self, logger_name: str):
        self.kst = pytz.timezone('Asia/Seoul')
        self.logger_name = logger_name
        if BaseHandler._logger is None:
            BaseHandler._logger = setup_logger('VIMonitor')
        self.logger = BaseHandler._logger
    
    def log(self, message: str, level: str = 'info') -> None:
        """통합 로깅 메서드"""
        log_message = f"[{self.logger_name}] {message}"
        getattr(self.logger, level)(log_message) 