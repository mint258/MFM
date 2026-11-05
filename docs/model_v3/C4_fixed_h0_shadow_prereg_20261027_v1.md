# C4 固定 H0 归因：透明捕获与终端影子预注册

2026-10-27。此诊断尚未执行；不提出新的可采用模型，不修改1435的38个失败，不用于选择C1/C3/头形式。既有候选的公开科学提交为5cdb2772dfa51e1cc72098c659fb741440219772（实际本地4068623），原48夹具、两种子、3个刚体变换、非零条件及1e-5/rtol0标准保持。

## 问题与边界

区分三种终端失败的来源：继承的H0漂移、输入几何/交互、头部算术误差。现有1435的52数组只有终端输出，不能重算实际H0。因此先做独立、明确标识fresh_capture_not_1435_H0的新捕获，再在新捕获的同一H0上归因；不把CPU重建encoder或新捕获当作1435的原H0。

捕获覆盖全部48组合、每组原4次forward，共192次。hook只保留实际bank输入/输出引用，原forward返回后复制H0/pos/batch/kwargs、完整typed bank tensor state与9个PD同次输出。原返回对象不改变，finally移除hook；与同次原52终端数组逐位核对，记录实际encoder-return次数和模型/bank参数SHA前后。不要求新捕获与1435跨作业逐位相同，也不因物理测试失败而少存某些组合。

## 固定分析

对全部48组合、三种变换和p_extensive、p_dipole、p_dipole_magnitude分别计算F00、Ft0、F0t、Ftt。CPU原FP32 bank严格加载实际状态；独立FP64 functional实现保持数学定义，不对诚实拒绝double的生产模块直接.double()。不重建encoder。

令向量映射L为统一的row-vector旋转，标量为identity：D=Ftt−L(F00)，H=L(Ft0−F00)，G=F0t−L(F00)，I=Ftt−F0t−L(Ft0−F00)。逐component保留符号并检验D=H+G+I，闭合误差≤1e-10；广延标量另检验位置无关。CPU FP32、FP64和GPU原输出的差异分列，不强求不同backend位等同。

分解算术及L统一用FP64；GPU_FP32_D指输入输出来自GPU FP32，不能误称所有差值和旋转映射都按FP32运算。原C4测试本身的FP32预期值/误差/通过数仍为权威验收；此处的算术对照不是C4通过声明或所有输入下的误差下界。

## 预算与判定

捕获输入128MiB：按原bank拓扑，48份完整tensor state约53.25MiB，H0约16.5MiB，附加输入、原控制及headers保守总量约105MiB；仍以实际bytes门禁为准，不删除字段或伪重建权重。来源、状态、shape/dtype、哈希与原同次输出不一致、缺任一组合或预算超限均拒绝。

GPU沿用实测c35/node21守卫、fd9公共锁、16CPU/32GiB、28GiB RSS、1100s/20min及whole/private各2GiB。CPU用可用CPU节点、16CPU/16GiB、4workers×4math threads、12GiB RSS、120秒计算和清理预留、whole/private各2GiB；120秒仅估计，超时保留真实失败。实际任务内前置小tensor/typed输入自检，不另开QA父或复跑2639。

源快照：[fixed_h0_shadow_v1](../../tools/model_v3/analysis_sources/fixed_h0_shadow_v1/)。原N目录source_pins_v1.json的SHA256为3d31af93aa63333f0efe8857724ff8438384026490b581d769db88f305427166。所有源先经Root AST/原始SHA/bash检查，再发布本预注册，之后才可执行GPU捕获；CPU须等实际capture父C0、监督/参数/输入闭合，按真实refs填写模板。全部NPZ、权重和运行产物位于仓库外。

## 独立 S 执行更新

S分段4521438已实际C0/2452秒，安全CP为1000更新/409491样本。CPU日志审计4521460实际C0/7秒，28项前置检查通过，完整1003条原生日志（steps0..1002）、config/summary/源前后、exit0/EOF均匹配。该局部成功不是四条2万步B验收。1459已按相同科学配置从该CP继续1000→2000，未启动正式预训练。