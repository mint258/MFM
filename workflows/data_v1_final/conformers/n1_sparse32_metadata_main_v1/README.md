# Main sparse32 metadata builder

纯stdlib小metadata helper，必须Root实际部署到 `repository/workflows/data_v1_final/conformers/n1_sparse32_metadata_main_v1` 后，由Main实际登录UID1278运行。`--approve --reason` 是Root对具体新stage的显式审查输入。它只生成plan、scope review、centralv2 stage_spec和后续materialize argv，不执行CPU entry、不构造/提交Slurm、不启动quota publisher或搬运数据。

```text
MainPY -B -m workflows.data_v1_final.conformers.n1_sparse32_metadata_main_v1.prepare \
  --approve --reason "Root concrete exact32 read-only export review" \
  --metadata-output RUN/control/n1_sparse32_export_stage_v1 \
  --science-output RUN/artifacts/conformers/n1_sparse32_readchain_v1/main_export_v1 \
  --alpha-input-root /gfshome/alpha/codex_data_v1_20261026/inputs/n1_sparse32_readchain_v1/source32_v1 \
  --job-name dv1_q_n1_sparse32_export_20261027_v1
```

所有路径必须替成绝对实际路径，输出严格fresh。可显式指定 `--pilot-review --quota-provider-review --resource-authority --cost-decision --source-handoff --wall-seconds`，默认值均是Root现有v4实际metadata。wall默认3600、必须整分钟且120<wall≤3600；node固定13、16CPU、analysis/pilot=false、no_mem、whole2GiB，central采用 `BOUNDED_METADATA_PREPARATION`。阶段实际会读取32 raw value，不能把“helper只读metadata”误写成“CPU阶段不读正文”。

helper只读小prepared32/receipt/population authority/cost review/accounting/raw/catalog/recipe/quota mapping/provider/源码及授权header。32task+32baseline JSON只从prepared.tasks/baseline_packets继承完整triple，显式DATA，连stat也不做；任何tasks/baselines/packets目录、JSONL、LMDB/Parquet正文都被读取函数拒绝。不会跟随recipe/catalog/authority内的大体积引用。原整LMDB SHA不生成，actual raw bytes/new库全SHA仍由真实Main CPU exporter产生。

11个Root source必须逐件匹配已冻结handoff的Root绝对路径和物理bytes/SHA，不借child同SHA路径。scope PARAMETERS从已核guard.py做受限AST literal/整数shift求值，不执行或import科学模块。3原reader/graph/prepare和原recipe保持实际原pins。Root helper自身、v4 io/contract/quota provider、centralv2和queuev1小transitive源码也纳入SourceRefs。DATA永不因小JSON变为Source。

现有实际32成本review只证明canonical来源及先前UFF科学结果，不用于预测本次只读IO、也不构成Alpha freshproof。原1417/1418全部known父raw账务需守恒、两者必须C0/UID1278/16CPU13。现有quotareview/provider/map/marker静态pins保留，运行时必须Root保持同一个provider新鲜有效；helper不把mutable latest/snapshot固定成过时Source pin，不宣称publisher已启动或仍有效。

成功输出 `plan.json,scope_review.json,stage_spec.json,metadata_handoff.json`。Root先review这4件，再手动执行handoff里的central_materialize_argv；该命令仍只生成request，Root另做真实queue submit/register/observer。不存在自动submit/retry、Alpha部署/传输验证或下一阶段放行。Alpha metadata mode将在另一个新namespace交付，本版登记后不改。
