# Alpha labels512：独立只读port v1（待Root实际执行）

Main4521327仍PENDING，不修改其已登记六文件/请求/作业。这里仅改变实际endpoint、逐文件explicit relocation、独立Alpha guard/输出和同allocation搬运SHA；原数值、mask、shape、6fixture方法body和扫描函数不变。本代理只读small metadata/source和大body stat，未运行Python/AST/tests/SSH/Git/Slurm或大body hash。

## 精确搬运范围

固定transfer_inventory_v1.json为515109B/SHA b20b5a8a707dc2614d1e77dda7ac7c7371f89e6cb673218900c35171bb20282d，源Main request132028B。data227共2714663309B（所有whole-file SHA已有Main冻结ref，本轮没有补猜）：

|用途|件数|bytes|
|---|---:|---:|
|scan canonical.sqlite|1|1733042176|
|scan原family Parquet|209|970140107|
|scan完整选择owner-index|16|249172|
|独立reduce额外expected_role.uint8|1|11231854|

扫描本身226件2703431455B；为后续闭合一并搬227。Main全部227已仅stat复核长度无差异；库存所有Alpha目标仍EXPECTED/NOT_INSTALLED/NOT_HASH_VALIDATED，不能称传输已通过。另原source_refs54件（41py/13metadata）共3983319B，原JSON保持Main路径、原字节/SHA。body到AlphaRoot/inputs/labels_payload512_v1/main/原Main-project-relative；repo内small到code/labels_payload512_frozen_v1/repo-relative，repo外small同inputs/main结构。

原scan只开这些body及small registry/calibration/plan/config，不触LMDB，也不递归打开full frozen plan/census所列其它715GB。raw archive locator仅保存候选，不打开未搬archive；record_id中的lmdb名字只是opaque provenance。source_model tree不涉及。

## 代码与明确端点

AlphaRoot=`/gfshome/alpha/codex_data_v1_20261026`，endpoint218.192.171.238:22，UID1264；与Main同名sonmi/node/job不可混用。

- primary `AlphaRoot/code/payload_audit_alpha_v1/run.py`，module payload_audit_alpha_v1.run，CLI `--plan PLAN --startup-proof PROOF`。独立新plan/proof/key/stage由Root secondary_cpu_readonly_queue_v5锁定。
- run.py的init_worker/source_columns/json_safe/bounded_worst/run_group全文保持Main字节；payload.py原7834B/SHA5f29b355abe5f5eed9de9c570cc2844c4bf394c1408e3ae302bef0e8e222bb0d原样复制。
- support.py是独立Alpha IO层；每个Main路径必须在281条一对一map中，不能prefix fallback。只解析声明的目标路径，不改原JSON、不monkeypatch Main module globals，不调用Main guard。
- 原6方法从Frozen层原`workflows.data_v1_final.labels.payload_audit_v1.test_payload`加载（4247B/SHA3ee3acc1394232a7f0b39fb035da8701cca89cb08a96e9b1877795ba4376b8d1），保持parents[4]仍是Frozen repo。原第6测试需要的streaming_v1.json新增辅助文件只改4个adapter.path，原4022B/SHA92445408cf6a64de2e3b30e41cb0ee99136046acaf6f4848faeb3e8b80694bb3另存Alpha metadata，来源不改写。这两者不增加固定281 map。
- observer保留原1s RSS/MemAvailable、4GiB软STOP、scan worker3GiB软件线、自然drain；仅修改Alpha输出root/schema/plan-reference与独立ENV。16CPU/no requested memory/no exclusive/7200s/output8GiB/quota200GB；无QM/UFF调用。

## 只读metadata打包

prepare_bundle.py纯stdlib，从固定库存和Main原streaming_v1.json生成小map/原配置copy/新辅助配置/变换receipt；不读/hash大body，不在Alpha安装或声明target已验证。Root可在Main实际执行：

```bash
PY=/share/home/zixiao/.conda/envs/chemprop/bin/python
R=/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025
$PY -B -m workflows.data_v1_final.labels.payload_audit_alpha_v1.prepare_bundle \
 --inventory "$R/repository/workflows/data_v1_final/labels/payload_audit_alpha_v1/transfer_inventory_v1.json" \
 --streaming-config "$R/repository/configs/data_v1/labels/streaming_v1.json" \
 --output-directory "$R/control/labels_payload512_alpha_small_package_v1"
```

package_receipt.json给4个small本地实际pin→Alpha target_locator：map至metadata/labels_payload512_v1/relocation_map.json，原streaming配置至metadata/.../streaming_v1_original.json，新辅助至Frozen/configs/data_v1/labels/streaming_v1.json，transform至metadata/.../fixture_auxiliary_transform.json。原227+54走固定库存SFTP，primary本目录所有.py/.json/.md及4个小文件都必须入Alpha实际source pins，不伪造Main prefix。

map schema LABEL_PAYLOAD512_READONLY_RELOCATION_MAP_V1、entries恰281；origin_reference完整保留库存（允许原metadata extras），target_reference纯path/bytes/sha三元组；每件源目标bytes/SHA相同。新辅助仅作为plan.fixture_auxiliary_config_reference单列source，原/变换分别plan.fixture_auxiliary_original_reference/fixture_auxiliary_transform_reference。

## 启动、原6测试、实际227 SHA、scan顺序

plan/proof固定为SECONDARY_LABEL_PAYLOAD512_READONLY_PLAN_V1/SECONDARY_LABEL_PAYLOAD512_READONLY_STARTUP_V1，scope_key labels_payload512_readonly_alpha_v1，stage LABEL_PAYLOAD512_EXISTING_VALUES_PILOT。fresh Alpha job/node/UID/boot/clock/current argv/source pins/Root review/quota通过后：

1. 原6fixture严格发现6/run6、fail/error/skip/expectedFail/unexpectedSuccess=0、源SHA不变；保存实际transcript/count/source pin，在此之前不打开任何真实body。
2. 本allocation用最多16个线程stream全部227文件SHA，1MiB buffer，open前后fstat/dev/inode/size/mtime/ctime/UID1264稳定，逐件比Main冻结expected SHA；不解析值、不写源。失败保留partial，不进入scan。
3. 当227/2714663309B全部actual PASS，输出output/transfer_verification.json，含实际Alpha endpoint/job/node/UID/boot、原expected inventory/map、actual target SHA/bytes及线程计数；plan.transfer_verification_reference启动时必须null，只声明expected_output_path，Rootcontroller不冒领未来body hash。
4. 再执行原16owner/512mol/4251records/14task scan，同dataset/calibration，不改变任何数值/shape/mask阈值；manifest定位实际transfer receipt。

独立guard核实际Python3.11.14/NumPy2.2.6/RDKit2025.09.5/Arrow17.0.0并记录；Main给定Arrow major25。原6纯数值helper PASS不是Arrow17 Parquet兼容已通过，真实4251-record source scan及之后coverage/quality归约才是实际证据。COCO profile不能代替Labels验收。

## 源等价证明和未完成项

verify_port.py仅读小source并做AST；比较五个完整science函数、kernel bytes，fixture gate仅两处endpoint locator替换的inverse相等，不运行数据。Root可在Main或Alpha用原Frozen repo和新包路径执行；本代理只做PowerShell文本byte预比较，science连续函数段/kernel均相等，Python AST证明尚未实际跑。

不能因port/6tests/227 SHA或source scan C0就称新mask冻结、1.5完成或D4完成。native打印precision、实际vector/tensor原点/frame、原unit/版本待证项目及full matched TRAIN calibration/common/diagnostic门槛全部保留。原P′协变矛盾没有由此放行；无新增QM或S′/P′来源替代。Main作业若后来执行，双方只读audit输出须分endpoint记账，不把Alpha同名job/node证据充Main。