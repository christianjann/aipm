"""Shared test fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent
LOCAL_TMP = TESTS_DIR / ".tmp"


@pytest.fixture()
def work_dir(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Provide a local working directory under tests/.tmp/<test_name>/.

    Files are easy to inspect after a test run. The directory is cleaned
    and recreated at the start of each test.
    """
    test_name = request.node.name
    test_dir = LOCAL_TMP / test_name

    # Clean previous run
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir(parents=True)

    monkeypatch.chdir(test_dir)
    return test_dir
