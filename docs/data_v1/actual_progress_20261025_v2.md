# 数据线实际进度快照（2026-10-25T17:28:06.275674+08:00）

目的：登记已实际完成和仍待完成的工作。此报告不是共同人群、最终注册表、归一化或训练导出的验收凭证。

输入与方法：脚本只读取不超过2MiB的闭合receipt/控制元数据，并查询本轮不可变提交记录对应的全部Slurm父作业；不读取大型科学数据正文。核秒为父作业ElapsedRaw×AllocCPUS，包含失败。

| 项目 | 实际结果 |
| --- | --- |
| X全原始输入回放 | 15,879,477唯一记录；规则及条件入选一致率100.000%；未解释差异0；1926条历史flag差异全部留存 |
| PubChem有界前缀 | 10,000输入行，16真实worker；X及身份/特征后8,198行，8,197唯一完整key；作业4520427 COMPLETED/0:0/14s |
| 特征失败 | 753行，比例7.53%；原错误和所有拒绝保留，三CID逐阶段诊断待执行，不新增化学排除 |
| 精确中位数小试点 | 512完整分子/4251记录/146字段；已完成median全部radix轮，MAD与最终mask待执行；本阶段新增mask最大比例0.000% |
| S′补齐小试点4520364 | 332/336完成；submitted=336；dispatch_allowed=True；resource_denial=None；尚待最终receipt/实际成本/失败分层审查 |
| 本轮作业记账 | 37个实际父作业，已终态34,080分配核秒；仍活动['4520364']，活动成本另为下限，不能报总成本完成 |

异常与处理：compute-0-20当前被其他作业全部占用，已备诊断/MAD/只读vector准备请求尚无提交intent；不修改或终止该作业。正式生成维持原16CPU/64GiB及普通全部用户申报内存85%要求，UFF/QM仅14–19。本轮336分子小试点的单次实测内存例外不扩展。

实现验证：size语义增量13项/16进程实际通过（4520430）；S′稳定物理ID新增9项实际通过；P′稳定raw policy4项、保留策略3项、正式流程8项及修复后的SQL fixture1项实际通过。旧SQL fixture失败证据保留。实现与合成测试不替代真实科学验收。

已知限制：前10000输入行不是PubChem代表性样本，尚未完成去污染。X回放仍待共同人群范围绑定。当前校准使用原TRAIN的小试点，不能用作D-4；D-4须冻结common及诊断几何后重算。D-1 draft.3尚未双方定为v3.0，D-2及D-3至D-7最终真实交付均未完成。

输入小文件引用：

```json
{
  "X_closure": {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/x_full_v3_actual_closure_v1.json",
    "bytes": 1801,
    "sha256": "2eb41060bbc3a15109de8f1dc3670f1174180d53647d32ef37b42ee0c7e4e344"
  },
  "prefix_receipt": {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion/screening/bounded_prefix_v2/receipt.json",
    "bytes": 5811,
    "sha256": "2806743412901d748efb26c1f1f1addbc5dd72e0d3c866fef009d9eeda9db25c"
  },
  "median_reduction": {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/labels/streaming_v1/reduce_med_r6_p32_v1/reduction.json",
    "bytes": 63322,
    "sha256": "cdc2a78a0f4d0e450e248baafda65fd402a6dfaa0ebeb515381919341dda4b6b"
  },
  "progress": {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/pilot_32g_v1/progress_000332_000.json",
    "bytes": 150,
    "sha256": "3d799ab63b2864ac607aeed9050cc6d3892e645b0f2c041b8118fc2aea9438bb"
  },
  "actual_accounting": {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/owned_accounting_v7.json",
    "bytes": 20646,
    "sha256": "0399153621c54b920dd68f09e4a50a5213ad123dd7f439f0b61e478361deaaf0"
  },
  "checkpoint": {
    "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/active_checkpoint_v7.json",
    "bytes": 3480,
    "sha256": "cd52ccdd7bfc2d451826408053b50eb1f32fcb4f59e07b82d6042bfab52ab3ae"
  }
}
```
