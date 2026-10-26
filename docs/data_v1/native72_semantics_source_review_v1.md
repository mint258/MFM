# Native72 打印精度排除后的静态语义复核 v1

本轮没有确认可解释原 15 项协变失败的源码缺陷。旋转约定、加噪补偿、向量单位转换和已查官方输出分量语义一致。打印精度传播已经实际不能解释残差；本报告不再把它或 SCF 作为推定原因，不改任何容差，原 15 FAIL 与 2000/full HOLD 保持。

## 证据和边界

仅检查现有源码、固定 commit 官方源码，以及 Root 回传的 `diagnosis_summary.json`（14,184 B；SHA256 `68741f9fe70fb5094741b0c9d6f7f6a2858703ffd423ba9b7f36b7c6d8892d6d`）。没有读取 2,456,111 B 的完整报告、SQLite、原 input/result 或科学输出正文；没有执行 Python、AST、测试、科学计算、SSH、Slurm 或 Git。

摘要对应 Alpha `1884773`，UID1264 / compute-0-6：4 fixture PASS、72 实际输入绑定和案例闭合、错误 0。完整报告的实际引用 SHA256 为 `0720c0fec59631ab02b6b574bf00933b31bd62062a38052b12c9de8375b77c8f`。15 项均重现原检查、几何 orbit 在原坐标容差内，分类均为 `RESIDUAL_NOT_EXPLAINED_BY_NATIVE_PRINT_PROPAGATION`。这些是读取的实际摘要事实，不是本轮重新计算的结果。

| 原失败字段 | 数量 | 摘要可确认的分布 |
| --- | ---: | --- |
| PM7 dipole | 2 | 两个 PM7 母几何 |
| PM7 gradient | 6 | PM7 与 UFF 几何均有 |
| xTB dipole | 6 | 三组扰动几何，各有 gradient 与 noisy-SP 两项 |
| xTB gradient | 1 | molecule_01200493 / pm7 / perturbed-gradient |

xTB 三组为 `molecule_01200493/pm7`、`molecule_01201800/uff_sprime`、`principal_00112266/pm7`。普通 clean-SP 没有被列为同类失败。这是定位范围，不能据此宣称电子态、SCF、程序实现或打印是根因。

## 已查一致性与反证

1. **R 的行列约定一致。** `vector_audit/math_v1.py:29–46` 将实际坐标写成 `base_actual @ R.T`；`:73–93` 的向量预期同为 `x @ R.T`；`frame_native_precision_alpha_v2/precision.py:110–124` 的 orbit 仍为 `x[p] @ R.T + t`。梯度在正交旋转下使用相同主动旋转关系。未见单纯转置、R/t 次序或符号混用。平移是独立控制，不混入这 15 组旋转比较。

2. **扰动坐标配对没有发现源码冲突。** `rotation_case` 先构造 `(clean+noise) @ R.T`，再为原 perturbed renderer 减去同 seed 的 lab noise；原 renderer 重新加同一 noise。noisy-SP 不再加噪，直接使用该目标。`prepare_v1.py:80–101` 的 companion 记录 ID 后缀不会改变非 perturbed SP 的坐标。更强的实际证据是摘要 15 组全部 orbit 合法且 72 输入绑定成立，不能再把未旋转 lab noise 当既成原因。

3. **MOPAC atom-major 是有官方反证支持的现实现，不是已发现的错序。** 本地 `read_outputs_v1.py:41–47` 把 3N 个 AUX 梯度按每三个一行排列。官方 AUX 输出确实遍历 `grad(1:nvar)`，不是显式带原子标签的数组；但同一 commit 的 `readmo` 又按外层原子、内层三个坐标构建 `loc`。冻结 renderer 的 XYZ 全部优化 flags 为 1，未加 SYMMETRY 或 dummy。故“仅 3N 长度不能证明语义”的一般提醒，不能升级为本批错序证据。原 stdout 的 ATOM/TYPE 表仍可作为独立逐运行交叉核对。[AUX 输出](https://github.com/openmopac/mopac/blob/490725eac356e0e75037f37bdd2db343d6bc9e09/src/output/to_screen.F90#L561-L572)，[loc 构建](https://github.com/openmopac/mopac/blob/490725eac356e0e75037f37bdd2db343d6bc9e09/src/input/readmo.F90#L1282-L1323)，[带索引梯度表](https://github.com/openmopac/mopac/blob/490725eac356e0e75037f37bdd2db343d6bc9e09/src/output/writmo.F90#L514-L535)。

4. **MOPAC 字段没有查到主体轴/实验室轴混读。** 官方 `DIP_VEC` 写 `dip(1:3,3)`；`ATOM_X_OPT` 写 `coord(:,atom)`。dipole 实现把同坐标电荷项与 hybrid 项相加，stdout 明确 X/Y/Z；离子 COM 平移另有条件并恢复坐标。冻结中性 B 不提供“离子原点变化”的依据。[字段写出](https://github.com/openmopac/mopac/blob/490725eac356e0e75037f37bdd2db343d6bc9e09/src/output/to_screen.F90#L494-L544)，[dipole 实现](https://github.com/openmopac/mopac/blob/490725eac356e0e75037f37bdd2db343d6bc9e09/src/properties/dipole.F90#L149-L181)。

5. **xTB 官方产物提供自己的坐标链，但 SP 有明确限制。** 固定 commit 的 Turbomole writer 同时按原子写 `mol%xyz` 和三个 gradient 分量；JSON 直接写 `sccres%dipole`；`axis3` 受 `do_cma_trafo` 条件控制。源码里存在条件路径，不等于本批走过该路径。[gradient writer](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/io/writer/turbomole.f90#L59-L61)，[分量顺序](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/io/writer/turbomole.f90#L95-L110)，[JSON 字段](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/main/json.F90#L144-L153)，[条件重定向](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/prog/main.F90#L405-L411)。

6. **真实逐运行 frame 证据不能由源代码代替。** `evaluate_v1.py:114–121` 直接用输入 R 做协变，但 `:175–177` 会另列输出坐标不支持输入轴的矛盾；原权威若严格只有 15 个 vector 原因，就不支持“已观测输出整体重定向”这一解释。新小摘要没有携带逐运行 output-frame 数值。SP 没有独立输出坐标块，原 `:139–153` 的同几何 gradient/SP 交叉控制只提供旁证，不能冒称每次 SP 均有自己的 frame 证明。这是证据覆盖边界，尚不是原失败原因。

同一标量单位因子或同一整体正负号会与两臂 R 作用交换，不能单独造成协变破坏；冻结解析器和原 token 的实际 bitwise 链也已由本轮真实读回支持。没有理由通过改单位、重排原子或拟合一个新 R 抹掉失败。

## 一个有限、充分的后续只读 CPU 阶段

**首选只消费现有完整诊断报告、14 KB 小摘要和冻结配置。** 固定 15 条失败和上述 3 组 xTB paired controls，结果限制为一个小汇总；不扩样本、不重跑 QM，不遍历人口，不选择或修正新阈值。完整报告必须在实际合法 CPU allocation 中按实际 bytes/SHA 验证后读取，登录端只读新小汇总。

报告的 `failures[].base/variant.native_token_details[]` 已保留原 token、`parsed_value_field_units`、`selected_token_index`、冻结 conversion factor；无需为这些向量再开 raw。可提取的最小字段与诊断为：

| 项 | 已有字段 | 只读计算/输出 |
| --- | --- | --- |
| 权威与范围 | runtime、original_failures、scientific_source_equivalence、all72_inputs_closed、synthetic_test_receipt、case_read_errors | 绑定实际 1884773/report SHA，确认原 15/4/72 和无新增科学调用 |
| 原门限与实际残差 | 每项 original_check、frozen_evaluator_check_on_retained_raw、original_predeclared_tolerance、geometry_orbit.declared_rotation | 原 max residual、allowance、exceeding-components；不重新拟合或改 gate |
| 向量旋转不变量 | 两臂按原 index 排列的 parsed_value_field_units；dipole 为 1×3，gradient 为 N×3 | 两臂向量范数、gradient Frobenius norm、逐原子 norm 最大差、gradient Gram 矩阵最大差；只报数值，不设新 PASS 阈值 |
| 直接原 R 复算 | 上述值及冻结 R | 原向量 residual 与原检查是否一致；禁止搜索任意 R/P 或挑最佳变换 |
| 三组同几何跨任务控制 | gradient/noisy-SP 两条件相同 molecule/geometry 的 base 和 rotated dipole，原 factor | 各臂两任务分量差/范数差，按原 `same_geometry_dipole_atol_au` 复现既有检查；不把其结果升级为协变 PASS |

范数/Gram 会区分“可能只是整体轴变换”与“已有数值不变量也变化”的模式；仅凭它们不能命名 SCF、电子态或程序 bug。若残差大而两任务在每臂一致，说明不是一个 isolated task 的字段错读；仍不能确定计算根因。

**报告缺 output-frame 时先用已有 metadata，不直接重复读 72 raw。** 原冻结 `frame_evaluation.json`（766,822 B）源码 schema 已包含 `measurements[case_id].coordinates`：`status`、`supports_input_axes`、`atom_order_matches`、`max_abs_coordinate_difference_A`、`proper_fit_RMSD_A`、`input_to_output_rotation`、`translation_A`、`centered_coordinate_rank`、`rotation_identifiable`，以及 xTB conversion hypotheses。其 `same_geometry_SP_gradient_controls` 还有 `exact_same_input_geometry`、`gradient_output_coordinates`、`SP_gradient_raw_dipole_agreement`。仅提取受影响固定 case/三组配对，输出小汇总。该旧 metadata 本轮没有被读取或重新当作新实际观测。

**只有上述值缺失/冲突才按固定调用重新开对应 raw。** 这不是自动执行的第二轮：Root 先看首阶段小汇总决定是否确有必要。

- PM7 六个失败 B 组的两臂，最多 12 个固定调用：`input.aux` 的 ATOM_EL / ATOM_X_OPT / DIP_VEC / GRADIENTS；如要独立核验梯度映射，仅再读 `input.out` 的 FINAL POINT AND DERIVATIVES 中 PARAMETER/ATOM/TYPE/VALUE/GRADIENT，以及对应 Cartesian 坐标表。索引表缺失必须 UNKNOWN，不能猜映射。
- xTB 三个 noisy 组的 gradient 与 SP 两条件/两臂，最多 12 个固定调用：`gradient` 的坐标/符号/导数块，`xtbout.json` 的 molecular dipole 与明确存在时的 partial charges / atomic dipole fields，`process.out` 的实际设置与分量标头。SP 未保存独立坐标块时应保留这一未知，不能从别的调用伪造自身 frame。
- 全部仍使用旧 raw 引用的 frame/body/member SHA 与 bounded reader；无新 seed、程序调用或质量豁免。若只读证据仍不能确定原因，就明确结束为“原因未定”，不无限追加诊断。

本报告没有改变任何注册源文件或结果，也不签发 2000/full release。
