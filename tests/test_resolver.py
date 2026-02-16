"""Tests for config resolver module."""

import json
import tempfile
from pathlib import Path

from sl_ot_tools.config.resolver import (
    find_company_dir,
    find_engagement_dir,
    find_repo_root,
    resolve_skip_senders,
)
from sl_ot_tools.config.defaults import PLATFORM_SKIP_SENDERS


def test_find_company_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        company_dir = Path(tmpdir) / "_company"
        company_dir.mkdir()
        assert find_company_dir(tmpdir) == company_dir


def test_find_company_dir_from_subdir():
    with tempfile.TemporaryDirectory() as tmpdir:
        company_dir = Path(tmpdir) / "_company"
        company_dir.mkdir()
        subdir = Path(tmpdir) / "engagement" / "workstream"
        subdir.mkdir(parents=True)
        assert find_company_dir(str(subdir)) == company_dir


def test_find_company_dir_not_found():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert find_company_dir(tmpdir) is None


def test_find_repo_root():
    with tempfile.TemporaryDirectory() as tmpdir:
        (Path(tmpdir) / "_company").mkdir()
        assert find_repo_root(tmpdir) == Path(tmpdir)


def test_find_engagement_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        eng_dir = Path(tmpdir) / "my-engagement"
        eng_dir.mkdir()
        (eng_dir / "engagement_config.json").write_text("{}")
        assert find_engagement_dir(str(eng_dir)) == eng_dir


def test_resolve_skip_senders_platform_only():
    result = resolve_skip_senders()
    assert len(result) == len(PLATFORM_SKIP_SENDERS)


def test_resolve_skip_senders_merges():
    company = {"skip_senders": ["noreply@example.com"]}
    engagement = {"skip_senders": ["alerts@example.com"]}
    result = resolve_skip_senders(company, engagement)
    assert "noreply@example.com" in result
    assert "alerts@example.com" in result
    assert len(result) == len(PLATFORM_SKIP_SENDERS) + 2


def test_resolve_skip_senders_deduplicates():
    company = {"skip_senders": ["no-reply@zoom.us"]}  # already in platform
    result = resolve_skip_senders(company)
    assert result.count("no-reply@zoom.us") == 1
