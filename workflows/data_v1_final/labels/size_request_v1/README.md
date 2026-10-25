# Root size pilot 请求物化

`materialize.py` 只用Python标准库，读取实际Root代码和小型闭合metadata并生成新的request、run_actual配置、sbatch和materialization receipt；不导入科学项目模块，不读Parquet/SQLite正文，不运行Git、scheduler、QM、拟合或相关性。

Root整合这两个新文件并静态检查后，调用实际Root入口：

```text
/share/home/zixiao/.conda/envs/chemprop/bin/python -B /share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository/workflows/data_v1_final/labels/size_request_v1/materialize.py --job-name dv1_size_rho_pilot_v1
```

该工具拒绝从child路径运行。新request的所有`source_references`都是实际物理路径、bytes和本次SHA，逐文件不超过2MiB；全部小metadata读取预算32MiB。对旧数据仅继承已绑定plan/receipt中的ref，不借小文件门槛读取科学Parquet，也不重新hash大正文。旧3.5MB catalog等authority引用保留为继承引用，不由本工具打开。16份每组mask JSON receipt均真实校验；≤2MiB指每个pin而非所有16份加总。

配置模板的proposal_config、scan_adapter必须字面指向Root，并按原bytes/SHA核对；legacy adapter_source_pins必须在Root。Root新run_actual配置完整复制冻结模板字节，因此科学参数完全不变；request登记新的run_actual绝对路径，即使其SHA与模板相等也不替代路径身份。源码含7个生产size模块、scan_v2/support/compact/calibration、normalization runtime/reader、legacy4源码、submit_reviewed和物化器自身。proposal registry/lineage、field_map、source config、mask规则、plan/scan/reduction及16receipt、真实13fixture和static/integration证据一并绑定。

物化只允许既有4251records/512molecules/16groups、相同coverage fingerprint与已闭合1% gate。默认输出为`artifacts/labels/size_rho_v1/<job-name>`的新子目录，`--output`可指定该冻结根下另一不存在的字面路径。所有控制文件只创建不覆盖；任何同名request/script/intent/receipt已存在即拒绝，不自动重试。

生成脚本使用node20、16CPU、64GiB、2h、8GiB输出预算，`CUDA_VISIBLE_DEVICES=''`、BLAS各1、`PYTHONPATH=repository:deps`，逻辑Python入口保持chemprop路径。fresh intent由后续Root `submit_reviewed.py`实际配额/全用户声明内存85%检查生成；物化器本身不伪造新鲜quota、不提交。输出receipt给出唯一待执行submission argv。

Root随后对生成request调用既有`submit_reviewed.py --request ...`。当前仅为准备入口；新科学两遍size尚未实际运行，不宣称RSS或结果闭合。最终common/diagnostic/Pprime仍未齐，不发布final registry或D4。
