"""웹소켓 관리 모듈"""
import json
import asyncio
import websockets
from typing import Optional

from src.core.base_handler import BaseHandler
from config.settings import ls_config

class WebSocketManager(BaseHandler):
    """웹소켓 관리 클래스"""
    def __init__(self, url: str, token: str):
        super().__init__('WebSocketManager')
        self.url = url
        self.token = token
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = True
        self.reconnect_delay = ls_config.WebSocket.RECONNECT_DELAY
        self.max_reconnect_attempts = ls_config.WebSocket.MAX_RECONNECT_ATTEMPTS
        self.reconnect_count = 0
        
    async def connect(self) -> None:
        """웹소켓 연결"""
        try:
            async with websockets.connect(self.url) as ws:
                self.ws = ws
                self.log("웹소켓을 성공적으로 연결했습니다.")
                await self._handle_connection()
        except Exception as e:
            self.log(f"웹소켓 연결 실패: {e}", 'error')
            await self._handle_reconnection()
    
    async def _handle_connection(self) -> None:
        """웹소켓 연결 처리"""
        try:
            while self.is_running and self.ws:
                message = await self.ws.recv()
                await self.event_queue.put(message)
        except websockets.exceptions.ConnectionClosed:
            self.log("웹소켓 연결이 종료되었습니다.")
            await self._handle_reconnection()
        except Exception as e:
            self.log(f"웹소켓 처리 중 오류 발생: {e}", 'error')
            await self._handle_reconnection()
    
    async def _handle_reconnection(self) -> None:
        """재연결 처리"""
        if not self.is_running:
            return
            
        self.reconnect_count += 1
        if self.reconnect_count <= self.max_reconnect_attempts:
            self.log(f"{self.reconnect_delay}초 후 재연결을 시도합니다... (시도 {self.reconnect_count}/{self.max_reconnect_attempts})")
            await asyncio.sleep(self.reconnect_delay)
            await self.connect()
        else:
            self.log("최대 재연결 시도 횟수를 초과했습니다.")
            self.is_running = False
    
    async def send(self, message: dict) -> None:
        """메시지 전송"""
        if self.ws:
            try:
                await self.ws.send(json.dumps(message))
            except Exception as e:
                self.log(f"메시지 전송 중 오류 발생: {e}", 'error')
                await self._handle_reconnection()
    
    def cleanup(self) -> None:
        """정리 작업"""
        self.is_running = False
        if self.ws:
            asyncio.create_task(self.ws.close())