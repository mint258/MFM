#!/bin/bash
#SBATCH --job-name=C1-final-byte-publication
#SBATCH --partition=cpu
#SBATCH --nodelist=compute-0-12
#SBATCH --exclude=compute-0-[0-7,14,18,20-22]
#SBATCH --cpus-per-task=1
#SBATCH --ntasks=1
#SBATCH --nodes=1
#SBATCH --time=00:20:00
#SBATCH --output=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/C1_final_publication_%j.log
set -euo pipefail
export PYTHONPATH=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119:/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119/runtime_deps:/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CUDA_VISIBLE_DEVICES='' PYTHONDONTWRITEBYTECODE=1
cd /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/benchmark_b1_20261119
/share/home/zixiao/.conda/envs/chemprop/bin/python -B - <<'PY'
import datetime,fcntl,json,os,re,socket,types
from pathlib import Path
from workflows.benchmark_data.admission import protect
root=Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/benchmark_B0_20261119")
b1=root.parent/"benchmark_B1_20261119";repo=root.parent.parent/"worktrees/benchmark_b1_20261119"
quota=root.parent.parent/"control/benchmark_B0_quota_20261119.json"
def safe():
    for local in (Path("/"),Path("/tmp")):
        st=os.statvfs(local)
        if st.f_bavail*st.f_frsize<max(10*1024**3,st.f_blocks*st.f_frsize//10)+64*1024**2 or st.f_favail<2000:
            raise RuntimeError("Actual root/tmp system/Slurm reserve insufficient")
    protect(root,64*1024**2,quota,own_concurrent_bytes=40*1024**3)
safe()
final=b1/"C1_final_results/job_4538512"
meta=json.loads((final/"manifest.json").read_text())
if (meta.get("status")!="FINAL_C1_RESULTS_CLOSED" or str(meta.get("job"))!="4538512"
    or meta.get("primary_configuration_rows")!=561 or meta.get("required_TabPFN_confirmations")!=175
    or meta.get("required_Chemprop_confirmations")!=17 or not 561<=meta.get("final_seed_rows",0)<=736
    or meta.get("original_primary_scores_recomputed") is not False
    or meta.get("independent_numeric_QA") is not False
    or meta.get("task_roster_reselection") is not False
    or meta.get("pretraining_overlap_status_explicit") is not True
    or meta.get("frozen_B1_screen_unchanged") is not True
    or meta.get("approved_pKa_result_role")!="APPENDIX"
    or Path(meta["final_C1_table"]).resolve()!=(final/"C1_results.csv").resolve()
    or not re.fullmatch("[0-9a-f]{64}",meta.get("C1_sha256",""))):
    raise ValueError("Exact actual first final producer closure required")
sources=json.loads((b1/"C1_remaining_P0_GPU_queues_native_chain/job_4538503/proposed_sources.json").read_text())
transport=types.ModuleType("native_slurm_transport")
exec(compile(sources["workflows/benchmark_evaluation/native_slurm_transport.py"],transport.__name__,"exec"),transport.__dict__)
accounting=transport.native_control(["sacct","-n","-X","-j","4538510,4538511,4538512","--format=JobID,User,State,ExitCode","--parsable2"])
actual={a[0]:a[1:4] for l in accounting.splitlines() if len(a:=l.strip().split("|"))>=4}
if any(actual.get(str(job))!=["zixiao","COMPLETED","0:0"] for job in (4538510,4538511,4538512)):
    raise ValueError("All exact final report-chain native identities must be C0")
out=b1/"C1_final_publication"/("job_"+os.environ["SLURM_JOB_ID"]);safe();out.mkdir(parents=True,exist_ok=False)
updates={}
for name in ("C1_results.csv","C1_results.csv.sha256","C1_second_seed_registered_comparisons.csv"):
    safe();payload=(final/name).read_bytes();updates["results/benchmark/"+name]=payload.decode("utf-8")
timestamp=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S CST")
counts=f'{meta["primary_configuration_rows"]} primary rows; {meta["required_TabPFN_confirmations"]} required second-seed configurations; {meta["final_seed_rows"]} final rows'
close_note=(f"\n\n## C1 final delivery ({timestamp})\n\n"
    f"Native report4538510, evidence join4538511 and final producer4538512 are COMPLETED/0:0. {counts}. "
    "All required configuration evidence has closed under the registered contract. "
    "The final table retains separate seed20261025/20261026 rows and explicit reproduction/failure status; "
    "nonreproduced improvements never change the frozen B1 role. "
    "The approved atomic7644 appendix replaces only the historical C1 mechanism placeholder. "
    "The nine capped TDC/ASAP Pprime cells remain explicit UNRESOLVED. "
    "B1 screening, its17 confirmations, original primary estimates, masks, folds and TRAIN means are reused. "
    "TabPFN pretraining inventory is NOT_OBTAINED/未检查; LightGBM is not applicable. "
    "The three final C1 files are byte copies from the first producer, including its sole existing SHA; no numerical readback, recomputation or independent QA. "
    "See [C1 results](../../results/benchmark/C1_results.csv) and [registered second-seed comparisons](../../results/benchmark/C1_second_seed_registered_comparisons.csv). "
    "P 预训练模型在下游接收的是 UFF 几何。\n")
for path in ("docs/benchmark/REPORTING_NOTES.md","docs/benchmark/CONDITIONAL_CONFIRMATION_PROTOCOL.md","docs/benchmark/VALIDATION_20261120.md"):
    prior=(repo/path).read_text()
    if "## C1 final delivery (" in prior:raise ValueError("Do not duplicate final delivery")
    updates[path]=prior+close_note
updates["docs/benchmark/DAILY_20261122.md"]=(
    f"# 下游基线日报（2026-11-22）\n\n{timestamp}：授权的B0、B1、C1及B2环境准备已闭合；GitHub最终同步与PR检查随后记录。\n\n"
    f"C1首次完整统计8208关闭561主行；175个显著且进入最终结果的TabPFN配置按seed20261026确认，"
    f"4538510首次确认统计→4538511合并→4538512最终导出均C0。最终{meta['final_seed_rows']}行，"
    "[结果表](../../results/benchmark/C1_results.csv)逐行列种子、显著性是否复现、实际覆盖、训练量及未完成原因；"
    "最终CSV及唯一SHA直接复用生产端，不重算原统计或独立复核。\n\n"
    "B1冻结96候选：55保留/34附录/6排除/1历史机制未决，[最终名单](DAILY_20261120.md)及筛选CSV/SHA保持。"
    "17个Chemprop确认已闭合，16项显著改善中15复现，HLM未复现；另含¹H训练重做例外。"
    "C1九格TDC/ASAP P′按两次失败上限未决，不做第三次修复；7644原子pKa仅替换C1历史占位并列附录。\n\n"
    "pKa宏观97614、实验微观0；作者目录TRAIN单/多/未决5588/18838/5546，外部9/29/6，不作全局物理分类。"
    "原子附录TRAIN5465/盲测9，P′4347/9。NMR保留2018作者划分、显式H、原子序及重复观测；HOSE同划分，CSTShift仅DFT参考上限。\n\n"
    "B0原324794 READY/286 PARTIAL、新53842/54均封存；分子P′为原67字段，原子P′38+RDKit37，原缺失保留。"
    "CPU按实际16/32核，V2/离线权重、预处理2、统计seed25及原预算保持；最多11模型，无运行作业重启。"
    "根/tmp、inode/UID配额及跨窗口future持续保护，数据经共享入口，不复制数据库。\n\n"
    "B2固定100推断定稿7可用/4未完成/1权重未公开/2需权限，UMA-S由用户申请。"
    "TabPFN预训练清单未取得，最终表标未检查；LightGBM不适用。"
    "P 预训练模型在下游接收的是 UFF 几何。"
    "本周成本沿用11/20已发布报告，不重复汇总；无新几何/QM、B2全量、B3/B4、付费服务器或预训练。\n")
name="workflows/benchmark_evaluation/native_jobs_20261120.json"
index=json.loads((repo/name).read_text())
index["C1_actual_final_results_closed_20261122"]=dict(meta,native_report_chain_accounting=accounting,
    byte_publication_job=int(os.environ["SLURM_JOB_ID"]),publication_source_cache=str(out/"proposed_sources.json"))
updates[name]=json.dumps(index,ensure_ascii=False,indent=2)+"\n"
before=out/"physical_preimages";safe();before.mkdir()
for name,value in updates.items():
    safe();path=repo/name
    if not path.resolve().is_relative_to(repo.resolve()) or path.is_symlink() or (path.exists() and path.stat().st_uid!=1278):
        raise ValueError("Only exact owned benchmark output paths")
    path.parent.mkdir(parents=True,exist_ok=True)
    if name.startswith("results/benchmark/C1_") and path.exists():raise ValueError("No second final-table publication")
    if path.exists():
        old=before/name;old.parent.mkdir(parents=True,exist_ok=True);os.link(path,old);mode=path.stat().st_mode&0o777
    else:mode=0o644
    temp=path.with_name(path.name+".final-byte-publication-"+os.environ["SLURM_JOB_ID"])
    with temp.open("xb") as stream:stream.write(value.encode("utf-8"))
    os.chmod(temp,mode);os.replace(temp,path)
notice=(f"\n## {timestamp} 下游C1最终生产与交付（本线）\n\n"
    f"4538510→4538511→4538512原生C0，561初始行、175必需确认配置、最终{meta['final_seed_rows']}行；"
    "正常生产端关闭完整证据后按原字节发布最终CSV、已生成的唯一SHA和注册比较。原始主统计/冻结B1名单与17确认不重算，"
    "7644只替换C1原子历史占位；九格TDC既定未决、实际未复现状态及预训练清单未检查均明确保留。"
    "共享B0字段/缺失/构象/标签/划分不变，无额外种子、独立数值QA、第三次TDC修复或重复周成本；"
    "GPU保护、真实节点根/tmp/inode/UID配额与同行future持续，无新几何/QM、B2全量、B3/B4、付费或预训练。"
    "GitHub最终同步及PR验收由本线继续完成。P 预训练模型在下游接收的是 UFF 几何。\n")
safe();status=repo/"docs/interfaces/STATUS.md"
if status.is_symlink() or status.stat().st_uid!=1278:raise ValueError("Owned append-only STATUS required")
with status.open("r+b") as stream:
    fcntl.flock(stream,fcntl.LOCK_EX);prior=stream.read()
    if "下游C1最终生产与交付（本线）".encode("utf-8") in prior:raise ValueError("Do not duplicate final notice")
    old=before/"docs/interfaces/STATUS.md";old.parent.mkdir(parents=True,exist_ok=True);old.write_bytes(prior)
    stream.seek(0,2);stream.write(notice.encode("utf-8"));stream.flush();os.fsync(stream.fileno())
updates["docs/interfaces/STATUS.md"]=(prior+notice.encode("utf-8")).decode("utf-8")
sources.update(updates)
for name,value in (("publication_updates.json",updates),("proposed_sources.json",sources)):
    safe();(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+"\n")
manifest=dict(status="FINAL_C1_FIRST_PRODUCER_BYTES_AND_DOCUMENTS_PUBLISHED",job=os.environ["SLURM_JOB_ID"],
    node=socket.gethostname(),published_CST=timestamp,source_final_producer=4538512,
    final_manifest=meta,changed_files=sorted(updates),source_cache=str(out/"proposed_sources.json"),
    original_STATUS_prefix_preserved=True,physical_preimages=str(before),scientific_CSV_parsed=False,
    original_statistics_recomputed=False,independent_numeric_QA=False,SHA_recomputed=False,
    existing_final_producer_SHA_copied=True,native_model_or_report_jobs_changed=False)
safe();(out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print(json.dumps(manifest),flush=True)
PY
