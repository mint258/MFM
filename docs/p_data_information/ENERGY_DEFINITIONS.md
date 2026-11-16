# 原生能量字段的定义区别

按[MOPAC官方生成热定义](https://openmopac.net/Manual/SCF_calc_hof.html)，原生TOTAL ENERGY包含电子与核排斥部分；生成热还包括原子参考/原子化项与氢键、色散项E_bits。后两项可随几何改变。因此同组成时也不能只作单位换算就把生成热构象差与原生TOTAL ENERGY构象差视为重复。两者都不是本报告可以任意改称的“分子结合能”。

在固定P字段中，r83（原生total_energy_eV）、r54（electronic_energy_eV）与r41（core_core_repulsion_eV）有程序定义层的代数关系；已有F64解析值的求和残差在energy_semantics.json。分项分别打印/解析后的不为零残差不构成新的独立物理信息，也不能将样本最大残差当作SCF误差界。r60生成热的附加项不能由减元素参考自动消除。

这补充了阶段0的物理语义与阶段4的代数关系列表；未修改注册表、启用字段、生产目标、mask或D4/A1，也未新增计算/拟合。全域计算与物理方法准确性仍未建立。
