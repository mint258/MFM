# 阶段2目标报告来源

任务书4.2、6、9要求的宽库逐字段截断比例，直接使用当前原通用A1拟合器的首次生产输出；没有另起数组扫描或复核作业。

| 库 | 原作业 | 分子字段 | 冻结共享参数 | 报告位置 |
| --- | --- | ---: | --- | --- |
| L1 | 4539166 / CPU11 | 197 | `/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/reference/L1/label_parameters.json` | `fit.fields` |
| L2 | 4539169 / CPU11 | 1320 | `/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/reference/L2/label_parameters.json` | `fit.fields` |

两库目前均在原完整TRAIN采集阶段，表中结果尚未生成。原本地文件分别为 `/tmp/d_recipe_20261120_stage2_A1_L1/collection/label_parameters.json` 和 L2 对应路径，随后由既有参考入口发布共享参数。只有原作业拟合闭合及实际发布后才转录结果，不以本页表示报告完成。

`tools/d_recipe/fit_reference.py:fit_collected` 调用既有 `element_reference.make_label_parameters`，在同一全TRAIN拟合流程中首次输出每字段 `field_name`、`target_policy`、`oof_r2`、`n_valid`、`clipped_TRAIN_count` 和 `clipping_fraction`；阈值为损失截断前标准化目标的绝对值>6。保留原拟合报告的精度与来源，不把它改写成一次独立原生标准化复核。

已有原D20/D3及逐原子SASA原生报告仍引用 [原全TRAIN报告](../../results/d_recipe/native_TRAIN_clipping_20261122.json)，由4538573完成。旧字段、D4、存储值与原报告计数不改；无需为新库重读旧SASA数组。最终报告分别注明原拟合器分子计数和既有原生报告的来源，不重复生成旧统计。
