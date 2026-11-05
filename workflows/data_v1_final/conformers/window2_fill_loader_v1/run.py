"""Reuse fast fill producer, omitting only unused HOF join and prior packets."""
from __future__ import annotations
import argparse
import collections
import types
from workflows.data_v1_final.conformers.window2_fill_runtime_v1 import run as fast
from workflows.data_v1_final.conformers.window2_population_v1 import fill as original


def tasks(db,metas):
    """Original full formal/UFF rows and ordering, with no HOF or prior I/O."""
    import pyarrow as pa
    db.register('batch',pa.table({'molecule_id':[row['molecule_id'] for row in metas]}))
    records=db.execute('SELECT f.* FROM formal f JOIN batch USING(molecule_id) ORDER BY molecule_id,record_id').fetch_arrow_table().to_pylist()
    uff=db.execute('SELECT u.* FROM uff u JOIN batch USING(molecule_id) ORDER BY molecule_id,sprime_conf_idx').fetch_arrow_table().to_pylist()
    byrecord=collections.defaultdict(list);byuff=collections.defaultdict(list)
    for row in records:byrecord[row['molecule_id']].append(row)
    for row in uff:byuff[row['molecule_id']].append(row)
    db.unregister('batch')
    return [{'meta':meta,'records':byrecord[meta['molecule_id']],
        'uff':byuff[meta['molecule_id']],'prior_packet':None} for meta in metas]


def bind(function,**replacements):
    """Private function namespace: no shared/active module is patched."""
    current=types.FunctionType(function.__code__,dict(function.__globals__,**replacements),
        function.__name__,function.__defaults__,function.__closure__)
    current.__kwdefaults__=function.__kwdefaults__
    return current


def part_values(db,metas,statistics,bounds,pool):
    # Reuse the exact already-complete qualification, original safe_fill,
    # meta-order reconstruction and slow pool behavior of the passed runtime.
    functions=types.SimpleNamespace(d7=types.SimpleNamespace(tasks=tasks),safe_fill=original.safe_fill)
    return bind(fast.part_values,original=functions)(db,metas,statistics,bounds,pool)


def run(plan):
    # All producer/checkpoint/new-geometry writing code is the existing runtime.
    return bind(fast.run,part_values=part_values)(plan)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True)
    args=parser.parse_args();run(original.read(args.plan))


if __name__=='__main__':main()