"""Launch smoke check for the real Qt startup path."""

import os
import subprocess
import sys
from pathlib import Path


def test_launch_smoke_imports_ui_and_runs_event_loop(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(repo_root / "src"), env.get("PYTHONPATH", "")]
    )

    result = subprocess.run(
        [sys.executable, "-m", "karaoke_buddy", "--smoke-check"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert result.returncode == 0, (
        "Launch smoke check failed.\n"
        f"stdout:\n{result.stdout}\n"
        f"stderr:\n{result.stderr}"
    )
