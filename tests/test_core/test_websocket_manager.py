import pytest
import asyncio
from unittest.mock import Mock, patch
from websockets.exceptions import ConnectionClosed
from src.core.websocket_manager import WebSocketManager
import json
from unittest.mock import AsyncMock

@pytest.fixture
def websocket_manager(test_logger, test_config):
    return WebSocketManager(
        url=test_config["base_url"],
        token="test_token"
    )

@pytest.mark.asyncio
async def test_connect_success(websocket_manager):
    """웹소켓 연결 성공 테스트"""
    with patch('websockets.connect') as mock_connect:
        mock_ws = AsyncMock()
        mock_connect.return_value.__aenter__.return_value = mock_ws
        
        await websocket_manager.connect()
        assert websocket_manager.ws == mock_ws

@pytest.mark.asyncio
async def test_connect_failure(websocket_manager):
    """웹소켓 연결 실패 테스트"""
    with patch('websockets.connect') as mock_connect:
        mock_connect.side_effect = Exception("Connection failed")
        
        with patch.object(websocket_manager, '_handle_reconnection') as mock_reconnect:
            await websocket_manager.connect()
            mock_reconnect.assert_called_once()

@pytest.mark.asyncio
async def test_send_message(websocket_manager):
    """메시지 전송 테스트"""
    mock_ws = AsyncMock()
    websocket_manager.ws = mock_ws
    
    message = {"type": "test", "data": "test_data"}
    await websocket_manager.send(message)
    
    mock_ws.send.assert_called_once_with(json.dumps(message))

@pytest.mark.asyncio
async def test_handle_reconnection(websocket_manager):
    """재연결 처리 테스트"""
    with patch.object(websocket_manager, 'connect') as mock_connect:
        await websocket_manager._handle_reconnection()
        assert websocket_manager.reconnect_count == 1
        mock_connect.assert_called_once()

def test_cleanup(websocket_manager):
    """정리 작업 테스트"""
    mock_ws = AsyncMock()
    websocket_manager.ws = mock_ws
    
    websocket_manager.cleanup()
    assert not websocket_manager.is_running 