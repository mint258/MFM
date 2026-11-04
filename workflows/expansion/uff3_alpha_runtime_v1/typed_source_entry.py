"""Strict Alpha startup wrapper for the existing full2.5M source orchestrator.

Ranking uses the independent strict alpha_typed_rank_v1 admission. This entry
cannot dispatch ranking or bypass its CPP/full-Ntuple proof requirements.
"""
import argparse
import json
from pathlib import Path
from ..alpha_runtime_v1 import common as Q
from .. import common as original_common
from ..exact_nn_cached_v1 import ordered_source,sql_runtime,engine
from ..portable_sources_v1 import transport
from ..pubchem_closed500_bulk_v2 import merge
from . import entry

MODULE='workflows.expansion.uff3_alpha_runtime_v1.typed_source_entry'


def dispatch(plan,plan_path):
    Q.need(plan['runtime_action']=='ordered_source'
        and plan['schema']=='PUBCHEM_TYPED_ORDERED_UFF_SOURCE_PLAN_V1',
        'Only full2.5M ordered source; ranking must use independent strict Alpha rank admission')
    return ordered_source.run(plan_path)


def execute(plan_path,proof_path):
    plan,actual,refs=entry.admit(plan_path,proof_path,module=MODULE)
    proof=Q.load(proof_path)
    # Pin actual imported implementations across namespace layers. Never infer
    # an external_sort path relative to a thin overlay which does not contain it.
    modules=(ordered_source,sql_runtime,engine,transport,original_common,merge)
    pins=[Q.reference(module.__file__)for module in modules]
    Q.need(all(ref in plan['code_references']and ref in proof['request']['source_references']for ref in pins),
           'Actual imported ordered source and dependencies pinned')
    return dispatch(plan,plan_path)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();print(json.dumps(execute(a.plan,a.startup_proof),sort_keys=True))


if __name__=='__main__':main()