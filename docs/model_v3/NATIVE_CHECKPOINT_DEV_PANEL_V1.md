# Native-S安全checkpoint至开发面板

本增补只接通既有Native-S FP32/BF16成员的只读H0加载，不改模型/factory/config、训练、下游协议或旧checkpoint schema。真实Native权重尚未在此新bridge执行；源码/测试是待Root CPU验证的实现，不是D5、B验收、架构选择或pretraining-seed SD。

## 已有闭合输入与缺口

544用冻结9638 evaluator、A00 source486 generic model_state和READY准入。其9任务/18cell、ridge+Linear64、1000分子bootstrap、421 selected TRAIN store仍可复用；原专用A00 READY launcher不可直接冒作Native准入。当前base3d9 bridge已有ArchitectureStepTrainer typed sample分支，但Native没有该分支的architecture_extension/trainer configuration/schema字段。

Native真实元数据（未读取payload）：slot011 `checkpoint_u10000_log10021/COMPLETE.json`记录10000更新/4076032draws、198763433B；slot012 `checkpoint_u11000_log11023/COMPLETE.json`记录11000/4480125、198765289B。它们在N/native_S_B20k_v3/slots/SLOT/child/下，schema=model_v3_training_checkpoint_v1，producer code3d9。原writer保存安全内置类型与CPU tensor，发布COMPLETE前用weights_only回读；这不替代新loader在实际CPU/GPU环境的真实核验。

## 最小现成入口

沿当前 `tools/model_v3/prepare_dev_evaluation.py:make_request` 与 `evaluate_dev_panel.py`，参数为：原closed `child/member_result.json`作model_configuration；同CP目录`payload.pt`作checkpoint、`COMPLETE.json`作training_completion；state_key=model、pretraining_seed=0、reference_kind=primary，不启用architecture_candidates。不转换权重，不新增导出格式，不复制原数据/训练标签。原TRAIN面板/packing membership与两readout协议不变；为Native建立fresh run/output/cache并绑定实际新evaluator codeSHA与source inventory，prereg39cf保持。pretraining code/data/cursor与downstream store/evaluator code分别记录。

新helper只认原existing_native_S_precision_member_v1及明确S-only且FP32或BF16训练contract。先bind/hash同目录marker和原payload，再torch.load(weights_only=True,map_location=cpu)，没有unsafe fallback。校验marker/payload bytes+SHA、六bindings、contract canonical hash、source/registry/data/normalization、完整member/common/seed/precision、sample clock/sampler/input-chain和已保存cursor。仅JSON的tuple/list transport以原producer canonical hash比较，不能将bool/int或其它语义差异折叠。

仅接受完整训练state中的严格encoder.子树，拒绝其它namespace/缺键/dtype/非finite；保留旧strict_state验证。candidate与random均使用相同原source-bound build_performance_model及producer声明的common.base_options（FP32）。严格要求execution.encoder等于replace(base_options,precision=实际训练member precision)，保留训练FP32/BF16 options；内部Runtime*会自行开启autocast，因此不能仅靠外层关AMP，而由独立FP32导出模型显式禁用这些选择性BF16上下文。权重不转换，源变化不能靠同形状混过。S registry只构造三字段metadata，不读取targets。原NativeSPrecisionPlan复用验证全部20k/10240000及validation grid，已知整数拒绝bool，sampler/input-chain双方必须有64hex。活跃constructor/common/heads/routes等源为固定mandatory集合，不能从自行声明inventory删掉后逃过。原架构/旧S/full-corpus/generic分支保留。

H0仍FP32，原cache fingerprint绑定真实实现与有效runtime；evaluator的Native-only common_source再纳完整Native provenance及COMPLETE，显式映射/reader/marker变化产生不同cache身份（正常new entry，不称拒绝），旧schema分支的原source dict行为保留；本轮CLI源码与完整source inventory已变，不宣称新树与旧树有相同cache身份，原旧树仍可复现。loader不修改全局TF32/matmul/AMP策略；未来launcher须明确绑定实际export政策并记录。训练checkpoint只读，不恢复optimizer、sampler或RNG；同架构random有独立seed/参数，不能将两个readout seed当两个pretraining seed。provenance分列训练precision/options与H0_export FP32/noAMP options，明确是已声明公共base路径投影，不是BF16训练运算逐位重放。只接受FP32存储权重，不对BF16/FP16权重静默cast。

## Root CPU验证与保留预算

预计新46项：一次真实save_new_checkpoint→6×512性能encoder/多视图wrapper→安全bridge→5原子FP32 H0精确比较与matching random；现有make_request真实接线；marker/payload/bindings/seed/cursor/source/registry/geometry/performance/namespace/dtype/finite与unsafe反例。尚未执行或collect，数量以Root实际XML为准。

仅两module级完整checkpoint（FP32与BF16元数据/FP32存储；空Adam状态，每个预计约90–110MiB，实际以writer结果为准），小负例用内存/metadata，不为每例另存200MB。BF16正例未执行BF16训练，只核真实writer格式与既有FP32 H0 exporter/外层AMP下的FP32输出。预计保留<300MiB，RSS约1–2GiB，均未实测。可在独立16CPU/16GiB、RSS12GiB、whole/private2GiB原监督内先跑新文件；不要把大量其它checkpoint测试无核算合并。显式`-p no:cacheprovider -o tmp_path_retention_policy=failed`避免pytest current symlink残留。

Root命令（仅说明，作者未运行）：

```bash
PYTHONPATH="$TREE/current:$DEPS" CUDA_VISIBLE_DEVICES='' "$PY" -B -m pytest \
  "$TREE/current/tests/test_model_v3_native_checkpoint_bridge.py" -q -p no:cacheprovider \
  -o tmp_path_retention_policy=failed --basetemp "$FRESH_SHARED_ROOT"
```

旧`test_model_v3_encoder_bridge.py`及ArchitectureStepTrainer桥回归应由Root按实际磁盘预算另纳现有回归任务；本增补不运行科学模型或提交作业。新的真实Native CP完整SHA/安全读取与完整9任务耗时仍需后续实际验证，不能因544约509秒先前观测就宣布此新checkpoint的一GPU小时目标通过。
