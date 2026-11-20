"""First fits for the newly user-approved single-site pKa appendix.

The closed B1 task screen is immutable. This supplement uses only the approved
catalogue projection, never rescans SMARTS, assigns microscopic labels, or
regenerates geometry/quantum fields.
"""
import argparse
import csv
import gc
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import numpy as np
from rdkit import Chem, DataStructs
from rdkit.Chem import Descriptors, rdFingerprintGenerator

DEFINITION = "AUTHOR_TABLE_S2_37_CATALOG_V1"
TARGET = "single_site_mechanism"
SEED = 20261025
ELEMENTS = (1,6,8,7,15,16,9,17)
HYBRIDS = (Chem.HybridizationType.S,Chem.HybridizationType.SP,Chem.HybridizationType.SP2,
           Chem.HybridizationType.SP3,Chem.HybridizationType.SP3D,Chem.HybridizationType.SP3D2)
KEY = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")

def validate_definition(manifest):
    a = manifest.get("user_definition_authority", {})
    if (manifest.get("status") != "ATOMIC_SINGLE_SITE_TARGETS_READY"
        or a.get("approved") is not True or a.get("definition_id") != DEFINITION
        or a.get("authority_kind") != "explicit_user_message_question_reply"
        or not a.get("question_item_id") or not a.get("user_reply")
        or a.get("proposal_job") != 4536942 or a.get("catalog_patterns") != 37
        or manifest.get("microscopic_experimental_records") != 0
        or manifest.get("predicted_microspecies_used_as_experimental") is not False
        or manifest.get("multi_site_microscopic_assignment") is not False):
        raise ValueError("The exact user-approved closed site definition is required")
    return a

def target_row(raw, domain):
    if (raw.get("definition_approved") is not True
        or raw.get("single_site_definition_id") != DEFINITION
        or raw.get("eligibility_status") != "APPROVED_SINGLE_SITE_ATOMIC_TARGET"
        or raw.get("experimental_macro_reused_under_single_site_definition") is not True
        or raw.get("experimental_microscopic_annotation") is not False
        or raw.get("microscopic_assignment_performed") is not False
        or raw.get("benchmark_role") not in {"TRAIN_POOL","EXTERNAL_BLIND"}
        or raw.get("endpoint") not in {"atomic_pKa_acid","atomic_pKa_base"}
        or not KEY.fullmatch(raw.get("full_InChIKey",""))):
        raise ValueError("Unapproved or microscopic atomic target cannot enter this supplement")
    for field in ("model_atom_index","source_atom_index"):
        if type(raw.get(field)) is not int or raw[field] < 0:
            raise ValueError("Original unambiguous atom indices are required")
    p = Chem.SmilesParserParams(); p.removeHs = False
    mol = Chem.MolFromSmiles(raw["model_smiles"],p)
    if mol is None or raw["model_atom_index"] >= mol.GetNumAtoms():
        raise ValueError("Approved model atom is outside its source graph")
    mapping = domain["model_atom_to_source"]
    if raw["model_atom_index"] >= len(mapping) or mapping[raw["model_atom_index"]] != raw["source_atom_index"]:
        raise ValueError("Original source/model atom correspondence changed")
    if not (domain["retained"] and domain["domain_eligible"]):
        raise ValueError("Approved proposal unexpectedly left the frozen B0 domain")
    y = raw["target_value"]
    if type(y) not in (float,int) or not math.isfinite(y):
        raise ValueError("Original finite F64 macro value is required")
    return dict(dataset="pKahub",task=TARGET,record_id=raw["record_id"],
        macro_record_id=raw["macro_record_id"],full_inchikey=raw["full_InChIKey"],
        model_smiles=raw["model_smiles"],original_mol_binary=mol.ToBinary(),
        model_atom_index=raw["model_atom_index"],source_atom_index=raw["source_atom_index"],
        geometry_dataset=raw["geometry_dataset"],geometry_record_id=raw["geometry_record_id"],
        official_split="train" if raw["benchmark_role"]=="TRAIN_POOL" else "test",
        retained=True,domain_eligible=True,y=y,source_endpoint=raw["endpoint"],
        source_challenge=raw.get("source_challenge"),challenge_compound_id=raw.get("challenge_compound_id"))

def validate_populations(rows):
    ids=[r["record_id"] for r in rows]
    if len(set(ids)) != len(ids): raise ValueError("Repeated approved endpoint identity")
    tr={r["full_inchikey"] for r in rows if r["official_split"]=="train"}
    te={r["full_inchikey"] for r in rows if r["official_split"]=="test"}
    if not tr or not te or tr & te:
        raise ValueError("Original complete-key external blind exclusion must remain intact")
    for r in rows:
        if r["official_split"]=="test":
            if r["source_challenge"] not in {"SAMPL6","SAMPL7"} or not r["challenge_compound_id"]:
                raise ValueError("An external compound must keep its challenge namespace")
    return len(tr),len(te)

def atom37(atom):
    z=atom.GetAtomicNum();v=atom.GetTotalValence();h=atom.GetHybridization()
    q=atom.GetFormalCharge();default=Chem.GetPeriodicTable().GetDefaultValence(z)
    return [float(z)]+[float(z==x) for x in ELEMENTS]+[float(v)]+[float(v==x) for x in range(1,7)]+[
        float(atom.GetIsAromatic())]+[float(h==x) for x in HYBRIDS]+[float(q==x) for x in (-1,0,1)]+[
        float(default==x) for x in range(1,7)]+[float(atom.IsInRingSize(x)) for x in range(3,8)]

def p_site_vector(atom_values, mapping, original_site):
    if atom_values is None: return None
    array=np.asarray(atom_values,dtype=np.float64)
    if array.ndim!=2 or len(array)!=len(mapping):raise ValueError("Native atom matrix and source mapping differ")
    positions=[i for i,x in enumerate(mapping) if x == original_site]
    if len(positions)!=1: raise ValueError("P-prime site must map to exactly one original atom")
    values=np.asarray(atom_values,dtype=np.float64)[positions[0]]
    return values.tolist() if np.isfinite(values).any() else None

def prediction_rows(rows, prediction, mean, model, seed=SEED, feature_group=None):
    if len(rows)!=len(prediction) or not np.isfinite(prediction).all():
        raise ValueError("Predictions must preserve the complete declared input population")
    answer=[]
    for r,p in zip(rows,prediction):
        out={k:r[k] for k in ("dataset","task","record_id","full_inchikey","retained","domain_eligible",
                              "model_atom_index","source_atom_index","macro_record_id")}
        out.update(evaluation_id=r["record_id"],y_true=r["y"],prediction=float(p),
            training_mean=mean,model=model,model_seed=seed,fit_population="retained",
            source_endpoint=r["source_endpoint"],source_challenge=r["source_challenge"],
            challenge_compound_id=r["challenge_compound_id"])
        if feature_group:out["feature_group"]=feature_group
        answer.append(out)
    return answer

def apply_to_c1(table, supplement):
    """Replace only the registered unresolved mechanism cell, without any score replay."""
    if (supplement.get("status")!="APPROVED_PKA_ATOMIC_SUPPLEMENT_CLOSED"
        or supplement.get("B1_task_screen_modified") is not False
        or supplement.get("predeclared_result_role")!="APPENDIX"
        or supplement.get("all_required_neural_confirmations_closed") is not True):
        raise ValueError("The approved atomic supplement has not closed")
    validate_definition(supplement["source_definition_manifest"])
    indices=[i for i,r in enumerate(table) if r.get("dataset")=="pKahub" and r.get("target")==TARGET]
    if len(indices)!=1:raise ValueError("Exactly one original registered atomic pKa cell is required")
    index=indices[0];old=table[index];new=supplement["C1_result"]
    fields=("endpoint_key","dataset","target","level","feature_group","learner","frozen_B1_role")
    if any(new.get(k)!=old.get(k) for k in fields) or old.get("frozen_B1_role")!="UNRESOLVED":
        raise ValueError("The supplement cannot change the frozen task roster or configuration")
    if new.get("task_roster_reselection") is not False:
        raise ValueError("Task reselection is prohibited")
    result=[dict(r) for r in table];result[index]=dict(old,**new)
    return result

def prepare(entry_path, out, safe):
    import pyarrow.parquet as pq
    import pyarrow as pa
    from workflows.benchmark_data.shared_reader import SharedB0Reader
    from workflows.benchmark_data.pprime_reader import PprimeReader
    from workflows.benchmark_data.shared_access import check_access
    from workflows.benchmark_evaluation.pprime_features import NativePprimeLayout,first_actual_conformer,append_unmapped_native_hydrogens
    from workflows.data_v1_final.labels.common import MISSING
    entry=json.loads(Path(entry_path).read_text());root=Path(entry["data_root"])
    handoff_path=Path(entry["both_scopes_final_handoff"]["manifest"])
    handoff=json.loads(handoff_path.read_text())
    if handoff.get("all_scopes_production_closed") is not True:
        raise ValueError("Both original B0 source scopes must be sealed")
    source=Path(handoff["active_target_manifests"]["pKahub_atomic"])
    definition=json.loads(source.read_text());validate_definition(definition)
    macro=json.loads(Path(definition["source_macro_manifest"]).read_text())
    domain=json.loads(Path(macro["source_domain_manifest"]).read_text())
    targets=[]
    for key in ("training_targets","blind_targets"):
        targets.extend(pq.read_table(definition[key]).to_pylist())
    wanted={r["geometry_record_id"] for r in targets};domains={}
    columns=["record_id","retained","domain_eligible","model_atom_to_source"]
    for batch in pq.ParquetFile(domain["records"]).iter_batches(batch_size=2048,columns=columns):
        for row in batch.to_pylist():
            if row["record_id"] in wanted:domains[row["record_id"]]=row
    if set(domains)!=wanted:raise ValueError("An approved target has no original B0 domain/mapping record")
    rows=[target_row(r,domains[r["geometry_record_id"]]) for r in targets]
    validate_populations(rows)
    protocol=dict(definition_id=DEFINITION,result_role="APPENDIX",
        frozen_B1_roster_unchanged=True,model_seed=SEED,statistics_seed=SEED,
        RF="Atom-centered ECFP4 radius2/2048bits; sklearn default100trees",
        LightGBM="Original RDKit2D descriptors plus original37 atom features; defaults",
        Chemprop="Official2.2.2 MolAtomBondMPNN; atom-only MABBondMessagePassing;50epochs,batch64,300hidden,depth3",
        C1="Original pretraining atomic Pprime fields plus original37 atom features; LightGBM only",
        extra_neural_seed="20261026 only for significant improvement versus the strongest traditional control in this final appendix",
        split="Frozen B0 TRAIN_POOL versus SAMPL6/SAMPL7 EXTERNAL_BLIND; complete InChIKey exclusion",
        target="Approved original F64 macro value at the unique catalogue-defined source site; experimental micro0",
        no_SMARTS_rescan=True,no_geometry_or_quantum_generation=True,no_TEST_selection=True)
    safe();out.mkdir(parents=True,exist_ok=False)
    (out/"protocol_before_fitting.json").write_text(json.dumps(protocol,indent=2)+"\n")
    safe();(out/"tmp").mkdir();os.environ["TMPDIR"]=str(out/"tmp")
    schema=json.loads(Path("/lfshome/zixiao/data_v1_20261025/D3_v31_pilot_20261105_v1/schema.json").read_text())
    wp=Path("/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts/wp5_parquet_v2.py")
    spec=importlib.util.spec_from_file_location("_original_pka_wp5_wire",wp)
    wire=importlib.util.module_from_spec(spec);spec.loader.exec_module(wire)
    def lookup(detail,path):
        value=wire.lookup(detail,path)
        return MISSING if value is wire.MISSING else wire.native(value)
    layout=NativePprimeLayout(schema,lookup)
    queues=(root/"geometry/shared_v1/queue.sqlite",root/"labels/Pprime/shared_v1/queue.sqlite")
    for queue in queues:
        access=check_access(queue)
        if not access or not access.get("immutable") or not access.get("cross_node_read_allowed"):
            raise ValueError("Shared Pprime/geometry must be sealed before atom consumption")
    generator=rdFingerprintGenerator.GetMorganGenerator(radius=2,fpSize=2048,includeChirality=False)
    descriptors=list(Descriptors._descList)
    with SharedB0Reader(queues[0]) as geometry,PprimeReader(queues[1]) as quantum:
        for i,row in enumerate(rows):
            if i%128==0:safe()
            mol=Chem.Mol(row["original_mol_binary"]);mol.UpdatePropertyCache(strict=False);Chem.GetSymmSSSR(mol)
            atom=row["model_atom_index"];a=atom37(mol.GetAtomWithIdx(atom))
            row["rdkit_atom37"]=a
            row["ecfp4_2048_packed"]=DataStructs.BitVectToBinaryText(generator.GetFingerprint(mol,fromAtoms=[atom]))
            values=[]
            for _,function in descriptors:
                try:v=float(function(mol))
                except Exception:v=float("nan")
                values.append(v if math.isfinite(v) else float("nan"))
            row["rdkit_2d_atom37"]=values+a
            native=geometry.get(row["geometry_dataset"],row["geometry_record_id"])
            cid=first_actual_conformer(native);vector=None;state=native["state"]
            if cid is not None:
                q=quantum.get(native["shared_molecule_id"],cid);state=q["state"]
                _,atomic,_=layout.extract(q,len(native["result"]["atomic_numbers"]))
                mapping=append_unmapped_native_hydrogens(native["model_atom_to_source"],native["result"]["atomic_numbers"])
                vector=p_site_vector(atomic,mapping,row["source_atom_index"])
            row["Pprime_atom"]=vector;row["Pprime_state"]=state
            row["c1_features"]=None if vector is None else vector+a
    path=out/"approved_atomic_features.parquet";safe()
    pq.write_table(pa.Table.from_pylist(rows),path,compression="zstd")
    return rows,dict(source_entry=str(Path(entry_path).resolve()),sealed_B0_manifest=str(handoff_path),
        approved_target_manifest=str(source),source_definition_manifest=definition,
        protocol=protocol,feature_cache=str(path),atom_P_fields=[c["field_key"] for c in layout.atom],
        rdkit_2d_fields=[name for name,_ in descriptors],source_counts=definition["source_site_counts"])

def atom_target_array(row):
    mol=Chem.Mol(row["original_mol_binary"])
    mol.UpdatePropertyCache(strict=False);Chem.GetSymmSSSR(mol)
    values=np.full((mol.GetNumAtoms(),1),np.nan,dtype=float)
    values[row["model_atom_index"],0]=row["y"]
    return mol,values

def cpu_guard(root, quota, needed=2*1024**3):
    from workflows.benchmark_data.admission import protect
    protect(Path(root),needed,Path(quota),own_concurrent_bytes=40*1024**3)

def run_chemprop(features,out,seed,root,quota):
    import pyarrow.parquet as pq
    import torch
    import importlib.metadata
    if importlib.metadata.version("chemprop")!="2.2.2":raise ValueError("Registered Chemprop2.2.2 is required")
    from lightning import pytorch as pl
    from lightning.pytorch.callbacks import Callback,ModelCheckpoint
    from chemprop import data,nn,models
    from chemprop.nn.message_passing.mol_atom_bond import MABBondMessagePassing
    torch.set_num_threads(4);torch.set_num_interop_threads(1)
    rows=pq.read_table(features).to_pylist()
    train=[r for r in rows if r["official_split"]=="train"];test=[r for r in rows if r["official_split"]=="test"]
    def point(r):
        mol,y=atom_target_array(r)
        return data.MolAtomBondDatapoint(mol=mol,atom_y=y,name=r["record_id"])
    pl.seed_everything(seed,workers=True,verbose=False)
    training=data.MolAtomBondDataset([point(r) for r in train]);testing=data.MolAtomBondDataset([point(r) for r in test])
    training.cache=True;testing.cache=True
    scaler=training.normalize_targets(key="atom")
    model=models.MolAtomBondMPNN(MABBondMessagePassing(return_edge_embeddings=False),
        atom_predictor=nn.RegressionFFN(output_transform=nn.UnscaleTransform.from_standard_scaler(scaler)))
    loader=data.build_dataloader(training,batch_size=64,num_workers=0,seed=seed,shuffle=True)
    testing_loader=data.build_dataloader(testing,batch_size=64,num_workers=0,shuffle=False,drop_last=False)
    out=Path(out);cpu_guard(root,quota);out.mkdir(parents=True,exist_ok=False)
    class Guard(Callback):
        def on_train_epoch_start(self,trainer,module):cpu_guard(root,quota)
        def on_train_epoch_end(self,trainer,module):
            print("APPROVED_PKA_CHEMPROP_EPOCH",seed,trainer.current_epoch+1,flush=True)
    checkpoint=ModelCheckpoint(dirpath=out,save_last=True,save_top_k=0,every_n_epochs=1,enable_version_counter=False)
    trainer=pl.Trainer(accelerator="cpu",devices=1,max_epochs=50,logger=False,
        enable_checkpointing=True,callbacks=[Guard(),checkpoint],enable_progress_bar=False,
        enable_model_summary=False,num_sanity_val_steps=0,limit_val_batches=0,default_root_dir=out,
        log_every_n_steps=50,precision="32-true")
    trainer.fit(model,loader)
    with torch.inference_mode():
        values=torch.cat([batch[1] for batch in trainer.predict(model,testing_loader)],dim=0).reshape(-1).cpu().numpy().astype(float)
    positions=[];offset=0
    for r in test:
        positions.append(offset+r["model_atom_index"]);offset+=Chem.Mol(r["original_mol_binary"]).GetNumAtoms()
    if len(values)!=offset:raise ValueError("Atom head lost the original source graph layout")
    prediction=values[np.asarray(positions,dtype=int)]
    if not np.isfinite(prediction).all():raise ValueError("Nonfinite primary atomic predictions")
    cpu_guard(root,quota);np.save(out/"predictions.npy",prediction)
    (out/"manifest.json").write_text(json.dumps(dict(status="APPROVED_PKA_CHEMPROP_FIT_CLOSED",
        seed=seed,epochs=50,batch_size=64,TRAIN_rows=len(train),TEST_rows=len(test),
        TRAIN_mean=float(np.mean([r["y"] for r in train])),model="Chemprop-v2",
        original_atom_targets_only=True,TEST_used_for_model_selection=False),indent=2)+"\n")

def run(entry_path,out,program_path,safe):
    import pyarrow as pa
    import pyarrow.parquet as pq
    from sklearn.ensemble import RandomForestRegressor
    from lightgbm import LGBMRegressor
    from workflows.benchmark_evaluation.c1_reporting import single_model_statistics,native_population
    from workflows.benchmark_evaluation.comparisons import paired_improvement,needs_second_seed
    rows,source=prepare(entry_path,Path(out),safe);out=Path(out)
    entry=json.loads(Path(entry_path).read_text());root=Path(entry["data_root"]);b1=root.parent/"benchmark_B1_20261119"
    quota=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/benchmark_B0_quota_20261119.json")
    proof=json.loads((b1/"endpoint_catalog/job_4536889/manifest.json").read_text())
    if proof.get("deferred_registry_full_inventory_verified") is not True or proof.get("deferred_endpoint_count")!=5:
        raise ValueError("The original complete five-deferred-endpoint proof is required")
    with (b1/"endpoint_catalog/job_4536889/candidate_endpoints.csv").open() as stream:catalog=list(csv.DictReader(stream))
    candidates=[r for r in catalog if r["dataset"]=="pKahub" and r["target"]==TARGET]
    if len(candidates)!=1:raise ValueError("The approved mechanism must remain the one existing endpoint")
    endpoint=candidates[0]["endpoint_key"]
    screen_paths=list((b1/"B1_task_screen").glob("job_*/B1_task_screen.csv"))
    if len(screen_paths)!=1:raise ValueError("The one frozen B1 roster is required")
    with screen_paths[0].open() as stream:screen=list(csv.DictReader(stream))
    role=next(r for r in screen if r["endpoint_key"]==endpoint)
    if role["decision"]!="UNRESOLVED":raise ValueError("This supplement cannot reinterpret a scored B1 task")
    train=[r for r in rows if r["official_split"]=="train"];test=[r for r in rows if r["official_split"]=="test"]
    baseline={};metrics=[];contrasts=[];fit_metadata=[]
    for name in ("RF-ECFP4","LightGBM-RDKit2D"):
        safe()
        if name=="RF-ECFP4":
            matrix=lambda pop:np.asarray([np.unpackbits(np.frombuffer(r["ecfp4_2048_packed"],dtype=np.uint8),bitorder="little") for r in pop],dtype=np.uint8)
            model=RandomForestRegressor(random_state=SEED,n_jobs=4)
        else:
            matrix=lambda pop:np.asarray([r["rdkit_2d_atom37"] for r in pop],dtype=np.float64)
            model=LGBMRegressor(random_state=SEED,n_jobs=4,verbosity=-1)
        y=np.asarray([r["y"] for r in train],dtype=np.float64);mean=float(y.mean())
        model.fit(matrix(train),y);prediction=np.asarray(model.predict(matrix(test)),dtype=float)
        baseline[name]=prediction_rows(test,prediction,mean,name)
        fit_metadata.append(dict(model=name,seed=SEED,TRAIN_rows=len(train),TEST_rows=len(test),parameters=model.get_params()))
        print("APPROVED_PKA_ATOMIC_MODEL_CLOSED",name,len(train),len(test),flush=True)
        del model;gc.collect()
    python=b1/"environments/gpu_cu118_job_4536985_step_24/chemprop/bin/python"
    def chemprop(seed):
        folder=out/("Chemprop_seed"+str(seed))
        safe()
        subprocess.run([str(python),"-B",str(program_path),"--chemprop","--features",source["feature_cache"],
            "--out",str(folder),"--seed",str(seed),"--root",str(root),"--quota",str(quota)],check=True)
        meta=json.loads((folder/"manifest.json").read_text());prediction=np.load(folder/"predictions.npy")
        if meta["seed"]!=seed or meta["epochs"]!=50 or meta["batch_size"]!=64:
            raise ValueError("Chemprop scientific budget changed")
        fit_metadata.append(meta)
        return prediction_rows(test,prediction,meta["TRAIN_mean"],"Chemprop-v2",seed)
    baseline["Chemprop-v2"]=chemprop(SEED)
    for name,predictions in baseline.items():
        score=single_model_statistics(predictions)
        metrics.append(dict(dataset="pKahub",task=TARGET,model=name,model_seed=SEED,result_role="APPENDIX",
            definition_id=DEFINITION,n_train=len(train),training_mean=predictions[0]["training_mean"],
            **{k:v for k,v in score.items() if k!="status"}))
        safe();pq.write_table(pa.Table.from_pylist(predictions),out/(name+"_predictions.parquet"),compression="zstd")
    controls=[r for r in metrics if r["model"]!="Chemprop-v2"];reference=min(controls,key=lambda r:r["RAE"])["model"]
    comparison=paired_improvement(baseline[reference],baseline["Chemprop-v2"])
    contrasts.append(dict(task=TARGET,candidate="Chemprop-v2",candidate_seed=SEED,reference=reference,**comparison))
    required=needs_second_seed(learner="Chemprop-v2",final_role="APPENDIX",significant_improvement=comparison["significant_improvement"])
    if required:
        confirmed=chemprop(SEED+1);score=single_model_statistics(confirmed)
        metrics.append(dict(dataset="pKahub",task=TARGET,model="Chemprop-v2",model_seed=SEED+1,
            result_role="APPENDIX",definition_id=DEFINITION,n_train=len(train),training_mean=confirmed[0]["training_mean"],
            **{k:v for k,v in score.items() if k!="status"}))
        contrasts.append(dict(task=TARGET,candidate="Chemprop-v2",candidate_seed=SEED+1,reference=reference,
                              **paired_improvement(baseline[reference],confirmed)))
        safe();pq.write_table(pa.Table.from_pylist(confirmed),out/"Chemprop-v2_seed20261026_predictions.parquet",compression="zstd")
    native_train=[r for r in train if r["c1_features"] is not None]
    native_test=[r for r in test if r["c1_features"] is not None]
    c1=dict(endpoint_key=endpoint,dataset="pKahub",target=TARGET,level="atom",
        feature_group="Pprime_plus_RDKit_atom",learner="LightGBM",model_seed=SEED,
        completed_seeds=1,frozen_B1_role="UNRESOLVED",post_freeze_definition_role="APPENDIX",
        task_roster_reselection=False,geometry="Shared Sprime UFF",definition_id=DEFINITION,
        target_definition="User-approved author37 catalogue; original macro value; experimental microscopic0",
        report_stage="FINAL_APPROVED_SINGLE_SITE_SUPPLEMENT",approved_source_manifest=source["approved_target_manifest"])
    if native_train and native_test:
        safe();model=LGBMRegressor(random_state=SEED,n_jobs=4,verbosity=-1)
        y=np.asarray([r["y"] for r in native_train],float);mean=float(y.mean())
        model.fit(np.asarray([r["c1_features"] for r in native_train],float),y)
        p=np.asarray(model.predict(np.asarray([r["c1_features"] for r in native_test],float)),float)
        records=prediction_rows(native_test,p,mean,"LightGBM",SEED,"Pprime_plus_RDKit_atom")
        available,coverage=native_population(baseline["LightGBM-RDKit2D"],records)
        score=single_model_statistics(available)
        c1.update(coverage,**{k:v for k,v in score.items() if k!="status"},
            status="FINAL_APPROVED_SINGLE_SITE_APPENDIX",actual_TRAIN_rows=len(native_train),
            input_feature_count=len(native_train[0]["c1_features"]),statistics_source="FIRST_ATOMIC_SUPPLEMENT_PRODUCER")
        contrasts.append(dict(task=TARGET,candidate="Pprime_plus_RDKit_atom_LightGBM",candidate_seed=SEED,
            reference="LightGBM-RDKit2D",**paired_improvement(baseline["LightGBM-RDKit2D"],records,allow_native_missing=True)))
        safe();pq.write_table(pa.Table.from_pylist(records),out/"C1_LightGBM_predictions.parquet",compression="zstd")
        metrics.append(dict(dataset="pKahub",task=TARGET,model="C1_Pprime_plus_RDKit_atom_LightGBM",
            model_seed=SEED,result_role="APPENDIX",definition_id=DEFINITION,n_train=len(native_train),
            training_mean=mean,**{k:v for k,v in score.items() if k!="status"}))
    else:
        c1.update(status="UNRESOLVED_NATIVE_PPRIME_POPULATION",completed_seeds=0,
            reason="Closed original Pprime unavailable at approved atoms; no imputation",
            original_primary_TEST_rows=len(test),available_TEST_rows=len(native_test),actual_TRAIN_rows=len(native_train))
    def csv_file(name,records):
        fields=list(dict.fromkeys(k for r in records for k in r))
        safe()
        with (out/name).open("x",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=fields,lineterminator="\n");writer.writeheader();writer.writerows(records)
    csv_file("pKa_atomic_approved_baselines.csv",metrics)
    csv_file("pKa_atomic_approved_comparisons.csv",contrasts)
    report=dict(status="APPROVED_PKA_ATOMIC_SUPPLEMENT_CLOSED",job=os.environ["SLURM_JOB_ID"],
        **source,predeclared_result_role="APPENDIX",frozen_B1_roster=str(screen_paths[0]),
        B1_task_screen_modified=False,all_required_neural_confirmations_closed=True,
        conditional_Chemprop_seed2_required=bool(required),C1_result=c1,
        fits=fit_metadata,baseline_models=["RF-ECFP4","LightGBM-RDKit2D","Chemprop-v2"],
        TRAIN_rows=len(train),TEST_rows=len(test),native_Pprime_TRAIN_rows=len(native_train),
        native_Pprime_TEST_rows=len(native_test),micro_experimental_records=0,
        no_task_reselection=True,no_new_geometry_or_quantum=True,
        filter_impact=dict(full_and_retained_are_same_approved_domain_population=True,excluded_rows=0,
            full_predictions_reuse_exact_same_fit=True,no_duplicate_fit_or_statistics=True),
        standalone_existing_scores_recomputed=False,independent_numeric_QA=False)
    safe();(out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    print("APPROVED_PKA_ATOMIC_SUPPLEMENT_CLOSED",out/"manifest.json","C1",c1["status"],"conditional_seed2",required,flush=True)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--chemprop",action="store_true")
    p.add_argument("--features");p.add_argument("--out",required=True);p.add_argument("--seed",type=int,default=SEED)
    p.add_argument("--root");p.add_argument("--quota");a=p.parse_args()
    if not a.chemprop:raise ValueError("Use the registered guarded production entry")
    run_chemprop(a.features,a.out,a.seed,a.root,a.quota)
