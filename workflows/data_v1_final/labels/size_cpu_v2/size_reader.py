"""Provisional/final owner selection with original source and compact-mask parity."""
from __future__ import annotations

import collections
from pathlib import Path

from aggregate import pair_keys
from compact import encode,restore_mask
from support import identity,load,require,checkpoint,checkpoint_iter


def rows_for_group(adapter, source_cfg, plan, group, mask_receipt, fit_side=None):
    checkpoint()
    import pyarrow.parquet as pq
    from reader import parity  # immutable normalization_v1 reader, pinned by Root
    rows=pq.read_table(require(fit_side or group["owner_index"]),use_threads=False).to_pylist()
    if len(rows)!=group["expected_records"] or len({r["record_id"] for r in rows})!=len(rows):
        raise ValueError("SIZE_OWNER_POPULATION_NOT_EXACT")
    if fit_side:
        owners={r["record_id"]:r for r in rows if r["fit_eligible"]}
        if any(r["effective_role"]!="TRAIN" or not r["common_population"] or r["fit_reason"]!="FIT_TRAIN_COMMON_NOT_DIAGNOSTIC" for r in owners.values()):
            raise ValueError("FORBIDDEN_FINAL_SIZE_FIT_POPULATION")
    else:
        owners={r["record_id"]:r for r in rows if r["new_role"]=="TRAIN"}
    numbers=adapter.base_numbers(group,owners)
    by_task=collections.defaultdict(list)
    for f in adapter.WORK["fields"]:by_task[f["task"]].append(f)
    seen={task:set() for task in by_task}
    mask_files={Path(p["path"]).name:p for p in mask_receipt["outputs"] if p["path"].endswith(".mask.parquet")}
    for index,pin in enumerate(checkpoint_iter(group["label_files"])):
        family=pin["family"];name=family+"_"+str(index).zfill(3)+".mask.parquet"
        compact={};ordinals={o["record_ordinal"] for o in owners.values()}
        for batch in checkpoint_iter(pq.ParquetFile(require(mask_files[name])).iter_batches(batch_size=4096,use_threads=False)):
            for r in batch.to_pylist():
                if r["record_ordinal"] not in ordinals:continue
                key=(r["record_ordinal"],r["task_code"])
                if key in compact:raise ValueError("DUPLICATE_SIZE_COMPACT_MASK_ROW")
                compact[key]=r
        used=set()
        for row,owner in adapter.match_source_rows(pin,owners,adapter.source_columns(family),source_cfg["source_read_batch_records"]):
            task=row.get("calc_type",family);row["calc_type"]=task
            if task not in by_task or owner["record_id"] in seen[task]:raise ValueError("SIZE_TASK_UNEXPECTED_OR_DUPLICATE")
            seen[task].add(owner["record_id"])
            if family not in {"D20","D3"} and (row["lane"]!=owner["lane"] or row["total_atoms"]!=owner["total_atoms"]):
                raise ValueError("SIZE_CANONICAL_LANE_OR_ATOM_COUNT_DIFFERS")
            row["total_atoms"]=owner["total_atoms"];entries=[];raw_cells={}
            if family not in {"D20","D3"}:
                raw_cells={int(c["registry_id"]):c for c in row.get("values") or []}
            pair_cache={}
            for field,values,indices,reason in adapter.WORK["common"].task_components(row,family,by_task[task]):
                _,sm,vm,sr,nr,review=adapter.WORK["masks"].source_value_mask(field,row,values,reason)
                e={"field":field,"field_id":field["field_id"],"field_key":field["field_key"],"source_path":field["source_path"],
                    "values_float64":[float(v) if type(v) in (int,float) else None for v in values],"atom_indices":indices,
                    "source_value_mask":sm,"value_mask":vm,"source_reasons":sr,"new_reasons":nr,"review_reasons":review}
                if field["level"]=="sparse_atom_pair":
                    rid=field["registry_id"]
                    if rid not in pair_cache:
                        try:raw=adapter.WORK["common"].decode_cell(raw_cells.get(rid))
                        except (ValueError,KeyError,TypeError):raw=None
                        pair_cache[rid]=pair_keys(raw,field["source_path"].split(".")[-1])
                    e["pair_keys"]=pair_cache[rid]
                entries.append(e)
            adapter.WORK["masks"].add_cross_field_checks(entries,row)
            key=(owner["record_ordinal"],plan["task_codes"][task])
            if key not in compact:raise ValueError("SIZE_PERSISTENT_MASK_MISSING")
            parity(compact[key],encode(*key,entries));used.add(key)
            for e in entries:e["value_mask"]=restore_mask(compact[key],e["field_id"],len(e["values_float64"]))
            yield owner,numbers[owner["record_id"]],task,{e["field_id"]:e for e in entries}
        if used!=set(compact):raise ValueError("SIZE_SOURCE_AND_MASK_TASK_COVERAGE_DIFFERS")
    if any(len(ids)!=len(owners) for ids in seen.values()):raise ValueError("SIZE_OWNER_TASK_COVERAGE_INCOMPLETE")
