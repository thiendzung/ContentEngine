from pathlib import Path
import subprocess
import sys


def test_production_research_runner_is_directly_executable() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    script = backend_root / "scripts" / "run_production_research.py"

    result = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=backend_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Run the CE04 production ResearchRouter." in result.stdout
    assert "ModuleNotFoundError" not in result.stderr
