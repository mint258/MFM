"""Render the startup stop report from immutable small metadata observations."""
from __future__ import annotations
import argparse, datetime, hashlib, json, re
from pathlib import Path

def ref(path):
    data = path.read_bytes()
    return {"path":str(path), "bytes":len(data), "sha256":hashlib.sha256(data).hexdigest()}
def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as f:
        f.write(text)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run-root", type=Path, required=True)
    args=p.parse_args(); root=args.run_root; repo=root/"repository"; ctl=root/"control"
    obs=json.loads((ctl/"preconditions_v2.json").read_text())
    pre=json.loads((ctl/"preflight_v1.json").read_text())
    net=json.loads((ctl/"pubchem_network_probe_v1.json").read_text())
    assert obs["status"]=="STOP_RULE_CONFLICT_PRECOMPUTATION"
    assert net["returncode"]==0 and "200 OK" in net["stdout"]
    qline=next(x.split() for x in pre["quota"]["stdout"].splitlines() if x.strip().startswith("/dev/"))
    used,soft,hard=[int(qline[i]) for i in (1,2,3)]
    finite=[x for x in (soft,hard) if x>0]
    free=(min(finite)-used)*1024
    now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds")
    refs=[ref(ctl/n) for n in ("preflight_v1.json","pubchem_network_probe_v1.json","preconditions_v2.json")]
    refs.extend(obs["sources"]); refs.append(pre["guide"])
    refs.extend(ref(repo/"workflows/data_v1_final"/n) for n in ("audit_preconditions.py","report_preflight.py"))
    manifest={"status":obs["status"],"observed_at":now,"base_commit":pre["expected_base_commit"],
              "source_branch":"data-v1","references":refs,
              "account_quota_free_bytes_as_observed":free,
              "selenium_unavoidable_exclusion_lower_bounds":obs["selenium_unavoidable_exclusion_lower_bounds"],
              "labels":obs["labels"],"scientific_jobs_submitted":[],
              "dataset_completion_claimed":False,"original_data_modified":False}
    put(repo/"configs/data_v1/preflight_sources.json",json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    se=obs["selenium_unavoidable_exclusion_lower_bounds"]
    se_table="\n".join(f'| {scope} | {r["unavoidable_exclusions"]:,} | {r["population"]:,} | {100*r["minimum_fraction"]:.4f}% |' for scope,r in se.items())
    role_table="\n".join(f'| {r["split_role"]} | {r["molecules"]:,} | {r["S_conformers"]:,} | {r["Sprime_usable_conformers"]:,} | {r["insufficient_usable_N_molecules"]:,} |' for r in obs["existing_role_summary"])
    report=f"""# v1 定稿与 PubChem 扩充：启动核验及规则冲突

更新时间：{now}。状态：**STOP_RULE_CONFLICT_PRECOMPUTATION，等待用户决定**。

## 目的与当前范围
依据项目根《数据线工作流程：v1 定稿与数据扩充（Codex B）.md》，先核验存储、节点、已有数据、科学实现和接口。
本次只读闭合审计元数据及源代码，并执行网络 HEAD；未进行 S′ 补齐、P′、训练格式导出或扩充计算，没有新科学 Slurm 作业。
工作仓库位于本 run 的 repository，分支 data-v1，基线 {pre["expected_base_commit"]}。原 LMDB、WP5/S′ 数据、历史代码与验收记录保持原样。

## 输入及哈希
[preflight_sources.json](../../configs/data_v1/preflight_sources.json) 列出指南、资源/网络观察、统计 CSV、Se 状态聚合、角色摘要和本轮脚本的实际字节数与 SHA256。
原始机器观察位于仓库外 ../control/。统计由 audit_preconditions.py 从既有小表重算，不重新扫描科学大表。
preconditions_v1.json 保留为第一次元数据观察；其标量分类误将展开矢量分量当作原标量，已由 v2 修正，不能引用 v1 的标量组计数。

## 规则、参数与必然冲突
指南 1.2 要求 UFF_UNSUPPORTED 从所有条件的共同人群排除，且不更换力场。
同一指南“停止条件”要求“某一元素的分子被排除超过 20%”时立即报告。
已闭合的 2,354 B Se 状态聚合表给出以下不可重试排除下限；分母为各角色全部含 Se 分子，元素出现按分子计一次。

| 范围 | UFF_UNSUPPORTED 中含 Se 分子 | 含 Se 分子总数 | 最低排除率 |
|---|---:|---:|---:|
{se_table}

即使其它所有失败和不足构象全部补齐，这些下限仍超过 20%。这是补齐前可以证明的规则冲突，不是伪称已完成补齐后的实测结果。
遵守指南开头“如果步骤与规则冲突，先停下来报告”，当前不启动科学试点或全量计算。
继续需要用户明确是否允许 Se 专项例外；其它停止阈值保持原规定。

## 已有数据统计
严格 S′ usable 为 SUCCESS 且 converged=True，不能直接使用 generated 数量。

| 范围 | 分子数 | PM7 构象数 | 严格可用 S′ 数 | 不足原 N 的分子 |
|---|---:|---:|---:|---:|
{role_table}

现有权威人口没有独立 VAL。WP5 population/manifest.json 与 S training_inputs_v1/manifest.json 只定义 TRAIN/FULL，routine 为 FULL 子集。
旧 S runner 使用 full/routine 做验证，不能据此自动发布新契约 VAL=FULL。
需在归一化和子集抽样之前确定 v1 的 VAL 权威：从 TRAIN 新划分，或明确将 FULL 用于 VAL 并保留原角色来源。

## 标签口径核验
264 个统计分量中，146 个非空且非常数，与指南总数一致。
分子级原始标量实际为 **43 P + 26 D**；D 另有 1 个逐原子 SASA_atom_A2。因此 27 个 D 字段不是 27 个分子标量。
63 个 N/A 原登记字段对应 103 个全缺失 active 分量，另有 5 个 legacy ESP 占位及 10 个常量壳层分量。
不能为凑指南的“42P/27D分子标量”改变标签层级或重复统计矢量分量。
尚未生成注册表 v3、新掩码或 TRAIN-only 归一化，旧分位数不能充当新 D-4。

## 存储、调度与网络
本次用户 quota 已用 {used:,} KiB，硬限 {hard:,} KiB，余量 {free:,} B（{free/1e12:.3f} TB）。
这是账户 quota，不是整盘 df 剩余容量；后续每批仍须以试点峰值检查 200 GB 保留线。
原检查目标 4520167 为 FAILED 1:0；后续 4520168 为 FAILED 1:0；4520169 正在 compute-0-6 以 48 CPU/8 GiB 执行既有删除任务。本轮未干预。
14–19 节点的逐节点状态、全部用户作业声明、分区和磁盘/inode 原始观察已保存。未提交新的计算，也未占用 GPU 或学校服务器。
compute-0-20 对官方 https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/CID-SMILES.gz 的 HEAD 返回 200，文件 Content-Length=1,488,715,010 B；未下载文件，不能声称已有文件 SHA 或完成获取。

## 五项分工的只读准备
并发工具最多容纳主 agent 加三个子 agent，因此按原五项职责分批调查；全部只读结果已由主 agent 整合。
- SB-1：D-1 未发布；VAL 权威待定。固定分子子集与构象诊断隔离必须在角色冻结后生成。
- SB-2：权威 S′ 为 sprime_s_convergence_20261013/dataset；复用 sprime_v6 的 ETKDGv3/UFF、严格图和立体检查、源索引 proper-Kabsch 0.5 Å 规则。历史队列节点/授权不可直接重用。
- SB-3：偶极矩实际为三分量矢量；PM7 AUX 梯度原布局 3N，xTB gradient 为 N×3、force 为负梯度单位换算。输出坐标系仍需受控验证，不能提前标为全部通过。
- SB-4：真实 WP5 runner_v14 导入 engine_v3，保留原 12 任务、MOPAC23.0.3/xTB6.7.1 和固定扰动协议。旧 compute_molecule 会重读原 LMDB 坐标，P′ 必须显式替换几何读取，独立记录 S′ 坐标 SHA；尚未实现或运行。每分子前两个不同构象的范围还需检查 N=1 人群，当前没有可信 N=1 计数。
- SB-5：X01–X05 实际没有重原子数上限；不能把观测最大 252 当筛选阈值。RDKit 保持 2025.09.5。WP5 泄漏键为 InChIKey前14位加质子化末位，不能用 Murcko 骨架代替。旧 test-only 去污染不满足本轮所有下游全部划分要求；新增来源尚未齐备。默认首批250万、R/N各半且不计算扩充P′，尚未执行。

## 异常处理、已知限制及恢复
停止来自指南中已经可以证明的条件冲突，并非配额不足或 PubChem 断网。
D-1 到 D-7、共同人群 v1、P′ 和扩充数据均未交付；不将本报告或源码检查通过称作数据验收通过。
未删除任何已有文件；后续新 raw 的清理只能按指南/WP5 规则实施，不能扩大到历史数据。
需用户明确 Se 例外与 VAL 来源后才能继续依赖它们的试点；先试点、审核核时和成功率，再提交大规模计算。
"""
    put(repo/"docs/data_v1/startup_preflight.md", report)
    status=f"""# 数据线与模型线接口状态

更新时间：{now}。数据线分支 data-v1，基线 {pre["expected_base_commit"]}。

**数据线状态：STOP_RULE_CONFLICT_PRECOMPUTATION，等待用户决定。**
Se 的 UFF_UNSUPPORTED 不可恢复排除下限已高于指南 20% 阈值；当前没有新科学计算或全量提交。

| 交付 | 状态 |
|---|---|
| D-1 契约 | 未发布；VAL 权威和标签标量层级口径需明确，尚未双方定为 v3.0 |
| D-2 注册表 v3 | 未生成；146 总分量成立，实际43P/26D分子标量及1个原子SASA |
| D-3 试点导出 | 未开始 |
| D-4 TRAIN-only 归一化 | 未开始，需先冻结独立角色 |
| D-5 子集及构象诊断集 | 未开始 |
| D-6 全量导出/分发 | 未开始 |
| D-7 构象统计 | 只复核既有可用性，未完成指南全项统计 |
| P′ / PubChem扩充 | 暂停，未下载或提交科学计算 |

模型线尚不能使用新的真实数据接口；本状态不是共同确认的契约。
完整证据、源哈希及恢复事项见 [启动核验](../data_v1/startup_preflight.md)。
"""
    put(repo/"docs/interfaces/STATUS.md",status)
    paths=[repo/"configs/data_v1/preflight_sources.json",repo/"docs/data_v1/startup_preflight.md",repo/"docs/interfaces/STATUS.md"]
    result={"status":obs["status"],"files":[ref(x) for x in paths],"scientific_jobs_submitted":[]}
    put(ctl/"report_generation_v1.json",json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))

if __name__=="__main__":
    main()
