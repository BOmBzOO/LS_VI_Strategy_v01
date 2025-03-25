"""주문 관리 모듈"""
from typing import Dict, Optional
import aiohttp
from config.settings import LSConfig as config

class OrderManager:
    """주문 관리 클래스"""
    
    def __init__(self, token_manager):
        """
        OrderManager 초기화
        
        Args:
            token_manager: 토큰 관리자 인스턴스
        """
        self.token_manager = token_manager
        self.base_url = f"{config.API_URL}/stock/order"
        self.headers = {
            "Content-Type": "application/json",
            "authorization": f"Bearer {self.token_manager.get_access_token()}"
        }
        
    async def place_order(
        self,
        account_no: str,
        symbol: str,
        order_type: str,
        price_type: str,
        quantity: int,
        price: float,
        side: str
    ) -> Dict:
        """
        주문 발주
        
        Args:
            account_no: 계좌번호
            symbol: 종목코드
            order_type: 주문유형 (1:신규, 2:정정, 3:취소)
            price_type: 가격유형 (1:지정가, 2:시장가)
            quantity: 주문수량
            price: 주문가격
            side: 매매구분 (1:매수, 2:매도)
            
        Returns:
            주문 응답 데이터
        """
        url = f"{self.base_url}/place"
        data = {
            "account_no": account_no,
            "symbol": symbol,
            "order_type": order_type,
            "price_type": price_type,
            "quantity": quantity,
            "price": price,
            "side": side
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=data) as response:
                return await response.json()
                
    async def modify_order(
        self,
        account_no: str,
        order_no: str,
        quantity: Optional[int] = None,
        price: Optional[float] = None
    ) -> Dict:
        """
        주문 정정
        
        Args:
            account_no: 계좌번호
            order_no: 원주문번호
            quantity: 정정 수량
            price: 정정 가격
            
        Returns:
            정정 응답 데이터
        """
        url = f"{self.base_url}/modify"
        data = {
            "account_no": account_no,
            "order_no": order_no
        }
        
        if quantity is not None:
            data["quantity"] = quantity
        if price is not None:
            data["price"] = price
            
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=data) as response:
                return await response.json()
                
    async def cancel_order(
        self,
        account_no: str,
        order_no: str
    ) -> Dict:
        """
        주문 취소
        
        Args:
            account_no: 계좌번호
            order_no: 원주문번호
            
        Returns:
            취소 응답 데이터
        """
        url = f"{self.base_url}/cancel"
        data = {
            "account_no": account_no,
            "order_no": order_no
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=self.headers, json=data) as response:
                return await response.json()
                
    async def get_order_status(
        self,
        account_no: str,
        order_no: str
    ) -> Dict:
        """
        주문 상태 조회
        
        Args:
            account_no: 계좌번호
            order_no: 주문번호
            
        Returns:
            주문 상태 데이터
        """
        url = f"{self.base_url}/status"
        params = {
            "account_no": account_no,
            "order_no": order_no
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=self.headers, params=params) as response:
                return await response.json() 