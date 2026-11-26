"""Metadata-only phase peaks inside the existing64GiB S output ceiling."""
import json
from pathlib import Path
import stat
from storage_20261122 import CONTROL,REPO,claim_current

GiB=1024**3
LIVE={'PENDING','RUNNING','CONFIGURING','COMPLETING','UNKNOWN'}


def allocated(root):
    root=Path(root)
    if root.is_symlink():raise ValueError('Output pool root must not be a link')
    if not root.exists():return 0
    seen=set()
    total=0
    for path in root.rglob('*'):
        try:value=path.lstat()
        except FileNotFoundError:continue
        if stat.S_ISLNK(value.st_mode):
            raise ValueError('New output pool must not follow a linked external cache')
        key=(value.st_dev,value.st_ino)
        if stat.S_ISREG(value.st_mode) and key not in seen:
            total+=value.st_blocks*512
            seen.add(key)
    return total


def unallocated_peak(bound,already_allocated):
    if min(bound,already_allocated)<0:raise ValueError('Negative physical peak')
    return max(0,bound-already_allocated)


def job_states(ledger,call):
    ids=sorted({int(row['job_id']) for row in ledger['statistics'].values() if row.get('job_id')})
    result={job:'UNKNOWN' for job in ids}
    if ids:
        raw=call('/usr/bin/sacct','-X','-n','-P','-j',','.join(map(str,ids)),'--format=JobIDRaw,State')
        for line in raw.splitlines():
            fields=line.split('|')
            if len(fields)>=2 and fields[0].strip().isdecimal():
                result[int(fields[0])]=fields[1].strip()
    return result


def forecast(ledger,states,*,incoming_bytes,incoming_finetune=False):
    read=lambda p:json.loads(Path(p).read_text())
    metadata=read(CONTROL/'current_state.json')
    pulse=read(metadata['latest_pipeline_pulse'])
    sources=list((REPO/'configs/s_recipe/confirmation').glob('S-*.json'))
    sources+=list((REPO/'configs/s_recipe/extensions_20261124').glob('*_training.json'))
    checkpoint_future=0
    for path in sources:
        c=read(path)
        observed=pulse['cursors'].get(c['run'],{}).get('samples',0)
        if observed<c['samples']:
            # Actual unchanged S checkpoints are<200MB; quarterGiB covers each
            # registered1M checkpoint plus the next possible full-state handoff.
            checkpoint_future+=((c['samples']-observed+999999)//1000000+1)*(GiB//4)
    phase_future=0
    fit_future=0
    cpu_seal_future=0
    for handle,row in ledger['statistics'].items():
        if states.get(int(row.get('job_id',0))) not in LIVE:continue
        if row.get('mode')=='finetune':
            need=unallocated_peak(GiB,allocated(CONTROL/'finetune_20261124'/row['run']))
            fit_future+=need
            phase_future+=need
        elif row.get('mode')=='gpu':
            c=read(row['configuration'])
            points=row.get('readout_points') or ([row['samples']] if '_budget_' in handle else c['evaluation_samples'])
            current=sum(allocated(CONTROL/'scratch/readout_features'/c['run']/str(n)) for n in points)
            phase_future+=unallocated_peak(len(points)*GiB,current)
        elif row.get('mode')=='fullft_cpu':
            cpu_seal_future+=GiB//4
            phase_future+=GiB//4
    unsealed=0
    root=CONTROL/'finetune_20261124'
    if root.exists():
        for directory in root.iterdir():
            if directory.is_dir() and not (directory/'selected_model_receipt.json').exists():
                unsealed+=allocated(directory)
    remaining=claim_current()
    needed=checkpoint_future+phase_future+incoming_bytes
    pool=unsealed+fit_future+cpu_seal_future+(incoming_bytes if incoming_finetune else 0)
    return dict(admitted=remaining>=needed and (not incoming_finetune or pool<=8*GiB),
        remaining_line_bytes=remaining,planned_checkpoint_future=checkpoint_future,
        active_phase_future=phase_future,incoming_peak_bytes=incoming_bytes,
        unfinished_FT_pool_peak=pool,unfinished_FT_pool_limit=8*GiB,
        basis='physical allocated inodes deduplicated; future bytes only, not total reread or new science')
