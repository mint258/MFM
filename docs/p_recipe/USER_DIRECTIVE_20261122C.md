# 配方线补充指示：组成信息诊断的指标定义更正（用户 2026-11-22）

适用：`USER_DIRECTIVE_20261122.md` 第 2 节（H-comp）与 `USER_DIRECTIVE_20261122B.md` 的 A2（H-B4）、F 与 p-capacity 中引用的组成信息诊断。其余条款不变。

更正：两份指示写的"原子 H 的 CEV、CVF、CVF_res"在现有工具中没有定义，作废。指标一律按 `tools/p_followup/collapse_composition.py` 与 `docs/p_followup/A_COLLAPSE_COMPOSITION.md` 的现有定义：

- mean(H)：CEV、CEV_size、CVF、CVF_res、参与率。
- 原子 H：只报告 EEV（按元素分组的组间平方和 / 原子总平方和），名称照写 EEV，不改称原子 CEV。
- 不新造原子级 CVF、CVF_res 或其他新指标。

H-comp 与 H-B4 的预注册判定只用 mean(H) 的 CEV，判定规则按原指示；EEV 与其余各项只作描述。
