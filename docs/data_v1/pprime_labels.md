# P′ 标签：冻结输入范围计算与覆盖已完成

2026-11-05。此为原冻结 ready 范围的计算和覆盖闭合，不代表最终 Common 或 D-6 放行。下文旧试点准备记录仅作历史。

| 项目 | 原闭合审计结果 |
| --- | --- |
| 原 ready 分子 | 1110751 |
| 完成构象 | 2221502 |
| 全12项成功构象 | 2217077 |
| 非全12项成功构象 | 4425 |
| 全12项成功率 | 99.800810% |
| 全任务结果行 | 26658024 |
| 缺失构象 | 0 |
| 意外构象 | 0 |
| 审计覆盖 family 文件 | 192170 |
| 审计覆盖 family 字节 | 125126615731 |
| 原ready范围之外N1或不可用分子 | 103467 |
| 生成实际父作业数 | 110 |
| 生成分配核时 | 5684.262222222223 |
| 每请求构象生成分配核秒 | 9.211490243988077 |

原固定随机顺序前两个构象、版本、关键词、精度、种子、输入及900秒单调用超时保持。失败和UNKNOWN历史保留，不重复Native重试。生成核时只包含生成父作业，不包括元数据、验证、清理和只读恢复，不代表全流程总成本。成功率超过用户已批准的99.45%线。

实际最终审计：4525885 COMPLETED0:0/962s16CPUcompute-0-18。本摘要只消费原闭合JSON，不增加审计、哈希、读回或QM。

正式结果：/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/pprime_complete_remaining_20261104_v1/final_delivery/final_analysis.json；原计算/覆盖审计脚本：/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/Pprime_complete_remaining_20261104_v1/audit_final_full_v2.py。其task_failures、role_outcomes、roles、family_rows保留失败、角色及家族计数；同目录completion_manifest.json追溯正式交付。

待完成：最终Common绑定、原1.5异常值扫描、TRAIN归一化、P/P′同字段分布与相关性对照。当前没有这些全量结果，不以试点代替。r674继续LOSS_DISABLED，不追加QM。

重建：python -B workflows/data_v1_final/pprime/render_closed_delivery_summary_v1.py。

<!-- ORIGINAL_PPRIME_PILOT_HISTORY -->

# P′ 标签：2000 UFF 构象试点准备

状态：代码和配置已准备，10项受控测试通过；未提交真实 P′ QM，不声称 P′ 标签或全量共同人群完成。

## 目的与范围

在共同人群的 UFF 几何上计算与 WP5 完全相同的12任务。先取已经充足且至少两个可用构象的1000分子，按固定顺序取前2个，完成2000构象试点。少于2个构象或尚待 S′ 补齐的分子不进入本试点；不复制构象。最终全量范围仍依赖补齐结果。

## 输入及来源

`configs/data_v1/pprime/pilot_v1.json` 保存实际外部路径、字节数和 SHA；主要来源为：

- WP5 `production_contract_v7.json`（SHA `f2966094cc57ef82ca79292a9640a9bbbcf99f46d12626d28dccbe0a507fe33f`）及其冻结的 `protocol.json`、registry、engine v3、parser v2、parquet v2 和复现包。
- S′ `dataset/manifest.json`（SHA `a67e36e4fb1203f7fb72074abad3614bef6cd0e34140a38088f2492005912e01`）及其中5组 conformer parquet。
- 已闭合 S/S′ 分子对齐及 WP5 原始源记录指针。大型源文件的全 SHA 显式继承闭合清单；准备阶段检查当前大小、选中行、读取前后文件身份，不把部分投影称为重新验证全文件 SHA。
- `roles/routine_v1_job4520334/manifest.json`（SHA `16619f25f2bec53ed2d3c5e8e8381faa746e03f141d9fba87f93b6ec1e8ef8a1`）。VAL 为7610分子的72525个全部 PM7 构象；原 ROUTINE 11322条的身份另留。TRAIN 保持既有分子成员，FULL其余6248分子不入选。

## 规则与参数

固定构象顺序完全采用 SB-2 `stable_key(20261025,molecule_id,'uff_sprime',sprime_conf_idx)`。仅接受 `status=SUCCESS && converged=True` 的 S′ 构象。分子试点用固定种子2026102504，在文件组、角色和大小层中确定性排序。

保持 MOPAC23.0.3、xTB6.7.1及原二进制 SHA、关键词、单点计算和单调用900秒限制。扰动 seed为 `1+int(sha256('20261010|'+record_id)[:16],16)%2147483646`，Gaussian σ=0.1Å，位于当前 UFF 坐标周围。无几何优化、POLAR、独立ESP或Hessian新增任务。

原只读 reader 用于验证 payload 和原子次序，随后新的几何 adapter 显式传入 UFF 坐标；原 PM7 和 UFF 几何摘要分开。原 PM7 HOF 与 UFF 几何的单点 HOF 不作 Q02 差，Q02为NULL/N/A。其它数组形状、有限值、required-scope及SCF判定不放宽。永久 family parquet 保持float64；逐试点字段实际读回比较类型及float64 bits。

raw沿WP5规则：全部失败计算、按文件组和大小分层约1%的记录之全部任务输出；输入正文不保存。解析并验证、保留raw实际提交且读回后才清理本轮节点scratch。新复现 manifest 绑定本轮清单/代码/审计成员，并引用原冻结软件和环境；原文件和历史合同保持不变。

## 统计与验收

待脚本实测，尚无P′计算成功率、耗时或存储数值。`prepare_pilot.py` 将输出实际入选分子/构象、角色组成、N=1候选数、20条审计成员及来源哈希；`run_pilot.py` 输出12任务成功/失败分类、16worker闭合、float64读回和存储；`close_pilot.py` 用实际Slurm父作业 `ElapsedRaw×AllocCPUS` 统计分配核时。

试点门槛为2000构象中全12任务成功率≥99.5%、完整父allocation耗时≤11.7核秒/构象（7.8×1.5），同时要求真实父终态退出0、全部记录与家族计数、16worker退出及读回通过。失败、初始化和导出时间均计入，不以成功记录分母美化，不重复计算batch/extern。未达到门槛时报告用户，不全量提交。

## 异常与已知限制

2026-10-25，Root在compute-0-20实际运行10项受控检查，退出码0、10 PASS、11.655秒；证据为本轮仓库外 `control/sb4_synthetic_v1.log` 和 `control/sb4_sb5_code_tests_v1.json`。检查覆盖实际SB-2顺序函数一致性、UFF坐标替换与源SHA分离、Q02 N/A、原WP5输入序列化、float64家族读回、raw保留/输入禁止与持久读回、精确1%分层样本、非有限float位模式JSON以及真实父核时门槛。测试明确未调用QM、未打开LMDB、未使用GPU或提交Slurm。

本轮仅Se排除比例>20%的例外已获批准；其余停止条件不变。尚无新的P′科学失败可分类，不能把准备通过当作SCF成功。

P′全人群异常掩码、P与P′同字段分布/相关性及实际输出矢量参考系验证仍待真实试点及后续数据。旧63个N/A字段继续保留N/A，不因P′阶段擅自增加关键词补算。当前准备子集不代表最终共同人群；N=1的全量P′覆盖规则仍需在真实计数返回后明确。

脚本：`workflows/data_v1_final/pprime/`。主agent统一审阅和提交，未调用学校付费服务器。
