# C4 固定 H0 捕获：参数审计修复 v2

2026-10-27。延续公开预注册 4aadef960ac06c7630ee4f48ab83806df139689c；本文件在第二次捕获执行前提交。

首次捕获4521484实际FAILED/1:0，分配11秒、16CPU、node21。4次encoder forward已返回，但参数SHA审计抛出自动微分上下文错误，完成捕获组合0/48。source前后一致；监督器确认无剩余记录进程、私有清理错误或对外部GPU进程发信号。原失败及其成本保留，见[实际闭合](reports/fixed_h0_capture_failure_20261027_v1/ACTUAL_FAILURE.json)。

原measure_case把参数摘要放在inference_mode中；新增捕获在返回后再做摘要，退出了该上下文。摘要先对requires_grad参数执行isfinite，再detach，触发abs/out自动微分错误。v2只用短torch.no_grad() helper包住两处只读参数SHA检查，调用后恢复调用方上下文。原forward、参数requires_grad、hook、backend、公式、判定阈值均不变。

[完整差异和逐字未变部分](../../tools/model_v3/analysis_sources/fixed_h0_shadow_v2/OPERATIONAL_DIFF_v2.json)明确记录：request、protocol、shadow_common、shadow_terminals与v1逐字相同；其他修改仅v2来源与输出路由。v1和原1435的38个失败不覆盖。完整[源快照](../../tools/model_v3/analysis_sources/fixed_h0_shadow_v2/)的原manifest SHA256为230a1ed03f8ad9318d94d70f75f4951c2b754fae393618640932aceb245d42b8；Root实际静态检查198原始来源、161个Python AST、8个bash脚本通过。

沿用全部48组合、192次forward、128MiB输入、原GPU16CPU/32GiB/1100秒/whole与private各2GiB，以及CPU16CPU/16GiB/4workers×4线程/120秒的预算。CPU仍须等待本次真实capture C0及输入、参数和源闭合后才执行。此修复不构成捕获成功、C4通过、候选采用或最终冻结；后续结果另记。