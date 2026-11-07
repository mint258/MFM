"""Reuse unchanged original Common graph scanner, selector and feature objects."""
import collections
import concurrent.futures as cf
import json
import multiprocessing as mp
from pathlib import Path
from .runtime import need,pin,save,Writer
from .context import ensure_spawn_entrypoint


def produce(ctx,common,mode='full'):
    from workflows.expansion.common_molecular_fp_main_v1 import scan as S,io as I,kernel as K
    from workflows.expansion.common_molecular_fp_main_v1.run import Dispatch
    from workflows.expansion.common_molecular_fp_candidate_v1 import census as Census
    out=ctx.out/'graph';out.mkdir();budget=ctx.budget
    members=common['membership_tables'];_,roles=ctx.roles(ctx.value);formal=ctx.formal_reference
    need(len(members)==len(roles)==16 and common['pilot_only'] is False,'TRUE_FULL_COMMON_33_SOURCE_VIEWS')
    data=[*members,*roles,formal];bodies={};db=None;dispatch=None
    source=Writer(out/'source_identity.DATA.jsonl',budget);results=Writer(out/'graph_results.DATA.jsonl',budget)
    try:
        for ref in data:bodies[ref['path']]=I.Body({k:ref[k] for k in ('path','bytes','sha256')},budget)
        db,expected=S.prepare(out,bodies,members,roles,common,mode,budget)
        context=mp.get_context('spawn');barrier=context.Barrier(16);proof_directory=out/'worker_sources';proof_directory.mkdir()
        ensure_spawn_entrypoint()
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=context,initializer=K.initialize,initargs=(barrier,str(proof_directory))) as pool:
            dispatch=Dispatch(pool,db,results,budget)
            try:scan=S.scan_formal(db,bodies[formal['path']],source,dispatch,budget)
            finally:dispatch.collect(True)
        Census.require_same_membership(expected,scan['all_common_observed_census'])
        need(db.execute('SELECT count(*) FROM selected s LEFT JOIN results r USING(mid) WHERE r.mid IS NULL').fetchone()[0]==0
             and db.execute('SELECT count(*) FROM results r LEFT JOIN selected s USING(mid) WHERE s.mid IS NULL').fetchone()[0]==0,
             'COMPLETE_SELECTED_SOURCE_AND_RESULT_CENSUS')
        n=db.execute('SELECT count(*) FROM results').fetchone()[0]
        holds=db.execute("SELECT count(*) FROM results WHERE status<>'UNIQUE_GRAPH_PROJECTION_CANDIDATE'").fetchone()[0]
        need(n==scan['selected_MIDs'] and len(dispatch.pids)==16,'EXACT_SELECTED_AND16_ACTUAL_WORKER_PIDS')
        source.close();results.close();projection=Writer(out/'strict5_projection.DATA.jsonl',budget)
        try:
            for mid,raw in db.execute('SELECT mid,strict5 FROM results WHERE strict5 IS NOT NULL ORDER BY mid'):
                projection.write(json.loads(raw))
        finally:projection.close()
        # The original reducer already proved all feature values equal for a
        # UNIQUE_GRAPH projection. Retain that complete feature row for2.1.
        # Never select a representative from a multiple-graph HOLD.
        features=Writer(out/'structural_features.DATA.jsonl',budget);pending=None;pending_mid=None
        try:
            with Path(results.path).open() as stream:
                for line in stream:
                    event=json.loads(line);phase=event['phase'];mid=event['molecule_id']
                    if phase=='GRAPH_RESULT':
                        if pending_mid!=mid:pending=None;pending_mid=mid
                        if pending is None and event.get('status')=='FEATURES_DERIVED':pending=event['features']
                    elif phase=='MID_REDUCTION':
                        if event['status']=='UNIQUE_GRAPH_PROJECTION_CANDIDATE':
                            need(pending_mid==mid and pending is not None and pending['full_key']==event['strict5_projection']['full_key'],
                                 'UNIQUE_GRAPH_FEATURES_BOUND_TO_ORIGINAL_REDUCER')
                            features.write(dict(pending,molecule_id=mid,effective_role=event['effective_role'],native_records=event['native_records']))
                        pending=None;pending_mid=None
        finally:features.close()
        need(features.rows==projection.rows,'WHOLE_UNIQUE_REFERENCE_FEATURE_AND_STRICT5_COUNTS')
        def member(mid):
            r=db.execute('SELECT role,n FROM members m JOIN selected s USING(mid) WHERE m.mid=?',(mid,)).fetchone()
            need(r is not None,'READBACK_MID_OUTSIDE_EXACT_COMMON');return r
        with Path(projection.path).open('rb') as f:parsed,observed=I.read_strict5_rows(f,member)
        need(parsed==projection.rows,'FULL_STRICT5_PARSED_READBACK')
        if holds==0:Census.require_same_membership(expected,observed)
        db.commit();db.close();db=None
        index=pin(out/'census.sqlite',budget.check)
        result=dict(schema='EXPANSION_FULL_COMMON_GRAPH_PRODUCER_V1',
            status='COMPLETE_PENDING_ACTUAL_PARENT_C0_AND_ROOT_ACCEPTANCE' if holds==0 else 'SOURCE_GRAPH_HOLD_NOT_A_SUBSET_REFERENCE',
            mode=mode,common_source_manifest=ctx.common_reference,HOLD_MIDs=holds,strict5_rows=projection.rows,
            projection=projection.reference(),structural_features=features.reference(),source_journal=source.reference(),
            graph_results=results.reference(),census_index=index,all33_source_views=data,
            expected_all_common_census=expected,observed_projection_census=observed,scan=scan,
            worker_MID_counts=dict(dispatch.pids),worker_CPU_seconds=dict(dispatch.cpu),
            targets_present=False,downstream_features_present=False,source_kind='v1_common_structure_projection',
            fingerprint_recipe='ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5',
            reference_is_not_55k_or_all_TRAIN_proxy=True,original_multiple_graph_HOLD_semantics_unchanged=True,
            graph_selector='ORIGINAL_CREATOR_SMILES_STRIP_TEMPLATE_V1',candidate_release_authorized=False)
        return save(out/'receipt.json',result),result
    finally:
        source.close();results.close()
        if db is not None:db.close()
        for body in bodies.values():body.close()
