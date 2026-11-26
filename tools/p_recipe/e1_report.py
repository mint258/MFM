"""Final E1 report consumer. It renders closed original results; no fits/draws."""
KS=(1,2,5,10)
TASKS={"qm9.U0_atom","qm9.homo","exp.LogD","exp.LogS"}

def validate_closed(value):
    if value.get("status")!="COMPLETE" or value.get("k_star") not in KS:
        raise ValueError("E1 closed local kstar required")
    if value.get("frozen_recipe")!=["A1","B3","B4","F2"] or value.get("samples")!=3000000:
        raise ValueError("E1 frozen own3M recipe changed")
    cells={x["k"]:x for x in value.get("cells",[])}
    results={x["k"]:x for x in value.get("results",[])}
    if len(value.get("cells",[]))!=4 or set(cells)!=set(KS) or set(results)!=set(KS):
        raise ValueError("E1 four-cell original results required")
    allowed=[]
    for k in KS:
        if not isinstance(cells[k].get("actual_mean_k"),(float,int)):
            raise ValueError("E1 full-cohort actual mean counts missing")
        row=results[k]
        if row.get("missing"):
            reason=row.get("timebox",{})
            if reason.get("scope")!="implementation_or_repair" or not (reason.get("failed_attempts",0)>=2 or reason.get("seconds",0)>=14400):
                raise ValueError("E1 missing cell lacks original timebox exception")
            continue
        if not row.get("frozen_primary") or not row.get("full_primary"):
            raise ValueError("E1 original primary result paths missing")
        ft=row.get("full_task_rows",[])
        if len(ft)!=4 or {r.get("task") for r in ft}!=TASKS or any(r.get("seed_count")!=3 for r in ft):
            raise ValueError("E1 original full4tasks x3seeds rows required")
        for name in ("frozen_R1","frozen_R3","full"):
            comparison=row.get(name,{})
            decision=comparison.get("decision",{})
            if comparison.get("bootstrap_draws_per_seed")!=1000 or decision.get("verdict") not in ("win","tie","loss"):
                raise ValueError("E1 original paired decisions missing")
            if any(decision.get(key) is None for key in ("delta","ci_lower","ci_upper")):
                raise ValueError("E1 paired effect or interval missing")
        if all(row[name]["decision"]["verdict"]!="loss" for name in ("frozen_R3","full")):
            allowed.append(k)
    if not allowed or results[10].get("missing") or value["k_star"]!=min(allowed):
        raise ValueError("E1 minimum non-LOSS local choice differs")
    if value.get("conditional_seed1_required") and not value.get("conditional_seed1_complete"):
        raise ValueError("E1 conditional adoption seed1 unfinished")
    return value

def render(value):
    validate_closed(value)
    def n(x):return "—" if x is None else format(float(x),".8g")
    def table(headers,rows):
        return "\n".join(["| "+" | ".join(headers)+" |","| "+" | ".join("---" for _ in headers)+" |"]+["| "+" | ".join(str(x) for x in row)+" |" for row in rows])
    cells={x["k"]:x for x in value["cells"]}
    results={x["k"]:x for x in value["results"]}
    text=["## 构象数：E1","",
        "全量1,194,228个TRAIN分子，冻结A1+B3+B4+F2。k=1/2/5分别自身3M、seed0；k=10复用round4 F2自身完整退火3M。按已发布固定随机秩、先排D5，不足保留全部、不补足；原固定VAL不变。均匀抽分子后，在允许构象中均匀抽一个。B32、FP32/TF32关闭、原11-07归一化、每臂原60k–150k梯度p99均保持。","",
        table(["k","实际平均k","本臂clip p99"],[[k,n(cells[k]["actual_mean_k"]),n(cells[k].get("clip_threshold"))] for k in KS]),"",
        "frozen使用原七任务R1/R3、第6层H0及读出seed0；full使用原四任务、三个微调种子。full点值与E1决策CI均为三个种子分数的均值，按共同scratch三种子MAE均值归一化。其分子bootstrap在首次主统计中与原ensemble描述区间分别保留；每数据集共享同一分子抽样，1,000次、seed20261025，不把ensemble CI改称种子均值CI。","",
        "每格对k=10沿用原τ=max(0.01,0.05×较大S)及CI规则；R1只报告，k*同时要求frozen R3与full非LOSS。",""]
    rows=[]
    for k in KS:
        r=results[k]
        if r.get("missing"):
            rows.append([k,"缺失","—","—","原实现/修复时间盒"]);continue
        for name in ("frozen_R1","frozen_R3","full"):
            x=r[name];d=x["decision"]
            rows.append([k,name,n(d["delta"]),"["+n(d["ci_lower"])+", "+n(d["ci_upper"])+"]",d["verdict"]])
    text += [table(["k","读出","对k10的Δ","95%CI","判定"],rows),"",
        "本线k*="+str(value["k_star"])+"；P/S共同k*取两线较大者，须用户确认后写入主线。",""]
    chosen=value["k_star"]
    if chosen==1:
        text+=["在本预算与本人群下，额外构象没有可检出的收益；这不表示构象无用。3M下每分子平均仅被采到约2.5次。",""]
    elif chosen<10:
        text+=["本预算与本人群下，构象收益在k*处饱和。",""]
    elif not results[5].get("missing") and any(results[5][name]["decision"]["verdict"]=="loss" for name in ("frozen_R3","full")):
        text+=["k=5仍有LOSS，本预算与本人群下构象收益到10仍未饱和；两种读出的结果分别保留。",""]
    if any(r.get("missing") for r in results.values()):
        text+=["有按时间盒记缺失的格；k*仅为已完成格中的最小合格值，不能据此排除缺失格。",""]
    ft=[]
    for k in KS:
        if results[k].get("missing"):continue
        for row in results[k]["full_task_rows"]:
            ft.append([k,row["task"],n(row["mae_seed_mean"]),n(row["mae_seed_std"]),n(row["scratch_improvement_seed_mean"])])
    text += [table(["k","任务","full MAE种子均值","种子std","scratch改善均值"],ft),"",
        "[完整本线k*与原主统计来源](../../configs/p_recipe/E1_k_star.json)。固定VAL各家族损失及按卡型的原样本/秒、整卡均功耗见当日日报与training目录。",""]
    return "\n".join(text)
