"""Compatibility entry point for the canonical local RAG evaluator.

The old semantic runner duplicated cases and metrics, which allowed its report
to drift away from the production pipeline. This wrapper now delegates to the
single evaluator in local_eval/rag_eval_local.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from local_eval.rag_eval_local import main  # noqa: E402


if __name__ == "__main__":
    main()
