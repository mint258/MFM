# D1 draft.3 的掩码粒度扩展候选

状态：DRAFT，未获模型线实际确认，未共同签署 v3.0。本文件是新候选补充，不回写已登记 wire_v1/codec.py、store.py 或已有训练契约。146是非恒定统计分量数，不是heads/loss units；原子/矢量/六分量二阶tensor的物理分组、单位、共参考系和最终family仍遵循原D1待冻结事项。

指南要求逐字段/逐记录有效性与原因，并未要求每个leaf都有独立精确原因。SB3已登记 compact mask 的信息边界是：精确逐leaf bool、字段级source/new/review原因集合、部分有效字段的稀疏generic leaf例外。全false字段不含全部leaf精确因果。不得为了适配早期候选 dense reason形状而伪造这些原因，也无需无条件生成巨大dense投影。

pipeline_v1/granular_store 使用同一MFM3规范JSON与原numeric codec，只扩展标签schema：mask_encoding=field-set+sparse-leaf-v1。每个physical target保留 values/<target> float32、valid/<target> uint8；每个原统计field另存：

| 数组 | 类型/含义 |
| --- | --- |
| reason_fields_source/<field_key> | uint16 一维、不重复、非零的原字段source原因集合 |
| reason_fields_new/<field_key> | uint16 一维的原新增invalid原因集合 |
| reason_fields_review/<field_key> | uint16 一维review集合；不修改valid |
| reason_leaf_index/<field_key> | int32 一维，指该field原物理leaf的展平位置 |
| reason_leaf_code/<field_key> | uint16 一维，与index同长，只保留原稀疏generic例外 |

header.reason_granularity[target]={mode:field_set_and_sparse_generic_leaf_v1,members:{field_key:{field_id,leaf_shape}}}，另存 reason_codebook_sha256。字段原因集合描述该字段发生过的原因，不声明每个原因都适用于每个leaf。各例外index必须在该field的leaf_shape范围内、唯一且对应false mask。vector按xyz、tensor按xx/xy/yy/xz/yz/zz映射独立field；matrix3x3重建仍保留六分量，不能把镜像项计两次物理loss。

新writer把values与全部valid/reason数组分别放records/masks named DB，同一LMDB事务提交；identity、role、geometry_source、exposure mask、源field、shape、tensor对称和atom-pair检查继续执行。旧Reader对扩展不宣称兼容；模型线需要明确使用新reader或认可后的等价实现。旧dense-exact reason候选记录仍可读，不能与新粒度无声明混用。

原source NULL仅在显式policy与all-false mask下表示为masked NaN，header记录source_null_fields_with_masked_nan_placeholder；这不是源数值或补造记录。原子稀疏scatter必须显式给索引及缺原子处理决定。source_role和实际ROUTINE effective_role保留；所有诊断base及其直接view在训练导出前反连接排除，UFF始终按(molecule_id,sprime_conf_idx)定位。

需要双方确认：新粒度字段/API、codebook JSON或等价机器可读形式、稀疏原子缺项语义、source→target physical mapping、六分量tensor头/单位/原点/参考系、归一化与loss单位。这些是待对齐事项，不是已经收到的模型线冲突。候选测试、真实source profile和未来10k读回都不能代替共同签字、科学冻结、模型loader确认或D3实物验收。
