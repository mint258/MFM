# P′ 试点输入：实际准备结果

目的：在不启动量化任务的前提下，固定1000个已有完整S′且PM7构象数至少2的分子、按SB2种子20261025固定随机顺序选择每分子前两个UFF几何，并确定1%完整记录审计成员。

输入及哈希由configs/data_v1/pprime/pilot_v1.json保存，包含已验收S′manifest、逐分子严格SUCCESS且converged表、WP5正式molecule/record索引、冻结ROUTINE角色manifest和原WP5 contract7。原LMDB未打开；未生成新构象、未启动QM。

实际job4520345：compute-0-20、16CPU/64GiB，COMPLETED/0:0，8秒，128分配核秒。输出1000个分子/2000个唯一UFF记录，固定rank恰好各为0/1；TRAIN530、VAL470，因按file_group/role/size分层而非按原人口比例抽样，不能据此推断全人群角色比例。审计成员恰好20条。三个输出均SHA读回通过；总输出19,391,882B。

prepared.json共4012B，SHA256为3fd2feb6adf9bc125c81fb8be07f97bdbe5737d7bb09f4690da115a8468dcfca。pairs.jsonl共19,385,976B，SHA256为05c1a4909760189b6bfe4b47d5c7b59a3fd5ab13c7d7911e05f687c14f1cbc82。外部根为runs/data_v1_20261025/artifacts/pprime/prepared_v1；Root闭合收据为control/pprime_preparation_actual_closure_v1.json。

异常：DuckDB fetch_arrow_table弃用警告保留，未影响输出；未为消除警告改动已登记源码。已完成的10项合成P′测试不代表真实量化成功率或成本达标。

限制：这是已充足、N≥2的子人群输入准备，最终共同人群尚未冻结。量化成功率≥99.5%和每构象分配核秒≤11.7的门槛仍待2000构象真实QM试点；受控矢量/张量参考系与P/P′分布比较尚未完成。PM7生成热不与不同UFF几何上的生成热作Q02差值；原WP5版本和关键字保持。
