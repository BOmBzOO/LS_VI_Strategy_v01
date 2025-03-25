"""메인 실행 모듈"""
import os
import asyncio
import csv
import aiohttp
from datetime import datetime
from pathlib import Path

from src.core.base_handler import BaseHandler
from src.core.data_manager import DataManager
from src.core.token_manager import TokenManager
from src.core.websocket_manager import WebSocketManager
from src.handlers.vi_event_handler import VIEventHandler
from src.handlers.ccld_event_handler import CcldEventHandler
from src.models.stock_info import StockInfo
from src.utils.logger import setup_logger

from config.settings import ls_config, STOCK_INFO_CACHE_SIZE, STOCK_INFO_DIR

class VIMonitor(BaseHandler):
    """VI 모니터링 메인 클래스"""
    def __init__(self):
        super().__init__('VIMonitor')
        
        # 컴포넌트 초기화
        self.data_manager = DataManager()
        self.token_manager = TokenManager(ls_config.API.APP_KEY, ls_config.API.SECRET_KEY)
        self.ws_manager = None
        self.vi_handler = None
        self.ccld_handler = None
        self.is_running = True
        
    async def initialize(self) -> None:
        """초기화"""
        try:
            # 토큰 발급
            token = await self.token_manager.get_access_token()
            if not token:
                raise Exception("토큰 발급 실패")
            
            # 종목 정보 조회
            await self.load_stock_info(token)
            
            # 웹소켓 매니저 초기화
            self.ws_manager = WebSocketManager(ls_config.WebSocket.WEBSOCKET_URL, token)
            
            # VI 이벤트 핸들러 초기화
            self.vi_handler = VIEventHandler(self.ws_manager, self.data_manager)
            
            # 메시지 프로세서 초기화
            self.ccld_handler = CcldEventHandler(self.ws_manager, self.vi_handler)
            
        except Exception as e:
            self.log(f"초기화 중 오류 발생: {e}", 'error')
            raise
    
    async def load_stock_info(self, token: str) -> None:
        """종목 정보 로드"""
        today = datetime.now(self.kst).strftime('%Y%m%d')
        os.makedirs(STOCK_INFO_DIR, exist_ok=True)
        csv_file = os.path.join(STOCK_INFO_DIR, f'stocks_info_{today}.csv')
        
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
        url = f"{ls_config.API.API_URL}/stock/etc"
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {token}",
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
                    await self.ccld_handler.process_message(message)
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
        
        if self.vi_handler:
            self.vi_handler.cleanup()
        
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