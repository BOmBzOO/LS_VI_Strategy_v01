"""데이터 관리 모듈"""
from datetime import datetime
from typing import Dict, Optional, List, Any
from functools import lru_cache
import asyncio

from src.core.base_handler import BaseHandler
from src.models.stock_info import StockInfo
from config.settings import STOCK_INFO_CACHE_SIZE, STOCK_INFO_DIR, ls_config

class DataManager(BaseHandler):
    """데이터 관리 클래스"""
    def __init__(self):
        super().__init__('DataManager')
        self.stock_info: Dict[str, StockInfo] = {}
        self.vi_active_stocks: Dict[str, datetime] = {}
        self.unsubscribed_stocks: Dict[str, Dict[str, Any]] = {}
        self._vi_timers: Dict[str, asyncio.Task] = {}  # VI 타이머 태스크 저장
    
    @lru_cache(maxsize=STOCK_INFO_CACHE_SIZE)
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
            await asyncio.sleep(ls_config.VI.SUBSCRIPTION_TIMEOUT)  # 3분 대기
            if stock_code in self.vi_active_stocks:
                await callback(stock_code)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.log(f"VI 타이머 실행 중 오류 발생: {e}", 'error')
        finally:
            if stock_code in self._vi_timers:
                del self._vi_timers[stock_code] 