"""pytest 配置:把 algorithm 目录加入 sys.path,让 `from src.xxx` 可 import。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
