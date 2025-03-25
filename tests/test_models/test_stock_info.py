import pytest
from src.models.stock_info import StockInfo

def test_stock_info_creation():
    """StockInfo 객체 생성 테스트"""
    stock = StockInfo(
        name="삼성전자",
        market="KOSPI",
        etf=False,
        upper_limit=70000,
        lower_limit=60000,
        prev_close=65000,
        base_price=65000
    )
    
    assert stock.name == "삼성전자"
    assert stock.market == "KOSPI"
    assert stock.etf is False
    assert stock.upper_limit == 70000
    assert stock.lower_limit == 60000
    assert stock.prev_close == 65000
    assert stock.base_price == 65000

def test_stock_info_str_representation():
    """StockInfo 문자열 표현 테스트"""
    stock = StockInfo(
        name="삼성전자",
        market="KOSPI",
        etf=False,
        upper_limit=70000,
        lower_limit=60000,
        prev_close=65000,
        base_price=65000
    )
    
    expected_str = "StockInfo(name='삼성전자', market='KOSPI', etf=False, upper_limit=70000, lower_limit=60000, prev_close=65000, base_price=65000)"
    assert str(stock) == expected_str

def test_stock_info_equality():
    """StockInfo 객체 비교 테스트"""
    stock1 = StockInfo(
        name="삼성전자",
        market="KOSPI",
        etf=False,
        upper_limit=70000,
        lower_limit=60000,
        prev_close=65000,
        base_price=65000
    )
    
    stock2 = StockInfo(
        name="삼성전자",
        market="KOSPI",
        etf=False,
        upper_limit=70000,
        lower_limit=60000,
        prev_close=65000,
        base_price=65000
    )
    
    stock3 = StockInfo(
        name="SK하이닉스",
        market="KOSPI",
        etf=False,
        upper_limit=80000,
        lower_limit=70000,
        prev_close=75000,
        base_price=75000
    )
    
    assert stock1 == stock2
    assert stock1 != stock3 