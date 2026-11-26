"""Produce the registered shared UFF cohort once, reusing the closed key join."""
from cpu_ssh_runtime import execution_handle
import argparse, csv, fcntl, io, json, os, sys, time
from collections import Counter
from pathlib import Path
from a5_contracts import require_runtime_configuration, open_native_store
from finetune_entry import CooperativeStop, set_actual_deadline
from finetune_statistics_entry import require_cpu_admission, atomic_json

def run(c):
    require_runtime_configuration(c)
    if c.get("ready") is not True:
        raise ValueError("Activated registered A5 producer required")
    with CooperativeStop() as stop:
        set_actual_deadline(c, stop); require_cpu_admission(c)
        import numpy as np
        from rdkit import Chem, rdBase
        from phychem_mfm.phase1.v3_dev_membership import GroupedTrainingView
        if rdBase.rdkitVersion != "2025.09.5":
            raise ValueError("Frozen source parser version changed")
        sys.path.insert(0, c["sealed_reader_worktree"])
        from workflows.benchmark_data.shared_reader import SharedB0Reader
        out=Path(c["output"]); out.mkdir(parents=True,exist_ok=True)
        with (out/"owner.lock").open("a") as lock:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            if (out/"primary_complete.json").exists():
                raise ValueError("Closed A5 cohort must be reused")
            catalogue=json.loads(Path(c["closed_matches"]).read_text())
            if catalogue["status"]!="TARGET_OPAQUE_FULL_KEY_JOIN":
                raise ValueError("Original completed key catalogue required")
            store=open_native_store(c["native_store"])
            view=GroupedTrainingView(store,"expansionrx","official",store.group_map)
            selection=json.loads(Path(c["original_selection"]).read_text())["selection"]["records"]["expansionrx"]
            original={r["member_index"]:r for r in selection}
            members=[(i,role) for role in ("train","train_inner_validation") for i in view.view(role)]
            identity=dict(closed_matches=c["closed_matches"],native_store=c["native_store"],
                          original_membership_sha256=view.membership_sha256,
                          sealed_queue=c["sealed_queue"],authority=c["authority"])
            progress=out/"cohort_cursor.json"
            state=json.loads(progress.read_text()) if progress.exists() else dict(
                identity=identity,cursor=0,rows=[],excluded=[],atom_alignment_producer_only=True)
            if state["identity"]!=identity or len(state["rows"])+len(state["excluded"])!=state["cursor"]:
                raise ValueError("A5 saved producer cursor identity differs")
            parser=Chem.SmilesParserParams();parser.removeHs=False
            last_guard=0.;handles={}
            def boundary():
                nonlocal last_guard
                now=time.time()
                if stop.requested or now+c["work_unit_seconds"]>=float(os.environ["P_MANAGED_STOP_NEW_UNITS_AT"]):
                    atomic_json(progress,state);return True
                if time.monotonic()-last_guard>=10:
                    require_cpu_admission(c);last_guard=time.monotonic()
                return False
            try:
                with SharedB0Reader(c["sealed_queue"]) as reader:
                    for cursor in range(state["cursor"],len(members)):
                        if boundary():return 75
                        index,role=members[cursor];record=original[index]
                        sample=view.get(index,role=role)
                        reason=None;accepted=None
                        if not sample.geometry_ready:reason="original_geometry_unavailable"
                        rows=catalogue["matches"].get(record["full_inchikey"],[])
                        if reason is None and not rows:reason="no_sealed_full_key_match"
                        if reason is None:
                            frame=record["original_member"]["source_frame"]
                            source_path=frame["source_file"]["path"]
                            if source_path not in handles:handles[source_path]=open(source_path,"rb")
                            stream=handles[source_path];start,end=frame["smiles_physical_span"]
                            stream.seek(start);field=stream.read(end-start).decode("utf-8")
                            original_smiles=next(csv.reader(io.StringIO(field),strict=True))[0]
                            native_mol=Chem.MolFromSmiles(original_smiles,parser)
                            native_z=(sample.x+1).tolist()
                            if native_mol is None:reason="native_source_graph_unavailable"
                            elif [a.GetAtomicNum() for a in native_mol.GetAtoms()]!=native_z:
                                reason="native_source_element_sequence_mismatch"
                            else:
                                charge=sum(a.GetFormalCharge() for a in native_mol.GetAtoms())
                                failures=[]
                                for row in rows:
                                    item=reader.get(row["dataset"],row["record_id"]);res=item.get("result") or {}
                                    confs=res.get("conformers") or []
                                    if not confs:failures.append("no_sealed_UFF_geometry");continue
                                    template=Chem.MolFromSmiles(res.get("model_smiles",""),parser)
                                    if template is None:failures.append("UFF_source_graph_unavailable");continue
                                    if sum(a.GetFormalCharge() for a in template.GetAtoms())!=charge:
                                        failures.append("total_charge_mismatch");continue
                                    source_map=item["model_atom_to_source"]
                                    template_map=res.get("model_atom_to_template",[])
                                    pairs={}
                                    for uff_atom,t in enumerate(template_map):
                                        if t>=0 and t<len(source_map):
                                            source_atom=source_map[t]
                                            if source_atom in pairs:raise ValueError("Duplicate sealed source atom mapping")
                                            pairs[source_atom]=uff_atom
                                    if set(pairs)!=set(range(len(native_z))):
                                        failures.append("native_atom_count_or_source_map_mismatch");continue
                                    order=[pairs[i] for i in range(len(native_z))]
                                    z=res.get("atomic_numbers",[])
                                    if len(z)!=len(template_map) or [z[i] for i in order]!=native_z:
                                        failures.append("element_sequence_mismatch");continue
                                    conf=confs[0]
                                    xyz=np.asarray(conf["coordinates_A"],dtype=np.float64)
                                    if xyz.shape!=(len(z),3) or not np.isfinite(xyz).all():
                                        failures.append("invalid_sealed_UFF_coordinates");continue
                                    accepted=dict(member_index=index,member_uid=sample.member_uid,role=role,
                                        full_inchikey=record["full_inchikey"],atomic_numbers=native_z,total_charge=charge,
                                        coordinates_A=xyz[order].tolist(),UFF_atom_indices_in_native_order=order,
                                        sealed_source=dict(dataset=row["dataset"],record_id=row["record_id"],
                                            shared_molecule_id=item["shared_molecule_id"],conformer_id=conf["conformer_id"]),
                                        appended_UFF_H_not_in_original_native_input=len(z)-len(order))
                                    break
                                if accepted is None:reason=";".join(sorted(set(failures)))
                        if accepted is not None:state["rows"].append(accepted)
                        else:state["excluded"].append(dict(member_index=index,member_uid=sample.member_uid,role=role,reason=reason))
                        state["cursor"]=cursor+1
                        if state["cursor"]%128==0:atomic_json(progress,state)
                atomic_json(progress,state)
                counts=dict(Counter(r["reason"] for r in state["excluded"]))
                result=dict(status="COMPLETE",identity=identity,rows=state["rows"],excluded=state["excluded"],
                    original_members=len(members),accepted_members=len(state["rows"]),exclusion_reasons=counts,
                    full_inchikey_exact_join=True,common_cohort_verified=True,
                    geometry_policy="First original sealed UFF conformer; explicit sealed atom map projects to unchanged native atom inventory; no isomorphism or geometry generation",
                    source_labels_and_original_inner_split_unchanged=True,
                    matching_recomputed=False,alignment_performed_once_by_producer=True,
                    new_geometry=False,job=execution_handle())
                atomic_json(out/"common_cohort.json",result)
                atomic_json(out/"primary_complete.json",dict(status="COMPLETE",common_cohort=str(out/"common_cohort.json"),
                    accepted_members=result["accepted_members"],exclusion_reasons=counts,job=execution_handle()))
                print(json.dumps(dict(status="COMPLETE",accepted=result["accepted_members"],excluded=len(state["excluded"]),reasons=counts)),flush=True)
                return 0
            finally:
                for stream in handles.values():stream.close()

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--configuration",required=True)
    args=p.parse_args();raise SystemExit(run(json.loads(Path(args.configuration).read_text())))

