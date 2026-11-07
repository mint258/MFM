# D1 / D3 / D5 消费边界复核，2026-10-26

本次仅静态读源码和小型既有验收记录；未运行 Python、模型、科学解析、SSH、Slurm 或 Git，未修改模型树、Root 契约或 STATUS。没有生成双方签名、最终人口、正式标签或真实 D3 验收。

下文 D 相对 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/`，M 相对 `/share/home/zixiao/descriptor_analysis/MFM_model_v3/`；行号为本次读取时的源码行号。
为简写，D 的 `wire_v1/`、`pipeline_v1/` 均位于 `workflows/data_v1_final/export/`；M 的 `phase1/`、`model/` 均位于 `current/phychem_mfm/`。未另列目录的模型 `v3_*.py` 指同一 `current/phychem_mfm/phase1/`。

## 已有新证据

D1 仍是 draft.3。D `docs/interfaces/training_format_v3.md:3,148–160` 已有 Codex A 审阅意见；这是模型线反馈，未共同冻结 v3.0。D `workflows/data_v1_final/export/pipeline_v1/export.py:298–303` 的正式入口仍要求 `MODEL_DATA_JOINT_CONTRACT_FROZEN`、version3.0、model_confirmation/data_confirmation，以及共同接受的 `field-set+sparse-leaf-v1`。现 registry 的实际状态为 `DRAFT_METADATA_MAPPED_NOT_SCIENTIFICALLY_FINAL`。

模型候选 consumer 已实现并实际测试，不能再概括为“provider 未实现”：

- M `docs/model_v3/results/candidate_interfaces_20261026_v1.json`：4521005 的四项 A→DataB projector/真实 MFM3 LMDB→provider/collate→原 trainer 合成贯通全部通过；scope 明确是 PM7 synthetic，UFF 只为未导出 locator 的索引元数据。`overall_guide_complete`、`formal_data_acceptance`、`data_line_final_D1_D7_delivered` 均为 false。
- 同记录及 `wire_provider_postmerge_v1_complete.json`：A+B 整合八分片共2475项，其中2473 PASS、2 CUDA skip，104文件，0failure/error；不能把两项 skip 宣称 GPU 验收，也不能把合成结果当真实 D3。
- 当前 M `v3_wire_provider.py` 为22752B / `80c728c157205ca1e9870d511751efc6b87a7c59c795d28a6911c313610c2ea8`，与其 source inventory 一致；当前 `v3_sampling_bridge.py` 为21527B / `2c15a8b61fa5b071d3e64cd8f769a8e43930174dbaa0555e70a1ef233809d946`，与候选桥文档一致。本次未推定整个模型工作树等同于旧执行 commit。
- 模型 provider 固定的6个 DataB 文件（wire codec/mapping/store、granular_store 及两包 init），本次逐项实际源码 SHA 均一致。DataB sampling projection 当前 SHA 为 `50aceee73de4718b7f35dbd2a37a207a7739d57f8ed53f39a36da16bfbc0e2dd`，仍与模型 typed bridge 的显式源绑定相同。

D `docs/interfaces/STATUS.md:19` 的 provider 待办应细化成“候选已测、真实 authority/VAL 及物理目标接入未验收”。本次不回写旧状态记录。

## 最小剩余证据矩阵

| 项 | 已有实现与精确路径 | 真正缺口 / 下一证据 |
|---|---|---|
| D1共同签认 | D 契约148–160已有模型意见；export.py298–303正式闸门存在 | 双方共同定稿的字段/物理目标、shape、单位、frame、codebook、D4/D5、shard/schema哈希及确认记录。候选测试和模型审阅意见均不代签名。 |
| r674 tensor6 | D `wire_v1/mapping.py:79–87,99–115,172,187` 支持 xx,xy,yy,xz,yz,zz 的 symmetric6/对称3×3与分量 mask | M `phase1/v3_contract.py:21` 只有 scalar/vector/magnitude；`phase1/v3_wire_provider.py:144–148` 明确拒 tensor。需共同确认原点、无迹定义、frame、归一化/loss，再由模型线实现消费。不能拆六个不变标量、删第六分量或单边选尺度。 |
| 原生frame / 实际扰动路由 | D 契约67–81要求原子序、原坐标轴和真实扰动坐标；D exporter以parent/view分区（`pipeline_v1/export.py:213,229,257`） | M provider146–148、235–237只接受base、parent/view为空；M `model/v3_multiview.py:55–65` 的PD仅读clean H0，`phase1/v3_structural.py:129–153`的S geom是另一个本地噪声视图。r623/r624/r625须绑定实际child坐标/hash/parent/协议并由模型线增加目标视图路由。当前原生frame/P′科学验收不能由字段shape替代。 |
| dtype/shape/Z与索引 | D 契约85–89、codec50–69、mapping130–195；M provider269–275、300–302已有Z→long[n,1]−1、fp32坐标、scalar/vector reshape及每字段pairs转置；M `v3_data.py:190–225`逐字段加atom offset | 这些候选实现不是空缺。缺最终逐字段selector/target mapping和真实值读回；需绑定实际source atom-order证据。M provider243–244要求的是test-only `model_fixture_atom_order_sha256`，真实D3不能靠复制这个标记冒充科学证据。各pair对角/方向规则仍须共同接受；当前collate203–205拒所有对角pair。 |
| 独立source ID/order / diagnostic | D `sampling_projection_v1.py:59–147`；D materialize.py167–172对诊断base及child anti-join、重排training_rank；M `v3_sampling_bridge.py:196–285`重核原输入及保留energy training_rank0 | 此桥已完成合成双向消费；不应再写为4个gap均未实现。真实D5需冻结common/geometry/三种order、diagnostic/subsets，并保留原training_arguments证据和表SHA，不能只交投影的minimum字段。M bridge304–305、343–351只在candidate里拒不足k，并未决定N=1/N=2及诊断后不足数的最终科学政策。 |
| reason与exposure | D granular_store保留source/new/review field sets、sparse leaf、uint16/65535；M provider276–290与`v3_wire_audit.py`已有独立CPU审计，all_components用于模型row validity，group/family exposure另记 | 不是缺provider sidecar。缺最终共同codebook/hash与真实记录读回；D1 mask段还需明确field集合与稀疏leaf粒度，不能称稠密逐叶完整因果。 |
| r73 basis / r82 atom scatter | D `pipeline_v1/source.py:105–147`已显式atom_indices scatter及缺失原因闸门，source_v2保留每字段动态n_pairs | M provider258–261拒basis_i/basis_j或sigma_pi_entries，普通atomic pair不能表示r73完整basis身份；不得去重/求和。r82仍需最终selector、索引基数和codebook，真实全原子消费读回；不能贴前n_heavy行或补有效零。 |
| P/P′条件D4 | D 契约56,142及158要求P′独立TRAIN统计；M `v3_losses.py:77`按model field name索引，`v3_contract.py:148–153`已要求vector零中心/各向同性尺度 | 单来源可绑定一套条件统计；同batch跨condition须显式路由。全共同人口、诊断排除及最终field/family尚未冻结，现有试点/标签分片闭合不替代最终D4。 |
| 真D3/VAL/no-pickle与D6 | D codec1,50–128为MFM3 JSON+little-endian arrays，无pickle；候选FamilyReader/COMPLETE/mask事务和模型本地只读句柄已有实现 | M CandidateWireFactory120–122只接受explicit opt-in +synthetic_fixture；provider235要求TRAIN，真实data_line和VAL硬拒。D exporter161–203要求正式D5与50k TRAIN+5k VAL；正式全量入口170–172还要求先有真实pilot模型验收。必须新增被双方接受的真实release adapter路径及真实1万条源值比对/16worker读回/本地磁盘容量和SHA/吞吐证据；不能只把authority字符串改为data_line。 |

## 可继续的数据侧最小源码方案

已有六个被模型固定 SHA 的 reader/codec 文件及 sampling projection 不应为这次状态核对而重写；其现有合成覆盖也无需再写镜像测试。本次未改这些冻结源码。

1. 下一新增数据模块可限定为 `workflows/data_v1_final/export/consumer_binding_v1/` 的小型 **绑定清单构建/预检**。输入只接受实际且已共同确认的 joint contract、registry+physical mapping、D4每condition、D5三order/diagnostic/subsets、source/atom-order/codebook/shard refs；输出保持真实状态或拒绝，不生成签名、物理规则、训练人口或假fixture atom-order收据。最终manifest字段应先由双方确认，不单边把模型toy manifest定义成D3标准。
2. 对当前已支持的base scalar/vector，可用原FamilyWriter/granular store生成明确synthetic_fixture的小型中立交换包，交Root在实际模型provider跑消费合同测试。只增真正缺少的跨线断言：source-native ID/诊断最低能、两来源重名不合并、逐字段pair transpose+offset、partial component validity/65535/source-new-review/exposure分离、一次fp32转换/负零。不要重跑镜像codec测试充当真实D3。
3. tensor6、basis和真实perturbed view先只形成“源数据完整保留+模型明确拒绝”的审计，不伪造正向消费PASS；对应科学定义/模型实现完成后再追加真实正向合同测试。data-only代码不能修复模型head/H0路由或替双方决定物理归一化。
4. 生产/试点入口另新增薄main CPU startup adapter，消费当前central v2及精确Root scope，随后调用冻结export_source_v2真实模式；不借旧fixture-only allocation。D `pipeline_v1/io.py:132–140` 的旧fixture仍限定compute20，正式路径只检查16CPU/CUDA空并无64GiB/85%硬门槛。本次没有把它误报为旧内存阻断，也不擅自修改它；新用户CPU节点规则由独立受控入口明确落实。

这些是后续源码边界与验收要求，未执行或宣称实现了新binding模块。真正D3仍取决于科学权威、真实几何及模型线接入；本地11.398m身份记录闭合只证明该身份scope，不证明共同人群、S′/P′、D4/D5或训练导出完成。
