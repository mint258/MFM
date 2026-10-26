# 1641 AV中心化局部诊断：只读结论

本次仅读取4521641的既有JSON/CSV结构和已计算标量，核对48个AV case的原始size/SHA，并以PowerShell聚合这些标量；没有执行新模型、算子、Python、SDK/NPZ解码或作业，没有修改冻结源。Root另做独立元数据闭合，本文件不替代其actual sacct/C0证书。

## 证据范围

`O/attention_AV_centering_GPU_v1_4521641/COMPLETE.json`记录failure=null、source前后相同；全48×4原encoder返回192次，AV捕获/原AV位重放/C32/Rraw/Rnorm/Cexact各1152次。全192实际bank H0对1492位等门先通过，科学AV控制开始前计数仍为0。tiny正负控制单列。实际supervisor为COMPLETED0，elapsed75.054s，remaining/cleanup均空，last_output9,119,213B，whole2GiB、child outer−96MiB保持。

这些是原coupled DenseGeoSelfAttention/SharedPairAttention、固定权重及小型合成物理视图的局部诊断。没有执行centered model，没有重跑FP64 encoder，没有证明原48物理门槛通过，也没有迁移NativeRuntimeDense、bf16或训练dropout。

## 结果

1152个AV覆盖64,880,640个有效query/head/channel分量。统计全部保留，未筛选层、case、head policy、变换或seed。这里的RMS为 `sqrt(sum(n*saved_RMS²)/sum(n))`，只聚合已保存标量；不同head policy重复使用相关encoder条件，不能把1152项当作独立随机试验。

|参考/比较|原AV|中心化C32|配对结果|
|---|---:|---:|---|
|Rnorm pooled RMS|5.27259e−8|4.67666e−8|960/1152改善，192变差|
|Rnorm全人口最大绝对误差|9.80421e−7|9.28966e−7|各AV的max：884改善，268变差|
|Rraw pooled RMS|4.63399e−8|4.97514e−8|424/1152改善，其余未列为改善|
|Rraw全人口最大绝对误差|8.23358e−7|9.29418e−7|各AV的max：784改善，368变差|

Rnorm是同一实际masked logits32提升至FP64后重新softmax，再乘实际V32提升值；不是全FP64网络/QK真值。Rraw是实际已存p32/V32提升后的乘积。因此，Rnorm改善与Rraw变差可以同时成立；结果不能概括为“修复固定p的AV GEMM精度”。

所有1152个原AV重放的记录均位等。有效query的最大 `|sum(p32_64)−1|` 为2.19588975e−7；独立Cexact64−Rraw共同项max为5.55837576e−7；恒等式残差max1.72084569e−15，全部在原声明FP64浮点审计界内。新FP32减法 `V−v0` 相对FP64减法的最大误差为1.19209290e−7。不同位置的这些max不能相除后冒充贡献比例。

### 分层结果

|层|AV数|各AV max改善/变差|各AV RMS改善/变差|Rnorm pooled RMS：原→C32|
|---|---:|---:|---:|---|
|0|192|12 /180|0 /192|5.14497e−8 →6.17543e−8|
|1|192|164 /28|192 /0|5.28550e−8 →4.80482e−8|
|2|192|172 /20|192 /0|5.13861e−8 →4.39546e−8|
|3|192|156 /36|192 /0|5.44970e−8 →4.24930e−8|
|4|192|192 /0|192 /0|5.34581e−8 →4.06706e−8|
|5|192|188 /4|192 /0|5.26418e−8 →4.01085e−8|

Layer0是明确负例：整体pooling改善不能掩盖它全部192项RMS变差。后续候选若测试统一公式，必须仍覆盖全部六层，不能依据此表事后跳过某层。

### C1、batch形状和seed

|组|AV数|max改善/变差|Rnorm pooled RMS：原→C32|
|---|---:|---:|---|
|C1-0|384|272 /112|5.07019e−8 →4.58045e−8|
|C1-a|384|316 /68|5.37737e−8 →4.71655e−8|
|C1-b|384|296 /88|5.36448e−8 →4.73150e−8|
|two views，B=6/P=32|576|436 /140|5.26017e−8 →4.69176e−8|
|three views，B=9/P=32|576|448 /128|5.28085e−8 →4.66657e−8|
|seed20261026|576|468 /108|5.27872e−8 →4.68263e−8|
|seed20261027|576|416 /160|5.26644e−8 →4.67068e−8|

各C1组RMS改善不是所有max改善：C1-a的全组max略升9.28190e−7→9.28966e−7；three视图max升9.02421e−7→9.28966e−7；seed20261027 max升8.02414e−7→9.28966e−7。不得只保留改善的组或seed。

实际原子数3/9/32都在每个物理batch内。现有每AV统计汇总所有有效图，不能从这些标量恢复三种原子数各自完整人口的RMS。可恢复的只有argmax所在图：原Rnorm与C32的max各自均有1148次位于32原子图、4次位于9原子图。这里没有为补齐size表而重读operands或重跑模型。

## 同分量例子与解释限制

在原Rnorm误差最大分量处，1148个AV改善、4个相同、0个变差；但各AV重新取全人口max后仍有268个变差。必须同时报告两种统计。

case00/role0/layer0：原max位置 `[4,1,24,47]` 的有符号误差为−5.23151952e−7，C32同位置为−4.63147936e−8。该位置sum(p)−1=−1.70606654e−7、anchor V=0.855263293，独立Cexact−Rraw=+1.45913609e−7，signed identity closure约6.28e−16。与此同时C32产生新的最大误差7.38557294e−7（位置 `[5,2,9,2]`），比原全人口max更差。这直接说明不能仅凭固定原argmax改善采用。

该实验观测的是完整表达式 `v0+p@(V−v0)` 的局部效果。`V−v0` 是新分配，可能改变原QKV切片V的stride/packing及所选kernel；现报告没有centered_v/C32的实测layout header。因此不能唯一归因共同模态消减，不能宣称排除了layout/kernel、FP32减法和回加等因素。Cexact的独立恒等核验支持共同分量机制存在，不能把它升级为所有C32收益的唯一原因。

## 下一步判断

可以支持**一个有界、预注册的统一六层FP32候选**，在相同原48组合、权重/seed/视图与全部原字段、原1e−5门槛上做end-to-end否证：总体Rnorm RMS约降11.3%，后五层的每项Rnorm RMS均改善，机制有可重复的实际局部依据。候选必须保持first-valid-key anchor与数学、512维H0 API/参数、dropout/全masked guard，不能根据本表选择层、case、seed或重缩放权重。

这是“值得一次全矩阵检验”，不是预计必过或建议采用。layer0全面RMS退化、部分组max退化、Rraw变差及layout混杂都可能令全网络收益消失或反转。应保留原路径与所有失败；若原完整门槛未过，就不采用、不恢复长程科学训练来赌收敛，也不依据预训练loss挑架构。当前不需要重跑192个FP64 encoder来包装已有旁证。

## 小型可追溯产物

- 原结果：`O/attention_AV_centering_GPU_v1_4521641/ANALYSIS_RESULT.json`，SHA256 `16259ab0da0e6b75026cc4e05a021a1d2a62db30a3e60696fd1115288aa060cd`。
- 全组既有标量汇总：`N/AV_1641_readonly_scalar_summary_v1.json`，SHA256 `99930bbf5c121c1ce6b41e2d4d2153c53c3bad51c018c3f20cf361bb18b8abb5`。其48个case raw refs均已本次只读重hash，未读取SDK/NPZ。

O=`runs/model_v3_20261025`，N=`runs/model_v3_20261026`。本报告没有新增科学接受或Root终态证书。
