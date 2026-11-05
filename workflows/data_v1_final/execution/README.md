# CPU 任务统一提交

`submit_reviewed.py --request /absolute/request.json` 仅由主 agent 在 sonmi 执行。它不启动训练，也不自动推进后续批次。

请求须绑定脚本和全部源代码/配置的绝对路径、字节数及 SHA256，声明 kind、node、cpus、memory_gib、wall_seconds、estimated_peak_output_bytes、pilot 与 root_review。主 agent 先审核具体试点及其科学输入，再将 root_review.status 写为 APPROVED；超过500核时的非试点还必须绑定已验收试点。

提交前核对：至少16CPU、14–19上的构象/量化、默认20上的其他分析、最长48h、脚本LF及声明与请求一致、没有GPU申请、账户quota扣峰值后至少200GB、所有用户当前声明内存与AllocMem中的较大者加新任务不超过85%。同名活动任务及已经登记的intent/receipt均禁止再次提交。

新鲜的intent在sbatch前fsync，科学程序可用它验证提交时预算。sbatch返回的真实job ID先持久化，再核对实际WorkDir/节点/CPU；后验查询失败仍保留job ID且禁止自动重投。receipt仅表示提交，不代表运行或科学完成。状态和核时由主agent根据sacct父作业与最终产物闭合。

`test_submission_guards.py` 的11个标准库边界测试已在compute20通过，包含软quota为0、内存单位、节点/CPU/时限/源码SHA、CRLF/GPU、未审请求、500核时门槛，以及控制器读回失败后的job ID保留和禁止重复提交。测试未提交真实Slurm任务。实际日志在本run仓库外control/submission_guard_tests_v2.log。
