"""Warstwa figur (T-008). Jedna figura = PNG + SVG + JSON + wpis w INDEX.md."""

from src.viz.save import FigureSpec, save_fig
from src.viz.style import CATEGORICAL_PALETTE, apply_style

__all__ = ["CATEGORICAL_PALETTE", "FigureSpec", "apply_style", "save_fig"]
