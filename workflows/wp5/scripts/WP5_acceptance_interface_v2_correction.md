# WP5 验收接口版本修正 v2

原接口说明 WP5_acceptance_interface.md（SHA9499891f0d0e901f698e73d1ac2282547e96140df150a1e8dbd87ff07dd937be）及原wrapper15627ee6保持原字节。

实际执行统一改为 `scripts/wp5_acceptance_v2.sbatch`。它逐字复制已验证正式main6的依赖前缀：

```bash
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps:/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/scripts:${PYTHONPATH:-}
```

删除原wrapper误写的 runs/.../scan_v2/deps 和额外project前缀；不添加main6未使用的其它docs/deps。新200重算同样使用此环境，显式runner6保持。首次dispatch前 idempotent 创建本轮ROOT/acceptance，资源、stage CLI、内部46h期限不变，无科学变化。

新wrapper SHA256：ce009783723ce8e7c28fe2880e70d0ebc77ff56bad439e39bb44a55c6ae66f78。仅准备，执行由Root统一提交；本次不新增测试或提交。
