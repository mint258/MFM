"""One post-C0 diagnostic supplement; no ordinary export mutation or new science."""
import argparse
import concurrent.futures as cf
import hashlib
import json
import multiprocessing as mp
import pathlib
import traceback
from . import contract as C, domain, source, verify
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v2 import (
    domain as D, io as I, run as Original, frame_mapping as M)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=pathlib.Path, required=True)
    parser.add_argument('--startup-proof', type=pathlib.Path, required=True)
    args = parser.parse_args()
    plan = C.meta(C.Q.pin(args.plan))
    C.need(plan['schema'] == 'D3_FAST55K_DIAGNOSTIC_SUPPLEMENT_PLAN_V1' and
           plan['scope_parameters'] == C.parameters(plan), 'EXACT_INDEPENDENT_SUPPLEMENT_PLAN')
    d3, norm, d5, receipt, prior, accepted, old = C.parents(plan)
    proof = C.guard(args.plan, args.startup_proof, plan)
    for ref in C.sources():
        C.need(ref in proof['request']['source_references'], 'ALL_NEW_AND_ORIGINAL_SOURCE_OBJECTS_PINNED')
    root = pathlib.Path(plan['output_directory'])
    C.need(C.OUTPUT in root.parents and not root.exists() and not any(p.is_symlink() for p in (root, *root.parents)),
           'FRESH_INDEPENDENT_DIAGNOSTIC_OUTPUT')
    root.mkdir(parents=True)
    I.configure(plan, old)
    gate, _ = Original.fixtures(root)  # Original three Source methods, same Parent; no new suite.
    budget = db = pool = None
    try:
        budget = I.Budget(plan, proof, root)
        budget.check(force=True)
        bounded = C.meta(plan['bounded_export_review_reference'])
        roots = list(bounded['transitive_closed_output_roots'])
        d3root = prior['output_directory']
        d5root = str(pathlib.Path(C.meta(d5['actual_acceptance_reference'])['actual_parent']['manifest']['path']).parent)
        roots.extend([d3root, d5root])
        roots = list(dict.fromkeys(roots))
        components = accepted['component_references']
        cfg = D.read(components['typed_reader_config_reference'], roots)
        coverage = D.read(components['coverage_reference'], roots)
        C.need(coverage['all14task_and_base_exact_once'] is True and not coverage['errors'] and not coverage['quality_hold_fields'],
               'ACTUAL_CLOSED_ALL_N_TYPED_VALUES_NOT_MASKED_DIAGNOSTIC_FIT_VALUES')
        for ref in cfg['data_references']:
            if ref['path'] not in I.B.ALLOWED:
                D.register(ref, roots)
        cfg = I.configure_reader(cfg, coverage, old['output_directory'])
        fields = I.load_data(cfg['field_map_reference'], 8 << 20)
        C.need(len(fields) == 146 and {f['field_id'] for f in fields} == set(range(146)), 'ALL146_ORIGINAL_FIELDS')
        configurations = receipt['actual_configuration_references']
        registry, mapping, recipe, physical = (D.read(configurations[k], roots) for k in
            ('registry_reference', 'mapping_reference', 'projection_recipe_reference', 'target_policy_reference'))
        compiled = M.compile_targets(registry, mapping)
        Original.checked_recipe(recipe, {f['field_key']: f for f in registry['fields'] if f['status'] == 'enabled'},
                                compiled, fields, plan['source_references'])
        for tid, target in compiled['physical_targets'].items():
            if any(member['registry_id'] == 674 for member in target['members']):
                C.need(physical['targets'][tid]['frozen_all_registry674_conditions_OFF'] is True,
                       'SAME_ACTUAL_D4_R674_OFF_NO_NUMERIC_MASK_CHANGE')
        db, selection = domain.build(plan, receipt, prior, d5, root, roots, budget)
        geometry = D.read(components['geometry_reference'], roots)
        binding = D.register(geometry['cell_binding_reference'], roots)
        I.require(binding)
        policy = dict(bounded, target_policy=physical['targets'], actual_cell_binding_reference=binding)
        book = D.read(cfg['logical_group_plan_reference'], roots, 8 << 20)
        catalog = I.connect(coverage['parts_catalog']['path'], True)
        wanted = {row[0] for row in db.execute('SELECT rid FROM wanted_rids')}
        jobs = {row[0] for row in catalog.execute('SELECT job,rid FROM selected') if row[1] in wanted}
        catalog.close()
        groups = [group for group in C.O.B.logical(book['groups']) if group['source_job_id'] in jobs]
        context = {'plan': plan, 'old_plan': old, 'reader_config': cfg, 'field_map': fields,
                   'compiled': compiled, 'recipe': recipe, 'domain_database': str(root / 'domain.sqlite'),
                   'binding_database': binding['path'], 'coverage_catalog': coverage['parts_catalog']['path'],
                   'control': budget.control, 'job_id': str(proof['job_id']), 'node': proof['request']['node'],
                   'registered_references': list(I.B.ALLOWED.values()), 'reader_origins': dict(I.B.ORIGINS)}
        pool = cf.ProcessPoolExecutor(max_workers=16, mp_context=mp.get_context('spawn'),
                                      initializer=source.initialize, initargs=(context,))
        stage = root / 'permanent_f64_source_groups'
        stage.mkdir()
        active, cursor = {}, iter(groups)
        exhausted = False
        while active or not exhausted:
            while not exhausted and len(active) < 32:
                budget.check()
                group = next(cursor, None)
                if group is None:
                    exhausted = True
                    break
                key = hashlib.sha256(json.dumps(group, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
                path = stage / (key + '.sqlite')
                C.need(not path.exists(), 'NO_AUTOMATIC_GROUP_RETRY')
                active[pool.submit(source.one, (key, group, str(path)))] = key
            if active:
                done, _ = cf.wait(active, timeout=1, return_when=cf.FIRST_COMPLETED)
                for future in done:
                    active.pop(future)
                    result = future.result()
                    I.add(result['reference'])
                    I.require(result['reference'])
                    Original.merge(db, result)
                    I.append(root / 'closed_groups.jsonl', result)
        stores, eligibility = source.write(db, root, compiled, policy, plan, proof, budget)
        verification = verify.run(db, stores, root, pool, budget)
        workers = list(pool._processes.values())
        pool.shutdown(wait=True, cancel_futures=False)
        pool = None
        C.need(all(not p.is_alive() and p.exitcode == 0 for p in workers), 'ALL_ORIGINAL_PROJECTION_WORKERS_CLOSED')
        db.close()
        db = None
        budget.check(force=True, dispatch=False)
        I.save(root / 'receipt.json', {'schema': 'D3_DIAGNOSTIC_SUPPLEMENT_PARENT_RECEIPT_V1',
            'status': 'DIAGNOSTIC_SUPPLEMENT_CLOSED_PENDING_ACTUAL_C0_ROOT_WRAPPER', 'actual_parent_job_id': str(proof['job_id']),
            'uid': 1278, 'node': proof['request']['node'], 'actual_cpus': 16,
            'plan_reference': C.Q.pin(args.plan), 'startup_proof_reference': C.Q.pin(args.startup_proof),
            'D3_export_reference': plan['D3_export_reference'], 'D4_normalization_reference': plan['D4_normalization_reference'],
            'D5_delivery_reference': plan['D5_delivery_reference'], 'actual_configuration_references': configurations,
            'source3_reference': gate, 'verification_reference': verification, 'role': C.ROLE,
            'store_namespace': C.STORE_NAMESPACE, 'consumer_alias_prefix': 'diagnostic/', 'store_references': stores,
            'diagnostic_role_available': bool(stores), 'original_molecule_effective_role': 'TRAIN',
            'training_excluded': True, 'scientific_masks_unchanged': True, 'same_D4_statistics_no_refit': True,
            'new_QM_UFF_calls': 0, 'r674_loss': 'OFF_WITH_ORIGINAL_VALUES_AND_MASKS',
            'r73': 'ORIGINAL_ORDERED_RECORDS_PERMANENT_F64_ONCE_F32', 'loss_eligibility_counts': eligibility,
            'all_handles_closed': True, 'Model_ACK': False, 'full_Common_D6_release': False, **selection})
        return 0
    except BaseException as error:
        I.save(root / 'failure.DATA.json', {'error': repr(error), 'traceback': traceback.format_exc(),
            'original_D3_D4_D5_unchanged': True, 'closed_groups_preserved_no_retry': True, 'new_QM_UFF_calls': 0})
        return 3
    finally:
        if pool is not None:
            pool.shutdown(wait=True, cancel_futures=False)
        if db is not None:
            db.close()
        if budget is not None:
            budget.close()


if __name__ == '__main__':
    raise SystemExit(main())
