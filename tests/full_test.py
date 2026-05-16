"""GMV-LiveLens 全功能测试 — tests/ 入口

用法：
  python tests/full_test.py [--host 127.0.0.1] [--port 8100] [--skip-api]
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

if __name__ == "__main__":
    from backend.tools.full_test import main
    main()
