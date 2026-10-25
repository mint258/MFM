"""Compare already-closed TRAIN/FULL aggregates without reading scientific data."""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import hashlib
import json
from pathlib import Path


def reference(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def closed_counts(rows, category, denominator, totals):
    grouped = {}
    for row in rows:
        role = row["population_scope"]
        if role not in totals:
            continue
        assert int(row["denominator_population_molecules"]) == totals[role]
        key, count = row[category], int(row[denominator])
        old = grouped.setdefault(key, {}).setdefault(role, count)
        assert old == count, (key, role, old, count)
    assert grouped and all(set(item) == set(totals) for item in grouped.values())
    return grouped


def comparison(counts, totals):
    result = []
    for category, values in counts.items():
        train_fraction = values["TRAIN"] / totals["TRAIN"]
        full_fraction = values["FULL"] / totals["FULL"]
        result.append({"category": category, "TRAIN_molecules": values["TRAIN"],
                       "FULL_molecules": values["FULL"],
                       "TRAIN_fraction": train_fraction, "FULL_fraction": full_fraction,
                       "FULL_minus_TRAIN_percentage_points": 100 * (full_fraction - train_fraction)})
    return result


def table(rows):
    lines = ["|类别|TRAIN 分子数|TRAIN %|FULL 分子数|FULL %|FULL−TRAIN 百分点|",
             "|---|---:|---:|---:|---:|---:|"]
    for row in rows:
        lines.append(f"|{row['category']}|{row['TRAIN_molecules']:,}|"
                     f"{100 * row['TRAIN_fraction']:.4f}|{row['FULL_molecules']:,}|"
                     f"{100 * row['FULL_fraction']:.4f}|"
                     f"{row['FULL_minus_TRAIN_percentage_points']:+.4f}|")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--population-manifest", type=Path, required=True)
    parser.add_argument("--decision-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    args = parser.parse_args()
    inputs = {
        "population_manifest": args.population_manifest,
        "user_decision": args.decision_file,
        "heavy_atom_bins": args.audit_root / "tables/s_population_marginals_v5/heavy_atom_bins.csv",
        "element_presence": args.audit_root / "tables/s_population_marginals_v5/element_presence_marginals.csv",
        "sprime_training_manifest": args.audit_root.parent / "sprime_s_convergence_20261013/training_inputs_v1/manifest.json",
    }
    training = json.loads(inputs["sprime_training_manifest"].read_text(encoding="utf-8"))
    routine_ref = next(row for row in training["references"]
                       if row["role"] == "routine" and row["kind"] == "record_metadata")
    inputs["routine_arrow"] = Path(routine_ref["path"])
    before = {key: reference(path) for key, path in inputs.items()}
    assert all(before["routine_arrow"][key] == routine_ref[key] for key in ("path", "bytes", "sha256"))
    decision = json.loads(args.decision_file.read_text(encoding="utf-8"))
    assert decision["validation"]["source"] == "ROUTINE"
    assert decision["validation"]["source_reference"] == before["routine_arrow"]
    assert training["roles"]["routine"]["records"] == 11322
    assert training["roles"]["routine"]["molecules"] == 7610
    population = json.loads(inputs["population_manifest"].read_text(encoding="utf-8"))
    totals = {row["split"].upper(): int(row["molecules"]) for row in population["roles"]}
    records = {row["split"].upper(): int(row["records"]) for row in population["roles"]}
    assert totals == {"TRAIN": 1206608, "FULL": 13858}
    assert "VAL" not in totals
    heavy = closed_counts(read_csv(inputs["heavy_atom_bins"]), "category_value",
                          "denominator_category_population_molecules", totals)
    elements = closed_counts(read_csv(inputs["element_presence"]), "element",
                             "denominator_element_population_molecules", totals)
    assert all(sum(values[role] for values in heavy.values()) == totals[role] for role in totals)
    heavy_rows, element_rows = comparison(heavy, totals), comparison(elements, totals)
    heavy_tv = 0.5 * sum(abs(row["TRAIN_fraction"] - row["FULL_fraction"]) for row in heavy_rows)
    after = {key: reference(path) for key, path in inputs.items()}
    assert after == before, "SOURCE_CHANGED_DURING_METADATA_REVIEW"
    result = {
        "status": "CLOSED_AGGREGATES_COMPARED_ROUTINE_VAL_AUTHORIZED",
        "observed_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
        "inputs": before, "producer": reference(Path(__file__)),
        "population_scope": "Existing pre-fill WP5 population, not final common population v1",
        "molecules": totals, "records": records, "larger_population": "TRAIN",
        "TRAIN_to_FULL_molecule_ratio": totals["TRAIN"] / totals["FULL"],
        "heavy_atom_bins": heavy_rows, "element_presence": element_rows,
        "heavy_atom_binned_total_variation": heavy_tv,
        "scientific_parquet_read": False, "source_data_modified": False,
        "routine_authority": {"legacy_records": 11322, "molecules": 7610,
            "source_role": "FULL", "subset_of_FULL": True,
            "effective_VAL_rule": "All geometries of ROUTINE molecule IDs",
            "legacy_record_rule": "Preserve original 11322 member flags separately",
            "actual_roles_manifest": "PENDING_ROOT_SLURM_ROLE_FREEZE"},
        "family_holdout": {"required": False,
            "status": "SUPERSEDED_BY_USER_ROUTINE_CORRECTION"},
        "validation_assignment": "AUTHORIZED_ROUTINE_MOLECULE_IDS_ACTUAL_ROLES_PENDING",
        "limitations": ["Descriptive marginals do not prove equal or different joint distributions.",
                       "Element marginals overlap and cannot be summed as disjoint classes.",
                       "Source and molecular-scaffold distribution comparisons are not available in these CSVs.",
                       "No new VAL role or family membership is created by this review."],
    }
    args.output_dir.mkdir(parents=True, exist_ok=False)
    result_path = args.output_dir / "population_comparison.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    json_ref = reference(result_path)
    refs = "\n".join(f"- {key}: {ref['path']}; {ref['bytes']:,} bytes; SHA256 {ref['sha256']}."
                     for key, ref in before.items())
    report = f"""# TRAIN/FULL 分布及 VAL 来源核验

状态：既有闭合聚合已比较；用户已指定 ROUTINE 分子作为 VAL，实际角色清单待冻结。日期：{result['observed_at']}。

## 目的

回答当前 TRAIN/FULL 的分子数量与已保存分布有何差异，并记录用户纠正后的 ROUTINE 验证集权威。本报告的原分布对照仍成立，但整家族留出已被用户替代；本报告本身没有物化新 VAL 清单。

## 输入及哈希

{refs}

机器结果：{json_ref['path']}，SHA256 {json_ref['sha256']}。生产脚本：workflows/data_v1_final/export/review_validation_population.py，SHA256 {result['producer']['sha256']}。这些为原 S′补齐前的 WP5 人口，不冒充共同人群 v1。

## 规则和参数

只读取六个小型输入（含 ROUTINE Arrow 的完整性哈希）；不解析 Arrow 的 ID 行，不扫描原 LMDB、科学 parquet 或分子明细。对每个角色与类别，核对各 availability 行重复携带的 population denominator 一致，再以该分母计算全人口比例。重原子组使用每分子的 canonical PM7 最大重原子数。元素每分子每元素计一次，边际可重叠。

TRAIN 为 {totals['TRAIN']:,} 分子／{records['TRAIN']:,} records；FULL 为 {totals['FULL']:,} 分子／{records['FULL']:,} records。TRAIN 分子数为 FULL 的 {result['TRAIN_to_FULL_molecule_ratio']:.4f} 倍。原 authority 只有 TRAIN/FULL；routine 是 FULL 内的监控子集。用户最新指定由该 ROUTINE 的分子成员定义本轮 VAL，不再从 TRAIN 新划家族。

## 统计结果

### 重原子数

{table(heavy_rows)}

既有分箱的描述性 total variation 为 {heavy_tv:.8f}。FULL 在 31–50 重原子组的比例较高，在 21–30 组较低。这是可观察的边际差异；没有进行等分布假设检验或把它写成全部联合分布结论。

### 元素出现率

{table(element_rows)}

例如 FULL 的 Si 比例较高，而 N、S 比例较低。不同元素行存在重叠，不相加推算不重复分子数。

### ROUTINE 验证集权威

用户已纠正此前家族信息，并指定 ROUTINE 用作验证集。原 population manifest 明确 ROUTINE 是 FULL 子集，共11,322条legacy records、7,610个分子；training_inputs_v1/manifest.json 精确绑定 routine.arrow 的路径、行数、字节数及SHA。本次实际核对该Arrow的字节哈希，但没有解析ID内容。

有效VAL以这7,610个 molecule_id 为单位，覆盖每个入选分子的全部可用PM7/S′几何；原11,322条record成员另保存 legacy_routine_member。不得把7,610个分子的其余构象改回TRAIN。原TRAIN成员保持，FULL中未入选的分子保留FULL。共同人群过滤后实际VAL数量须重新统计，不能把7,610当作最终已可训练数量。

Role-freeze入口为 workflows/data_v1_final/export/freeze_routine_roles.py。任务只读取 molecule_index.parquet 与 routine.arrow，按16个互不重叠分片统计、验证及输出molecule roles；不复制1,100万记录表。实际检查ROUTINE distinct counts、属于FULL、TRAIN/VAL分子ID及precomputed identity component无交叉。molecule_index无完整InChIKey或骨架字面列，因此该层零交叉只继承原WP5绑定manifest的三路identity_checks=0，明确不冒充新全表化学身份重扫。

已保存聚合仍不含TRAIN/FULL来源交叉分布或分子骨架分布。先前整家族VAL方案仅为被用户纠正的历史，不再查找或生成家族分类。

## 异常与处理

没有修改原角色，也没有将整个 FULL 自动改名 VAL。按用户最新指令，仅ROUTINE分子定义effective VAL，source_role仍保留FULL；完整角色清单由Root统一提交16CPU的Slurm任务后验收。VAL的所有构象须在TRAIN归一化和嵌套训练子集生成之前排除。

## 已知限制

本报告只比较现有预补齐人口的边际；共同人群筛选及 Se 例外后的分布必须另算。旧输入曾用 FULL/routine 作模型监控，不代表本轮已建立独立、未被使用的验证集。实际role-freeze尚待执行和验收，不声称D-5完成。
"""
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("x", encoding="utf-8") as stream:
        stream.write(report)
    args.source_manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.source_manifest.open("x", encoding="utf-8") as stream:
        json.dump({"status": result["status"], "inputs": before, "result": json_ref,
                   "producer": result["producer"]}, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": result["status"], "result": json_ref,
                      "report": reference(args.report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
