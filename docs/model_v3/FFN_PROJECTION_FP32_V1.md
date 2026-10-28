# 固定FP32 FFN投影候选 v1

本文件是单一候选的源码方法，尚无新CPU/GPU通过或科学采用声明。独立基线为geometry候选03e26bea6a29ef96ba5611760763329207212741/tree2d3b8f17e06d73bc2bc47745ccde982625646dd0；其实际4524579完整48组合仍为15通过/33失败，原证据不改写。

## 唯一方法

仅将全部六层FFN的两个affine改用现成固定FP32线性helper。显式配置backbone.ffn_projection_mode="blocked_k64_compensated_fp32_v1"；缺省或legacy仍直接调用原DenseFFN.net，不给旧config补键。原Linear/Parameter对象及net.0、net.3状态键保持，无参数、持久buffer、RNG、初始化、输出缩放或H0/API变更。

实数公式仍为Linear512→1024、原SiLU、原Identity、Linear1024→512。两次affine直接复用未改动的v3_attention_projection.blocked_linear_fp32：K64叶、rowtile128、平衡Neumaier树、bias一次。K与rowtile不是搜索空间；其解析backward对应同一实数线性函数，并保留高阶梯度连接。模型实际前向/反向浮点端口均保持FP32，不引入FP64、AMP、TF32或全局策略变更。

候选仅支持6×512×8、ff_mult2、零dropout，以及既有COMPENSATED、centered_fp32_v1聚合、blocked attention投影、residual_expansion_fp32_v1几何。C1-a/b直接复用原FFN对象，三种C1共用同一实现。全部12个FFN affine必须保留原DenseFFN/Linear/SiLU/Identity布局。局部mode漂移、未知/替换/compiled FFN或backbone，以及未实现的performance/Native路径均明确拒绝，不能声明新mode却运行旧RuntimeFFN。

LayerNorm、softmax、SiLU、attention logits/AV/QKV/out、geometry、pooling/heads、epsilon、物理域、噪声/视图/split/seed/权重/损失均不改。裸tensor状态不能认证mode；须使用完整model config及既有numeric checkpoint contract。SharedPair现有extra_state只在opt-in时新增FFN mode，默认状态结构保持。

## 假设依据与边界

实际CPU4524597保存操作数代数全48闭合，但6项最终norm的CPU/GPU逐位差仍导致HOLD/FAILED。51个原偶极失败argmax处，|H|最大38次、|Q|最大13次；moment链E自身最大值低于1e-5。这些标签不识别上游encoder算子；五条广延标量失败未由两qMLP诊断解释。

源码中DenseFFN仍用两个原生Linear；nn.LayerNorm和torch.softmax也仍为原生路径。numeric_mode仅附加元数据，并不实现补偿LayerNorm。旧4563/4564各stage漂移随层增长、out_norm后降低，但没有分离attention与FFN，不能比较各自max后作因果排名。此次选择仅因为复用已有线性primitive所需的新算术更少；未证明FFN是根因，效果可能改善、恶化或不变。

## 工程测试：尚未运行

test_model_v3_ffn_projection.py有62个计划用例，作者未collect或执行。覆盖实际512→1024→512两site调用、两affine分别跨K取消/bias一次、非连续输入/行顺序/空行、SiLU(1)非零解析一阶梯度，以及SiLU(0)处input/W1/b1/W2/b2完整混合Hessian-vector oracle。后者使用phi'=phi''=1/2，五组二阶块为独立dyadic解析值，方向二阶为37/1024，不重放blocked算法当oracle。

完整六层C1-0/a/b计划验证forward/backward、原Parameter对象、state键、RNG、checkpoint身份；另覆盖缺省/显式legacy、局部fallback、非法构造、dtype/AMP/精度控制、替换FFN/dropout/backbone、空packed输入和直接RuntimeFFN/performance拒绝。参考计算只在测试中，未放入模型路径。工程测试不等于C4或真实数据训练资格；Root须实际normal checker和full regression后才可发布/物理验证。

## 原完整48接线与窄spy

复用既有geometry完整48 harness及资源守卫，配置adapter仅新增上述backbone.ffn_projection_mode，并切到本隔离树及最终真实tested/published bindings。不能使用Core64或混合精度代码。原1492全部named-parameter、fixture/view/registry身份及非零/域检查不变。新候选有意改变舍入，不能要求其terminal等于4579；旧default逐位复现单独核验。

实际call-site为phychem_mfm.model.attention.ffn_projection(owner,linear,values)，实现在v3_ffn_projection.py。未来observer应patch该imported alias，按原FFN/Linear对象ID映射(layer,in/out)，每次只调用saved original一次、原对象原样返回，finally恢复alias。TorchFunctionMode只在单次真实helper内部检查所有浮点操作数/结果是CUDA FP32，不扩为全模型observer，不注入值。

固定预期为48组合、192 encoder forward、2304次FFN helper、12 site全覆盖，原2304 attention projection及512 geometry helper继续核。two/three视图dense rows为192/288，即2/3个rowtile；全矩阵静态预期69120个FFN K64叶调用。这些是待实际检查的源码计数，不是已测数。没有额外encoder baseline/replay或FP64encoder。

保持13字段×3变换、每case52 terminal、两seed、全部48组合、abs≤1e-5且rtol0、所有失败先durable、原参数/source beforeafter/runtime guards。禁止挑层/seed/字段、调阈值、缩初始输出或事后选mode。五条extensive仍由原完整门直接实测，不能拿qMLP结论代替。

## 资源与证伪

每rowtile的两次原GEMM分别改为8及16个K64小GEMM，加固定树算术。全矩阵新增69120个FFN叶、2304次helper，小kernel开销可能显著。两类affine一个满tile的单份partial stack均为4MiB，不能冒称峰值：partials、高低部分、树临时量及activation会共存。无padded edge×512矩阵或持久权重副本；backward保存原输入/权重引用。

保持原16CPU/32GiB、28GiB RSS、1100秒、whole/private各2GiB、85% GPU、单物理UUID和公共锁。不能为跑过而扩cap或调K/rowtile。Root先实际CPU/full/source与方法公开，才能独立提交GPU；future binding在真实证据前保持pending。

若任一case未过，则原物理要求未满足，保留负例且不采用；非单调变化不能说成一致改善。即使全过，也仅是固定测试域/权重的实测，不是所有实数/权重的误差界或模块因果证书。候选同时影响全部下游头的H0，但不承诺解释或消除所有广延标量失败。
