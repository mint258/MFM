# G1 seed0 3M诊断执行口径

状态：原训练4539204、主统计4539205和配对4539206均COMPLETED0:0，自有root进程已reap并ABSENT、resident children=[]。G1原判TIE，CI未跨0，保留D3。下列五入口已绑定/登记并提交：几何前向4539284、缓存层GPU4539285、CPU传输4539286(afterok4539284)、几何统计4539287(afterok4539286)、层CPU4539288(afterok4539285)。原主统计4539205已成功且原出口核实；不依赖已从scontrol移除的旧job再次调度。两GPU均实际RUNNING，前向原cursor608；首个OWNED_TREE_REAPED只指预检子树，不表示整个诊断结束。诊断仅描述、不改变主判定。

| 步骤 | 原执行器 | 目标 | 真实TimeLimit/提前收尾 |
| --- | --- | --- | --- |
| 一次固定5000VAL F64前向 | tools.d_recipe.diagnostic_forward | GPU6/2CPU/RTX3090 | 1h/300s |
| 闭合几何scope传输 | tools.d_recipe.transfer_diagnostic | GPU6→CPU13/1CPU | 30m/300s |
| F64几何统计 | tools.d_recipe.diagnostic_statistics | CPU13/1CPU | 2h30m/900s |
| 缓存层3–5读出 | tools.d_recipe.layer_readouts / gpu | 原生产GPU7/5CPU | 45m/300s |
| 层统计、复用原层6 | 同上 / cpu | CPU13/1CPU | 3h15m/900s |

几何与层诊断各入口时限合计14400s；按实际Slurm父分配累计成本和两次失败规则登记，队列不算计算。条件成功依赖逐个提交；统计不先占CPU空等。若提前科学安全边界退出，保留原闭合结果，不能把75/TIMEOUT当完成，不因观察器结束重启。五入口仅克隆既有source-independent resident生命周期，原科学执行器未改；TERM/join/reap全部自有子树，不用KILL。

五配置前缀configs/d_recipe/diagnostics/D-G1_seed0_3M_，唯一端点/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/full/stage2/D-G1_seed0_3M/training/samples_3000000.pt。固定5000VAL/seed20261112、层3–6、F64、1000次分子bootstrap/seed20261025和原P公式。主层6现有分数复用，3–5只消费原GPU7开发层缓存，不做额外编码器前向或扫层。R1已UR几何不重试。

几何独立scope/tmp/d_recipe_20261120_D_G1_seed0_geometry；原固定队列元信息预测F64值5,131,075,584B、最大rsync临时4,349,591,552B。GPU6私有8GiB+同行8GiB+128MiB日志；CPU13私有12GiB+同行16GiB+余量8GiB+128MiB日志，转运只复制闭合几何scope，不复制数据库或开发层缓存。GPU7层缓存仍在原scope/tmp/d_recipe_20261120_D_G1_seed0，8GiB自己+8GiB同行+128MiB日志保持。实际findmnt均为各节点xfs root，/tmp同盘；三节点字节/inode/GPU UUID/零上下文已核。完整声明见[G1_node_storage_20261123.json](../../configs/d_recipe/diagnostics/G1_node_storage_20261123.json)。

共享小统计写原full/stage2/D-G1_seed0_3M/representation_statistics及layer_readouts；NFS42074762973B不增。源发布与实际入口均须原fresh UID配额/同行future守卫准入，另留系统max10GiB/10%。绑定和容量只是实际观察，不代替启动时复核。旧数组、已闭合统计和其它线任务全部保留。
