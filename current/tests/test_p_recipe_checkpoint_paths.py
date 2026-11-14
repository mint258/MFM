import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/p_recipe'))
from checkpoint_paths import evaluation_checkpoint


def test_exact_old_checkpoint_and_current_final(tmp_path):
    old = tmp_path / 'old'
    new = tmp_path / 'new'
    old.mkdir()
    new.mkdir()
    (old / 'configuration.json').write_text(json.dumps(dict(output=str(old))))
    old_point = old / 'samples_1500000.pt'
    final = new / 'samples_3000000.pt'
    old_point.touch()
    final.touch()
    configuration = dict(output=str(new), resume_from_output=str(old))
    assert evaluation_checkpoint(configuration, 1500000) == old_point
    assert evaluation_checkpoint(configuration, 3000000) == final


def test_missing_exact_point_does_not_use_later_checkpoint(tmp_path):
    (tmp_path / 'samples_2000000.pt').touch()
    with pytest.raises(FileNotFoundError, match='1500000'):
        evaluation_checkpoint(dict(output=str(tmp_path)), 1500000)
