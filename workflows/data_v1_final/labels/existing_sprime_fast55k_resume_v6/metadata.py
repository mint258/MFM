"""Existing metadata protocol with explicit closed-table and corrected-node inputs."""
import argparse,types
from pathlib import Path
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v5 import metadata as OLD
P=C.P

def source_paths():
    return list(dict.fromkeys([*OLD.source_paths(),*(C.HERE/n for n in C.FILES),
      *(C.REPO/'workflows/data_v1_final/export/lossless_sqlite_io_v1'/n for n in ('__init__.py','codec.py','README.md'))]))

def draft(request_path,out):
    from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v4 import metadata as M4
    r=C.meta(P.pin(request_path));out=Path(out)
    f=M4.draft;namespace=dict(f.__globals__,C=C,source_paths=source_paths)
    seed=types.FunctionType(f.__code__,namespace,f.__name__,f.__defaults__,f.__closure__)(request_path,out/'base')
    p=C.meta(seed);p.update(completed_geometry_review_reference=r['completed_geometry_review_reference'],
      source_metadata_frame_review_reference=r['source_metadata_frame_review_reference'])
    review=C.meta(r['completed_geometry_review_reference']);frame=C.meta(r['source_metadata_frame_review_reference'])
    p['source_references']=C.unique([*p['source_references'],r['completed_geometry_review_reference'],r['source_metadata_frame_review_reference'],
      frame['actual_same_storage_mapping_probe_reference'],*review['parent_registration'].values()])
    p['actual_parent_evidence_references']=C.unique([*p['actual_parent_evidence_references'],*review['parent_registration'].values()])
    p['scope_parameters']=C.scope(p);return P.write(out/'plan_candidate.json',p)

def stage(plan_path,out,scope_review=None):
    from workflows.data_v1_final.labels.existing_sprime_native_pilot_resume_v2 import metadata as M
    f=M.stage;g=dict(f.__globals__,C=C)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(plan_path,out,scope_review)

def close(registration_path,out):
    from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v3 import metadata as M
    f=M.close;g=dict(f.__globals__,C=C)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(registration_path,out)

def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('stage');a.add_argument('--plan',required=True);a.add_argument('--output',required=True);a.add_argument('--scope-review')
    a=s.add_parser('close');a.add_argument('--registration',required=True);a.add_argument('--output',required=True)
    a=p.parse_args();print(draft(a.request,a.output)if a.action=='draft'else stage(a.plan,a.output,a.scope_review)if a.action=='stage'else close(a.registration,a.output))
if __name__=='__main__':main()
