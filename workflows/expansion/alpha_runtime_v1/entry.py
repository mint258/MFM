"""Absolute standalone entry: PY -I -B ENTRY MODULE [ARGS]."""
import os
from pathlib import Path
import runpy
import sys

if __name__ == '__main__':
    root = Path(__file__).resolve().parents[3]
    if not sys.flags.isolated or Path.cwd().resolve() != root or root == Path.home().resolve() or (root / 'string.py').exists():
        raise RuntimeError('Require Python-I and the exact clean code working directory')
    if len(sys.argv) < 2 or not sys.argv[1].startswith('workflows.expansion.'):
        raise RuntimeError('An explicit expansion module is required')
    module = sys.argv[1]
    sys.path.insert(0, str(root))
    sys.argv = [module, *sys.argv[2:]]
    runpy.run_module(module, run_name='__main__', alter_sys=True)
