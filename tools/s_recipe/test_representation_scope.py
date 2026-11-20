import json
import pytest

import representations


def test_unresolved_layer_scope_is_never_inferred(tmp_path, monkeypatch):
    monkeypatch.setattr(representations, 'REPO', tmp_path)
    folder = tmp_path/'configs/s_recipe'
    folder.mkdir(parents=True)
    path = folder/'preregistration.json'
    c = dict(seed=0, samples=3000000, arm='S-B0')
    path.write_text(json.dumps(dict(status='DRAFT')))
    with pytest.raises(ValueError, match='registration freeze'):
        representations.registered(c)
    path.write_text(json.dumps(dict(status='FROZEN', diagnostics={})))
    with pytest.raises(ValueError, match='Explicit registered representation layers'):
        representations.registered(c)
    path.write_text(json.dumps(dict(status='FROZEN', diagnostics=dict(representation_layers=[3, 4, 5, 6]))))
    assert representations.registered(c) == [3, 4, 5, 6]
    with pytest.raises(ValueError, match='seed0 only'):
        representations.registered(dict(c, seed=1))
