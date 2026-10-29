# 模型线开发 GPU 作业自动内存声明方案 v1

状态：PROPOSED_USER_APPROVAL_REQUIRED，尚未应用或提交新 GPU 作业。

适用范围：开发服务器上的模型线 GPU 数值验收、性能测量及指南授权的短程训练；不包含学校付费服务器或正式预训练。已有作业、冻结源和失败记录不修改。

## 实际阻塞与只读试排

2026-10-29 08:38 Asia/Shanghai，compute-0-20 的 Slurm 观察为 CPUAlloc=52/104、RealMemory=120000 MiB；实际 MemAvailable=127520012 KiB。未使用的物理 4090 `GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02` 当时无计算进程，显存空闲 48539/49140 MiB。资源状态只作当时观察，不能作为以后准入。

同一节点、16 CPU、两小时的 `sbatch --test-only`：显式 `--mem=64G` 返回 `Requested node configuration is not available`；不声明内存大小返回可试排。试排没有提交计算作业，输出中的预计 job number 不计为实际作业。现有两个带固定内存声明的模型任务仍为 PENDING。

## 拟变更

仅对新作业省略 SBATCH、sbatch argv 及继承环境中的显式内存大小声明，不使用 `--mem=0`。不添加 exclusive、overcommit 或 oversubscribe 选项。Slurm 实际默认值原样记录，不声称获得了 64 GiB 物理内存保证。

以下约束全部保留：

- 每项至少 16 CPU，原 GPU UUID、实际进程和公共 UUID 锁核验；单卡一个模型实验，不抢占或终止其他任务。
- 原软件内存预算：普通 A 验证 64 GiB、RSS 上限 56 GiB；已有 Native B 仍采用其原 32 GiB、RSS 28 GiB 预算。本方案不扩大预算。
- 新作业的软件预算连同已登记自有并发 GPU 作业预算，必须低于节点 RealMemory 的 85%；其他用户已声明的有限内存也纳入原准入。无法解析的声明不虚构为有限保证。
- 每次提交和启动均重新核验实际 MemAvailable，保留原软件预算加节点 15% 余量；RSS 超限立即按原监督规则停止自有任务。
- 原 GPU 显存 85% 上限、双 2 GiB 输出/私有目录保护、quota 与所有已登记未来存储预算、原墙钟/进程身份/清理门不变。
- 旧科学输入、模型/种子/优化器、20 批次及 500 步验收、R1 配对计时、W&B、所有误差和失败规则不变。每项新运行绑定新的资源政策版本及预注册方法，不回填旧结果。

若用户批准，先冻结并发布相应新声明规则及方法，再现场准入、一次性提交；既有 PENDING 作业不自动改写或取消，须按其真实源资格和防重复规则逐项处理。

## 需要确认的依据

`C:\Users\mint\.codex\skills\huagong_hpc_requirement\SKILL.md` 的 2026-10-29 CPU 自动内存条款明确写明“GPU训练/微调及学校正式预训练的资源规则不变”。当前授权只扩展到 CPU，因此本 GPU 声明变化须获得用户明确确认。
