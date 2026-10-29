# C1-a：三种 GPU、同真实批次、关闭激活检查点

用户 2026-10-29 v3 明确要求的工程测量。每种 GPU 只跑一次 C1-a 窗口，2 次预热、5 次计时；6×512、FP32/TF32关闭、seed0、原生产 S sampler 和同一 snapshot。不运行 C1-0、小批或 ABBA，不缩批、不因 OOM 重试。该测量不用于架构科学选型。

三卡固定使用 detached 工程代码 `866b2d4a42b36e62abda730585b66c52a011fde1`（功能基线 `e92b6125e0b3ea430970bc7ee24fc152e26919c5`）。共享 pair encoder 没有 checkpoint，backbone 与去噪 head 重算均关闭；保留 C-only 的末端 bias=False。完整训练步含 zero_grad、forward、loss、backward、clip、Adam，CUDA 同步计时；不含加载/H2D/SDK/监控。峰值含初始化、预热及首次 Adam 状态。

| GPU | 实际作业 | 状态 | 平均步时 ms | 原生 S 构象/秒 | 峰值 allocated GiB | 峰值 reserved GiB |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| 4090 | 4525165 | COMPLETED/0:0，46秒，16CPU，node20 | 857.6336 | 596.9915 | 22.4846 | 25.7134 |
| 3090 | 未提交 | 等待实际空闲 CPU/GPU | NA | NA | NA | NA |
| 5090 | 未提交 | 等待实际空闲 GPU | NA | NA | NA | NA |

4090 实际7次更新完成、5次计时，无OOM/缩批/日志故障；supervisor无first_failure和遗留记录进程。卡的实际总显存为49140MiB，不能套用通常24GiB规格。当前真实批次为512条构象、276个不同分子、17896个原生原子、1536个物理视图图/53688个物理原子、最大47原子，实际padded-pairs3393024；8M仅是sampler上限。实际batch receipt为`f8762a29f9c757c1cea7ac8ad59a831d0bb608fa9f20c10308a27e2b3766c2bd`；其他两卡完成后必须核对同receipt及shape才能声称同批。

3090节点现有CPU满额，三张5090均有他人GPU作业。Root已启动只读、有24小时边界的资源等待器（v2，PID3348339）；只在实际资源可用后，每个尚未测量的型号调用一次原Root提交器，不重复4090，不修改他人作业，不以进程短暂间隙冒充已空闲。失败/未知提交不自动重试。资源未就绪不阻塞20配置、真实数据接线等独立工作。

完整实际结果保留于 `runs/model_v3_20261026/C1a_checkpoint_off_4090_first_v1/child/{summary.json,batch_identity.json,measurement_rows.json}`；聚合元数据见 [实际进度](results/C1a_checkpoint_off_three_GPU_20261029.json)。源码保留于 [测量方法](pre_registered_methods/C1a_three_GPU_checkpoint_off_v1/README.md)。W&B已持久离线保存，按每日集中同步；未同步不阻塞。当前只有一张卡的结果，不能推断三卡平均收益或选择C1。
