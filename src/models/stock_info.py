"""종목 정보 모델"""
from dataclasses import dataclass

@dataclass
class StockInfo:
    """종목 정보를 저장하는 데이터 클래스"""
    name: str
    market: str
    etf: bool
    upper_limit: int
    lower_limit: int
    prev_close: int
    base_price: int 