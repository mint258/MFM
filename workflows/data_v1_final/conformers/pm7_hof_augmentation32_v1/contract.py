"""Exact existing32 derived-cache contract. No source generation authority."""
from __future__ import annotations
import hashlib,json,pathlib,struct
RUN=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO=RUN/'repository';BASE=RUN/'artifacts/conformers/pm7_independent_cache32_v1'
HERE=pathlib.Path(__file__).absolute().parent
FILES=('contract.py','derive.py','run.py','materialize.py','test_derive.py','README.md')
SCOPE='pm7_hof_augmentation32_v1';CAP=2<<30


def need(value,message):
    if not value:raise ValueError(message)


def scope():
    return {'stage':'PM7_CANONICAL_HOF_ORDER_AUGMENTATION32','molecules':32,'records':203,
      'golden':16,'independent':16,'maximum_workers':16,'new_UFF_calls':0,'new_QM_calls':0,
      'new_LMDB_reads':0,'new_geometry_or_RMSD_calls':0,'registry_id':60,'task':'pm7_B',
      'unit':'kcal/mol','order_seed':20261025,'directional_cached_RMSD_preserved':True,
      'original_random_order_preserved':True,'whole_output_cap_bytes':CAP,'common':False,
      'full_cache_or_physical_int64_release':False,'cost_policy':'REPORT_AND_CONTINUE'}


def bits(value):return struct.pack('<d',float(value)).hex()


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()


def digest(value):return hashlib.sha256(canonical(value)).hexdigest()


def complete_hof(values):return bool(values) and all(v['valid'] for v in values.values())
