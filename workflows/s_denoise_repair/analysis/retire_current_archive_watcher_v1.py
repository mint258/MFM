"""Request closure only of this exact own S-repair metadata watcher."""
import argparse,hashlib,json,os
from pathlib import Path
import socket,time
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/s_denoise_repair_20261016')
CONTROL=ROOT/'control/wandb_archive_service_v1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--expected-pid',type=int,required=True);args=parser.parse_args()
    assert os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi'
    ref=json.loads((CONTROL/'current.json').read_text());path=Path(ref['identity_path'])
    assert path.is_relative_to(CONTROL) and sha(path)==ref['identity_sha256']
    identity=json.loads(path.read_text());assert identity['pid']==args.expected_pid and identity['uid']==1278
    proc=Path('/proc')/str(identity['pid'])
    assert proc.stat().st_uid==1278 and proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]==str(identity['start_ticks'])
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==identity['boot_id']
    command=[x.decode() for x in proc.joinpath('cmdline').read_bytes().split(b'\0') if x];assert command==identity['argv']
    script=Path(command[-1]);assert script.is_relative_to(ROOT/'analysis') and sha(script)==identity['source_sha256']
    proof=ROOT/'reports/wandb_archive_v4_preflight_v1.json'
    assert json.loads(proof.read_text())['errors']==[]
    request=path.with_name('STOP_REQUEST.json')
    with request.open('x') as stream:
        json.dump(dict(reason='Upgrade own watcher to discovery of clearly named development tagged SDK runs',timestamp=time.time(),
            identity_reference=ref,preflight_reference=dict(path=str(proof),sha256=sha(proof)),no_scientific_process_signalled=True),stream,indent=2)
        stream.write('\n')
    print('EXACT_OWN_METADATA_STOP_REQUESTED',identity['pid'])

if __name__=='__main__':main()
