# FFN固定FP32投影：完整48方法 v2（仅Root采集操作修订）
## v2唯一操作差异：Root三路SSH一次并行

v1已实际公开a8f04cfb53f6b3b391c57b188f8f5aee91beb04a/tree9b0b71c12390cbfd7586dbd5f2ef6ab0fab73559，FINAL绑定及audit0曾成功。其三个Root准入尝试都因串行三SSH使资源采集超过原30秒而停在prelaunch：O/ffn_fp32_e2e_GPU_v1_attempt1.json、attempt2.json、attempt3.json均job_id=null、6条原始observations、无sbatch、无admission frame，更无GPU执行。原回执和v1包保留。

实际SSH latency诊断只存阶段标记：authentication约0.134s、Sending command约0.355s、Exit约19.829s，说明一次命令启动可慢；这不证明v2必能准入。v2只在Root submit阶段新增one-shot parallel_resource_frame：原scontrol/node与squeue先照常capture，再用3个独立原guard.Recorder分别对原memory/GPU/applications SSH argv同时capture。每项原strict-known-host、timeout、stdout/stderr/rawSHA、真实started/finished/elapsed不变。三个future全部返回、线程join后，按role分组原样汇入主Recorder；分组不是伪造完成顺序。任何异常均保留各独立Recorder的真实行，随后拒绝。

采集计时在node/queue之前开始，包含SSH认证/登录shell/命令启动、三个future全部结束、合并与原validators，仍须≤30秒；不排除慢启动，不缓存或借用旧值。原root_resource_evidence按唯一role argv核原raw rows，verify_root_resources重建完整body并检查每项age≤120s；它们不要求时间区间互斥或按列表顺序完成。node_capacity、gpu_idle、quota、原public-lock SSH和wholeRoot提交前≤120s门全部不变。worker仍调用原d3的本地worker_resource_evidence，不使用新并行函数。

科学6×512/48/192FP32/0FP64/13字段×3/52终端、1492参数、FFN2304helper/69120K64叶、原attention2304/geometry512及绝对1e-5、rtol0均不变；没有新候选、monitor、dispatcher或QA父。输出、worker/census、SB日志和新尝试使用独立O/ffn_fp32_e2e_GPU_v2_前缀，不与三次v1 NoJob记录混用。协议schema可继续v1，操作包/方法公开路径为ffn_fp32_full48_v2；不能拿v1 method proof准入v2。候选仍e4b/public9977/full4602。

新v2 method尚未公开，输入相应proof保持null，FINAL硬拒；Root须实际源码检查/normal checker/精确9叶公开后再final绑定和fresh资源采集。Source-only作者没有执行Python/AST/SSH/Slurm或任何模型运算。

这是独立薄适配，复用已实际geometry4524579完整48方法及同一资源监督。新候选仓库为MFM_model_v3_ffn_fp32_candidate_v1，Root实际local e4b21193be60fcb396ab1d2d56c1cba6736078dd/tree55eb3d963668e597f4ba3cba16e166465ba4588f；base为geometry03e26bea，不是Core64。原geometry15通过/33失败、原6项CPU norm重放HOLD及全部历史负例保持。

## 同一物理门，单一新增模式

原fixture字节SHA为0c49debe901ee5db79a71fcbc8541d426231c5090eb9740b84649e867d8df0e8，仍固定全部48组合：C1-0/a/b、two/three、H1_fixed/H1_learned/H2_fixed/H3_fixed、两seed。6×512 encoder、原1492全部named-parameter SHA、registry/完整seed权重/非零终端/输入域/噪声和视图变换均不变。

adapter保留原COMPENSATED、centered_fp32_v1、blocked attention projection、residual_expansion_fp32_v1 geometry及原头，仅增加backbone.ffn_projection_mode="blocked_k64_compensated_fp32_v1"。六层FFN两affine全用固定K64/row128 primitive；原SiLU、LayerNorm、softmax、heads/pool、几何和attention算术不变。没有FP64encoder/core或中间dtype升级。新数值路径有意不同，因此不要求新terminal逐位等于4579；旧legacy复现由candidate CPU回归验证，不新增encoder baseline。

完整48共192次真实FP32 encoder forward，原13字段×3变换和每case52终端均先durable保存，再应用原abs≤1e-5、rtol0标准。pytest不fail-fast，不xfail、不删case；完整科学失败与工程前置失败分列，不能把未采集说成48完成。所有源/命令/资源/清理门保持。

## 窄FFN观察器

两个caller类别都实例化/复用attention.DenseFFN，其forward只从attention.ffn_projection这个imported alias调用原helper；SharedPair没有第二FFN alias。adapter先验证alias与v3_ffn_projection.ffn_projection同一函数。按六个原FFN对象与各net[0]/net[3] Linear对象ID建立12个site映射。

spy每次只调用saved original一次、返回同一结果对象；TorchFunctionMode只在这一次实际helper作用域内，核其全部浮点参数/结果为CUDA FP32并记录实际linear叶数。不复制或替换中间tensor，不跨整个model，不重放encoder。finally还原alias、原fixture三个构造器以及原attention/geometry spies。保留原QKV2304和geometry512计数，单独新增FFN2304；three/two native88/132及mask不变。

每个FFN输入affine K512有8叶，输出K1024有16叶；按固定dense rows192/288和rowtile128，每case四frame为1152/1728叶。全矩阵预登记69120叶、每forward12个FFN site、192forward共2304 helper。实际counts/shape/dtype记录不足时拒绝完整验收，不以推算替实测。

## 同job独立tiny控制

保留原projection与geometry真实helper的取消/bias/解析一二阶控制，geometry方向二阶值为26，原projection为56.3125。新增一个实际DenseFFN512→1024→512的小CUDA控制，非encoder：在独立合成dyadic参数处利用SiLU(0)=0、phi'=phi''=1/2，核input/W1/b1/W2/b2五组完整一阶、混合Hessian blocks及37/1024方向二阶。参数对象、实际FP32梯度端口、拒绝非FP32/AMP和CPU/CUDA RNG恢复均检查。Tiny构造在fork_rng内，finally恢复精度设置；不更改物理模型seed或权重。

Tiny和metadata自检不增加科学case/encoder次数，单独落盘，不能作为full48通过。非FP32 guard输入在算术前拒绝，不是混合精度模型路径。

## 来源与未具备的准入

Root实际4524602 CPU已C0/128秒、16CPU/node14，117模块2881 collected=2878PASS+3旧optional skip，0F/0E。其actual Root闭合须严格绑定完整source-before/after/current map、117文件四shards/JUnit、原3skip、supervisor/private/exec receipts及local e4b；这些CPU skips不授权CUDA或真实D3。

Root已实际公开候选9977c6b4995b97eb5537b15aaf85cea67e0647bf，双readback/tree覆盖8个candidate blob，与local e4b/tree55eb同树；实际publication回执及4602 full证书由新版DRAFT绑定。新method公开proof和最终source map尚未具备，相应字段继续保持null/empty。ffn_publication/final_binding只接受实际严格rawref及既有exact-tree/双readback/checker协议；缺失立即拒绝，不能将DRAFT当GPU admission。候选public SHA由真实Root回执输入，不在源中捏造未来ID。方法与2个metadata叶同一批精确发布，验证不可变commit与9叶mapping，不要求reporting HEAD永远停在那个commit。

metadata collector复用actual4602 runtime项目map和原typed两字段external source协议，另显式加入8个candidate authored叶（含runtime scope外的doc）；3字段metadata rawref仍严格，不能缺bytes时通用放行。生成顺序source/input graph→request→pins→result；生成输出不加入自身source_refs，没有SHA自引用环。旧geometry与旧DRAFT文件不改写。

## 资源和结论

原d3cba6资源helper、a1b16 supervisor、UUID admission、单C35/node21/公共fd9锁、16CPU/32GiB、28GiB RSS、1100秒、20min Slurm、whole/private各2GiB、全用户/NVML85%及fresh quota/hold/receipt均复用。没有新monitor、dispatcher或前置QA父。新增仅FFN标量coverage元数据，仍只保存原52终端，不导出参数/数据payload进Git。

新CPU与源码方法公开后，由Root实际准入并唯一提交GPU。任何case未过都保留且不采用；即便实测全过，也仅是原固定域/权重的完整测量，不证明FFN因果或普遍数值界。不得放宽阈值、挑层/seed/字段、缩权重/初始幅度、改坐标量化或用FP64替代正式门。
