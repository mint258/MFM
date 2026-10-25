# 流式标签扫描 v1：准备、实测与验收边界

本目录是新实现，旧注册表、旧试点脚本、配置及已登记输出保持原字节。尚未运行本目录的真实源扫描，也未发布D4。

## 已知负面结果与本次目的

job4520344的旧I/O试点已真实完成：4个完整TRAIN分子、40条记录、146字段、新增mask为0，11个输出共1,604,722字节。其closure为 `control/label_mask_io_actual_closure_v1.json`。该试点把正常逐叶值复制到observations，约40kB/record；不能直接全量复制约450GB，再把它当成唯一可行方案或已测存储预算。

新实现保持原有source eligibility、物理界和跨字段检查，正常标签原值不再落盘。原值始终保留在只读WP5 family parquet；新产物只保存紧凑mask、原因、必要的稀疏leaf例外及有上限的异常/审计预览。TRAIN统计所需的无record ID加权联合直方图被明确标为临时统计scratch，其峰值仍计入预算。

## 计划与完整人群守恒

配置为 `configs/data_v1/labels/streaming_v1.json`，绑定最终catalog、D20 failure-aware读回报告、冻结ROUTINE角色、原population和已真实执行过的解码/mask函数SHA。

`prepare.py --mode pilot` 选择16个有足够分子的canonical owner job，每组固定seed选择32个完整分子，共512个。它不按S′成功与否过滤，也不只保留TRAIN，避免把“完整原人群异常扫描”暗改成共同人群或成功子集。优先低源文件字节量仅用于I/O试点；该试点不代表总体分布。

`prepare.py --mode full` 构造全部1,220,466分子、11,231,854记录，验证record ID和物理ordinal唯一、全分子记录数一致、ordinal精确覆盖0至11,231,853；每个最终owner组都必须有所有标签家族及base_geometry。TRAIN/VAL/FULL角色由现有角色清单保留，TRAIN不重新划分。full模式并不授权自动提交后续扫描。

`record_ordinal` 是SHA绑定的单个authority parquet中的物理行号，使用DuckDB的 `file_row_number`，不是筛选后的重新编号；接口参见[DuckDB官方Parquet文档](https://duckdb.org/docs/1.5/data/parquet/overview)。语义测试直接检查过滤后的ordinal仍指向原物理行。

worker按完整record/molecule/attempt/job/task匹配，量化表再核lane和原子数。base_geometry核atomic_numbers、原子序SHA、payload SHA和heavy-atom count。不打开原LMDB或WP5 SQLite。已知D20 PROPERTY_FAILED／NULL names／全False masks依照最终failure-aware authority处理，不能升级为新异常或源缺损。

每个worker对14项任务（12个量化任务加D20、D3）维护逐record seen位图，重复立即失败；每项任务必须恰好覆盖本组全部ordinal。reducer从准备索引重新读取ordinal摘要，核每组、每任务和146字段分母；full模式必须合计134,782,248个量化槽及157,245,956个含D20/D3槽。少组、重复组或缺任何task均不能发布完整覆盖结果。

## 紧凑mask契约

field_map按enabled field_key固定排序，为146个统计分量赋新ID 0–145。它仍不等于146个独立预测头。

每条record/task写：uint64 ordinal、uint8 task code和5个19字节field bitsets，分别表示in-scope、source-valid、仍有有效值、全部leaf有效及新增掩盖字段。原因按code合并为field bitset；只有部分有效数组才保存稀疏leaf索引。全False字段无需复制成数千个False，也不复制正常数值。

这种固定部分的未压缩大小约95字节/task，另有索引、稀疏原因及审计开销；实际压缩大小必须由新试点测得。不能先声称全量能装下。

source已有缺失、NULL/ABSENT/EMPTY、形状失败、numeric_issues和新物理掩盖分别计数。收敛NULL只是review；显式False沿用原规则。z>20、MAD=0且偏离及同分子数量级跳变也只review，不自动mask。偶极矩模必须来自独立保存来源；不能计算同一向量的模后自证。

所有分子的全部构象在同一owner组，故同分子标量跳变可完整检查；ratio仅用于非零且同号的有效值，阈值1000只作复核。符号跨越/零值不伪造比值。异常样例按field＋reason保留各组top20，reducer再合并global top20，度量和并列规则写入每条预览。常见状态类问题采用相同严重度并按ordinal固定排序。

## TRAIN校准与归一化边界

所有统计仅使用TRAIN，不使用VAL/FULL标签。当前fit scope是共同人群/diagnostic过滤前的原TRAIN，适用于异常参考及size分析，不能冒充最终归一化。

1. profile阶段收集分级float64 radix计数及小型TSQR状态，不保存原子/原子对全部无损值直方图。
2. reducer定位精确median所需的prefix。尚未精确到64位时输出新的query文件；Root按新鲜预算另行提交 `scan.py --phase refine --queries ...`，然后reduce。所有prefix质量必须与上轮完全一致，否则失败。
3. median闭合后自动生成MAD queries；再次经Root提交必要的refine轮次，得到exact TRAIN median/MAD。小于2条、无值、常数或MAD=0均保留显式状态，不填伪尺度。
4. `scan.py --phase mask --calibration ... --energy-reference ...` 只接受相同coverage fingerprint、相同pilot/full scope和TRAIN-only来源。pilot阈值不能用于full。z只增加review；任一字段新增mask记录率>1%，reducer先保存证据并退出2，不继续拟合。

radix使用IEEE float64单调位编码，numeric signed zero在统计中合并，源标签不变。type-7分位的插值采用明确的有理权重及可复现舍入，同核支持q0.001/q0.999。它避免数千亿leaf的持久原值复制，但可能需要多次完整源读取：这个I/O/CPU代价必须实测、预算并写入报告，不能隐藏成一次扫描或改用未声明的近似分位。

TSQR只对登记为分子能量参考的字段拟合，保存basis、rank、系数和rcond。TRAIN分子标量与heavy count的Spearman使用临时 `(value,heavy_atoms,count)` 表，在有效交集上计算精确平均ties排名；不保存record ID。生成热没有TRAIN元素残差参考时明确pending，不能把原HOF相关冒充修正结果。

非标量size相关尚需明确旋转一致的分子级聚合定义，当前保留pending，不拿xyz分量或数组索引伪装为分子标量。登记表的最终family冻结仍需这些结果及模型线接口意见。

`WinsorMoments`提供只影响统计、不修改原标签的Chan矩合并；`normalization_gate.py`要求真正冻结的共同人群membership和2万个TRAIN分子的PM7/S′诊断几何排除物理清单。仅ROUTINE角色冻结不能通过。

最终D4还需：将真实common/diagnostic eligibility侧表接入最终fit population，运行该population上的尾部分位、元素参考及逐元素缩尾矩，完成哈希/独立重建读回。当前流式异常fit不具备这个最终人口定义，代码和报告始终标 `normalization_completed=false`。

## 资源与提交步骤

所有任务是CPU analysis／compute20，CUDA可见设备为空。prepare/reduce默认16CPU、32GiB、1小时；scan默认16CPU、64GiB、2小时。统一Root intent绑定脚本、配置、所有源码及各阶段输入。启动前检查实际账户quota和全用户声明内存，结果后至少剩200GB。不会更改他人任务或占用GPU。

16个source task首波通过barrier，实际扫描manifest和reducer都要求16个不同worker PID；不能再把申请16个worker但只产生11个任务写成16实际worker。

每个worker使用小批源记录、受限压缩输出缓冲和RSS阈值。输出先在有界压缩buffer中完成，已知确切字节后在共享锁下检查整个run的unique inode bytes，再新建持久文件。目录和失败证据计入，拒绝symlink和指向run外的hardlink。DuckDB spill也有独立上限。任何失败设置peer stop，不开始新的源组；原值和partial证据保留，没有自动重投或删除。

Root依次物化 `prepare.sbatch.in`、`scan.sbatch.in`、`reduce.sbatch.in`，替换新路径及intent占位符。首次只运行pilot；full请求必须为非pilot，并绑定Root已验收的流式实测。full存储和核时要按新输出的mask、临时统计、审计和失败开销分别估计，不能仅按旧40-record试点线性外推。

语义测试入口：

```bash
python -B workflows/data_v1_final/labels/streaming_v1/test_semantics.py \
  --config configs/data_v1/labels/streaming_v1.json
```

它仅使用很小的合成parquet和已绑定解码器，不读真实科学label正文；包含16个实际进程的barrier测试。实际执行由Root在16CPU Slurm内完成。静态检查不等于这些测试已执行；合成测试通过也不等于512分子或全人群科学验收通过。
