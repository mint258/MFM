# 阶段5：架构候选实现与科学决策状态

2026-10-25（Asia/Shanghai），SA-4。状态：组件、整树与主树整合后回归均已通过。
412实际C0/55秒，2,162 passed/1 CUDA skip；合并44a543a后415实际C0/50秒，
2,231 passed/1 CUDA skip。精确源码SHA由各外部summary与前后校验绑定。
没有启动代理预训练，没有架构胜出结论。本文是实现交接，不是模型/配方冻结。

## 已接受的输入证据

阶段1报告由主agent在本地执行历史`4693dcd`接受：三型GPU原生S运行
4520365/366/367、九份trace分析369及汇总378均闭合。代表样本中dist_mlp
占kernel busy并集的72.7582%（3090）、78.7592%（4090）、76.0836%（5090）。
它支持优先实现共享距离编码；不证明当前峰值显存的因果主因，不足以选择架构。
原路径已经是tiled65536+checkpoint，不能拿未分块dense假想基线给新候选报收益。

所有决策沿用`DECISION_RULES.md`：只用下游TRAIN内层开发面板，S/P都要比较；
领先两项补第二seed，计算seed SD；不根据预训练损失单独选模型，不打开最终评价。

## 文件边界和旧路径

- `model/v3_architecture.py`：显式`ArchitectureOptions`及`build_architecture_model`。
- `phase1/v3_architecture_views.py`：显式两视图builder和`V3TwoViewModel`。
- `phase1/v3_architecture_training.py`：显式`ArchitectureStepTrainer`，复用原trainer的优化、追踪、检查点和两验证集逻辑。
- `phase1/v3_encoder_bridge.py`及两个dev-panel工具：仅增加显式新候选/新checkpoint opt-in，旧primary/historical默认门槛保持。
- `configs/model_v3/architecture_candidates_v1.json`：实现参数与待完成依赖，未宣告科学冻结。
- 三个`test_model_v3_architecture*.py`：控制、几何、梯度、checkpoint和监督边界测试。

未修改旧`factory.py`、`SharedBackboneMFM`、`backbone.py`、`attention.py`、
原三视图builder、loss、`V3StepTrainer`或数据线目录。C1-0直接返回所选legacy builder建立的模型，
没有插入新计算，旧state keys保留。正式S比较使用`build_source_s_architecture_model`，
其配置由`source_s_architecture_configuration`封印`v3_legacy_memory`：冻结
`s_model_memory_v1.py`的raw SHA和pair_rows65536。入口在加载前复核源字节，
C1-0实际保持旧tiled+每tile checkpoint；不能把未分块factory当成已测旧生产路径。
层checkpoint及A4头其余选项仍按完整model配置记录，科学比较必须与基线匹配。
C1-a/b替换后不继续保留误导性的`s_memory_implementation`实际模块清单，
仅将旧清单标记为`v3_legacy_control_memory_implementation`用于control provenance。
其他公共头、embedding、QKV、FFN、norm
沿用同一初始化；新距离模块的初始化被局部RNG作用域隔离，不推进全局RNG。
新C1仍通过`encode_atoms(batch)`返回按源原子顺序的`[N,D]`，下游H0不加入
任务门控或目标。正式候选配置D=512、layers=6；小维度只用于快速组件测试。

新builder已提供配置、checkpoint/H0和trainer接线；现有通用
`factory.build_model`不会静默识别这些新候选。不得只在JSON写一个字段而继续
用旧factory，然后声称跑过C1-a/b。新backbone的extra_state绑定全部C1选项，
已有训练checkpoint外部身份与配置校验仍须保留。
`configuration_with_architecture`把新选项封印进完整model配置，导出的
`config_dict().backbone_config`保留相同配置，拒绝显式options与配置冲突。
`load_encoder_pair`必须显式`enable_architecture_candidates=True`才可选择
新builder；匹配随机参考也走相同builder、同一科学配置。

新`ArchitectureStepTrainer(structural_views='two'|'three')`只在显式新路径启用。
它按2/3个物理视图计算padded-cost，保留原native-atom/sample预算口径；
在device copy与数值更新前检查实际view ID顺序和逐图原子数。C3的指标表和
source loss共同使用相同独立role mask，因此masked元素准确率、noise MAE/R²、
键级标签计数和梯度探针都进入原trainer的实际step/validation，而非只停留在helper。
contract绑定物理视图政策、encoder配置/options、encoder state前缀和实现文件SHA；
配置hash随之进入既有immutable checkpoint、resume和W&B lineage。

新v3 sample checkpoint进入H0需显式`training_completion`引用同一目录的
`COMPLETE.json`：同时核对payload bytes/SHA、bindings、配置文件raw SHA、
trainer contract hash、源码逐文件SHA、sample/update提交时钟及已知模型命名空间。
只提取`encoder.`前缀并严格逐key/shape/dtype/finite/extra-state校验；P/D头不进入
H0模型。沿用safe weights-only读取，不添加宽松state-dict或pickle fallback。
两个评估工具的JSON模板支持这两个可选参数，旧模板不增加默认字段，旧路由不变。
这些新集成已过第二轮组件，整树回归仍待完成；尚未运行代理科学比较。

## C1的精确定义

| 候选 | 距离编码 | 共享与逐层部分 |
| --- | --- | --- |
| C1-0 | 旧每层dist²→Linear(1,D)→SiLU→Linear(D,heads) | 旧模块及S tiled/checkpoint builder可复现 |
| C1-a | Euclidean distance→64 normalized Gaussians→Linear(64,64)→SiLU→Linear(64,64) | 一次共享pair embedding；各层Linear(64,heads,bias=False) |
| C1-b | 元素有序对的可学习scale·distance+shift，再走C1-a | 比C1-a多119²个scale和119²个shift；初始1与0 |

64个Gaussian中心初始等距覆盖0–8 Å，可学习；正宽度用softplus参数化，
初值对应8/63 Å，再加1e-5下界。8 Å是**中心初始化范围**，不是全局注意力截断。
距离与RBF计算显式fp32；共享MLP和层投影可服从外层autocast，几何输入不降精度。
有序元素对ID=`source_type*119+destination_type`，只取输入元素，包括实际遮蔽后的
元素，不读取`target_x`或其他标签。没有额外邻居搜索或删除全局边。

元素对仿射距离和归一化Gaussian形式参考
[Uni-Mol作者仓库GaussianLayer](https://github.com/dptech-corp/Uni-Mol/blob/main/unimol/unimol/models/unimol.py)
（2026-10-25读取，GaussianLayer与gaussian）。本实现的K、共享小MLP、逐层投影、
初始化与半径政策由本指南和显式配置确定，并非复现完整Uni-Mol。
两候选的共同pair MLP/逐层投影初始化逐位相同；恒定初始化的C1-b embedding不消耗
这条公共初始化流。各层投影不含常数bias，避免添加每头softmax不变的冗余常数方向。

### 半径语义

原已测配置`use_radius_mask=False`，真实注意力作用域无界；原`radius=8`未启用。
主agent已明确：全局版本`cutoff=None`保持与真实作用域一致，可以作为本指南C1
对应实现；不得暗中拿8 Å截断。Gaussian远端可能自然变小，但所有有效key仍参与
softmax与AV。若另启用有限radius mask，构造器只接受Gaussian cutoff与真实radius
完全相同；在共享MLP之后施加cosine envelope，使半径外pair embedding为零。
所有此类新科学配置仍须在实验前单独预注册，不能据实现配置宣称选中半径。

共享pair encoder在每次physical forward仅调用一次，层checkpoint只重算层内QKV、
投影和FFN，不重复调用pair encoder。共享`[B,N,N,64]`仍是显式驻留张量，不能
在没有真实三卡profile/容量测量前声称峰值显存或吞吐改进。

## C3两视图监督

物理图顺序为每个原分子`clean(id0), both(id3)`，干净P/D-only仍仅一份clean。
复用原`degrade_once(mode='both')`，其执行顺序为拓扑替换、再加Gaussian噪声。
显式保持拓扑强度0.3对应9%替换、几何强度0.2对应sigma0.1 Å，禁止删原子、
角度扰动和键长缩放。两个强度分开传入，不能因单个both模式level覆盖另一项。
局部CPU generator沿用`seed:ordinal:epoch`，不改全局Python/NumPy/Torch RNG。
both的几何随机流已在拓扑步骤后推进，与纯geom视图不逐位相同；这属于显式
C3输入候选，并非A类相同批次等价变换。

原`compute_phase1_loss`已原生支持id3同时满足geom/topo谓词。因此保留原损失：

- 元素仅监督both里`element_corrupt_mask`记录的真实改变；替换尝试未改变不监督。
- A4 noise监督both的全部合格原子，仍用干净`target_pos`及声明sigma。
- 键级仅来自clean正键，仍为原五类CE，无新非键采样。
- P/D预测头仅取同一次encoder forward中的clean H0、clean坐标和源原子顺序。

SA-2独立role-mask helper原来选择element id2/noise id1。两视图桥仅给该
**mask helper**一个sample_type元数据浅复制，映射id3到该role的旧标识；实际
source loss仍接收未变的id3。元素/noise各自的graph/atom资格和键pair资格
保持独立，不让一种任务的掩码误过滤另一种任务。原batch、腐蚀事实和标签不写回。
两视图model拒绝拿三视图布局冒充C3；三视图旧model和helper均未修改。

## H与C4复用

SA-2的`model/v3_heads.py`已包含H1线性、H2组共享MLP+逐字段输出、H3字段独立
MLP（默认hidden64）、注册表固定sum/mean和可学习sum/mean mixer，以及对称
pair标量、原子等变向量、图dipole向量/模长。C4复用这些显式模块，不重复造接口。
它们只读H0，原H0 API保持；径向Huber保持旋转不变。既有真实合成过拟合和
等变性报告见`03_labels_losses.md`；不能把固定随机H0过拟合当完整主干真实标签验收。

## C2分析项

默认A4不变。已只读核对旧指南与真实生产链，而非仅根据distance索引判断。
旧`user_repair_guide.md` raw SHA
`240b7b8132603517a7640662a5ea75e67371d5633e8a3c723ab148174c0b8fa3`，
第88–93行要求同样的查表模型在新TRAIN重拟合、FULL评估；其上下文和第9/59/91行
的指标是干净距离<2 Å原子对的局部键距RMSE，没有给出坐标输出定义。

冻结`workflows/s_denoise/refit_lookup.py`的`pairs()`返回codes、clean distance
和noisy distance三个一维原子对数组；TRAIN聚合无序元素对及0.05 Å noisy bin的
条件clean距离均值，最少32次观测。`evaluate_chunk()`的`predicted=noisy.copy()`
随后仅按code替换每对距离，未在该源链重建XYZ或计算ε/坐标RMSE。未命中的对
保留observed noisy distance并进入全部误差分母，不能称为删除失败对。

闭合`lookup_refit_closure_v1.json`绑定原任务4515527 COMPLETED/0:0、22691秒、
16CPU、TRAIN11,104,772记录，源result SHA
`c78df4d5206bb7b25b79a2f6011198ebdf26fac629b41aaab06a5a0b0e1034e6`。
其FULL 127,082记录/9,080,671对的pair-distance RMSE=0.0413792212 Å，
D3_FULL2000 18,486构象记录/1,319,881对=0.0412985903 Å；这可复用为历史
距离分析，不能写成同值的coordinate/noise RMSE。它使用旧TRAIN人口、sigma0.1、
view_seed0/epoch0和旧新noise-epoch政策，不是本轮6×512模型的匹配开发面板比较。
查表无主干模型参数，不能给它编造“同一6×512规模”。

当前指南新增“坐标级查找表”措辞，在这条已核实链中尚无相应坐标输出证据。
用户已明确选择“按局部几何分桶查表，预测三维去噪向量”，独立实现采用该定义。
详细方法、冻结参数及合成
证据见[C2_COORDINATE_LOOKUP_PREREG.md](C2_COORDINATE_LOOKUP_PREREG.md)。
当前未运行真实C2科学测量，不把旧距离条件均值推成唯一XYZ。
此项只用于分析，不作为C1/C3/C4验收门槛，亦不重启旧GUIDE_STOP工作流。

## 验证与待办

首次CPU测试4520398由主agent统一Slurm执行，五个文件实际58 passed，
pytest报告9.21秒，子任务完整墙钟14.4157秒、returncode=0；Slurm精确
Elapsed由主agent账本记录。包含两个新增测试文件及既有structural、labels、
vector_loss，覆盖：
旧C1-0逐位/state/RNG；共同参数初始化；平移/旋转、原子置换、padding隔离；
元素对响应、共享调用次数、坐标/参数有限梯度（含重合原子）；checkpoint梯度；
autocast内几何/RBF的fp32；全局/有限半径拒绝规则；两视图实际腐蚀、原source
loss/gradient、独立mask、clean-only键/P/D、无改变元素不虚构监督。

源前后SHA相同，外部证据`runs/model_v3_20261025/unit_checks_4520398/summary.json`
和同目录`sa4_architecture.json/.xml/.log`。两个新模块SHA分别为
`fe1bee9f3a29571a73dd2655a49b7b31c56819774058f2260bca5cfba9bcb02f`、
`a8de5b69ecc57cccacd450c17444f3e557e8ab2fd2d6d5638682cb11b12b26a8`。
本轮测试在提交前绑定实际逐文件SHA，不把基线4693dcd说成新源执行提交；
checker、提交和整树suite由主agent统一完成，后续commit另记。

可执行集成后的4520408实际子任务returncode=0，59 passed（pytest32.41秒，
完整子任务36.7815秒），源码前后SHA相同；父Slurm状态/成本以主agent账本为准。
证据`runs/model_v3_20261025/unit_checks_4520408/sa4_architecture.json/.xml/.log`。
本轮覆盖architecture、architecture_views、architecture_training、encoder_bridge、
trainer、experiment_tools六个测试文件。新测试实际执行C1-a/b两视图优化、
masked元素/noise/键/P/D真实指标表、按2/3视图不同容量、两种C1的完整resume
（模型、AdamW、输入/随机状态、验证/日志cursor、梯度探针逐位相同），并实际
写入512×6完整sample checkpoint再通过safe bridge加载encoder及独立匹配随机模型。
缺COMPLETE、同形异配置、坏源码绑定、未知state命名空间和错时钟均实际拒绝；
旧CLI默认不增加opt-in字段，生产S builder的旧tiling65536模块与source SHA已核验。
398是较早纯组件源快照，不能拿其SHA冒充集成后的408源码；两个版本的证据均保留。

未运行三卡新候选测量、
D-3逐字段过拟合或代理科学比较；D-1/D-2/D-4/D-5未交付时不发明数据契约或
240k子集，不因实现测试通过接受任何架构。600万sample预算的平台确认、候选
开发面板分数/seed SD、速度和显存容量仍按指南在整合后的真实实验中决定。

C2 coordinate lookup analysis is now reported separately in05_C2_coordinate_baseline.md:
fixed1024 PRETRAIN_VAL evaluation603 and independent SDK/report606 both actualC0.
Prior parameters belong to TRAIN559; component RMSE0.0654994134A and vector
RMSE0.113448312A use all55,650 atoms. This does not select a denoising head or
compare the old pair-only0.0413A as coordinate RMSE. Real model C2/SDP comparisons
and seed-SD-dependent architecture decisions still require the data-line inputs.
