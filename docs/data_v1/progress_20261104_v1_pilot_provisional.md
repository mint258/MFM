# 2026-11-04 数据线每日汇总 — v1-pilot-provisional

D‑1 v3.0已冻结，D‑2、D‑4、D‑5保持已交付；D‑3尚未交付。用户要求P′暂时挂起，先完成D‑3，本日不启动P′修复或新QM。

D‑3当前实际作业4525670在compute-0-8 RUNNING、16CPU。固定50,000 TRAIN＋5,000 ROUTINE VAL；141/171源组已真实登记复用，现已关闭144/171组，剩余27组正在处理。已观察16个新源组SQLite文件、合计已分配1,130,262,528B；这是中间结果，不是训练载荷。存储状态READY；实际自动交付观察器2100147的UID/start_ticks身份已核对存活。

大文件输出沿Lustre；750GB为预测非硬上限，100GB真实账户余量保持。脚本无任务时间及内存参数，程序无总墙钟、RSS、MemAvailable停止门。原始Parquet、D4几何和141个闭合成果全部保留。

本日格式/资源修复一行：补齐闭合索引及所属计划冻结引用；4525668在回连SSH临时拒绝后仅同job重排，随后暴露漏写资源字段；4525669在源组复用前被旧single_job目录分类拦截。已按事先授权修正资源字段、目录分类及早期Slurm UID未知观察；四个提取/投影/坐标/读取源码与旧parallel_store登记字节完全相同，不放松其完整字节一致性检查，无新增QM/UFF。旧失败和原回执保留；没有独立数据复核作业。

导出末尾只做一次计数、随机1,000条原Parquet逐字段比较与总清单SHA；一次rsync --checksum复制、一次180秒随机读取测试。模型加载器及逐预测头过拟合为交付后的验收，当前不代填模型ACK。

[D‑2注册表](../../configs/data_v1/v1-pilot-provisional/D2_registry.json)、[D‑4归一化](../../configs/data_v1/v1-pilot-provisional/D4_normalization.json)、[D‑5诊断载荷](../../configs/data_v1/v1-pilot-provisional/D5_diagnostic_payload.json)保持原交付。r73完整有序F64与单次F32、r674 LOSS_DISABLED保持。本轮不宣称最终Common、D‑6/D‑7或模型实际加载ACK完成。
一次性能处理：OS进程观察显示磁盘等待，36.7GB冻结几何库原仅2.4GB缓存；在现有作业4525670内以低优先级只读预热，step4525670.0实际C0/206秒，之后OS观察缓存驻留36.7GB。没有新增sbatch、数据比较、SHA或质量测试；缓存可由系统回收，源文件与活跃代码未改。
