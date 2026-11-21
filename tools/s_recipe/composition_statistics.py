"""Load the existing frozen P follow-up statistics; do not copy its code."""
from pathlib import Path
import subprocess

from runtime import ROOT

SOURCE_COMMIT = '5af7d2b730fd14d4ad2f3a0a0b9c2f32049816ea'
SOURCE_PATH = 'tools/p_followup/composition_statistics.py'
_git = ROOT/'runs/p_followup_20261116/test_tools/git/bin/git'
# The existing follow-up repository owns this published source object. Reading it
# pins the original math without importing a moving worktree or duplicating it.
_source = subprocess.check_output(
    [str(_git), '-C', str(ROOT/'MFM_p_followup_20261117'), 'show', SOURCE_COMMIT+':'+SOURCE_PATH],
    timeout=30)
_namespace = {'__name__': 's_reused_frozen_composition_statistics',
              '__file__': SOURCE_COMMIT+':'+SOURCE_PATH}
exec(compile(_source, _namespace['__file__'], 'exec'), _namespace)
for _name, _value in _namespace.items():
    if not _name.startswith('_'):
        globals()[_name] = _value
