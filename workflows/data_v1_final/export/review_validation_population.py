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
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path, required=True)
    args = parser.parse_args()
    inputs = {
        "population_manifest": args.population_manifest,
        "heavy_atom_bins": args.audit_root / "tables/s_population_marginals_v5/heavy_atom_bins.csv",
        "element_presence": args.audit_root / "tables/s_population_marginals_v5/element_presence_marginals.csv",
        "sprime_training_manifest": args.audit_root.parent / "sprime_s_convergence_20261013/training_inputs_v1/manifest.json",
    }
    before = {key: reference(path) for key, path in inputs.items()}
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
        "status": "CLOSED_AGGREGATES_COMPARED_VAL_FAMILY_AUTHORITY_PENDING",
        "observed_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
        "inputs": before, "producer": reference(Path(__file__)),
        "population_scope": "Existing pre-fill WP5 population, not final common population v1",
        "molecules": totals, "records": records, "larger_population": "TRAIN",
        "TRAIN_to_FULL_molecule_ratio": totals["TRAIN"] / totals["FULL"],
        "heavy_atom_bins": heavy_rows, "element_presence": element_rows,
        "heavy_atom_binned_total_variation": heavy_tv,
        "scientific_parquet_read": False, "source_data_modified": False,
        "family_authority": {"status": "NOT_IDENTIFIED_IN_REVIEWED_SOURCES",
            "not_equivalent": ["94 account top-level directories", "65 storage inventory groups",
                               "13 WP5 storage/label families", "downstream scaffold folds"]},
        "validation_assignment": "PENDING_AUTHORITY_AND_COMPLETE_FAMILY_MEMBERSHIP",
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

状态：既有闭合聚合已比较；VAL 家族权威待定位。日期：{result['observed_at']}。

## 目的

回答当前 TRAIN/FULL 的分子数量与已保存分布有何差异，并为用户指定的“从较大人口中整家族留作 VAL”提供来源依据。本报告没有建立新 VAL。

## 输入及哈希

{refs}

机器结果：{json_ref['path']}，SHA256 {json_ref['sha256']}。生产脚本：workflows/data_v1_final/export/review_validation_population.py，SHA256 {result['producer']['sha256']}。这些为原 S′补齐前的 WP5 人口，不冒充共同人群 v1。

## 规则和参数

只读取四个既有小型元数据/CSV；不扫描原 LMDB、科学 parquet 或分子明细。对每个角色与类别，核对各 availability 行重复携带的 population denominator 一致，再以该分母计算全人口比例。重原子组使用每分子的 canonical PM7 最大重原子数。元素每分子每元素计一次，边际可重叠。

TRAIN 为 {totals['TRAIN']:,} 分子／{records['TRAIN']:,} records；FULL 为 {totals['FULL']:,} 分子／{records['FULL']:,} records。TRAIN 分子数为 FULL 的 {result['TRAIN_to_FULL_molecule_ratio']:.4f} 倍，是用户要求的较大来源人口。原 authority 只有 TRAIN/FULL；routine 是 FULL 内的监控子集，不能视为独立 VAL。

## 统计结果

### 重原子数

{table(heavy_rows)}

既有分箱的描述性 total variation 为 {heavy_tv:.8f}。FULL 在 31–50 重原子组的比例较高，在 21–30 组较低。这是可观察的边际差异；没有进行等分布假设检验或把它写成全部联合分布结论。

### 元素出现率

{table(element_rows)}

例如 FULL 的 Si 比例较高，而 N、S 比例较低。不同元素行存在重叠，不相加推算不重复分子数。

### 来源、骨架和“九十几个家族”

本次已保存聚合不含 TRAIN/FULL 的来源交叉分布或分子骨架分布，尚不能报告这些维度的实测差异。已检查 docs/phase1/ 顶层文档、审计报告、workflows/dataset_rebuild/scripts/、workflows/screening/scripts/ 与审计脚本中的分类/聚类/骨架线索，尚未识别可用的约九十个分子家族权威清单。账户94个顶层目录、65个存储组、13个WP5家族及下游 scaffold folds 均不是所需的分子家族。

下一步应优先取得原分类清单和生成规则，并在有界 CPU Slurm 作业内只投影 molecule ID、原家族 ID、角色、身份键及必要结构列：检查一分子一家族/多家族规则、TRAIN/FULL 家族分布、家族大小、跨家族身份重叠及约定的去泄露键。未定位原分类前不另造新分类并称其为历史约九十个家族。

## 异常与处理

没有修改原角色，也没有将 FULL 自动改名 VAL。用户已要求差异存在时以较大人口作来源，因此候选来源为 TRAIN；具体家族 ID、完整成员清单与占比仍须权威分类支持后冻结。VAL 的所有构象必须随分子一起隔离，并在归一化和嵌套子集生成之前排除；既有 FULL 保留原角色。

## 已知限制

本报告只比较现有预补齐人口的边际；共同人群筛选及 Se 例外后的分布必须另算。旧输入曾用 FULL/routine 作模型监控，不代表本轮已建立独立、未被使用的验证集。未确定家族 ID，不输出训练可用的 VAL 清单或声称 D-5 完成。
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
