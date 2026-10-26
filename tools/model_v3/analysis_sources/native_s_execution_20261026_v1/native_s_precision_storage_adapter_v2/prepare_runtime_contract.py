"""Root-only metadata binding of a combined immutable tree; no reservation."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import re
import subprocess
import runtime_origin as origin


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-root',type=Path); parser.add_argument('--git',default='git')
    parser.add_argument('--commit'); parser.add_argument('--tree'); parser.add_argument('--combined-record',type=Path)
    parser.add_argument('--publication-receipt',type=Path); parser.add_argument('--publication-sha256')
    parser.add_argument('--full-runtime-verification',type=Path); parser.add_argument('--full-runtime-verification-sha256')
    parser.add_argument('--candidate-profile-only',action='store_true')
    parser.add_argument('--candidate-admission',type=Path); parser.add_argument('--candidate-admission-sha256')
    parser.add_argument('--metadata-only',action='store_true'); parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    combined=None
    if args.combined_record:
        combined=json.loads(args.combined_record.read_text())
        origin.require(combined['schema']=='model_v3_combined_immutable_native_runtime_v1'
            and combined['all_native_and_proxy_storage_sources_in_one_package'] is True,'Actual combined machine record required')
        args.runtime_root=Path(combined['runtime_root']); args.commit=combined['code_sha']; args.tree=combined['tree_sha']
    origin.require(args.runtime_root is not None and args.commit and args.tree,'Actual immutable runtime root/commit/tree required')
    root=args.runtime_root.absolute()
    origin.require(not (args.metadata_only and args.candidate_profile_only),'Choose one explicit metadata/candidate/full admission mode')
    origin.require(not args.output.exists(),'Fresh runtime contract output required')
    origin.require(all(re.fullmatch('[0-9a-f]{40}',x) for x in (args.commit,args.tree)),'Exact machine commit/tree required')
    observations=[]
    def git(*command):
        argv=[args.git,'-C',str(root),*command]
        completed=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30)
        observations.append(dict(argv=argv,returncode=completed.returncode,stdout=completed.stdout.decode('utf-8'),stderr=completed.stderr.decode('utf-8')))
        origin.require(completed.returncode==0,'Actual Git metadata command failed')
        return completed.stdout.decode('utf-8').strip()
    origin.require(git('rev-parse','HEAD')==args.commit and git('rev-parse','HEAD^{tree}')==args.tree,'Actual immutable HEAD/tree differs')
    origin.require(git('status','--porcelain','--untracked-files=normal')=='','Combined runtime must be clean')
    files=list((root/'current/phychem_mfm').rglob('*.py'))
    files+=list((root/'tools/model_v3').glob('*.py'))
    files+=list((root/'current/configs/model_v3/performance').glob('b*.json'))
    files+=[root/'workflows/sprime_s/formal_s/B1_seed0_v2.json',root/'workflows/s_denoise/configs/A4_seed0_v3.json']
    files+=[root/'workflows/sprime_s/scripts'/name for name in
        ('s_native_adapter_v1.py','s_native_adapter_v2.py','s_loader_recovery_v1.py','s_loader_recovery_v2.py','s_model_memory_v1.py','prepare.py')]
    leaf=json.loads((Path(__file__).parent/'accounting_leaf_provenance.json').read_text())
    origin.require(origin.sha(root/leaf['leaf']['relative_path'])==leaf['leaf']['sha256'],'075 accounting implementation leaf changed')
    publication=None; public_commit=None
    if not args.metadata_only or args.publication_receipt is not None:
        origin.require(args.publication_receipt is not None and args.publication_sha256
            and origin.sha(args.publication_receipt)==args.publication_sha256,'Actual public raw receipt required')
        raw=json.loads(args.publication_receipt.read_text()); public_commit=raw['github_commit_sha']
        origin.require(raw['local_code_sha']==args.commit and raw['tree_sha']==args.tree
            and raw['exact_tree_verified'] and raw['published_head_readback_verified'],'Combined/public exact-tree receipt differs')
        publication=dict(path=str(args.publication_receipt.absolute()),bytes=args.publication_receipt.stat().st_size,sha256=args.publication_sha256)
        if args.candidate_profile_only:
            origin.require(args.candidate_admission is not None and args.candidate_admission_sha256
                and origin.sha(args.candidate_admission)==args.candidate_admission_sha256,'Actual bounded candidate QA admission required')
        elif not args.metadata_only:
            origin.require(args.full_runtime_verification is not None and args.full_runtime_verification_sha256
                and origin.sha(args.full_runtime_verification)==args.full_runtime_verification_sha256,
                'Actual full-runtime C0 verification required; publication candidate alone cannot admit GPU')
    value=dict(schema='native_S_single_combined_runtime_v2',status='PREPUBLICATION_METADATA_ONLY' if args.metadata_only else
        'CANDIDATE_PROFILE_ONLY' if args.candidate_profile_only else 'PUBLISHED_IMMUTABLE_RUNTIME',
        runtime_root=str(root),combined_commit=args.commit,combined_tree=args.tree,public_commit=public_commit,
        publication_receipt=publication,accounting_leaf_provenance=leaf,Git_observations=observations,
        combined_machine_record=None if args.combined_record is None else dict(path=str(args.combined_record.absolute()),
            bytes=args.combined_record.stat().st_size,sha256=origin.sha(args.combined_record)),
        full_runtime_verification=None if args.full_runtime_verification is None else dict(
            path=str(args.full_runtime_verification.absolute()),bytes=args.full_runtime_verification.stat().st_size,
            sha256=args.full_runtime_verification_sha256),
        candidate_profile_admission=None if args.candidate_admission is None else dict(path=str(args.candidate_admission.absolute()),
            bytes=args.candidate_admission.stat().st_size,sha256=args.candidate_admission_sha256),
        production_20k_allowed=not(args.metadata_only or args.candidate_profile_only),
        files=[dict(relative_path=str(path.relative_to(root)),bytes=path.stat().st_size,sha256=origin.sha(path)) for path in sorted(set(files))])
    with args.output.open('x') as stream: json.dump(value,stream,indent=2); stream.write('\n')
    origin.read_contract(args.output,metadata_only=args.metadata_only,allow_candidate_profile=args.candidate_profile_only)


if __name__=='__main__': main()
