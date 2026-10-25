# Canonical 标签 I/O 与掩码试点：实际结果

目的：验证从已闭合 WP5 canonical owner 读取完整分子的标签、保存逐叶原值与掩码、按字段汇总和 SHA 读回；本次不拟合全人群统计量。

输入为 job4520341 生成的 4 个完整 TRAIN 分子、40 条记录，原 owner 为 job4514019。owner_receipt.json 共9941B，SHA256 956515adb25e207540ed5a17d318f1c80ddee565225ab193864302b3eed21c3e；注册表585411B，SHA256 b6a230b74b5bebfa0108e67572ed2ccc699718c2958fb69e99c58b8323c6ce45。外部 runtime_plan.json 保存所有源文件和规则的精确 path/bytes/SHA，4222B，SHA256 fa60a7d92dba449c2e549fa1fe780bebd1ef547bd9f6a85b1cc0244a5f12e178。

沿用 canonical_reader.py 的 record/molecule/attempt/job/task/lane 身份匹配、源 mask 与新增 mask 分开、float64 叶值保留、物理定义范围和已知形状检查。未知收敛状态仅复核，z>20 不自动掩盖。任何字段新增 mask 比例超过1%保存证据并停止。

实际 Slurm job4520344：compute-0-20、16CPU、32GiB，COMPLETED/0:0，5秒，80分配核秒。11份来源 family parquet 由11个实际worker进程处理；申请的16 worker容量不等同于16个实际参与者。146个enabled统计分量各覆盖40条记录，新增掩码 record-field 对为0，stop_fields为空。11份输出 parquet 全部实际SHA读回；总持久输出1,604,722B。输出没有删除记录或修改原WP5文件。

外部结果为 runs/data_v1_20261025/artifacts/labels/mask_io_v1/results/pilot_report.json，57822B，SHA256 7ce452c4c57387ff9965147ef87bdb2e992921d238b652c134fdd5109515ebf1b。Root闭合收据为 control/label_mask_io_actual_closure_v1.json，包含实际 sacct 父作业、全部输出核验数量和参与进程。

限制：这4个分子只验证实际I/O流程，不证明全人群异常率、通过率或代表性。TRAIN-only median/MAD、完整分子跨构象跳变、独立偶极模长对照、矢量/张量参考系和全人群扫描仍待执行；所有试点记录 training_eligible=false，最终共同人群和归一化仍未冻结。负面或异常结果将保留，不用此小试点外推全量掩码数量。
