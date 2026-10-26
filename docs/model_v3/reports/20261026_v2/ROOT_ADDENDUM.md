# Root 更新：候选发布、真实 GPU 等变性与后续预注册

这是报告快照之后的补充记录；整份指南尚未完成。

候选执行提交 `3d9b1cc0c580dacc9398a5570b0c2fff3e257618` 的完整 Git tree `73a9e47af34aa6e46c2b421c946b1dc39209a584` 已精确发布为 `ce7cbf5776ff546cd47538b120c8f884e2e5867d`。main 读回仍为 `037546cd7f07b32dbb46bc21a69109dfd273f8da`。候选发布没有将完整回归标为通过。普通 repository checker 的实际父作业为4521127，C0。

完整新Root回归仍待完成。4521159在pytest刚启动时被CPU监督器身份检查中止；旧记录缺少发生差异的字段和两份完整身份，不能确认为NTP或唯一fork/exec原因。4521158的216项测试有213通过、3失败，失败均为原生spawn预取45秒超时；原因尚未解决，未改超时或断言。旧结果保留，不将操作失败和pytest失败合并解释。其他分片的部分通过不替代完整回归。

## 已实际完成的新验证

| 范围 | 实际父作业 | 结果 | 限制 |
|---|---|---|---|
| GPU launcher metadata |4521154，C0/46秒|55/55通过|仅启动/来源工具验证，不是模型验收|
| Layer/head diagnostic metadata |4521155，C0/410秒|24/24通过|原始生产instrument源保持；未运行完整诊断|
| A01 RTX4090 ABBA metadata |同上|52/52通过|独立四窗口计时尚未运行|
| 真实RTX5090组合等变性 |4521160，FAILED/138秒|48个case全部执行，2通过、46失败；两项原CUDA测试均通过|原abs1e-5/rtol0保持，组合模型未通过等变性验收|
| 聚合报告图 |4521162，C0/40秒|两幅PNG，Root已视觉检查|只读取已冻结公开聚合JSON；没有读取原生标签、NPZ或权重|

真实GPU矩阵的源前后inventory一致，132个原冻结ref的aggregate SHA一致；实际矩阵计算耗时74.79626152012497秒，138秒为整个Slurm父作业分配时长，两者不是同一计时口径。数据读取计数为0。全部48例执行完毕不意味着达到原数学门槛；没有架构采用、容差放宽、FP64生产替换或正式预训练放行。

## 本次实验前注册

[A01 protocol](../../../../configs/model_v3/a01_4090_abba_v1.json) 规定同一实际RTX4090 UUID上的reference/candidate/candidate/reference顺序，每成员2 warmup+20 timed updates。原4520456完整20-batch/500-update数值资格和新52项QA均须保留；本次协议提交先于任何独立ABBA计时。原配方和硬件不改，配方冻结仍需用户确认。

[C4 execution protocol](../../../../tools/model_v3/analysis_sources/C4_layer_head_diagnostic_v2/execution_protocol_v1.json) 规定48个无hook控制加48个有hook诊断，共384次完整encoder forward，要求原终端数组逐位一致、来源/权重/输入不变，原abs1e-5/rtol0不变。该诊断只定位误差，不授予模型采用资格。24项QA的实际C0绑定见data目录。

W&B服务器认证已通过实际API检查，账户mint_leaf、默认entity mint_leaf258。原运行project仍从原生SDK核实；尚未宣称任何新增在线同步成功。最终D1–D7仍未交付，Native-S短profile、4×20k精度曲线、真实新标签验收和最终配方/B*均未闭合。

两幅图及其生成脚本位于figures目录；原A06与七变体聚合快照保持不变，结果图不是新增科学实验。
