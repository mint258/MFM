2026-10-29 后续实际验收：成熟完整回归CPU4525171 C0/272秒，137模块3235PASS/3原CUDA skip/0失败；包含新50有效更新接线模块及原pilot/CP/H0测试。首seed20科学设计与20接线模板的静态检查已PASS，50步实现通过合成/UNIT验证；真实D3尚未到达，20项真实50步及三卡2000仍待实际运行。详[A采用及回归报告](A_ADOPTION_OPERATIONS_20261029.md)。

# 阶段5首种子配置准备（用户v3）

首种子seed0的20项设计已生成；静态检查实际由CPU4525168（16CPU，node13）运行并通过：20份科学模板、20份独立D3接线模板，6×512×8、H0=512，6+4+9+1项齐全。此静态成功不代表该父作业整体C0；后续测试包装被临时存储保护停止，原FAILED保留。

| 设计 | 首种子数量 | 状态 |
| --- | ---: | --- |
| C1-0/C1-a/C1-b × S/P | 6 | 全部生成；D5/平台/容量证据待绑定 |
| C3两/三视图 × S/SDP | 4 | 全部生成；科学C1胜者待真实选择 |
| H1/H2/H3 × P/D/SDP | 9 | 全部生成；科学C1/C3胜者待真实选择 |
| H1/P可学习池化 | 1 | 已生成；科学前序胜者待真实选择 |

正式模板在 `current/configs/model_v3/stage5_seed0_user_v3/scientific/`，20项清单和顺序见 [PLAN](../../current/configs/model_v3/stage5_seed0_user_v3/PLAN.json)。原24万TRAIN分子、全部授权构象、PM7、lr3e-4/AdamW betas(0.9,0.95)/clip1/2%warmup+cosine保持。6M仍是原提案，平台证据和B0未就绪不伪称冻结。后14项保留科学选择依赖，不把默认C1-0/三视图冒胜者；约6次补种子也不冒生成实际排名或种子SD。

接线模板在同目录 `smoke/`，前序未知项只用明确的C1-0/三视图/H1 anchor，标注NOT_SELECTED_NOT_SCIENTIFIC；C3保留自己的2/3views，H保留自己的H1/H2/H3，池化保留自己的比较项。全部保留plain C及bias=False。未测C/SDP容量继续旧checkpoint；没有塞当前C不支持的performance/training_execution。

薄实现提供 `tools/model_v3/prepare_architecture_wiring_smoke.py`：真实D3普通pilot基请求先走既有validate_request/bind_inputs，真实release、D1–D4、reader、TRAIN和两VAL均保持原语义；再为指定trial生成独立UNADMITTED请求，Root重新绑定新配置。50指累计有效optimizer更新，暂停/恢复也累计到50；不按样本数猜步。50结果不能闭合原2000验收或阶段5科学试验。真实Data未交付，不生成假release、假归一化、假准入或运行结果。

静态检查复用命令：

```bash
python tools/model_v3/check_stage5_seed0_templates.py --root current/configs/model_v3/stage5_seed0_user_v3
```

测试状态：额外检查包装首个父4525167因Root错误假定输出目录已存在而1秒失败、未执行测试；新鲜目录修正后4525168已完成上述静态检查，但pytest临时目录current链接不符合该包装的private-storage规则，8秒被原保护停止，未获得完整测试结果。按用户“两次失败即停止”要求，该额外包装路径标“未解决”，不继续修复或追加QA父。功能回归改用既有已验证的完整回归入口；其通过前不宣称50步实现已验收。两个失败及全部新源保留，不修改原2000 pilot函数或科学DECISION_RULES。

C4已按用户v3 PASS，FP32仅诊断；r674保留头、LOSS_DISABLED。真实D3到达后按用户要求逐项50步，并在24小时内完成阶段3真实验收及三种GPU各一次SDP2000；真实D5到达后开始阶段5科学顺序，不等待非阻塞日志事项。当前D2–D6仍独立待交付。
