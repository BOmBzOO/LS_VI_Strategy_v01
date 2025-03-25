import os
import json
import asyncio
import websocket
import aiohttp
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv, set_key
import csv
import logging
from logging.handlers import RotatingFileHandler

# 환경 변수 로드
load_dotenv()

class VIEventHandler:
    """VI 이벤트 처리 및 체결 구독 관리 클래스"""
    def __init__(self, token, ws, kst, stock_info):
        self.token = token
        self.ws = ws
        self.kst = kst
        self.stock_info = stock_info
        self.vi_active_stocks = {}  # VI 발동된 종목 코드와 발동 시각 저장
        self.unsubscribed_stocks = {}  # 해지 완료된 종목 정보 저장
        self.event_loop = None  # 이벤트 루프 저장
        self.is_reconnecting = False  # 재연결 중 여부
        
        # 로거 설정
        self.logger = logging.getLogger('VIEventHandler')
        
    def log_and_print(self, message, level='info'):
        """로그 출력 및 저장"""
        if level == 'info':
            self.logger.info(message)
        elif level == 'error':
            self.logger.error(message)
        elif level == 'warning':
            self.logger.warning(message)
        elif level == 'debug':
            self.logger.debug(message)

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
        self.log_and_print(vi_message)
        
        # VI 발동된 경우 체결 정보 구독
        if vi_gubun in ["1", "2", "3"] and stock_code not in self.vi_active_stocks:
            self.vi_active_stocks[stock_code] = current_time
            self.subscribe_trade_data(stock_code, tr_cd)
            sub_message = f">>> {market_type} {stock_name}({stock_code}) 종목 체결 정보 구독 시작"
            self.log_and_print(sub_message)
            
            # 3분 후 자동 구독 취소를 위한 타이머 시작
            if self.event_loop:
                asyncio.run_coroutine_threadsafe(
                    self.delayed_unsubscribe_after_3min(stock_code, market_type, stock_name),
                    self.event_loop
                )
            else:
                self.log_and_print("이벤트 루프가 설정되지 않았습니다.", level='error')

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
            self.log_and_print(trade_message)

    async def delayed_unsubscribe_after_3min(self, stock_code, market_type, stock_name):
        """3분 후에 구독 취소"""
        try:
            self.log_and_print(f">>> {market_type} {stock_name}({stock_code}) 종목 3분 타이머 시작")
            await asyncio.sleep(180)  # 3분 대기
            
            if stock_code in self.vi_active_stocks:
                self.log_and_print(f">>> {market_type} {stock_name}({stock_code}) 종목 3분 경과")
                
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
                self.log_and_print(unsub_message)
            else:
                self.log_and_print(f">>> {market_type} {stock_name}({stock_code}) 종목은 이미 구독이 취소되었습니다.")
        except Exception as e:
            self.log_and_print(f"구독 취소 지연 처리 중 오류 발생: {e}", level='error')

    def update_websocket(self, ws):
        """웹소켓 객체 업데이트"""
        if ws is None:
            self.log_and_print("웹소켓 객체가 None입니다.", level='error')
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
            self.log_and_print(f"웹소켓 업데이트 중 오류 발생: {e}", level='error')
            self.is_reconnecting = False
            return False

    def subscribe_trade_data(self, stock_code, market_type):
        """체결 정보 구독"""
        if self.ws is None:
            self.log_and_print(f"웹소켓 연결이 없습니다. {stock_code} 종목 구독을 건너뜁니다.", level='error')
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
                self.log_and_print(f">>> 현재 구독 중인 종목 수: {len(self.vi_active_stocks)}개 ({', '.join(sorted(self.vi_active_stocks))})")
        except Exception as e:
            self.log_and_print(f"구독 요청 중 오류 발생: {e}", level='error')

    def unsubscribe_trade_data(self, stock_code, market_type):
        """체결 정보 구독 해제"""
        if self.ws is None:
            self.log_and_print(f"웹소켓 연결이 없습니다. {stock_code} 종목 구독 해제를 건너뜁니다.", level='error')
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
                self.log_and_print(f">>> 현재 구독 중인 종목 수: {len(self.vi_active_stocks)}개 ({', '.join(sorted(self.vi_active_stocks))})")
        except Exception as e:
            self.log_and_print(f"구독 해제 요청 중 오류 발생: {e}", level='error')

    def cleanup(self):
        """프로그램 종료 시 정리 작업"""
        self.log_and_print("구독 정리 작업 시작...")
        
        # VI 발동된 모든 종목의 체결 정보 구독 해제
        for stock_code in list(self.vi_active_stocks.keys()):
            market_type = self.stock_info.get(stock_code, {}).get('market', 'KOSPI')
            tr_cd = self.get_tr_cd(market_type)
            self.unsubscribe_trade_data(stock_code, tr_cd)
        
        self.log_and_print("구독 정리 작업 완료")

class TokenManager:
    """토큰 관리 클래스"""
    def __init__(self, api_key, api_secret, kst):
        self.api_key = api_key
        self.api_secret = api_secret
        self.token_url = "https://openapi.ls-sec.co.kr:8080/oauth2/token"
        self.token = None
        self.token_expires_at = None
        self.kst = kst
        
        # 로거 설정
        self.logger = logging.getLogger('TokenManager')
        
    def log_and_print(self, message, level='info'):
        """로그 출력 및 저장"""
        if level == 'info':
            self.logger.info(message)
        elif level == 'error':
            self.logger.error(message)
        elif level == 'warning':
            self.logger.warning(message)
        elif level == 'debug':
            self.logger.debug(message)

    def save_token_to_env(self, token, expires_in):
        """토큰 정보를 .env 파일에 저장"""
        current_time = datetime.now(self.kst)
        expires_at = current_time + timedelta(seconds=expires_in)
        
        # 토큰 정보를 .env 파일에 저장
        set_key('.env', 'LS_ACCESS_TOKEN', token)
        set_key('.env', 'LS_TOKEN_EXPIRES_AT', expires_at.isoformat())
        
        self.token = token
        self.token_expires_at = expires_at
        self.log_and_print(f"토큰 정보가 .env 파일에 저장되었습니다. (만료일시: {expires_at.strftime('%Y-%m-%d %H:%M:%S %Z')})")
    
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
            self.log_and_print(f"토큰 유효성 검사 중 오류 발생: {e}")
            return False
        
    async def get_access_token(self):
        """접근 토큰 발급"""
        # 저장된 토큰이 유효한지 확인
        if self.is_token_valid():
            self.log_and_print("유효한 토큰이 이미 저장되어 있습니다.")
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
        
        self.log_and_print("\n토큰 발급 요청 정보:")
        self.log_and_print(f"URL: {self.token_url}")
        self.log_and_print(f"Headers: {headers}")
        self.log_and_print(f"Data: {data}")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.token_url, headers=headers, data=data) as response:
                    self.log_and_print(f"\n응답 상태 코드: {response.status}")
                    result = await response.json()
                    self.log_and_print(f"응답 데이터: {json.dumps(result, indent=2)}")
                    
                    if response.status == 200:
                        token = result.get("access_token")
                        expires_in = result.get("expires_in")
                        self.save_token_to_env(token, expires_in)
                        return token
                    else:
                        self.log_and_print(f"\n토큰 발급 실패: {result.get('error_description', '알 수 없는 오류')}")
                        raise Exception(f"토큰 발급 실패: {result.get('error_description', '알 수 없는 오류')}")
                        
            except Exception as e:
                self.log_and_print(f"\n토큰 발급 중 오류 발생: {str(e)}")
                raise

class VIMonitor:
    def __init__(self):
        self.api_key = os.getenv('LS_APP_KEY')
        self.api_secret = os.getenv('LS_SECRET_KEY')
        self.ws_url = "wss://openapi.ls-sec.co.kr:9443/websocket"  # 운영 도메인
        self.api_url = "https://openapi.ls-sec.co.kr:8080"  # API 기본 URL
        self.kst = pytz.timezone('Asia/Seoul')
        self.ws = None  # 웹소켓 객체 저장
        self.is_running = True  # 프로그램 실행 상태 플래그
        self.stock_info = {}  # 종목 정보 저장
        self.event_handler = None  # VI 이벤트 핸들러
        self.reconnect_delay = 5  # 재연결 대기 시간 (초)
        self.max_reconnect_attempts = 5  # 최대 재연결 시도 횟수
        self.reconnect_count = 0  # 현재 재연결 시도 횟수
        self.is_reconnecting = False  # 재연결 중 여부
        
        # 토큰 매니저 초기화
        self.token_manager = TokenManager(self.api_key, self.api_secret, self.kst)
        self.token = None
        
        # 로거 설정
        self.setup_logger()

    def setup_logger(self):
        """로거 설정"""
        today = datetime.now(self.kst).strftime('%Y%m%d')
        log_file = f'log_{today}.txt'
        
        # 로거 생성
        self.logger = logging.getLogger('VIMonitor')
        self.logger.setLevel(logging.INFO)
        
        # 포맷터 생성
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        
        # 파일 핸들러 생성 (10MB 크기 제한, 최대 5개 파일 백업)
        file_handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # 콘솔 핸들러 생성
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # 핸들러 추가
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
        
        self.logger.info("VI 모니터링 프로그램이 시작되었습니다.")

    def log_and_print(self, message, level='info'):
        """로그 출력 및 저장"""
        if level == 'info':
            self.logger.info(message)
        elif level == 'error':
            self.logger.error(message)
        elif level == 'warning':
            self.logger.warning(message)
        elif level == 'debug':
            self.logger.debug(message)

    async def get_stock_info(self):
        """전체 종목 정보 조회"""
        # 오늘 날짜로 파일명 생성 (YYYYMMDD 형식)
        today = datetime.now(self.kst).strftime('%Y%m%d')
        csv_file = f'stocks_info_{today}.csv'

        if os.path.exists(csv_file):
            self.log_and_print(f"오늘({today}) 저장된 종목 정보 파일을 불러옵니다.")
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # CSV에서 읽은 문자열 값을 적절한 타입으로 변환
                    self.stock_info[row['종목코드']] = {
                        'name': row['종목명'],
                        'market': row['시장구분'],
                        'etf': row['ETF구분'] == 'True',
                        'upper_limit': int(row['상한가']),
                        'lower_limit': int(row['하한가']),
                        'prev_close': int(row['전일가']),
                        'base_price': int(row['기준가'])
                    }
            return

        # 종목 정보 조회 URL
        url = f"{self.api_url}/stock/etc"

        # 요청 헤더
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {self.token}",
            "tr_cd": "t8430",
            "tr_cont": "N",
            "tr_cont_key": "",
            "mac_address": "000000000000"  # 개인용은 기본값 사용
        }

        # 요청 바디
        request_data = {
            "t8430InBlock": {
                "gubun": "0"  # 0: 전체, 1: 코스피, 2: 코스닥
            }
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, headers=headers, json=request_data) as response:
                    self.log_and_print(f"\n종목 정보 조회 응답 상태: {response.status}")
                    if response.status == 200:
                        result = await response.json()
                        stock_list = result.get("t8430OutBlock", [])
                        
                        # 종목 정보 저장
                        for stock in stock_list:
                            market = "KOSPI" if stock["gubun"] == "1" else "KOSDAQ"
                            self.stock_info[stock["shcode"]] = {
                                "name": stock["hname"],
                                "market": market,
                                "etf": stock["etfgubun"] == "1",
                                "upper_limit": stock["uplmtprice"],
                                "lower_limit": stock["dnlmtprice"],
                                "prev_close": stock["jnilclose"],
                                "base_price": stock["recprice"]
                            }
                        
                        # 종목 정보를 CSV 파일로 저장
                        with open(csv_file, 'w', encoding='utf-8', newline='') as f:
                            fieldnames = ['종목코드', '종목명', '시장구분', 'ETF구분', '상한가', '하한가', '전일가', '기준가']
                            writer = csv.DictWriter(f, fieldnames=fieldnames)
                            writer.writeheader()
                            
                            for code, info in self.stock_info.items():
                                writer.writerow({
                                    '종목코드': code,
                                    '종목명': info['name'],
                                    '시장구분': info['market'],
                                    'ETF구분': info['etf'],
                                    '상한가': info['upper_limit'],
                                    '하한가': info['lower_limit'],
                                    '전일가': info['prev_close'],
                                    '기준가': info['base_price']
                                })
                        
                        self.log_and_print(f"전체 {len(self.stock_info)}개 종목 정보를 CSV 파일로 저장했습니다.")
                        self.log_and_print(f"- KOSPI: {sum(1 for info in self.stock_info.values() if info['market'] == 'KOSPI')}개")
                        self.log_and_print(f"- KOSDAQ: {sum(1 for info in self.stock_info.values() if info['market'] == 'KOSDAQ')}개")
                    else:
                        self.log_and_print(f"종목 정보 조회 실패: {response.status}")
                        error_text = await response.text()
                        self.log_and_print(f"에러 응답: {error_text}")
                        raise Exception(f"종목 정보 조회 실패: {response.status}")
                        
            except Exception as e:
                self.log_and_print(f"종목 정보 조회 중 오류 발생: {e}")
                raise

    async def create_websocket(self):
        """웹소켓 객체 생성"""
        websocket_headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        def on_message(ws, message):
            try:
                data = json.loads(message)
                self.log_and_print(f"메시지 수신: {message}")
                
                # 헤더와 바디가 있는지 확인
                if not isinstance(data, dict):
                    self.log_and_print("잘못된 메시지 형식입니다.")
                    return
                    
                header = data.get("header", {})
                body = data.get("body", {})
                
                if not body:
                    if header:
                        tr_cd = header.get('tr_cd', '')
                        tr_key = header.get('tr_key', '')
                        rsp_msg = header.get('rsp_msg', '')
                        tr_type = header.get('tr_type', '')
                        
                        # 종목 정보 가져오기
                        stock_info = self.stock_info.get(tr_key, {})
                        stock_name = stock_info.get('name', '알 수 없음')
                        
                        # 구독/구독해지 상태 확인
                        status = "구독" if tr_type == "3" else "구독해지" if tr_type == "4" else ""
                        
                        if tr_cd and tr_key and status:
                            self.log_and_print(f">>> {stock_name}({tr_key}) {status} - {rsp_msg}")
                        else:
                            self.log_and_print(rsp_msg)
                    return
                    
                # VI 메시지인지 확인
                if header.get("tr_cd") == "VI_":
                    self.event_handler.handle_vi_event(data)
                # KOSPI 체결 정보 메시지인지 확인
                elif header.get("tr_cd") == "S3_":
                    self.event_handler.handle_trade_data(data, "S3_")
                # KOSDAQ 체결 정보 메시지인지 확인
                elif header.get("tr_cd") == "K3_":
                    self.event_handler.handle_trade_data(data, "K3_")
                
            except json.JSONDecodeError as e:
                self.log_and_print(f"JSON 파싱 오류: {e}")
                self.log_and_print(f"원본 메시지: {message}")
            except Exception as e:
                self.log_and_print(f"메시지 처리 중 오류 발생: {e}")
        
        def on_error(ws, error):
            self.log_and_print(f"웹소켓 에러 발생: {error}")
            if hasattr(error, 'status_code'):
                self.log_and_print(f"상태 코드: {error.status_code}")
            if hasattr(error, 'reason'):
                self.log_and_print(f"사유: {error.reason}")
        
        def on_close(ws, close_status_code, close_msg):
            self.log_and_print(f"웹소켓 연결이 종료되었습니다. (상태 코드: {close_status_code}, 메시지: {close_msg})")
            if self.is_running:
                self.reconnect_count += 1
                if self.reconnect_count <= self.max_reconnect_attempts:
                    self.log_and_print(f"{self.reconnect_delay}초 후 재연결을 시도합니다... (시도 {self.reconnect_count}/{self.max_reconnect_attempts})")
                    asyncio.get_event_loop().call_later(self.reconnect_delay, self.reconnect_websocket)
                else:
                    self.log_and_print("최대 재연결 시도 횟수를 초과했습니다. 프로그램을 종료합니다.")
                    self.cleanup()
        
        def on_open(ws):
            self.log_and_print("웹소켓 연결이 성공했습니다.")
            self.reconnect_count = 0  # 재연결 성공 시 카운트 초기화
            
            # VI 모니터링 구독 요청
            subscribe_message = {
                "header": {
                    "token": self.token,
                    "tr_type": "3"  # 실시간 시세 등록
                },
                "body": {
                    "tr_cd": "VI_",
                    "tr_key": "000000"  # 전체 종목
                }
            }
            
            self.log_and_print("VI 모니터링 구독 요청 전송:")
            self.log_and_print(json.dumps(subscribe_message, indent=2))
            
            ws.send(json.dumps(subscribe_message))
            self.log_and_print("VI 모니터링 시작...")
        
        # 웹소켓 객체 생성
        return websocket.WebSocketApp(
            self.ws_url,
            header=websocket_headers,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )

    def reconnect_websocket(self):
        """웹소켓 재연결"""
        if not self.is_running or self.is_reconnecting:
            return
            
        try:
            self.is_reconnecting = True
            self.log_and_print("웹소켓 재연결 시도 중...")
            
            # 기존 웹소켓 연결 종료
            if self.ws:
                try:
                    self.ws.close()
                except:
                    pass
                self.ws = None
            
            # 새로운 웹소켓 객체 생성
            self.ws = asyncio.get_event_loop().run_until_complete(self.create_websocket())
            
            if self.ws:
                # VI 이벤트 핸들러의 웹소켓 객체 업데이트
                if self.event_handler and self.event_handler.update_websocket(self.ws):
                    self.log_and_print("웹소켓 재연결 성공")
                    self.reconnect_count = 0  # 성공 시 카운트 초기화
                else:
                    raise Exception("VI 이벤트 핸들러 업데이트 실패")
                
                # 웹소켓 실행
                self.ws.run_forever()
            else:
                raise Exception("웹소켓 객체 생성 실패")
                
        except Exception as e:
            self.log_and_print(f"웹소켓 재연결 중 오류 발생: {e}", level='error')
            self.ws = None
            
            # 재연결 실패 시 재시도
            self.reconnect_count += 1
            if self.reconnect_count <= self.max_reconnect_attempts:
                self.log_and_print(f"{self.reconnect_delay}초 후 재연결을 다시 시도합니다... (시도 {self.reconnect_count}/{self.max_reconnect_attempts})")
                asyncio.get_event_loop().call_later(self.reconnect_delay, self.reconnect_websocket)
            else:
                self.log_and_print("최대 재연결 시도 횟수를 초과했습니다. 프로그램을 종료합니다.")
                self.cleanup()
        finally:
            self.is_reconnecting = False

    async def create_test_vi_event(self):
        """테스트용 VI 이벤트 생성"""
        await asyncio.sleep(5)  # 5초 대기
        
        # 테스트용 VI 이벤트 데이터 생성 (발동)
        test_vi_data_on = {
            "header": {
                "tr_cd": "VI_",
                "tr_key": "005930"  # 삼성전자
            },
            "body": {
                "svi_recprice": "72000",
                "vi_gubun": "1",  # 정적발동
                "shcode": "005930",
                "time": datetime.now(self.kst).strftime("%H%M%S"),
                "vi_trgprice": "72000",
                "dvi_recprice": "0",
                "ref_shcode": "005930"
            }
        }
        
        self.log_and_print("\n테스트 VI 발동 이벤트 발생:")
        self.log_and_print(json.dumps(test_vi_data_on, indent=2))
        
        # VI 이벤트 핸들러에 전달
        if self.event_handler:
            self.event_handler.handle_vi_event(test_vi_data_on)
            
            # 10초 후 VI 해제 이벤트 발생
            await asyncio.sleep(100)
            
            # 테스트용 VI 이벤트 데이터 생성 (해제)
            test_vi_data_off = {
                "header": {
                    "tr_cd": "VI_",
                    "tr_key": "005930"
                },
                "body": {
                    "svi_recprice": "0",
                    "vi_gubun": "0",  # VI 해제
                    "shcode": "005930",
                    "time": datetime.now(self.kst).strftime("%H%M%S"),
                    "vi_trgprice": "0",
                    "dvi_recprice": "0",
                    "ref_shcode": "005930"
                }
            }
            
            self.log_and_print("\n테스트 VI 해제 이벤트 발생:")
            self.log_and_print(json.dumps(test_vi_data_off, indent=2))
            self.event_handler.handle_vi_event(test_vi_data_off)
        else:
            self.log_and_print("VI 이벤트 핸들러가 초기화되지 않았습니다.", level='error')

    async def monitor_vi_status(self):
        """VI 상태 모니터링"""
        if not self.token:
            self.log_and_print("토큰이 없습니다. 먼저 토큰을 발급받아주세요.")
            return
            
        self.log_and_print("\n웹소켓 연결 시도...")
        self.log_and_print(f"URL: {self.ws_url}")
        
        try:
            # 웹소켓 연결
            self.ws = await self.create_websocket()
            
            # VI 이벤트 핸들러 초기화 (웹소켓 연결 후에 초기화)
            self.event_handler = VIEventHandler(self.token, self.ws, self.kst, self.stock_info)
            self.event_handler.event_loop = asyncio.get_event_loop()
            
            # 테스트 VI 이벤트 생성 태스크 시작
            asyncio.create_task(self.create_test_vi_event())
            
            # 웹소켓 실행
            self.ws.run_forever()
            
        except Exception as e:
            self.log_and_print(f"웹소켓 연결 실패: {str(e)}")
            raise

    def cleanup(self):
        """프로그램 종료 시 정리 작업"""
        self.log_and_print("프로그램 종료 중...")
        self.is_running = False
        
        # VI 이벤트 핸들러 정리
        if self.event_handler:
            self.event_handler.cleanup()
        
        # 웹소켓 연결 종료
        if self.ws:
            self.ws.close()
        
        self.log_and_print("프로그램이 종료되었습니다.")

async def main():
    monitor = VIMonitor()
    try:
        monitor.token = await monitor.token_manager.get_access_token()
        await monitor.get_stock_info()
        await monitor.monitor_vi_status()
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