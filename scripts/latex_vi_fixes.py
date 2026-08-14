"""
Shared module for Fix A (template-rotation) and Fix G (Vietnamese
placeholder substitution in LaTeX).

Public API:
    _AGENT3_FALLBACK_POOL
    _diversified_agent3_fallback_lines
    substitute_vietnamese_in_latex

All three names are re-exported from `convert_datasheet_to_agents.py`
so this module is the single import surface used by:
    - scripts/transform_for_5agent.py  (Fix A + Fix G)
    - scripts/expand_dataset.py        (Fix G)
    - any postprocess_* script         (Fix A + Fix G)

DO NOT duplicate the underlying implementation. The canonical source
lives in `convert_datasheet_to_agents.py`; this file only re-exports
the names so other scripts can `from latex_vi_fixes import ...` without
spreading the dict / regex / helper across the codebase.
"""

from convert_datasheet_to_agents import (
    _AGENT3_FALLBACK_POOL,
    _diversified_agent3_fallback_lines,
    substitute_vietnamese_in_latex,
)

__all__ = [
    "_AGENT3_FALLBACK_POOL",
    "_diversified_agent3_fallback_lines",
    "substitute_vietnamese_in_latex",
]