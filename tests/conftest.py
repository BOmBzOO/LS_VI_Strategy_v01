import os
import sys
import pytest
import logging
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = str(Path(__file__).parent.parent)
sys.path.insert(0, project_root)

# 테스트용 로거 설정
@pytest.fixture
def test_logger():
    """테스트용 로거 fixture"""
    logger = logging.getLogger("test_logger")
    logger.setLevel(logging.DEBUG)
    
    # 핸들러가 이미 있다면 제거
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # 콘솔 핸들러 추가
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

# 테스트용 설정 fixture
@pytest.fixture
def test_config():
    """테스트용 설정 fixture"""
    return {
        "api_key": "test_api_key",
        "api_secret": "test_api_secret",
        "base_url": "https://test.api.com",
        "websocket_url": "wss://test.ws.com",
        "log_dir": "logs",
        "stock_info_file": "stock_info.csv",
        "vi_duration": 2,  # VI 지속 시간 (분)
        "reconnect_delay": 5,  # 재연결 대기 시간 (초)
        "max_reconnect_attempts": 3  # 최대 재연결 시도 횟수
    }

# 테스트용 임시 디렉토리 fixture
@pytest.fixture
def test_data_dir(tmp_path):
    """테스트용 데이터 디렉토리 fixture"""
    data_dir = tmp_path / "data"
    data_dir.mkdir(exist_ok=True)
    return data_dir

# 테스트용 임시 로그 디렉토리 fixture
@pytest.fixture
def test_log_dir(tmp_path):
    """테스트용 로그 디렉토리 fixture"""
    log_dir = tmp_path / "logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir 