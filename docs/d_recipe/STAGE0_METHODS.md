# 阶段 0：数据与接收接口（实现中）

以下描述已经写入代码的处理路径。215项新增逻辑测试已通过；全量数据、真实 loader 接收和科学结果尚未完成。过滤规则以数据分支 `configs/data_d_descriptors/preregistration.json` 的预注册为准。

## 输入与人群

沿用 P 的 TRAIN molecule_index 清单（1194228，含原有 323 项排除），通过既有 compact ID map 对应 molecule_id。VAL 使用原 common membership 中的 VAL/ROUTINE；额外 VAL 诊断只从已登记 D5 与该角色的交集取得。TRAIN 的诊断标志不会将该分子移入验证统计。原始角色、索引和分子 ID 保留，不引入 TEST。

原始 SMILES 从只读 native pointer 取回，二维图采用原 D20 的 `Chem.MolFromSmiles(stored_smiles)`。不从 Z 和键列表猜测同位素、电荷等状态，不增加盐处理或加氢步骤。原 D20 代码中的 `AddHs` 属于 D3 几何计算；本线不会据此改变二维图。源图无法读取的记录保留人口，显式记录原因，不能补成零。

5000 TRAIN 成本面板先从固定随机候选集按重原子数、元素集合、环和分支复杂度分层，冻结 ID/SMILES 后再算描述符。源图缺失记录在 UNKNOWN 层保留。全量计算复用该面板已关闭的结果。

## 描述符与存储

- L1：固定安装版本的 RDKit 二维标量描述符，按字段名排序。与 D20 同名的字段保持原启用状态和原参数。
- L2：`Calculator(descriptors, ignore_3D=True)`。这是 [CheMeleon 作者代码](https://github.com/JacksonBurns/how-to-train-your-chemeleon/blob/main/features/_mordred.py) 使用的字段构造方式；生产时记录实际 1613 项名称、顺序、对应索引和软件版本。这里仅对齐目标库定义，输入图处理仍遵守本任务书的 D20 口径。
- 新库原值按 F64 存储，统计使用 F64；以独立 uint8 状态区分 missing、valid、实际非有限/溢出。真实零保持 valid。字段过滤、归一化和损失截断均不覆盖原值。
- 每库按固定分块写入 memmap；数据同步后才关闭该块的检查点。恢复复用已关闭块，只处理未关闭部分。不生成内容哈希、独立 QA 或收据。

L1 的共享 D20 数值直接取原 compact 分子记录，不调用描述符函数重算；新字段才在原 SMILES 图上计算。L2 不跨库映射。原 F64 值保留；超过既有 FP32 原始头传输范围的值作为实际溢出事件记录，不通过拟合阈值截断成合法值。

## TRAIN-only 统计

常数、有效率低于 95%、实际非有限/数值溢出的字段按预注册过滤；每个字段记录有效率、真实零、missing 和去除原因。新字段用精确 type-7 q0.001/q0.999 缩尾估计均值与总体标准差（ddof=0），原标签不截尾。现有 D20/D3 的 11-07 参数原样复用，零尺度不以任意 epsilon 替换。

训练只在损失计算时把标准化目标截至 ±6，各字段记录 TRAIN 被截断比例。L1/L2 不作为嵌套库解读；尚无结果支持任何库的收益结论。

## 接收与后续

生产过程执行一次身份、字段次序、角色及 mask/零/常数检查。消费者以只读 mmap 精确按 `(split, molecule_index)` 取批，并沿用冻结字段顺序与参数。原子 SASA 继续走原 loader 和源 atom ID；宽库不重建该映射。

真正的接收验收仍待执行：真实 loader，64 样本、冻结编码器只训新头，loss 低于初值 1%；以及任务书规定的 SASA 对应检查。单元测试只覆盖新增逻辑，不能代替接收验收。CPU 作业仍排队，尚无成本、字段过滤统计、下游特征或过拟合结果。

接收入口为 `tools/d_recipe/acceptance.py`：冻结随机 C1-0 的 H0，只在同一 64 分子缓存上以 F64 最小二乘拟合原生 H1 分子标量头，再转换回实际 raw-output 参数，通过真实模型预测比较逐头 Huber 损失；标准化标签仅在该损失目标中截至 ±6。阈值为初值 1%（严格小于），绝对数值零容差 1e-12；未通过记为接收未通过，不立即伪造 UNRESOLVED 或交付完成。SASA 核对原 compact 的 atom-label 行与原子序列，不重建原子顺序。

## A1、训练与判定接入（尚未运行）

环境/新增逻辑已在 compute-0-17 通过显式原生 SSH 单核短程模式：215项、OK、exit0，原始日志为项目根 `D_native_cpu_tests_20261120_1622.log`。测试复用已有 pyarrow25.0.1 CPython3.11 deps；未改共享环境。实际 NFS 设备锚定 `/share/home`，配额发布器中的 `/share` 仍是服务器端账户作用域，不能将计算节点的本地 `/share` 目录设备用于比对。小型测试夹具用已核实根盘容量的 `/tmp`，峰值16MiB，每项测试前检查可用字节/inode及 max(10GiB,10%) 底线。此结果只验证新逻辑，以下实际科学流程仍待执行。

A1 收集复用 P 的既有规则：独立 `default_rng(20261112)` 分别决定完整 TRAIN 分子排列与每分子的一个允许构象。原始标量、native Z（含实际 H）和 valid mask 分块写入可恢复数组。五折共享同一分子折号；岭强度、折号 seed 和模型名称由训练预注册明确供给，当前未拟合或选参。OOF R² 的 0.30/0.999 分档严格依任务书；不足 100000 有效 TRAIN 分子的字段保留原目标并明确未解决。

只有残差分档产生独立的 A1 派生参数：F64 减冻结元素参考，再按 D4 的 type-7 缩尾方法估计残差位置尺度；原 11-07 D4 与原目标分档逐值保留。逐字段报告 TRAIN ±6 截断比例，原始存储不改。

训练使用进程内适配器包装既有 P 循环，不复制或修改 P 文件。三块聚合、空块为零、G1 不重分配权重、K1 独立 RNG 与计数均纳入检查点条件绑定。宽库额外构建原生 D20+D3 初始化参照，共享头/PMA/投影器同键同形张量沿用原生初值，宽库新头保留新初值，全局 RNG 恢复到原生初始化完成位置，抽样 RNG 独立。

R1/R3 和 bootstrap 复用 `tools/p_recipe/evaluate.py`，结果写入 D 目录。旧 P helper 的 LOSS 还要求负效应量达阈值，D 4.6 明确只要求 CI 上界 < 0，因此 D 包装器按该明确文字覆盖这一处分档。两种子逐个 WIN 才采纳，不以合并种子 CI 替代。D-G1 删除规则按“只有 CI 跨 0 才采纳”执行；整体正区间如实报告并保留 D3，不自行扩展删除条件。

`compare.py` 消费已有分数与原分子 bootstrap 群，要求 R3 完整覆盖冻结七任务、同 1000 抽样/seed/置信度且分子群一致；不重采样。`seed_plan.py` 只由同一 seed0 的 WIN 比较生成 seed1，按科学臂共享对照；基础设施续跑更名不会产生第二条同条件对照。9M 不生成 seed1。K1 的 seed1 专用掩码 seed 须由预注册显式提供。这些接入逻辑尚未运行。

全量存储预算将在成本测试后按实测分项配置。当前成本面板预留峰值 4 GiB；目标节点字节/inode 和既有实时 UID 配额保护、100GB 账户余量均保留。联合预算按真实文件系统分账：114569896448 字节的模型总峰值（其中含 P61GB）登记在 `/lfshome`，不扣除 `/share` 空间；NFS 模型未来量沿用原 guard 的 23179869184 字节，加已登记 seed1 的独立 2GiB。NFS 另计 B0 两组 P′各 80GB 预测减已占物理字节、24GiB 环境余量、额外元数据余量；未关闭的几何生产保留预测，只有已封存且有原生成功闭合记录的几何才退掉未来写入预算。不在 `/tmp` 复制输入数据库。


正式运行入口（未运行）为模块命令 python -B -m tools.d_recipe.resources train --configuration <Root冻结配置>。资源包装复用数据线 Guard 的自有子进程暂停/恢复，不复制进程控制；每 5 秒核对实际根分区与 NFS，根分区保留 max(10GiB,10%) 和写入缓冲，NFS 刷新当前 UID 配额及 B0 等剩余联合预算。内部训练模块为 tools.d_recipe.train。它调用既有 D 训练适配器与最终 R1/R3 读出，只调度该运行的预算终点，不新增中途探针；已关闭的训练和读出从生产者状态继续复用，完整交接立即返回，不覆盖为完成。bootstrap 留给 CPU 命令，GPU 完成状态只记等待 CPU 统计。整卡功耗采样复用 P helper，并将其输出前缀定向到 D；Root 仍须先完成训练预注册、P依赖、臂/seed判定，以及实际节点 GPU/存储准入和运行期保护，当前不提交 GPU。

CPU 收尾命令为 python -B -m tools.d_recipe.resources cpu_statistics --configuration <同一冻结配置>：只消费已关闭的最终 predictions，复用既有 bootstrap；scores 已存在时不再抽样或追加 CSV，结束后才把该运行记为统计完成。已完成的运行不降级或重跑，配置的科学条件必须与原运行相同。新增入口与收尾测试已通过 215 项新逻辑套件；真实训练和统计收尾尚未执行。

资源适配的新逻辑测试覆盖：监视 NFS 输出时仍核对根盘、每轮刷新联合未来量、根盘不足或真实配额/容量未知均进入原有暂停路径。这些用例已通过新逻辑套件；不新增发布器、过程收据或其他线写入。

宽库新增目标在归一化时先对 F64 原值执行减中心、除尺度，再转换成 FP32 训练目标。不能先把接近常数但非恒定的新字段舍入成 F32，丢失其真实变化。复用原 loader 已有的 F64 算术路径，选择器只在调用局部生效；原 D20/D3 的既有路径、冻结参数、原值及缺失状态保持原样。该算术模式纳入目标检查点条件绑定。新增近常数用例覆盖 raw=1+2^-30/1+2*2^-30、center=1、scale=2^-30 的差异；用例已通过新逻辑套件，并不是科学结果。

Mordred 的 Missing/Error 对象由 MissingValueBase 显式识别，其 float 转换会返回 NaN，不能据此把普通缺失误标为实际非有限值。正常缺失保留 missing 状态；对象中明确包装的 OverflowError 仍记数值溢出；直接返回的 NaN/Inf 记数值事件。该修正执行既有过滤规则，没有改变 95% 阈值或增加新过滤条件。新增分类用例已通过新逻辑套件。接口依据：[Mordred error objects](https://github.com/JacksonBurns/mordred-community/tree/main/mordred/error)。

## 表示诊断接入（新逻辑测试通过，真实诊断尚未运行）

`diagnostic_forward` 复用 P follow-up 的 `diagnose.validation_indices`、严格 encoder 加载和第 3–6 层提取函数，不调用其任务入口或写其 CONTROL/RESULTS。仅接收 D-R0、D-R1、D-G1 和实际采纳臂的 seed0 3M 终点。固定 5000 VAL 的全部允许 k10 构象只做一次前向，保存 F64 mean(H)，并按原始原子顺序保留每分子首允许构象的原子 H。分块 flush 后原子替换游标；已有完整缓存直接复用，基础设施中断从已关闭游标继续。未增加全层探针扫描。

`diagnostic_statistics` 只在 CPU 8–19 的真实分配上执行，复用 `collapse_composition.py` 所调用的原 `composition_statistics.py`：原组成基底含显式 H 的元素计数、总原子数和重原子数；原五折嵌套 ridge、CEV、CVF、CVF_res 不变。一次生成 1000 次分子 bootstrap 权重（seed20261025），所有层和指标共用；不重新拟合 OOF 预测。参与率点值沿用原总体协方差的谱公式，区间用相同分子权重和精确 F64 原子矩，按 trace(C)^2/sum(C*C) 计算同一谱量。原子参与率与 mean(H) 参与率均基于首允许构象，不把原子当独立重采样单位。闭合统计直接复用，不重复前向或抽样。

入口为 `python -B -m tools.d_recipe.resources diagnostic_forward --configuration <Root冻结配置>` 及 `diagnostic_statistics`。目前没有诊断作业、前向缓存、指标、成本实测或完成结论。实际提交前单独登记这些输出的联合峰值：缓存数值字节为 4×512×8×（允许构象总数＋首构象原子总数），另计 panel、原子替换临时文件及其他未完成 D 写入；不把它们偷偷放入现有阶段 0 的 14GiB 预算。CPU 的每层重采样外积累加器约 1.96GiB 内存，不落节点临时盘。累计 4 小时或连续两次实际失败仍按任务书 UNRESOLVED 处理。

逐层 R1/R3 也按原 P 的固定层3–6接入，不增加1–6全层扫描：显式设置 `diagnostic_feature_root` 时，在既有开发面板末层前向中同时保留已计算的3–5层；模型工厂与特征生产函数在进程内包装，结束或异常均还原，原源成员、atom ID、n_ref和末层H0不变。不开启该字段时沿用原路径。各数据集原子顺序只由该生产步骤对齐一次，缓存按checkpoint/run/store绑定并原子关闭；重复调用读取关闭缓存，旧末层缓存缺少中间层时不补跑编码器。

`layer_readouts` 的GPU阶段只对D-R0、D-R1、D-G1及实际采纳臂的seed0 3M终点读取关闭的3–5层缓存，直接调用原P的R1/R3循环；6层复用主读出。CPU阶段复用原分子bootstrap，6层复用主统计，不重新采样。两阶段分别以配置 `phase=gpu/cpu` 通过资源包装执行；结果放诊断自己的 `layer_scores.csv`，`decision_input=false`，不能参与配方选择。潜在采纳臂只在原前向中保留已有中间张量，采纳决定前不拟合诊断探针；新增缓存峰值须在提交前单独登记，现14GiB阶段0预算不包含它们。尚无真实逐层诊断结果。

该接入后新逻辑套件扩展到223项并在CPU17实际全部通过（原始日志 `D_native_cpu_tests_20261120_1638.log`，exit0，总7.42秒）；包括单次前向、缓存恢复、原子顺序、默认路径与异常恢复、主末层读出/统计复用及未采纳宽臂不做探针。未运行全仓库回归或仓库检查，仍仅在开PR前执行一次。

开发D3的 `development_d3` 以原member自身source-frame图和原生Z/F64坐标调用既有 `downstream_science.geometry_descriptors`。分块保存六分子D3 F64/u8、独立逐原子SASA F64/u8和源atom映射，游标闭合后复用；不合并同MID的不同member几何。氢政策必填且尚未选择，不缺构象重嵌入。`append_member_d3` 只按原完整member UID或(dataset,record_id)纯连接，保原molecule/split、顺序/重复及0/缺失/numeric-event；不读文件、标签或重新计算几何。可选标准化只接受原TRAIN六参数，F64仿射且不截尾；PBF字段沿原D3.PBF_A命名。原子SASA不追加到分子向量。新增11项用例后共244项通过（CPU10真实4537508.step0单核，总6.63秒），仍无实际D3生产或A/B/C结果。
