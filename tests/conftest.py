"""
Shared pytest fixtures and helpers for the Executive Pulse test suite.

Every test must run from any working directory on any machine — no
absolute paths.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime

import pandas as pd
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SAMPLE_CSV = os.path.join(REPO_ROOT, "app", "data", "sample_data.csv")


@pytest.fixture(scope="session")
def sample_df() -> pd.DataFrame:
    """Validated sample dataset (unscored)."""
    from app.data.loader import load_and_validate

    return load_and_validate(file_path=SAMPLE_CSV)


@pytest.fixture(scope="session")
def scored_df(sample_df: pd.DataFrame) -> pd.DataFrame:
    """Sample dataset with flags, scores and ranking applied."""
    from app.engine.rule_engine import compute_all_flags, rank_attention

    return rank_attention(compute_all_flags(sample_df))


@pytest.fixture
def today() -> datetime:
    return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
