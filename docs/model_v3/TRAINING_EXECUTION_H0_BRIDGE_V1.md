# 训练 execution 检查点与 FP32 H0 桥 v1

本文描述显式 opt-in 工程接口，源码交付时未执行新 QA，不构成数据、容量、C4、模型或配方验收。

## 唯一执行合同

训练配置只有顶层 training_execution。共同入口 phase1/v3_training_execution.py 负责解析/最终定型，trainer.contract.training_execution 与 extra_state.execution.training_execution 保存同一份合同。桥只调用共同适配器，不重新选择 auto、不复制容量或精度 policy。

共同适配器的 validate_h0_export_contract 是纯元数据能力检查，与实际 build_h0_export_encoder 使用同一支持边界。桥提供 validate_h0_export_capability(model_configuration, training_execution_contract)，返回 supported、training_execution_contract_sha256、H0_export、H0_export_sha256、H0_dimension 以及两个 false 的容量/科学授权标志。它不创建模型、不读取数据或权重，不是验收证书。READY consumer 仍保留原 6×512、来源、数据角色、panel 和日志门。

## 安全读取与显式路径

load_encoder_pair 新 keyword enable_training_execution 默认为 False。新训练配置、保存的 execution 扩展或 performance 包装不能落回旧 plain builder；需要显式 True 和已支持的原 sample CP。旧无 opt-in 请求、Native 与 B3 分支不增加新 metadata 键。

仍由原入口绑定原 configuration、payload.pt 和同目录 COMPLETE.json 的原 bytes/SHA，使用 weights_only=True，无 unsafe pickle fallback。原 sample CP 与 panel ACK schema 不变。新分支另核共同 execution 合同/保存的实际运行 projection、原源图、真实样本预算/milestone、sampler、scheduler、update/log cursor 和无 pending log，再严格装载 encoder. 状态。优化器/provider/RNG 不由 H0 reader 恢复。

导出构造器只能是共同适配器声明的固定实现。它使用保存的 resolved 策略和显式 FP32 export mapping，不运行 auto 选择，也不把训练容量 profile 授给新的下游 packing。参数、持久缓冲和公共 H0 保持 FP32；检查内部 wrappers 的 precision，避免仅靠外层关闭 AMP。实际 pretraining 与 export options/provenance 分列。

candidate 与 seed=20261025 的 matched random 共享同一 export builder、模型配置、C1/packing 策略和有效 FP32 runtime；参数所有权独立。不能把 BF16 训练 forward 与独立 FP32 H0 称作位等重放。compiled 或其他未支持的导出映射在 metadata 阶段拒绝，不能先 READY 再静默 plain-load。

## 评估入口和缓存

prepare_dev_evaluation.make_request 增加同名 keyword；CLI 可传 --enable-training-execution，也可在原 JSON template 明确为 true。两者相互矛盾时拒绝。False 默认不写新 request 键。

新 opt-in 要求原 primary sample configuration 与 COMPLETE，并要求声明实际 adapter/bridge/evaluator 源文件。evaluate_dev_panel 继续原资源、packing、锁、SDK 与 ACK 路径，向 loader 转发显式开关；仅新 opt-in 的 H0 编码进入共同 adapter.h0_export_context，按映射显式应用 highest/TF32/deterministic 等 controls 并在成功或异常后恢复，readout/default/Native 策略不变。load/builder 本身不静默设置训练全局状态或 RNG。CUDA 的 CUBLAS_WORKSPACE_CONFIG 必须由实际 fresh worker 在初始化前按合同设置，context 缺证拒绝且不迟设环境变量。缓存来源另绑定已验证 execution 合同的 canonical hash、完整小 H0 映射/hash、桥实现、committed 游标/flags 和原 COMPLETE。完整合同只在原 CP/pair 保留，避免六份 cache 重复完整源码图；不扩大原 2MiB JSON门。统一 stdlib-only training_execution_cache_projection 先验证完整 provenance/hash 闭合再投影，不能拿投影代替原件或 capability/source 验证。loader/evaluator 先核共同 policy，ACK 再将两 hash 对原事件。旧默认/Native cache source dict 不变。

## 历史 Native 路径保留

旧 3d9 长 CP 继续使用独立、已发表且完整 QA 的 MFM_model_v3_native_checkpoint_bridge_v1@17f975bb094c9c3ec010d7f8134c5700adcc85e4 原受监督 evaluator 命令/PYTHONPATH。其 performance 仍为旧 3d9 字节。新整合树不能重写原 CP source inventory 或假装旧训练由新代码产生；也不拼两树 namespace 或清 sys.modules。

## 工程核验与尚未覆盖

新增测试调用 SA3 的两 fresh-CLI engineering helper，只有一个 6×512 大检查点 fixture 族：有效更新、safe CP、fresh CLI resume、outbox、严格恢复 producer 后的 H0 与 matched random。数值对照标为 saved-state roundtrip，不冒 pre-save 观察；拒绝测试复用这些检查点的元数据，不复制大权重。原 ACK 测试使用真实 H0 cache，但 panel 分数及其外层/SDK证据明确是既有 synthetic grammar fixture，不是实际九任务/SDK验收。计划核真实 optimizer 更新/save/resume/outbox/桥/cache、FP32 同路径 H0、matched random/RNG 隔离、runtime/config/来源/游标/mapping 变更拒绝、默认字典兼容和缺 opt-in 拒绝。测试计数与通过只由 Root 实际 collect/运行报告；不能把 source-only 或合成 CLI 当作真实 D3、CUDA BF16、完整 9×2 panel、三 GPU容量或 D5/D6 验收。

源码必须与共同 execution adapter、trainer/proxy/READY consumer 一起合并到隔离树后做实际 QA。旧冻结源、检查点、失败与来源记录不修改。

## H0-CUDA-PREINIT-001：源码修订 v2

原 v1 六叶及其 freeze/handoff 按原字节保存在外部 execution_H0_bridge_v1_source_snapshot；没有覆盖其历史记录。v1 的 context 拒绝条件正确，但生成脚本未在 CUDA 前声明 CUBLAS 环境，不能称 CUDA 已可启动。

v2 只为新 opt-in 请求增加 h0_preinit：原 configuration rawref、唯一 metadata policy rawref 和由它产生的 runtime_controls。策略值来自 SA1 的同一 stdlib 叶 phase1/v3_training_execution_policy.py::h0_runtime_controls_from_deterministic；adapter/context 也委托该函数，不在桥/脚本复制另一套 policy。固定叶路径和原 SHA 绑定后才执行同一 raw bytes，配置不能指定任意可执行路径。

make_request 生成此声明；生成 sbatch 的 exec 前按声明设置所需环境，已有冲突值拒绝。evaluator 首先运行 stdlib metadata 门，在 load_plan/package/model CUDA 操作之前核 request/config/source/policy 字节与同源 controls；CUDA 已初始化则拒绝，绝不迟设后声称初始化前已生效。validate-only 使用同样来源核验但不设置环境、不授运行准入。后续完整 CP 的 H0 map/source controls 与预声明再精确比对，原 context 仍独立核验并保存/恢复 globals。

旧默认/Native 不增加 h0_preinit，不增加 CUBLAS 脚本行或改变其环境策略。原资源、锁、CP/panel/ACK schema、weights_only、FP32 H0 API和 2MiB 元数据门均保留。新增测试核实际脚本顺序、同源声明、缺失/不一致/晚初始化/冲突拒绝，以及无 Torch 的纯元数据子进程；它们仍是 CPU/metadata 工程核验，不能宣称 CUDA 初始化、模型前向或 GPU 性能通过。全部 63 项仍仅计划，尚未 collect 或执行。
