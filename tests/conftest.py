"""Shared test fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

TESTS_DIR = Path(__file__).parent
LOCAL_TMP = TESTS_DIR / ".tmp"


@pytest.fixture(autouse=True)
def _no_copilot() -> None:
    """Prevent tests from calling the real Copilot SDK."""
    _side_effect = RuntimeError("Copilot disabled in tests")
    with (
        patch("aipm.utils.copilot_chat", side_effect=_side_effect),
        patch("aipm.commands.check.copilot_chat", side_effect=_side_effect),
    ):
        yield  # type: ignore[misc]


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
