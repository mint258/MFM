# A候选容量预筛选（2026-10-25）

状态：静态组件界与已消费输入元数据，不是候选峰值显存实测，也不授予A验收。
SA-1只读审阅；实际运行源码由405的configuration与逐文件SHA绑定。
字节量下表采用十进制GB。任何更小批预算都须两侧一致、单列条件、重过20批与500步。

405的固定20批已出现P=3BN²=7,994,721和T=3BN=105,750。
这一窗口的双模型A00 allocated/reserved峰值为5.405/11.218GB；不外推整个500步，
也不当作单模型生产容量。head有向边数E没有实测记录，只能用原子数给范围。

| 候选 | 能由源码证明的保存语义/组件量 | 原8M预算下的下一步 |
| --- | --- | --- |
| A01 backbone checkpoint关闭 | 六层attention/FFN保留；distance仍按tile checkpoint。一个固定批的FFN两hidden、attention概率和distance输入必存子集约6.911GB | 总容量未证；4090优先实测 |
| A02 distance checkpoint关闭 | outer仍开；只在当前层backward replay保存两份512维hidden，2PD×4=32.746GB，不能乘六层 | 该项已超3090/5090保守85%容量；两卡原预算N/A。4090其余激活/workspace仍需实测 |
| A03 head checkpoint关闭 | feature1056与四份64维hidden共5248E字节；已消费批次只知E≤6,631,968，即组件范围0–34.805GB | 上界不能当作实测或必失败；不能用head-on峰值保证head-off安全 |
| A04 checkpoint全部关闭 | 六层distance hidden同时驻留，仅每层一份已≥98.239GB；当前eager两份约196.478GB | 三卡原预算均N/A，不以故意OOM验证 |

输入storage是共享引用。不得按每tile重复计算完整distance输入，或按每head chunk
重复计算同一H0/pos/edge storage。Torch2.10 nested checkpoint下，inner保存对outer隐藏，
inner输入由outer管理，replay张量unpack后释放；此规则决定A02按当前一层计量。
以上不能给整个CUDA进程严格上界：还缺QKV/norm/layout复制、optimizer状态、库workspace、
确定性sort和allocator行为。A00 reserved加新hidden不是总容量上界。

匹配小预算的候选起点为3090 A02/A03=2M、A04=250k；5090 A02=4M、A03=2M、
A04=500k；4090 A02=8M待测、A03=4M、A04=1M。这些是预筛选条件，不是通过结论。
采样器保留超预算singleton，因此必须核对原manifest最大N及将消费的原子数清单。
只计六层两hidden时，单分子N≥542/624/767分别超过3090/5090/4090的85%容量；
不能只降低声明budget就声称覆盖全部TRAIN。编译或融合也不自动豁免保存量。

单项数值通过后才做同GPU、同预算、同控制签名的独立A/B/B/A吞吐测量；
双模型paired耗时不填生产速度倍数。合法叠加重新过原20批/500步门槛。
bucket/sort机制已实现，但改变逻辑batch的结果仅探索；保留raw吞吐，不填虚假的
等价提速倍数。保持原batch/顺序/损失分母的内部微分组是另外一种尚未验收的实现。
