import os

# 생성할 파일과 내용
files = {
    'src/core/__init__.py': '"""VI 모니터링 시스템 - 핵심 기능 모듈"""',
    'src/handlers/__init__.py': '"""VI 모니터링 시스템 - 이벤트 핸들러 모듈"""',
    'src/models/__init__.py': '"""VI 모니터링 시스템 - 데이터 모델"""',
    'src/utils/__init__.py': '"""VI 모니터링 시스템 - 유틸리티 모듈"""'
}

# 파일 생성
for file_path, content in files.items():
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content) 