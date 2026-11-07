"""Original actual bytes -> new numerical keywords/args, same native coordinates."""
import copy,pathlib
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from . import contract as C
Q=C.Q


def targets(original_task,inputs,old_protocol,new_protocol,engine):
    import numpy as np
    before=original_task['original_task'];after=next(t for t in new_protocol['tasks'] if t['name']==before['name'])
    native,seed=T.bridge(original_task['case'],inputs,before,old_protocol,engine)
    rendered=engine.render_inputs(after,native,original_task['case']['row'],new_protocol)
    old=T.arrays(inputs,original_task['case']['symbols']);new=T.arrays(rendered,original_task['case']['symbols'])
    Q.need(old.tobytes()==new.tobytes(),'NUMERICAL_SETTINGS_MUST_NOT_CHANGE_ACTUAL_COORDINATE_BITS')
    if before['family']=='mopac':
        Q.need(rendered['input.xyz']==inputs['input.xyz'] and rendered['input.mop'].splitlines(keepends=True)[1:]==inputs['input.mop'].splitlines(keepends=True)[1:],
            'ONLY_MOPAC_KEYWORD_FIRST_LINE_CHANGED')
    else:Q.need(rendered==inputs,'XTB_INPUT_FILES_MUST_STAY_BYTE_IDENTICAL')
    Q.need(seed==original_task['seed'] and native['coords'].tolist()==original_task['native_coordinates_A'],'ORIGINAL_SEED_AND_RENDER_BRIDGE')
    return native,seed,after,rendered


def all_tasks(plan,source,prepared,cases,old_protocol,new_protocol,engine,out,store):
    from workflows.data_v1_final.pprime.causal15_geometry_readonly_v1.run import body
    result=[];evidence={};controls={}
    from common import read_staging
    for row in prepared['tasks']:
        old_qa=row['qa_id'];case=cases[old_qa];task=read_staging(body(row['task_reference'],1<<20))
        inputs={pathlib.Path(r['path']).name:body(r,C.O.INPUT_CAP) for r in row['target_input_references']}
        actual={pathlib.Path(r['path']).name:body(r,C.O.INPUT_CAP) for r in case['actual_input_references']};Q.need(actual==inputs,'OLD_ACTUAL_TARGET_BYTES_BINDING')
        native,seed,after,new_inputs=targets(task,inputs,old_protocol,new_protocol,engine);qa='strict-'+old_qa
        refs=[store.write(out/'prepared_targets'/qa/name,b) for name,b in sorted(new_inputs.items())]
        new=copy.deepcopy(task);new.update(qa_id=qa,original_qa_id=old_qa,original_task=after,target_input_references=refs,
            native_coordinates_A=native['coords'].tolist(),seed=seed,candidate_protocol_reference=plan['candidate_protocol_reference'],
            original_task_reference=row['task_reference'],original_prepared_reference=plan['original_prepared_reference'])
        task_ref=store.json(out/'prepared_tasks'/(qa+'.json'),new)
        result.append({'qa_id':qa,'original_qa_id':old_qa,'task_reference':task_ref})
        evidence[qa]=read_staging(body(row['original_evidence_reference'],C.O.RESULT_CAP))
        controls[qa]=read_staging(body(case['record_reference'],C.O.RESULT_CAP))
    Q.need(len(result)==15,'EXACT15_NEW_TASKS_NO_SUBSTITUTION');return result,evidence,controls
