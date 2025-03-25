"""체결 이벤트 처리 모듈"""
import json
from typing import Dict, Any

from src.handlers.base_handler import BaseHandler
from src.core.websocket_manager import WebSocketManager
from src.handlers.vi_event_handler import VIEventHandler

class CcldEventHandler(BaseHandler):
    """체결 이벤트 처리 클래스"""
    def __init__(self, ws_manager: WebSocketManager, vi_handler: VIEventHandler):
        super().__init__('CcldEventHandler')
        self.ws_manager = ws_manager
        self.vi_handler = vi_handler
        
    async def process_message(self, message: str) -> None:
        """메시지 처리"""
        try:
            data = json.loads(message)
            if not isinstance(data, dict):
                self.log("잘못된 메시지 형식입니다.")
                return
                
            header = data.get("header", {})
            body = data.get("body", {})
            
            if not body:
                await self._process_system_message(header)
                return
            
            tr_cd = header.get("tr_cd")
            if tr_cd == "VI_":
                await self._process_vi_message(data)
            elif tr_cd in ["S3_", "K3_"]:
                await self._process_trade_message(data)
                
        except json.JSONDecodeError as e:
            self.log(f"JSON 파싱 오류: {e}", 'error')
        except Exception as e:
            self.log(f"메시지 처리 중 오류 발생: {e}", 'error')
    
    async def _process_system_message(self, header: Dict[str, Any]) -> None:
        """시스템 메시지 처리"""
        tr_cd = header.get('tr_cd', '')
        tr_key = header.get('tr_key', '')
        rsp_msg = header.get('rsp_msg', '')
        tr_type = header.get('tr_type', '')
        
        if tr_cd and tr_key:
            stock_info = self.vi_handler.data_manager.get_stock_info(tr_key)
            if stock_info:
                status = "구독" if tr_type == "3" else "구독해지" if tr_type == "4" else ""
                self.log(f">>> {stock_info.name}({tr_key}) {status} - {rsp_msg}")
            else:
                self.log(rsp_msg)
    
    async def _process_vi_message(self, data: Dict[str, Any]) -> None:
        """VI 메시지 처리"""
        await self.vi_handler.handle_vi_event(data)
    
    async def _process_trade_message(self, data: Dict[str, Any]) -> None:
        """체결 메시지 처리"""
        await self.vi_handler.handle_trade_data(data) 