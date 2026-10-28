# D1 参数清单边界与共同冻结候选补充（DRAFT v1）

状态：`SOURCE_CHAIN_ADDENDUM_AND_JOINT_CANDIDATES_NOT_JOINT_FREEZE`。这是对既有 Source-only 报告的增量；不修改 draft3/5、Registry、模型、冻结生产源码或历史结论。本轮只读原源码、已闭合小定义/参数资产 headers 和 Model 条件反馈；无 Python/AST/测试、SSH/Slurm、Native、科学 payload 读取或新计算。

## 参数清单实际证明到哪里

Root 新提供的 `D1_actual_source4_and_frozen_parameter_headers_v1.json` 已逐字核对四个当前原源码与缓存：`wp5_parquet.py`、`wp5_parquet_v2.py`、`wp5_reproduction_package_v2.py`、`wp5_prepare_runtime_freeze_v14.py` 全部相同。故旧报告中的这四项“当前原件待比较”现在已闭合；这不会把别的 SourceSnapshot 文件自动等同于实际历史 producer。

实际 G4 job4513932 的 report 状态是 PASS；四个已闭合 reproduction manifest 和 G4 参数 bindings 均列六项。六项之一是隐藏文件 `.param_gfnff.xtb`，其余为 `param_gfn0-xtb.txt`、`param_gfn1-si-xtb.txt`、`param_gfn1-xtb.txt`、`param_gfn2-xtb.txt`、`param_ipea-xtb.txt`。没有 `.xtbrc`。准确结论是“这六个已列出的资产受 hash 约束”，不是“目录所有可读文件恰好只有六个”。

SourceSnapshot30 中的 G4 v1–v8 均有同一条来源链：

1. `build()` 读取 `spec['xtb_verification']` 的 JSON；v1 第67、71行，v8 第145、149行。
2. 只循环 `xtb['parameter_files']`，把各 `name/bytes/sha256` 变成 XTBPATH 下的 hash target；v1 第82–83行，v8 第160–161行。这里没有对参数目录做完整 census，也没有“拒绝清单以外文件/隐藏文件”的断言。
3. G4 `bindings` 是成功读取的 target 投影。`wp5_reproduction_package_v2.py:69–78` 再从旧 `bindings` 中筛选参数前缀；第69行注释中的“every”没有补上完整性谓词。
4. `wp5_engine_v3.py:264–266` 在初始化中逐项核对已列 asset 的原件和永久副本 hash；它没有据此拒绝 XTBPATH 中未列出的新文件。`wp5_prepare_runtime_freeze_v14.py` 的资产继承也没有建立完整目录负面清单。

所有已缓存 G4 spec 从机器字段读取到同一个 verification 路径：

`/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/software/xtb/verification.json`

其 expected SHA、各 SourceSnapshot member 的 bytes/SHA 和原 manifest refs 均在配套 evidence JSON 中机器保存，不由终端折行转抄。当前新 header 没有实际 G4 report 的 `source_sha256/spec_path`，因此本页明确把八个 G4 文件称作“已静态检查的缓存版本”，不假称已逐字匹配该历史 job 的唯一 producer。

**历史 rc 缺失尚不能从此链推出。** 上游 verification 清单的生成方式尚未取得；即便它在安装时枚举全部条目，也还须区分安装/冻结时刻 census 与每次 Native 调用时的状态。现有逐项 hash 校验本身不禁止后来添加一个未列出的 `.xtbrc`。包含一个隐藏参数文件不等于对所有隐藏文件有完整性检查。

Root 随后提供原 `verification.json` 的完整软件验证 JSON 和机器 producer triple（3064 B）。其当前 SHA 与以上冻结 spec 的 expected SHA 完全相同，六项名称/bytes/SHA 也逐项等于 G4 清单。这关闭了“清单当前是否已漂移”问题。它记录 xTB6.7.1(edcfbbe)、conda-forge 包身份以及 `installer_source_sha256/receipt_source_sha256`，却没有 producer 路径、目录 census 或清单生成代码。SourceSnapshot30 的全部 Source SHA 索引中也没有该 installer SHA。因此现在唯一尚缺的**枚举算法证据**是这个机器 SHA 对应的原 installer Source；不猜其文件名，也不再要求取同一个 verification。

Root 还提供当前参数目录的独立 lstat 小元数据：UID1278、目录 inode 已记录，当前 `.xtbrc` 不存在且不是 symlink；目录 mtime 与 ctime 均为 `1791618838079141536 ns`（2026-10-10），早于 WP5 和本轮诊断。目录条目的增加、删除或改名在正常文件系统语义下会更新父目录时间。结合单一显式 XTBPATH、冻结清单未漂移及这两个旧目录时间，**在可信正常 FS、时钟连续、同一路径/目录未被替换、快照恢复或特权时间戳操纵的假设下，支持调用期间未增删该目录条目、因而没有临时加入 `.xtbrc` 的 provenance inference**。这是可交 Root/Model 审阅的有限结论，不需要为追求绝对负面证明无限补件。

建议审阅标记为 `RC_ABSENCE_SUPPORTED_BY_TRUSTED_DIRECTORY_CONTINUITY_INFERENCE`，同时记录上述假设和 `historical_absence_absolute_proof=false`。原 installer Source 仍可进一步核清安装清单是否包含所有隐藏项，但不是必须重跑 Native 或重做192项坐标观测的理由。Root 尚未签认这个新增 inference；本页不把它自动变为最终物理政策。

## XTBPATH 与日志的可证明范围

原 protocol 和独立精度诊断 protocol 均显式设置同一个非空、单路径 XTBPATH：

`/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/software/xtb/conda_env/share/xtb`

原 invoke 在每调用新建 scratch 中写 `native.inp`、运行 `--input native.inp --norestart --parallel 1`，再把 protocol 的 `xtb_environment` 覆盖到环境。XTBPATH 指向上面的持久目录，不是新 scratch。已绑定官方 `environment` 与 `rdpath` Source 表明：对这个显式非空单路径，rc 候选是唯一的 `XTBPATH/.xtbrc`；不会再追加 HOME fallback。`--norestart` 不能用作禁用 rc 的证据。

原生成的 xcontrol/六种 single-point argv 没有 `$cma`、`--cma` 或 sandwich wall 设置；这关闭了这些显式生成分支，却没有关闭未证实的持久 rc 分支。已核官方 Source 中 rc 以 `copy_file=.false.` 读取；成功读 rc、`set_cma` 和 `axis3` 并无必然 stdout 标记。`sandwich wallpotential with radius in A ...` 是成功经过该 wall 分支的正面日志标记，不能由缺失这行普遍推出没有 CMA/rc。当前目录 absence 与旧 mtime/ctime 的组合按上一节明确假设形成连续性推断；它既不是单凭当前缺失的断言，也不是没有假设的绝对历史证明。

既有实际407引用物理审阅报告已经到达，不能再写成“尚缺实际 physics report”。五种 MOPAC 与 gradient 的独立坐标观测及已完成关系检查按原报告保留；六种 xTB single-point 的192项独立坐标观测仍为 UNKNOWN。上面的 Source 分支结论不把这些192项变成 PASS 或 FAIL，也不为既有标签新造异常 mask。

## 提交双方审阅的具体候选

下列是数据侧建议，不是 Model 已采用、消费者已实现或 joint ACK。依据是 Model `model-v3` 精确 commit `a45495e0398bc38ffda88f8384aee5d6011fc04d` 的 `training_format_v3_draft5_model_feedback_DRAFT_v1.md`（Git blob 身份见 evidence）。该反馈已经实质审阅 draft5，状态仍为条件式共同审阅。

| 项目 | 本页提出的候选选择 | 仍须双方确认/实际交件 |
| --- | --- | --- |
| r73 数值精度 | 选择“权威原 F64 sidecar＋consumer 恰一次 F32 转换”路线。F64 保存原解析值 bit；可得原 token/打印精度另留引用。旧 f4 wire 不承担永久 F64 保存承诺。 | sidecar/wire/consumer 的共同版本、转换位置与恢复 hash；模型真实读取及 retained-entry 对照。 |
| r73 域 | 独立 ordered-entry 域；保留两端零基 atom、两个原 UTF-8 channel、onsite、方向、重复项和 retained parser-list 内 ordinal；不并码 DEL/DELL/DELTA、不去重、不镜像。ordinal 只服务对齐/审计/恢复。 | 双端 channel 的可逆编码及 SHA；新 FieldSpec/provider/collate/head/loss/count。普通 pair、无 channel 的交换对称 head 不可直接顶替。 |
| r674 目标 | 一个 full symmetric6 目标，原顺序 `xx,xy,yy,xz,yz,zz`，保留六项原值、原有效性/原因和源打印精度；不再次乘1.5、不减 trace、不删 zz。 | 逐 target 的源 unit/sign/origin/frame 共同科学审阅；实际 tensor consumer。未闭轴保留 UNKNOWN。 |
| r674 partial | 候选先用“完整六项才进入完整 tensor loss”eligibility；原 component masks/reasons 与 retained/excluded coverage 全保留，partial 值仍审计/导出，不补零，不把 loss ineligibility 写成新增数据异常。 | 完整6资格、component 审计与1%质量口径共同版本；若以后选择 frame-aware partial operator，须另有明确变换/consumer。 |
| r674 尺度 | 候选 `c=0`，每 condition 只有一个实际 Common TRAIN-only 拟合的 scalar scale；不采用六个独立 component offset/std。尺度只能绑定真实 D4 已计算 series/算法、适用人口、SHA 和退化规则；本页不发明 RMS 或复用未计算数值。 | Root/Model 指定 exact series/计算算法与 zero/degenerate 规则。现有 D4 Source 不支持的算法保持 NONEXEC，不能以本提案生成参数。 |
| r674 旋转/损失 | 行坐标约定固定为 `X'=XR+t`，同原点 tensor 旋转为 `Q'=R^T Q R`；六项 Frobenius 权重 `(1,2,1,2,2,1)`。候选走 tensor Frobenius-radial 路线，不把 weighted component Huber 冒充旋转不变。 | radial radius/归一分母d6或d9、delta、组权重、eligibility/count/平均人口须双方明确选择并由模型实现；现有 vector radial head 不等于 tensor6。 |

这些可先形成“双方选项决议”，但最终 D1 仍须绑定五层映射、实际 geometry/child、Registry/D4/D5 同一 release 和模型实际 consumer 验收。gradient 必须使用真实 child 的输入/hash/atom-order 路由；不能借 base/N1 或 S 噪声。TRAIN 是最终 Common∩effectiveTRAIN 且 anti-join 全部 D5 heldout base/真实直接 children；角色层整 ROUTINE 为 VAL，5000 pilot 候选仍受 Common∩effectiveVAL 约束。来源独立、原阈值及>1%报告/HOLD 规则不变。

## 供 Root 状态记录的短句

D1 新增源码与实际参数 header 审阅已闭合四项当前源码字节比较。G4→reproduction 是上游 `verification.json.parameter_files` 的有限继承；原verification已匹配冻结SHA，当前rc缺失和早于调用的mtime/ctime支持有明确可信FS假设的历史连续性推断，绝对历史证明不声称。Model a45495e 已有条件反馈；新增可评审的 r73 F64-sidecar/一次F32 与 r674 full6/完整6 eligibility/c=0单尺度候选，尚无 joint ACK。192项 xTB 独立坐标 UNKNOWN、原 masks 和已完成实际证据保持不变。