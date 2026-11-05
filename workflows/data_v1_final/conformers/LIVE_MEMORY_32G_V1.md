# 336分子小试点：32GiB隔离版本

用户实际回复：“在小规模数据测试时可以降低资源使用情况，但是之后的正式数据生成必须使用原有硬件要求”。

Root的本轮解释固定为：仅既有336分子小试点，16CPU、32GiB、4h，节点14–19。正式S′/P′/扩充生成恢复原硬件要求，不能复用这个例外。SB2只准备代码，Root审阅、创建实际decision和提交。

新增32G runner、policy和Root-only submit adapter；原64G proposal及原科学/配置/prepared字节均不改。节点准入是 MemTotal−MemAvailable+32GiB <= 85%×min(SlurmRealMemory,OSMemTotal)。运行时完整加32GiB，保守重复计入自身内存。自身parent+严格核验的同UID/同job descendants RSS≥24GiB、指标失效或超过2秒未刷新时，只停止新派发；运行中分子自然完成并持久化，不signal/kill/科学重试。监控1秒、parent wait超时0.5秒，8GiB写前输出预算不变。

Root实际decision格式（以下只是文档，没有创建控制目录中的批准文件）：

    {
      "schema": "DATA_V1_LIVE_MEMORY_32G_USER_APPROVAL_V1",
      "status": "APPROVED_BY_USER",
      "user_reply": "在小规模数据测试时可以降低资源使用情况，但是之后的正式数据生成必须使用原有硬件要求",
      "scope": {
        "task": "SB2_SPRIME_FILL_336_PILOT_ONLY",
        "molecules": 336, "cpus": 16, "memory_gib": 32, "wall_seconds": 14400,
        "allowed_nodes": ["compute-0-14","compute-0-15","compute-0-16","compute-0-17","compute-0-18","compute-0-19"],
        "root_interpretation": "仅336分子小试点采用16CPU/32GiB/4h和实测内存监控；正式生成恢复原硬件要求",
        "formal_generation_uses_original_hardware_requirements": true,
        "config_reference": {
          "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/conformers/pilot_v1.json",
          "bytes": 3629,
          "sha256": "cfd153fb524ad823d3903b0ff7d78e402bbbcb74e124136b4bfeb3035279407a"
        },
        "prepared_reference": {
          "path": "/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/prepared_v1/prepared.json",
          "bytes": 54827,
          "sha256": "74b1cda893683e070097d1784b557c6600cdf088a77a077f3026ab9d34b72d34"
        }
      }
    }

request沿原Root控制器字段，新增 memory_basis=LIVE_NODE_MEMAVAILABLE_PLUS_FULL_32G_USER_SMALL_PILOT_EXCEPTION 和实际decision的 approval_reference（path/bytes/SHA）。资源固定 kind=conformer、pilot=true、16CPU/32GiB/14400秒、一个14–19节点；estimated_peak_output_bytes至少8589934592；root_review.status=APPROVED。job-name以dv1_sb2_fill_32g_开头。

source_references必须含新adapter/32G runner/policy、实际decision、原config、closed prepared.json，以及未改动的原run_pilot/common/science/selection/statistics_tools。Root登录source guard拒绝大于2MiB的单个引用，GiB数据只能通过已闭合小authority receipt绑定。

adapter以SHA 6d1e3f5623bcdf04351d50710ccc81b5ca50f23d3b19051cba29f6fee173ee7f 导入已验收原execution/submit_reviewed.py，复用其source pin/SBATCH/CPU/quota检查和元数据工具。共享原Root锁，检查active同名和既有intent/receipt；未知结果不重投，实际job ID先落盘再controller readback。保留全部用户声明，MinMemoryNode=0仍未知/无上限记账，绝不解释为0使用量；仅本批准小试点改用新鲜物理内存准入。严格SSH host key和hostname核验节点，核CPU、全部用户元数据、quota及2秒内内存样本；runner启动后再次现场核验。

Root-only提交：

    /share/home/zixiao/.conda/envs/chemprop/bin/python /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/conformers/submit_pilot_live_memory_32g_v1.py --request /absolute/reviewed_32g_request.json

Root渲染的LF SBATCH脚本必须16CPU/32G/4h、无GPU；保留OMP/BLAS线程1、空CUDA_VISIBLE_DEVICES、PYTHONDONTWRITEBYTECODE=1。化学版本、种子、配方不变。其argv为：

    /share/home/zixiao/.conda/envs/chemprop/bin/python /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/conformers/run_pilot_live_memory_32g_v1.py --config /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/configs/data_v1/conformers/pilot_v1.json --prepared /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/prepared_v1 --output /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/conformers/pilot_32g_v1 --root-preflight /absolute/actual-name.intent.json --approval /absolute/actual_32g_decision.json --approval-bytes ACTUAL_BYTES --approval-sha256 ACTUAL_SHA --workers 16

32个fixture测试（不读真实/proc，不读LMDB，不启动UFF或sbatch）：

    /share/home/zixiao/.conda/envs/chemprop/bin/python workflows/data_v1_final/conformers/test_live_memory_32g_v1.py -v

覆盖32G scope、32G+85%边界、24G RSS、真实原回复/正式硬件保护、原23个身份/时效场景，以及adapter成功、拒绝、timeout、未知响应、既有intent幂等、controller失败仍先落盘job ID、登录guard拒读GiB。Fixture通过不等于实际科学验收。
