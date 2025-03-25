"""주문 이벤트 처리 모듈"""
import logging
from typing import Dict, Optional, Callable
from src.core.base_handler import BaseHandler

logger = logging.getLogger(__name__)

class OrderEventHandler(BaseHandler):
    """주문 이벤트 처리 클래스"""
    
    def __init__(self, order_manager, callback: Optional[Callable] = None):
        """
        OrderEventHandler 초기화
        
        Args:
            order_manager: 주문 관리자 인스턴스
            callback: 주문 이벤트 발생 시 호출할 콜백 함수
        """
        super().__init__()
        self.order_manager = order_manager
        self.callback = callback
        
    async def handle_message(self, message: Dict) -> None:
        """
        주문 이벤트 메시지 처리
        
        Args:
            message: 수신된 메시지
        """
        try:
            event_type = message.get("event_type")
            
            if event_type == "ORDER_ACCEPTED":
                await self._handle_order_accepted(message)
            elif event_type == "ORDER_FILLED":
                await self._handle_order_filled(message)
            elif event_type == "ORDER_REJECTED":
                await self._handle_order_rejected(message)
            elif event_type == "ORDER_MODIFIED":
                await self._handle_order_modified(message)
            elif event_type == "ORDER_CANCELLED":
                await self._handle_order_cancelled(message)
            else:
                logger.warning(f"알 수 없는 주문 이벤트 타입: {event_type}")
                
            if self.callback:
                await self.callback(message)
                
        except Exception as e:
            logger.error(f"주문 이벤트 처리 중 오류 발생: {str(e)}")
            
    async def _handle_order_accepted(self, message: Dict) -> None:
        """
        주문 접수 이벤트 처리
        
        Args:
            message: 주문 접수 메시지
        """
        order_no = message.get("order_no")
        symbol = message.get("symbol")
        quantity = message.get("quantity")
        price = message.get("price")
        
        logger.info(f"주문 접수: 주문번호={order_no}, 종목={symbol}, 수량={quantity}, 가격={price}")
        
    async def _handle_order_filled(self, message: Dict) -> None:
        """
        주문 체결 이벤트 처리
        
        Args:
            message: 주문 체결 메시지
        """
        order_no = message.get("order_no")
        symbol = message.get("symbol")
        filled_quantity = message.get("filled_quantity")
        filled_price = message.get("filled_price")
        
        logger.info(f"주문 체결: 주문번호={order_no}, 종목={symbol}, 체결수량={filled_quantity}, 체결가격={filled_price}")
        
    async def _handle_order_rejected(self, message: Dict) -> None:
        """
        주문 거부 이벤트 처리
        
        Args:
            message: 주문 거부 메시지
        """
        order_no = message.get("order_no")
        symbol = message.get("symbol")
        reject_reason = message.get("reject_reason")
        
        logger.warning(f"주문 거부: 주문번호={order_no}, 종목={symbol}, 사유={reject_reason}")
        
    async def _handle_order_modified(self, message: Dict) -> None:
        """
        주문 정정 이벤트 처리
        
        Args:
            message: 주문 정정 메시지
        """
        order_no = message.get("order_no")
        symbol = message.get("symbol")
        modified_quantity = message.get("modified_quantity")
        modified_price = message.get("modified_price")
        
        logger.info(f"주문 정정: 주문번호={order_no}, 종목={symbol}, 정정수량={modified_quantity}, 정정가격={modified_price}")
        
    async def _handle_order_cancelled(self, message: Dict) -> None:
        """
        주문 취소 이벤트 처리
        
        Args:
            message: 주문 취소 메시지
        """
        order_no = message.get("order_no")
        symbol = message.get("symbol")
        cancelled_quantity = message.get("cancelled_quantity")
        
        logger.info(f"주문 취소: 주문번호={order_no}, 종목={symbol}, 취소수량={cancelled_quantity}")
        
    async def subscribe_order_events(self, account_no: str) -> None:
        """
        주문 이벤트 구독
        
        Args:
            account_no: 계좌번호
        """
        # WebSocket을 통한 주문 이벤트 구독 로직 구현
        pass
        
    async def unsubscribe_order_events(self, account_no: str) -> None:
        """
        주문 이벤트 구독 해제
        
        Args:
            account_no: 계좌번호
        """
        # WebSocket을 통한 주문 이벤트 구독 해제 로직 구현
        pass 