"""Analysis system for ISI Macroscope.

This package provides Fourier-based retinotopic analysis, visual field sign
computation, and area segmentation. Uses constructor injection pattern - all
dependencies passed explicitly.
"""

from .pipeline import AnalysisPipeline
from .manager import AnalysisManager, AnalysisResults, SessionData, DirectionData
from .renderer import AnalysisRenderer

__all__ = [
    "AnalysisPipeline",
    "AnalysisManager",
    "AnalysisResults",
    "SessionData",
    "DirectionData",
    "AnalysisRenderer",
]
