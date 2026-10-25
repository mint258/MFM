# MFM3 候选训练格式实现

这是D1 draft.3的候选实现，未与模型线共同签为v3.0。代码和合成测试不代表D3试点、D5真实清单或全量导出已完成；本阶段不读取真实科学记录。

## Codec与数据类型

codec.encode_record/decode_record使用MFM3 magic、uint32小端header长度、规范UTF-8 JSON header及连续数组bytes。header含元数据、精确name/dtype/shape/offset/nbytes和payload SHA256；禁止重复JSON键、非规范编码、object dtype、重叠/间隙/越界、未声明尾部及超出显式上限的shape/header/payload。

float64仅在编码时转float32；已有float32保持相同bytes。有限数转float32溢出时拒绝；无效标签可保留NaN，但必须有false mask及非零原因码。int8来源可无损升为int16；线格式仅允许<f4、<i2、<i4、<i8、<u2、|u1。解码数组只读。默认上限为1MiB header、256MiB payload、512数组、4维、单数组16M元素；这些是候选工程边界，真实大记录须先试点测量，不自动扩大。

## 显式物理目标映射

mapping.preflight_registry要求独立physical_targets清单覆盖所有enabled源分量恰好一次；不能把146统计行自动视为146头。每个target明确ID、S/D/P组、condition、family、unit、geometry_source、level、kind、members、component_order及mask_reduction。每个member精确绑定field_key、source_path、registry_id、component。多个分量必须来自同一个task/registry/source物理目标，防止把不同方法的xyz混成一个矢量。

支持scalar、vector、symmetric_tensor。矢量三分量顺序为x,y,z；原子矢量可由一个已提取[N,3]源值提供。二阶tensor保留xx,xy,yy,xz,yz,zz六个存储分量，可输出symmetric6或对称matrix3x3。代码不自行判断源tensor原点/无迹约束，不删第六个分量。矢量/tensor保留逐component mask，物理头要求all_components有效；不把部分缺失填有效0。

require_final=True默认拒绝DRAFT登记/映射、未定稿family、未验证unit/frame及不可用Pprime。候选模式仍严格核对源分量，只返回CANDIDATE_NOT_TRAINING_ELIGIBLE。Pprime必须是P组、UFF几何的condition，不是第四组。配方可按几何条件分别编译相同物理target ID，不能复制PM7实测值冒充UFF标签。

~~~bash
PYTHONPATH=<repository>/workflows/data_v1_final/export \
python -m wire_v1.mapping --registry <registry.json> --mapping <explicit_targets.json>
~~~

当前真实登记表仍为draft，所以默认最终预检应拒绝。--candidate-only仅供候选开发，不能改变科学冻结状态。source→export适配器需先按精确field_key提取和核验numeric source components；assemble_target负责明确分量组合，不代替WP5复杂cell的身份/数值解析。

## 分家族LMDB与按分子索引

FamilyWriter只新建绝对路径的外部store，必须显式给有界map_bytes，不自动扩容。schema.kind为geometry或labels；标签schema由family_schema按family/geometry筛选已编译targets。atomic_numbers和positions_A、每字段自己的pair indices、mask/reason与exposure mask在写前实际验证。

每个store有records和dupsort molecule_index named DB；labels额外有独立masks named DB。值与mask在同一个LMDB写事务原子提交；按分子索引保存molecule_id→export_record_id，不把百万分子ID列表攒成单个JSON。重复ID导致整个batch回滚，计数不增加。数据与掩码分开保存，reader组合后再校验shape、原因码、几何来源和身份。

未完成store为WRITING，reader拒绝；finish记录COMPLETE、计数、schema SHA和data.mdb SHA。lock.mdb作为运行期锁不构成数据内容身份，但其空间属于外部产物。例外退出只关闭句柄，保留partial，不删除文件。Reader的数组独立持有LMDB读回的bytes，关闭reader后仍可读。每个spawn worker独立打开只读句柄，不能传父进程LMDB句柄。

write_export_manifest核实各family data.mdb实际SHA并记录source/registry/roles/common/orders引用，状态固定为候选，不制造真实D3/全量release完成状态。

## 子集代码及冻结闸门

subsets.plan_subsets是已冻结输入的候选生成函数：固定PCG64 seed、排序输入ID后置换，生成120k⊂240k⊂600k⊂全部、50k试点TRAIN、5k VAL及20k诊断分子。诊断按各几何随机顺序最后一项生成PM7/UFF两个排除项，并明确用于所有训练条件的排除。测试小规模只能显式fixture=True，生产规模参数必须等于指南默认值。

调用前必须提供：ROUTINE roles FROZEN、最终common population FROZEN且geometries_frozen、三种conformer orders FROZEN；common→roles及orders→common/roles的SHA必须一致，且每个共同人群分子具有PM7/UFF三种相同成员的无重复顺序。缺任何项、人口不足或诊断分子不足均拒绝。

~~~bash
PYTHONPATH=<repository>/workflows/data_v1_final/export \
python -m wire_v1.subsets --roles <roles.json> --common <common.json> \
  --orders <orders.json> --metadata-only-preflight
~~~

该CLI只做轻量manifest预检，不读大表或实际生成D5。plan_subsets接收已经验证的common_rows及conformer_orders，返回外部清单所需的候选结构；大数据输入适配、统计分布报告及Slurm正式生成属于后续工作，不在本阶段假称完成。当前common/orders尚未冻结，实际D5必须等待。

## 验证

compute20上合成测试覆盖：payload损坏和校验、重复header键、offset重叠/间隙、dtype/shape界限、一次float32转换、原子对越界/重复、mask/reason、vector/tensor分组、对称tensor重建、LMDB事务回滚/分子索引/独立mask、partial store拒绝及未冻结subset拒绝。另有16个实际spawn worker读取32条外部fixture记录，核对一致性并按PID/start确认全部关闭。

~~~bash
PYTHONPATH=<repository>/workflows/data_v1_final/export:<existing_dependencies> \
python -B -m wire_v1.tests --output <new_external_fixture_directory> --workers 16
~~~

fixture、LMDB、结果JSON都在仓库外，新目录已存在则拒绝；测试不删除已有文件。测试结果记录实际源码SHA和环境，不能作为真实50k数据读回、训练吞吐或参考系科学验收的替代。
