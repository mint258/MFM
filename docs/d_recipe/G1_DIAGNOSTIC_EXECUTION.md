# G1 seed0 3M诊断执行口径

状态：五份配置已准备，未提交诊断作业。当前训练4539204、主统计4539205和主比较4539206保持原依赖链；本页不表示3M已结束或诊断已有结果。

| 步骤 | 原执行器 | 配置后缀 | 依赖 |
| --- | --- | --- | --- |
| 一次5000VAL F64前向 | `tools.d_recipe.diagnostic_forward` | `forward.json` | 原4539204成功、精确3M checkpoint |
| 闭合几何缓存传输 | `tools.d_recipe.transfer_diagnostic` | `transport.json` | 同条件FORWARD_COMPLETE，实际CPU节点准入 |
| F64几何统计 | `tools.d_recipe.diagnostic_statistics` | `statistics.json` | 原几何缓存转运成功 |
| 缓存层3–5读出 | `tools.d_recipe.layer_readouts` / gpu | `layer_readouts_gpu.json` | 原主读出结束、既有开发层缓存可用 |
| 层统计 | 同上 / cpu | `layer_readouts_cpu.json` | 原层读出及4539205成功，主层6原scores已关闭 |

配置前缀为 `configs/d_recipe/diagnostics/D-G1_seed0_3M_`。精确端点是 `/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/full/stage2/D-G1_seed0_3M/training/samples_3000000.pt`；只消费原seed0/3M，不搜索或载入其他checkpoint。原生产器负责条件对应检查，当前不加载张量。

沿用固定5000VAL/seed20261112、层3–6、F64、1000次分子配对bootstrap/seed20261025与原P统计公式。层6复用主读出/统计，3–5只用已有缓存拟合原探针，不增加编码器前向。诊断仅描述；按任务书单项累计4小时或连续2次失败记UR，不改变采用门槛，也不重启R1已UR的几何诊断。

几何独立scope为 `/tmp/d_recipe_20261120_D_G1_seed0_geometry`，与训练时的开发层缓存分开。原同一固定VAL元信息预测F64数组5,131,075,584B、最大文件4,349,591,552B，直接引用既有元数据，不二次读取旧数值数组。GPU私有峰值8GiB；CPU转运私有峰值12GiB涵盖原数组、rsync临时文件和缓冲。原传输器只复制这个闭合几何scope，不复制原数据库或开发层缓存；原相对/绝对manifest路径保留。

几何配置的实际GPU/CPU节点尚未绑定，未新增节点分配或缓存写入。就绪后先选健康实际节点、核实根/tmp文件系统字节/inode/UID配额与所有同行future，再绑定forward的local_node及transport的source_node/local_node和statistics的local_node，按实际同行预算更新local_concurrent_bytes并登记共享预留，最后提交已有自包含resident入口。CPU候选只在8–19、21禁用；不绕过drain，不占exclusive。原预计GPU其它future8GiB、CPU其它future16GiB和每节点日志128MiB只是待绑定配置基准，不能替代实际节点的完整并发预算。使用真实TimeLimit和提前收尾窗口、TERM/join/reap自有子树。

开发层缓存当前实际生产主机为GPU7，层GPU配置据此绑定；若届时该主机不可用，只转运已关闭缓存并更新实际绑定，不重做编码器前向。CPU层统计仅消费共享预测和scores，没有GPU缓存绑定。几何小统计/原bootstrap直接写共享 `full/stage2/D-G1_seed0_3M/representation_statistics`；全局NFS42074762973B保持，真正执行前仍须原守卫准入。旧文件和所有已关闭统计保留。未新增训练、种子、扫层或独立数值QA。
