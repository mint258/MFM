"""Register a closed current-release N1 physical-QA result, without rerunning QA."""
import argparse, fcntl, hashlib, json, os, pathlib, subprocess, time

ROOT = pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REGISTRY = ROOT/'control/n1_current_canonical_registry_v1/current.json'
CONTROL = ROOT/'control/n1_current_canonical_actual_20261105_v1'
OUTPUT = ROOT/'artifacts/conformers/n1_current_canonical_physical_qa_v1/alpha4407_current_v1'


def load(path):
    return json.loads(pathlib.Path(path).read_bytes())


def reference(path):
    path = pathlib.Path(path)
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def save_new(path, value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode()
    if path.exists():
        assert path.read_bytes() == raw, ('EXISTING_DIFFERENT_PUBLICATION', str(path))
    else:
        with path.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    return reference(path)


def atomic_replace(path, value):
    pending = path.with_name('.'+path.name+'.accept4525894.pending')
    with pending.open('xb') as stream:
        stream.write((json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)+'\n').encode())
        stream.flush(); os.fsync(stream.fileno())
    os.replace(pending, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job-id', required=True, choices=['4525894'])
    args = parser.parse_args(); jid = args.job_id
    argv = ['sacct','-j',jid,'-X','--parsable2',
            '--format=JobIDRaw,State,ExitCode,ElapsedRaw,User,UID,AllocCPUS,NodeList']
    actual = subprocess.run(argv, capture_output=True, text=True, check=True, timeout=30)
    lines = [line.split('|') for line in actual.stdout.splitlines() if line.strip()]
    assert len(lines) == 2 and lines[0][0] == 'JobIDRaw', lines
    parent = dict(zip(lines[0], lines[1]))
    expected = dict(JobIDRaw=jid, State='COMPLETED', ExitCode='0:0', User='zixiao',
                    UID='1278', AllocCPUS='16', NodeList='compute-0-18')
    assert all(parent[k] == value for k, value in expected.items()), parent
    receipt = load(OUTPUT/'receipt.json'); handoff = load(OUTPUT/'D6_geometry_handoff.json')
    scope = receipt['identity_scope']
    assert receipt['job_id'] == jid and receipt['uid'] == 1278
    assert receipt['accepted_extra_count'] == receipt['independent_QA_passed'] == 4400
    assert receipt['new_QM_calls'] == receipt['new_UFF_calls'] == 0
    assert receipt['source_state_counts'] == dict(REAL_SECOND_GEOMETRY_SELECTED=4400,
        PPRIME2_PENDING_GENERATION_OR_INPUT_FAILURE=4, PPRIME2_PENDING_NO_SECOND_REAL_GEOMETRY=3)
    assert receipt['historical_noncanonical_coverage'] == 'UNKNOWN'
    assert receipt['all_global_registered_extra_identity_tables_included'] is False
    assert handoff['physical_QA_receipt_reference'] == reference(OUTPUT/'receipt.json')
    assert handoff['identity_scope'] == scope
    # Consume the original closed publisher metadata. Never scan coordinates,
    # reopen active databases, recompute native calls or rehash payload files.
    for key in ('accepted_extra_index','extra_geometry_table','Pprime_two_conformer_order_sidecar'):
        ref = receipt[key]
        assert handoff[key] == ref and pathlib.Path(ref['path']).stat().st_size == ref['bytes']
    accounting_path = CONTROL/('actual_'+jid+'_accounting.json')
    if accounting_path.exists():
        accounting = load(accounting_path)
        assert accounting['parent'] == parent and accounting['query_returncode'] == 0
    else:
        raw_path = CONTROL/('actual_'+jid+'.sacct.psv')
        with raw_path.open('x') as stream: stream.write(actual.stdout)
        save_new(accounting_path, dict(schema='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1',
            status='ACTUAL_PARENT_ACCOUNTING_CLOSED',endpoint='202.38.247.57:22',uid=1278,
            query_returncode=actual.returncode,query_argv=argv,raw_sacct_reference=reference(raw_path),
            observed_unix_seconds=time.time(),parent=parent))
    account_ref = reference(accounting_path)
    with (REGISTRY.parent/'current.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        registry = load(REGISTRY)
        assert registry['identity_scope'] == scope and registry['historical_noncanonical_coverage'] == 'UNKNOWN'
        members = registry['members']
        found = [row for row in members if row['actual_parent_job_id'] == jid]
        member = dict(actual_parent_job_id=jid,actual_parent_accounting_reference=account_ref,
            publisher_receipt_reference=reference(OUTPUT/'receipt.json'),
            accepted_extra_index_reference=receipt['accepted_extra_index'],
            registered_identity_table_reference=receipt['extra_geometry_table'],accepted_extra_count=4400,
            Pprime_two_conformer_order_reference=receipt['Pprime_two_conformer_order_sidecar'])
        if found:
            assert found == [member]
        else:
            history = REGISTRY.parent/'snapshots'; history.mkdir(exist_ok=True)
            previous = history/(registry['registry_snapshot_id']+'.json')
            old_raw = REGISTRY.read_bytes()
            if previous.exists(): assert previous.read_bytes() == old_raw
            else:
                with previous.open('xb') as stream: stream.write(old_raw)
            registry['previous_registry_snapshot_reference'] = reference(previous)
            registry['members'] = members + [member]
            registry['registry_snapshot_id'] = 'v1-final-candidate-N1-4400-4525894-20261105'
            registry['source_input_pointer_history_preserved'] = True
            registry['current_registered_extra_count'] = sum(row['accepted_extra_count'] for row in registry['members'])
            snapshot = history/(registry['registry_snapshot_id']+'.json')
            save_new(snapshot, registry)
            atomic_replace(REGISTRY, registry)
        registry_ref = reference(REGISTRY)
    acceptance = dict(schema='N1_CURRENT_CANONICAL_PHYSICAL_ACCEPTANCE_V1',
        status='CURRENT_RELEASE_REGISTERED_PHYSICAL_COMPONENT',identity_scope=scope,
        actual_parent_job_id=jid,actual_parent_accounting_reference=account_ref,
        accepted_extra_count=4400,source_state_counts=receipt['source_state_counts'],
        current_registry_reference=registry_ref,registry_snapshot_id=registry['registry_snapshot_id'],
        **{k:receipt[k] for k in ('accepted_extra_index','extra_geometry_table','Pprime_two_conformer_order_sidecar')},
        publisher_receipt_reference=reference(OUTPUT/'receipt.json'),
        D6_geometry_handoff_reference=reference(OUTPUT/'D6_geometry_handoff.json'),
        historical_noncanonical_coverage='UNKNOWN',all_global_registered_extra_identity_tables_included=False,
        original_source_history_and_IDs_preserved=True,ordinary_N_and_D5_unchanged=True,
        new_QM_calls=0,new_UFF_calls=0,final_Common_D6_training_release=False,
        remaining_dependencies=['ordinary_orders_statistics','final_Common_join','Pprime_scope_completion',
                                'full_TRAIN_normalization_and_masks','Model_actual_payload_ACK'])
    accepted_path = CONTROL/'accepted_current_release_4525894.json'
    accepted_ref = save_new(accepted_path, acceptance)
    with (ROOT/'control/current_work_state.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state_path=ROOT/'control/current_work_state.json'; state=load(state_path)
        state['N1_current_release_actual_20261105'] = dict(acceptance,acceptance_reference=accepted_ref)
        atomic_replace(state_path,state)
    with (ROOT/'control/root_current_all_future_ledger_v1.lock').open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ledger_path=ROOT/'control/root_current_all_future_ledger_v1.json'; ledger=load(ledger_path)
        entry=ledger['entries']['n1_current_canonical_physical_qa_20261105_v1']
        assert entry['job_id'] == jid
        entry.update(status='ACTUAL_C0_CURRENT_RELEASE_REGISTERED_PHYSICAL_COMPONENT',
                     future_reserved_bytes=0,actual_parent_accounting_reference=account_ref,
                     acceptance_reference=accepted_ref,actual_used_bytes_not_refunded=True)
        total=sum(row['future_reserved_bytes'] for row in ledger['entries'].values())
        ledger.update(known_future_reserved_bytes=total,total_future_reserved_bytes=total,
                      entries_observed_unix_seconds=time.time())
        atomic_replace(ledger_path,ledger)
    print('CURRENT_RELEASE_N1_REGISTERED=4400; SOURCE_FAILURE_STATES_PRESERVED=7; NEW_QM_UFF=0')


if __name__ == '__main__': main()