#!/bin/bash
#SBATCH --job-name=PPE-Benson-fixed-published-GA
#SBATCH --partition=cpu
#SBATCH --exclude=compute-0-2,compute-0-18,compute-0-21
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=01:30:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/PPE_Benson_%j.log
set -euo pipefail
repo=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
export PYTHONPATH="$repo:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd "$repo"
findmnt -T "$repo"
df -B1 "$repo" /tmp
df -Pi "$repo" /tmp
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import json,os,subprocess,time,signal,urllib.request,tarfile
from pathlib import Path
from workflows.benchmark_data.admission import protect
entry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'
quota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')
def safe():protect(root,3*1024**3,quota,own_concurrent_bytes=24*1024**3)
safe();out=b1/'PPE_Benson'/('job_'+os.environ['SLURM_JOB_ID']);out.mkdir(parents=True,exist_ok=False)
tmp=out/'tmp';tmp.mkdir();env=dict(os.environ,TMPDIR=str(tmp),PIP_NO_CACHE_DIR='1',XDG_CACHE_HOME=str(out/'cache'))
def run(args,**kwargs):
    safe();p=subprocess.Popen(args,env=env,start_new_session=True,**kwargs)
    try:
        while p.poll() is None:safe();time.sleep(5)
    except BaseException:
        os.killpg(p.pid,signal.SIGTERM);p.wait();raise
    return p.returncode
base='/share/home/zixiao/.conda/envs/chemprop/bin/python';venv=out/'venv'
if run([base,'-m','venv','--system-site-packages',str(venv)]):raise RuntimeError('Benson environment preparation failed')
python=str(venv/'bin/python')
commit='cecd9819ba60884efce483ceb3fb18d03ac27f84';archive=out/'pgradd_source.tar.gz'
with urllib.request.urlopen('https://codeload.github.com/VlachosGroup/PythonGroupAdditivity/tar.gz/'+commit,timeout=60) as response,archive.open('xb') as stream:
    total=0
    while True:
        block=response.read(65536)
        if not block:break
        total+=len(block)
        if total>32*1024**2:raise ValueError('Benson source archive exceeds peak forecast')
        safe();stream.write(block)
# pip accepts the pinned archive; no project source or base environment is changed.
with (out/'pip_install.log').open('x') as stream:
    rc=run([python,'-m','pip','install','--disable-pip-version-check','--no-cache-dir',str(archive)],stdout=stream,stderr=subprocess.STDOUT)
if rc:raise RuntimeError('Benson pinned package installation failed')
source_code="\nimport json,math,os,sys,time,importlib.metadata\nfrom pathlib import Path\nfrom collections import Counter\nimport pyarrow as pa\nimport pyarrow.parquet as pq\nimport pgradd.ThermoChem\nfrom pgradd.GroupAdd.Library import GroupLibrary\nfrom workflows.benchmark_data.admission import protect\nentry=json.loads(Path('configs/benchmark_data/B0.DELIVERY.json').read_text());root=Path(entry['data_root']);b1=root.parent/'benchmark_B1_20261119'\nmanifest=json.loads(Path(entry['manifest']).read_text());out=Path(sys.argv[1])\nquota=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json')\ndef safe():protect(root,3*1024**3,quota,own_concurrent_bytes=24*1024**3)\nproof=b1/'endpoint_catalog/job_4536889/manifest.json';assert json.loads(proof.read_text())['deferred_registry_full_inventory_verified']\ntargets_path=Path(manifest['PPE_targets']['path'])\ntarget_rows=pq.read_table(targets_path).to_pylist();targets={r['record_id']:r for r in target_rows}\nif len(targets)!=len(target_rows):raise ValueError('Ambiguous original PPE target identity')\n# Fix BensonGA, temperature, units and source database before any target values are consumed.\nlib=GroupLibrary.Load('BensonGA')\nschema=pa.schema([('record_id',pa.string()),('retained',pa.bool_()),('domain_eligible',pa.bool_()),('feature_smiles',pa.string()),('experimental_DeltaHf_kcal_mol',pa.float64()),('BensonGA_DeltaHf_kcal_mol',pa.float64()),('residual_experimental_minus_BensonGA_kcal_mol',pa.float64()),('published_PM7_DeltaHf_kcal_mol',pa.float64()),('residual_experimental_minus_published_PM7_kcal_mol',pa.float64()),('Benson_groups_json',pa.string()),('state',pa.string()),('reason',pa.string())])\ncounts=Counter();source=Path(manifest['source_groups']['PPE1694']['records']);start=time.monotonic()\nwith pq.ParquetWriter(out/'PPE_Benson_targets.parquet',schema,compression='zstd') as writer:\n    for batch in pq.ParquetFile(source).iter_batches(batch_size=32):\n        buffer=[]\n        for row in batch.to_pylist():\n            target=targets[row['record_id']]\n            if not target['target_name_bound']:raise ValueError('PPE original experiment is not name-bound')\n            smiles=row['model_smiles'] or row['original_smiles']\n            prediction=None;groups=None;reason=None;residual=None\n            experimental=target['experimental_DeltaHf_kcal_mol']\n            try:\n                native_groups=lib.GetDescriptors(smiles)\n                groups={str(k):float(v) for k,v in native_groups.items()}\n                estimate=lib.Estimate(native_groups,'thermochem')\n                prediction=float(estimate.get_H(298.15,units='kcal/mol'))\n                if not math.isfinite(prediction):raise ValueError('Nonfinite native Benson estimate')\n                if experimental is not None and math.isfinite(experimental):residual=float(experimental-prediction)\n                state='BENSON_GA_ESTIMATE_READY'\n            except Exception as error:\n                prediction=None;state='BENSON_GA_UNRESOLVED_NATIVE_RECORD';reason=type(error).__name__+': '+str(error)[:500]\n            counts[state]+=1;counts['domain_eligible_source_rows']+=bool(row['retained'] and row['domain_eligible'])\n            counts['domain_eligible_Benson_residual_points']+=bool(row['retained'] and row['domain_eligible'] and residual is not None)\n            buffer.append(dict(record_id=row['record_id'],retained=row['retained'],domain_eligible=row['domain_eligible'],feature_smiles=smiles,experimental_DeltaHf_kcal_mol=experimental,BensonGA_DeltaHf_kcal_mol=prediction,residual_experimental_minus_BensonGA_kcal_mol=residual,published_PM7_DeltaHf_kcal_mol=target['published_PM7_DeltaHf_kcal_mol'],residual_experimental_minus_published_PM7_kcal_mol=target['residual_experimental_minus_published_PM7_kcal_mol'],Benson_groups_json=json.dumps(groups,sort_keys=True) if groups is not None else None,state=state,reason=reason))\n        safe();writer.write_table(pa.Table.from_pylist(buffer,schema=schema))\n        print('PPE_BENSON_NATIVE_SOURCE_PROGRESS',sum(counts[s] for s in ('BENSON_GA_ESTIMATE_READY','BENSON_GA_UNRESOLVED_NATIVE_RECORD')),flush=True)\nreport=dict(status='PPE_BENSON_NATIVE_BASELINE_AND_RESIDUAL_BINDING_CLOSED',job=os.environ['SLURM_JOB_ID'],method='pGrAdd BensonGA fixed published gas-phase group values and native corrections',pgradd_version=importlib.metadata.version('pgradd'),temperature_K=298.15,enthalpy_unit='kcal/mol',method_reference='https://doi.org/10.1016/j.cpc.2021.108277',source_repository='https://github.com/VlachosGroup/PythonGroupAdditivity',source_commit='cecd9819ba60884efce483ceb3fb18d03ac27f84',license='MIT',source_entry=str(Path('configs/benchmark_data/B0.DELIVERY.json').resolve()),source_records=str(source),source_original_targets=str(targets_path),scope_proof=str(proof),counts=dict(counts),records=str(out/'PPE_Benson_targets.parquet'),elapsed_seconds=time.monotonic()-start,learned_group_values=False,experimental_labels_refit=False,original_experimental_targets_modified=False,missing_group_values_filled=False,Joback_substituted=False,PM7_recomputed=False,model_fits_run=False,task_screen_decisions_produced=False,independent_numeric_readback=False)\nsafe();(out/'manifest.json').write_text(json.dumps(report,indent=2)+'\\n');print('PPE_BENSON_SOURCE_CLOSED',json.dumps(report),flush=True)\n"
with (out/'native_Benson_stdout.txt').open('x') as stream:
    rc=run([python,'-B','-c',source_code,str(out)],stdout=stream,stderr=subprocess.STDOUT)
with (out/'effective_freeze.txt').open('x') as stream:run([python,'-m','pip','freeze'],stdout=stream)
if rc:raise RuntimeError('Benson native baseline producer failed: '+str(rc))
print('PPE_BENSON_PRODUCER_COMPLETE',out/'manifest.json',flush=True)

PY
