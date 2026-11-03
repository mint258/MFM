"""Original full scanner/dispatcher/kernel/reducer, independent Alpha I/O."""
import collections,concurrent.futures as cf,json,multiprocessing as mp
from pathlib import Path
from . import io as I,science


def produce(plan,out,guard,common,members,roles,formal,objects):
    S=objects['scan'];Census=objects['census'];old_io=objects['io'];Dispatch=objects['Dispatch']
    graph=out/'graph';graph.mkdir();bodies={};db=None
    source=I.Writer(graph/'source_identity.DATA.jsonl',guard);results=I.Writer(graph/'graph_results.DATA.jsonl',guard)
    try:
        for ref in [*members,*roles,formal]:bodies[ref['path']]=I.Body(ref,guard)
        db,expected=S.prepare(graph,bodies,members,roles,common,'full',guard)
        ctx=mp.get_context('spawn');barrier=ctx.Barrier(16);directory=graph/'worker_sources';directory.mkdir()
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=science.initialize,initargs=(plan,barrier,str(directory))) as pool:
            dispatch=Dispatch(pool,db,results,guard)
            try:scan=S.scan_formal(db,bodies[formal['path']],source,dispatch,guard)
            finally:dispatch.collect(True)
        Census.require_same_membership(expected,scan['all_common_observed_census'])
        I.need(db.execute('SELECT count(*) FROM selected s LEFT JOIN results r USING(mid) WHERE r.mid IS NULL').fetchone()[0]==0
          and db.execute('SELECT count(*) FROM results r LEFT JOIN selected s USING(mid) WHERE s.mid IS NULL').fetchone()[0]==0,'ALL_SELECTED_SOURCE_RESULTS_CONSERVED')
        n=db.execute('SELECT count(*) FROM results').fetchone()[0]
        holds=db.execute("SELECT count(*) FROM results WHERE status<>'UNIQUE_GRAPH_PROJECTION_CANDIDATE'").fetchone()[0]
        I.need(n==scan['selected_MIDs']==1196122 and len(dispatch.pids)==16,'FULL_COMMON_AND16_ACTUAL_WORKERS')
        worker_refs=[]
        for pid in dispatch.pids:
            ref=I.pin(directory/('worker_%s.json'%pid));value=I.read(ref)
            I.need(str(value['worker_pid'])==pid and value['uid']==1264 and value['job_id']==str(os_job()),'HONEST_ALPHA_WORKER_SOURCE_PROOF')
            worker_refs.append(ref)
        source.close();results.close()
        projection=I.Writer(graph/'strict5_projection.DATA.jsonl',guard)
        try:
            for mid,raw in db.execute('SELECT mid,strict5 FROM results WHERE strict5 IS NOT NULL ORDER BY mid'):projection.write(json.loads(raw))
        finally:projection.close()
        # Match the existing standalone producer: retain a feature row only
        # after the original reducer proves all molecular feature values equal.
        features=I.Writer(graph/'structural_features.DATA.jsonl',guard);pending=None;pending_mid=None
        try:
            with results.path.open() as stream:
                for line in stream:
                    guard.check();event=json.loads(line);phase=event['phase'];mid=event['molecule_id']
                    if phase=='GRAPH_RESULT':
                        if pending_mid!=mid:pending=None;pending_mid=mid
                        if pending is None and event.get('status')=='FEATURES_DERIVED':pending=event['features']
                    elif phase=='MID_REDUCTION':
                        if event['status']=='UNIQUE_GRAPH_PROJECTION_CANDIDATE':
                            I.need(pending_mid==mid and pending is not None and pending['full_key']==event['strict5_projection']['full_key'],'UNIQUE_ORIGINAL_REDUCTION_BINDS_COMPLETE_FEATURE_ROW')
                            features.write(dict(pending,molecule_id=mid,effective_role=event['effective_role'],native_records=event['native_records']))
                        pending=None;pending_mid=None
        finally:features.close()
        I.need(features.rows==projection.rows,'FEATURE_AND_STRICT5_ROW_CENSUS')
        def member(mid):
            value=db.execute('SELECT role,n FROM members m JOIN selected s USING(mid) WHERE m.mid=?',(mid,)).fetchone()
            I.need(value is not None,'READBACK_NOT_OUTSIDE_COMMON');return value
        references=[source.reference(),results.reference(),projection.reference(),features.reference()];frames=[]
        for ref in references:
            body=I.Body(ref,guard)
            try:
                if ref['path']==str(projection.path):
                    parsed,observed=old_io.read_strict5_rows(body.stream,member)
                    I.need(parsed==projection.rows,'ACTUAL_INDEPENDENT_STRICT5_READBACK')
                    if holds==0:Census.require_same_membership(expected,observed)
                frames.append(dict(reference=ref,frame=list(body.frame)))
            finally:body.close()
        input_frames=[dict(destination_reference=body.reference,current_Alpha_frame=list(body.frame)) for body in bodies.values()]
        db.commit();db.close();db=None
        return dict(schema='ALPHA_FULL_COMMON_GRAPH_COMPONENT_V1',status='COMPLETE_PENDING_ALPHA_C0_AND_ROOT_ACCEPTANCE' if holds==0 else 'SOURCE_GRAPH_HOLD_NOT_A_SUBSET_REFERENCE',
          expected_all_common_census=expected,scan=scan,observed_projection_census=observed,HOLD_MIDs=holds,strict5_rows=projection.rows,
          projection=references[2],structural_features=references[3],source_journal=references[0],graph_results=references[1],
          input_current_SHA_frames=input_frames,all_output_journals_current_SHA_readback=frames,census_index=I.pin(graph/'census.sqlite',guard.check),
          worker_MID_counts=dict(dispatch.pids),worker_CPU_seconds=dict(dispatch.cpu),actual_worker_proofs=worker_refs,
          source_kind='v1_common_structure_projection',fingerprint_recipe='ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5',
          graph_selector='ORIGINAL_CREATOR_SMILES_STRIP_TEMPLATE_V1',original_multiple_graph_HOLD_semantics_unchanged=True,
          reference_is_not_55k_or_all_TRAIN_proxy=True,consumer_manifest_emitted=False,candidate_release_authorized=False)
    finally:
        source.close();results.close()
        if db is not None:db.close()
        for body in bodies.values():body.close()


def os_job():
    import os
    return os.environ['SLURM_JOB_ID']
