# H6：PMA 注意力的化学落点

当前阶段：化学类别准备已完成；注意力、熵、富集、query贡献和热图尚待GPU阶段，尚无H6预注册判定。

沿用H1和工作A的同一批5000个预训练VAL分子，每个分子取第一个允许的PM7构象。在compute-0-20以1 CPU读取D6元素、坐标和原始中性PM7净原子电荷；MFM4/D20没有直接总电荷列，使用完整原子电荷和的最近整数作为分子总电荷传入RDKit rdDetermineBonds.DetermineBonds。未改变任何标签、mask或归一化。

重建时唯一一次逐原子核对元素序列与D6相同；重建失败或对齐失败的分子会记录原因并排除。化学类别包括元素×杂化、芳香、环，以及RDKit BaseFeatures.fdef的Donor、Acceptor、PosIonizable、NegIonizable、Aromatic、Hydrophobe。未定位到现成的28类SMARTS交付，因此不等待或新增搜索任务。

生成步骤已报告 H6_CHEMISTRY_COMPLETE 5000 0：5000个分子全部成功，剔除0个。真实Slurm 4535408为COMPLETED 0:0，耗时3分01秒，1 CPU；没有GPU计算。缓存大小为 9922491 字节（文件stat逻辑长度），位置为服务器 /share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/H6_chemistry.json，留在本线NFS控制目录，不进入Git。缓存只保留逐分子类别的原子索引、整数总电荷及失败信息；进度按原子发布保存，续接只处理尚未完成的分子。

GPU阶段将只读取这份完整缓存，不重复重建分子或核对元素序列。随后加载B3预训练PMA，提取8 query×8 head×atom的注意力；主分析平均8个头，逐头只附表。类别富集为类别原子平均注意力除以均匀基线1/N，按分子bootstrap得到95%CI；熵以H/logN归一化。依照冻结预注册判定，并按要求补充frontier/IP-EA的query块权重贡献和热图。

局限：RDKit基于坐标和总电荷重建的化学类别是本任务指定的解释性标签；重建完成本身不证明PMA具有选择性或化学可解释性。那些结论必须等待实际注意力结果及预注册检验。
