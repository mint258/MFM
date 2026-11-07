# D1：原生单位、符号、原点与轴的限定源码审阅

六类 xTB SP 不打印独立坐标，**不等于物理失败**。192 条 `UNKNOWN_NO_INDEPENDENT_NATIVE_COORDINATE_BLOCK` 应原样保留为观测状态；源码定义、实际调用分支和独立坐标观测是三种不同证据。特别是能量、VIPEA、Fukui、FOD、原子电荷等标量，本来没有 Cartesian axes/origin 要求，不能由坐标缺失制造新 QC 门。

本审阅只读冻结 Source 和小事实元数据，没有打开科学 DATA/raw/坐标，没有运行 Python/AST/tests/QM/Slurm，也不签署 Root/Model 接受。冻结 15 Source 的 SHA/bytes 与 catalog 全部匹配；60377B 的 `physical_D1_review_facts.json` 与给定 SHA `9df27291d7d26870261b6b3fed76881fef58851c32ee3416d2dedd984589897d` 匹配。

## 已有实际证据与其限度

- 384 = 12 条件 × 32 key。MOPAC 五条件共160项、xTB perturbed-gradient32项的原独立坐标/原子顺序门 PASS；六 SP 各32项，共192项保留上述坐标 UNKNOWN。
- 原定义500向量比较全部 PASS；100 retained tensor、100 gradient/force relation PASS；old72 原点8、companion16、tensor24 PASS。r674 trace32 PASS，另352是 `NA_OR_UNKNOWN`，不是352 FAIL。
- 这些结果不能自动等同全部物理字段的语义/全人口精度 PASS；原1200只属限定更严精度诊断，不能由本 memo 扩大成生产参数许可。旧失败、mask、容差和原返回状态均不改变。
- facts 中 xTB `native_explicit_unit_headers_by_condition={}` **不是缺少所有单位证据**：该收集项由 `physical_closure_day_v1/native.py:85–86` 仅筛 MOPAC AUX 冒号标签。它没有筛 xTB JSON 中明文的 `dipole / a.u.`。这项空结果不可作物理 FAIL 或 unit 未知的依据。
- 同源 `native.py:99` 已明确记载旧报告的 `unit_sign_axis_accepted=False` 是固定的待独立接受标记，不能读成实际数值 FAIL；同样，本 memo 的 Source 判定不能自行把该 Root/Model 签署标记改成 true。

## 最短逐字段判定表

行号均为已匹配 SHA 的本地冻结文件，1-based；文件位于 `ROOT/control/pprime_physical_closure_official_sources_v1/`，真实官方 URL/commit/bytes/SHA 见同目录 `official_source_catalog.json`。下表说的是原生定义；训练字段的重命名、单位换算和 mask 仍以冻结 WP5 映射为准。

| 物理字段/原生 token | 单位、符号、原点/轴的源码结论 | 精确冻结证据与仍需区分的事项 |
|---|---|---|
| MOPAC `ATOM_X_OPT` | Å；按 atom 外循环、x/y/z 内循环输出 `coord`，不是主惯性轴标签。 | `to_screen.F90:550–551`；160项独立坐标门已 PASS。 |
| MOPAC 中性 `DIP_VEC` | Debye；输出 `dip(:,3)`，由净电荷坐标项加 one-centre hybrid 项构成，不能只用点电荷重建。 | `to_screen:506–508`；`dipole.F90:105–157,169–172`。分量沿 `coord` 的 x/y/z；中性总偶极不依赖平移原点。 |
| MOPAC cation/anion 偶极 | 同为 Debye、同 Cartesian 方向；实际 flags 为 `CHARGE=±1` 且无 FORCE/THERMO/IRC。源码在 `abs(sum(q))>0.5` 判作离子时，暂移至**质心原点**算偶极后恢复坐标。 | `dipole:81–103,173–179`。离子分支不能套固定实验室原点的 `Q*t` 关系；这不是轴旋转或坐标输出错误。 |
| MOPAC `GRADIENTS` | kcal mol⁻¹ Å⁻¹ 的导数，**不是 force**。Cartesian XYZ 情形为所选变量 atom→x/y/z；不能对任意 `nvar` 向量无条件 reshape 为3N。 | `to_screen:568–578`；`readmo.F90:1287–1328`；`writmo.F90:505–535` 明列 derivatives、Cartesian X/Y/Z。实际桥的完整3N映射已有原门；需要 force 时取负梯度并沿用原单位转换。 |
| MOPAC `ATOM_CHARGES` / `AO_CHARGES` / `AO_SPINS` | 前者是净原子电荷；后两者分别是密度矩阵对角占据和 α−β占据，不应因 token 中有 charges 就反号当净电荷。原子净电荷是空间标量；AO分量是 **basis索引的数值**，不可把 px/py/pz 的占据分别当旋转不变量。 | `to_screen:552–565`；`dipole:53` 明述 q 为核+电子总电荷。基组/原子索引映射另由原元数据约束。 |
| MOPAC AO density / r674 类3×3量 | 原始 `P` 是 AO 密度/占据对象；其 basis 不可仅凭“3×3”判成任意 Cartesian 张量。trace/协变 PASS 是已有数值证据，不替代字段→AO标签/矩阵块映射。 | `to_screen:264–270,897–898` 提供 AO atom/symmetry 与 lower triangle 定义；r674 trace32、retained tensor100 已 PASS。尚未在本审阅取得完整冻结 registry→parser/AO block 映射，不自签 basis 接受。 |
| MOPAC SIGMA/PI pair 通道 | `denrot` 用原子对方向和 `coe` 变换到 **bond-local σ/π 通道**，不能把其序号直接当实验室 x/y/z。 | `denrot.F90:53–57,97–100,130–137`。局部 π 细分与模型表示选择仍须按原字段定义。 |
| xTB `mol%xyz` / gradient 文件坐标 | 内部为 bohr；结构坐标直接传入并赋给 `mol%xyz`。gradient writer 按同一 atom、同一 x/y/z 次序写坐标和导数。 | `type/molecule.f90:85,264–267,405–411`；`io/reader.f90:63–64,94–95`；`io/writer/turbomole.f90:64–65,103–118`。gradient32 独立坐标已 PASS。 |
| xTB gradient / force | writer 明称 `dE/dxyz`；原子坐标为 bohr；官方同commit计算器还明文标 energy=Eh、gradient norm=Eh/a0。force 是负梯度，不能反号保存成 gradient。 | 冻结 `turbomole:112–118`；原100 force relation PASS。补充 primary `src/xtb/calculator.f90` 的 `singlepoint` SUMMARY 写入三行 total energy/Eh、gradient norm/Eh/a0、gap/eV（本文网络只读核实，未冒称15-source catalog内已有该文件）。 |
| xTB JSON `dipole / a.u.` | 分量为 atomic units 的原生偶极，JSON 直接写 `sccres%dipole`，不是 Debye；输出 Debye 字段必须沿用原冻结换算。 | `main/json.F90:155–164`；`mctc/convert.f90:25–28,64`。不能将原 JSON 已乘一次 Debye 的值再乘一次。 |
| xTB stdout `full:` 偶极 | 前三分量仍为 a.u.，第四项模长才乘 `autod` 成 Debye；标题尾部 `tot (Debye)` 不能解释成四列全 Debye。完整 GFN2 偶极含原子偶极贡献，不是 charges-only。 | `aespot.f90:675–701`：净电荷×`xyz`加`dipm`；JSON/direct结果与此调用链需同一终态对象，不能拿旧 SCC 块混比。 |
| xTB atomic dipole / quadrupole | 跟随内部 xyz；原子 multipoles 围绕原子中心，分子总矩另含位置项。原生CAMM `qp` 顺序明确为 **xx,xy,yy,xz,yz,zz**；其无迹约定是1.5×矩阵减0.5×trace对角项，不可套另一规范。 | `aespot:169–187,174–176,222–224,255–262`；分子矩 `706–740`；`main/json:218–236` 按原序写。模型 parser 的重排/单位/归一化仍需显式映射。 |
| xTB total energy / gap、VIPEA、Fukui、FOD、partial charges | 能量、响应和原子标量不要求一个额外坐标块才能具有定义；axes/origin 对这些标量为 N/A。不同能量/响应的单位及符号须各取原 token/公式，不能一概当 Hartree 或净电荷。 | `main/json:160–164,178–184` 直接区分 energy、gap/eV、dipole/a.u.、partial charges；其余响应的确切单位/符号需原冻结 parser/producer 映射，不从该坐标 UNKNOWN 推导失败。 |

## 六 SP 的输入轴：能证明什么

冻结 observed-prefix Source 的路径是：

1. `prog/main.F90:392` 读输入结构；`io/reader:94–95`、`type/molecule:405–411,264–267` 将原坐标与原子次序传入 mol。
2. `setparam.f90:234` 的 `do_cma_trafo` 默认 false。`main:433–440` 只有该开关为真才调用 `axis3` 后覆盖 `mol%xyz`。**没有“SP 不输出坐标就默认转到主轴”的 Source 路径。**
3. `main:687` 在 mol 上做单点；`main:1027–1042` 把同一 mol/res 传给属性/JSON输出；JSON writer 没有额外重排或转轴。补充官方同commit `xtb/calculator.f90::singlepoint` 调用 scf 并更新结果，不把“不输出坐标”作为任何转轴条件；实际SCF/property完整链仍应与 frozen invoke 一起闭合。
4. 实际384元数据中六 SP flags 是 `--gfn 2 --chrg 0 --uhf 0`，或加 `--alpb water/octanol`、`--vfukui`、`--etemp 5000`；VIPEA 用 `--gfn 1 --vipea`。均未列 cma/opt。方法、溶剂、温度、垂直电荷响应本身不定义新坐标轴。

因此：**冻结调用契约若封闭了控制输入、且没有设置 CMA/优化/结构转换，程序定义足以证明这些分量在输入轴，不需要为每个 SP 新增“必须打印独立坐标”的 QC。** 同时保持192项独立坐标观测 UNKNOWN；二者不矛盾。

本次已读60377B摘要的 flags 是 task keyword 变体，不是完整 argv/environment/control 清单。源码 `main:298,354–359,427` 还会读 xcontrol、搜索 `.xtbrc` 并读 userdata；所以**仅凭该关键词摘要不能无条件证明具体192调用均未受其他控制项影响**。所缺是现有冻结 WP5 invoke 的完整 argv、工作目录与 `XTBPATH`/rc/xcontrol 隔离/绑定的 Source/元数据，不是新 QM 或新容差。可据已存在契约补这一条 Source 链；不得把本次未取得该文件等同实际存在未知控制或数值失败。

还须区分版本谱系：15-file catalog 固定 xTB observed-prefix commit `edcfbbe39d411edc225e27315fbda3a204ddb023`，MOPAC `490725eac356e0e75037f37bdd2db343d6bc9e09`；v49 另列 exact-tag `26b28010` 五文件 Source acquisition。不能只因两者都叫6.7.1就宣称二进制/build 与全部 Source 字节相同。本次后续正常 Source SFTP 被连接拒绝，未取得那五文件及完整 invoke 源码，故没有假称已复核；这也是谱系补件，不是新增物理 FAIL。

## 给 Root 的最小政策审阅结论

可直接关闭的是“SP 不打印独立坐标本身说明单位/轴失败”和“xTB AUX-unit统计为空说明完全无单位”的误读。可由 Source 明确定义 native 单位、gradient/force 的符号区别、MOPAC离子COM原点以及 bond-local/AO 量的区别。对已有 PASS 的数值门不重判；对N/A/观测UNKNOWN不伪造数据。输入轴的实际分支证明只需补现有 invoke/控制输入封闭链；registry→parser/AO/tensor顺序映射按字段补齐。这里不要求新的独立坐标打印、不创造新QC阈值、不授权生产精度或2000/full。

主要官方出处：[xTB frozen main](https://github.com/grimme-lab/xtb/blob/edcfbbe39d411edc225e27315fbda3a204ddb023/src/prog/main.F90)、[xTB JSON](https://github.com/grimme-lab/xtb/blob/edcfbbe39d411edc225e27315fbda3a204ddb023/src/main/json.F90)、[xTB multipoles](https://github.com/grimme-lab/xtb/blob/edcfbbe39d411edc225e27315fbda3a204ddb023/src/aespot.f90)、[MOPAC AUX](https://github.com/openmopac/mopac/blob/490725eac356e0e75037f37bdd2db343d6bc9e09/src/output/to_screen.F90)、[MOPAC dipole](https://github.com/openmopac/mopac/blob/490725eac356e0e75037f37bdd2db343d6bc9e09/src/properties/dipole.F90)。行号以此次实际匹配SHA的冻结文件为准，不使用网页文本渲染的折叠行号。

补充官网 Source（同精确commit，作为定义证据，不假称已加入现15文件冻结清单）：[xTB concrete calculator](https://github.com/grimme-lab/xtb/blob/edcfbbe39d411edc225e27315fbda3a204ddb023/src/xtb/calculator.f90)。上述原生单位标签与 Source 确认不能替代 actual binary/build 谱系，也不要求额外新QM。
