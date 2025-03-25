import os
import json
import asyncio
import websockets
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv, set_key
import csv
import logging
from logging.handlers import RotatingFileHandler
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Dict, Optional, List, Any
from dataclasses import dataclass
from collections import defaultdict
import aiohttp

# 환경 변수 로드
load_dotenv()

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

class BaseHandler(ABC):
    """기본 핸들러 클래스"""
    _logger = None  # 클래스 변수로 로거 객체 저장
    
    def __init__(self, logger_name: str):
        self.kst = pytz.timezone('Asia/Seoul')
        self.logger_name = logger_name
        if BaseHandler._logger is None:
            BaseHandler._logger = self._setup_logger()
        self.logger = BaseHandler._logger
    
    def _setup_logger(self) -> logging.Logger:
        """로거 설정"""
        logger = logging.getLogger('VIMonitor')
        logger.setLevel(logging.INFO)
        
        # 이미 핸들러가 있다면 추가하지 않음
        if logger.handlers:
            return logger
        
        # 오늘 날짜로 로그 파일명 생성
        today = datetime.now(self.kst).strftime('%Y%m%d')
        log_file = f'vi_monitor_{today}.log'
        
        # 포맷터 생성
        formatter = logging.Formatter('%(asctime)s [%(name)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        
        # 파일 핸들러 생성 (10MB 크기 제한, 최대 5개 파일 백업)
        file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # 콘솔 핸들러 생성
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # 핸들러 추가
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def log(self, message: str, level: str = 'info') -> None:
        """통합 로깅 메서드"""
        log_message = f"[{self.logger_name}] {message}"
        getattr(self.logger, level)(log_message)

class DataManager(BaseHandler):
    """데이터 관리 클래스"""
    def __init__(self):
        super().__init__('DataManager')
        self.stock_info: Dict[str, StockInfo] = {}
        self.vi_active_stocks: Dict[str, datetime] = {}
        self.unsubscribed_stocks: Dict[str, Dict[str, Any]] = {}
        self._vi_timers: Dict[str, asyncio.Task] = {}  # VI 타이머 태스크 저장
    
    @lru_cache(maxsize=1000)
    def get_stock_info(self, stock_code: str) -> Optional[StockInfo]:
        """종목 정보 조회 (캐시 적용)"""
        return self.stock_info.get(stock_code)
    
    def add_vi_stock(self, stock_code: str) -> None:
        """VI 발동 종목 추가"""
        current_time = datetime.now(self.kst)
        self.vi_active_stocks[stock_code] = current_time
        self.log(f"VI 발동 종목 추가: {stock_code} (발동시각: {current_time.strftime('%H:%M:%S')})")
    
    def remove_vi_stock(self, stock_code: str) -> None:
        """VI 발동 종목 제거"""
        if stock_code in self.vi_active_stocks:
            activation_time = self.vi_active_stocks.pop(stock_code)
            deactivation_time = datetime.now(self.kst)
            self.unsubscribed_stocks[stock_code] = {
                'activation_time': activation_time,
                'deactivation_time': deactivation_time,
                'status': '해지완료'
            }
            self.log(f"VI 발동 종목 제거: {stock_code} (해제시각: {deactivation_time.strftime('%H:%M:%S')})")
            
            # 타이머 취소
            if stock_code in self._vi_timers:
                self._vi_timers[stock_code].cancel()
                del self._vi_timers[stock_code]
    
    def is_vi_active(self, stock_code: str) -> bool:
        """VI 발동 상태 확인"""
        return stock_code in self.vi_active_stocks
    
    def get_active_stocks(self) -> List[str]:
        """현재 활성화된 VI 종목 목록 반환"""
        return list(self.vi_active_stocks.keys())
    
    async def start_vi_timer(self, stock_code: str, callback) -> None:
        """VI 타이머 시작"""
        if stock_code in self._vi_timers:
            self._vi_timers[stock_code].cancel()
        
        # 3분 타이머 시작
        timer = asyncio.create_task(self._vi_timer(stock_code, callback))
        self._vi_timers[stock_code] = timer
    
    async def _vi_timer(self, stock_code: str, callback) -> None:
        """VI 타이머 실행"""
        try:
            await asyncio.sleep(180)  # 3분 대기
            if stock_code in self.vi_active_stocks:
                await callback(stock_code)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.log(f"VI 타이머 실행 중 오류 발생: {e}", 'error')
        finally:
            if stock_code in self._vi_timers:
                del self._vi_timers[stock_code]

class WebSocketManager(BaseHandler):
    """웹소켓 관리 클래스"""
    def __init__(self, url: str, token: str):
        super().__init__('WebSocketManager')
        self.url = url
        self.token = token
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = True
        self.reconnect_delay = 5
        self.max_reconnect_attempts = 5
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
            
class MessageProcessor(BaseHandler):
    """메시지 처리 클래스"""
    def __init__(self, data_manager: DataManager, ws_manager: WebSocketManager):
        super().__init__('MessageProcessor')
        self.data_manager = data_manager
        self.ws_manager = ws_manager
        
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
                self._process_system_message(header)
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
    
    def _process_system_message(self, header: dict) -> None:
        """시스템 메시지 처리"""
        tr_cd = header.get('tr_cd', '')
        tr_key = header.get('tr_key', '')
        rsp_msg = header.get('rsp_msg', '')
        tr_type = header.get('tr_type', '')
        
        if tr_cd and tr_key:
            stock_info = self.data_manager.get_stock_info(tr_key)
            if stock_info:
                status = "구독" if tr_type == "3" else "구독해지" if tr_type == "4" else ""
                self.log(f">>> {stock_info.name}({tr_key}) {status} - {rsp_msg}")
            else:
                self.log(rsp_msg)
                
    async def _process_vi_message(self, data: dict) -> None:
        """VI 메시지 처리"""
        body = data.get("body", {})
        stock_code = body.get('ref_shcode')
        vi_gubun = body.get("vi_gubun", "0")
        
        if not stock_code:
            return
            
        stock_info = self.data_manager.get_stock_info(stock_code)
        if not stock_info:
            return
            
        # VI 발동 처리
        if vi_gubun in ["1", "2", "3"] and not self.data_manager.is_vi_active(stock_code):
            self.data_manager.add_vi_stock(stock_code)
            await self._subscribe_trade_data(stock_code, stock_info.market)
            
            # 3분 타이머 시작
            await self.data_manager.start_vi_timer(
                stock_code,
                lambda code: self._unsubscribe_trade_data(code, stock_info.market)
            )
            
    async def _process_trade_message(self, data: dict) -> None:
        """체결 메시지 처리"""
        body = data.get("body", {})
        stock_code = body.get("shcode")
        
        if not stock_code or not self.data_manager.is_vi_active(stock_code):
            return
            
        stock_info = self.data_manager.get_stock_info(stock_code)
        if not stock_info:
            return
            
        # 체결 정보 출력
        current_time = datetime.now(self.kst)
        self.log(f"[{current_time.strftime('%H:%M:%S')}] 체결 | {stock_info.name}({stock_code}) | "
                f"{body.get('price'):>7}원 | {body.get('cvolume'):>6}주")
    
    async def _subscribe_trade_data(self, stock_code: str, market: str) -> None:
        """체결 정보 구독"""
        tr_cd = "S3_" if market == "KOSPI" else "K3_"
        message = {
            "header": {
                "token": self.ws_manager.token,
                "tr_type": "3"
            },
            "body": {
                "tr_cd": tr_cd,
                "tr_key": stock_code
            }
        }
        await self.ws_manager.send(message)
        
    async def _unsubscribe_trade_data(self, stock_code: str, market: str) -> None:
        """체결 정보 구독 해제"""
        tr_cd = "S3_" if market == "KOSPI" else "K3_"
        message = {
            "header": {
                "token": self.ws_manager.token,
                "tr_type": "4"
            },
            "body": {
                "tr_cd": tr_cd,
                "tr_key": stock_code
            }
        }
        await self.ws_manager.send(message)

class TokenManager(BaseHandler):
    """토큰 관리 클래스"""
    def __init__(self, api_key, api_secret, kst):
        super().__init__('TokenManager')
        self.api_key = api_key
        self.api_secret = api_secret
        self.token_url = "https://openapi.ls-sec.co.kr:8080/oauth2/token"
        self.token = None
        self.token_expires_at = None
        self.kst = kst
    
    def save_token_to_env(self, token, expires_in):
        """토큰 정보를 .env 파일에 저장"""
        current_time = datetime.now(self.kst)
        expires_at = current_time + timedelta(seconds=expires_in)
        
        # 토큰 정보를 .env 파일에 저장
        set_key('.env', 'LS_ACCESS_TOKEN', token)
        set_key('.env', 'LS_TOKEN_EXPIRES_AT', expires_at.isoformat())
        
        self.token = token
        self.token_expires_at = expires_at
        self.log(f"토큰 정보가 .env 파일에 저장되었습니다. (만료일시: {expires_at.strftime('%Y-%m-%d %H:%M:%S %Z')})")
    
    def is_token_valid(self):
        """저장된 토큰의 유효성 검사"""
        saved_token = os.getenv('LS_ACCESS_TOKEN')
        saved_expires_at = os.getenv('LS_TOKEN_EXPIRES_AT')
        
        if not saved_token or not saved_expires_at:
            return False
            
        try:
            # 저장된 만료 시간을 파싱
            expires_at = datetime.fromisoformat(saved_expires_at)
            
            # 현재 시간을 KST로 변환
            current_time = datetime.now(self.kst)
            
            # naive datetime을 aware datetime으로 변환
            if expires_at.tzinfo is None:
                expires_at = self.kst.localize(expires_at)
            
            # 만료 5분 전부터는 갱신 필요
            if expires_at - timedelta(minutes=5) <= current_time:
                return False
                
            self.token = saved_token
            self.token_expires_at = expires_at
            return True
        except Exception as e:
            self.log(f"토큰 유효성 검사 중 오류 발생: {e}", 'error')
            return False
        
    async def get_access_token(self):
        """접근 토큰 발급"""
        # 저장된 토큰이 유효한지 확인
        if self.is_token_valid():
            self.log("유효한 토큰이 이미 저장되어 있습니다.")
            return self.token
            
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "client_credentials",
            "appkey": self.api_key,
            "appsecretkey": self.api_secret,
            "scope": "oob"
        }
        
        self.log("\n토큰 발급 요청 정보:")
        self.log(f"URL: {self.token_url}")
        self.log(f"Headers: {headers}")
        self.log(f"Data: {data}")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.token_url, headers=headers, data=data) as response:
                    self.log(f"\n응답 상태 코드: {response.status}")
                    result = await response.json()
                    self.log(f"응답 데이터: {json.dumps(result, indent=2)}")
                    
                    if response.status == 200:
                        token = result.get("access_token")
                        expires_in = result.get("expires_in")
                        self.save_token_to_env(token, expires_in)
                        return token
                    else:
                        error_msg = f"\n토큰 발급 실패: {result.get('error_description', '알 수 없는 오류')}"
                        self.log(error_msg, 'error')
                        raise Exception(error_msg)
                        
            except Exception as e:
                error_msg = f"\n토큰 발급 중 오류 발생: {str(e)}"
                self.log(error_msg, 'error')
                raise

class VIEventHandler(BaseHandler):
    """VI 이벤트 처리 및 체결 구독 관리 클래스"""
    def __init__(self, token, ws, kst, stock_info):
        super().__init__('VIEventHandler')
        self.token = token
        self.ws = ws
        self.kst = kst
        self.stock_info = stock_info
        self.vi_active_stocks = {}  # VI 발동된 종목 코드와 발동 시각 저장
        self.unsubscribed_stocks = {}  # 해지 완료된 종목 정보 저장
        self.event_loop = None  # 이벤트 루프 저장
        self.is_reconnecting = False  # 재연결 중 여부
    
    def get_tr_cd(self, market_type):
        """시장 구분을 tr_cd로 변환"""
        return "S3_" if market_type == "KOSPI" else "K3_" if market_type == "KOSDAQ" else market_type

    def handle_vi_event(self, vi_data):
        """VI 이벤트 처리"""
        body = vi_data.get("body", {})
        current_time = datetime.now(self.kst)
        timestamp = current_time.strftime("%H:%M:%S")
        
        vi_gubun = body.get("vi_gubun", "0")
        vi_status = {
            "0": "해제",
            "1": "정적발동",
            "2": "동적발동",
            "3": "정적&동적"
        }.get(vi_gubun, "알 수 없음")
        
        stock_code = body.get('ref_shcode')
        stock_info = self.stock_info.get(stock_code, {})
        market_type = stock_info.get('market', 'KOSPI')
        tr_cd = self.get_tr_cd(market_type)
        stock_name = stock_info.get('name', '알 수 없음')
        
        # VI 상태 정보를 한 줄로 출력
        vi_message = f"[{timestamp}] [VI {vi_status}] {market_type} | {stock_name}({stock_code}) | 기준가: {body.get('vi_trgprice')} | 발동시각: {body.get('time')}"
        self.log(vi_message)
        
        # VI 발동된 경우 체결 정보 구독
        if vi_gubun in ["1", "2", "3"] and stock_code not in self.vi_active_stocks:
            self.vi_active_stocks[stock_code] = current_time
            self.subscribe_trade_data(stock_code, tr_cd)
            sub_message = f">>> {market_type} {stock_name}({stock_code}) 종목 체결 정보 구독 시작"
            self.log(sub_message)
            
            # 3분 후 자동 구독 취소를 위한 타이머 시작
            if self.event_loop:
                asyncio.run_coroutine_threadsafe(
                    self.delayed_unsubscribe_after_3min(stock_code, market_type, stock_name),
                    self.event_loop
                )
            else:
                self.log("이벤트 루프가 설정되지 않았습니다.", 'error')

    def handle_trade_data(self, trade_data, market_type):
        """체결 데이터 처리"""
        body = trade_data.get("body", {})
        stock_code = body.get("shcode")
        current_time = datetime.now(self.kst)
        timestamp = current_time.strftime("%H:%M:%S")
        
        # 구독된 종목의 체결 정보만 출력
        if stock_code in self.vi_active_stocks:
            stock_info = self.stock_info.get(stock_code, {})
            stock_name = stock_info.get('name', '알 수 없음')
            
            # 체결 정보를 간단하게 출력
            trade_message = f"[{timestamp}] 체결 | {stock_name}({stock_code}) | {body.get('price'):>7}원 | {body.get('cvolume'):>6}주"
            self.log(trade_message)

    async def delayed_unsubscribe_after_3min(self, stock_code, market_type, stock_name):
        """3분 후에 구독 취소"""
        try:
            self.log(f">>> {market_type} {stock_name}({stock_code}) 종목 3분 타이머 시작")
            await asyncio.sleep(180)  # 3분 대기
            
            if stock_code in self.vi_active_stocks:
                self.log(f">>> {market_type} {stock_name}({stock_code}) 종목 3분 경과")
                
                # 해지 완료 정보 저장
                activation_time = self.vi_active_stocks[stock_code]
                deactivation_time = datetime.now(self.kst)
                self.unsubscribed_stocks[stock_code] = {
                    'activation_time': activation_time,
                    'deactivation_time': deactivation_time
                }
                
                # 활성 목록에서 제거
                del self.vi_active_stocks[stock_code]
                tr_cd = self.get_tr_cd(market_type)
                self.unsubscribe_trade_data(stock_code, tr_cd)
                
                unsub_message = f">>> {market_type} {stock_name}({stock_code}) 종목 체결 정보 구독 해제 (3분 경과)"
                self.log(unsub_message)
            else:
                self.log(f">>> {market_type} {stock_name}({stock_code}) 종목은 이미 구독이 취소되었습니다.")
        except Exception as e:
            self.log(f"구독 취소 지연 처리 중 오류 발생: {e}", 'error')

    def update_websocket(self, ws):
        """웹소켓 객체 업데이트"""
        if ws is None:
            self.log("웹소켓 객체가 None입니다.", 'error')
            return False
            
        try:
            self.ws = ws
            self.is_reconnecting = True
            
            # 재연결 시 활성화된 VI 종목들의 체결 정보 재구독
            for stock_code in list(self.vi_active_stocks.keys()):
                stock_info = self.stock_info.get(stock_code, {})
                market_type = stock_info.get('market', 'KOSPI')
                tr_cd = self.get_tr_cd(market_type)
                self.subscribe_trade_data(stock_code, tr_cd)
                
            self.is_reconnecting = False
            return True
        except Exception as e:
            self.log(f"웹소켓 업데이트 중 오류 발생: {e}", 'error')
            self.is_reconnecting = False
            return False

    def subscribe_trade_data(self, stock_code, market_type):
        """체결 정보 구독"""
        if self.ws is None:
            self.log(f"웹소켓 연결이 없습니다. {stock_code} 종목 구독을 건너뜁니다.", 'error')
            return
            
        try:
            subscribe_message = {
                "header": {
                    "token": self.token,
                    "tr_type": "3"  # 실시간 시세 등록
                },
                "body": {
                    "tr_cd": market_type,  # KOSPI 또는 KOSDAQ 체결 정보
                    "tr_key": stock_code
                }
            }
            
            self.ws.send(json.dumps(subscribe_message))
            if not self.is_reconnecting:
                self.log(f">>> 현재 구독 중인 종목 수: {len(self.vi_active_stocks)}개 ({', '.join(sorted(self.vi_active_stocks))})")
        except Exception as e:
            self.log(f"구독 요청 중 오류 발생: {e}", 'error')

    def unsubscribe_trade_data(self, stock_code, market_type):
        """체결 정보 구독 해제"""
        if self.ws is None:
            self.log(f"웹소켓 연결이 없습니다. {stock_code} 종목 구독 해제를 건너뜁니다.", 'error')
            return
            
        try:
            unsubscribe_message = {
                "header": {
                    "token": self.token,
                    "tr_type": "4"  # 실시간 시세 해제
                },
                "body": {
                    "tr_cd": market_type,  # KOSPI 또는 KOSDAQ 체결 정보
                    "tr_key": stock_code
                }
            }
            
            self.ws.send(json.dumps(unsubscribe_message))
            if not self.is_reconnecting:
                self.log(f">>> 현재 구독 중인 종목 수: {len(self.vi_active_stocks)}개 ({', '.join(sorted(self.vi_active_stocks))})")
        except Exception as e:
            self.log(f"구독 해제 요청 중 오류 발생: {e}", 'error')

    def cleanup(self):
        """프로그램 종료 시 정리 작업"""
        self.log("구독 정리 작업 시작...")
        
        # VI 발동된 모든 종목의 체결 정보 구독 해제
        for stock_code in list(self.vi_active_stocks.keys()):
            market_type = self.stock_info.get(stock_code, {}).get('market', 'KOSPI')
            tr_cd = self.get_tr_cd(market_type)
            self.unsubscribe_trade_data(stock_code, tr_cd)
        
        self.log("구독 정리 작업 완료")

class VIMonitor(BaseHandler):
    """VI 모니터링 메인 클래스"""
    def __init__(self):
        super().__init__('VIMonitor')
        self.api_key = os.getenv('LS_APP_KEY')
        self.api_secret = os.getenv('LS_SECRET_KEY')
        self.ws_url = "wss://openapi.ls-sec.co.kr:9443/websocket"
        self.api_url = "https://openapi.ls-sec.co.kr:8080"
        self.is_running = True
        
        # 컴포넌트 초기화
        self.token_manager = TokenManager(self.api_key, self.api_secret, self.kst)
        self.data_manager = DataManager()
        self.ws_manager = None
        self.message_processor = None
        
    async def initialize(self) -> None:
        """초기화"""
        try:
            # 토큰 발급
            self.token = await self.token_manager.get_access_token()
            if not self.token:
                raise Exception("토큰 발급 실패")
            
            # 종목 정보 조회
            await self.load_stock_info()
            
            # 웹소켓 매니저 초기화
            self.ws_manager = WebSocketManager(self.ws_url, self.token)
            
            # 메시지 프로세서 초기화
            self.message_processor = MessageProcessor(self.data_manager, self.ws_manager)
            
        except Exception as e:
            self.log(f"초기화 중 오류 발생: {e}", 'error')
            raise
    
    async def load_stock_info(self) -> None:
        """종목 정보 로드"""
        today = datetime.now(self.kst).strftime('%Y%m%d')
        csv_file = f'stocks_info_{today}.csv'
        
        if os.path.exists(csv_file):
            self.log(f"오늘({today}) 저장된 종목 정보 파일을 불러옵니다.")
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.data_manager.stock_info[row['종목코드']] = StockInfo(
                        name=row['종목명'],
                        market=row['시장구분'],
                        etf=row['ETF구분'] == 'True',
                        upper_limit=int(row['상한가']),
                        lower_limit=int(row['하한가']),
                        prev_close=int(row['전일가']),
                        base_price=int(row['기준가'])
                    )
            return
        
        # API로 종목 정보 조회
        url = f"{self.api_url}/stock/etc"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.token}",
            "tr_cd": "t8430",
            "tr_cont": "N",
            "tr_cont_key": "",
            "mac_address": "000000000000"
        }
        
        request_data = {
            "t8430InBlock": {
                "gubun": "0"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=request_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        stock_list = result.get("t8430OutBlock", [])
                        
                        # 종목 정보 저장
                        for stock in stock_list:
                            market = "KOSPI" if stock["gubun"] == "1" else "KOSDAQ"
                            self.data_manager.stock_info[stock["shcode"]] = StockInfo(
                                name=stock["hname"],
                                market=market,
                                etf=stock["etfgubun"] == "1",
                                upper_limit=stock["uplmtprice"],
                                lower_limit=stock["dnlmtprice"],
                                prev_close=stock["jnilclose"],
                                base_price=stock["recprice"]
                            )
                        
                        # CSV 파일로 저장
                        self.save_stock_info_to_csv(csv_file)
                    else:
                        raise Exception(f"종목 정보 조회 실패: {response.status}")
            except Exception as e:
                self.log(f"종목 정보 조회 중 오류 발생: {e}", 'error')
                raise
    
    def save_stock_info_to_csv(self, csv_file: str) -> None:
        """종목 정보를 CSV 파일로 저장"""
        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
            fieldnames = ['종목코드', '종목명', '시장구분', 'ETF구분', '상한가', '하한가', '전일가', '기준가']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for code, info in self.data_manager.stock_info.items():
                writer.writerow({
                    '종목코드': code,
                    '종목명': info.name,
                    '시장구분': info.market,
                    'ETF구분': info.etf,
                    '상한가': info.upper_limit,
                    '하한가': info.lower_limit,
                    '전일가': info.prev_close,
                    '기준가': info.base_price
                })
    
    async def start(self) -> None:
        """모니터링 시작"""
        try:
            await self.initialize()
            
            # 웹소켓 연결 시작
            await self.ws_manager.connect()
            
            # 메시지 처리 루프
            while self.is_running:
                try:
                    message = await self.ws_manager.event_queue.get()
                    await self.message_processor.process_message(message)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.log(f"메시지 처리 중 오류 발생: {e}", 'error')
                    
        except Exception as e:
            self.log(f"모니터링 중 오류 발생: {e}", 'error')
        finally:
            self.cleanup()
    
    def cleanup(self) -> None:
        """정리 작업"""
        self.log("프로그램 종료 중...")
        self.is_running = False
        
        if self.ws_manager:
            self.ws_manager.cleanup()
        
        self.log("프로그램이 종료되었습니다.")

async def main():
    """메인 함수"""
    monitor = VIMonitor()
    try:
        await monitor.start()
    except KeyboardInterrupt:
        print("키보드 인터럽트가 감지되었습니다.")
        monitor.cleanup()
    except Exception as e:
        print(f"예상치 못한 오류가 발생했습니다: {e}")
        monitor.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("프로그램이 종료되었습니다.") 