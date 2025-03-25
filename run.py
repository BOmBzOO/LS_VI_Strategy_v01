import os
import sys
import asyncio
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = str(Path(__file__).parent)
sys.path.insert(0, project_root)

# main.py 실행
if __name__ == "__main__":
    try:
        from src.main import main
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n프로그램이 종료되었습니다.") 