# 新增 alpha 集群实际接入

用户授权测试218.192.171.238的alpha账户，并在可用时分担部分新数据生成；同时明确原集群没有金钱计算费用。密码仅用于交互式SSH/SFTP认证，不保存在项目、技能、脚本、日志或命令历史。本记录不含认证秘密。

已实际登录。新账户UID1264，hostname与Slurm ClusterName均为sonmi，必须与原zixiao端点分别记录。CPU分区包含compute-0-1、3–6及sonmi1；接入时1和6各有64空闲CPU。Slurm使用CR_CORE，内存字段只有1MiB且默认UNLIMITED；新脚本按用户要求不申请内存，不从这些字段虚构物理容量。

`/share`账户quota现场已超限。独立新目录 `/gfshome/alpha/codex_data_v1_20261026` 已创建并实测写通；计算节点statvfs报告总2TiB、剩余2199020990464字节，原share配额不作为该挂载的剩余量。任何正式输出仍需单独检查容量、阶段上限和至少200GB余量，不覆盖旧环境或用户数据。

实际CPU环境检查1884759在compute-0-1完成：COMPLETED/0:0，34秒、16CPU；未指定内存、未调用UFF/QM。完整结果已通过SFTP传回 `control/secondary_cluster_20261026_v1/environment_1884759.json`，5899字节，SHA256 `39bddd0e42e94871b9ed4201529368aeb47f5de48bcd1568f1ea94f25002f134`。源probe脚本在仓库及新集群字节相同，SHA256 `04813de423dcfc8cc8586f17c896cdf1d4c60a840b6beb8e42428d92e754969c`。

现有mopac环境为Python3.9/RDKit2024.03.2，与原冻结RDKit2025.09.5不符，未用于新科学计算。隔离环境构建1884760实际FAILED/1:0，61秒、16CPU：官方conda-forge未提供该请求中的SciPy1.15.3及PyArrow25.0.1组合。失败回执已保留；没有改旧环境或替换科学版本。

后续1884761在CPU1运行最小兼容环境构建：先尝试Python3.11.14、RDKit2025.09.5、NumPy2.2.6，再安装SciPy1.15.3、LMDB1.7.5和用于I/O的Arrow17。它仍是环境准备，不构成UFF、golden重放或正式新数据成功。原科学核心、原始pickle字节及其SHA、task/seed、图/立体/0.5Å规则将保持；只有受控重放逐项一致后才放行新切片，防止两集群重复计算同一task。

技能两份副本已同步1.0.121，SHA256 `118b46f7777e2a87826f677bda70629f884a00f95545cfc83cc73c073c039b29`；资源授权单独见 `configs/data_v1/secondary_cluster_user_authorization_20261026_v1.json`。原学校付费预训练服务器未使用。金钱费用与分配核时分别处理，全部失败、超时及实际核时继续保留。
