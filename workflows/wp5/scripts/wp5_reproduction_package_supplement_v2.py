#!/usr/bin/env python3
"""Supplement a closed reproduction package with actual ELF libraries/env locks.

Original package, source libraries, environment, scientific protocol/IDs/recipes
remain unchanged. Actual ldd uses each software's protocol environment. Only safe
conda metadata keys are exported (no token URLs). Root sole metadata submission.
"""
from __future__ import annotations
import argparse,ast,concurrent.futures,hashlib,json,multiprocessing,os,platform,re,shutil,socket,subprocess,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
NODES={'compute-0-'+str(n) for n in (12,13,14,17,18,19)}
SAFE_KEYS=('name','version','build','build_number','subdir','sha256','md5','fn','license','license_family')
BARRIER=None
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for data in iter(lambda:f.read(8<<20),b''):h.update(data)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def write(p,j):
    with Path(p).open('x') as f:json.dump(j,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
def reference(p):return {'path':str(p),'bytes':Path(p).stat().st_size,'sha256':sha(p)}
def parse_ldd(text):
    files=[];virtual=[]
    for raw in text.splitlines():
        line=raw.strip()
        if not line:continue
        if 'not found' in line:raise ValueError('Unresolved actual ELF dependency:'+line)
        if re.match(r'linux-vdso(?:64)?\.so',line):
            virtual.append({'soname':line.split()[0],'source':'KERNEL_VIRTUAL_DSO_NOT_A_REGULAR_LIBRARY_FILE'});continue
        hit=re.match(r'(\S+)\s+=>\s+(/\S+)(?:\s+\(0x[0-9a-fA-F]+\))?\s*$',line)
        if hit:files.append({'soname':hit[1],'loader_resolved_path':hit[2]});continue
        hit=re.match(r'(/\S+)\s+\(0x[0-9a-fA-F]+\)\s*$',line)
        if hit:files.append({'soname':Path(hit[1]).name,'loader_resolved_path':hit[1]});continue
        if 'statically linked' in line or 'not a dynamic executable' in line:
            raise ValueError('Expected actual dynamic software dependency closure')
        raise ValueError('Unrecognized actual ldd output; do not invent dependency:'+line)
    if not files:raise ValueError('No actual file dependencies resolved')
    return files,virtual
def safe_lock(prefix,family,software):
    meta=prefix/'conda-meta'
    if not meta.is_dir():raise ValueError('Actual software prefix conda-meta unavailable:'+str(prefix))
    rows=[]
    for p in sorted(meta.glob('*.json')):
        raw=read(p);row={k:raw[k] for k in SAFE_KEYS if k in raw}
        if not all(k in row for k in ('name','version','build')):raise ValueError('Conda record required identity absent:'+p.name)
        # These dependency constraints are names/version expressions, not URLs.
        dependencies=[]
        for dep in raw.get('depends',[]):
            if not isinstance(dep,str) or '://' in dep or re.search(r'(?i)(token=|password=|/t/)',dep):
                raise ValueError('Unsafe non-package dependency constraint omitted rather than archived')
            dependencies.append(dep)
        row['depends']=dependencies;row['source_conda_metadata_filename']=p.name;row['source_conda_metadata_sha256']=sha(p)
        rows.append(row)
    if not rows:raise ValueError('Actual software conda package records empty')
    return {'schema':'WP5_SAFE_SOFTWARE_CONDA_PREFIX_LOCK_V1','family':family,
        'software_version_id':software['software_version_id'],'software_version':software['version'],
        'source_prefix':str(prefix),'packages':rows,'package_count':len(rows),
        'explicit_specs':[r['name']+'='+r['version']+'='+r['build'] for r in rows],
        'export_source':'ACTUAL_PREFIX_CONDA_META_PACKAGE_RECORDS','URLs_tokens_channels_history_not_exported':True,
        'all_loaded_ELF_file_bytes_separately_SHA_pinned':True}
def initialize(barrier):
    global BARRIER;BARRIER=barrier
def lane(arg):
    entries,out=arg;BARRIER.wait(timeout=180);result=[]
    for entry in entries:
        kind=entry['kind'];old=entry.get('asset')
        if kind=='original_reference':
            item=entry['reference'];p=Path(item['path']);before=p.stat()
            if sha(p)!=item['sha256'] or (item.get('bytes') is not None and before.st_size!=item['bytes']):raise ValueError('Original auxiliary reference changed')
            if p.stat().st_mtime_ns!=before.st_mtime_ns:raise ValueError('Original auxiliary reference changed during readback')
            result.append({'kind':kind,'reference':item,'worker_pid':os.getpid(),'readback_verified':True});continue
        if kind=='existing':
            copied=Path(old['path']);before=copied.stat()
            if before.st_size!=old['bytes'] or sha(copied)!=old['sha256']:raise ValueError('Original frozen asset bytes/SHA differs:'+str(copied))
            if copied.stat().st_mtime_ns!=before.st_mtime_ns:raise ValueError('Original frozen asset changed during verification')
            result.append({'kind':kind,'asset':old,'worker_pid':os.getpid(),'readback_verified':True});continue
        source=Path(entry['path']);resolved=source.resolve(strict=True);before=resolved.stat();actual=sha(resolved)
        if not resolved.is_file():raise ValueError('Actual regular asset required')
        if entry.get('sha256') and actual!=entry['sha256']:raise ValueError('Additional frozen source/library SHA changed')
        role=entry['role'];destination=Path(out)/'assets'/role/(actual+'_'+hashlib.sha256(str(resolved).encode()).hexdigest()[:12]+'_'+resolved.name)
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():raise FileExistsError('Duplicate new asset target')
        shutil.copy2(resolved,destination)
        if sha(destination)!=actual or resolved.stat().st_mtime_ns!=before.st_mtime_ns or resolved.stat().st_size!=before.st_size:
            raise ValueError('New frozen asset copy/readback/source stability differs')
        asset={'role':role,'source_path':str(source),'resolved_source_path':str(resolved),'path':str(destination),
            'sha256':actual,'bytes':before.st_size,'source_uid':before.st_uid,'mode':before.st_mode&0o777,'worker_pid':os.getpid()}
        result.append({'kind':kind,'asset':asset,'worker_pid':os.getpid(),'readback_verified':True})
    return {'worker_pid':os.getpid(),'assets':result}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--original-manifest',type=Path,default=ROOT/'reproduction_package/job_4513947/manifest.json')
    p.add_argument('--additional-sources',type=Path);p.add_argument('--out',type=Path);p.add_argument('--workers',type=int,default=24);a=p.parse_args()
    if a.check:
        ast.parse(Path(__file__).read_text())
        files,virtual=parse_ldd('linux-vdso.so.1 (0x123)\n libmopac.so.2 => /env/lib/libmopac.so.2 (0x123)\n /lib64/ld-linux-x86-64.so.2 (0x123)')
        assert len(files)==2 and virtual
        try:parse_ldd('libfoo.so => not found')
        except ValueError:pass
        else:raise AssertionError('Missing library was falsely accepted')
        print('PACKAGE_SUPPLEMENT_AST_AND_LDD_PARSER_CHECK_PASS_NO_COPY_NO_QM');return
    if not os.environ.get('SLURM_JOB_ID') or a.workers<24 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers or socket.gethostname().split('.')[0] not in NODES:
        raise ValueError('Authorized actual24+ worker Slurm allocation required')
    original=read(a.original_manifest)
    if original['schema']!='WP5_REPRODUCTION_PACKAGE_V1' or original['status']!='REPRODUCTION_PACKAGE_CLOSED':raise ValueError('Actual original closed reproduction package required')
    protocol=read(original['protocol']['path'])
    if sha(original['protocol']['path'])!=original['protocol']['sha256']:raise ValueError('Original frozen protocol changed')
    out=a.out or ROOT/'reproduction_package'/('supplement_job_'+os.environ['SLURM_JOB_ID'])
    if not out.resolve().is_relative_to(ROOT) or out.exists():raise ValueError('Immutable new own supplement path required')
    out.mkdir(parents=True);start=time.monotonic();items=[{'kind':'existing','asset':asset} for asset in original['assets']]
    for key in ('environment','recipes','protocol','registry','audit_membership'):
        value=original.get(key)
        if isinstance(value,dict) and {'path','sha256'}.issubset(value):items.append({'kind':'original_reference','reference':value})
    original_sources={asset['source_path']:asset for asset in original['assets']};dependencies={};software_exports={};resolved_assets={}
    for family,software in original['software_versions'].items():
        binary=Path(software['executable']);actual=sha(binary)
        if actual!=software['sha256']:raise ValueError('Original executable SHA changed')
        runtime_env=protocol.get(family+'_environment',{})
        env={**os.environ,**{k:str(v) for k,v in runtime_env.items()}}
        proc=subprocess.run(['ldd',str(binary)],capture_output=True,text=True,env=env,timeout=60)
        if proc.returncode!=0:raise ValueError('Actual ldd failed for '+family+':'+proc.stderr[:1000])
        libs,virtual=parse_ldd(proc.stdout);required='libmopac.so' if family=='mopac' else 'libxtb.so'
        if not any(required in lib['soname'] for lib in libs):raise ValueError('Actual core implementation library absent:'+family)
        prefix=binary.parent.parent.resolve();lock=safe_lock(prefix,family,software)
        lock_path=out/(family+'_environment_lock.json');write(lock_path,lock)
        if read(lock_path)!=lock:raise ValueError('Safe software environment JSON readback differs')
        software_exports[family]=reference(lock_path)
        for lib in libs:
            source=Path(lib['loader_resolved_path']);resolved=source.resolve(strict=True);lib['resolved_source_path']=str(resolved)
            if str(resolved) not in resolved_assets:
                resolved_assets[str(resolved)]={'kind':'shared_library','path':str(resolved),'role':'software_shared_library'}
        dependencies[family]={'source_executable':str(binary),'source_executable_sha256':actual,
            'required_core_library_soname_prefix':required,'ldd_command':['ldd',str(binary)],
            'ldd_stdout':proc.stdout,'ldd_stdout_sha256':hashlib.sha256(proc.stdout.encode()).hexdigest(),
            'runtime_environment':{k:v for k,v in runtime_env.items() if k in {'LD_LIBRARY_PATH','XTBPATH','OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS'}},
            'libraries':libs,'virtual_libraries_not_files':virtual,'conda_prefix':str(prefix)}
    items.extend(resolved_assets.values())
    additional=read(a.additional_sources) if a.additional_sources else None
    if additional:
        if not isinstance(additional.get('files'),list):raise ValueError('Additional inventory must provide files list')
        for entry in additional['files']:
            if not {'path','sha256','role'}.issubset(entry):raise ValueError('Frozen additional path/SHA/role required')
            if entry['path'] in original_sources:
                if entry['sha256']!=original_sources[entry['path']]['sha256']:raise ValueError('New version must use independent source path')
                continue
            items.append({'kind':'additional_source',**entry})
    # Every worker gets a nonempty owned shard, and the barrier runs in worker
    # functions, ensuring actual24 hash/readback/copy participants.
    batches=[items[i::a.workers] for i in range(a.workers)]
    if any(not b for b in batches):raise ValueError('Not enough actual distinct assets for24 effective workers')
    ctx=multiprocessing.get_context('spawn');barrier=ctx.Barrier(a.workers)
    with concurrent.futures.ProcessPoolExecutor(max_workers=a.workers,mp_context=ctx,initializer=initialize,initargs=(barrier,)) as pool:
        result=list(pool.map(lane,[(b,str(out)) for b in batches],chunksize=1))
    pids={r['worker_pid'] for r in result}
    if len(pids)!=a.workers:raise ValueError('Effective24 worker participation not observed')
    rows=[r for worker in result for r in worker['assets']]
    assets=[r['asset'] for r in rows if 'asset' in r];by_resolved={r.get('resolved_source_path',r['source_path']):r for r in assets}
    for family,dep in dependencies.items():
        for lib in dep['libraries']:
            asset=by_resolved[lib['resolved_source_path']]
            lib.update(frozen_asset={'path':asset['path'],'sha256':asset['sha256'],'bytes':asset['bytes']},
                recreate_soname_as=lib['soname'])
    manifest=dict(original);manifest.update(job_id=os.environ['SLURM_JOB_ID'],seconds=time.monotonic()-start,
        assets=assets,asset_bytes=sum(r['bytes'] for r in assets),original_manifest=reference(a.original_manifest),
        software_environment_exports=software_exports,software_binary_dependency_closure=dependencies,
        package_supplement={'schema':'WP5_SOFTWARE_RUNTIME_PACKAGE_SUPPLEMENT_V1','status':'ALL_ACTUAL_ASSET_BYTES_SHA_READBACK_VERIFIED',
          'source_path_digest_distinguishes_equal_SHA_basename_from_distinct_prefixes':True,'original_assets_preserved':len(original['assets']),'original_auxiliary_refs_readback_verified':[r['reference'] for r in rows if r['kind']=='original_reference'],'additional_library_assets':sum(r['kind']=='shared_library' for r in rows),
          'additional_source_assets':sum(r['kind']=='additional_source' for r in rows),
          'actual_worker_count':len(pids),'worker_pids':sorted(pids),'software_IDs_protocol_science_and_recipes_unchanged':True,
          'main_executables_are_dynamic_ELF_frontends_not_complete_implementations':True,
          'system_libraries_are_pinned_readonly_never_installed_or_overridden':True,
          'recreate_runtime_recipe':'Use original packaged main executable plus listed SHA-verified libraries at their SONAME basenames in a recreated prefix/lib; preserve protocol family LD_LIBRARY_PATH/XTBPATH and pinned parameter assets. No host library/environment is changed by this supplement.',
          'additional_sources':reference(a.additional_sources) if a.additional_sources else None,
          'library_context':{'system':platform.system(),'machine':platform.machine(),'kernel_release':platform.release()}},
        script_sha256=sha(__file__),original_data_written=False,new_QM_calls=0,environment_modified=False)
    # Original chemprop environment, recipes, software version IDs, audit and
    # science references remain exactly the original fields.
    write(out/'manifest.json',manifest)
    print(json.dumps({'status':manifest['status'],'manifest':str(out/'manifest.json'),'original_assets':len(original['assets']),
        'assets':len(assets),'asset_bytes':manifest['asset_bytes'],'workers':len(pids)}))
if __name__=='__main__':main()
