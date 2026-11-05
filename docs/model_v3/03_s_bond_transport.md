# 可选原生 S bond transport 修复

日期：2026-10-25（Asia/Shanghai）。实现基线：Root `8fa743ecc864699e94141e60bf33ba174c6a3ed4`；隔离分支 `model-v3-s-bond-transport`，工作树 `MFM_model_v3_s_bond`。
当前状态：**实际定向及整合前后全量 CPU 回归均通过**。新增20项通过/1项CUDA条件跳过；完整套件2,388通过/2项CUDA条件跳过，102个测试文件。实际代码与闭合见末节。

## 问题与修复边界

既有 `phase1/v3_data.py` 的 DecodedSample/collate 只把 x/pos 放入 PyG Data，丢失旧 S 键任务需要的原生 rdkit_bond_index、rdkit_bond_order、rdkit_bond_status。原结构桥会复制输入 Data 的原属性；直接保留这些字段的自定义 provider.prepare 不受此 loader 缺口影响。

本修复只扩展模型侧**已解码原生事实**的可选传递，不实现 D1 wire codebook，不改标签、head、loss、采样器、三视图、H0 或公共 factory/shared。D1 draft.3 审阅及 tensor/r73/r82/扰动几何/原因 sidecar 需求仍按外部冻结报告独立处理，没有借此签署 v3.0 或验收 D3–D6。

## 接口与行为

`NativeBondTransport(pair_index, order, status, fail_reason='')` 明确承接现有模型原生属性：

- pair_index：CPU long[2,p]，原分子本地原子行索引。
- order：CPU long[p]，原始值逐项保留，包括 0、负值或未知代码。transport 不 remap、不筛选、不排序、不镜像、不去重；既有 S head 保持原有效性过滤。
- status/fail_reason：原始字符串逐字保留；不改大小写、不 trim，也不把失败/未知状态改为 ok。

`DecodedSample` 末尾增加 `native_bonds=None` 默认参数，原有 7 参数调用保持兼容。只校验 tensor 类型/dtype/shape、索引范围和字符串类型，不代替旧 S head 决定哪些键是有效监督。读取和 collate 边界重新校验可变 tensor，拒绝被修改为越界的索引。

全批 native_bonds 均为空时，保留原来的无 bond PyG 属性路径。混合批为保持 PyG keys 一致，仅给缺失行补空 pair/order 和 status=''、fail_reason=''；其中 status='' 正是旧 `SharedBackboneMFM._graph_string_attr` 的真实默认值，不是虚构成功。显式传入的状态原样保留。PyG 只做正常批次原子 offset；unbatch 可恢复原 pair 顺序与值。`.to()`/`pin_memory()` 沿用已有 PyG graph 属性迁移能力。

## 新自动化测试的声明范围

独立文件：`current/tests/test_model_v3_native_bond_transport.py`。
按源码参数化展开预计 **21 项**；无可见 CUDA 时预计 20 项可执行、1 项 CUDA pin/transfer skip。该数量是静态预估，不是实际运行结果。

1. 两分子的全部原生 graph 属性与 direct Data 精确比较，包括 offsets、unbatch、原输入不变、重复/乱序 pair、未知/零/负原始 order 与 status/fail_reason。
2. 全无 bond 的旧 keys 和旧 head 的真实空默认状态；混合缺失、失败、零键记录不增加监督；三个独立零监督负例要求 bond count/raw=0 且旧 bond head 无梯度。
3. 512 维/1层的 direct 三视图桥与 decoded loader 桥：非零 S bond raw/count，S element/noise、P/D 与 clean H0 精确一致。逐字段及总损失对**全部 named parameters** 比较 None/非 None 梯度结构和 torch.equal 数值。
4. 严格反向测试限定单 intra-op 线程并退出恢复原设置，保持 torch.equal，不放宽容差。依据保留的 4520338 原 source 自身 8 线程重复反向不逐位诊断；本测试不将其归因于具体算子，也不宣称 GPU 逐位确定性。
5. 全参数梯度结构保存为 pytest 自有 tmp 目录中的 `native_bond_gradient_structure.json`，包含每任务/总损失的参数名、None 标记、shape、逐位比较结果；不保存梯度 tensor。
6. PD-only 输出保持一致，旧 S heads 无梯度；类型/shape/字符串/索引错误和非 typed transport 明确拒绝。
7. CPU `.to()` 保留 graph store 独立性；可见 CUDA 时真实测试 bond 数组 pin 与 nonblocking transfer。
8. 已绑定 dataset 单进程读/close；真实两个 spawn worker 各自打开只读合成源句柄，传递原生 bond 并与 direct 输入比较，退出后 join 和关闭事件闭合。provider fixture 自己注册其句柄清理，不把 fixture cleanup 推广为任意生产 provider 的关闭证明。

建议 Root 在受控 Slurm allocation 内先执行：

```bash
PYTHONPATH=current:$PYTHONPATH /share/home/zixiao/.conda/envs/chemprop/bin/python -B -m pytest \
  current/tests/test_model_v3_native_bond_transport.py \
  current/tests/test_model_v3_labels.py \
  current/tests/test_model_v3_structural.py \
  current/tests/test_model_v3_transfer.py -q
```

依赖路径、线程/资源设置、日志与源码前后 SHA 由 Root 的既有 CPU wrapper 明确绑定。定向通过后仍需完整 premerge suite；不复用旧 2368 PASS/1 CUDA skip 作为本修订结果。实际作业终态与完整来源见末节。

## 修改文件

仅修改 `current/phychem_mfm/phase1/v3_data.py`；新增上述独立测试和本报告。原 S 头/损失/结构桥、旧测试与其单线程 fixture、数据线仓库、外部 draft.3 审阅目录均未修改。

## Root 实际整合验收

定向作业4520643：51项中49通过、2项CUDA条件跳过；其中新文件21项为20通过/1跳过。全部源前后SHA一致。真实两个spawn worker和句柄关闭、非零S键监督以及六项任务/总损失的全参数梯度None结构与torch.equal均通过；参数名/shape/布尔证明已保存，不导出梯度或权重。

分支代码`8e1223ba79861f7e3f8d9d453d7b3599ee447d4d`的648–651四个实际C0分区完整覆盖102文件；Root整合代码`91f0c40a78478447a14ef2e8e91f05c07e0f5019`的656–659四个实际C0分区再次完整覆盖相同测试源。两次各2,388通过/2 CUDA条件跳过，无失败或错误。每作业CPU节点16核/32GiB，输出与进程监督闭合。

本修复不实现或验收D1新wire/provider、tensor、basis索引、扰动视图或D3真实标签，不改变旧原生head/loss有效性语义。CUDA pin/transfer尚无本轮GPU实测；两项条件跳过明确保留。完整机器结果见results/S_native_bond_*.json。
