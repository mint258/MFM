# 2026-10-28 日级任务实际进展 v5

正式数据工作合并为约24小时的sbatch；500分子等内部批次只作检查点。HPC skill1.0.123两份已同步，科学函数、种子和质量阈值保持原定义。

|端点|真实父作业|实际资源与上限|本次观察|
|---|---|---|---|
|Main|4524666 S′余量|compute-0-14，16CPU，24h|RUNNING；9项preflight通过，原24,338个once键核对结束，已开始新分子|
|Main|4524665 标签整理|compute-0-18，16CPU，24h|RUNNING；已复用完整旧哈希阶段，原typed质量检查及剩余投影继续|
|Alpha|1885075 PubChem A|compute-0-1，32CPU，24h|RUNNING|
|Alpha|1885076 PubChem B|compute-0-6，32CPU，24h|RUNNING|
|Alpha|1884790 Coconut|compute-0-1，16CPU，原48h|RUNNING，保留原作业自然完成|

S′新父一次观察有357份派发、341份结果包、0份执行器错误；这些是文件计数，不代表质量通过数或最终Common。现父从原成果和once记录续接，不再把500分子批次分别提交Slurm。原4524556的C0/64CPU/23,208秒及全部产物保留。

4524658实际FAILED/655秒/16CPU：history读回把原writer的evidence_json列误写为evidence。已在独立新Source中修复，并新增真实writer→reader回环断言；4524666同父9项检查通过。4524664实际FAILED/88秒/16CPU：整数worker数被旧回执列表同名覆盖；已用字面变量重命名修复，统计数学不变。两次失败及全部核时保留。

MoleculeNet17的4524659实际C0/156秒/16CPU，业务仍HOLD：806,735条strict5记录、27项原PDB问题中22项已取得官方证据，余21项为ClinTox1、ToxCast15、PDBbind5。随后4524667实际C0/50秒/16CPU仅整理21项已关闭证据，不新增网络、图、key、QM或UFF；没有解除UNKNOWN或全池放行。

D1静态源链已核查r73、r674、偶极和梯度的单位/存储/参考系。4个实际serializer/freezer当前Source与缓存逐字节一致。192项singlepoint坐标UNKNOWN保留；参数清单未列出.xtbrc不能单独证明历史不存在它。Model已收到并给出conditional review，尚无joint ACK。

本次Main会计纳入669个已登记真实父作业；全部失败、超时和启动成本保留，运行中核时仍增长。Alpha单独按真实端点、UID和作业计账，不混入Main身份。全部future allowance当前合计1,121,856,357,376字节；继续用真实账户quota核对200GB余量，无SBATCH内存请求。

D1–D7及250万扩充尚未全部完成。Common最终验收、TRAIN-only统计、子集/试点导出、模型实际Loader确认、正式P′试点和完整扩充沿原依赖继续。既有15+1200次精度例外仅用于诊断，不能据此启动修改精度的全量P′。

证据：control/active_checkpoint_v54.json、owned_accounting_checkpoint55_cpu_daypack_20261028_v1.json、daypack_actual_main_queue_observation_20261028_v5.json及alpha_daypack_actual_queue_observation_20261028_v5.json。旧进度仅作为原观察时刻记录保留。
