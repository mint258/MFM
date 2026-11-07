# 双集群实际进度 v10

点时：2026-10-27T01:40:20.617112+00:00。全指南仍未完成，未开最终PR。

S′当前93批/46,500包闭合，状态OBSERVED_BOUNDED_NEXT_TRANSITION。max2科学+1辅助有限控制器运行；实际空闲核不足16时等待，不超配、不终止他人作业。PM7全247控制器的新6纯测试已实际C0通过，人口首5000/39511记录保持完整；full range等待S′179实际闭合。

标签首批全源续算4521904已提交并运行在CPU17，累计whole-cache cap32GiB。实际完成的PM75000和有界标签任务64GiB/32GiB未来cap已在C0+observer闭合证据后退役，原文件保留，原S′182cap全部预留；其他未来scope上界1.64TB，实际quota与200GB余量已核。更大cache预算不自动授权，须旧book全部实际accept闭合后复制式迁移、保留游标并封存旧book。

SourceTRAIN缓存接入试点4521915 FAILED1/36秒/16CPU15：6纯测试通过后，真实base metadata恢复失败。已确认它误选来源ref.seconds浮点元数据到空数值池视图；新v2只选所需owner ordinal与Z/order/hash/status，不补零、不去除原索引唯一/边界门，3项新边界及真实512重放待验证。旧输出与576核秒失败成本保留。全量最终mask/Common D4未放行。

P′新增1891只读电子证据C0，无新QM。xTB B/P90显式13步、一般R14步，各调用均报告收敛；原生能量/梯度仍存在方向相关差异。PM7及xTB梯度自带输出轴支持输入，SP自身轴未知；stdout与JSON偶极尚非全部打印区间闭合。辅助53/54行表混入轨道数据，不能当SCF次数。根因未定。仅15次加严数值设置的提案已准备，尚无用户批准或执行；原15FAIL/full/2000 HOLD不变。

Kraken全量4521873 C0/177秒：1552原SMILES与21287原MolBlock全部完成、未知0；1201构象图与SMILES full-key不同，全部保守并集保留，134根有多个观察键。Drugs558002构象sourceSMILES全量仍运行，native SDF图绑定另需完成。TDC2原未决记录4521907只读诊断C0，全字节回绑原44源ZIP，未重算键或改变unknown。

QM7b作者v3原XYZ已核全7211帧、SHA/发布MD5/EOF，原身份字段0；FPS重排不能冒MAT行号。已有冻结策略允许原图不可用时用原生非H组成保守去污染，新7件适配待真实运行；不反演Coulomb或推断键。

Alpha34点时85父任务/578.862222观察核时。45个PubChem分片闭合11,250,000原始行，其中10,251,456筛选通过、997,926化学排除、618技术未决；尚未全局去重去污染。六CSV全源C0证据保留，COCONUT与有限500片队列继续运行。Main35为467父任务/366.964444观察核时；新后继父成本按实际单项另存，不能与重叠快照重复相加。

代码执行提交472312bc8f99881a4487994b402b0549eada4234；公开data-v1为6c15b4f0c44fab3f506f15dab3dbe10cecdf97b8，同树d80a67126d2d9c78c1d70499650788d223b952b3，91文件、只公开源码。Source21实际PASS：3022文件/1943Python/1311原源码核验、错误0。

机器检查点 `/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/active_checkpoint_v30.json`，SHA `936ac09113049c595ef995d552754739a6860700f2ab79a7d3888e66bf570879`。
