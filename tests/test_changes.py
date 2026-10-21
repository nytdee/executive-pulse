"""
Change detection tests.

The change feed must survive Streamlit reruns (every filter change and
navigation click re-runs the script). Previously the baseline snapshot was
rewritten on every rerun, so "What Changed" was empty by the second
interaction.
"""

from __future__ import annotations

import json
import os
import shutil

import pandas as pd
import pytest

import main as app_main
from app.engine.rule_engine import compute_changes
from tests.helpers import make_row


@pytest.fixture
def snapshot_dir(tmp_path, monkeypatch):
    """Redirect snapshot storage to a temp directory."""
    monkeypatch.setattr(app_main, "SNAPSHOT_DIR", str(tmp_path / "snapshots"))
    yield tmp_path / "snapshots"
    shutil.rmtree(tmp_path / "snapshots", ignore_errors=True)


def frame(reference, rows):
    return pd.DataFrame([make_row(reference, **r) for r in rows])


def test_changes_detected_against_previous_baseline(today):
    """A status change must be reported as a status change."""
    old = frame(today, [{"Task_ID": "A", "Status": "In Progress"}])
    new = frame(today, [{"Task_ID": "A", "Status": "Blocked", "Blocker": "x"}])

    changes = compute_changes(new, old)
    assert len(changes["status_changes"]) == 1
    assert changes["status_changes"].iloc[0]["Old_Status"] == "In Progress"
    assert changes["status_changes"].iloc[0]["New_Status"] == "Blocked"


def test_no_changes_when_data_identical(today):
    df = frame(today, [{"Task_ID": "A", "Status": "In Progress"}])
    changes = compute_changes(df, df)
    assert all(len(v) == 0 for v in changes.values())


def test_fingerprint_stable_for_identical_data(today):
    df = frame(today, [{"Task_ID": "A", "Status": "In Progress"}])
    reordered = frame(today, [{"Task_ID": "A", "Status": "In Progress"}])
    assert app_main._data_fingerprint(df) == app_main._data_fingerprint(reordered)


def test_fingerprint_changes_when_status_changes(today):
    df = frame(today, [{"Task_ID": "A", "Status": "In Progress"}])
    changed = frame(today, [{"Task_ID": "A", "Status": "Blocked"}])
    assert app_main._data_fingerprint(df) != app_main._data_fingerprint(changed)


def test_snapshot_roundtrip(today, snapshot_dir):
    df = frame(today, [{"Task_ID": "A", "Status": "In Progress"}])
    fp = app_main._data_fingerprint(df)
    app_main._save_snapshot(df, "sample", fp)

    loaded, loaded_fp, stored = app_main._load_snapshot("sample")
    assert loaded is not None
    assert loaded_fp == fp
    assert list(loaded["Task_ID"]) == ["A"]
    assert stored is None


def test_snapshot_absent_returns_none(today, snapshot_dir):
    loaded, fp, stored = app_main._load_snapshot("never-written")
    assert loaded is None
    assert fp == ""
    assert stored is None


def test_changes_survive_repeated_reruns(today, snapshot_dir):
    """The regression that mattered: changes were wiped by the next rerun.

    Mirrors the main-loop contract:
        prev, prev_fp, stored = load_snapshot()
        changes = compute_changes(df, prev)
        if fingerprint != prev_fp: save_snapshot(df, fingerprint, changes)
        elif stored: changes = deserialise(stored)

    A rerun with unchanged data must keep reporting the same change.
    """
    baseline = frame(today, [{"Task_ID": "A", "Status": "In Progress"}])
    updated = frame(today, [{"Task_ID": "A", "Status": "Blocked", "Blocker": "vendor"}])

    # Seed the baseline from the old data.
    app_main._save_snapshot(baseline, "sample", app_main._data_fingerprint(baseline))

    def run_once(current):
        fingerprint = app_main._data_fingerprint(current)
        previous, previous_fp, stored = app_main._load_snapshot("sample")
        changes = compute_changes(current, previous)
        if fingerprint != previous_fp:
            app_main._save_snapshot(current, "sample", fingerprint, changes)
        elif stored:
            changes = app_main._deserialise_changes(stored)
        return changes

    first = run_once(updated)
    assert len(first["status_changes"]) == 1, "first render must show the change"

    # Subsequent reruns with the same data must not erase the change feed.
    for _ in range(3):
        again = run_once(updated)
        assert len(again["status_changes"]) == 1, "change feed must survive reruns"


def test_new_baseline_advances_when_data_changes_again(today, snapshot_dir):
    """After a second real change, the feed reports the newest delta."""
    baseline = frame(today, [{"Task_ID": "A", "Status": "In Progress"}])
    v2 = frame(today, [{"Task_ID": "A", "Status": "Blocked", "Blocker": "x"}])
    v3 = frame(today, [{"Task_ID": "A", "Status": "Done"}])

    app_main._save_snapshot(baseline, "sample", app_main._data_fingerprint(baseline))

    def run_once(current):
        fingerprint = app_main._data_fingerprint(current)
        previous, previous_fp, stored = app_main._load_snapshot("sample")
        changes = compute_changes(current, previous)
        if fingerprint != previous_fp:
            app_main._save_snapshot(current, "sample", fingerprint, changes)
        elif stored:
            changes = app_main._deserialise_changes(stored)
        return changes

    run_once(v2)
    third = run_once(v3)
    assert len(third["status_changes"]) == 1
    assert third["status_changes"].iloc[0]["New_Status"] == "Done"


def test_changes_serialise_roundtrip(today, snapshot_dir):
    old = frame(today, [{"Task_ID": "A", "Status": "In Progress"}])
    new = frame(today, [{"Task_ID": "A", "Status": "Blocked", "Blocker": "x"}])
    changes = compute_changes(new, old)

    serialised = app_main._serialise_changes(changes)
    restored = app_main._deserialise_changes(serialised)
    assert len(restored["status_changes"]) == len(changes["status_changes"])
    assert restored["status_changes"].iloc[0]["New_Status"] == "Blocked"


def test_snapshots_are_isolated_per_source(today, snapshot_dir):
    """Switching data source must not compare against another source."""
    df = frame(today, [{"Task_ID": "A", "Status": "In Progress"}])
    app_main._save_snapshot(df, "sample", app_main._data_fingerprint(df))

    other, fp, stored = app_main._load_snapshot("gsheet:abc:0")
    assert other is None
    assert fp == ""
    assert stored is None
