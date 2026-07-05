from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA = PROJECT_ROOT / "data" / "raw"
CORE_PDF = RAW_DATA / "2026-06-09" / "26-06-09 数据总表（趋势识别＋相对比价＋资金监控）（核心数据集）.pdf"
BETTING_PDF = RAW_DATA / "2026-06-09" / "26-06-09 数据总表（趋势识别＋相对比价＋资金监控）（押注工具）.pdf"
