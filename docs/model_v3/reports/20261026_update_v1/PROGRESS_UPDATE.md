# 模型 v3 进展补充：继续执行指南

这是一份新增进展快照，不是最终交接、训练配方冻结或正式预训练许可。既有报告、失败证据和源码快照保持原样。

| 证据 | 本次可以确认的范围 |
|---|---|
| Root 3d9 完整 retry1 | 8 个实际 Slurm 父均 COMPLETED/0:0；2592 collected，2589 PASS、3 skip，0 failure/error；112 个测试文件，显式 Python/config/external-ref 源码范围；7248 allocated CPU seconds。 |
| Native storage v2 修订 QA，4521200 | 82 PASS、0 skip，父 C0，源前后相同。生产适配器仍是原979518…源清单；两份测试来自独立 test_revision_v1。 |
| 原4521193 | 82 collected 中75 PASS、7 FAIL，父 FAILED；保留，不改写为通过。 |
| 原4521104真实reader | 独立实际数据入场的1 PASS、0 skip及父C0继续有效；不由完整CPU回归的skip替代。 |
| C4 layer/head diagnostic v3 | 27 QA PASS及1186父C0；源码已在985f599…公开。完整新诊断矩阵仍待实际CPU运行，不视作组合等变性已通过。 |
| A01 ABBA v2 | 76项QA和新操作协议仅已准备，尚未测试/公开后实跑；CPU繁忙不能记作已通过。原1173失败和v1提交intent保留。 |

完整 retry1执行码为3d9b1cc0c580dacc9398a5570b0c2fff3e257618，原候选公开快照为
[ce7cbf5](https://github.com/mint258/MFM/commit/ce7cbf5776ff546cd47538b120c8f884e2e5867d)，
同tree73a9e47…。后来新增报告/预注册的local41b72bf…与
[public985f599](https://github.com/mint258/MFM/commit/985f599adf15ca6f107eb49f3d47db34def5baa0)
对应treeaa9e91c…。这两个执行/报告身份分别记录，不把后者当作新生产模型训练执行码。

1200修订的是测试fixture的共同时间绑定与真实node-local TMPDIR使用；不能把它解释为生产freshness放宽、某次NTP事件已被确证，或Native GPU profile/precision证书已经完成。它也不代表内部QK/AV CUDA精度观测、20k训练、recipe扫描或B*判定已完成。完整回归的3 skip仍按skip记录；1104实际reader证据单列，不能靠公共环境的optional skip获得真实数据验收。

已公开 public_source_mapping.root.json 保留其创建时的 full_Root_regression=PENDING /
report_publication=Pending。新补充以retry1证书和985实际公开回执更新阅读上下文，不倒改旧映射或旧1159监督器失败。生产工作树MFM_model_v3与报告pubtree MFM_model_v3_reporting_v3也分开核对。

A06 15-update producer已公开在f69的candidate_interfaces子目录，且当前pubtree字节与1091/1123绑定的40539B源码相同。不能因顶层没有A06目录就说producer未公开。现有报告已公开结果、CSV和图；仍应补公开独立SDK verifier、严格schema/聚合脚本和对应测试的精确源码快照。详见SOURCE_MAPPING_AUDIT.md和A06_SOURCE_WHITELIST.json。原archive-v7 bounded reader已公开且同SHA，保持复用。补公开源码不升级A06原NOT_ACCEPTED，也不把15-update诊断当20/500完整验收或已证因果归因。

复制方案只有显式逐文件白名单，不递归复制结果目录，不导出原SDK、NPZ、权重、Native/下游Store、坐标/预测、private member IDs或完整Root输入帧。这里只准备文档和源白名单；未执行Python、SSH、Slurm、Git、发布、绘图或科学选择。后续仍按整份指南推进真实诊断、性能/数值验证、D交付与开发面板依赖，不生成最终HANDOFF或冻结配方。
