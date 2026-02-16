"""Tests for knowledge dedup module."""

import json
import tempfile
from pathlib import Path

from sl_ot_tools.knowledge.dedup import (
    add_to_checkpoint,
    is_processed,
    load_checkpoint,
    make_dedup_key,
    normalize_subject,
    save_checkpoint,
)


def test_normalize_subject_strips_re():
    assert normalize_subject("RE: Hello World") == "hello world"


def test_normalize_subject_strips_fw():
    assert normalize_subject("FW: Hello World") == "hello world"


def test_normalize_subject_strips_fwd():
    assert normalize_subject("FWD: Hello World") == "hello world"


def test_normalize_subject_strips_nested():
    assert normalize_subject("RE: FW: RE: Hello World") == "hello world"


def test_normalize_subject_collapses_whitespace():
    assert normalize_subject("  RE:   Hello   World  ") == "hello world"


def test_normalize_subject_case_insensitive():
    assert normalize_subject("Re: hello") == normalize_subject("RE: Hello")


def test_make_dedup_key():
    key = make_dedup_key("RE: AWS PoC Update", "2026-02-15T10:30:00")
    assert key == "aws poc update|2026-02-15"


def test_make_dedup_key_same_thread():
    k1 = make_dedup_key("AWS PoC Update", "2026-02-15T08:00:00")
    k2 = make_dedup_key("RE: AWS PoC Update", "2026-02-15T14:00:00")
    assert k1 == k2


def test_checkpoint_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "checkpoint.json"

        cp = load_checkpoint(path)
        assert cp["processed"] == []

        add_to_checkpoint(cp, "RE: Test Email", "2026-02-15T10:00:00")
        save_checkpoint(path, cp)

        loaded = load_checkpoint(path)
        assert len(loaded["processed"]) == 1
        assert loaded["processed"][0]["key"] == "test email|2026-02-15"


def test_is_processed():
    cp = {"processed": [{"key": "hello world|2026-02-15", "subject": "Hello World", "date": "2026-02-15"}]}
    assert is_processed(cp, "RE: Hello World", "2026-02-15T09:00:00")
    assert not is_processed(cp, "Different Subject", "2026-02-15T09:00:00")
    assert not is_processed(cp, "Hello World", "2026-02-16T09:00:00")
