# 本次代码交付验证

日期：2026-10-16。Linux 检查和测试在默认开发服务器的 `compute-0-20` 上进行；没有使用付费学校服务器，没有启动正式预训练或新的 QM/数据生成。

## 静态与来源检查

- 1,317 份服务器代码/配置/协议按原字节导出；逐文件源路径、大小及 SHA256 见 `SOURCE_MANIFEST.json`。
- 所有候选 Python 文件执行编译检查；检查器不导入或执行历史生产脚本。
- 检查大文件、模型/数据/归档后缀和常见嵌入式凭据；未发现需上传的重资产或凭据。
- Git 索引的 blob 与所有导出文件原字节核对，防止 Windows 换行转换破坏冻结来源。
- 两份已被替代且有语法错误的 `wp5_reproduction50_v1.py`、`wp5_reproduction50_v2.py` 不上传；服务器原件保留，排除原因记录在 source manifest。重复的 S 源码引用复用 `workflows/sprime_s/scripts`。

精确导出核验：`python tools/check_repository.py --verify-export`。后续新开发默认用不带该参数的语法/大小/凭据检查，保留原始 manifest 作为追溯依据。

## 核心回归测试

作业 **4515505**，Slurm 实际 `COMPLETED / 0:0`，compute-0-20，16 CPU、16 GiB、实际47秒。**191 passed**，pytest 用时24.25秒，3条第三方弃用提示。

测试文件：

- `test_encoder_api.py`：H0/图池化接口与无任务融合约束。
- `test_backbone_checkpoint.py`：主干 checkpoint 和梯度等价。
- `test_dataset_parity.py`：原 LMDB 样本对齐、batching 与恢复。
- `test_phase1_full_corpus_loader.py`：合成 tiny LMDB 原生 transport、覆盖率、预取和已消费游标恢复。
- `test_phase1_downstream_training.py`：冻结/微调优化、追踪、checkpoint/RNG 恢复和独立参考算法。
- `test_phase1_downstream_readout.py`：源原子顺序、候选掩码及下游读出。

首次作业4515504因测试收集缺少 `PHASE1_NATIVE_TRANSPORT_PATH` 而退出（FAILED/2:0）；补齐绑定到仓库导出的 transport 后，用独立4515505完成上述测试。原失败记录保留，不修改科学源码。

## 新 H0 推理工具

同一4515505中使用临时随机初始化的合成模型测试，无真实训练权重下载。两个 XYZ 分子、5个原子，验证：

- 普通 `model_state/model_config` 和 S-runner `model/config_sha256` 两种 checkpoint。
- H0 形状、图池化、batch-size 1/2 等价和文件/原子顺序。
- 配置 SHA 不一致时拒绝加载且不写出结果。

临时 checkpoint/XYZ/npz 在测试私有临时目录内创建并自动删除。小型验证结果见 `INFERENCE_CHECK.json`；CPU 环境见 `SERVER_ENVIRONMENT.json`。

## 验证范围

此次验证证明代码交付、上述核心接口和新增推理工具可用，不代表重做整个预训练、全部 WP5 科学验收或新标签 LMDB 整合。其他原 workflow 仍需要外部数据/证据与实际运行资源；GPU/CUDA 容量和兼容性不在本次 CPU 检查范围。
