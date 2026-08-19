"""P47 (minimal): the floor=p50 config BINDS on the real archive replay — the
'not identity' check. Skipped when the archive data is absent (it is only
temporarily tracked)."""
import importlib.util
from pathlib import Path

import pytest

_ARCHIVE = Path(__file__).resolve().parents[2] / "experiment_data" / "archive"
_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_blink_clamp.py"

pytestmark = pytest.mark.skipif(
    not _ARCHIVE.is_dir() or not _SCRIPT.is_file(),
    reason="archive data / verify script not present",
)


def _load_script():
    spec = importlib.util.spec_from_file_location("verify_blink_clamp", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("metric", ["tbr", "alpha"])
def test_floor_p50_binds(metric):
    """F2-style acceptance: floor=p50 changes decisions (>0), preserves more
    than half the true switches, and blocks at least one false trigger."""
    mod = _load_script()
    total = {"decision_changes": 0, "true_kept": 0, "true_total": 0,
             "false_blocked": 0, "false_total": 0}
    for sid in mod.SESSIONS[metric]:
        sd = _ARCHIVE / sid
        if not sd.is_dir():
            continue
        trials, stream, p50 = mod._load(sd, metric)
        r = mod._evaluate(trials, stream, p50)
        for k in total:
            total[k] += r[k]
    assert total["decision_changes"] > 10
    assert total["true_kept"] > total["true_total"] / 2
    assert total["false_blocked"] > 0
