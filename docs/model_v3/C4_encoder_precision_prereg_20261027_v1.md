# C4 主干精度参考：预注册 v1

2026-10-27。执行前提交。它是独立分析，不是生产FP64改造、架构选择或模型采用。

## 问题与现有证据

已闭合CPU4521503的同H0分析中，FP64终端仍31/48组合、65/432观测超过1e-5；81个GPU超限argmax处H为最大项61次，头算术差最大20次。原物理10PASS/38FAIL仍权威。这支持继续检查encoder求值，不支持只改电荷质心或宣称FP32不可避免下界。

## 固定输入与重放门

沿用原48组合、两个seed、C1三形式、两种views和四种head/pooling，不筛case或权重，不修改三种刚体变换及1e-5/rtol0。输入只读实际1492捕获；它不是1435缺失H0的替代。

先做全部192次原FP32前向。instrumentation只留embedding、6层post及out_norm/final引用，原完整forward返回后复制；不改返回值、参数、backend、requires_grad或RNG，finally移除。区分packed88/132与canonical44节点。

全部48的4次实际bank H0均须与1492逐位一致，参数/缓冲/来源闭合，才允许参考阶段；任一不符保留真实失败，不以近似阈值替代、丢掉case或声称新内部值是1492。旧1397的unhooked重放本身不位等，不能当作hook透明证明；本次门禁独立实际执行。

## FP64 数学参考

192次reference encoder求值仍在同一GPU实验内完成。严格复制原FP32 encoder；参数和持久缓冲逐值无损转FP64并以cast-back SHA核对，禁止重新初始化权重、Gaussian中心、scale或width。只在分析副本上显式设legacy数学mode并核所有相关属性；原apply_numeric_mode(legacy)是no-op，不能假装已切换。原模型、配置、检查点和H0导出位置/512维不动。此legacy/直接规约是同实数公式的有限参考，并非原补偿算法逐指令仅换dtype。1492未保存的旧encoder buffer独立SHA不补造：旧named-parameter SHA、PD完整state及全H0位等门作为原捕获绑定；当前重放原encoder的buffer前后及影子cast-back SHA另行闭合。

独立dtype-preserving打包forward和Gaussian实现只去除已审阅的强制float32转换；其余六层、投影、MLP、LayerNorm/attention仍同拓扑、同原参数。使用实际FP32输入逐值promote，L用原R castFP64；不加入ideal坐标、polar/SVD、新旋转或重新高精度生成输入。记录原R正交残差。

只复用1503已公开functional64计算p_extensive、p_dipole、p_dipole_magnitude。PD bank保持FP32权重，函数内临时转FP64；device接线单列，小tensor CPU/CUDA parity在同一作业内先执行。不把此参考扩大为S几何、5Å原子矢量头或8Åpair envelope的F64验收。encoder实际global attention且cutoffNone，记录真实enable flags，不把unused radius当生效邻接。

逐层及最终H0标量漂移、原FP32与参考求值差和三种终端D分列，全48完整报告。原FP32 C4判定仍权威；F64残余仍包含实际输入离散化、原R非正交及有限F64求值等因素，不能严格单独归咎坐标舍入，不能据此宣称FP32下界或改阈值。编码器384次病例前向与小tensor控制、functional头调用分别计数。

## 预算与闭合

沿用c35/node21/公共fd9锁与原新鲜资源守卫，16CPU/32GiB、28GiB RSS、1100秒计算及20分钟SBATCH、whole/private各2GiB。实际87.7MB捕获只读复用，输入仍128MiB；不导出48份模型权重，只保存必要H0、统计和SHA。超时/预算/位等门失败如实非零结束，不扩限重写旧结果。

实际来源、所有parity/位等门、计数、source前后、supervisor及父sacct C0均须闭合；成功完成参考也不是原FP32物理通过。无需D3的合成分析不代替真实标签三卡冒烟、开发面板比较、配方/B*或用户确认。

源码快照：tools/model_v3/analysis_sources/full_encoder_fp64_v1。原N包source_pins_v1.json原始SHA256=e14c0d33b8b0bb7ef5cd019e1ad1189bf97a2c8815af7c6e27025753f21fbefd。Root实际267份原始引用、167个Python AST与11个bash语法检查通过，SA1独立静态复核核心17363B/1dbf90dfb0e4faa8af6b93147aaf3235b22ff39142b32b0dea97fc5ab21c385c未见阻断。tiny/192位等门/384求值仍待实际运行。内部层仅为本轮重放观察，不能补造1492未保存的历史内部tensor。