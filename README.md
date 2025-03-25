# LS VI 모니터링 시스템

## 프로젝트 개요
이 프로젝트는 LS증권의 VI(Volatility Interruption) 발동 및 해제 정보를 실시간으로 모니터링하는 시스템입니다.

## 주요 기능
- VI 발동/해제 실시간 모니터링
- WebSocket을 통한 실시간 데이터 수신
- 토큰 기반 인증 및 자동 갱신
- 시장별(KOSPI/KOSDAQ) VI 정보 처리
- 로깅 시스템을 통한 이벤트 기록

## 시스템 구성
- `TokenManager`: API 토큰 관리 및 갱신
- `WebSocketManager`: WebSocket 연결 및 데이터 수신 관리
- `VIEventHandler`: VI 이벤트 처리
- `MessageProcessor`: 수신된 메시지 처리
- `VIMonitor`: 전체 시스템 관리

## 설치 방법
1. 저장소 클론
```bash
git clone [repository_url]
cd [repository_name]
```

2. 가상환경 생성 및 활성화
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

3. 의존성 설치
```bash
pip install -r requirements.txt
```

4. 환경 변수 설정
- `.env.template` 파일을 `.env`로 복사하고 필요한 값을 설정
```bash
cp .env.template .env
```

## 실행 방법
```bash
python main.py
```

## 테스트 실행
```bash
pytest
```

## 프로젝트 구조
```
.
├── src/
│   ├── core/
│   │   ├── token_manager.py
│   │   ├── websocket_manager.py
│   │   └── message_processor.py
│   ├── handlers/
│   │   └── vi_event_handler.py
│   └── monitor.py
├── config/
│   └── settings.py
├── tests/
│   └── test_core/
├── logs/
├── data/
└── README.md
```

## 로깅
- 로그 파일은 `logs` 디렉토리에 일자별로 생성
- 로그 포맷: `[시간] [모듈명] [로그레벨] 메시지`
- 로그 파일 크기: 최대 10MB
- 백업 파일 수: 5개

## 라이선스
이 프로젝트는 MIT 라이선스를 따릅니다.

## 기여 방법
1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 문의사항
문의사항이나 버그 리포트는 이슈 트래커를 이용해 주시기 바랍니다. 