import json

import numpy as np

from benchmarks.runner import write_artifact


def test_summary_artifacts_use_json_when_chains_are_not_requested(tmp_path):
    path = write_artifact(tmp_path / "case", {"observed": np.array([1.0, np.nan])}, False)
    assert path.suffix == ".json"
    assert json.loads(path.read_text()) == {"observed": [1.0, None]}
    assert not list(tmp_path.glob("*.npz"))
