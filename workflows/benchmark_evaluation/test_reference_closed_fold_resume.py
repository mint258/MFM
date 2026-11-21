"""Synthetic producer continuations: no closed model fit or statistic is repeated."""
import ast
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from .reference_closed_fold_resume import require_terminal_failure,collect_closed_folds,ResumeContext,prepare_resume_source

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
