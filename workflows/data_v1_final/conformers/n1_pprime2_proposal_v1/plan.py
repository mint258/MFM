"""Read-only N=1 second-real-UFF proposal; contains no embedding/optimization."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

sys.dont_write_bytecode=True
FORMAL=Path(__file__).parent.parent/"formal_v1"
sys.path.insert(0,str(FORMAL))
from full_common import IO,authority_roles,config,review,runtime,q
from selection import conformer_orders,select_fill,stable_key


def proposed_seed(mid):
    value=int.from_bytes(hashlib.sha256(("sprime-ETKDGv3-v1-n1-pprime2:"+mid).encode()).digest()[:4],"big")
    return max(value&0x7fffffff,1)


def choose_second(old,candidates,distance):
    """Pure selection fixture API; callers must separately validate scientific provenance."""
    if old["origin"]!="accepted_sprime":raise ValueError("ONE_REAL_BASELINE_REQUIRED")
    for row in candidates:
        if row["origin"]!="data_v1_n1_pprime2" or row.get("optimizer_code")!=0 or row.get("stereo_valid") is not True or row.get("finite") is not True:
            raise ValueError("REAL_CONVERGED_STEREO_VALID_CANDIDATES_REQUIRED")
        if type(row["candidate_id"]) is not int or row["candidate_id"]<0 or row["seed"]==old["seed"]:
            raise ValueError("NEW_PROPOSAL_SEED_AND_REAL_CANDIDATE_ID_REQUIRED")
    selected=select_fill([old],candidates,2,distance,0.5)
    if len(selected)!=2:return {"status":"PPRIME2_UNRESOLVED_NO_SECOND_REAL_CANDIDATE","second":None}
    return {"status":"PROPOSED_REAL_SECOND_SELECTED","second":selected[1]}


def expanded_orders(mid,old,second,distance):
    """Separate expanded view; never rewrites original N=1 or its baseline order."""
    rows=[dict(old,conformer_id=0),dict(second,conformer_id=f"n1p2:{second['seed']}:{second['candidate_id']}")]
    if not all(math.isfinite(float(row["energy"])) for row in rows):raise ValueError("FINITE_UFF_ENERGIES_REQUIRED")
    return conformer_orders(rows,distance,mid,"uff_sprime",20261025)


def budget_evidence(rows,pilot_records,actual_core_seconds):
    times=[float(row["summary"]["elapsed_seconds"]) for row in pilot_records]
    if not times or any(not math.isfinite(t) or t<0 for t in times) or sum(times)<=0:
        raise ValueError("FINITE_REAL_PILOT_TIMINGS_REQUIRED")
    # Source336 was not a dedicated N1 second-candidate experiment. This is
    # disclosed as a coarse scenario, never a calibrated formal cost guarantee.
    overhead=max(1.,actual_core_seconds/sum(times))
    estimate=len(rows)*max(times)*overhead/3600
    return {"scope_molecules":len(rows),"candidate_optimization_calls_max":len(rows)*10,
        "max_optimizer_iterations_per_candidate":2000,"optimizer_iteration_steps_max":len(rows)*10*2000,
        "coarse_scenario_core_hours":estimate,"actual_336_parent_core_hours":actual_core_seconds/3600,
        "maximum_observed_336_molecule_seconds":max(times),"actual_allocation_overhead_factor":overhead,
        "calibrated_n1_cost":False,"dedicated32_molecule_pilot_required_before_formal_estimate":True,
        "formal_total_over500_requires_explicit_root_review":True}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--config",type=Path,required=True);p.add_argument("--pilot-review",type=Path,required=True)
    p.add_argument("--root-preflight",type=Path,required=True);p.add_argument("--output",type=Path,required=True)
    a=p.parse_args();proposal=json.loads(a.config.read_text())
    if proposal.get("status")!="PROPOSAL_NOT_AUTHORIZED_TO_GENERATE" or proposal.get("schema")!="DATA_V1_N1_PPRIME2_PROPOSAL_V1":
        raise ValueError("PROPOSAL_CONFIG_REQUIRED_NO_SCIENCE_AUTHORITY")
    formal=config(IO.require_pin(proposal["formal_config"]))
    runtime(proposal,a.root_preflight,a.config)
    decision,_,actual=review(a.pilot_review,for_planning=True)
    refs=json.loads(Path(decision["pilot_reproduction_manifest"]["path"]).read_text())
    pilot=[]
    for ref in refs:
        pilot.append(json.loads(gzip.decompress(IO.require_pin(ref).read_bytes())))
    if len(pilot)!=336 or len({row["summary"]["molecule_id"] for row in pilot})!=336:
        raise ValueError("ALL336_UNIQUE_ACTUAL_PILOT_PACKAGES_REQUIRED")
    roles_ref,roles=authority_roles(formal)
    import duckdb
    import pyarrow as pa
    db=duckdb.connect();db.execute("SET threads=16");db.execute("SET memory_limit='20GB'")
    db.execute("CREATE VIEW p AS SELECT * FROM read_parquet("+q(formal["per_molecule"]["path"])+")")
    all_n1=db.execute("SELECT count(*) FROM p WHERE S_conformers=1").fetchone()[0]
    if all_n1!=proposal["expected_source_pm7_n1_molecules"]:
        raise ValueError("SOURCE5040_PM7_N1_COUNT_NEEDS_ROOT_RECONCILIATION")
    rows=db.execute("""SELECT p.*,r.source_role,r.effective_role,r.records,r.file_group
      FROM p JOIN read_parquet(ROLES) r USING(molecule_id)
      WHERE p.S_conformers=1 AND r.effective_role IN ('TRAIN','VAL') ORDER BY p.molecule_id
      """.replace("ROLES","["+",".join(q(ref["path"]) for ref in roles)+"]")).fetch_arrow_table().to_pylist()
    for row in rows:
        mid=row["molecule_id"]
        row.update(source_N=1,baseline_count_target=1,proposed_second_candidate_count=10,
            proposed_seed=proposed_seed(mid),
            task_key=hashlib.sha256(("n1-pprime2-once-proposal-v1:"+mid).encode()).hexdigest(),
            baseline_ready=row["S_usable_conformers"]==1 and row["Sprime_conformers"]>=1 and row["Sprime_status"]!="UFF_UNSUPPORTED",
            prospective_common_only=True,actual_common_membership_pending=True)
    pilot_rows=sorted([row for row in rows if row["baseline_ready"]],
        key=lambda row:(stable_key(20261025,row["molecule_id"],"n1_pprime2_pilot",0),row["molecule_id"]))[:32]
    out=IO.new_output_directory(a.output,proposal)
    IO.write_parquet_new(out/"prospective_train_val_n1.parquet",pa.Table.from_pylist(rows))
    IO.write_parquet_new(out/"proposed_pilot32.parquet",pa.Table.from_pylist(pilot_rows))
    budget=budget_evidence(rows,pilot,actual);IO.write_json_new(out/"budget_evidence.json",budget)
    IO.write_json_new(out/"proposal.json",{"schema":"N1_PPRIME2_READONLY_PROPOSAL_V1",
        "status":"PROPOSAL_REQUIRES_ROOT_SCIENTIFIC_REVIEW","config":IO.reference(a.config),
        "roles_manifest":roles_ref,"original_source_pm7_n1":all_n1,"prospective_train_val_n1":len(rows),
        "baseline_ready":sum(row["baseline_ready"] for row in rows),"proposed_pilot_molecules":len(pilot_rows),
        "tables":[IO.reference(out/"prospective_train_val_n1.parquet"),IO.reference(out/"proposed_pilot32.parquet")],
        "budget_evidence":IO.reference(out/"budget_evidence.json"),"pilot_review":IO.reference(a.pilot_review),
        "generated_or_optimized_geometries":0,"original_counts_changed":False,"common_membership_changed":False,
        "source_pins":formal["per_molecule"],"needs_frozen_common_intersection_before_science":True,
        "production_science_runner_present":False})
    db.close()


if __name__=="__main__":main()
