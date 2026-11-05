# A类采用与完整回归：2026-10-29

用户v3已生效；本轮实现与报告已公开于 `model-v3` 的 `af11eaae3992dcc33145fd44271b80b9481a7b25`，对应实际执行代码 `e7c0a2ccc188ca42785d2a87cf0c66cf5141e35a`，Git tree完全相同。科学DECISION_RULES及TRAIN/noTEST保持。

完整回归实际CPU4525171 C0/272秒/16CPU/node19：137模块，3238项，**3235通过、3个原有CUDA跳过、0失败/错误**；两新增模块49项均通过。沿既有四pytest/fixture census入口执行。此前额外包装5167/5168的失败保留，该包装停止修复；随后本次主线回归通过，不覆盖旧记录。新接线测试中仅修正了继承一层UNIT默认值的ff_mult，使六层fixture为2；原fixture和生产模型未改。

## 采用依据与边界

| GPU | 已证明选择 | 原数值验收 | 原R1候选/参考吞吐 |
| --- | --- | --- | ---: |
| 5090 C35 | HeadOff | 4722、5063，当前梯度v2通过 | 1.0693858781 |
| 4090 ec788… | BackboneOff | 5046及CPU5074，当前梯度v2通过 | 1.2248576848 |

自动入口现直接消费已闭合普通R1的配置/summary，不要求旧记录出现当时不存在的performance_execution字段，也不因新增源码图或SHA/SDK记录问题抹掉已通过的数学资格。实际GPU UUID、Torch/CUDA/driver、原模型/损失/seed0/sampler、实测峰值、空闲显存及85%仍保护；外来进程/未知物理资源不被元数据回退捕获。

该容量事实只覆盖原fresh S的2次预热+20次测量、单模型、已知实际卡及相同负载。未知长程训练、C/SDP、其他卡或形状继续旧checkpoint；不把8M sampler上限当任意形状容量。5090通过项在匹配已证卡时可用HeadOff，尚未声称所有5090或C模型均有已测容量。

## 实际操作验证

| 作业 | 环境 | 实际结果 |
| --- | --- | --- |
| 4525172，C0/103秒 | CUDA12.8 | 与原4090的CUDA12.6不匹配，安全保留backbone/distance/head全开；原结果保留 |
| 4525173，C0/84秒 | 原Torch2.10.0+cu126/CUDA12.6 | 实际选择backbone关闭、distance/head开启，22次forward完成，20个测量批次与原R1的输入receipt完全相同 |

两次均使用同一已验代码，第二次仅采用原运行环境。没有重跑20批+500步数学资格，也没有另开精度分支；候选position2只为原CLI兼容，未宣称组成一组新的ABBA或由这两次不同环境估计因果提速。第二次stderr保留一行`terminate called without an active exception`；父作业、supervisor、summary和run_status均正常完成，未据此追加诊断或阻塞主线。

原证据见 [完整回归](results/USER_V3_FULL137_actual_v1.json)、[实际操作](results/USER_V3_A_ADOPTION_OPERATIONS_actual_v1.json) 与 [两条真实运行记录](results/A_operational_adoption_20261029.csv)。CSV的config_sha256为实际配置文件原字节SHA256，elapsed_seconds为Slurm父耗时；原R1表与数值失败记录不改。C1-a另见[同批关闭checkpoint测量](C1A_CHECKPOINT_OFF_THREE_GPU_20261029.md)，不混为本次A操作。
