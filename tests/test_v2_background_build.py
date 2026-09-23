"""The BUILD_CORPUS_V2 background build launcher (ING-008). No build runs: Popen is a fake."""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import corpus_runtime  # noqa: E402
import start_backend  # noqa: E402


class FakePopen:
    calls = []

    def __init__(self, command, **kwargs):
        FakePopen.calls.append((command, kwargs))
        self.pid = 4242


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path):
    FakePopen.calls = []
    mount = tmp_path / "chroma_db"
    mount.mkdir()
    monkeypatch.setenv("BUILD_CORPUS_V2", "1")
    monkeypatch.setenv("CHROMA_DIR", str(mount))
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(mount))
    monkeypatch.delenv("CHROMA_DIR_V2", raising=False)
    return mount


def test_off_unless_the_flag_is_set(monkeypatch):
    monkeypatch.setenv("BUILD_CORPUS_V2", "0")
    assert start_backend.maybe_start_v2_build(FakePopen) == "off"
    assert FakePopen.calls == []


def test_starts_a_resumable_low_priority_child_inside_the_volume(env):
    assert start_backend.maybe_start_v2_build(FakePopen) == "started"
    command, kwargs = FakePopen.calls[0]
    assert command[1:] == ["-m", "ingestion", "build", "--corpus", "v2", "--resume", "--chroma-dir", str((env / "v2").resolve())]
    assert kwargs["start_new_session"] is True and kwargs["env"]["PYTHONUNBUFFERED"] == "1"
    assert (env / "v2").is_dir()


def test_refuses_a_target_outside_the_volume(monkeypatch, tmp_path):
    monkeypatch.setenv("CHROMA_DIR_V2", str(tmp_path / "chroma_v2"))
    assert start_backend.maybe_start_v2_build(FakePopen) == "outside-volume"
    assert FakePopen.calls == []


def test_does_not_retry_after_a_quota_or_auth_stop(env):
    (env / "v2").mkdir()
    (env / "v2" / "BUILD_FAILED").write_text("FatalOpenAIError: insufficient_quota", encoding="utf-8")
    assert start_backend.maybe_start_v2_build(FakePopen) == "failed-before"
    assert FakePopen.calls == []


def test_complete_store_is_left_alone(env, monkeypatch):
    (env / "v2").mkdir()
    (env / "v2" / "chroma.sqlite3").write_text("x", encoding="utf-8")
    monkeypatch.setattr(corpus_runtime, "verify_store", lambda client, manifest=None: [])
    monkeypatch.setattr("chromadb.PersistentClient", lambda **kwargs: object())
    assert start_backend.maybe_start_v2_build(FakePopen) == "complete"
    assert FakePopen.calls == []


def test_outside_volume_works_before_the_directory_exists(tmp_path):
    mount = tmp_path / "vol"
    mount.mkdir()
    assert corpus_runtime.outside_volume(str(mount / "v2"), str(mount)) is None
    assert "not inside" in corpus_runtime.outside_volume(str(tmp_path / "elsewhere"), str(mount))
