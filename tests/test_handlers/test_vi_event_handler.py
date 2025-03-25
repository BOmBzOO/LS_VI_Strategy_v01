import pytest
from unittest.mock import Mock, patch
from src.handlers.vi_event_handler import VIEventHandler

@pytest.fixture
def vi_event_handler(test_logger, test_config):
    ws_manager = Mock()
    data_manager = Mock()
    return VIEventHandler(
        ws_manager=ws_manager,
        data_manager=data_manager
    )

@pytest.mark.asyncio
async def test_handle_vi_event_trigger(vi_event_handler):
    """VI 발동 이벤트 처리 테스트"""
    # 종목 정보 모의 설정
    stock_info = Mock()
    stock_info.name = "삼성전자"
    stock_info.market = "KOSPI"
    vi_event_handler.data_manager.get_stock_info.return_value = stock_info
    
    # VI 발동 데이터
    vi_data = {
        "body": {
            "vi_gubun": "1",
            "ref_shcode": "005930",
            "vi_trgprice": "65000",
            "time": "090000"
        }
    }
    
    await vi_event_handler.handle_vi_event(vi_data)
    vi_event_handler.data_manager.add_vi_stock.assert_called_once_with("005930")

@pytest.mark.asyncio
async def test_handle_vi_event_release(vi_event_handler):
    """VI 해제 이벤트 처리 테스트"""
    # 종목 정보 모의 설정
    stock_info = Mock()
    stock_info.name = "삼성전자"
    stock_info.market = "KOSPI"
    vi_event_handler.data_manager.get_stock_info.return_value = stock_info
    
    # VI 해제 데이터
    vi_data = {
        "body": {
            "vi_gubun": "4",
            "ref_shcode": "005930",
            "vi_trgprice": "65000",
            "time": "090000"
        }
    }
    
    await vi_event_handler.handle_vi_event(vi_data)
    vi_event_handler.data_manager.add_vi_stock.assert_not_called()

@pytest.mark.asyncio
async def test_handle_trade_data(vi_event_handler):
    """체결 데이터 처리 테스트"""
    # 종목 정보 모의 설정
    stock_info = Mock()
    stock_info.name = "삼성전자"
    vi_event_handler.data_manager.get_stock_info.return_value = stock_info
    vi_event_handler.data_manager.is_vi_active.return_value = True
    
    # 체결 데이터
    trade_data = {
        "body": {
            "shcode": "005930",
            "price": "65000",
            "cvolume": "100"
        }
    }
    
    await vi_event_handler.handle_trade_data(trade_data)
    vi_event_handler.data_manager.get_stock_info.assert_called_once_with("005930")

@pytest.mark.asyncio
async def test_subscribe_trade_data(vi_event_handler):
    """체결 정보 구독 테스트"""
    stock_code = "005930"
    market_type = "S3_"
    
    await vi_event_handler.subscribe_trade_data(stock_code, market_type)
    vi_event_handler.ws_manager.send.assert_called_once()

@pytest.mark.asyncio
async def test_unsubscribe_trade_data(vi_event_handler):
    """체결 정보 구독 해제 테스트"""
    stock_code = "005930"
    market_type = "S3_"
    
    await vi_event_handler.unsubscribe_trade_data(stock_code, market_type)
    vi_event_handler.ws_manager.send.assert_called_once()
    vi_event_handler.data_manager.remove_vi_stock.assert_called_once_with(stock_code)

@pytest.mark.asyncio
async def test_handle_reconnection(vi_event_handler):
    """재연결 처리 테스트"""
    # 활성화된 VI 종목 모의 설정
    stock_info = Mock()
    stock_info.name = "삼성전자"
    stock_info.market = "KOSPI"
    vi_event_handler.data_manager.get_stock_info.return_value = stock_info
    vi_event_handler.data_manager.get_active_stocks.return_value = ["005930"]
    
    await vi_event_handler.handle_reconnection()
    vi_event_handler.ws_manager.send.assert_called_once() 