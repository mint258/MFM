# 待用户批准：P′限定15调用数值精度诊断

状态：PROPOSED_UNAPPROVED_NOT_EXECUTED。这里只准备提案和纯元数据源码，未运行测试、准备科学输入、初始化QM worker、提交作业或调用程序。它不是修复结论；原15FAIL及生产/full/2000 HOLD不变。

现有0QM证据表明：实际输入满足native打印精度内的刚性关系；同向重复和精确P90通过原门，一般R可重复出现原生能量、梯度及偶极差异。各调用显式报告收敛，xTB一般R为14步而B/P为13步。SCF原因仍UNKNOWN，stdout与JSON独立表示亦未全部闭合。新增实验只测试更严格数值设置是否改变这种模式。

## 两条固定设置及依据

1. MOPAC仅给pm7_B追加 `SCFCRT=1.D-9`，保留PM7、1SCF、GRADIENTS、LET、AUX(PRECISION=6)等原关键词及线程1。官方定义SCFCRT为相邻迭代的主要能量变化准则，单位kcal/mol；默认通常为1e-4，允许显式替换，1e-9在所列常用区间内。其他限定条件仍由原程序实施，过严可能不收敛；不保证有效全部阈值恰等于该数字。[官方SCFCRT](https://openmopac.net/Manual/scfcrt.html)、[SCF判据的限定条件](https://openmopac.net/Manual/scf_test.html)

   新关键词完整行（程序仍按原逻辑追加THREADS=1）：

   `PM7 1SCF XYZ GRADIENTS BONDS MULLIK PI SUPER ENPART DISP AUX(PRECISION=6) LARGE LET CHARGE=0 SCFCRT=1.D-9 THREADS=1`

2. xTB仅给本次用到的singlepoint及perturbed-gradient追加 `--acc 0.01`。官方允许0.0001到1000，数值越小会同时收紧积分筛选与SCC收敛；原实际accuracy为1.0。此参数同时影响多个数值环节，所以即使改善也不能单独归因为SCF。[官方accuracy语义](https://xtb-docs.readthedocs.io/en/latest/sp.html)

   单点完整argv尾部：`input.xyz --input native.inp --norestart --parallel 1 --gfn 2 --chrg 0 --uhf 0 --acc 0.01`

   梯度完整argv尾部：`input.xyz --input native.inp --norestart --parallel 1 --gfn 2 --grad --chrg 0 --uhf 0 --acc 0.01`

   executable仍为原协议指定的同一SHA文件；不改变温度、restart、最大迭代次数、seed、方法或版本。不另加PRECISE/GNORM，也不优化几何。

## 精确范围与隔离

只用原六来源case054/055、058/059、060/061，对同一molecule_01200493、三condition各做B1/B2/R1/P1/P2，总计最多15次新QM调用。沿用原record ID、seed20261010、扰动sigma0.1、同一实际坐标token/原子顺序及一般R/P90矩阵。MOPAC目标文件只改首关键词行，其余输入字节必须一致；xTB输入文件保持全字节一致，仅命令参数不同。新实际postcall输入必须与新targets闭合。

原12-task顺序保留以满足冻结engine接口，但本提案仅改并执行pm7_B、xtb_singlepoint、xtb_perturbed_gradient这三类；其余九类不改不运行。因此这不是全12任务配方的验证。程序仍为原MOPAC23.0.3/xTB6.7.1构建及binary/env锁，单次原900秒timeout不变；不改变原解析、容差、mask或原返回状态。

静态接口审查确认原engine可从独立protocol dict/path初始化；原NATIVE.invoke直接消费task关键词/argv，不需要重写或包装invoke。需要用户明确批准的科学配置变化是这个新QA协议及其精确三字段diff；它不能冒充原production protocol SHA。新once域含namespace、new protocol triple、原prepared triple及qa-ID；不重开、清除或复用旧15次once，不以替换case重试失败/UNKNOWN。

## 资源、留存与判读

最多一份16CPU、CPU-only、无SBATCH内存/exclusive申请的分配，墙钟最多2小时；最多15个单线程native调用，每调用仍900秒。Root按现场允许QM节点的空闲CPU安排。整体输出cap2GiB，保留原每调用raw16MiB/result8MiB边界及全部原生输出；这是沿用此前15调用的保守容量包络，不是新试点的运行时/成功率预测。所有注册cap之后仍保留200GB有效quota余量，并监测实际RSS/MemAvailable；压力停止新派发、自然drain，不新增强制信号。所有实际失败、启动及验证核时照实记账；费用免费不等于核时为零。

新严格B/P重复与原6来源、旧15、1845/1891事实并列比较。继续用原输入/轴/原子序、协变、native打印及stored/raw门，所有状态与新SCF实际设置/版本/argv均留证。stdout full前三分量a.u./第四总模长Debye分开，JSON/atomic贡献/阶段缺口保留。后继新observer须先修正自身SCF表尾分段，不能采用1891辅助rows53/54；原1891源码和报告不改。

任何FAIL、TIMEOUT、技术UNKNOWN或门未满足都报告并保持HOLD，不自动扩大范围；用户批准的上限不是必须凑满或重试的数量。即使这15次全过，后续仍须独立审查20分子、全部12任务及原旋转QA，再决定是否提出新生产配方。这里不授权20分子执行或全量/pool放行。

供Root最终一次询问用户的限定句草案：

> 是否批准仅这一次最多15调用的数值精度诊断：MOPAC追加SCFCRT=1.D-9，xTB追加--acc 0.01；保持原6来源/15arms、程序方法版本、seed、实际坐标、900秒单调用timeout及全部质量阈值；最多16CPU、2小时、2GiB输出，失败不自动重试，生产与全量继续HOLD？

新纯源码四件在 `workflows/data_v1_final/pprime/strict_numerics_qa_proposal_v1`，仅有协议精确diff/逆变换、独立once-key计算、metadata draft和三个未执行的纯测试；没有QM执行入口、提交器或自动审批系统。用户未批准之前不得把拟议protocol传入任何QM初始化/调用。
