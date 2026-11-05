# 正式训练前整理：实际闭合与 CPU 诊断预注册（v2）

2026-10-27。本报告是中间状态；完整指南、模型与配方均未冻结。

## 真实 S 续训

4521438与4521459均实际COMPLETED/0:0，分别2452和2433秒。安全检查点累计1000和2000次更新，分别409491和818176次base sample draws。原S自然记录采样不等同于尚未交付的D-5/24万分子代理。

4521459的独立SDK审计4521487实际C0/6秒；28项前置检查通过，1002条新记录steps1003..2004、完整科学字段/config/summary/exit0/EOF均匹配，parent=fw6q26wr，新run=k17r9xsd。见本目录Native_SLOT3两份实际证书。下一段4521485从安全2000继续，不把运行中进展当保存点或2万步验收。

## W&B

原固定50条加imuc199l、xswjijb6、jumhvnta、fw6q26wr和k17r9xsd，共55条完整日志完成官方同步、在线回读和Root实际父C0闭合；失败run保持failed。原7条不完整日志保留，未修补伪造或计入55。新增4条与k17的独立闭合及发布凭证见本目录WandB文件；原50证明见上一报告。

在线页面已追加到项目根W&B_训练记录.html，并保留此前完整字节备份。旧50页与旧offline索引不覆盖。在线结论来自各同步作业实际API回读；Root收尾只读元数据及stat，没有再解码SDK，也没有把当前独立SDK重hash写成已完成。

## 固定 H0 捕获及 CPU 分析预注册

预注册06ed098a275a4fa757ec4e6812eb69f7ae148131之后，v2 GPU4521492实际C0/48秒、16CPU/node21/c35。48组合、192次原forward全部捕获；输入在COMPLETE前87711350B，低于128MiB。原返回及参数未改，源前后一致，监督器无剩余记录进程、私有清理错误或外部信号。见CAPTURE各实际证书。

物理测试仍10PASS/38FAIL，不能据捕获成功采用候选。原1435与1484失败完整保留；本次明确为fresh_capture_not_1435_H0。

CPU尚未执行。预检查原精确sacct argv返回父、batch、extern三行；v2只接受一行，与站点实际不符。CPU-only v3严格核原始三行及其SHA：唯一父zixiao/C0/16CPU，两命名step空User/C0/16CPU，非负elapsed不超过父；其他行或重复拒绝。原raw不截取、不改argv。显式分别绑定成功capture v2 manifest与新CPU v3 source，expected supervised argv继续指向v2；不重标producer，不重捕获。

数学、decode、selfcheck与分解函数在main之前逐字沿用v2，shared common/request/protocol也逐字相同。覆盖全部48×3字段×3变换，不重建encoder；FP32原bank与独立FP64 functional shadow比较。D=H+G+I逐component闭合阈值1e-10及原FP32物理门槛保持；FP64分解不当作FP32验收。源快照位于tools/model_v3/analysis_sources/fixed_h0_shadow_v3，manifest SHA2fc31c55ccd916778730f5d047cf4a9018e81ab95c528dee8e173dd2225ee6fc。实际同一CPU作业前置metadata正负自检；16CPU/16GiB、4×4线程、120秒计算、12GiB RSS及whole/private各2GiB预算不变。

## 费用范围修正

截至v16实际快照UTC 2026-10-26T19:35:40.540371+00:00，427个父任务，258.106667分配核小时、10.523889 GPU作业分配小时；不是GPU利用率或金钱费用，包含失败与重试，仍有4521338/4521485活动，非最终总成本。

旧v15按model_v3名称前缀发现，漏了当时raw discovery已存在的6个CPU父：4521401/1405/1458/1460/1478/1482。另新增1487/1488/1491/1492是在旧快照后出现，不能叫旧漏记。原v13字段CPU_parents_previously_omitted只是集合差，混合这两类，解释以本目录实际scope correction为准；旧快照不改。新记账显式核303条CPU回执，保留原417父和精确GPU身份；未知、缺失、重复或CPU/GPU冲突拒绝。

## 剩余依赖

数据线最新STATUS仍未交付最终D3–D6，D1draft3未共同签v3.0。真实新标签三卡SDP2000、24万分子P/SDP架构与配方、双种子SD、D6全量收敛/B*及用户确认仍待完成。A01的4090作业4521338仍排队。没有main改写、最终配置/tag、正式预训练或下游最终测试。