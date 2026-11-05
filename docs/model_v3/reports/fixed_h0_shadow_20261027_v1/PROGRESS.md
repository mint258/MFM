# 固定 H0 结果与 S 分段更新

2026-10-27。独立CPU分析已执行，下一encoder参考尚待源码冻结和本预注册公开后执行。

## 问题、配置与规则

原48矩阵的FP32物理结果10PASS/38FAIL；此处区分H0继承、几何及头算术。GPU1492透明捕获48×4原前向，CPU1503在公开9179d4818798144d0c6a56dea8f2135b0d56f18f后执行，独立来源及C0闭合见ROOT_CLOSURE.json。输入仍actual1492/new_capture，不是1435缺失H0。

原1e-5/rtol0/两seed/全48均保持。四项带符号分解逐component闭合限1e-10；CPU实际最大FP32、FP64残差分别1.05879e-22、1.32349e-23。16个metadata parser controls和4种小head检查均通过；212份来源原始SHA前后及当前独立核验一致，actual C0/13秒/16CPU13。没有模型或配方采用。

## 结果与决策

三字段共432观察，FP64头仍65项、31/48组合超过1e-5；G最大2.55101e-7、I最大4.28334e-11。在81个GPU超限观察各自argmax同分量，H最大61次、head算术差最大20次。完整21格表及worst同分量有符号项见[分析](ANALYSIS.md)和RESULT_SUMMARY.json。

本固定输入域的偶极相关误差主要继承H0；证据不支持只重写charge中心就能完整修复。下一步用严格原捕获位等门后独立encoder FP64数学reference；原FP32物理门槛仍权威，高精度参考不当作FP32验收，不证明精度下界，不选择C1/视图/头形式。详见../../C4_encoder_precision_prereg_20261027_v1.md；代码未跑前提交。

## 真实 S 与日志

三个成功段的安全endpoint为1000/2000/3000更新，base draws409491/818176/1224619；实际父1438/1459/1485分别2452/2433/2449秒，均C0。三次独立全SDK审计1460/1487/1510通过；恢复游标和parent链不重置。CSV为../../results/native_S_segment_observations_20261027_v2.csv，旧失败1411和旧startup快照保留于v1，不能把新表当新增三次独立从零训练。

| endpoint更新 | PRETRAIN_VAL去噪component RMSE（Å） | R² |
|---:|---:|---:|
|1000|0.08297404937218698|0.3133279975293023|
|2000|0.07011926026837355|0.5096124665245085|
|3000|0.07000775053557823|0.5111709399539909|

VAL取member.validation[str(endpoint)].metrics，并与SDK_expected_summary.fields核对；不把W&B合并summary遗留的顶层TRAIN值当VAL。1024 PRETRAIN_VAL/55650 atoms、同noise seed0。它是现有S自然记录采样，不是D-5/24万分子代理，不能据单条损失/三点曲线选架构、定义平台或通过B比较。

56份完整日志已官方同步、API回读和Root实际闭合；新wpggfu9n为1002行steps2005..3006、nativeexit0/finished，原7不完整保留。统一在线入口已更新。旧offline index仍56条历史entries，与在线56不是同一清单；新6和旧pending bb3fue46缺集中CSV/曲线，已明确七项范围并在准备独立归档，不改旧index/offline_unsynced或伪造已归档。全部原SDK保留。

## 限制与剩余

更新：1505也已实际C0/2442秒，安全4000更新/1629317base、run hk1qa9kl，新的完整SDK核验待执行。本目录SLOT5证书保存该状态；上表及v2 CSV仍是前三段的时间点记录。1548已从安全4000继续5000，运行中不当闭合结果。A01/4090的1338仍排队。D3–D6最终未交、D1draft3未共同冻结，三卡真实SDP2000、P/SDP代理、开发面板种子SD、全量B*及最终用户确认仍待；整体指南未完成。无main、最终tag、recipe冻结或学校付费预训练。