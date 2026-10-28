# D1：native token、解析、存储与控制输入的限定源码闭合

本轮可以补齐 r73、r674、dipole、perturbed-gradient 的源码定义与数据路径；六 SP 的实际输入轴仍应分别记录“源码控制分支”和“独立坐标观测”。原192项 `UNKNOWN_NO_INDEPENDENT_NATIVE_COORDINATE_BLOCK` 保持不变，既不补 PASS，也不据此判物理失败。没有改 registry、合同、Model、科学代码、mask、容差或生产精度，没有运行 Python、AST、tests、Native、QM、Slurm、SSH，未读科学 DATA。网络只读取了精确 commit 的官方源码和 Git tree/blob 元数据。

Root 提供的40件 Source/小定义已逐成员 bytes/SHA 核对；13件缓存经 Root 当前源比较确认同字节。新增六件官方控制定义源码位于 `additional_official_Source/`，固定 observed-prefix commit `edcfbbe39d411edc225e27315fbda3a204ddb023`，完整文件均核 Git blob SHA1 和 SHA256；它们没有被冒称已加入旧15件 catalog，也没有替代实际 binary/build 绑定。来源清单见 accompanying JSON。

Model 当前公开 commit 为 `a45495e0398bc38ffda88f8384aee5d6011fc04d`，反馈 blob `5b0970ae33d3549f268f4fec775f59c55f400d67`，状态是 `MODEL_CONDITIONAL_SOURCE_REVIEW_NOT_JOINT_FREEZE`。反馈已存在且是实质条件式审阅，不能再写“尚未 review”；也不能据此写 joint ACK、consumer 已验收或最终物理政策已选择。

## 逐字段路径

行号对应本轮已核字节文件；原 WP5 源根为 `runs/phase1_wp5_20261011/scripts/`，native/parser 原根为 `runs/phase1_dataset_rebuild_20261010/scripts/`。精确绝对路径、bytes/SHA 由证据 JSON 绑定。

| 字段 | native → 实际 parser | 已存布局与源码可证明的边界 |
|---|---|---|
| `P.pm7_B.r73.value`，registry73，`values.sigma_pi_entries` | MOPAC `denrot.F90` 打印 `SIGMA-PI BOND-ORDER MATRIX`；native `invoke:383–385` 将 selective AUX/sparse parser hook 传入 active parser；`wp5_parser_v2:46–50` → `wp5_parser:58–61` → legacy，最终采用 `wp4_native_pilot_v4.sparse_sigma_pi:171–195`。 | 每项为原方向 `atom_i,basis_i,atom_j,basis_j,value`。atom 是打印编号减1；basis 是两个独立原字符串。`keys` 的原子/通道索引不是原始 AO ordinal。所有 same-atom 项及 selected atom-pair 项按解析追加顺序保留，包含同 atom 不同 channel。`entry_ordinal` 可绑定已保留列表的位置，不能声称恢复完整原打印矩阵或被 parser 跳过的项。 |
| `P.xtb_singlepoint.r674.{xx,xy,yy,xz,yz,zz}`，registry674，`values.molecular_quadrupole_traceless_au` | `wp4_parsers:247–250` 取最后一个 molecular-quadrupole 标题之后 `full:` 的六原 token，逐 `f()` 转有限 Python float；active parser v2 → base 不重排或再缩放。native `invoke:453,461–462` 仅在 singlepoint 留该物理量。 | 完整六项顺序是 `xx,xy,yy,xz,yz,zz`。官方 `molmom:669–740` 对 q/dip 平移项各做 `1.5*T−0.5*trace(T)*I` 后加 atomic qp；full 已含该约定，禁止再次乘1.5、投影去 trace 或删 zz。它是 xTB 分子 quadrupole，不是 MOPAC AO density；旧 memo 中泛称“AO density/r674类3×3”不能作为本 registry674 的映射依据。 |
| MOPAC dipole：registry52/196/265/332/399，对应 B/anion/cation/octanol/water，`values.dipole_Debye` | `wp4_parsers:137` 取 `DIP_VEC:DEBYE`，selective AUX reader保留该 label；`f()` 识别 E/D 指数并转有限 float。没有第二次单位换算。 | 三项按 Cartesian x/y/z。官方 `to_screen:506–508` 直接打印 dip(:,3)，单位 Debye。`dipole.F90:81–103,173–179` 的带电分支暂移到质量中心计算后还原坐标；本协议 ±1 的 MOPAC 调用必须明确 COM 原点约定，不能直接套固定实验室原点的 Q·t 定律。neutral 总偶极与离子不能混用原点政策。 |
| xTB dipole：registry669，`P.xtb_singlepoint.r669.{x,y,z}` | `wp4_parsers:209–214` 优先 `xtbout.json['dipole / a.u.']`，各项乘冻结常数 `2.541746473`。若缺 JSON，`wp5_parser:83–90` 取 stdout molecular dipole 的 full 前三项，同常数换到 Debye，并记录打印精度。 | 官方 JSON 写 a.u.；stdout `aespot:696–701` 的前三项仍 a.u.，只有第四项 tot 乘 autod 成 Debye。故当前 parser 的单次转换有源码依据，不能因标题 `tot (Debye)` 把四列都当 Debye或再次转换。完整偶极包括原子 dipm，不是 charges-only。 |
| gradient registry625 `values.gradient_Eh_bohr`、force registry624 `values.forces_eV_A` | `wp4_parsers:259–265` 只在 gradient 文件 N 行坐标、N 行导数和原 symbols 顺序相符时赋值。gradient 为 dE/dR；force 为每项 `−gradient*27.211386245988/0.529177210903`。 | 官方 Turbomole writer `103–118` 同 atom/x/y/z 写 bohr 坐标及 Eh/bohr 导数；parser 输出 nested N×3。符号及单位转换分别可闭合，不能把 force 正号称 gradient。其目标是实际 perturbed child，不能绑定 base geometry。 |

MOPAC denrot 的 channel 是 pair-dependent 的 bond-local sigma/pi 等，并将 degenerate channel 累积、最后替换特殊对角 valency；它不是全局 px/py/pz tensor，也不能借 `AO_ATOMINDEX` 解释 r73。源实现接受 DEL/DELL/DELTA 的原字符串，不自动折叠别名。原 `sparse_sigma_pi` 有 pair 选择与跳过分支；“无损”仅能指已保留 parser 列表及可得 raw 证据。参考 [MOPAC denrot 精确 tag](https://github.com/openmopac/mopac/blob/490725eac356e0e75037f37bdd2db343d6bc9e09/src/output/denrot.F90)。

r674 的 `xyz` 是输入 Cartesian 分量的内部 bohr 坐标；`property.F90:274` 直接调用 `molmom(mol%xyz,wfx%q,wfx%dipm,wfx%qp)`。`scc_core:485–495` 将核壳电荷减电子 Mulliken population 得到 q，再汇总原子；CAMM 电子项和正电荷符号不能靠字段名猜测。此调用链、六序和1.5约定有源码依据，但实际控制分支、binary 谱系及 Root/Model 物理政策仍须分别绑定。[xTB molmom 定义](https://github.com/grimme-lab/xtb/blob/edcfbbe39d411edc225e27315fbda3a204ddb023/src/aespot.f90)。

## 存储精度与 geometry 绑定

`wp5_runner_v14.schema_for:1098–1100` 指向 `wp5_parquet_v2.CELL`。本地 Source30 的 serializer 两件仍待 Root 当前 external 原文件最后比对，已给1514B机器请求；不能只因文件同名就冒称已比对。

该版本 `CELL:8–20` 使用 f64/array_f64、shape 和 text。r73 的 list-of-dicts 进入 kind8 JSON，保留列表顺序、重复和双端字符串，有限 Python float 经 JSON 原类型返回；r674 六项、dipole 三项和 gradient/force N×3 进入 kind5 array_f64，加原 shape。`encode/decode:51–91` 不施单位或坐标变换；`exact:93–105` 用 `struct.pack('>d')` 逐 float 比 bits。runner `1139–1154` 从 staging 重建 typed rows，在永久发布前逐值复核。这里证明容器/IO规则，不把源码容器精度当 native token 精度，也不把模型旧 f4 wire 冒称永久 F64。r73 的权威 F64 sidecar 或新 f8 family codec、joint head/loss/count 仍由双方决定。

native `read_native:104–136` 对原 payload SHA、原子数/顺序和 `<f8` base 坐标 SHA 绑定；`invoke:311–312` 按冻结 `20261010|record_id` 派生 seed 和 sigma0.1 Å Gaussian perturbation。`invoke:325–330` 用12位小数写实际 input.xyz 并检查 roundtrip；`411` 的 `positions_A` 是扰动后、打印前的 coords。`native_coordinates_sha256` 在扰动前由 base 产生，单独使用它不能成为 child SHA。真正 child 必须绑定 task/record/seed、原子顺序、实际 input 文件/whole bundle SHA和12位原 token；打印前数组与实际渲染坐标要区分。`causal15.render.bridge:55–69` 的完整 rendered==inputs 字节门及 strict20 worker 的 pre/post-call input hash 复核可复用，但定义/桥接源码不是新几何观测或全域 D5 接受。

## 六 SP 的控制输入

六项为 singlepoint、vipea、vfukui、ALPB_water、ALPB_octanol、fod。原协议/实际1200 candidate 都固定12任务顺序；三 diff 仅 pm7_B SCFCRT 与 singlepoint/perturbed-gradient 的 --acc0.01，不改下述 XTBPATH/xcontrol/六 SP 其他参数。此诊断例外不扩成生产精度、2000/full 或新 QM 授权。

`native.invoke:313,331–353` 每调用新建 node-local mkdtemp，显式 cwd=scratch；argv 是固定 executable/input.xyz/`--input native.inp --norestart --parallel 1` 加该 task args。默认 native.inp 仅 `$write json=true $end`；FOD 仅多 fod 写入设置。所有这些 task args 没有 --cma/--opt。工作目录和输入文件有定义与 hash 绑定；`--norestart` 不等于禁止 rc。

关键是环境在继承 os.environ 后由 protocol.xtb_environment 覆盖：

`XTBPATH=/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/software/xtb/conda_env/share/xtb`

这是持久参数目录，不是每调用 scratch。官方 `type/environment:138–148` 只有 XTBPATH 未设/空时才回退 XTBHOME，再到 HOME；此非空显式值不走 HOME fallback。`mctc/systools:66–99` 按 Linux ':' 拆路径，每段拼接 `/.xtbrc`，取首个 existing。这个协议只有一个 rc 候选：

`/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/software/xtb/conda_env/share/xtb/.xtbrc`

main `355–357` 用 rdcontrol 读取它；不能因为工作目录新建就把这个路径排除。

能设 CMA 的已闭源码分支是：CLI `main:1632–1633 --cma`；`set_module:779` 的 `$cma`（native.inp 或经 rdcontrol 读的 rc）→ `set_cma:1115`；以及 `constrain_param:1083–1093` 的 userdata `$wall sandwich`。当前 native.inp 仅 $write，可排除其中 cma/wall；仍应核唯一持久 rc 的历史冻结内容/absence。不能把“尚缺该证据”表述成它实际有未声明控制项或坐标轴失败。[控制 parser](https://github.com/grimme-lab/xtb/blob/edcfbbe39d411edc225e27315fbda3a204ddb023/src/set_module.f90)、[userdata](https://github.com/grimme-lab/xtb/blob/edcfbbe39d411edc225e27315fbda3a204ddb023/src/constrain_param.f90)。

## 日志与现有冻结资产能提供什么

`rdcontrol:748–763` 成功读文件没有必然 echo；rc 使用 copy_file=False。set_cma 只赋布尔，无 print；`axis_trafo::axis3:337–423` 也没有 write/print。故默认完整 stdout 不含 CMA 字样不能排除 `$cma`。成功执行 sandwich 的 `constrain_param:1144–1145` 则有不受 verbose 保护的固定 `sandwich wallpotential with radius in A (diameter=2*radius+2*4A safety buffer)`；可在现有原日志做正证据检索，但异常提前返回等边界使 absence 不成为全局禁用证明。无需新 QM、坐标门或容差。

已有冻结机制可优先复用：`wp5_reproduction_package_v2:69–73` 从旧 G4 bindings 中取 XTBPATH 下文件为 role=xtb_parameter；`wp5_engine_v3:260–281` 验 binary、所列原/副本 assets SHA、Python/conda lock、单线程变量；`prepare_runtime_freeze_v14:175–179` 保留原 software/environment/closure 字段。它们不自动证明未列出的 rc 在历史各调用时不存在。应从四个已知 frozen package manifest 的实际资产行和其 g4_reference/参数目录清单定位唯一 rc；若已有被校验的 rc asset，可查同 SHA 控制定义。若没有，当前 absence/逐层目录 mtime/ctime 只能限定当前，不能伪过去 absence。

四个原 package 位于 `runs/phase1_wp5_20261011/reproduction_package/`：`queue_recovery_v13_job_4514282`、`queue_recovery_v14_job_4515309`、`queue_recovery_job_4514065`、`supplement_job_4513971`。精确 manifest triple 来自 native_body32 的既冻清单，见证据 JSON；不需要打开 audit-selected Parquet、LMDB、坐标或旧 whole scientific body。

## 本轮关闭与待件

源码层可关闭：r73 双端通道/onsite/原列表序/非 AO ordinal；r674 确切 xTB 六项及打印约定；dipole 一次单位转换与 MOPAC 离子 COM；gradient/force 符号与单位、真实 child 绑定要求；私有 invoke、实际显式 XTBPATH 的唯一 rc 搜索路径；哪些控制输入能够设 CMA 及哪些日志不是必要标记。

仍需的小件精确为：当前两 serializer 与两个参数 freeze Source 的最后 bytes/SHA 比较；四个原 package 中唯一候选 rc 的资产/参数 census header及可得的同 SHA 控制内容或历史 absence 证据。不能用当前 lstat 补历史；也不因这些待件要求新 Native。Root 后续可在已有审计的一次 CPU 只读阶段核现成 refs/控制证据，不需要新控制器。

原 actual384/retained100/old72 的数值证据已到达，沿原 scope 使用，不重新要求同样 summary。六 SP192项独立坐标 UNKNOWN 继续保留。最终逐 target 的 field geometry/origin/unit/sign/frame 物理接受、r73 新域/codec、r674 单尺度/partial/radial/count、D4真实 TRAIN 与 D3–D6 consumer release 仍待具体 Root+Model 共同约定；本报告不代签。
