import pytest
from unittest.mock import Mock, AsyncMock, patch
import json
from src.handlers.ccld_event_handler import CcldEventHandler

@pytest.fixture
def ccld_event_handler(test_logger):
    ws_manager = Mock()
    vi_handler = Mock()
    vi_handler.handle_vi_event = AsyncMock()
    vi_handler.handle_trade_data = AsyncMock()
    return CcldEventHandler(
        ws_manager=ws_manager,
        vi_handler=vi_handler
    )

@pytest.mark.asyncio
async def test_process_system_message_with_stock_info(ccld_event_handler):
    """시스템 메시지 처리 테스트 - 종목 정보 있음"""
    header = {
        "tr_cd": "H1_",
        "tr_key": "005930",
        "rsp_msg": "구독 성공",
        "tr_type": "3"
    }
    
    # 종목 정보 모의 설정
    stock_info = Mock()
    stock_info.name = "삼성전자"
    ccld_event_handler.vi_handler.data_manager.get_stock_info.return_value = stock_info
    
    await ccld_event_handler._process_system_message(header)
    ccld_event_handler.vi_handler.data_manager.get_stock_info.assert_called_once_with("005930")

@pytest.mark.asyncio
async def test_process_system_message_without_stock_info(ccld_event_handler):
    """시스템 메시지 처리 테스트 - 종목 정보 없음"""
    header = {
        "tr_cd": "H1_",
        "tr_key": "000000",
        "rsp_msg": "구독 실패",
        "tr_type": "3"
    }
    
    # 종목 정보가 없는 경우
    ccld_event_handler.vi_handler.data_manager.get_stock_info.return_value = None
    
    await ccld_event_handler._process_system_message(header)
    ccld_event_handler.vi_handler.data_manager.get_stock_info.assert_called_once_with("000000")

@pytest.mark.asyncio
async def test_process_system_message_unsubscribe(ccld_event_handler):
    """시스템 메시지 처리 테스트 - 구독 해지"""
    header = {
        "tr_cd": "H1_",
        "tr_key": "005930",
        "rsp_msg": "구독 해지 성공",
        "tr_type": "4"
    }
    
    # 종목 정보 모의 설정
    stock_info = Mock()
    stock_info.name = "삼성전자"
    ccld_event_handler.vi_handler.data_manager.get_stock_info.return_value = stock_info
    
    await ccld_event_handler._process_system_message(header)
    ccld_event_handler.vi_handler.data_manager.get_stock_info.assert_called_once_with("005930")

@pytest.mark.asyncio
async def test_process_vi_message(ccld_event_handler):
    """VI 메시지 처리 테스트"""
    vi_data = {
        "header": {"tr_cd": "VI_"},
        "body": {"ref_shcode": "005930"}
    }
    
    await ccld_event_handler._process_vi_message(vi_data)
    ccld_event_handler.vi_handler.handle_vi_event.assert_called_once_with(vi_data)

@pytest.mark.asyncio
async def test_process_trade_message(ccld_event_handler):
    """체결 메시지 처리 테스트"""
    trade_data = {
        "header": {"tr_cd": "S3_"},
        "body": {"shcode": "005930"}
    }
    
    await ccld_event_handler._process_trade_message(trade_data)
    ccld_event_handler.vi_handler.handle_trade_data.assert_called_once_with(trade_data)

@pytest.mark.asyncio
async def test_process_message_valid_json(ccld_event_handler):
    """유효한 JSON 메시지 처리 테스트"""
    message = json.dumps({
        "header": {"tr_cd": "VI_"},
        "body": {"ref_shcode": "005930"}
    })
    
    await ccld_event_handler.process_message(message)
    ccld_event_handler.vi_handler.handle_vi_event.assert_called_once()

@pytest.mark.asyncio
async def test_process_message_no_body(ccld_event_handler):
    """본문이 없는 메시지 처리 테스트"""
    message = json.dumps({
        "header": {
            "tr_cd": "H1_",
            "tr_key": "005930",
            "rsp_msg": "구독 성공",
            "tr_type": "3"
        }
    })
    
    # 종목 정보 모의 설정
    stock_info = Mock()
    stock_info.name = "삼성전자"
    ccld_event_handler.vi_handler.data_manager.get_stock_info.return_value = stock_info
    
    await ccld_event_handler.process_message(message)
    ccld_event_handler.vi_handler.data_manager.get_stock_info.assert_called_once_with("005930")

@pytest.mark.asyncio
async def test_process_message_invalid_json(ccld_event_handler):
    """잘못된 JSON 메시지 처리 테스트"""
    message = "invalid json"
    
    await ccld_event_handler.process_message(message)
    ccld_event_handler.vi_handler.handle_vi_event.assert_not_called()

@pytest.mark.asyncio
async def test_process_message_invalid_format(ccld_event_handler):
    """잘못된 형식의 메시지 처리 테스트"""
    message = json.dumps(["not a dict"])
    
    await ccld_event_handler.process_message(message)
    ccld_event_handler.vi_handler.handle_vi_event.assert_not_called()
    ccld_event_handler.vi_handler.handle_trade_data.assert_not_called()

@pytest.mark.asyncio
async def test_process_message_unknown_type(ccld_event_handler):
    """알 수 없는 메시지 타입 처리 테스트"""
    message = json.dumps({
        "header": {"tr_cd": "UNKNOWN"},
        "body": {}
    })
    
    await ccld_event_handler.process_message(message)
    ccld_event_handler.vi_handler.handle_vi_event.assert_not_called()
    ccld_event_handler.vi_handler.handle_trade_data.assert_not_called()

@pytest.mark.asyncio
async def test_process_message_exception(ccld_event_handler):
    """예외 발생 케이스 테스트"""
    message = json.dumps({
        "header": {"tr_cd": "VI_"},
        "body": {"ref_shcode": "005930"}
    })
    
    # 예외 발생 시나리오 설정
    ccld_event_handler.vi_handler.handle_vi_event.side_effect = Exception("테스트 예외")
    
    # 예외가 처리되어야 함
    await ccld_event_handler.process_message(message) 