"""Synthetic producer continuations: no closed model fit or statistic is repeated."""
import ast
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from .reference_closed_fold_resume import require_terminal_failure,collect_closed_folds,ResumeContext,prepare_resume_source,validate_resume_plan,validate_targeted_resume_plan,TARGETED_RESUME_SCHEMA,TARGETED_GPU_PYTHONS,validate_cpu_resume_plan,CPU_RESUME_SCHEMA

MODEL="C1-TabPFN-Pprime"
TASK="Absorption max (nm)"
def native(state="TIMEOUT",job=11):
    return "JobId=%s UserId=zixiao(1278) JobState=%s Restarts=0 RunTime=12:00:00 ExitCode=0:0"%(job,state)

def fixture_source():
    return """from pathlib import Path
SEED=20261025
binding_path=Path('C1_Pprime_reference_features/job_4537149/Pprime/Joung2020_cv_binding.json')
out=root/'reference_cv_models'/('job_'+str(new_job))
out.mkdir(parents=True,exist_ok=False)
def eligible(row):return row['retained']
def matrix(rows):return rows
def mean_reference_metrics(*args):return {'metric_status':'PENDING_CPU_STATISTICS'}
def fixed_population(*args):return []
def fit_predict(train,test,directory,tag):
    checkpoint=Path('tabpfn-v2-regressor.ckpt')
    estimator=TabPFNRegressor.create_default_for_version(ModelVersion.V2,device='cuda',model_path=str(checkpoint),random_state=SEED)
    fit_calls.append(tag)
    return None
results=[]
completed_fits=0
group='Joung2020'
task='Absorption max (nm)'
model_name='C1-TabPFN-Pprime'
taskdir=out/group/task
taskdir.mkdir(parents=True)
for repetition in range(5):
    for fold in range(5):
        for fit_population in ('retained',):
            fitdir=taskdir/('r%d_f%d_%s'%(repetition,fold,fit_population))
            fitdir.mkdir()
            fit_predict([],[],fitdir,(repetition,fold))
            (fitdir/'predictions.parquet').write_bytes(b'new native prediction fixture')
            metric=dict(dataset=group,task=task,model=model_name,repetition=repetition,fold=fold,fit_population=fit_population,evaluation_population='retained',seed=SEED,metric_status='PENDING_CPU_STATISTICS')
            record=dict(metric,results=[metric])
            (fitdir/'results.json').write_text(json.dumps(record))
            results.extend(record['results'])
            completed_fits+=1
report=dict(job=str(new_job),closed_fit_populations=completed_fits,results=results)
"""

class ClosedFoldResumeTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)/"owned"
        self.source=self.root/"reference_cv_models/job_11"
        self.source.mkdir(parents=True)
        self.new=self.root/"reference_cv_models/job_12"
    def closed(self,task=TASK,rep=0,fold=0):
        folder=self.source/"Joung2020"/task/("r%d_f%d_retained"%(rep,fold));folder.mkdir(parents=True,exist_ok=True)
        metric=dict(dataset="Joung2020",task=task,model=MODEL,repetition=rep,fold=fold,
            fit_population="retained",evaluation_population="retained",seed=20261025,
            metric_status="PENDING_CPU_STATISTICS",training_mean=42.125)
        record=dict(metric,results=[metric])
        (folder/"results.json").write_text(json.dumps(record))
        (folder/"predictions.parquet").write_bytes(b"opaque original producer bytes")
        return folder,record,"REFERENCE_CV_MODEL_FIT_CLOSED Joung2020 %s %s %d %d retained seconds 10.2"%(task,MODEL,rep,fold)
    def collect(self,text,tasks=None):
        return collect_closed_folds(self.source,native(),11,text,"Joung2020",MODEL,{TASK} if tasks is None else tasks)
    def context(self,rows,guard=lambda:None):
        return ResumeContext(self.root,11,12,rows,guard)
    def test_only_actual_owned_nonrequeued_terminal_failure_is_admitted(self):
        self.assertEqual(require_terminal_failure(native(),11)["JobState"],"TIMEOUT")
        for state in ("PENDING","RUNNING","COMPLETING","COMPLETED","CANCELLED"):
            with self.assertRaises(ValueError):require_terminal_failure(native(state),11)
        for raw in (native().replace("1278","999"),native().replace("Restarts=0","Restarts=1"),
                    native().replace("12:00:00","00:00:00"),native(job=13),"",native(job=0)):
            with self.assertRaises(ValueError):require_terminal_failure(raw,11)
    def test_collect_uses_only_producer_closure_and_never_opens_prediction_values(self):
        folder,record,line=self.closed()
        partial=self.source/"Joung2020"/TASK/"r0_f1_retained";partial.mkdir()
        (partial/"results.json").write_text("unfinished producer record")
        with patch.object(Path,"read_bytes",side_effect=AssertionError("numeric readback forbidden")):
            rows=self.collect(line)
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["record"],record)
        self.assertEqual(rows[0]["source_predictions"],str(folder/"predictions.parquet"))
    def test_duplicate_malformed_or_unknown_task_closures_are_not_replayed(self):
        _,_,line=self.closed()
        for text in (line+"\n"+line,"REFERENCE_CV_MODEL_FIT_CLOSED malformed",line.replace(TASK,"unregistered task")):
            with self.assertRaises(ValueError):self.collect(text)
    def test_missing_file_or_changed_original_identity_stops_before_continuation(self):
        folder,record,line=self.closed()
        (folder/"predictions.parquet").unlink()
        with self.assertRaises(ValueError):self.collect(line)
        (folder/"predictions.parquet").write_bytes(b"original")
        record["fold"]=1;(folder/"results.json").write_text(json.dumps(record))
        with self.assertRaises(ValueError):self.collect(line)
    def test_reuse_hardlinks_opaque_bytes_and_keeps_original_metadata(self):
        folder,record,line=self.closed()
        rows=self.collect(line);ctx=self.context(rows);self.new.mkdir()
        ctx.initialize(self.new);target=self.new/"Joung2020"/TASK/"r0_f0_retained";target.parent.mkdir(parents=True)
        result=ctx.reuse(target,"Joung2020",TASK,MODEL,0,0,"retained")
        self.assertEqual(result,record)
        self.assertEqual((target/"predictions.parquet").stat().st_ino,(folder/"predictions.parquet").stat().st_ino)
        self.assertEqual((target/"results.json").read_text(),(folder/"results.json").read_text())
        self.assertEqual(ctx.provenance()["reference_closed_fold_resume"]["reused_closed_folds"][0]["source_job"],11)
        with self.assertRaises(ValueError):ctx.reuse(target,"Joung2020",TASK,MODEL,0,0,"retained")
    def test_unclosed_fold_has_no_source_read_and_runs_normally(self):
        ctx=self.context([]);self.new.mkdir();ctx.initialize(self.new)
        self.assertIsNone(ctx.reuse(self.new/"Joung2020"/TASK/"r0_f1_retained","Joung2020",TASK,MODEL,0,1,"retained"))
        self.assertFalse((self.new/"Joung2020").exists())
    def test_capacity_guard_prevents_new_links_without_altering_old_files(self):
        folder,_,line=self.closed()
        def full():raise RuntimeError("actual target capacity insufficient")
        ctx=self.context(self.collect(line),full);self.new.mkdir();ctx.initialize(self.new)
        target=self.new/"Joung2020"/TASK/"r0_f0_retained";target.parent.mkdir(parents=True)
        with self.assertRaisesRegex(RuntimeError,"capacity"):ctx.reuse(target,"Joung2020",TASK,MODEL,0,0,"retained")
        self.assertFalse(target.exists());self.assertTrue((folder/"predictions.parquet").is_file())
    def test_new_native_directory_and_every_selected_origin_are_required(self):
        _,_,line=self.closed();ctx=self.context(self.collect(line))
        with self.assertRaises(ValueError):ctx.initialize(self.source)
        self.new.mkdir();ctx.initialize(self.new)
        with self.assertRaises(ValueError):ctx.provenance()
        with self.assertRaises(ValueError):ctx.reuse(self.root/"outside","Joung2020",TASK,MODEL,0,0,"retained")

    def test_original_scientific_functions_stay_identical_and_seed_binding_device_are_fixed(self):
        source=fixture_source();generated=prepare_resume_source(source,"Joung2020","Pprime")
        before={n.name:ast.dump(n) for n in ast.parse(source).body if isinstance(n,ast.FunctionDef)}
        after={n.name:ast.dump(n) for n in ast.parse(generated).body if isinstance(n,ast.FunctionDef)}
        self.assertEqual(before,after)
        for bad in (source.replace("SEED=20261025","SEED=20261026"),source.replace("device='cuda'","device='cpu'"),
                    source.replace("Pprime/Joung2020","Pprime/other_dataset")):
            with self.assertRaises(ValueError):prepare_resume_source(bad,"Joung2020","Pprime")
    def test_continuation_executes_only24_unclosed_fits_and_preserves_closed_rows(self):
        _,record,line=self.closed();ctx=self.context(self.collect(line))
        class ModelVersion:V2="original V2"
        class TabPFNRegressor:
            @classmethod
            def create_default_for_version(cls,*args,**kwargs):return object()
        namespace=dict(root=self.root,new_job=12,json=json,fit_calls=[],
            ModelVersion=ModelVersion,TabPFNRegressor=TabPFNRegressor,_reference_resume=ctx)
        program=prepare_resume_source(fixture_source(),"Joung2020","Pprime")
        exec(compile(program,"synthetic_original_model","exec"),namespace)
        self.assertEqual(len(namespace["fit_calls"]),24)
        self.assertNotIn((0,0),namespace["fit_calls"])
        self.assertEqual(namespace["report"]["closed_fit_populations"],25)
        self.assertEqual(namespace["results"][0],record["results"][0])
        self.assertTrue(namespace["report"]["reference_closed_fold_resume"]["closed_statistics_not_recomputed"])
    def test_original_unit_slashes_in_task_names_keep_the_same_nested_identity(self):
        task="log(e/mol-1 dm3 cm-1)";_,record,line=self.closed(task=task)
        ctx=self.context(self.collect(line,{task}));self.new.mkdir();ctx.initialize(self.new)
        target=self.new/"Joung2020"/task/"r0_f0_retained";target.parent.mkdir(parents=True)
        self.assertEqual(ctx.reuse(target,"Joung2020",task,MODEL,0,0,"retained"),record)
    def test_symlinked_prediction_and_ambiguous_source_loop_are_rejected(self):
        folder,_,line=self.closed();external=self.root/"external";external.write_bytes(b"foreign")
        (folder/"predictions.parquet").unlink();(folder/"predictions.parquet").symlink_to(external)
        with self.assertRaises(ValueError):self.collect(line)
        source=fixture_source().replace("fitdir.mkdir()","fitdir.mkdir()\n            fitdir.mkdir()")
        with self.assertRaises(ValueError):prepare_resume_source(source,"Joung2020","Pprime")
    def test_plan_cannot_run_live_sources_repair_TDC_or_invent_new_seed_or_extra_attempt(self):
        from .reference_closed_fold_resume import validate_resume_plan
        plan=dict(schema="REFERENCE_TERMINAL_FAILED_CLOSED_FOLD_RESUME_V1",source_job=4537812,
            new_native_job=99,repair_attempt=1,dataset="Joung2020",feature_group="Pprime",
            model_seed=20261025,benchmark_NFS_pool_bytes=40*1024**3,maximum_concurrent_GPU7_models=1,
            frozen_task_names=[TASK],source_native_record=native(job=4537812))
        self.assertEqual(validate_resume_plan(plan,99),4537812)
        for key,value in (("source_job",4537788),("repair_attempt",2),("model_seed",20261026),
                          ("benchmark_NFS_pool_bytes",68*1024**3),("maximum_concurrent_GPU7_models",2),
                          ("source_native_record",native("RUNNING",4537812)),("new_native_job",98)):
            bad=copy.deepcopy(plan);bad[key]=value
            with self.assertRaises(ValueError):validate_resume_plan(bad,99)

if __name__=="__main__":unittest.main()


class TargetedResumePlanTests(unittest.TestCase):
    def plan(self,node="compute-0-6",python="/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/gpu_cu118_job_4536985_step_24/tabpfn/bin/python"):
        return dict(schema=TARGETED_RESUME_SCHEMA,source_job=4537812,new_native_job=900001,
            repair_attempt=1,dataset="Joung2020",feature_group="Pprime",model_seed=20261025,
            benchmark_NFS_pool_bytes=40*1024**3,maximum_concurrent_reference_GPU_models=1,
            source_native_record=native(job=4537812),frozen_task_names=[TASK],
            target_node=node,gpu_uuid="GPU-9db54192-dd3f-3177-e56f-dcd161ff932c",gpu_python=python)
    def validate(self,plan,**changes):
        args=dict(actual_node=plan["target_node"],registered_python=plan["gpu_python"])
        args.update(changes)
        return validate_targeted_resume_plan(plan,900001,**args)
    def test_registered_targets_and_both_existing_environments_preserve_the_original_plan(self):
        for node in tuple("compute-0-"+str(index) for index in range(8))+("compute-0-20","compute-0-22"):
            for python in TARGETED_GPU_PYTHONS:
                plan=self.plan(node,python);before=copy.deepcopy(plan)
                old,target=self.validate(plan)
                self.assertEqual(old,4537812)
                self.assertEqual(target,dict(target_node=node,gpu_uuid=plan["gpu_uuid"],gpu_python=python))
                self.assertEqual(plan,before)
    def test_prohibited_or_unallocated_targets_are_rejected(self):
        for node in ("compute-0-21","compute-0-8","sonmi","202.38.252.202",None,[]):
            plan=self.plan();plan["target_node"]=node
            with self.assertRaises(ValueError):self.validate(plan)
        with self.assertRaises(ValueError):self.validate(self.plan(),actual_node="compute-0-7")
    def test_uuid_cannot_be_missing_partial_or_contain_shell_text(self):
        for value in (None,"","GPU-unknown","GPU-9db54192","GPU-9db54192-dd3f-3177-e56f-dcd161ff932c;exit"):
            plan=self.plan();plan["gpu_uuid"]=value
            with self.assertRaises(ValueError):self.validate(plan)
    def test_unapproved_or_mismatched_interpreters_are_rejected(self):
        for python in ("/usr/bin/python","/tmp/python","/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/gpu_cu118_job_4536985_step_24/tabpfn/bin/python;echo",None,[]):
            plan=self.plan();plan["gpu_python"]=python
            with self.assertRaises(ValueError):self.validate(plan)
        with self.assertRaises(ValueError):self.validate(self.plan(),registered_python="/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B1_20261119/environments/gpu_cu128_job_4537025_step_5/tabpfn/bin/python")
    def test_original_live_success_cancelled_or_requeued_sources_remain_ineligible(self):
        for state in ("RUNNING","PENDING","COMPLETING","COMPLETED","CANCELLED"):
            plan=self.plan();plan["source_native_record"]=native(state,job=4537812)
            with self.assertRaises(ValueError):self.validate(plan)
        plan=self.plan();plan["source_native_record"]=native(job=4537812).replace("Restarts=0","Restarts=1")
        with self.assertRaises(ValueError):self.validate(plan)
    def test_original_seed_scope_pool_attempt_and_frozen_tasks_cannot_expand(self):
        for key,value in (("model_seed",20261026),("source_job",4537694),("repair_attempt",2),
            ("feature_group","Pprime_plus_D"),("dataset","TDC_ADME"),("benchmark_NFS_pool_bytes",68*1024**3),
            ("maximum_concurrent_reference_GPU_models",2),("maximum_concurrent_reference_GPU_models",True),
            ("maximum_concurrent_reference_GPU_models","1"),("frozen_task_names",[])):
            plan=self.plan();plan[key]=value
            with self.assertRaises(ValueError):self.validate(plan)
    def test_original_gpu7_validator_cannot_silently_ignore_a_targeted_plan(self):
        with self.assertRaises(ValueError):validate_resume_plan(self.plan(),900001)
        plan=self.plan();plan["maximum_concurrent_GPU7_models"]=1
        with self.assertRaises(ValueError):self.validate(plan)
    def test_all_five_original_producers_keep_their_actual_dataset_identity(self):
        for job in (4537812,4537813,4537814,4537817,4537818):
            plan=self.plan();plan.update(source_job=job,source_native_record=native(job=job),
                dataset="C7H10O2" if job==4537818 else "Joung2020")
            self.assertEqual(self.validate(plan)[0],job)

class TargetedCPUResumeTests(unittest.TestCase):
    def plan(self,job=4537812):
        return dict(schema=CPU_RESUME_SCHEMA,source_job=job,new_native_job=9000001,repair_attempt=1,
            dataset="C7H10O2" if job==4537818 else "Joung2020",feature_group="Pprime",model_seed=20261025,
            benchmark_NFS_pool_bytes=40*1024**3,maximum_parallel_CPU_models=5,
            source_native_record=native(job=job),frozen_task_names=[TASK],target_node="compute-0-16",allocated_CPUs=32)
    def check(self,plan,**kwargs):
        return validate_cpu_resume_plan(plan,9000001,actual_node=kwargs.get("node","compute-0-16"),allocated_cpus=kwargs.get("cpus",32))
    def test_exact_original_failed_source_and_allocation_without_plan_mutation(self):
        plan=self.plan();before=copy.deepcopy(plan)
        self.assertEqual(self.check(plan),(4537812,dict(target_node="compute-0-16",allocated_CPUs=32)))
        self.assertEqual(plan,before)
        for job in (4537812,4537813,4537814,4537817,4537818):self.assertEqual(self.check(self.plan(job))[0],job)
    def test_only_eligible_actual_CPU_nodes(self):
        for node in ("compute-0-"+str(i) for i in range(8,20) if i not in (14,18)):
            plan=self.plan();plan["target_node"]=node;self.assertEqual(self.check(plan,node=node)[1]["target_node"],node)
        for node in ("compute-0-7","compute-0-14","compute-0-18","compute-0-20","compute-0-21","compute-0-22","sonmi","202.38.252.202"):
            plan=self.plan();plan["target_node"]=node
            with self.assertRaises(ValueError):self.check(plan,node=node)
        with self.assertRaises(ValueError):self.check(self.plan(),node="compute-0-13")
    def test_exact_demand_allocations_and_types(self):
        for cpus in (16,32):
            plan=self.plan();plan["allocated_CPUs"]=cpus;self.assertEqual(self.check(plan,cpus=cpus)[1]["allocated_CPUs"],cpus)
        for cpus in (True,2,8,64,"32",None):
            plan=self.plan();plan["allocated_CPUs"]=cpus
            with self.assertRaises(ValueError):self.check(plan,cpus=cpus)
        with self.assertRaises(ValueError):self.check(self.plan(),cpus=16)
        with self.assertRaises(ValueError):self.check(self.plan(),cpus="32")
    def test_live_success_cancelled_and_requeued_sources_are_never_replayed(self):
        for state in ("PENDING","RUNNING","COMPLETING","COMPLETED","CANCELLED"):
            plan=self.plan();plan["source_native_record"]=native(state=state,job=4537812)
            with self.assertRaises(ValueError):self.check(plan)
        plan=self.plan();plan["source_native_record"]=native(job=4537812).replace("Restarts=0","Restarts=1")
        with self.assertRaises(ValueError):self.check(plan)
    def test_original_seed_scope_attempt_pool_and_task_guards_unchanged(self):
        for key,value in (("source_job",4537694),("dataset","TDC_ADMET"),("feature_group","Pprime_plus_D"),
                          ("model_seed",20261026),("repair_attempt",2),("benchmark_NFS_pool_bytes",68*1024**3),
                          ("frozen_task_names",[]),("frozen_task_names",[TASK,TASK]),
                          ("maximum_parallel_CPU_models",8),("maximum_parallel_CPU_models",True)):
            plan=self.plan();plan[key]=value
            with self.assertRaises(ValueError):self.check(plan)
    def test_CPU_schema_cannot_claim_GPU_execution_or_bypass_legacy_guard(self):
        for key in ("maximum_concurrent_GPU7_models","maximum_concurrent_reference_GPU_models"):
            plan=self.plan();plan[key]=1
            with self.assertRaises(ValueError):self.check(plan)
        with self.assertRaises(ValueError):validate_resume_plan(self.plan(),9000001)
        with self.assertRaises(ValueError):self.check([])
    def test_CPU_resume_program_changes_only_device_after_closed_fold_control(self):
        from .reference_cpu_primary import prepare_reference_cpu_source
        gpu=prepare_resume_source(fixture_source(),"Joung2020","Pprime")
        cpu=prepare_reference_cpu_source(gpu,"Joung2020","Pprime")
        parsed=ast.parse(cpu)
        call=next(n for n in ast.walk(parsed) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute) and n.func.attr=="create_default_for_version")
        device=next(k for k in call.keywords if k.arg=="device")
        self.assertEqual(device.value.value,"cpu");device.value=ast.Constant(value="cuda")
        self.assertEqual(ast.dump(parsed),ast.dump(ast.parse(gpu)))
        self.assertIn("_reference_resume.reuse",cpu)
        self.assertIn("_reference_resume.provenance",cpu)


class ConditionalClosedFoldResumeTests(unittest.TestCase):
    def failure(self,job=4538341):
        pids={4538341:{"2628220":"ABSENT","2628221":"ABSENT"},4538342:{"4154093":"ABSENT","4154094":"ABSENT"}}[job]
        node={4538341:"compute-0-8",4538342:"compute-0-11"}[job]
        return dict(origin="NATIVE_SACCT_AND_LOCAL_PROC_EXIT_AUDIT",job=job,user="zixiao",uid=1278,
                    state="FAILED",exit_code="1:0",exit_proof=dict(
                        status="ORIGINAL_FAILED_SOURCE_USER_PROCESSES_ABSENT",source_job=job,node=node,
                        known_identity_status=pids,remaining_owned=[],unreadable_unassigned_UID1278=[],
                        reads_only_local_proc=True,signals_sent=False))

    def test_seed26_reuses_closed_bytes_without_refit_and_guards_only_missing_unit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);source=root/"reference_cv_models/job_4538341"
            folder=source/"Joung2020"/TASK/"r0_f0_retained";folder.mkdir(parents=True)
            metric=dict(dataset="Joung2020",task=TASK,model=MODEL,repetition=0,fold=0,
                        fit_population="retained",evaluation_population="retained",seed=20261026,
                        metric_status="PENDING_CPU_STATISTICS")
            record=dict(metric,results=[metric])
            (folder/"results.json").write_text(json.dumps(record))
            (folder/"predictions.parquet").write_bytes(b"opaque closed conditional prediction fixture")
            line="REFERENCE_CV_MODEL_FIT_CLOSED Joung2020 "+TASK+" "+MODEL+" 0 0 retained seconds 1.0"
            with patch.object(Path,"read_bytes",side_effect=AssertionError("no prediction readback")):
                rows=collect_closed_folds(source,self.failure(),4538341,line,"Joung2020",MODEL,{TASK},
                                          confirmation=True)
                calls=[];context=ResumeContext(root,4538341,9999991,rows,lambda:None,
                                               model_seed=20261026,unit_start_guard=lambda:calls.append("new"))
                out=root/"reference_cv_models/job_9999991";out.mkdir();context.initialize(out)
                target=out/"Joung2020"/TASK/"r0_f0_retained";target.parent.mkdir(parents=True)
                self.assertEqual(context.reuse(target,"Joung2020",TASK,MODEL,0,0,"retained"),record)
                self.assertEqual(calls,[])
                self.assertEqual((folder/"predictions.parquet").stat().st_ino,
                                 (target/"predictions.parquet").stat().st_ino)
                self.assertIsNone(context.reuse(target.with_name("r0_f1_retained"),
                                  "Joung2020",TASK,MODEL,0,1,"retained"))
                self.assertEqual(calls,["new"])
                self.assertEqual(context.provenance()["reference_closed_fold_resume"]["model_seed"],20261026)

    def test_live_or_unreaped_or_foreign_conditional_source_is_never_admitted(self):
        from .reference_closed_fold_resume import require_failed_confirmation_source
        good=self.failure()
        self.assertEqual(require_failed_confirmation_source(good,4538341),good)
        for field,value in [("state","RUNNING"),("uid",999),("exit_code","0:0"),("job",4538356)]:
            bad=copy.deepcopy(good);bad[field]=value
            with self.assertRaises(ValueError):require_failed_confirmation_source(bad,4538341)
        bad=copy.deepcopy(good);bad["exit_proof"]["remaining_owned"]=[{"pid":2628221}]
        with self.assertRaises(ValueError):require_failed_confirmation_source(bad,4538341)
        bad=copy.deepcopy(good);bad["exit_proof"]["known_identity_status"]["2628221"]="SAME_IDENTITY_PRESENT"
        with self.assertRaises(ValueError):require_failed_confirmation_source(bad,4538341)

    def test_conditional_AST_adapter_preserves_both_frozen_feature_groups_and_seed(self):
        declaration=dict(model_seed=20261026,split_and_statistics_seed=20261025,
                         reason="FINAL_SIGNIFICANT_IMPROVEMENT",
                         selected_original_tasks=[("Joung2020",TASK)],task_roster_reselection=False,
                         original_model_budget_unchanged=True,primary_fit_population_only=True)
        for feature in ("Pprime","Pprime_plus_D"):
            original=("MODEL_SEED=20261026\n__confirmation_declaration="+repr(declaration)+"\n"+
                      fixture_source().replace("Pprime/Joung2020",feature+"/Joung2020")
                      .replace("'C1-TabPFN-Pprime'","'C1-TabPFN-"+feature+"'")
                      .replace("random_state=SEED","random_state=MODEL_SEED").replace("seed=SEED","seed=MODEL_SEED"))
            prepared=prepare_resume_source(original,"Joung2020",feature,confirmation=True)
            before={n.name:ast.dump(n) for n in ast.parse(original).body if isinstance(n,ast.FunctionDef)}
            after={n.name:ast.dump(n) for n in ast.parse(prepared).body if isinstance(n,ast.FunctionDef)}
            self.assertEqual(before,after)
            self.assertIn("_reference_resume.reuse",prepared)
            self.assertIn("MODEL_SEED = 20261026",prepared)
            with self.assertRaises(ValueError):
                prepare_resume_source(original.replace("MODEL_SEED=20261026","MODEL_SEED=20261025"),
                                      "Joung2020",feature,confirmation=True)

