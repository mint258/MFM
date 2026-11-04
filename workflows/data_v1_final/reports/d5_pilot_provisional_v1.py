"""Render D5 delivery counts already computed and read back by its CPU producer."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delivery", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    delivery = json.loads(Path(args.delivery).read_text(encoding="utf-8"))
    if delivery["status"] != "DELIVERED_PROVISIONAL_SCOPE_NOT_FINAL_COMMON":
        parser.error("D5 must have actual accepted provisional delivery status")
    c = delivery["components"]
    n = c["subset_counts"]
    rows = "\n".join(f"| {name} | {n[name]:,} |" for name in (
        "train_120000", "train_240000", "train_600000", "train_all",
        "pilot_train", "pilot_val", "val_all"))
    text = f"""# D-5 暂定交付：{delivery['version']}

[正式交付清单](../../configs/data_v1/D5_v1_pilot_provisional_delivery.json)已绑定实际 C0 作业、数据文件、字节数和 SHA，以及 Root 验收。适用范围为已有完整 S′ 的冻结暂定母人群；最终共同人群、D-6、D-7 后续另行发布。

| 清单 | 分子数 |
| --- | ---: |
{rows}

TRAIN 子集为 120,000 ⊂ 240,000 ⊂ 600,000 ⊂ {n['train_all']:,}。试点为其中 {n['pilot_train']:,} 个 TRAIN 分子和 {n['pilot_val']:,} 个 ROUTINE VAL 分子。VAL 全清单的 {n['val_all']:,} 个分子属于本次完整 S′ 母人群。

诊断集含 {c['diagnostic_TRAIN_molecules']:,} 个 TRAIN 分子，留出 {c['heldout_PM7_bases']:,} 个 PM7 构象与 {c['heldout_ordinary_Sprime_bases']:,} 个普通 S′ 构象。留出目标及其全部已登记子几何和实际程序输入视图，已在取前 k 个构象之前从训练索引排除；诊断分子仍保留其他训练构象。该集合仅用于预训练损失诊断，不用于模型选择。

元素出现、重原子数和骨架分布的子集与全集对照，见正式清单中的 `distributions_manifest_reference`。实际几何、输入视图、字段绑定和训练索引也由同一清单引用。当前构象索引使用固定随机顺序；D-7 的能量和多样性顺序后续发布。

此报告由 `workflows/data_v1_final/reports/d5_pilot_provisional_v1.py` 从已接受的正式清单生成。清单与诊断集的计算、排除和回读实现为 `workflows/data_v1_final/export/bounded_old_complete_d5_resume_v2/`；实际生产作业为 4525184，终态 COMPLETED / 0:0。
"""
    Path(args.output).write_text(text, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
