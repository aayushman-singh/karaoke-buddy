"""Launch smoke check for the real Qt startup path."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


def _run_launch_smoke(tmp_path, env_overrides=None):
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = os.pathsep.join([str(repo_root / "src"), env.get("PYTHONPATH", "")])
    if env_overrides:
        env.update(env_overrides)

    try:
        return subprocess.run(
            [sys.executable, "-m", "karaoke_buddy", "--smoke-check"],
            cwd=tmp_path,
            env=env,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        pytest.fail(f"Launch smoke check timed out.\nstdout:\n{stdout}\nstderr:\n{stderr}")


def test_launch_smoke_imports_ui_and_runs_event_loop(tmp_path):
    result = _run_launch_smoke(tmp_path)

    assert result.returncode == 0, (
        f"Launch smoke check failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "Traceback (most recent call last)" not in result.stderr
    assert "Uncaught exception during launch smoke check" not in result.stderr


def test_launch_smoke_fails_on_uncaught_event_loop_exception(tmp_path):
    result = _run_launch_smoke(
        tmp_path,
        {"KARAOKE_BUDDY_SMOKE_RAISE_UNCAUGHT": "1"},
    )

    assert result.returncode != 0, (
        "Launch smoke check unexpectedly passed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
    assert "Injected launch smoke exception" in result.stderr
    assert "Uncaught exception during launch smoke check" in result.stderr
