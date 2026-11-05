# PubChem 官方原始文件：实际获取结果

目的：取得有版本、完整SHA和gzip完整性证据的官方CID–SMILES原始输入；本任务不执行化学筛选或量化计算。

官方来源为 https://ftp.ncbi.nlm.nih.gov/pubchem/Compound/Extras/CID-SMILES.gz 。版本由Last-Modified固定为Sat, 24 Oct 2026 18:17:31 GMT。下载前、各分片和最终发布均核对相同长度/版本；未使用镜像、代理、自动重试或网络限制绕过。

实际job4520348在compute-0-20申请16CPU/4GiB，COMPLETED/0:0，282秒，4,512分配核秒（1.253333核时）。16个真实worker各负责一个不重叠范围，网络并发2；全部严格HTTP206、Content-Range和长度匹配。随后独立并行重哈希16个完整part、顺序组装并计算整体SHA、流式读取gzip至EOF核CRC和ISIZE；未把解压正文落盘。

完整文件1,488,715,010B，SHA256为2504bc00da1b0587ae208d8a5fb2a4fe6043c215436150f2023d59c57c5cd2b7；gzip解压流实际读取8,880,849,781B。最终CID-SMILES.gz与已验证assembly为同一inode硬链接，parts及全部失败/重现证据保留。作业报告的unique-inode占用2,977,466,207B，低于4GiB硬预算；不能按两个文件名重复累计最终数据体。

外部路径：runs/data_v1_20261025/artifacts/expansion/raw/pubchem_20261025_v1/CID-SMILES.gz。attempt_4520348/receipt.json共10827B，SHA256为2a945e3bfa378b1f958d0214e6a2448cf97d22f81ec2455f359077e3887ad478。Root实际父作业和元数据闭合收据为control/pubchem_raw_actual_closure_v1.json；采集入口为workflows/expansion/download_raw_v1.py。

异常及处理：compute20→sonmi的严格SSH因未登记sonmi主机键返回255，未放宽检查或修改共享SSH配置。实际采用入口已支持的published_receipt：Root在既有已认证sonmi会话重新执行quota，保存原始文本、SHA和真实时间，通过本任务feed原子发布；开始与组装前均强制五分钟内的新鲜收据、扣除完整4GiB预算后保留200GB。任务结束后不再需要持续更新该feed。

限制：此结果仅证明raw获取与完整性。CID/分子数、筛选漏斗、X规则全输入99.9%回归、全部下游全部划分去污染、R/N排序和UFF/D标签仍未验收；不将源文件获取称为扩充候选已完成。
