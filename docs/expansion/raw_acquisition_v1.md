# 官方 raw 获取：Root 提交接口

本入口只获取并校验官方 gzip 文件，不做 PubChem 化学筛选。既有 source pin
保持原样；如文件版本变化，先报告，由 Root 新建版本 pin，不能静默覆盖。

`workflows/expansion/pubchem_raw_v1.sbatch` 使用 all / compute-0-20、16CPU、
4G、1小时，没有 GPU 申请。Root 必须提供唯一 stdout/stderr、准确 repository
与 `RAW_DOWNLOAD_PLAN`、`RAW_ROOT_SUBMISSION_INTENT`，并按现场资源、全部用户
声明内存和 quota 验证后提交。
代码实际运行命令为：

```bash
python -B -m workflows.expansion.download_raw_v1 \
  --plan /absolute/raw_acquisition_plan.json \
  --root-submit-intent /absolute/control/submissions/root_name.intent.json
```

raw plan 的 schema 为 `pubchem_raw_acquisition_plan_v1`，必须包含：

- `source_pin`：实际 pin 的 path/bytes/SHA256；URL 仅允许官方 CID-SMILES.gz。
- `sources`：实际导入的 download_raw_v1.py、common.py、source.py 及执行模板等物理 refs；不能只校验另一份未执行副本。
- `output_root`：`artifacts/expansion/raw/<newdir>` 的绝对路径。
- `workers=16`、`network_concurrency=2`（允许1–4）、`peak_output_cap_bytes=4294967296`、`chemical_screening_authorized=false`。
- `quota`：下述三种实际供应方式之一，必须得到五分钟内的真实用户 quota。

Root 的实际 submit_reviewed intent 使用现有 observed_at/uid/request/quota_raw/
account_free_bytes 等结构，无需改主提交器。脚本验证 UID、node20、16CPU、
2–4GiB、<=1h、>=4GiB峰值及 Root APPROVED；request.source_references 必须
精确绑定 raw plan、pin 和实际导入源。Root 提交时 quota 只保留为提交证据，
不会被当成工作开始时的新鲜运行期 quota。

quota 方式：

1. `mode=submission_preflight`，附 `preflight` 的物理 ref。支持 Root 既有
   `observed_at`、`quota.returncode/stdout` 结构，解析真实 numeric quota -v
   KiB 行。排队或传输使其超过300秒时拒绝继续，绝不把旧提交快照标为 fresh。
2. `mode=published_receipt`，附 `path`：Root 当前发布的
   `expansion_user_quota_receipt_v1`。验证真实 UID/原始 quota 文本 SHA/正的限额
   和时间；启动及组装前重新读取。Root 必须把该供应器的来源与运行身份纳入
   已审阅提交证据，不允许沿用未经核验的旧服务。
3. `mode=login_ssh`、`verified_login_host=sonmi`：仅在 Root 已核实 compute→sonmi
   密钥/host-key 路径时使用。脚本严格 host-key 检查，在登录节点取 hostname、
   UID 和实际 quota；失败就停止，不放宽认证、不读陈旧快照、不尝试网络绕过。

16个 worker 各负责一个连续且不重叠的范围，共覆盖完整文件。每个请求必须
是精确206，Content-Range、长度、Last-Modified 与 pin 相符；支持已有自有
partial 的精确续传。HTTP429或其它错误会阻止新的网络请求，无自动重试；
已在途请求自然闭合，不取消或杀死任何 Slurm/外来进程。

下载完成后16个 part 再进行独立并行 SHA256 复核，然后流式组装并计算整体
SHA。gzip 必须读到真实 EOF，由 gzip trailer 校验 CRC/ISIZE，最多读取64GiB
解压内容且不落解压文件。该读取不解析 CID/SMILES，不属于化学筛选。

HEAD 在开始、分片完成和发布前均与同一 pin 比较。parts 约1.489GB、assembly
约1.489GB；最终文件与 assembly 仅为同 inode 硬链接，按 unique inode 计量
总输出，严格4GiB上限。parts、ownership、失败与 partial 全保留，不删除任何
已有文件。重用目录须新 intent 显式绑定 `resume_from_intent` 原物理 ref。

新合成测试只覆盖此入口，不重跑已闭合的16项：

```bash
python -B -m unittest workflows.expansion.test_raw_acquisition_v1 -v
```

测试包括16段完整覆盖、错误200/Range/长度/版本拒绝、自有 partial 精确续传、
429无重试、整体SHA和真实 gzip CRC，以及300秒陈旧 quota 拒绝。此文档不
预先声称测试或真实获取已通过；实际 receipt 是最终依据。
