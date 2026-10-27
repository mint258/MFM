# 数据线实际进度 v16（2026-10-27）

本次完成了原生字段证据复核、独立 NEW20 输入准备和 Drugs 全原生结构核验。D1–D7、P′、完整去污染及第一批扩充仍在执行，未开最终 PR；本页是实际执行快照。

## 实际结果与范围

| 工作 | 已完成的实际结果 | 后续边界 |
| --- | --- | --- |
| 原获准15次P′诊断 | 4523473 C0，15调用、25原向量比较及5同几何检查通过原容差 | 原15FAIL保留，原因不强推；2000/full仍HOLD |
| NEW20输入准备 | 4523779 C0/60s/16CPU13，20唯一MID×12任务×5臂=1200输入；16真实render线程；original-init1、candidate-init0、invoke0 | 从1000MID中780个1–80atom eligible选20；220>80仅本QA不可用，不据此排除生产人口或外推成功率 |
| 新执行器与原生汇总源码 | 4523855 C0/31s/16CPU15，两组各3 pure，共6 PASS、0skip | 执行器已完整接入，下一最多1200调用需新的用户限定授权；未启动新QM |
| native32定位 | 4523878 C0/75s/16CPU15，384份原证据完整SHA/fstat，冻结384 input bundle locators | 定位阶段未打开input/raw，也未重新读17GB旧档案 |
| native32数值/域汇总 | 4523953 C0/120s/16CPU15，384完成、0held；每条件32条input绑定和原parser完整复核一致 | 单位、符号、property axes仍待官方调用链和共同审阅；不是full20k原生审计 |
| Drugs全原生图 | 4523818 C0/1579s/16CPU14，1000旧C0直接采用、557002新增，共558002；未检查/技术unknown/比较unknown均0 | 126条涉及31个名称的native/source key差异保留全部并集；不修复、不化学剔除、不据此放行全候选池 |
| 旧标签窗口与新book | 4523621 C0已核448窗口；4523763的CPU13只读采用/新book创建仍在运行 | 旧1904 TIMEOUT及费用、两个RESERVED窗口和原32GiB逻辑账本保留，不能把新C0当旧任务完成 |
| TRAIN512数值缓存 | r0、r1、r2、r3四轮均实际C0，4251记录/512MID/146字段；r4已提交4523971到CPU18 | 仍是源TRAIN median/MAD诊断及legacy parity，非最终Common D4 |

native汇总的r73仅pm7_B适用：114356个原条目、3574个onsite，样本中duplicate key为0，原通道双端和ordinal完整保留；另四个PM7条件的128条原本N/A且没请求PI，不计新质量失败。r674只有xtb_singlepoint的32条适用，六分量及原顺序全部保留；打印Decimal trace恰0为21/32，其他11条原样留存，未做trace投影、未推定残差幅度或新容差。192条有原输出坐标比较，逐float64完全相等为0；另192条未发射独立坐标。input/parser一致不能替代property-axis验收。

Drugs全源的6件DATA均在CPU作完整SHA/fstat，ZIP所有成员EOF/CRC/SHA闭合，558002个旧source-key结果不重算。75099个名称、290个多SMILES组及所有原SDF记录保留。新输出实测6766849242B（receipt前），低于12GiB范围；新1000图未重复执行。

S′有限CPU13链继续：截至本次观察，wave2已有101批/50500包闭合；旧95与新96均各500包、无未知。后续仍沿原179批计划、种子、参数和once继续，不重提运行中的科学任务。整体共同人群及N1扩展尚未最后验收。

## 双集群与有限资源授权

Alpha原PubChem控制器21921保持原绝对deadline1793149349.1500428。本次保存的12:22:59 UTC点为32000000原始行：accepted29870535、chemReject2126183、technicalUnresolved3282；technical独立保留。历史actual_parent_ids含失败和QA，不能当成功分片数。

新的手动有限epoch协调层10件已独立安装；1884950实际C0/33s/16CPU6通过3项源码检查，未运行科学DATA、Budget、pool或ordinal claim。已在旧控制器仍live时固定PID/UID/boot/start/argv。还没有新grant/cutover/live：未来必须由Root另行签≤20h新grant，原deadline后旧身份停止、全局锁和稳定终态证据齐全，再逐原grant采用实际闭合/运行父件、observe-only后有限live；不自动续期，不改原13件科学源、旧grant/state/claim，不把未知退出码写成0。

COCONUT全物理身份任务1884790仍在运行，不读取其active SQLite或journal。QM7b官方2013ZIP及被动格式扫描已C0，3个opaque UTF8+1个XYZ；没有从文件次序或7211推MAT行关联。Main作者XYZ保守composition任务4523546也已C0，图/key未知与composition策略分开。

独立账本点：Main44为551个已注册唯一父任务、507.41777777777776分配核时；Alpha42为177父、1316.2044444444443分配核时。两点不是同一时刻的最终总账，不能把历史快照相加；之后新父件及失败/启动费用继续附入。免费集群没有货币费用，核时仍如实报告。

空间重新核算只退休已TIMEOUT、observer闭合且旧文件帧不变的1904的未来物理writer预算；原32GiB逻辑账本、UNKNOWN收费、历史数据和核时均不返还或删除，也不授权重启旧writer。全部182个S′cap及200GB配额余量保留。NEW20具体提案仅是32GiB共享上限/16CPU/24h/900s/调用的限定QA，local scratch为软观察，不宣称硬总限额；未获新用户决定就没有可执行QM spec。

## 与模型线的实际新反馈

当前D1权威仍draft3，draft4/5是提案。模型公开精确commit1f7f255fd412cd53ce7f6913ddbb43645d9f9ee7已包含draft4条件审阅，状态为MODEL_REVIEW_RECEIVED_CONDITIONAL_DOMAIN_DESIGN；不能再说没有新审阅。22项Model引用中20项同字节，11件关键consumer全部与原冻结/当前工作树同字节；local branch ref3d9b1cc与公开commit不同的事实保留。

已接收r73有序双端channel/onsite/ordinal、F64版本边界，及r674行坐标旋转约定/Frobenius-radial/TRAIN单尺度/partial-mask的共同设计条件。实际consumer仍拒真实VAL/authority、basis、tensor及真实child-view；条件审阅和原synthetic provider PASS都不能代替实现或真实D3验收。见[draft5](../interfaces/training_format_v3_draft5_native_consumption_joint_review_proposal.md)和[公开精确HEAD补充](../interfaces/training_format_v3_draft5_public_head_addendum_v1/ADDENDUM.md)。

## 可复现证据与下一步

当前已检查且公开的源码仍为v22：execution35f1a671c996ba27e897a03a84ab534a8def547a，public77b30228e21f6ec0d716a3fc3a2c5b59c7a365a8，tree ec44c0882eaf9769f733a1c298c765466534df2f。Source28的3379源文件/35800918B、原checker和27+3检查完整通过；新源码将按下一Source29整体检查后提交。未将新包的SourceOnly交付当实际科学成功。

外部运行根为`/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025`，与X盘完全同一目录。主要小证据：

- `control/root_actual_pprime_new20_zero_invoke_preparation_review_v1.json`及`control/pprime_new20_concrete_user_review_v1/actual_prepared20_user_proposal.json`；
- `control/root_actual_native_summary32_384_technical_review_v1.json`、`artifacts/labels/source_status_v1/native_frame_summary32_v1/summary_v1/manifest.json`；
- `artifacts/expansion/marcel_drugs_native_graph_full_v1/full_v1/receipt.json`及`control/accounting/drugs_native_full_cpu14_4523818_actual_C0_v1.json`；
- `control/alpha42_manual_epoch_source3_small_metadata_transfer_verified_v1.json`的17件逐字节传输闭合，含Alpha source3/实际身份/账本/原grant及事件；
- `control/root_pprime_new20_concrete_proposal_resource_review_v2.json`；原始输出、全部DATA和完整哈希清单均在仓库外。

下一阶段继续D1原生定义/共同审阅、D4无损紧凑cache的实际512对照及全源覆盖、D5真实入口与共同人群/N1收尾；1.6正式统计仍须TRAIN-only元素reference、0.1/99.9分位缩尾的mean/std，median/MAD不是最终normalizer。扩充继续全PubChem筛选/去重去污染、1M基线与准确NN、1000万有序R/N和10000 UFF+D试点，再按实测批准首250万；无扩充QM。全部原质量阈值保持，只有用户已批准的Se例外及核时报告后继续。
## 本页冻结前的实际闭合补充

- 标签恢复 seed **4523763** 已实际 C0/3225秒/16CPU13，分配核时51600核秒。CPU核验完成448闭合区间的只读采用，新 sidecar 1951233行/82703589字节且已重新打开校验。原5@57685、17@58540仍HOLD，旧1904仍TIMEOUT、旧账和未知消耗原样保留；新book不是原全量成功。
- TRAIN512 r4 **4523971** 已实际C0/158秒/16CPU18；r5已提交 **4524045**。这仍是源TRAIN诊断缓存精化，不是最终D4。
- Drugs全558002原生图的小件、源链和实际会计已由Root接受，范围仅为保留全部来源/native full-key并集；126条差异/31名称、290多SMILES组原样保留，尚未放行全候选池或全局去污染。
- 固定384条原生标签的[D1实际证据补充](../interfaces/training_format_v3_draft5_actual_native_summary32_addendum_v1/ADDENDUM.md)已独立加入；保留物理定义、全20k、共同冻结和消费者实现各自未闭合的边界。