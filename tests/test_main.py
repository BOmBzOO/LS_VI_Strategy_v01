import pytest
import os
import csv
from unittest.mock import Mock, patch, AsyncMock
from src.main import VIMonitor, main
from src.models.stock_info import StockInfo
from datetime import datetime
from config.constants import STOCK_INFO_DIR

@pytest.fixture
def sample_stock_data():
    return [
        {
            "code": "005930",
            "name": "삼성전자",
            "market": "KOSPI",
            "etf": "N",
            "upper_limit": "70000",
            "lower_limit": "50000",
            "prev_close": "60000",
            "base_price": "60000"
        }
    ]

@pytest.fixture
def vi_monitor(test_logger):
    return VIMonitor()

@pytest.mark.asyncio
async def test_initialize(vi_monitor):
    """초기화 테스트"""
    with patch('src.core.token_manager.TokenManager.get_access_token') as mock_get_token:
        mock_get_token.return_value = "test_token"
        
        with patch.object(vi_monitor, 'load_stock_info') as mock_load_info:
            await vi_monitor.initialize()
            
            assert vi_monitor.ws_manager is not None
            assert vi_monitor.vi_handler is not None
            assert vi_monitor.message_processor is not None
            mock_load_info.assert_called_once_with("test_token")

@pytest.mark.asyncio
async def test_load_stock_info_from_csv(vi_monitor):
    """CSV 파일에서 종목 정보 로드 테스트"""
    # CSV 파일 생성
    today = datetime.now(vi_monitor.kst).strftime('%Y%m%d')
    csv_file = os.path.join(STOCK_INFO_DIR, f'stocks_info_{today}.csv')
    os.makedirs(STOCK_INFO_DIR, exist_ok=True)
    
    with open(csv_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['종목코드', '종목명', '시장구분', 'ETF구분', '상한가', '하한가', '전일가', '기준가'])
        writer.writeheader()
        writer.writerow({
            '종목코드': '005930',
            '종목명': '삼성전자',
            '시장구분': 'KOSPI',
            'ETF구분': 'False',
            '상한가': '70000',
            '하한가': '60000',
            '전일가': '65000',
            '기준가': '65000'
        })
    
    await vi_monitor.load_stock_info("test_token")
    assert '005930' in vi_monitor.data_manager.stock_info

@pytest.mark.asyncio
async def test_load_stock_info_from_api(vi_monitor):
    """API에서 종목 정보 로드 테스트"""
    with patch('aiohttp.ClientSession.post') as mock_post:
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "t8430OutBlock": [{
                "shcode": "005930",
                "hname": "삼성전자",
                "gubun": "1",
                "etfgubun": "0",
                "uplmtprice": 70000,
                "dnlmtprice": 60000,
                "jnilclose": 65000,
                "recprice": 65000
            }]
        })
        mock_post.return_value.__aenter__.return_value = mock_response
        
        await vi_monitor.load_stock_info("test_token")
        assert '005930' in vi_monitor.data_manager.stock_info

@pytest.mark.asyncio
async def test_save_stock_info_to_csv(vi_monitor):
    """종목 정보 CSV 파일 저장 테스트"""
    # 종목 정보 설정
    vi_monitor.data_manager.stock_info['005930'] = StockInfo(
        name='삼성전자',
        market='KOSPI',
        etf=False,
        upper_limit=70000,
        lower_limit=60000,
        prev_close=65000,
        base_price=65000
    )
    
    # CSV 파일 저장
    today = datetime.now(vi_monitor.kst).strftime('%Y%m%d')
    csv_file = os.path.join(STOCK_INFO_DIR, f'stocks_info_{today}.csv')
    vi_monitor.save_stock_info_to_csv(csv_file)
    
    # 파일 존재 확인
    assert os.path.exists(csv_file)

def test_cleanup(vi_monitor):
    """정리 작업 테스트"""
    # 컴포넌트 모의 설정
    vi_monitor.vi_handler = Mock()
    vi_monitor.ws_manager = Mock()
    
    vi_monitor.cleanup()
    
    assert not vi_monitor.is_running
    vi_monitor.vi_handler.cleanup.assert_called_once()
    vi_monitor.ws_manager.cleanup.assert_called_once()

@pytest.mark.asyncio
async def test_main_function():
    """메인 함수 테스트"""
    # VIMonitor 인스턴스 모의 설정
    mock_monitor = Mock()
    mock_monitor.initialize = AsyncMock()
    mock_monitor.start = AsyncMock()
    mock_monitor.cleanup = AsyncMock()
    
    with patch("src.main.VIMonitor", return_value=mock_monitor):
        # 메인 함수 실행
        await main()
        
        # 함수 호출 확인
        mock_monitor.initialize.assert_called_once()
        mock_monitor.start.assert_called_once()
        mock_monitor.cleanup.assert_called_once() 