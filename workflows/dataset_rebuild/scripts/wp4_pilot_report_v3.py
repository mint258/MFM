"""Produce WP4 decision numbers from the formal native pilot, with no LMDB writes.

Use the formal whole-molecule 10,000-record panel, completed WP1 quality file,
closed native bucket roots, their receipts/metadata, and a root capacity snapshot.
Bounded and synthetic populations are deliberately ineligible for extrapolation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import concurrent.futures
import hashlib
import json
import math
import multiprocessing
import os
from pathlib import Path
import re
import socket
import sys
import time

ROOT = Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
DEPS = Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps')
CD_TASKS = {'pm7_ESP', 'pm7_water', 'pm7_octanol', 'pm7_cation', 'pm7_anion'}
UNFINISHED = {'INTERRUPTED_DEADLINE', 'INTERRUPTED_STOP', 'NOT_STARTED_DEADLINE', 'NOT_STARTED_STOP'}
SCF = re.compile(r'SCF DOES NOT CONVERGE|SCF NOT CONVERGED|SCF FAILED|UNABLE TO ACHIEVE SELF-CONSISTENCY|SCC IS NOT CONVERGED|SELF CONSISTENT CHARGE ITERATOR DID NOT CONVERGE', re.I)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024*1024), b''):
            value.update(block)
    return value.hexdigest()


def q(value):
    return "'" + str(value).replace("'", "''") + "'"


def read_json(path):
    return json.loads(Path(path).read_text())


def save_json(path, value):
    pending = Path(str(path) + '.pending')
    pending.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    os.replace(pending, path)


def number(value):
    return isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value)


def distribution(values):
    import numpy as np
    data = np.asarray([float(x) for x in values if number(x)], dtype=float)
    if not len(data):
        return {'n': 0, 'mean': None, 'p50': None, 'p90': None, 'p99': None, 'min': None, 'max': None}
    p50, p90, p99 = np.quantile(data, [.5, .9, .99])
    return {'n': len(data), 'mean': float(data.mean()), 'p50': float(p50), 'p90': float(p90),
            'p99': float(p99), 'min': float(data.min()), 'max': float(data.max())}


def ratio(numerator, denominator):
    return numerator/denominator if denominator else None


def positive_count(values, predicate):
    values = [value for value in values if number(value)]
    count = sum(bool(predicate(value)) for value in values)
    return {'n': len(values), 'count': count, 'fraction': ratio(count, len(values)), 'distribution': distribution(values)}


def rowdicts(db, sql):
    cursor = db.execute(sql)
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def deps():
    try:
        import pyarrow.parquet as pq
        import numpy as np
        import duckdb
    except ModuleNotFoundError:
        sys.path.insert(0, str(DEPS))
        import pyarrow.parquet as pq
        import numpy as np
        import duckdb
    return pq, np, duckdb


def read_receipt(receipt_path):
    """Parallel bounded per-molecule read; return summaries, never AO matrices."""
    pq, np, _ = deps()
    receipt_path = Path(receipt_path)
    receipt = read_json(receipt_path)
    if receipt.get('status') not in {'COMPLETE_WITH_RECORDED_OUTCOMES','COMPLETE_WITH_RECORDED_OUTCOME'}:
        return {'receipt_path': str(receipt_path), 'receipt': receipt, 'calls': [],
                'issue': 'Receipt is partial; its absent final results are not a measured zero'}
    ref = receipt.get('parquet', {})
    path = Path(ref.get('path', str(receipt_path.parent/'results.parquet')))
    if not path.is_file():
        raise ValueError('Closed receipt Parquet missing: ' + str(path))
    actual = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': sha(path)}
    if ref.get('bytes') is not None and actual['bytes'] != ref['bytes']:
        raise ValueError('Closed receipt Parquet size differs: ' + str(path))
    if ref.get('sha256') and actual['sha256'] != ref['sha256']:
        raise ValueError('Closed receipt Parquet SHA differs: ' + str(path))
    calls = []
    for row in pq.read_table(path, use_threads=False).to_pylist():
        detail = json.loads(row['details_json'])
        value = detail.get('values', {})
        status = row['status']
        launched = bool(detail.get('argv')) and not status.startswith(('SKIPPED_', 'Q03_SOURCE', 'NOT_STARTED_'))
        call = {key: row.get(key) for key in ('record_id','molecule_id','task','family','status','failure_code',
            'size_stratum','natoms','heavy_atoms','elapsed_seconds','qm_child_cpu_seconds','raw_total_bytes',
            'aux_bytes','archive_bytes','payload_sha256','Q01_gradient_norm_kcal_mol_A','Q02_delta_HOF_kcal_mol')}
        call.update(launched=launched, job_id=detail.get('job_id',receipt.get('job_id')),
          B_base_success=detail.get('B_base_success'), returncode=detail.get('returncode'),
          confirmed_scf_failure=('XTB_SCC_FAILED' in detail.get('qc_codes',[]) or
              bool(SCF.search(' '.join(detail.get('diagnostic_lines',[]))+' '+str(detail.get('failure_reason',''))))),
          normal_end=value.get('normal_end'), qc_codes=detail.get('qc_codes',[]),
          missing_properties=detail.get('missing_properties',[]), length_issues=detail.get('length_issues',[]),
          available_properties=[key for key,item in value.items() if item is not None],
          null_properties=[key for key,item in value.items() if item is None],
          empty_properties=[key for key,item in value.items() if isinstance(item,(list,dict)) and len(item)==0],
          observed_zero_scalars=[key for key,item in value.items() if number(item) and item==0],
          legitimate_empty_sparse_properties=['mulliken_overlap_population_pairs']
            if value.get('mulliken_overlap_population_pairs')==[] and
              (value.get('mulliken_overlap_qc') or {}).get('status')=='AVAILABLE_CHARGE_QC_PASS' and
              (value.get('mulliken_overlap_qc') or {}).get('requested_pair_count')==0 else [],
          aux_archived=detail.get('aux_archived'), scratch_bytes_removed=detail.get('scratch_bytes_removed'),
          preserved_scratch=detail.get('preserved_scratch'), scratch_cleanup_error=detail.get('scratch_cleanup_error'),
          xyz_roundtrip_max_error_A=detail.get('xyz_roundtrip_max_error_A'),
          archive_path=detail.get('archive',{}).get('path'),
          archive_per_call_bytes=detail.get('archive',{}).get('per_call_compressed_bytes',row.get('archive_bytes')),
          details_json_bytes=len(row['details_json'].encode()),
          archived_files=detail.get('archived_files',[]), details_sha256=hashlib.sha256(row['details_json'].encode()).hexdigest(),
          property_failure_lines=value.get('property_failure_lines',[]), software_version_lines=detail.get('software_version_lines',[]),
          polar_asymmetry_bohr3=value.get('static_polar_block',{}).get('max_antisymmetric_component_bohr3') if value.get('static_polar_block') else None,
          mulliken_qc=value.get('mulliken_overlap_qc'),
          mulliken_reconstruction_error_e=value.get('mulliken_reconstruction_charge_max_error_e'),
          spin_Sz=value.get('spin_Sz'),spin_S2=value.get('spin_S2'),
          IP_eV=value.get('IP_eV'),EA_eV=value.get('EA_eV'),Gsolv_Eh=value.get('Gsolv_Eh'),
          dielectric_energy_eV=value.get('dielectric_energy_eV'),cosmo_area_A2=value.get('cosmo_area_A2'),cosmo_volume_A3=value.get('cosmo_volume_A3'),
          NFOD_e=value.get('NFOD_e'),
          frequency_count=len(value['frequencies_cm_inverse']) if isinstance(value.get('frequencies_cm_inverse'),list) else None,
          negative_frequency_count_raw=value.get('negative_frequency_count_raw'),
          imaginary_frequency_count_below_minus20=value.get('imaginary_frequency_count_below_minus20'),
          thermo_supported=value.get('thermo_tot_H_cal_mol_Cp_cal_mol_K_S_cal_mol_K_S_J_mol_K') is not None,
          ZPE_Eh=value.get('ZPE_Eh'), enthalpy_Eh=value.get('enthalpy_Eh'),
          hessian_warnings=value.get('warnings',[]),
          derived_pm7=value.get('derived_from_same_geometry_charged_states',{}))
        charge=value.get('net_charges_e',value.get('charges_e'))
        call['charge_sum_e']=float(sum(charge)) if isinstance(charge,list) and all(number(x) for x in charge) else None
        call['esp_charge_sum_e']=float(sum(value['esp_charges_e'])) if isinstance(value.get('esp_charges_e'),list) else None
        fukui=value.get('fukui')
        if isinstance(fukui,list) and fukui:
            call['fukui_column_sums']=np.asarray(fukui,dtype=float).sum(axis=0).tolist()
        quad=value.get('molecular_quadrupole_traceless_au')
        call['quadrupole_trace_au']=quad[0]+quad[2]+quad[5] if isinstance(quad,list) and len(quad)==6 else None
        call['homo_eV']=value.get('homo_eV');call['lumo_eV']=value.get('lumo_eV')
        if call['frequency_count'] is not None:
            call['frequency_observation_valid']=(call['frequency_count']==3*int(row['natoms']) and call['returncode']==0
                and not call['confirmed_scf_failure'] and status not in UNFINISHED|{'TIMEOUT','RUNNER_ERROR','CALCULATION_FAILED'})
        force=value.get('forces_eV_A')
        if isinstance(force,list) and force:
            forces=np.asarray(force,dtype=float)
            call['atomic_force_norm_eV_A']=np.linalg.norm(forces,axis=1).tolist()
            call['force_component_eV_A']=forces.reshape(-1).tolist()
        if value.get('perturb_seed') is not None and value.get('perturb_sigma_A') is not None:
            noise=np.random.default_rng(value['perturb_seed']).normal(0,value['perturb_sigma_A'],(int(row['natoms']),3))
            call['configured_perturb_sigma_A']=value['perturb_sigma_A']
            call['seed_reconstructed_noise_components_A']=noise.reshape(-1).tolist()
        # Exact paired no-POLAR probe uses the same results.parquet schema.
        if detail.get('paired_cost') is not None:
            call['paired_cost']=detail['paired_cost']
        calls.append(call)
    archive=receipt.get('archive')
    if archive and Path(archive['path']).is_file() and Path(archive['path']).stat().st_size != archive['bytes']:
        raise ValueError('Closed receipt archive size differs: '+archive['path'])
    return {'receipt_path':str(receipt_path),'receipt_sha256':sha(receipt_path),'receipt':receipt,
            'parquet':actual,'archive':archive,'calls':calls,'worker_pid':os.getpid()}


def capacity(path):
    if not Path(path).is_file():
        return {'available':False,'reason':'Capacity/quota snapshot missing','scheduled_cpus':None,'physical_cores':None}
    raw=read_json(path); nodes=[]
    for name,entry in sorted(raw.get('nodes',{}).items()):
        if name not in {f'compute-0-{i}' for i in range(14,20)}: continue
        text=entry.get('stdout','')
        def field(key):
            found=re.search(r'\b'+key+r'=([^\s]+)',text)
            return found.group(1) if found else None
        def integer(key):
            value=field(key)
            return int(value) if value is not None and value.isdigit() else None
        cpus, threads = integer('CPUTot'), integer('ThreadsPerCore')
        nodes.append({'node':name,'CPUTot':cpus,'CPUEfctv':integer('CPUEfctv'),'CPUAlloc':integer('CPUAlloc'),
          'ThreadsPerCore':threads,'physical_cores':cpus//threads if cpus and threads else None,
          'RealMemory_MiB':integer('RealMemory'),'AllocMem_MiB':integer('AllocMem'),
          'FreeMem_MiB':integer('FreeMem'),'state':field('State'),'partitions':field('Partitions')})
    quota=None
    quota_raw=raw.get('quota',{})
    if quota_raw.get('exit_code',quota_raw.get('rc'))==0:
        for line in quota_raw.get('stdout','').splitlines():
            tokens=line.split()
            if len(tokens)>=4 and tokens[0].startswith('/'):
                try: used,soft,hard=[int(x.rstrip('*')) for x in tokens[1:4]]
                except ValueError: continue
                finite=[value for value in (soft,hard) if value>0]
                limit=min(finite) if finite else None
                quota={'filesystem':tokens[0],'used_KiB':used,'soft_KiB':soft,'hard_KiB':hard,
                  'remaining_bytes':(limit-used)*1024 if limit is not None else None,
                  'remaining_TB_decimal':(limit-used)*1024/1e12 if limit is not None else None}
                break
    return {'available':len(nodes)==6 and all(n['CPUTot'] is not None for n in nodes),
      'source':str(path),'sha256':sha(path),'time_UTC':raw.get('time_UTC'),'nodes':nodes,
      'scheduled_cpus':sum(n['CPUTot'] for n in nodes) if nodes and all(n['CPUTot'] is not None for n in nodes) else None,
      'physical_cores':sum(n['physical_cores'] for n in nodes) if nodes and all(n['physical_cores'] is not None for n in nodes) else None,
      'quota':quota,'budget_bytes':min(2_000_000_000_000,quota['remaining_bytes']) if quota and quota['remaining_bytes'] is not None else None,
      'allocation_note':'Snapshot records capacity, not a reservation. AllocMem=0 does not establish free declared memory. Main coordinator must recheck all users commitments before submission.',
      'cpu_note':'696 is the current expected Slurm CPU total; SMT on compute-0-17 must be calibrated by measured parallel throughput.'}


def summarize_tasks(calls, tasks, strata):
    grouped=defaultdict(list)
    for call in calls:
        grouped[(call['task'],call['size_stratum'])].append(call)
        grouped[(call['task'],'ALL_PANEL')].append(call)
    output=[]
    for task in tasks:
        for stratum in [*strata,'ALL_PANEL']:
            group=grouped.get((task,stratum),[])
            launched=[row for row in group if row['launched']]
            statuses=Counter(row['status'] for row in group)
            success=sum(row['status']=='SUCCESS' for row in launched)
            unfinished=sum(row['status'] in UNFINISHED for row in group)
            timed_out=sum(row['status']=='TIMEOUT' for row in launched)
            failures=sum(row['status']!='SUCCESS' and row['status'] not in UNFINISHED for row in launched)
            times=[row['elapsed_seconds'] for row in launched]
            elapsed=distribution(times)
            if launched and timed_out/len(launched)>=.1:
                elapsed['p90_uncensored_identified']=False
                elapsed['p90_censoring_note']='At least 10% calculation timeouts; observed p90 is censored, not the uncensored completion time.'
            else:
                elapsed['p90_uncensored_identified']=bool(launched)
            x=[float(row['natoms']) for row in launched if number(row.get('natoms')) and number(row.get('elapsed_seconds'))]
            y=[float(row['elapsed_seconds']) for row in launched if number(row.get('natoms')) and number(row.get('elapsed_seconds'))]
            corr=None
            if len(x)>1 and max(x)!=min(x) and max(y)!=min(y):
                import numpy as np
                corr=float(np.corrcoef(x,y)[0,1])
            failures_by_reason=Counter(row.get('failure_code') or row['status'] for row in launched if row['status']!='SUCCESS')
            classified=Counter(code for row in group for code in row['qc_codes'] if code in
              {'POLAR_FRAGILE','ESP_D_ORBITAL_UNSUPPORTED','ESP_SURFACE_FAILED','XTB_SCC_FAILED'})
            properties=Counter(key for row in group for key in row['available_properties'])
            bands=defaultdict(list)
            for row in launched:
                if number(row.get('natoms')): bands[int(row['natoms'])//25*25].append(row)
            atom_bands=[{'natoms_min':band,'natoms_max':band+24,'calls':len(values),
                'elapsed_seconds':distribution(row['elapsed_seconds'] for row in values),
                'service_seconds_including_getter':distribution(service_seconds(row) for row in values)}
                for band,values in sorted(bands.items())]
            output.append({'task':task,'size_stratum':stratum,'outcomes':len(group),'launched':len(launched),
              'successes':success,'success_rate_launched':ratio(success,len(launched)),
              'failures':failures,'failure_rate_launched':ratio(failures,len(launched)),
              'timeouts':timed_out,'timeout_rate_launched':ratio(timed_out,len(launched)),
              'unfinished_outcomes':unfinished,'Q03_skipped':sum('Q03' in row['status'] and row['task']!='pm7_B' for row in group),
              'confirmed_SCF_failure_count':sum(row['confirmed_scf_failure'] for row in launched),
              'confirmed_SCF_failure_rate_launched':ratio(sum(row['confirmed_scf_failure'] for row in launched),len(launched)),
              'statuses':dict(statuses),'failure_reasons':dict(failures_by_reason),
              'native_method_failure_classifications':dict(classified),
              'classification_policy':'Verified native-v4 QC codes distinguish POLAR fragile, ESP d-basis refusal, ESP surface generation and xTB SCC failure. Older outcomes keep their original failure codes; SCC text is recognized independently.',
              'elapsed_seconds':elapsed,'qm_child_cpu_seconds':distribution(row.get('qm_child_cpu_seconds') for row in launched),
              'natoms':distribution(row.get('natoms') for row in launched),'atoms_elapsed_Pearson_r':corr,
              'empirical_25_atom_bands':atom_bands,
              'raw_total_bytes':distribution(row.get('raw_total_bytes') for row in launched),
              'aux_bytes':distribution(row.get('aux_bytes') for row in launched),
              'per_call_compressed_bytes':distribution(row.get('archive_per_call_bytes') for row in launched),
              'properties_available_cases':dict(properties),
              'null_property_counts':dict(Counter(key for row in group for key in row['null_properties'])),
              'empty_property_counts':dict(Counter(key for row in group for key in row['empty_properties'])),
              'observed_zero_scalar_counts':dict(Counter(key for row in group for key in row['observed_zero_scalars'])),
              'legitimate_empty_sparse_property_counts':dict(Counter(key for row in group for key in row['legitimate_empty_sparse_properties'])),
              'property_state_policy':'A non-null empty container is separate from null/uncomputed; numeric zero is observed. Parser-emitted empty placeholders alone do not prove a valid calculated sparse result. Native runner failure codes remain unchanged.',
              'missing_property_counts':dict(Counter(key for row in group for key in row['missing_properties'])),
              'length_issue_counts':dict(Counter(key for row in group for key in row['length_issues']))})
    return output


def observations(calls):
    task_groups=defaultdict(list)
    for call in calls: task_groups[call['task']].append(call)
    base=task_groups['pm7_B']
    mulliken=[row['mulliken_qc'] for row in base if row.get('mulliken_qc')]
    polar=[row.get('polar_asymmetry_bohr3') for row in base]
    hf=[row.get('Q02_delta_HOF_kcal_mol') for row in base]
    hess=task_groups['xtb_hessian']; valid_hess=[row for row in hess if row.get('frequency_observation_valid')]; force=task_groups['xtb_perturbed_gradient']
    derived=[row.get('derived_pm7',{}) for row in base]
    result={
      'Q01_gradient_norm_kcal_mol_A':distribution(row.get('Q01_gradient_norm_kcal_mol_A') for row in base),
      'Q02_HOF_difference_kcal_mol':distribution(hf),
      'Q02_absolute_HOF_difference_kcal_mol':distribution(abs(x) for x in hf if number(x)),
      'Q03_record_codes':dict(Counter(code for row in base for code in row['qc_codes'] if code=='Q03')),
      'pm7_B_base_success':{'assessed':sum(row.get('B_base_success') is not None for row in base),
        'successes':sum(row.get('B_base_success') is True for row in base)},
      'pm7_vertical_IP_eV':distribution(row.get('vertical_IP_eV') for row in derived),
      'pm7_vertical_EA_eV':positive_count([row.get('vertical_EA_eV') for row in derived],lambda x:x<0),
      'xtb_vertical_IP_eV':distribution(row.get('IP_eV') for row in task_groups['xtb_vipea']),
      'xtb_vertical_EA_eV':positive_count([row.get('EA_eV') for row in task_groups['xtb_vipea']],lambda x:x<0),
      'negative_EA_interpretation':'Negative vertical EA is an observed physical result, not automatically an SCF failure or exclusion.',
      'POLAR_asymmetry_bohr3':positive_count(polar,lambda x:x>.01),
      'POLAR_tensor_note':'All nine native-frame components retained. Above 0.01 bohr^3 is reported QC; no forced symmetrization.',
      'mulliken_per_case_QC':{'assessed':len(mulliken),'status_counts':dict(Counter(x.get('status','UNKNOWN') for x in mulliken)),
        'codes':dict(Counter(code for row in mulliken for code in row.get('codes',[]))),
        'reconstructed_charge_max_error_e':distribution(row.get('reconstructed_charge_max_error_e') for row in mulliken),
        'negative_overlap_eigenvalue_count':distribution(row.get('negative_overlap_eigenvalues') for row in mulliken),
        'absolute_condition_number':distribution(row.get('overlap_absolute_condition_number') for row in mulliken),
        'getter_elapsed_seconds':distribution(row.get('elapsed_seconds') for row in mulliken),
        'cases':[{'record_id':row['record_id'],**{key:(row.get('mulliken_qc') or {}).get(key) for key in
          ('status','codes','reconstructed_charge_max_error_e','charge_tolerance_e','negative_overlap_eigenvalues','overlap_absolute_condition_number')}}
          for row in base],
        'scope':'Per-case charge consistency checks the official reconstruction. Independent atom-pair truth is not available.'},
      'ESP':{'cases':len(task_groups['pm7_ESP']),'successes':sum(x['status']=='SUCCESS' for x in task_groups['pm7_ESP']),
        'charge_sum_e':distribution(row.get('esp_charge_sum_e') for row in task_groups['pm7_ESP'])},
      'ions':{},
      'solvation':{task:distribution(row.get('Gsolv_Eh') for row in task_groups[task])
                   for task in ('xtb_ALPB_water','xtb_ALPB_octanol')},
      'PM7_COSMO':{task:{field:distribution(row.get(field) for row in task_groups[task])
                      for field in ('dielectric_energy_eV','cosmo_area_A2','cosmo_volume_A3')}
                      for task in ('pm7_water','pm7_octanol')},
      'PM7_water_HOF_difference_kcal_mol':distribution(row.get('pm7_water_HOF_difference_kcal_mol') for row in derived),
      'PM7_octanol_HOF_difference_kcal_mol':distribution(row.get('pm7_octanol_HOF_difference_kcal_mol') for row in derived),
      'FOD_NFOD_e':distribution(row.get('NFOD_e') for row in task_groups['xtb_fod']),
      'xTB_neutral_charge_sum_e':distribution(row.get('charge_sum_e') for row in task_groups['xtb_singlepoint']),
      'xTB_quadrupole_trace_au':distribution(row.get('quadrupole_trace_au') for row in task_groups['xtb_singlepoint']),
      'xTB_HOMO_eV':distribution(row.get('homo_eV') for row in task_groups['xtb_singlepoint']),
      'xTB_LUMO_eV':distribution(row.get('lumo_eV') for row in task_groups['xtb_singlepoint']),
      'xTB_Fukui_column_sums':{str(k):distribution(row['fukui_column_sums'][k] for row in task_groups['xtb_vfukui']
          if len(row.get('fukui_column_sums',[]))==3) for k in range(3)},
      'perturbation':{'configured_sigma_A':distribution(row.get('configured_perturb_sigma_A') for row in force),
        'seed_reconstructed_noise_components_A':distribution(x for row in force for x in row.get('seed_reconstructed_noise_components_A',[])),
        'noise_note':'Noise is regenerated from recorded seed and configured sigma by the frozen runner algorithm. Original LMDB coordinates are not read by this report; coordinate subtraction is not claimed.',
        'atomic_force_norm_eV_A':distribution(x for row in force for x in row.get('atomic_force_norm_eV_A',[])),
        'force_component_eV_A':distribution(x for row in force for x in row.get('force_component_eV_A',[]))},
      'hessian':{'cases':len(hess),'launched':sum(row['launched'] for row in hess),
        'successful':sum(row['status']=='SUCCESS' for row in hess),
        'valid_complete_frequency_observations':len(valid_hess),
        'negative_frequency_count_raw':positive_count([row.get('negative_frequency_count_raw') for row in valid_hess],lambda x:x>0),
        'imaginary_frequency_count_below_minus20':positive_count([row.get('imaginary_frequency_count_below_minus20') for row in valid_hess],lambda x:x>0),
        'frequency_count':distribution(row.get('frequency_count') for row in hess),
        'ZPE_Eh':distribution(row.get('ZPE_Eh') for row in hess),'enthalpy_Eh':distribution(row.get('enthalpy_Eh') for row in hess),
        'thermo_supported_cases':sum(row['thermo_supported'] for row in hess),
        'thermo_missing_cases':sum(not row['thermo_supported'] for row in hess),
        'warnings':dict(Counter(warning for row in hess for warning in row['hessian_warnings'])),
        'thermo_policy':'No optimization is performed. Report native PM7-geometry imaginary modes and unsupported/absent thermochemistry; do not silently repair the geometry.'},
      'xyz_roundtrip_max_error_A':distribution(row.get('xyz_roundtrip_max_error_A') for row in calls),
      'scratch_cleanup_failures':[{'record_id':row['record_id'],'task':row['task'],'reason':row['scratch_cleanup_error'],
                                  'path':row['preserved_scratch']} for row in calls if row.get('scratch_cleanup_error')],
    }
    for task, expected_charge in [('pm7_cation',1),('pm7_anion',-1)]:
        group=task_groups[task]
        result['ions'][task]={'cases':len(group),'launched':sum(row['launched'] for row in group),
          'successes':sum(row['status']=='SUCCESS' for row in group),
          'confirmed_SCF_failure_count':sum(row['confirmed_scf_failure'] for row in group),
          'spin_Sz':distribution(row.get('spin_Sz') for row in group),'spin_S2':distribution(row.get('spin_S2') for row in group),
          'charge_sum_error_e':distribution(row['charge_sum_e']-expected_charge for row in group if number(row.get('charge_sum_e')))}
    return result


def accounting(paths, job_ids):
    jobs={}; missing=[]
    for path in paths:
        if not Path(path).is_file(): continue
        raw=read_json(path)
        for job,entry in raw.get('jobs',{}).items():
            if str(job) not in job_ids: continue
            if entry.get('sacct_exit_code')!=0: continue
            lines=entry.get('sacct_stdout','').splitlines()
            if not lines: continue
            names=lines[0].split('|')
            for line in lines[1:]:
                row=dict(zip(names,line.split('|')))
                if row.get('JobID')!=str(job): continue
                try: cpus,elapsed=int(row['AllocCPUS']),int(row['ElapsedRaw'])
                except (KeyError,ValueError): continue
                value={'job_id':str(job),'state':row.get('State'),'exit_code':row.get('ExitCode'),
                  'AllocCPUS':cpus,'ElapsedRaw':elapsed,'allocated_core_hours':cpus*elapsed/3600,
                  'source':str(path),'source_sha256':sha(path)}
                jobs[str(job)]=value
    missing=sorted(job_ids-set(jobs))
    return {'jobs':list(jobs.values()),'missing_job_ids':missing,
      'allocated_core_hours':sum(row['allocated_core_hours'] for row in jobs.values()) if jobs else None,
      'accounting_complete':not missing,'method':'Only exact parent JobID rows; batch and extern are not added again.'}


def service_seconds(call):
    elapsed=call.get('elapsed_seconds')
    if not number(elapsed): return None
    getter=(call.get('mulliken_qc') or {}).get('elapsed_seconds')
    return float(elapsed)+(float(getter) if number(getter) else 0.0)


def paired_polar(probe_calls, strata):
    output={}
    for stratum in strata:
        pairs=[call['paired_cost'] for call in probe_calls if call.get('size_stratum')==stratum and call.get('paired_cost')]
        ratios=[]; raw_ratios=[]
        for pair in pairs:
            with_qm=pair.get('B_with_POLAR_elapsed_seconds'); without_qm=pair.get('B_without_POLAR_elapsed_seconds')
            with_get=pair.get('B_with_POLAR_getter_seconds'); without_get=pair.get('B_without_POLAR_getter_seconds')
            if number(with_qm) and with_qm>0 and number(without_qm):
                with_service=with_qm+(with_get if number(with_get) else 0)
                without_service=without_qm+(without_get if number(without_get) else 0)
                ratios.append(without_service/with_service)
            raw_with=pair.get('B_with_POLAR_raw_bytes'); raw_without=pair.get('B_without_POLAR_raw_bytes')
            if number(raw_with) and raw_with>0 and number(raw_without): raw_ratios.append(raw_without/raw_with)
        output[stratum]={'paired_cases':len(pairs),
          'service_without_to_with_ratio':distribution(ratios),
          'raw_bytes_without_to_with_ratio':distribution(raw_ratios),
          'signed_POLAR_increment_elapsed_seconds':distribution(pair.get('POLAR_increment_elapsed_seconds') for pair in pairs),
          'signed_POLAR_increment_QM_CPU_seconds':distribution(pair.get('POLAR_increment_QM_CPU_seconds') for pair in pairs),
          'HOF_with_minus_without_kcal_mol':distribution(pair.get('HOF_with_minus_without_POLAR_kcal_mol') for pair in pairs),
          'note':'At most five measured minimum conformers per stratum. Signed increments are retained; negative noisy differences are not clipped.'}
    return output


def projections(panel, calls, manifest, task_names, task_stats, cap, acct, population_complete, polar_probe, storage_calibration):
    strata={row['size_stratum']:row for row in manifest['strata']}
    slots={(call['record_id'],call['task']):call for call in calls}
    low=[row for row in panel if row.get('molecule_lowest_energy_conformer') is True]
    all_mols={row['molecule_id'] for row in panel}
    known_mols={row['molecule_id'] for row in low}
    unknown_minima=sorted(all_mols-known_mols)
    stat_map={(row['task'],row['size_stratum']):row for row in task_stats}
    native_jobs={str(call['job_id']) for call in calls if call.get('job_id') is not None}
    observed_service=sum(service_seconds(call) or 0.0 for call in calls if call['launched'])
    allocated_seconds=sum(job['allocated_core_hours']*3600 for job in acct['jobs'])
    overhead_factor=max(1.0,allocated_seconds/observed_service) if observed_service>0 and acct['accounting_complete'] else None
    definitions=[('A_all_CD_all_xtb','all','all',False),('B_min_CD_all_xtb_B_contains_POLAR','minimum','all',False),
                 ('C_all_CD_min_xtb','all','minimum',False),('D_min_CD_min_xtb_B_contains_POLAR','minimum','minimum',False)]
    if all(polar_probe.get(key,{}).get('service_without_to_with_ratio',{}).get('n',0)>0 for key in strata):
        definitions += [('B_strict_min_CD_POLAR_all_xtb','minimum','all',True),
                        ('D_strict_min_CD_POLAR_min_xtb','minimum','minimum',True)]
    scenarios=[]
    for label,cd_scope,xtb_scope,strict in definitions:
        components=[]; required_missing=[]
        for task in task_names:
            scope='minimum' if task in CD_TASKS and cd_scope=='minimum' or task.startswith('xtb_') and xtb_scope=='minimum' else 'all'
            for key,weight in strata.items():
                selected=[row for row in (low if scope=='minimum' else panel) if row['size_stratum']==key]
                expected_count=len(selected); missing=[]; service=0.0; qm=0.0; raw=0.0; archive=0.0; json_bytes=0
                missing_metrics=Counter(); launched=0
                for source in selected:
                    call=slots.get((source['record_id'],task))
                    if call is None or call['status'] in UNFINISHED:
                        missing.append(source['record_id']); continue
                    launched += call['launched']
                    json_bytes += call['details_json_bytes']
                    value=service_seconds(call)
                    if value is None: missing_metrics['service_seconds']+=1
                    else: service += value
                    for field,total_name in [('qm_child_cpu_seconds','QM_CPU_seconds'),('raw_total_bytes','raw_bytes'),
                                              ('archive_per_call_bytes','archive_bytes')]:
                        value=call.get(field)
                        if number(value):
                            if total_name=='QM_CPU_seconds': qm+=value
                            elif total_name=='raw_bytes': raw+=value
                            else: archive+=value
                        elif call['launched']: missing_metrics[total_name]+=1
                    # An explicitly skipped Q03 follower incurred no QM runtime;
                    # absent output metrics for that known skip are a measured zero.
                population_weight=weight['molecule_population_weight'] if scope=='minimum' else weight['record_population_weight']
                known_minimum=scope!='minimum' or not unknown_minima
                measured=not missing and not missing_metrics['service_seconds'] and known_minimum and expected_count>0
                if not measured:
                    required_missing.append({'task':task,'size_stratum':key,'missing_slots':len(missing),
                      'sample_ids':missing[:5],'missing_metrics':dict(missing_metrics),
                      'unknown_minimum_molecules':len(unknown_minima) if scope=='minimum' else 0})
                component={'task':task,'size_stratum':key,'scope':scope,'sample_calls':expected_count,
                  'launched_calls':launched,'population_calls':weight['population_molecules'] if scope=='minimum' else weight['population_records'],
                  'population_weight':population_weight,'complete':measured,
                  'estimated_service_seconds':service*population_weight if measured else None,
                  'estimated_QM_CPU_seconds':qm*population_weight if measured and not missing_metrics['QM_CPU_seconds'] else None,
                  'estimated_raw_bytes':raw*population_weight if measured and not missing_metrics['raw_bytes'] else None,
                  'estimated_archive_bytes':archive*population_weight*storage_calibration.get(key,{}).get('archive_pack_factor',1) if measured and not missing_metrics['archive_bytes'] else None,
                  'estimated_parquet_bytes':json_bytes*population_weight*storage_calibration[key]['parquet_to_details_json_ratio']
                    if measured and storage_calibration.get(key,{}).get('parquet_to_details_json_ratio') is not None else None}
                if strict and task=='pm7_B' and measured:
                    scale=polar_probe[key]['service_without_to_with_ratio']['mean']
                    all_seconds=sum(service_seconds(slots[(source['record_id'],task)]) or 0 for source in selected)
                    minimum_seconds=sum(service_seconds(slots[(source['record_id'],task)]) or 0 for source in low if source['size_stratum']==key)
                    component['estimated_service_seconds']=all_seconds*weight['record_population_weight']*scale + minimum_seconds*weight['molecule_population_weight']*(1-scale)
                    component['strict_POLAR_model']='B-without-POLAR on every record plus signed paired incremental POLAR service on molecular minima.'
                    # Raw/compressed variants have different output. The probe's
                    # uncompressed ratio cannot prove a compressed archive ratio.
                    component['estimated_QM_CPU_seconds']=None
                    component['estimated_raw_bytes']=None
                    component['estimated_archive_bytes']=None
                    component['estimated_parquet_bytes']=None
                components.append(component)
        full=population_complete and not required_missing
        totals={}
        for field in ('estimated_service_seconds','estimated_QM_CPU_seconds','estimated_raw_bytes','estimated_archive_bytes','estimated_parquet_bytes'):
            totals[field]=sum(row[field] for row in components) if full and all(row[field] is not None for row in components) else None
        core_hours=totals['estimated_service_seconds']/3600 if totals['estimated_service_seconds'] is not None else None
        calibrated=core_hours*overhead_factor if core_hours is not None and overhead_factor is not None else None
        cpus=cap.get('scheduled_cpus')
        scenarios.append({'name':label,'PM7_CD_scope':cd_scope,'xTB_nonhessian_scope':xtb_scope,
          'neutral_B_POLAR_scope':'minimum, paired modeled' if strict else 'all; still merged in B',
          'complete':full,'known_measured_components':components,'missing_components':required_missing,
          'estimated_single_worker_service_core_hours':core_hours,
          'estimated_QM_core_hours':totals['estimated_QM_CPU_seconds']/3600 if totals['estimated_QM_CPU_seconds'] is not None else None,
          'calibrated_allocated_core_hours':calibrated,
          'ideal_wall_hours_at_capacity':core_hours/cpus if core_hours is not None and cpus else None,
          'calibrated_wall_hours_at_capacity':calibrated/cpus if calibrated is not None and cpus else None,
          'estimated_uncompressed_call_output_bytes':totals['estimated_raw_bytes'],
          'estimated_archived_output_bytes_percall_model':totals['estimated_archive_bytes'],
          'estimated_Parquet_bytes_json_model':totals['estimated_parquet_bytes'],
          'hessian_included':False,
          'notes':['Core-hours for service include frozen QM walltime plus measured Mulliken getter. Parsing/read/archive overhead is separately calibrated from full pilot allocation.',
            'Calibration includes startup, tail imbalance and historical interruptions; capacity walltime is a planning estimate, not a queue reservation.']})
    hessian=[]
    for fraction in (.001,.01,.05,.1,1.0):
        complete=population_complete and not unknown_minima; seconds=0.0; archive_percall=0.0; archive=0.0; missing=[]
        for key,weight in strata.items():
            group=[row for row in low if row['size_stratum']==key]
            for row in group:
                call=slots.get((row['record_id'],'xtb_hessian'))
                if call is None or call['status'] in UNFINISHED or service_seconds(call) is None:
                    complete=False; missing.append(row['record_id']); continue
                seconds+=(service_seconds(call) or 0)*weight['molecule_population_weight']*fraction
                value=call.get('archive_per_call_bytes')
                if number(value):
                    raw_estimate=value*weight['molecule_population_weight']*fraction
                    archive_percall+=raw_estimate
                    archive+=raw_estimate*storage_calibration.get(key,{}).get('archive_pack_factor',1)
                elif call['launched']: complete=False
        hessian.append({'molecular_subset_fraction':fraction,
          'estimated_molecules':sum(row['population_molecules'] for row in strata.values())*fraction,
          'complete':complete,'service_core_hours':seconds/3600 if complete else None,
          'ideal_wall_hours_at_capacity':seconds/3600/cap['scheduled_cpus'] if complete and cap.get('scheduled_cpus') else None,
          'archive_bytes':archive if complete else None,'missing_measured_minima':len(missing),
          'archive_bytes_percall_compression_model':archive_percall if complete else None,
          'archive_calibration':'Same per-stratum closed-archive/per-call pack factor as the non-hessian scenarios; per-call estimate retained separately.',
          'policy':'Subset fraction is a decision input. Imaginary modes stay observed; supported thermochemistry is not imputed.'})
    packing=[]
    for scenario in scenarios:
        for key,weight in strata.items():
            population_average=weight['population_records']/weight['population_molecules']
            per_record=0.0; per_molecule=0.0; missing=[]; censored=[]
            for task in task_names:
                stat=stat_map.get((task,key),{})
                estimate=stat.get('elapsed_seconds',{}).get('p90')
                if estimate is None: missing.append(task); continue
                if not stat.get('elapsed_seconds',{}).get('p90_uncensored_identified'): censored.append(task)
                if task=='pm7_B':
                    getter=distribution((row.get('mulliken_qc') or {}).get('elapsed_seconds') for row in calls if row['task']==task and row['size_stratum']==key)
                    estimate+=getter['p90'] if getter['p90'] is not None else 0.0
                    if scenario['neutral_B_POLAR_scope']=='minimum, paired modeled':
                        scale=polar_probe[key]['service_without_to_with_ratio']['mean']
                        per_molecule+=estimate*(1-scale)
                        estimate*=scale
                minimum=task in CD_TASKS and scenario['PM7_CD_scope']=='minimum' or task.startswith('xtb_') and scenario['xTB_nonhessian_scope']=='minimum'
                if minimum: per_molecule+=estimate
                else: per_record+=estimate
            cost=per_record*population_average+per_molecule
            for node in cap.get('nodes',[]):
                cpu_ceiling=node.get('CPUEfctv') or node.get('CPUTot')
                k=node.get('suggested_k_from_measured_memory') if node.get('k_memory_cpu_evidence_available') else cpu_ceiling
                ideal_molecules=math.floor(k*20*3600/cost) if k and cost>0 and not missing and not censored else None
                calibrated_cost=cost*overhead_factor if cost>0 and not missing and overhead_factor is not None else None
                molecules=math.floor(k*20*3600/calibrated_cost) if k and calibrated_cost and not censored else None
                packing.append({'scenario':scenario['name'],'size_stratum':key,'node':node['node'],
                  'k_CPU_ceiling':cpu_ceiling,'k_proposed_with_available_memory_evidence':k,
                  'per_worker_memory_budget_MiB_at_85pct_node':node['RealMemory_MiB']*.85/k if k and node.get('RealMemory_MiB') else None,
                  'predicted_p90_service_seconds_per_average_molecule':cost if not missing else None,
                  'ideal_molecules_per_20h_task_CPU_only':ideal_molecules,
                  'ideal_approximate_records_per_20h_task_CPU_only':math.floor(ideal_molecules*population_average) if ideal_molecules is not None else None,
                  'allocated_service_overhead_factor':overhead_factor,
                  'calibrated_p90_service_seconds_per_average_molecule':calibrated_cost,
                  'recommended_molecules_per_20h_task':molecules,
                  'recommended_approximate_records_per_20h_task':math.floor(molecules*population_average) if molecules is not None else None,
                  'capacity_policy':'Actual 20h suggestion applies the measured allocated/service overhead factor. Without complete accounting, only an explicitly ideal CPU-only capacity is provided.',
                  'missing_task_timings':missing,'censored_p90_tasks':censored,
                  'memory_validation':'k is a CPU ceiling pending measured peak RSS and all-user memory commitments. Whole molecules must be packed by their individual cost; these averages are planning examples.'})
    return {'scenarios':scenarios,'hessian_subsets':hessian,'task_packing_20h':packing,
      'strict_minimum_POLAR_available':any(row[3] for row in definitions),
      'POLAR_paired_probe_by_stratum':polar_probe,
      'pilot_allocated_to_observed_service_factor':overhead_factor,
      'unknown_original_minimum_energy_molecules':unknown_minima,
      'estimation_policy':'Formal manifest record weights for all-conformer tasks and molecule weights for minimum-only tasks; full totals withheld when required measurement or final population is missing.'}


def storage_summary(items, calls, strata, cap):
    unique_archives={}; unique_parquets={}; per_stratum=defaultdict(lambda:{'archive_bytes':0,'parquet_bytes':0,'molecules':0})
    record_strata={row['molecule_id']:row['size_stratum'] for row in calls}
    for item in items:
        receipt=item['receipt']; key=record_strata.get(receipt.get('molecule_id'))
        if not item.get('parquet'): continue
        path=item['parquet']['path']
        unique_parquets[path]=item['parquet']
        if key:
            per_stratum[key]['parquet_bytes']+=item['parquet']['bytes']
            per_stratum[key]['molecules']+=1
        ref=item.get('archive')
        if ref:
            unique_archives[ref['path']]=ref
            if key: per_stratum[key]['archive_bytes']+=ref['bytes']
    calibration={}
    for key in strata:
        selected=[row for row in calls if row['size_stratum']==key]
        percall=sum(row['archive_per_call_bytes'] for row in selected if number(row.get('archive_per_call_bytes')))
        details=sum(row['details_json_bytes'] for row in selected)
        calibration[key]={**per_stratum[key],
          'archive_pack_factor':per_stratum[key]['archive_bytes']/percall if percall else 1.0,
          'parquet_to_details_json_ratio':per_stratum[key]['parquet_bytes']/details if details else None,
          'percall_archive_bytes':percall,'details_json_bytes':details}
    archived_aux=[item for call in calls for item in call['archived_files'] if item.get('name','').endswith('.aux')]
    aux_calls=[call for call in calls if call.get('aux_archived') is True]
    return {'unique_closed_archive_bytes':sum(ref['bytes'] for ref in unique_archives.values()),
      'unique_closed_archive_files':len(unique_archives),
      'unique_closed_Parquet_bytes':sum(ref['bytes'] for ref in unique_parquets.values()),
      'unique_closed_Parquet_files':len(unique_parquets),
      'archive_references':list(unique_archives.values()),'Parquet_references':list(unique_parquets.values()),
      'aux_generated_bytes':sum(call['aux_bytes'] for call in calls if number(call.get('aux_bytes'))),
      'aux_archived_call_count':len(aux_calls),'aux_archived_raw_bytes':sum(item.get('bytes',0) for item in archived_aux),
      'raw_total_bytes_all_measured_calls':sum(call['raw_total_bytes'] for call in calls if number(call.get('raw_total_bytes'))),
      'scratch_cleanup_bytes_measured':sum(call['scratch_bytes_removed'] for call in calls if number(call.get('scratch_bytes_removed'))),
      'scratch_cleanup_byte_measurements':sum(number(call.get('scratch_bytes_removed')) for call in calls),
      'per_stratum_calibration':calibration,
      'decimal_budget_bytes':{'lmdb_1_ceiling':600_000_000_000,'Parquet_ceiling':200_000_000_000,
        'raw_archive_ceiling':800_000_000_000,'scratch_and_margin_reservation':400_000_000_000},
      'account_remaining_bytes':(cap.get('quota') or {}).get('remaining_bytes'),
      'actual_forward_budget_bytes':cap.get('budget_bytes'),
      'measurement_notes':['Archive totals use unique receipt archive paths; repeated shared archive references in per-call rows are not added repeatedly.',
        'Scenario archive estimates calibrate weighted per-call compressed bytes against closed packed archive bytes, including historical interrupted logs.',
        'Scenario Parquet estimates calibrate weighted task JSON bytes by the observed per-stratum Parquet/details ratio; final task granularity and chosen field layout can alter compression.',
        'lmdb_1 volume and scratch peak are design ceilings/reservations, not measurements. Peak RSS and concurrent scratch peak are not inferred from sums of removed bytes.']}


def markdown(report):
    def fmt(value, digits=3):
        if value is None: return '待测'
        if isinstance(value,int): return f'{value:,}'
        if not number(value): return str(value)
        return f'{value:,.{digits}f}'
    def percent(value): return fmt(value*100,2)+'%' if value is not None else '待测'
    def scientific(value): return f'{value:.3e}' if number(value) else '待测'
    coverage=report['coverage']; obs=report['observations']; cap=report['capacity']; storage=report['storage']
    lines=['# WP4 试跑：决策数字','',
      f"状态：**{report['status']}**；人口：{report['population_scope']}。",'',
      f"已读取 {fmt(coverage['measured_records'])} 条原始记录、{fmt(coverage['completed_molecules'])} 个闭合分子；面板共 {fmt(coverage['panel_records'])} 条、{fmt(coverage['panel_molecules'])} 个分子。缺失任务槽 {fmt(coverage['missing_slots'])} 个。",'',
      '| 指标 | 实测 |','| --- | --- |',
      f"| Native pilot 记账核时 | {fmt(report['accounting']['allocated_core_hours'])} core h |",
      f"| PM7 Q01 梯度范数 p50 / p90 | {fmt(obs['Q01_gradient_norm_kcal_mol_A']['p50'])} / {fmt(obs['Q01_gradient_norm_kcal_mol_A']['p90'])} kcal/mol/Å |",
      f"| PM7 \|Q02 ΔHf 差\| p50 / p90 | {scientific(obs['Q02_absolute_HOF_difference_kcal_mol']['p50'])} / {scientific(obs['Q02_absolute_HOF_difference_kcal_mol']['p90'])} kcal/mol |",
      f"| POLAR 反对称分量 >0.01 bohr³ | {fmt(obs['POLAR_asymmetry_bohr3']['count'])}/{fmt(obs['POLAR_asymmetry_bohr3']['n'])} |",
      f"| xTB hess 存在 <-20 cm⁻¹ 虚频 | {fmt(obs['hessian']['imaginary_frequency_count_below_minus20']['count'])}/{fmt(obs['hessian']['imaginary_frequency_count_below_minus20']['n'])} |",
      f"| 已闭合归档 / Parquet | {fmt(storage['unique_closed_archive_bytes']/1e9)} / {fmt(storage['unique_closed_Parquet_bytes']/1e9)} GB |",
      f"| WP5 六节点调度 CPU / 物理核 | {fmt(cap.get('scheduled_cpus'))} / {fmt(cap.get('physical_cores'))} |",
      f"| 账户剩余 / 本轮可用预算 | {fmt(storage['account_remaining_bytes']/1e12) if storage['account_remaining_bytes'] is not None else '待测'} / {fmt(storage['actual_forward_budget_bytes']/1e12) if storage['actual_forward_budget_bytes'] is not None else '待测'} TB (decimal，1 TB=10¹² bytes) |",'']
    projection=report['projections']
    if projection.get('disabled'):
        lines += ['**本报告仅供集成检查，关闭所有全量核时、墙钟和存储外推；正式 WP4 面板另行完成。**','']
    else:
        lines += ['| 方案（hess 另计） | 服务核时 | 校正后分配核时 | 六节点校正墙钟 h | 归档 / Parquet GB |',
          '| --- | --- | --- | --- | --- |']
        for row in projection['scenarios']:
            archived=row['estimated_archived_output_bytes_percall_model']; parquet=row['estimated_Parquet_bytes_json_model']
            lines.append(f"| {row['name']} | {fmt(row['estimated_single_worker_service_core_hours'])} | {fmt(row['calibrated_allocated_core_hours'])} | {fmt(row['calibrated_wall_hours_at_capacity'])} | {fmt(archived/1e9) if archived is not None else '待测'} / {fmt(parquet/1e9) if parquet is not None else '待测'} |")
        lines += ['', 'C/D 最低构象方案中的 B 仍含 POLAR，除非行名明确标出 paired 模型。xTB 最低构象方案另列，供覆盖范围决策。','',
          '| hess 分子子集比例 | 服务核时 | 归档 GB |','| --- | --- | --- |']
        for row in projection['hessian_subsets']:
            lines.append(f"| {percent(row['molecular_subset_fraction'])} | {fmt(row['service_core_hours'])} | {fmt(row['archive_bytes']/1e9) if row['archive_bytes'] is not None else '待测'} |")
        lines += ['','20 h 任务按逐分子的 p90 预测成本装包，所有保留构象共同分配。各节点 k 上限及样本容量见附录；最终 k 还需实测峰值 RSS 与提交时的全部用户内存承诺。','']
    lines += ['待决：C/D 与 xTB 的构象覆盖、hess 子集和虚频处理、原始输出是否保留 AUX、WP5 每任务核数与时限、lmdb_1 分文件边界。','',
      '## 附录：任务与失败','',
      '| 任务 | 已启动 | 成功率 | 超时率 | Q03 跳过 | 耗时 mean / p50 / p90 s |',
      '| --- | --- | --- | --- | --- | --- |']
    for row in report['task_statistics']:
        if row['size_stratum']!='ALL_PANEL': continue
        t=row['elapsed_seconds']
        lines.append(f"| {row['task']} | {fmt(row['launched'])} | {percent(row['success_rate_launched'])} | {percent(row['timeout_rate_launched'])} | {fmt(row['Q03_skipped'])} | {fmt(t['mean'])} / {fmt(t['p50'])} / {fmt(t['p90'])} |")
    lines += ['', '各任务、大小层的详细失败代码、性质缺失、原子数与耗时相关性，以及 timeout 删失说明见 wp4_pilot_report.json 的 task_statistics。',
      '', '## 附录：数值和方法','',
      f"Mulliken per-case QC：{json.dumps(obs['mulliken_per_case_QC']['status_counts'],ensure_ascii=False)}；charge 最大误差 {scientific(obs['mulliken_per_case_QC']['reconstructed_charge_max_error_e']['max'])} e。独立原子对真值未验证。",'',
      f"垂直 EA<0：PM7 {obs['pm7_vertical_EA_eV']['count']}/{obs['pm7_vertical_EA_eV']['n']}；xTB {obs['xtb_vertical_EA_eV']['count']}/{obs['xtb_vertical_EA_eV']['n']}。负 EA 按物理结果记录。",'',
      f"扰动坐标 σ 配置 p50 {fmt(obs['perturbation']['configured_sigma_A']['p50'])} Å；逐原子受力范数 p50/p90 {fmt(obs['perturbation']['atomic_force_norm_eV_A']['p50'])}/{fmt(obs['perturbation']['atomic_force_norm_eV_A']['p90'])} eV/Å。噪声数值分布由记录 seed 重建，报告未读取 LMDB 坐标。",'',
      f"hess 热化学 TOT 支持 {obs['hessian']['thermo_supported_cases']}/{obs['hessian']['cases']}；未进行结构优化，虚频不修饰。",'',
      '全部 SHA、软件版本、关键词配置、来源与面板绑定、容量 snapshot、缺失证据、完整观察统计和逐层外推均保存在同目录 wp4_pilot_report.json。原 LMDB 未打开或写入。']
    if report['issues']:
        lines += ['', '## 附录：尚缺证据','']+[f'- {value}' for value in report['issues']]
    return '\n'.join(lines)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panel-manifest',default=str(ROOT/'wp4_native_panel/pilot_panel_manifest.json'))
    parser.add_argument('--panel')
    parser.add_argument('--quality')
    parser.add_argument('--native-root',action='append',default=[])
    parser.add_argument('--b-probe-root',action='append',default=[])
    parser.add_argument('--capacity',default=str(ROOT/'reports/wp5_capacity_snapshot.json'))
    parser.add_argument('--accounting',action='append',default=[])
    parser.add_argument('--output',default=str(ROOT/'reports/wp4_pilot_report'))
    parser.add_argument('--workers',type=int,default=16)
    parser.add_argument('--integration-review',action='store_true',help='Review bounded native measurements; disable all full-corpus projections')
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.check:
        import ast
        ast.parse(Path(__file__).read_text())
        print(json.dumps({'status':'REPORT_SOURCE_SYNTAX_PASS','inputs_read':False,'LMDB_opened':False}))
        return 0
    allocation=int(os.environ.get('SLURM_CPUS_PER_TASK','0'))
    if not os.environ.get('SLURM_JOB_ID') or allocation<16 or not 16<=args.workers<=allocation:
        raise RuntimeError('Report data processing requires Slurm >=16 allocated CPUs and effective workers <= allocation')
    if not args.native_root: parser.error('At least one --native-root required; use closed formal bucket roots')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','BLIS_NUM_THREADS'):
        os.environ[name]='1'
    started=time.monotonic(); pq,np,duckdb=deps()
    manifest=read_json(args.panel_manifest)
    label=manifest.get('scope','')
    bounded=(manifest.get('is_formal_wp4_10000_record_panel') is False or 'BOUNDED' in label or 'SYNTHETIC' in label)
    if not args.integration_review and (bounded or manifest.get('target_records',0)<10000):
        raise ValueError('Formal cost reporting requires the actual 10000-record whole-molecule panel. Use --integration-review for bounded numeric review with no extrapolation.')
    if manifest.get('status')!='READY_FOR_NATIVE_WP4':
        raise ValueError('Panel selection has not completed')
    if not manifest.get('all_retained_conformers_of_each_selected_molecule'):
        raise ValueError('Manifest does not establish whole retained molecules')
    panel_path=Path(args.panel or manifest['output'])
    panel_sha=sha(panel_path); manifest_sha=sha(args.panel_manifest)
    if manifest.get('panel_sha256') and manifest['panel_sha256']!=panel_sha:
        raise ValueError('Panel differs from the selector manifest SHA')
    columns=['record_id','molecule_id','record_payload_sha256','retained','size_stratum',
             'retained_conformer_count','molecule_lowest_energy_conformer','total_atoms','heavy_atoms']
    panel=pq.read_table(panel_path,columns=columns).to_pylist()
    if len(panel)!=manifest['actual_records'] or any(row['retained'] is not True for row in panel):
        raise ValueError('Panel count/retention disagrees with manifest')
    panel_by_id={row['record_id']:row for row in panel}
    if len(panel_by_id)!=len(panel): raise ValueError('Duplicate panel record identity')
    grouped=defaultdict(list)
    for row in panel: grouped[row['molecule_id']].append(row)
    if len(grouped)!=manifest['molecules']:
        raise ValueError('Panel molecule count disagrees with manifest')
    for key,group in grouped.items():
        if any(int(row['retained_conformer_count'])!=len(group) for row in group):
            raise ValueError('Incomplete retained molecule in panel: '+key)
    strata=sorted(row['size_stratum'] for row in manifest['strata'])
    roots=[Path(value).absolute() for value in args.native_root]
    issues=[]; metadata=[]; receipt_paths=[]; summary_jobs=set()
    for root in roots:
        if not root.is_dir():
            issues.append('Native root missing: '+str(root)); continue
        metadata_paths=([root/'metadata.json'] if (root/'metadata.json').is_file() else sorted(root.rglob('metadata.json')))
        if not metadata_paths: issues.append('Native metadata missing: '+str(root))
        for path in metadata_paths:
            raw=read_json(path)
            if 'SYNTHETIC' in raw.get('scope',''):
                raise ValueError('Synthetic capability results cannot be mixed into native population statistics')
            binding=raw.get('input_and_implementation_binding',{})
            if binding.get('panel_sha256')!=panel_sha:
                raise ValueError('Native output belongs to a different panel: '+str(path))
            if binding.get('panel_manifest_sha256') and binding['panel_manifest_sha256']!=manifest_sha:
                raise ValueError('Native output panel manifest SHA differs: '+str(path))
            snapshots=[]
            snapshot=path.parent/'source_snapshot'
            if snapshot.is_dir():
                for source in sorted(snapshot.iterdir()):
                    if source.is_file(): snapshots.append({'path':str(source),'bytes':source.stat().st_size,'sha256':sha(source)})
            metadata.append({'path':str(path),'sha256':sha(path),'data':raw,'source_snapshot':snapshots})
            for summary_path in path.parent.glob('job_*_summary.json'):
                summary=read_json(summary_path)
                if summary.get('job_id'): summary_jobs.add(str(summary['job_id']))
        receipt_paths.extend(sorted(root.rglob('receipt.json')))
    receipt_paths=list(dict.fromkeys(str(path) for path in receipt_paths))
    native=[]; worker_pids=set()
    with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
        for item in pool.map(read_receipt,receipt_paths,chunksize=1):
            if item.get('worker_pid'): worker_pids.add(item['worker_pid'])
            if item.get('issue'): issues.append(item['issue']+': '+item['receipt_path'])
            native.append(item)
    # Identical duplicate receipts can arise from archive-only migration; count
    # each molecular result once. Conflicting closed outcomes are not blended.
    molecules={}
    for item in native:
        if not item.get('parquet'): continue
        key=item['receipt']['molecule_id']
        if key in molecules:
            if molecules[key]['parquet']['sha256']!=item['parquet']['sha256']:
                raise ValueError('Conflicting closed molecule Parquet in supplied roots: '+key)
            continue
        molecules[key]=item
    closed=list(molecules.values()); calls=[row for item in closed for row in item['calls']]
    for call in calls:
        source=panel_by_id.get(call['record_id'])
        if source is None or source['molecule_id']!=call['molecule_id'] or source['record_payload_sha256']!=call['payload_sha256']:
            raise ValueError('Native measured record/source payload is not in the selected panel: '+str(call['record_id']))
        if source['size_stratum']!=call['size_stratum']:
            raise ValueError('Measured size stratum differs from panel')
    slots={(call['record_id'],call['task']):call for call in calls}
    if len(slots)!=len(calls): raise ValueError('Duplicate measured record/task slot')
    configs=[item['data'].get('config',{}) for item in metadata if item['data'].get('config')]
    if not configs:
        raise ValueError('Missing native job config; expected tasks cannot be inferred from successful outputs alone')
    config=configs[0]; tasks=[task['name'] for task in config['tasks']]; hess_name=config['hessian_task']['name']
    config_fingerprints={hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest() for value in configs}
    if len(config_fingerprints)>1: issues.append('Different native job configurations were supplied; full totals are withheld.')
    measured_jobs={str(row['job_id']) for row in calls if row.get('job_id') is not None}|summary_jobs
    accounting_paths=args.accounting or sorted(str(path) for path in (ROOT/'reports').glob('accounting_*.json'))
    acct=accounting(accounting_paths,measured_jobs); cap=capacity(args.capacity)
    resources=[]
    for root in roots:
        for path in sorted(root.rglob('job_*_resources.json')):
            resources.append({'path':str(path),'sha256':sha(path),'data':read_json(path)})
    process_rss=[item['data']['maximum_process_rss_kib']*1024 for item in resources
                 if number(item['data'].get('maximum_process_rss_kib'))]
    cgroup_per_cpu=[item['data']['own_cgroup_memory_peak_bytes']/item['data']['slurm_cpus'] for item in resources
      if number(item['data'].get('own_cgroup_memory_peak_bytes')) and number(item['data'].get('slurm_cpus')) and item['data']['slurm_cpus']>0]
    # A worker can coexist with a QM child. GNU time is a process maximum,
    # while an isolated cgroup is a measured concurrent job total. Keep both
    # scopes explicit and use the larger declared planning estimate.
    candidates=[]
    if process_rss: candidates.append(2*max(process_rss))
    if cgroup_per_cpu: candidates.append(1.25*max(cgroup_per_cpu))
    memory_per_worker=max(candidates) if candidates else None
    cap['pilot_resource_evidence']=resources
    cap['planning_peak_bytes_per_worker']=memory_per_worker
    cap['memory_planning_method']='Larger of 2*maximum GNU-time single-process RSS (worker plus child planning allowance) and 1.25*isolated concurrent cgroup peak/allocated CPUs. These are planning extrapolations, not measured RSS totals for a new larger job.'
    for node in cap.get('nodes',[]):
        cpu=node.get('CPUEfctv') or node.get('CPUTot')
        memory_k=math.floor(node['RealMemory_MiB']*1024*1024*.85/memory_per_worker) if memory_per_worker and node.get('RealMemory_MiB') else None
        node['suggested_k_from_measured_memory']=min(cpu,memory_k) if cpu and memory_k is not None and memory_k>=16 else None
        node['k_memory_cpu_evidence_available']=memory_k is not None
    if acct['missing_job_ids']: issues.append('Missing parent sacct accounting: '+', '.join(acct['missing_job_ids']))
    expected_panel=panel
    if args.integration_review:
        selected=set()
        for item in metadata:
            binding=item['data'].get('input_and_implementation_binding',{})
            count=int(binding.get('bucket_count',1)); bucket=int(binding.get('bucket',0))
            eligible=[mid for mid in grouped if int(hashlib.sha256(mid.encode()).hexdigest()[:16],16)%count==bucket]
            eligible.sort(key=lambda mid:hashlib.sha256((str(config['seed'])+'|'+mid).encode()).hexdigest())
            maximum=binding.get('max_molecules')
            if maximum is not None: eligible=eligible[:int(maximum)]
            selected.update(eligible)
        expected_panel=[row for row in panel if row['molecule_id'] in selected] if metadata else panel
    expected={(row['record_id'],task) for row in expected_panel for task in tasks}
    expected.update((row['record_id'],hess_name) for row in expected_panel if row['molecule_lowest_energy_conformer'])
    missing=sorted(expected-set(slots)); unfinished=sum(row['status'] in UNFINISHED for row in calls)
    coverage={'panel_records':len(panel),'panel_molecules':len(grouped),'native_slice_planned_records':len(expected_panel),
      'native_slice_planned_molecules':len({row['molecule_id'] for row in expected_panel}),
      'completed_molecules':len(closed),'measured_records':len({row['record_id'] for row in calls}),
      'expected_slots':len(expected),'measured_slots':len(calls),'missing_slots':len(missing),
      'missing_slot_examples':[{'record_id':record,'task':task} for record,task in missing[:50]],
      'unfinished_slots':unfinished,'all_expected_slots_closed':not missing and not unfinished,
      'measured_workers':len(worker_pids),'worker_pids':sorted(worker_pids)}
    task_stats=summarize_tasks(calls,[*tasks,hess_name],strata)
    obs=observations(calls); storage=storage_summary(closed,calls,strata,cap)
    quality_path=args.quality or (manifest.get('input') if isinstance(manifest.get('input'),str) else None)
    quality_population=None; population_complete=False
    if quality_path and not args.integration_review:
        db=duckdb.connect();db.execute(f'SET threads={args.workers}');db.execute("SET memory_limit='24GB'")
        db.execute(f'CREATE VIEW quality AS SELECT * FROM read_parquet({q(quality_path)})')
        description={row[0] for row in db.execute('DESCRIBE quality').fetchall()}
        condition=' AND '.join('NOT coalesce('+code+',false)' for code in ['X01','X02','X03','X04','X05'])
        missing_geometry=db.execute(f'SELECT count(*) FROM quality WHERE NOT coalesce(geometry_evaluated,false) AND {condition}').fetchone()[0]
        db.execute('''CREATE TABLE population_molecules AS SELECT molecule_id,count(*) AS conformers,max(heavy_atoms) AS heavy_atoms,
          count(*) FILTER(WHERE energy_raw IS NOT NULL AND isfinite(energy_raw))>0 AS known_minimum
          FROM quality WHERE retained GROUP BY molecule_id''')
        query='''SELECT CASE WHEN heavy_atoms<=10 THEN '0_10' WHEN heavy_atoms<=20 THEN '11_20'
          WHEN heavy_atoms<=30 THEN '21_30' WHEN heavy_atoms<=50 THEN '31_50'
          WHEN heavy_atoms<=75 THEN '51_75' WHEN heavy_atoms<=100 THEN '76_100' ELSE 'above_100' END AS size_stratum,
          count(*) AS molecules,sum(conformers) AS records,count(*) FILTER(WHERE NOT known_minimum) AS unknown_minimum_molecules
          FROM population_molecules GROUP BY size_stratum ORDER BY size_stratum'''
        counts=rowdicts(db,query);db.close()
        quality_population={'path':str(quality_path),'bytes':Path(quality_path).stat().st_size,
          'missing_required_geometry':missing_geometry,'strata':counts,
          'retained_records':sum(row['records'] for row in counts),'retained_molecules':sum(row['molecules'] for row in counts)}
        actual={row['size_stratum']:row for row in counts}
        population_complete=missing_geometry==0 and len(config_fingerprints)==1
        for row in manifest['strata']:
            value=actual.get(row['size_stratum'])
            if value is None or value['records']!=row['population_records'] or value['molecules']!=row['population_molecules']:
                population_complete=False;issues.append('Formal manifest population differs from current quality: '+row['size_stratum'])
        if set(actual)!=set(strata): population_complete=False;issues.append('Formal panel does not cover every retained size stratum')
        if missing_geometry: issues.append(f'WP1 still lacks required geometry for {missing_geometry} records; population is incomplete.')
    elif not args.integration_review:
        issues.append('Completed WP1 quality file not supplied; population completeness cannot be established.')
    probe=[]; probe_metadata=[]
    if args.b_probe_root:
        probe_paths=[]
        for value in args.b_probe_root:
            path=Path(value)
            if not path.is_dir(): issues.append('Paired POLAR cost root missing: '+value);continue
            probe_paths.extend(str(p) for p in path.rglob('receipt.json'))
            for meta_path in ([path/'metadata.json'] if (path/'metadata.json').is_file() else path.rglob('metadata.json')):
                probe_metadata.append({'path':str(meta_path),'sha256':sha(meta_path),'data':read_json(meta_path)})
        with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers,mp_context=multiprocessing.get_context('spawn')) as pool:
            for item in pool.map(read_receipt,list(dict.fromkeys(probe_paths)),chunksize=1): probe.extend(item['calls'])
        for row in probe:
            source=panel_by_id.get(row['record_id'])
            if source is None or source['record_payload_sha256']!=row['payload_sha256']:
                raise ValueError('Paired POLAR probe belongs to a different panel')
    paired=paired_polar(probe,strata)
    projection={'disabled':True,'reason':'Bounded integration population; full-corpus cost projections are intentionally disabled.'} if args.integration_review else projections(
      panel,calls,manifest,tasks,task_stats,cap,acct,population_complete,paired,storage['per_stratum_calibration'])
    if not args.integration_review:
        if not projection['strict_minimum_POLAR_available']:
            issues.append('Paired B without POLAR is absent in one or more size strata. Only executable B-with-POLAR scenarios are estimated; no POLAR saving is claimed.')
        for scenario in projection['scenarios']:
            archive=scenario['estimated_archived_output_bytes_percall_model']; parquet=scenario['estimated_Parquet_bytes_json_model']
            estimate=archive+parquet+600_000_000_000+400_000_000_000 if archive is not None and parquet is not None else None
            scenario['forward_plan_bytes_using_lmdb_ceiling_and_scratch_reservation']=estimate
            scenario['within_current_forward_budget']=estimate<=cap['budget_bytes'] if estimate is not None and cap.get('budget_bytes') is not None else None
            scenario['budget_note']='600 GB LMDB ceiling and 400 GB scratch/margin reserved; scenario archive and Parquet volumes measured-model projections; Hessian subset additional. Account quota is snapshot evidence and must be refreshed before formal output.'
    if not coverage['all_expected_slots_closed']: issues.append('Native panel has absent or unfinished task slots; full totals are withheld.')
    status=('INTEGRATION_NUMERIC_REVIEW_COMPLETE' if coverage['all_expected_slots_closed'] else 'INTEGRATION_NUMERIC_REVIEW_PARTIAL') if args.integration_review else (
      'WP4_PILOT_REPORT_COMPLETE' if coverage['all_expected_slots_closed'] and population_complete else 'WP4_PILOT_REPORT_INCOMPLETE')
    report={'status':status,'population_scope':'Bounded native integration test; no extrapolation' if args.integration_review else 'Formal stratified whole-molecule WP4 panel',
      'integration_review':args.integration_review,'seed':config['seed'],'job_id':os.environ['SLURM_JOB_ID'],
      'hostname':socket.gethostname(),'python_logical_entry':sys.executable,'threads':args.workers,
      'script_sha256':sha(Path(__file__).absolute()),'software':{'numpy':np.__version__,'duckdb':duckdb.__version__},
      'panel_manifest':{'path':str(args.panel_manifest),'sha256':manifest_sha,'data':manifest},
      'panel':{'path':str(panel_path),'bytes':panel_path.stat().st_size,'sha256':panel_sha},
      'quality_population':quality_population,'population_complete':population_complete,
      'coverage':coverage,'task_statistics':task_stats,'observations':obs,'storage':storage,'projections':projection,
      'capacity':cap,'accounting':acct,'execution_metadata':metadata,'paired_probe_metadata':probe_metadata,
      'closed_molecule_receipt_references':[{'path':item['receipt_path'],'sha256':item.get('receipt_sha256'),
        'molecule_id':item['receipt'].get('molecule_id'),'qm_child_cpu_seconds_all_attempts':item['receipt'].get('qm_child_cpu_seconds'),
        'attempts':item['receipt'].get('total_qm_attempts')} for item in closed],
      'software_version_lines':sorted({value for row in calls for value in row['software_version_lines']}),
      'keyword_merge':{'actual_B_keywords':next(task['keywords'] for task in config['tasks'] if task['name']=='pm7_B'),
        'recipe':'ENPART LARGE and static POLAR merged into B; ESP is a separate request; charged-state UHF calls are separate.',
        'native_B_successes':sum(row['status']=='SUCCESS' for row in calls if row['task']=='pm7_B'),
        'native_B_base_successes':sum(row.get('B_base_success') is True for row in calls if row['task']=='pm7_B'),
        'capability_evidence':{'path':str(ROOT/'reports/wp4_capability_conclusions.json'),
          'scope':'Auxiliary synthetic keyword compatibility only; excluded from native timing and population projections',
          'findings':[value for value in read_json(ROOT/'reports/wp4_capability_conclusions.json').get('findings',[])
            if value.get('property') in ('ESP merge','PM7 charge +/-1 UHF','POLAR static recipe')]}
          if (ROOT/'reports/wp4_capability_conclusions.json').is_file() else None},
      'issues':list(dict.fromkeys(issues)),'seconds':time.monotonic()-started,
      'lmdb_opened_or_written':False,'source_index_or_quality_modified':False}
    out=Path(args.output).absolute()
    if not out.is_relative_to(ROOT) or out==ROOT: raise ValueError('Use a report directory inside this phase root')
    out.mkdir(parents=True,exist_ok=True)
    save_json(out/'wp4_pilot_report.json',report)
    pending=out/'pilot_report.md.pending';pending.write_text(markdown(report));os.replace(pending,out/'pilot_report.md')
    print(json.dumps({'status':status,'report':str(out/'pilot_report.md'),'measured_records':coverage['measured_records'],
      'completed_molecules':coverage['completed_molecules'],'projection_enabled':not args.integration_review,
      'actual_reader_worker_pids':sorted(worker_pids)}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
