"""토큰 관리 모듈"""
import os
import json
from datetime import datetime, timedelta
import aiohttp
from dotenv import set_key

from src.core.base_handler import BaseHandler
from config.settings import ls_config

class TokenManager(BaseHandler):
    """토큰 관리 클래스"""
    def __init__(self, api_key: str, api_secret: str):
        super().__init__('TokenManager')
        self.api_key = api_key
        self.api_secret = api_secret
        self.token_url = f"{ls_config.API.API_URL}/oauth2/token"
        self.token = None
        self.token_expires_at = None
    
    def save_token_to_env(self, token: str, expires_in: int, env_file: str = '.env') -> None:
        """토큰 정보를 .env 파일에 저장"""
        current_time = datetime.now(self.kst)
        expires_at = current_time + timedelta(seconds=expires_in)
        
        # 토큰 정보를 .env 파일에 저장
        set_key(env_file, 'LS_ACCESS_TOKEN', token)
        set_key(env_file, 'LS_TOKEN_EXPIRES_AT', expires_at.isoformat())
        
        # 환경 변수 로드
        from dotenv import load_dotenv
        load_dotenv(env_file)
        
        self.token = token
        self.token_expires_at = expires_at
        self.log(f"토큰 정보가 .env 파일에 저장되었습니다. (만료일시: {expires_at.strftime('%Y-%m-%d %H:%M:%S %Z')})")
    
    def is_token_valid(self) -> bool:
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
            if expires_at - timedelta(seconds=ls_config.Timer.TOKEN_REFRESH_MARGIN) <= current_time:
                return False
                
            self.token = saved_token
            self.token_expires_at = expires_at
            return True
        except Exception as e:
            self.log(f"토큰 유효성 검사 중 오류 발생: {e}", 'error')
            return False
        
    async def get_access_token(self) -> str:
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