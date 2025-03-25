import pytest
import os
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from src.core.token_manager import TokenManager

@pytest.fixture
def token_manager(test_logger, test_config):
    with patch('src.core.token_manager.API_URL', 'https://test.api.com'):
        manager = TokenManager(
            api_key=test_config["api_key"],
            api_secret=test_config["api_secret"]
        )
        return manager

@pytest.mark.asyncio
async def test_get_access_token_success(token_manager):
    """토큰 발급 성공 테스트"""
    with patch('os.getenv', return_value=None):
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value={
                "access_token": "test_token",
                "token_type": "Bearer",
                "expires_in": 3600
            })
            mock_post.return_value.__aenter__.return_value = mock_response
            
            token = await token_manager.get_access_token()
            assert token == "test_token"

@pytest.mark.asyncio
async def test_get_access_token_failure(token_manager):
    """토큰 발급 실패 테스트"""
    with patch('os.getenv', return_value=None):
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.json = AsyncMock(return_value={
                "error": "invalid_client",
                "error_description": "Invalid client credentials"
            })
            mock_post.return_value.__aenter__.return_value = mock_response
            
            with pytest.raises(Exception):
                await token_manager.get_access_token()

def test_is_token_valid(token_manager):
    """토큰 유효성 검사 테스트"""
    # 토큰이 없는 경우
    with patch('os.getenv', return_value=None):
        assert not token_manager.is_token_valid()
    
    # 토큰이 있지만 만료된 경우
    expired_time = datetime.now(token_manager.kst) - timedelta(hours=1)
    with patch('os.getenv', side_effect=["test_token", expired_time.isoformat()]):
        assert not token_manager.is_token_valid()
    
    # 토큰이 있고 유효한 경우
    valid_time = datetime.now(token_manager.kst) + timedelta(hours=1)
    with patch('os.getenv', side_effect=["test_token", valid_time.isoformat()]):
        assert token_manager.is_token_valid()

def test_save_token_to_env(token_manager):
    """토큰 저장 테스트"""
    with patch('src.core.token_manager.set_key') as mock_set_key:
        token = "test_token"
        expires_in = 3600
        
        token_manager.save_token_to_env(token, expires_in)
        
        assert token_manager.token == token
        assert token_manager.token_expires_at is not None
        assert mock_set_key.call_count == 2

@pytest.mark.asyncio
async def test_save_token_to_env(token_manager, tmp_path):
    """토큰 환경 파일 저장 테스트"""
    # 기존 환경 변수 백업
    original_token = os.getenv('LS_ACCESS_TOKEN')
    original_expires_at = os.getenv('LS_TOKEN_EXPIRES_AT')

    try:
        # 환경 변수 초기화
        if 'LS_ACCESS_TOKEN' in os.environ:
            del os.environ['LS_ACCESS_TOKEN']
        if 'LS_TOKEN_EXPIRES_AT' in os.environ:
            del os.environ['LS_TOKEN_EXPIRES_AT']

        # 테스트용 환경 파일 경로 설정
        env_file = tmp_path / ".env"

        # 테스트용 토큰 정보
        test_token = "test_token"
        test_expires_in = 3600  # 1시간

        # 토큰 저장
        token_manager.save_token_to_env(test_token, test_expires_in, str(env_file))

        # 환경 변수 확인
        assert os.getenv('LS_ACCESS_TOKEN') == test_token
        assert os.getenv('LS_TOKEN_EXPIRES_AT') is not None
        assert token_manager.token == test_token
        assert token_manager.token_expires_at is not None

    finally:
        # 원래 환경 변수 복원
        if original_token:
            os.environ['LS_ACCESS_TOKEN'] = original_token
        elif 'LS_ACCESS_TOKEN' in os.environ:
            del os.environ['LS_ACCESS_TOKEN']

        if original_expires_at:
            os.environ['LS_TOKEN_EXPIRES_AT'] = original_expires_at
        elif 'LS_TOKEN_EXPIRES_AT' in os.environ:
            del os.environ['LS_TOKEN_EXPIRES_AT'] 