"""VI 이벤트 처리 모듈"""
import json
from datetime import datetime
import asyncio
from typing import Dict, Any

from src.core.base_handler import BaseHandler
from src.core.websocket_manager import WebSocketManager
from src.core.data_manager import DataManager
from config.settings import ls_config

class VIEventHandler(BaseHandler):
    """VI 이벤트 처리 및 체결 구독 관리 클래스"""
    def __init__(self, ws_manager: WebSocketManager, data_manager: DataManager):
        super().__init__('VIEventHandler')
        self.ws_manager = ws_manager
        self.data_manager = data_manager
        self.is_reconnecting = False
    
    def get_tr_cd(self, market_type: str) -> str:
        """시장 구분을 tr_cd로 변환"""
        return ls_config.MARKET_CODES.get(market_type, market_type)

    async def handle_vi_event(self, vi_data: Dict[str, Any]) -> None:
        """VI 이벤트 처리"""
        body = vi_data.get("body", {})
        current_time = datetime.now(self.kst)
        timestamp = current_time.strftime("%H:%M:%S")
        
        vi_gubun = body.get("vi_gubun", "0")
        vi_status = ls_config.VI.STATUS.get(vi_gubun, "알 수 없음")
        
        stock_code = body.get('ref_shcode')
        stock_info = self.data_manager.get_stock_info(stock_code)
        if not stock_info:
            return
            
        market_type = stock_info.market
        tr_cd = self.get_tr_cd(market_type)
        
        # VI 상태 정보를 한 줄로 출력
        vi_message = (f"[{timestamp}] [VI {vi_status}] {market_type} | {stock_info.name}({stock_code}) | "
                     f"기준가: {body.get('vi_trgprice')} | 발동시각: {body.get('time')}")
        self.log(vi_message)
        
        # VI 발동된 경우 체결 정보 구독
        if vi_gubun in ["1", "2", "3"] and not self.data_manager.is_vi_active(stock_code):
            self.data_manager.add_vi_stock(stock_code)
            await self.subscribe_trade_data(stock_code, tr_cd)
            
            # 3분 후 자동 구독 취소를 위한 타이머 시작
            await self.data_manager.start_vi_timer(
                stock_code,
                lambda code: self.unsubscribe_trade_data(code, tr_cd)
            )

    async def handle_trade_data(self, trade_data: Dict[str, Any]) -> None:
        """체결 데이터 처리"""
        body = trade_data.get("body", {})
        stock_code = body.get("shcode")
        
        if not self.data_manager.is_vi_active(stock_code):
            return
            
        stock_info = self.data_manager.get_stock_info(stock_code)
        if not stock_info:
            return
            
        # 체결 정보를 간단하게 출력
        current_time = datetime.now(self.kst)
        trade_message = (f"[{current_time.strftime('%H:%M:%S')}] 체결 | {stock_info.name}({stock_code}) | "
                        f"{body.get('price'):>7}원 | {body.get('cvolume'):>6}주")
        self.log(trade_message)

    async def subscribe_trade_data(self, stock_code: str, market_type: str) -> None:
        """체결 정보 구독"""
        message = {
            "header": {
                "token": self.ws_manager.token,
                "tr_type": ls_config.TRADE_TYPES["SUBSCRIBE"]
            },
            "body": {
                "tr_cd": market_type,
                "tr_key": stock_code
            }
        }
        await self.ws_manager.send(message)
        
        if not self.is_reconnecting:
            active_stocks = self.data_manager.get_active_stocks()
            self.log(f">>> 현재 구독 중인 종목 수: {len(active_stocks)}개 ({', '.join(sorted(active_stocks))})")

    async def unsubscribe_trade_data(self, stock_code: str, market_type: str) -> None:
        """체결 정보 구독 해제"""
        message = {
            "header": {
                "token": self.ws_manager.token,
                "tr_type": ls_config.TRADE_TYPES["UNSUBSCRIBE"]
            },
            "body": {
                "tr_cd": market_type,
                "tr_key": stock_code
            }
        }
        await self.ws_manager.send(message)
        self.data_manager.remove_vi_stock(stock_code)
        
        if not self.is_reconnecting:
            active_stocks = self.data_manager.get_active_stocks()
            self.log(f">>> 현재 구독 중인 종목 수: {len(active_stocks)}개 ({', '.join(sorted(active_stocks))})")

    async def handle_reconnection(self) -> None:
        """재연결 처리"""
        self.is_reconnecting = True
        
        # 재연결 시 활성화된 VI 종목들의 체결 정보 재구독
        for stock_code in self.data_manager.get_active_stocks():
            stock_info = self.data_manager.get_stock_info(stock_code)
            if stock_info:
                market_type = self.get_tr_cd(stock_info.market)
                await self.subscribe_trade_data(stock_code, market_type)
        
        self.is_reconnecting = False

    def cleanup(self) -> None:
        """정리 작업"""
        self.log("구독 정리 작업 시작...")
        
        # VI 발동된 모든 종목의 체결 정보 구독 해제
        for stock_code in self.data_manager.get_active_stocks():
            stock_info = self.data_manager.get_stock_info(stock_code)
            if stock_info:
                market_type = self.get_tr_cd(stock_info.market)
                asyncio.create_task(self.unsubscribe_trade_data(stock_code, market_type))
        
        self.log("구독 정리 작업 완료") 