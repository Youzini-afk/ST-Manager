from pathlib import Path
import subprocess


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_node_worldinfo_send_to_st_runtime_script_passes():
    result = subprocess.run(
        ['node', 'tests/worldinfo_send_to_st_runtime_test.mjs'],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert 'worldinfo_send_to_st_runtime_test: ok' in result.stdout
