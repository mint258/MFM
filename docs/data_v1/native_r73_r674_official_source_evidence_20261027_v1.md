# 原生 r73/r674 官方源码证据，2026-10-27

本记录仅解释两份官方固定版本源码，作为 D1 共同审阅依据。未执行二进制或读取科学 DATA，未冻结单位、frame、mask 或模型消费契约。现有 D1 权威仍 draft3，draft4 为待双方审阅提案。

实际源码保存在外部 control/official_native_domain_sources_mopac23_xtb671_v2/；GitHub 插件取得的完整字节分别与下列官方 Git blob SHA1 闭合，同时保存了本地 SHA256。第一次直接下载连接重置，v1 未形成接受记录。

| 项 | 官方固定版本 | 完整源码身份 |
| --- | --- | --- |
| MOPAC denrot | v23.0.3，commit 490725eac356e0e75037f37bdd2db343d6bc9e09 | src/output/denrot.F90，8266B，SHA256 d956dfae57aa2b8ee91878ae23ba96c6b4001320d925818dfc4cbcf70c6e539a；Git blob 53b9490213ccf49b38e737237cecae4343e9d12c |
| xTB molmom | v6.7.1，commit 26b28010e805f7d1aeeef39813feb473e69cc4be | src/aespot.f90，38736B，SHA256 155da3359cc01a0d8afc3b86f28bfaf2ecffbfc07ae8d2117423249b7455a5c8；Git blob c10d90b672c482026a69e78c9879349cccac0df8 |

MOPAC 的 r73 来自 SIGMA-PI 矩阵。`denrot` 将密度矩阵依原子对坐标差旋转，平方旋转结果并按 sigma/pi/delta 类别累加；degenerate pi 通道经 isp 映射归组，输出对角项随后置为对应行的键级和。这里的 channel 身份与原始打印条目顺序必须保留，不应从 AO_ATOMINDEX 推成全局 px/py/xyz，也不应删掉同原子条目或擅自求和去重。以上属于对固定源码的解释；实际条目与原 parser 的逐值闭合由独立 CPU 证据汇总验证。[官方 denrot](https://github.com/openmopac/mopac/blob/490725eac356e0e75037f37bdd2db343d6bc9e09/src/output/denrot.F90)

xTB 的 r674 对应 `molmom` 最后打印的完整无迹四极矩，原顺序为 xx, xy, yy, xz, yz, zz。令 A 为各原子 q·r⊗r 的和，B 为原子 dipole 与坐标交叉项的和，C 为 atomic traceless quadrupole 的和；源码使用 `1.5 A - 0.5 trace(A) I + 1.5 B - 0.5 trace(B) I + C`。它在传入 Cartesian 坐标中输出，未在该函数内对角化为主轴；不能混用少一个 1/2 的另一种 quadrupole 定义。原子内 CAMM 的符号与坐标内部单位仍需沿调用链和实际二进制/原输出证据共同核实，不能只因字段名含 au 就自签单位或坐标轴。[官方 molmom](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/aespot.f90#L669)

官方用户文档也说明 dipole Cartesian 分量与总量单位有别，且 GFN2 把 quadrupole 的六个 Cartesian 分量按上述顺序打印；该文档只能作交叉参考，不能替代固定版本及实际来源绑定。[xTB properties](https://xtb-docs.readthedocs.io/en/latest/properties.html)

实际 native32 body 的 384 条记录均观察完成、0 held。r73 的 128 个 UNKNOWN 对应其他四个 PM7 条件没有请求 PI 的原记录，其原 registry 字段本来 N/A；后续汇总将保留原 UNKNOWN 原因并单列原 N/A，不把它们冒成 r73 新增质量失败。r674 只有 xtb_singlepoint 的 32 条适用，其余 N/A。原坐标读回证据覆盖五种 PM7 条件及 xTB gradient，共192条；另192条原输出没有独立坐标块，input hash 匹配不能补作 property-axis 证明。这些分类仍要由实际 CPU 汇总逐项闭合，未以本说明代替执行结果。