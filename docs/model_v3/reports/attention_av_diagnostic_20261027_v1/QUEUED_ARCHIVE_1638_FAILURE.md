# Native7 queued JIT 4521638：只读失败闭合

观察时间UTC：2026-10-26T22:11:12.9891266Z。Root实际回报1638 FAILED/1:0/1秒；监督器实读FAILED/exit1、first_failure=child_exit1、elapsed=1.0150103755295277s、remaining=[]、retirement=null。GPU初始化未允许。

失败是计算节点Slurm分配内向登录端点202.38.247.57:22发起SSH得到Connection refused，SSH returncode255、stdout空、无Python subprocess exception；bootstrap因非零RPC抛异常，最终Python/Slurm退出1。它尚未到host-key/authentication或远端Python，不能归因密钥失败，也不能用此前login/nested-SSH探测证明分配内网络可达。未重试、取消或修改源码。

本地compute13 UID1278、job4521638的kernel/cgroup observation已产生；远端controller/内存核验、fresh120s quota、原v1 archive worker均未启动。N/native7_archive_JIT_4521638目录、.allocation.json、.prepare.json仍不存在。原worker未处理SDK/journal或生成归档。

共享archive路径此时已存在，不能再谎称当前不存在。其RESULT.json actual_job_id=4521639，来自Root随后原v1即时路径（Root已回报C0/11秒），不是1638的输出。RESULT的worker状态原样仍为ARCHIVED7_PENDING_ACTUAL_CPU_PARENT_C0；本报告不改它，也不代替1639的独立parent闭合/入口操作。

当前冻结JIT pins仍3668e86b55336faf616b55acb035082d17d42d0f2ddccdffaceec8141af84937；4 own leaves及9 dependencies按原bytes/SHA逐一匹配，包括原v1 worker/export/tests、10bb CPU supervisor、runtime monitor、公共hostfile和固定wrapper。失败后bootstrap的尾部verify未执行，故本报告依据的是现在对冻结清单的独立只读复核，不伪称它产生了运行尾部source snapshot。

旧监督器last_total_bytes=4575，private sampled_max=496、first_sampling_failure=null、exact_peak=false。只读补列新request/queue/observation/RPC的8个常规文件，共10873B；确切1638监督/stdio文件7252B。均为新输出，不当历史输入；1639归档payload不计入1638。完整逐文件raw refs在JSON。

限制：external_bytes及final whole census在RPC成功以后才定义/执行，失败路径没有finally完成这部分计量。因此1638缺少JIT自身最终512KiB/whole2GiB census；旧监督器自动覆盖archive/private/stdio/journal/storage，不能据其4575B声称已包括N端所有新文件。本次补查仅逻辑常规文件字节，未从Windows挂载测Linux目录st_size或私有/tmp的最终物理大小，不充作完整物理census，也没有观察到预算越界。旧16MiB finalization reserve仍原样保留，不能据此捏造本次计量已闭合。

后续边界：原metadata RPC即使成功，也必须保持唯一实际job/node/UID/controller与fresh quota绑定；本次未到该阶段。固定7条归档、科学门槛、旧FAILED/HOLD和原源码均不变。Root已选择原v1即时路径，本报告不开发替代JIT、不操作归档/统一入口。

- compact JSON：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native7_archive_queued_jit_1638_readonly_failure_v1.json`；27783B；`50d1504d360cfb7aef45b86e99a12226df0fc3722e88f68c51690eb385d50a7d`。
- supervisor：`/share/home/zixiao/descriptor_analysis/runs/phase1_full_corpus/wandb_archive/model_v3_20261025/native7_20261027_v1.queued_supervisor.json`；`2bd41117a55cbc12e0e492c747ac9e16cf4dece2732fcf5151d12a2b3c124b91`。
- raw RPC：`/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/native7_archive_RPC_4521638.json`；`8c844d5d75b01779a04288dee0032f075475a24dff005dabbb7049e4ae4e71a9`。
- later1639 RESULT（仅溯源）：`/share/home/zixiao/descriptor_analysis/runs/phase1_full_corpus/wandb_archive/model_v3_20261025/native7_20261027_v1/RESULT.json`；`9bddaa5426e33d7c495ffaf819b35f33b343e599c7ccaff9ecdf8e4c624be49d`。
