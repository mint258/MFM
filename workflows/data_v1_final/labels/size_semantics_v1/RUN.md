# 已批准新 size pass v1：实现与执行入口

Root已批准PROPOSAL主口径。本实现是新variant；原registry、streaming v1/v2、normalization及其配置/结果均保持字节。尚未执行本variant的真实label扫描或增量fixture，不能把实现/静态检查当作科学PASS。

## 输入与两个scope

`configs/data_v1/labels/size_rho_pilot_v1.json` 实际绑定已闭合4251记录/512完整分子/16source groups的plan、原profile compact masks和reduction，scope=`PROVISIONAL_SOURCE_TRAIN_PILOT`，coverage fingerprint为`cdff29d469c2a59e51859c429d31bec502e08e1c2884b819b870080c9f9b76bc`。这些pin来自本轮小metadata文件的实际观测，不靠手抄未来calibration路径。pilot仅选择既有canonical role=TRAIN，不虚构common=true或已排除diagnostic。

`FINAL_FROZEN_COMMON_TRAIN` 另需新配置、新Root nonpilot request及真实被接受的试点。必须full+phase=mask、真正冻结common/roles/geometry/order/diagnostic四方authority及独立final masked dataset manifest。复用已经24fixture实际验证的normalization_v1 authority/side-table实现，构建原population全部记录的准确纳入/排除表，并逐geometry排除诊断及其扰动目标。缺任何权威就拒绝；不会将source TRAIN pilot升级为final。最终配置应重新按实测资源/存储预算，不能直接用8GiB试点cap假称全量足够。

原P/D共146登记组件按同一field_map固定映射到129统计target；它不是模型head数。P′独立UFF来源尚未接齐，本variant不拿PM7值或ρ填P′。P′后续需要自己的完整source adapter、geometry/mask/参考人口与统计输出。

## 实际数据流

每个source group由一个实际worker处理其完整latest owner分子。复用SHA固定scan_v2的canonical五键、lane/natom、base atomic_numbers/atom-order/payload hash验证以及旧typed decoder；新reader再与持久compact mask的bitset/source/new reason/partial leaf exception逐项parity。不把收敛NULL或z>20变成新mask。pair keys另从原typed CELL读取，与值按同一源顺序对应；普通atom pair为unordered(i,j)，sigma/pi为unordered((atom,basis),(atom,basis))，保持轨道组键，不把数组行号当物理ID。重复/冲突只排除该target的ρ资格并计原因，不改原mask或label。

两遍明确源读取：

1. HOF reference pass：各自context在完全有效的TRAIN标量上拟合元素计数TSQR，重核整个选中记录的masked value/atom/pair-key质量摘要，保留每组状态。未复用旧uncorrected rho或scope不匹配的reference。
2. Rho pass：按批准定义产生每记录每target一个数，HOF先扣对应参考。主数组要求所有语义拥有值完整有效，partial、empty、键冲突单列rho_missing；有效0保留。源、mask和HOF参考质量必须与首遍相同。每组完整分子上的有效构象中位数另形成每分子一票敏感性；RMS local target再给signed mean/sum_abs，向量给global L2敏感性。

没有持久复制正常原子/原子对leaf。输出统计scratch是压缩 `(target_id,variant,value,heavy_atoms,n)` 直方图，没有record ID；缓冲按8192唯一项刷出。Spearman用外存exact value/heavy count平均tie ranks及longdouble中心协方差，按未舍入absρ>=0.95给candidate。另守恒primary n、molecule sensitivity n、每target记录分母、按heavy count的missingness及每分子有效构象数量分布。

所有129target和146component结果都输出，未定义rho为NULL并保留原因。sigma/pi明确`BASIS_INVARIANCE_UNPROVEN`，无论候选ρ多高都不自动冻结family。MolMR原单位/候选scale、Fukui单位冲突、SUPER推导单位、D19可能继承float32有效精度及实际运行版待证按组件带入。family_v1_final始终NULL，最终family/head/pooling需Root与模型线共同确认；合成旋转通过也不宣称真实QM source frame/origin audit完成。

## Root执行

生产入口默认analysis/node20、16实际worker、request及实际64GiB、2小时，CPU-only且BLAS/OMP/ArrowCPU/IO每worker各1。worker RSS2.5GiB、压缩buffer256MiB、整个run unique inode输出8GiB硬停，DuckDB内存12GB/spill4GiB；失败保留证据无自动重投、不删除旧数据。新鲜account quota保持至少200GB，Root核全部用户声明内存85%。本模板预算未经本variant实测，先只跑4251/512小试点。

```
python -B workflows/data_v1_final/labels/size_semantics_v1/run_size.py \
  --config configs/data_v1/labels/size_rho_pilot_v1.json \
  --root-preflight /external/fresh_size_intent.json \
  --output /external/new_size_pilot_run
```

输出HOF_TRAIN_element_reference.json、两遍每组receipt/质量摘要、统计scratch、physical_target_size_rho.json及manifest。manifest绑定plan、scan、reduction、Root intent、所有结果SHA与2遍实际成本；scope与registry_final=false明确保留。全量另请求，不能自动提交或绕过共同人群冻结。

增量验证（只合成label＋小metadata；不重跑19/24套）：

```
python -B workflows/data_v1_final/labels/size_semantics_v1/test_size_incremental.py \
  --output /external/new_size_incremental_fixture_receipt.json
```

Root可用16CPU/node20/8GiB/1小时小Slurm执行。13项增量语义测试覆盖非平凡vector/tensor/atomvector旋转与错误六分量norm负例、完整mask与原值不变、empty/zero、charge cancellation/SUPER范围、pair duplicate/conflict/存储表示、ENPART符号、轨道basis键、独立HOF context、exact SQL tie/variant过滤、record-vs-molecule权重、146→129穷尽映射与单位pending、实际新canonical reader对合成VAL极值的排除。16个partition worker均经barrier，测试少于16时空partition仅验证初始化资源，不假装额外语义test。

Root source refs需绑定新全部.py/配置、冻结scan_v2与其共享support/calibration/compact/legacy decoder、normalization_v1共享authority/reader/sources/runtime、实际plan/scan/reduction/field_map、prototype metadata config与其小lineage pins。旧文件无任何修改。
