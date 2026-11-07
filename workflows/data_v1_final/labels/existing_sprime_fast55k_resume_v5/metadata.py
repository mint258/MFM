"""Original terminal-phase metadata protocol; new explicit IO source namespace."""
import argparse,types
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_fast55k_resume_v4 import metadata as OLD
P=C.P

def source_paths():return list(dict.fromkeys([*OLD.source_paths(),*(C.HERE/n for n in C.FILES)]))

def draft(request_path,out):
    f=OLD.draft;g=dict(f.__globals__,C=C,source_paths=source_paths)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(request_path,out)

def stage(plan_path,out,scope_review=None):
    f=OLD.stage;g=dict(f.__globals__,C=C)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(plan_path,out,scope_review)

def close(registration_path,out):
    f=OLD.close;g=dict(f.__globals__,C=C)
    return types.FunctionType(f.__code__,g,f.__name__,f.__defaults__,f.__closure__)(registration_path,out)

def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('stage');a.add_argument('--plan',required=True);a.add_argument('--output',required=True);a.add_argument('--scope-review')
    a=s.add_parser('close');a.add_argument('--registration',required=True);a.add_argument('--output',required=True)
    a=p.parse_args();print(draft(a.request,a.output)if a.action=='draft'else stage(a.plan,a.output,a.scope_review)if a.action=='stage'else close(a.registration,a.output))
if __name__=='__main__':main()
