"""Harunobu - 行政データ（Excel/CSV）の機械可読性判定システム。"""

from importlib.metadata import version

from harunobu.core.analyzer import analyze, analyze_sheet
from harunobu.core.models import AnalysisResult, Config

__version__ = version("harunobu")

__all__ = ["__version__", "analyze", "analyze_sheet", "AnalysisResult", "Config"]
