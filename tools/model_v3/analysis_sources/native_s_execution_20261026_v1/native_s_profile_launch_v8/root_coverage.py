"""Actual supervisor/private/environment roots mapped to finite accounting."""
from __future__ import annotations
import json
import os
from pathlib import Path
import stat
import hashlib
import sys

SDK_KEYS=('WANDB_CACHE_DIR','WANDB_DATA_DIR','WANDB_CONFIG_DIR')


def ops_extension_source():
    """Explicit new ops source; prior82 QA covers only the original V2 file."""
    here=Path(__file__).absolute()
    policy=json.loads(here.with_name('coverage_ops_extension_provenance.json').read_text())
    original=policy['original_V2_source'];new=policy['extension_source']
    for row in (original,new):
        path=Path(row['path'])
        require(path.is_file() and not path.is_symlink() and path.stat().st_size==row['bytes']
            and hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256'],'Coverage ops source provenance differs')
    require(Path(new['path'])==here and policy['prior82_covers_extension'] is False,
        'New coverage extension cannot borrow prior82 acceptance')
    return dict(module=__name__,actual_file=str(here),source=new,original_V2_source=original,
        validation_scope='new_ops_compatibility_not_original82',prior82_covers_extension=False)


def task_scratch_metadata(root,*,job_id,uid=None):
    """Schema check only. Live inode/device/UID/mount checks remain in observe."""
    uid=os.getuid() if uid is None else uid
    path=Path(root['path'])
    require(root['kind']=='task_scratch' and root['reused'] is False and root['uid']==uid
        and path==Path('/tmp')/('mv3n_'+str(job_id)) and '..' not in path.parts
        and type(root['device']) is int and root['device']>=0
        and type(root['inode']) is int and root['inode']>0,
        'Fresh exact actual-job task_scratch metadata required')
    return str(path)


def require(value,message):
    if not value: raise ValueError(message)


def physical(path):
    value=Path(path)
    require(value.is_absolute() and '..' not in value.parts,'Absolute output path required')
    for parent in (value,*value.parents):
        try: info=parent.lstat()
        except FileNotFoundError: continue
        require(not stat.S_ISLNK(info.st_mode),'Output path has symlink ancestry')
        require(info.st_uid==os.getuid() or parent in (Path('/'),Path('/tmp'),Path('/share'),Path('/share/home')),
            'Output ancestry has another owner')
    return value.absolute()


def parent_observation():
    pid=os.getppid(); root=Path('/proc')/str(pid)
    require(root.stat().st_uid==os.getuid(),'Supervisor parent UID differs')
    before=(root/'stat').read_text().rsplit(')',1)[1].split()
    raw=(root/'cmdline').read_bytes(); require(len(raw)<=256*1024,'Bounded supervisor argv required')
    argv=[item.decode() for item in raw.split(b'\0') if item]
    io={name:os.readlink(root/'fd'/fd) for name,fd in (('stdout','1'),('stderr','2'))}
    after=(root/'stat').read_text().rsplit(')',1)[1].split()
    require(before[19]==after[19],'Supervisor PID changed during observation')
    return dict(pid=pid,uid=os.getuid(),start_ticks=int(after[19]),pgid=int(after[2]),sid=int(after[3]),
        argv=argv,argv_raw_sha256=hashlib.sha256(raw).hexdigest(),stdio=io,cgroup=(root/'cgroup').read_text(),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())


def filesystem_fact(path):
    rows=[]
    for line in Path('/proc/self/mountinfo').read_text().splitlines():
        left,right=line.split(' - ',1); fields=left.split(); tail=right.split()
        mount=Path(fields[4].replace('\\040',' '))
        if Path(path).is_relative_to(mount): rows.append((len(str(mount)),dict(mount=str(mount),filesystem=tail[0],source=tail[1],device=fields[2])))
    require(rows,'Actual mount observation missing')
    return max(rows,key=lambda row:row[0])[1]


def option(argv,name,*,required=True):
    hits=[]
    for index,item in enumerate(argv):
        if item==name:
            require(index+1<len(argv),'Supervisor option value missing: '+name); hits.append(argv[index+1])
        elif item.startswith(name+'='): hits.append(item[len(name)+1:])
    require(len(hits)==1 or (not required and not hits),'Unique explicit supervisor option required: '+name)
    return hits[0] if hits else None


def verify_snapshot_directory(storage,artifact):
    """Resolve every manifest-relative entry; field names are explicit, not guessed."""
    root=physical(artifact['path']); layout=artifact['relative_manifest']
    manifest=storage.read_bound(layout['raw_reference'])
    entries=manifest[layout['entries_field']]
    require(type(entries) is list,'Explicit source snapshot entry list required')
    expected=set()
    for entry in entries:
        relative=Path(entry[layout['path_field']])
        require(not relative.is_absolute() and '..' not in relative.parts,'Snapshot entry must remain relative to its actual root')
        target=physical(root/relative)
        reference=dict(path=str(target),bytes=entry[layout['bytes_field']],sha256=entry[layout['sha256_field']])
        require(storage.binding(target)==reference,'Source snapshot manifest entry differs: '+str(relative))
        require(str(target) not in expected,'Duplicate source snapshot manifest entry')
        expected.add(str(target))
    manifest_path=Path(layout['raw_reference']['path'])
    if manifest_path.is_relative_to(root): expected.add(str(manifest_path))
    actual={str(physical(path)) for path in root.rglob('*') if path.is_file()}
    require(actual==expected,'Snapshot manifest does not enumerate every physical source file')


def observe(callback,admission,principal,storage,contract,*,parent=None):
    """No guessed external directory names; known child SDK paths are explicit."""
    parent=parent_observation() if parent is None else parent
    require(parent['uid']==os.getuid() and str(admission['job_id'])==os.environ.get('SLURM_JOB_ID'),
        'Actual supervisor/job identity differs')
    require(parent['cgroup']==Path('/proc/self/cgroup').read_text(),'Supervisor/child actual Slurm cgroup differs')
    argv=parent['argv']; source=storage.read_bound(admission['supervisor_launch'])
    require(source['schema']=='native_S_actual_supervisor_launch_v2' and source['argv']==argv
        and source['job_id']==str(admission['job_id']) and source['uid']==os.getuid(),
        'Root raw supervisor launch projection differs from actual parent argv')
    require(storage.binding(source['supervisor_source']['path'])==source['supervisor_source']
        and Path(source['supervisor_source']['path'])==Path(contract['runtime_root'])/'tools/model_v3/run_supervised.py'
        and str(source['supervisor_source']['path']) in argv,'Actual supervisor source is not the combined runtime')
    require(sys.dont_write_bytecode,'Unknown Python cache output is forbidden; launch with bytecode writes disabled')
    child=physical(callback['output_root'])
    require(physical(option(argv,'--output-root'))==child,'Supervisor and child output roots differ')
    outer=int(option(argv,'--output-budget-bytes'))
    require(outer==admission['resource_envelope']['outer_output_budget_bytes'],'Actual supervisor outer budget differs')
    observations=[dict(role='child_output',path=str(child),type='directory',domain='durable')]
    for artifact in source['prepared_external_artifacts']:
        row=dict(role=artifact['role'],path=str(physical(artifact['path'])),type=artifact['type'],domain='durable')
        require(row['type'] in ('directory','file'),'Prepared external artifact type required')
        if row['type']=='file':
            require(storage.binding(row['path'])==artifact['raw_reference'],'Prepared external artifact bytes differ')
        else: verify_snapshot_directory(storage,artifact)
        observations.append(row)
    for role,flag in (('supervisor_record','--record'),('supervisor_observations','--observations')):
        observations.append(dict(role=role,path=str(physical(option(argv,flag))),type='file',domain='durable'))
    for role,value in parent['stdio'].items():
        require(Path(value).is_absolute(),'Unknown piped supervisor stdio requires a new explicit scheduler observation protocol')
        require(source['stdio'][role]==value,'Root stdio projection differs from actual parent fd')
        observations.append(dict(role='slurm_'+role,path=str(physical(value)),type='file',domain='durable'))
    receipt=callback['private_storage']
    receipt_ref=dict(path=receipt['receipt_path'],sha256=receipt['receipt_sha256'],bytes=Path(receipt['receipt_path']).stat().st_size)
    require(storage.binding(receipt_ref['path'])==receipt_ref,'Actual private storage receipt bytes differ')
    raw=storage.read_bound(receipt_ref)
    require({k:v for k,v in receipt.items() if k not in ('receipt_path','receipt_sha256')}==raw,
        'Callback private storage differs from actual supervisor receipt')
    require(receipt['job_id']==str(admission['job_id']) or str(receipt['job_id'])==str(admission['job_id']),
        'Private storage belongs to another actual job')
    require(receipt['boot_id']==parent['boot_id'] and receipt['uid']==os.getuid(),'Private supervisor boot/UID differs')
    source_pin=[row for row in contract['files'] if row['relative_path']=='tools/model_v3/private_runtime_storage.py']
    require(len(source_pin)==1 and receipt['source_sha256']==source_pin[0]['sha256'],
        'Actual private storage implementation differs from combined runtime')
    require(receipt['private_storage_budget_bytes']==admission['resource_envelope']['private_storage_budget_bytes'],
        'Actual private budget differs from Root resource envelope')
    observations.append(dict(role='private_receipt',path=str(physical(receipt_ref['path'])),type='file',domain='durable'))
    private_domains=admission['private_root_domains']
    require(len(private_domains)==len(receipt['roots']),'Every actual private root needs one domain binding')
    for root in receipt['roots']:
        path=physical(root['path']); info=path.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid==root['uid']==os.getuid()
            and info.st_dev==root['device'] and info.st_ino==root['inode'],'Actual private inode/device differs')
        domain=[row for row in private_domains if row['path']==str(path)]
        require(len(domain)==1 and domain[0]['domain'] in ('node_local_ephemeral','durable_compiler_cache'),
            'Private root accounting domain missing/ambiguous')
        fs=filesystem_fact(path)
        if domain[0]['domain']=='node_local_ephemeral':
            task_scratch_metadata(root,job_id=admission['job_id'])
            require(path.is_relative_to(Path('/tmp')) and fs['filesystem'] in ('tmpfs','xfs','ext4','overlay','btrfs'),
                'Ephemeral node-local claim lacks actual scratch/local filesystem evidence')
        else:
            require(root['kind']=='compiler_cache' and type(domain[0]['max_growth_bytes']) is int
                and 0<=domain[0]['max_growth_bytes']<=receipt['private_storage_budget_bytes'],
                'Durable compiler cache needs a finite extra growth hold')
        observations.append(dict(role='private_root',path=str(path),type='directory',domain=domain[0]['domain'],
            device=info.st_dev,inode=info.st_ino,filesystem_fact=fs))
    for key,value in receipt['environment'].items():
        require(os.environ.get(key)==value,'Actual private environment differs: '+key)
        path=physical(value)
        require(any(path.is_relative_to(Path(root['path'])) for root in receipt['roots']),
            'Private environment output lies outside sampled roots')
        observations.append(dict(role='environment:'+key,path=str(path),type='directory',domain='private_environment'))
    sdk=dict(WANDB_CACHE_DIR=str(child/'cache'),WANDB_DATA_DIR=str(child/'wandb_data'),
        WANDB_CONFIG_DIR=os.environ.get('WANDB_CONFIG_DIR'))
    require(sdk['WANDB_CONFIG_DIR'],'Root must explicitly bind WANDB_CONFIG_DIR; unknown HOME defaults are rejected')
    for key,value in sdk.items():
        observations.append(dict(role=key,path=str(physical(value)),type='directory',domain='durable'))
    observations.extend([dict(role='lineage',path=str(physical(admission['lineage_root'])),type='directory',domain='durable'),
        dict(role='management',path=str(physical(principal['durable_root'])),type='directory',domain='durable')])
    declared=admission['root_coverage']
    for row in observations:
        path=Path(row['path'])
        if path.exists():
            require(path.is_dir() if row['type']=='directory' else path.is_file(),'Actual output type differs: '+row['role'])
        matches=[item for item in declared if item['role']==row['role'] and item['path']==row['path'] and item['domain']==row['domain']]
        require(len(matches)==1,'Actual output omitted from Root coverage: '+row['role'])
        if row['domain'] in ('private_environment','node_local_ephemeral'): continue
        count_root=physical(matches[0]['accounting_root'])
        entries=[dict(path=str(child),type='directory'),dict(path=principal['durable_root'],type='directory'),
            dict(path=admission['lineage_root'],type='directory'),*admission['external_roots']]
        compatible=[item for item in entries if physical(item['path'])==count_root
            and (Path(row['path'])==count_root if item['type']=='file' else Path(row['path']).is_relative_to(count_root))]
        require(compatible,'Actual output has no registered disjoint counting root: '+row['role'])
    growth=sum(row.get('max_growth_bytes',0) for row in private_domains if row['domain']=='durable_compiler_cache')
    require(admission['resource_envelope']['additional_durable_private_growth_hold_bytes']>=growth,
        'Whole-segment hold omits possible durable private/cache growth')
    return dict(schema='native_S_actual_root_coverage_v2',observed=observations,private_receipt=receipt_ref,
        ops_extension_module_source=ops_extension_source(),
        parent_observation=parent,planned_SDK_environment=sdk,private_budget_bytes=receipt['private_storage_budget_bytes'],
        private_bindings=receipt,sampled_private_semantics=receipt['peak_semantics'],all_actual_outputs_covered=True)
