"""Actual Alpha232 native-step FP-only far-tail export from complete209 source."""
import argparse
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
from . import core as C


def read(Q,ref):
    Q.need(ref['bytes']<=2<<20,'Small original source/reference/plan metadata; large lists stay external')
    return Q.load(Q.verify(ref))


def execute(plan_path,proof_path):
    from ..alpha_runtime_v1 import common as Q,profile
    from ..alpha_runtime_v1.guard import Guard
    from ..exact_nn_cached_v1.engine import RECIPE
    import duckdb
    import pyarrow.parquet as pq
    plan=Q.load(plan_path);proof=Q.load(proof_path);request=proof['request'];out=Path(plan['output_directory'])
    Q.need(not out.exists(),'Fresh independent FP export output; preserve previous partials/results')
    actual=profile.admit(plan,minimum_workers=16);step=os.environ.get('SLURM_STEP_ID','')
    Q.need(sys.flags.dont_write_bytecode and plan['schema']=='ALPHA_EXACT_FP_RESCUE_EXPORT_PLAN_V1'
        and str(actual['job_id'])==str(plan['expected_parent_job_id'])=='1885232'and step.isdigit()
        and proof.get('step_id',step)==step and str(proof['job_id'])==actual['job_id']
        and proof['uid']==actual['uid']==os.getuid()==1264 and proof['endpoint']==Q.ENDPOINT
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        and request['producer_plan_reference']==Q.reference(plan_path)and request['scope_key']==plan['scope_key']
        and request['execution_argv']==plan['execution_argv']
        and sys.argv[-4:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)],
        'Actual Alpha232 numeric native step/UID/plan/startup; not a completed-parent claim')
    Q.need(plan['md5_hex_text_prefixes']==C.TARGETS and plan['duckdb_threads']in(4,8)
        and 0<plan['sql_memory_bytes']<plan['parent_rss_cap_bytes']==48<<30
        and plan['software_rss_budget_bytes']==48<<30 and plan['minimum_node_available_bytes']>=24<<30
        and 0<plan['spill_cap_bytes']<=plan['output_cap_bytes']<=30_000_000_000,
        'Actual modest SQL concurrency/private30GB including spill/48GiB parent+24GiB reserve')
    pins=[Q.reference(path)for path in Path(__file__).parent.glob('*.py')]
    Q.need(all(ref in plan['code_references']and ref in request['source_references']for ref in pins),'Actual immutable exporter source pins')
    ids={str(item['runtime']['job_id'])for item in plan['excluded_active_allocations']}
    Q.need({'1885201','1885232','1885233'}<=ids,'201+232+233 stay active exclusions, never closed credits')
    scope=Path(plan['output_scope_root'])
    for item in plan['excluded_active_allocations']:
        old=read(Q,item['plan_reference']);old_out=Path(old['output_directory'])
        Q.need(not scope.is_relative_to(old_out)and not old_out.is_relative_to(scope)
            and not out.is_relative_to(old_out),'Private export scope never contains/touches an active query cache/root')
    source=read(Q,plan['source_filter_reference']);reference=read(Q,plan['reference_manifest_reference'])
    Q.need(source['schema']=='PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1'and source['status']=='COMPLETE'
        and source['eligible_molecules']==105670833 and source['actual_parent']['uid']==1264
        and str(source['actual_parent']['job_id'])=='1885209'
        and set(source['policy']['identity_kinds'])=={'full','wp5'}and source['policy']['composition_veto']is False,
        'Original complete105670833 exact-only209 candidate source, never a narrow substitute')
    Q.need(reference['status']=='COMPLETE'and reference['schema']=='expansion_exact_ecfp4_reference_v1'
        and reference['molecules']==1196122 and reference['fingerprint_recipe']==RECIPE and reference['targets_present']is False,
        'Original full196 reference identity is carried to Main, no reference DATA/computation here')
    groups={bucket:[]for bucket in C.HEX};seen=set()
    for part in source['candidates']:
        bucket=part['fp_bucket'];Q.need(bucket in groups and len(bucket)==1 and part['path']not in seen,'Unique original physical candidate parts')
        seen.add(part['path']);groups[bucket].append(part)
    Q.need(sum(part['rows']for part in source['candidates'])==105670833,'Complete source manifest candidate-row conservation')
    out.mkdir(mode=0o700,parents=True,exist_ok=True);stop=threading.Event();guard=Guard(plan,stop);db=None;monitor=None
    started=time.perf_counter_ns();cpu=time.process_time_ns()
    try:
        db=duckdb.connect(':memory:')
        db.execute('SET threads='+str(plan['duckdb_threads']))
        db.execute("SET memory_limit='"+str(plan['sql_memory_bytes'])+"B'")
        db.execute("SET temp_directory='"+str(out/'spill').replace("'","''")+"'")
        db.execute("SET max_temp_directory_size='"+str(plan['spill_cap_bytes'])+"B'")
        db.execute('SET preserve_insertion_order=false')
        done=threading.Event()
        def observe():
            while not done.wait(.5):
                if stop.is_set():db.interrupt();return
        monitor=threading.Thread(target=observe,daemon=True);monitor.start()
        input_counts={bucket:0 for bucket in C.HEX};selected_counts=dict(input_counts);unique_counts=dict(input_counts);parts_count=0
        parts_path=out/'parts_catalog.jsonl';journal_path=out/'closed_files.jsonl';inputs_path=out/'input_parts_catalog.jsonl'
        with parts_path.open('xb')as parts,journal_path.open('xb')as journal,inputs_path.open('xb')as inputs:
            for bucket,refs in groups.items():
                guard.check()
                if not refs:continue
                paths=[];frames={}
                for ref in refs:
                    path=Q.verify(ref);before=C.frame(path);footer=pq.ParquetFile(path)
                    Q.need(footer.metadata.num_rows==ref['rows']and str(footer.schema_arrow.field('ecfp4_2048_hex').type)=='string',
                        'Actual original candidate part footer/row count/FP string type')
                    paths.append(path);frames[str(path)]=before
                    inputs.write(C.canonical(dict(reference=ref,current_frame=list(before),whole_body_SHA_verified=True)))
                    guard.check()
                stats=C.export_bucket(db,paths,bucket,sum(ref['rows']for ref in refs),out,Q.reference,parts,journal,
                    guard.check,prefixes=plan['md5_hex_text_prefixes'],max_rows=plan.get('rows_per_part',200000))
                for path,before in frames.items():Q.need(C.frame(path)==before,'Original candidate part changed during verified column-pruned scan')
                input_counts[bucket]=stats['input_candidate_rows'];selected_counts[bucket]=stats['selected_candidate_rows']
                unique_counts[bucket]=stats['distinct_fingerprints'];parts_count+=stats['part_count']
                print(json.dumps(dict(event='FP_RESCUE_PHYSICAL_BUCKET_CLOSED',physical_fp_bucket=bucket,**stats)),flush=True)
            inputs.flush();os.fsync(inputs.fileno())
        Q.need(sum(input_counts.values())==105670833 and sum(unique_counts.values())<=sum(selected_counts.values())<=105670833,
            'Whole input/selected row/distinct FP conservation')
        done.set();monitor.join();monitor=None;db.close();db=None;guard.sample();guard.check()
        actual.update(step_id=step,parent_completion_claimed=False,step_completion_claimed=False,
            step_completion_requires_external_native_accounting=True)
        result=dict(schema='ALPHA_EXACT_FP_RESCUE_EXPORT_V1',status='COMPLETE',endpoint=Q.ENDPOINT,uid=1264,
            actual=actual,source_filter_reference=plan['source_filter_reference'],reference_manifest_reference=plan['reference_manifest_reference'],
            md5_hex_text_prefixes=C.TARGETS,partition_rule='MD5_OF_CANONICAL_512_LOWERHEX_FP_TEXT_FIRST_NIBBLE',
            physical_partition_rule='FIRST_CANONICAL_FP_HEX_CHARACTER',fingerprint_recipe=RECIPE,
            input_candidate_rows=105670833,input_candidate_rows_by_physical_fp_bucket=input_counts,
            selected_candidate_rows=sum(selected_counts.values()),selected_candidate_rows_by_physical_fp_bucket=selected_counts,
            distinct_fingerprints=sum(unique_counts.values()),per_bucket_counts=unique_counts,part_count=parts_count,
            parts_catalog_reference=Q.reference(parts_path),parts_catalog_format='JSONL_FLAT_REFERENCE_WITH_ROWS_AND_PHYSICAL_FP_BUCKET',
            closed_files_journal_reference=Q.reference(journal_path),input_parts_catalog_reference=Q.reference(inputs_path),
            columns=[dict(name='ecfp4_2048_hex',arrow_type='string',required_lowercase_hex_characters=512)],
            within_physical_bucket_order='ecfp4_2048_hex_ASC_STRICT',global_FP_uniqueness_proof='DISJOINT_PHYSICAL_FP_PREFIX_DOMAINS_AND_EACH_BUCKET_DISTINCT',
            rows_per_part=plan.get('rows_per_part',200000),maximum_single_part_bytes=256<<20,
            original_candidate_source_rows_and_FP_domain_verified=True,source_candidate_whole_body_SHA_verified=True,
            CID_labels_graphs_or_downstream_features_exported=False,new_fingerprint_or_RDKit_calls=0,new_exact_NN_calls=0,
            source_plan_reference=Q.reference(plan_path),startup_proof_reference=Q.reference(proof_path),source_references=pins,
            sql_threads=plan['duckdb_threads'],resource_observation=guard.receipt(),wall_nanoseconds=time.perf_counter_ns()-started,
            process_CPU_nanoseconds=time.process_time_ns()-cpu,parent_232_233_or_201_modified=False,
            content_completion_is_not_Slurm_parent_or_step_C0=True)
        Q.need(len(C.canonical(result))<2<<20,'Small final manifest; all part/source lists stay external')
        return Q.write(out/'manifest.json',result)
    except BaseException:
        Q.write(out/'failure.json',dict(error=traceback.format_exc(),partials_preserved=True,active_jobs_modified=False));raise
    finally:
        if monitor is not None:done.set();monitor.join()
        if db is not None:db.close()
        guard.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True,type=Path);parser.add_argument('--startup-proof',required=True,type=Path)
    args=parser.parse_args();print(execute(args.plan,args.startup_proof))


if __name__=='__main__':main()
