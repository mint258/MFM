"""Consume the exact closed author ZIP; passive format evidence in a real CPU job."""
import argparse,collections,hashlib,io,json,os,stat,sys,time,unittest
from pathlib import Path
from secondary_moleculenet_csv6_identity_v1.runtime import Budget
from secondary_moleculenet_csv6_identity_v1 import journal as J
from . import contracts as C,guard as G,formats as F
Q=C.Q


def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid)


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries)
    Q.need(suite.countTestCases()==3,'EXACT_NEW3_PASSIVE_FORMAT_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    result={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),
        'transcript':stream.getvalue(),'before_original_DATA_and_Budget':True,'old_methods_reexecuted':False}
    Q.write_new(out/'fixtures3.json',result)
    Q.need(r.wasSuccessful() and r.testsRun==3 and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),
        'NEW3_MUST_PASS_BEFORE_ZIP_OR_MONITOR')
    return result


def imports(plan):
    for name,module in list(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if path and Path(path).suffix=='.py' and name.startswith('secondary_'):
            Q.need(C.ROOT/'code' in Path(path).absolute().parents and Q.ref(path) in plan['source_references'],
                'ALL_ACTUAL_NEW_AND_ORIGINAL_IMPORTS_PINNED:'+name)


def open_verified(reference,budget):
    C.data_locator(reference);path=Q.literal(reference['path']);s=path.lstat();before=frame(s)
    Q.need(stat.S_ISREG(s.st_mode) and not path.is_symlink() and s.st_uid==1264
        and s.st_size==reference['bytes'],'EXACT_OWNED_ORIGINAL_ZIP_FRAME')
    stream=path.open('rb')
    try:
        Q.need(frame(os.fstat(stream.fileno()))==before,'SAME_ORIGINAL_ZIP_OPEN_FD')
        n=0;digest=hashlib.sha256()
        while n<=reference['bytes']:
            budget.check();raw=stream.read(min(1<<20,reference['bytes']+1-n))
            if not raw:break
            n+=len(raw);digest.update(raw)
        Q.need(n==reference['bytes'] and digest.hexdigest()==reference['sha256']
            and frame(os.fstat(stream.fileno()))==before==frame(path.lstat()),
            'COMPLETE_ORIGINAL_ZIP_SHA_AND_STABLE_FD_BEFORE_MEMBER_DECODE')
        stream.seek(0);return stream,path,before
    except BaseException:stream.close();raise


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True)
    p.add_argument('--startup-proof',type=Path,required=True);args=p.parse_args()
    plan,proof=G.require_startup(args.plan,args.startup_proof);parents=C.inputs(plan)
    out=Q.literal(plan['output_directory']);Q.need(not out.exists(),'FRESH_PASSIVE_FORMAT_OUTPUT');out.mkdir(parents=True,mode=0o700)
    budget=None;archive_fd=None;members=None;line_index=None;fx=None;started=time.monotonic()
    progress={'verified_member_prefix':0};kind_counts=collections.Counter();unknown=0;mat_fields=[]
    try:
        fx=fixtures(out);imports(plan);budget=Budget(plan,proof,out);budget.check()
        archive_ref=parents['data'][0];archive_fd,path,before=open_verified(archive_ref,budget)
        members=(out/'passive_member_format_evidence.DATA.jsonl').open('xb')
        line_index=(out/'opaque_original_line_segments.DATA.jsonl').open('xb')
        J.append(line_index,{'schema':'QM7B2013_OPAQUE_ORIGINAL_LINE_INDEX_V1','event':'INDEX_START_NO_RAW_TEXT',
            'original_archive_reference':archive_ref,'original_uncompressed_producer_reference':parents['original_raw_reference']},budget)
        sink=F.MemberSink(C.EXPANDED)
        def emit_member(original):
            nonlocal unknown
            raw=sink.take();ordinal=original['physical_member_ordinal'];segment=original['original_uncompressed_blob_segment']
            Q.need(len(raw)==segment['bytes'] and hashlib.sha256(raw).hexdigest()==segment['sha256'],
                'MEMORY_MEMBER_EQUALS_FROZEN_INVENTORY_BYTES')
            line_buffer=[]
            def flush_lines():
                if line_buffer:
                    J.append(line_index,{'schema':'QM7B2013_OPAQUE_ORIGINAL_LINE_SEGMENT_BATCH_V1','member_ordinal':ordinal,
                        'source_original_uncompressed_reference':parents['original_raw_reference'],
                        'segments':list(line_buffer),'line_text_IDs_SMILES_coordinates_or_targets_copied':False},budget)
                    line_buffer.clear()
            def emit_line(line):
                budget.check()
                line_buffer.append({'line_ordinal':line['line_ordinal'],
                    'source_segment':{'offset':segment['offset']+line['member_uncompressed_offset'],
                                      'bytes':line['bytes'],'sha256':line['sha256']}})
                if len(line_buffer)>=256:flush_lines()
            finding=F.inspect_member(original['original_filename'],raw,emit_line)
            flush_lines()
            status=finding['format'];kind_counts[status]+=1;unknown+=('UNKNOWN' in status or 'HOLD' in status)
            if finding.get('fields') is not None:
                mat_fields.append({'member_ordinal':ordinal,'fields':finding['fields'],
                    'scipy_version':finding['scipy_version'],'MAT_row_mapping':'UNKNOWN'})
            inventory={k:v for k,v in original.items() if k!='event'}
            J.append(members,{'schema':'QM7B2013_PASSIVE_MEMBER_FORMAT_EVIDENCE_V1','event':'CURRENT_ZIP_MEMBER_FULLY_REHASHED',
                'original_archive_reference':archive_ref,'opaque_original_member_reference':{
                    'original_uncompressed_producer_reference':parents['original_raw_reference'],'source_segment':segment},
                'original_inventory_metadata':inventory,'format_finding':finding,
                'original_member_names_or_ordinals_are_row_mapping':False,'new_raw_alias_written':False},budget)
            progress.update(verified_member_prefix=ordinal+1,verified_uncompressed_prefix_bytes=sink.total)
        observation=F.inventory(archive_fd,sink,emit_member,lambda n=0:budget.check(),C.EXPANDED,C.MEMBERS)
        Q.need(observation['physical_members']==C.MEMBERS and observation['total_uncompressed_bytes']==C.EXPANDED
            and observation['directory_flags']==0 and observation['duplicate_literal_filenames_preserved']==0
            and observation['every_member_EOF_CRC_SHA_verified'] is True,'CURRENT_CONTAINER_EQUALS_ACTUAL1884892_STRUCTURAL_MASS')
        Q.need(observation==parents['expected_container'],'ALL_FROZEN_AQ_CONTAINER_METADATA_MATCHES_ACTUAL_PARENT')
        Q.need(sink.total==parents['original_raw_reference']['bytes']
            and sink.concat.hexdigest()==parents['original_raw_reference']['sha256'],
            'RECOMPUTED_ZIP_CONCAT_SIGNATURE_EQUALS_CLOSED_ORIGINAL_RAW_PRODUCER')
        Q.need(frame(os.fstat(archive_fd.fileno()))==before==frame(path.lstat()),'ORIGINAL_ZIP_UNCHANGED_AFTER_FORMAT_SCAN')
        archive_fd.close();archive_fd=None
        for handle in (members,line_index):handle.flush();os.fsync(handle.fileno());handle.close()
        refs={'member_format_DATA_reference':J.pin(out/'passive_member_format_evidence.DATA.jsonl'),
              'opaque_line_index_DATA_reference':J.pin(out/'opaque_original_line_segments.DATA.jsonl')}
        budget.sample();Q.need(budget.reason is None,'RESOURCE_STOP_NOT_FULL_FORMAT_CLOSURE')
        status='PASSIVE_FORMAT_TECHNICAL_CLOSURE_UNKNOWN_HOLD_RETAINED' if unknown else 'PASSIVE_FORMAT_METADATA_TECHNICALLY_CLOSED_MAPPING_UNKNOWN'
        summary={'schema':'QM7B2013_PASSIVE_FORMAT_SUMMARY_V1','status':status,'original_acquisition_job':'1884892',
            'physical_members':observation['physical_members'],'total_uncompressed_bytes':sink.total,'format_counts':dict(kind_counts),
            'members_with_unknown_format_hold':unknown,'MAT_field_name_shape_class_metadata':mat_fields,
            'original_archive_reference':archive_ref,'current_original_ZIP_frame':list(before),
            'complete_whole_ZIP_SHA_every_member_EOF_CRC_SHA_verified':True,
            'original_concat_signature_recomputed_from_ZIP_not_a_new_old_raw_file_hash':True,
            'new_compressed_or_uncompressed_aliases':0,'original_assets_or_UNKNOWNs_changed':False,
            'new_network_graph_key_UFF_QM_calls':0,'MAT_row_mapping':'UNKNOWN',
            'names_order_counts_or7211_are_mapping_evidence':False,'graph_or_identity_pool_decontamination_accepted':False,
            'numeric_arrays_or_coordinate_floats_loaded':False,'summary_contains_IDs_coordinates_target_values':False,**refs}
        sr=J.write_json(out/'finding_summary.json',summary,budget)
        receipt={'schema':'SECONDARY_QM7B2013_PASSIVE_FORMAT_RECEIPT_V1','status':status,'job_id':str(proof['job_id']),
            'endpoint':Q.ENDPOINT,'uid':1264,'node':plan['node'],'plan_reference':Q.ref(args.plan),
            'startup_proof_reference':Q.ref(args.startup_proof),'scope_parameters':C.PARAMETERS,
            'acquisition_receipt_reference':plan['acquisition_receipt_reference'],
            'acquisition_accounting_reference':plan['acquisition_accounting_reference'],'original_archive_reference':archive_ref,
            'finding_summary_reference':sr,'fixtures':fx,'all_member_observation':observation,**refs,
            'runtime':budget.receipt(),'elapsed_seconds':time.monotonic()-started,'reader_processes':1,'allocated_cpus':16,
            'graph_SMILES_MAT_mapping_accepted':False,'new_network_graph_key_UFF_QM_calls':0,'full_or_pool_release':False,
            'actual_new_parent_terminal_cost_pending_Root':True,'cost_overrun_action':'REPORT_AND_CONTINUE'}
        J.write_json(out/'receipt.json',receipt,budget);print(json.dumps({'status':status,'receipt_reference':J.pin(out/'receipt.json')}));return 0
    except BaseException as exc:
        for handle in (members,line_index):
            if handle and not handle.closed:handle.flush();os.fsync(handle.fileno());handle.close()
        Q.write_new(out/'partial_hold.json',{'schema':'QM7B2013_PASSIVE_FORMAT_PARTIAL_HOLD_V1','status':'PREFIX_RETAINED_NOT_COMPLETE',
            'error_type':type(exc).__name__,'contract_error':str(exc) if isinstance(exc,ValueError) else 'NONCONTRACT_EXCEPTION',
            'fixtures':fx,'progress':progress,'runtime':budget.receipt() if budget else None,
            'original_assets_unchanged':True,'new_network_graph_key_UFF_QM_calls':0,'MAT_row_mapping':'UNKNOWN',
            'identity_or_pool_release':False,'actual_new_parent_cost_pending_Root':True});raise
    finally:
        if archive_fd:archive_fd.close()
        if budget:budget.finish()


if __name__=='__main__':raise SystemExit(main())
