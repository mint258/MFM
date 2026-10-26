# 全WP5实际footer目录（仅SOURCE）

未执行Python/AST/tests/源data/SSH/Git/Slurm。只新增本目录5件，已冻结的
projection6、augmentation6与批次/norm方案2docs全部不动。不fit、无新mask、
不授予full numeric cache/Common/D4。Root静态审查、生成新request并实际提交。

准确输入来自现有source_status prepared/census和其catalog引用：2024 label＋
184 base＝2208唯一Parquet，producer bytes575,920,810,664。label物理taskrows
157,254,650，继承canonical157,245,956/差额8694；base producer物理rows
11,232,475，继承canonical11,231,854/差额621。两差额单列，不能混合或悄丢。
本任务不读row keys、不重做canonical join；它只能实际验证footer物理行数，
canonical/非canonical差额仍是closed metadata lineage，不冒称本轮逐行分类。

## 先静态估size，actual目录待CPU

按producer rows和冻结writer默认RG32768作场景：6648RG、200652column chunks。
每file64KiB＋RG512B＋chunk1024B＋80MiB预留＝437,460,992 B。此为静态场景，
不是actual RG数/当前wholebody hash/压缩输出forecast。实际可能不同；512MiB
是不可超的whole cap，不是已经保证能装下完整目录。超限保留已关闭member及
pending，退出非零，不假称2208已全部观察。原full lossless约1.3TB与此无关。

whole512MiB分432MiB实际compressed成员、64MiB独立observer、16MiB reports/
index/admin余量。16固定worker shards，每worker一个串接独立gzip members文件
及一个小index/report；总输出inode软件cap128。每source先有界构建metadata，
gzip CRC/rawSHA读回，再跨进程锁内预留实际compressed bytes并追加。写失败
不回收其未确认reservation，防止别的worker重复花预算。每source的member是
独立完整gzip，index保存byte[lo,hi)/compressedSHA/rawSHA，可单独读取和复核。
未关或错误member不计完成。没有2208个大型临时副本或第二个queue。

## 严格footer读法

不能对原路径直接调用ParquetFile来假定没有尾部prefetch。footer_only显式读取
原header4B、trailer8B、trailer声明的精确footer区，检查PAR1/magic、长度界限；
原source fd前后fstat的UID/type/bytes/device/inode/mtime/ctime必须稳定。它将
PAR1＋原footer＋trailer组为**没有data pages的内存metadata文件**，仅交给
pyarrow.parquet.read_metadata(BufferReader)。原column offsets完整保留，仍指向
原source，不是这个短的内存文件。不存在原路径的Arrow page读取机会。

只访问num_rows、actual RG数、每RG连续physical[lo,hi)、column chunk的
compressed/uncompressed大小、num_values、file/data/dictionary offsets、外部
file_path、codec/encodings、physical/logical schema/创建writer版本。原footer
可能包含统计字段，但代码不访问statistics/min/max或to_dict，不输出样本值。
不调用iter_batches/read_table，不解CELL/数组/JSON，不读LMDB。Footer之外的
数据页没有给Arrow；坏长度/magic/metadata失败明确pending，不尝试body修复。

当前footer SHA是本次真实footer观察；原producer整个文件SHA只作lineage，
不说当前wholebody已hash。num_values是footer级count，不证明逐record实际数组
长度；created_by是Parquet writer，不是MOPAC/xTB或原生成precision；schema
DOUBLE不能证明程序native double，frame/origin也未验证。所有这类界限写receipt。

软件界限：单serialized footer128MiB、单source metadata raw buffer64MiB、
单metadata record256KiB（一般RG/chunk4KiB）、worker3GiB RSS软STOP。16CPU/
no_mem/≤1h，中央实际RSS/MemAvailable自然drain、200GB quota约束不变；4GiB
MemAvailable只停止新source，绝不强杀/自动重试。超软件cap不是标签质量失败。

## Root入口与输出

metadata helper只读prepared/census小JSON及其已绑定3.48MiB catalog JSON，
后者明确是metadata，不是Parquet。它不stat/hash科学Parquet，实际去重2208件、
守恒rows/bytes、生成source_inventory/static_size/config/resource_binding/
scope_review/stage_spec，复用centralv2，不提交。输出目录必须是旧observer
允许的artifacts/labels/source_status_v1下新child。

    PY -B -m workflows.data_v1_final.labels.footer_inventory_v1.materialize \
      --prepared-census RUN/artifacts/labels/source_status_v1/auto_memory_v1/prepared/manifest.json \
      --census-reduction RUN/artifacts/labels/source_status_v1/auto_memory_v1/reduction/audit.json \
      --resource-authority CURRENT_NO_MEM_AUTHORITY --metadata-directory NEW_METADATA \
      --output NEW_ARTIFACTS_CHILD --approve --reason ROOT_REASON

scope_key=labels_wp5_footer_inventory_v1，analysis/pilot=false/
BOUNDED_METADATA_PREPARATION/16CPU/no_mem/3600s/512MiB。原大输入refs仍只是
DATA locators；本任务CPU只读取上述header/footer区域。fresh admission＋exact
source pins后，3新纯边界必须实际全PASS/no skip才打开真实source。只验证
footer-only envelope、synthetic Arrow metadata范围/chunk、坏magic/长度/row数/
output-bound拒绝，不重跑旧9/19/24套，也不代替真实2208元数据实测。

manifest闭合必须16真实PID、2208文件及label/base物理行数全部守恒。完整状态
ALL2208_SOURCE_FOOTERS_OBSERVED_VALUES_PENDING只表示footer完成；任何source
错误/软件STOP保留具体file IDs、已关members并FOOTER_INVENTORY_PARTIAL_PENDING。
label8694与base621继承差额分别列；full1.5、native precision、frame、newmask、
final Common/D4均不因此完成。partial实际读字节计数只含成功关闭source，
失败attempt的已读字节不在该合计，不能拿它当全作业精确storage吞吐。

## 后续bounded typed parts/cursor的最小改动（本次不实现）

1. 直接复用冻结projection.py的cache_row/verify_cache_row及原payload.evaluate/
   registry264→146和mask规则；不改旧6件。原run.schema是可导入函数；flush
   目前是run_group内局部函数，不能假称有现成公共part writer。新独立sink只
   提取该Arrow writer/flush模式，另加whole-ticket/part轮转、source/RG/row cursor。
2. 本目录实际file/RG目录作为唯一physical range输入，不把formal ordinal当label
   seek；一个source句柄顺序读指定RG，已关RG不回扫，RG内续跑仅有界重解其
   prefix并报告额外bytes。Footer inventory不授予这些value读取的新job权限。
3. 每part复制原科学signature/ordered keys和source位置，关闭/fsync/reopen后才
   publish cursor；崩溃partial不计coverage，range overlap拒绝，原数据不改。
4. full不克隆pilot全部资格假设：保留不可用base/旧invalid/NA/未知，不能drop
   record或造Z。原9列canonical索引仍无payloadSHA/heavy_atoms，需独立小列侧表
   才能声称对formal SHA逐record核验。新full calibration不得拿512代替。
5. 等Root根据actual目录/边界RG大小、实际剩余quota冻结首批cap和独立request，
   再实现range driver；Common未冻结不finalfit。Norm仍需显式cache adapter、
   冻结fit侧表与确定性归并/replay，不能因本metadata C0授予全量或D4完成。
