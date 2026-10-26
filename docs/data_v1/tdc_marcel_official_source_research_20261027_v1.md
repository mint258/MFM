# TDC / MARCEL 官方来源只读研究（2026-10-27）

本轮只读官网、作者仓库、论文及官方API文档；没有SSH、科学body/归档下载、解pickle、Python/Slurm执行或修改冻结源。结论是：**TDC现行官码仍明确给出原Dataverse GET入口；MARCEL仍公开原Drive IDs及原身份字段格式；尚未核到可替代的、官方确认的Zenodo/HF/GitHub payload release。三份归档的实际GET可获取性、bytes、SHA、全人口及stereo完整性仍PENDING。**

HEAD403/landing超时是Root已有实际观察，不是本轮新执行。下列网页工具不可访问也不等于该host实际HTTP403或GET永久不可用。

## TDC：22 endpoints × train_val/test = 44逻辑成员

精确官方归档候选：`https://dataverse.harvard.edu/api/access/datafile/4426004`，ZIP。当前官码及既有冻结commit `c310c35f27e3f506411018ac43d97b8ba23ca652` 均把 `admet_group` 指到这个file ID，格式为zip；此commit只固定**代码/locator语义**，不等于归档bytes/SHA。[TDC metadata](https://raw.githubusercontent.com/mims-harvard/TDC/c310c35f27e3f506411018ac43d97b8ba23ca652/tdc/metadata.py)

官方group loader从上述地址调用 `requests.get(...,stream=True)`，没有HEAD成功前提；group以每endpoint的 `train_val.csv` 和 `test.csv` 读取完整源表。应保留全部22 endpoint的两侧，不用单任务loader重切split或只取test替代44成员。[官方下载链](https://raw.githubusercontent.com/mims-harvard/TDC/c310c35f27e3f506411018ac43d97b8ba23ca652/tdc/utils/load.py)、[group读取代码](https://raw.githubusercontent.com/mims-harvard/TDC/main/tdc/benchmark_group/base_group.py)、[官方22端点说明](https://tdcommons.ai/benchmark/admet_group/overview/)

原生身份：TDC官方入门文档说明输出含Drug IDs、SMILES及labels；但本轮没有读4426004内部CSV，**不能宣称每一成员的实际ID/SMILES列名、行数或stereo文本已核**。下载后应保留源ID文本与源SMILES原值，不能拿canonicalized/去盐/删invalid后的表覆盖原身份，也不能从行号补造ID。[TDC输出说明](https://tdcommons.ai/start/)

当前可读的官方TDC README仍把Dataverse DOI `doi:10.7910/DVN/21LKWG` 列为数据服务器。其网页在本轮普通web打开时显示JavaScript人机验证；小metadata API调用被工具标为不可访问，没有取得upstream checksum/size，未尝试绕过。官网HF组织 `https://huggingface.co/tdc` 本轮页面显示0个公开datasets；TDC HF新闻描述的是模型接口，不能当作原ADMET44归档新release证据。[官方repo](https://github.com/mims-harvard/TDC)、[官方HF组织](https://huggingface.co/tdc)、[官方HF新闻](https://tdcommons.ai/news/)

## MARCEL Drugs-75K

作者现行及冻结commit `dae6b3b824b68d1362ed3b9fa23b34a45fa5366c` 的README，均指向同一官方Drive landing：

`https://drive.google.com/file/d/1PHgbrxdDyyjnxSUA71zXWG8WNwocDLPH/view?usp=sharing`

描述归档为 `Drugs.zip`，含 `Drugs.sdf` 和 `Drugs.csv`。SDF保存各构象，原分子由`name`分组、原构象有`ID`；CSV按name给分子汇总量。75,099分子/558,002构象是上游描述数，**不是本轮实测**。[作者格式说明](https://raw.githubusercontent.com/SXKDZ/MARCEL/dae6b3b824b68d1362ed3b9fa23b34a45fa5366c/datasets/Drugs/README.md)

作者loader还明确读取SDF的原生 `smiles` property、`_Name`和`ID`。因此原始身份候选可从SDF保存的SMILES+原name/ID取得，无需从坐标猜graph、charge或stereo；不能凭README便假设CSV一定包含SMILES列。后续应逐分子跨全部构象核对原SMILES/MolBlock一致性，冲突保留UNKNOWN，不用处理后PyG序号替换原ID。[冻结官方loader](https://raw.githubusercontent.com/SXKDZ/MARCEL/dae6b3b824b68d1362ed3b9fa23b34a45fa5366c/benchmarks/data/drugs.py)

## MARCEL Kraken

官方Drive landing：

`https://drive.google.com/file/d/1QrV651Re7s6UF7Lg4KC9PM5QQUMPU7wd/view?usp=sharing`

README描述 `Kraken.zip → Kraken.pickle`；顶层以原`ligand_ids`为key，每项含原SMILES、分子汇总属性、conformer dict；后者保留conformer ID和MolBlock。1552分子/21287构象是描述数，尚无本轮bytes/SHA/成员实测。[官方格式](https://raw.githubusercontent.com/SXKDZ/MARCEL/dae6b3b824b68d1362ed3b9fa23b34a45fa5366c/datasets/Kraken/README.md)

官方loader把原ligand key转为`mol{int(ligand_id)}`，另设cursor；去污染输入应保存原pickle key及其原类型/文本，并保留原SMILES和MolBlock，不把这些派生名称或cursor说成native ID。取得文件后只做有界真实CPU解码/全成员覆盖，不根据RDKit重建结果补造native charge/stereo。[冻结官方loader](https://raw.githubusercontent.com/SXKDZ/MARCEL/dae6b3b824b68d1362ed3b9fa23b34a45fa5366c/benchmarks/data/kraken.py)

原官网 `https://kraken.cs.toronto.edu/` 本轮重定向至 `https://descriptor-libraries.molssi.org/kraken/`，web可读内容只提示需JavaScript。MolSSI/C-CAS官方框架repo说明这是命名空间化的当前库基础设施，但没有因此确认一个可直接替代MARCEL1552归档的静态身份表URL；其API文档/OpenAPI网页本轮工具不可访问。[当前官方框架](https://github.com/Descriptor-Libraries/descriptor-libraries-framework)

MARCEL作者论文仍指repo提供数据，仓库release页面本轮显示无release；本轮检查的作者README/论文未给出Zenodo或HF payload release。搜索没有发现可确认归属作者的替代release，这是检索范围内的未发现，不是证明世界上不存在。[作者论文](https://sxkdz.github.io/files/publications/ICLR/MARCEL/MARCEL.pdf)、[官方releases](https://github.com/SXKDZ/MARCEL/releases)

原Kraken论文摘要描述1558个计算ligands，而MARCEL要求1552。即使找到MolSSI原库或原论文补充数据，也不能未经明确ID交集/版本/剔除原因核验就当作MARCEL同人口。[原论文](https://pubs.acs.org/doi/10.1021/jacs.1c09718)

## HEAD与GET：可执行的正常官方路径，不是成功声明

HTTP标准中HEAD与GET语义相同但不传body；本轮没有证据证明Dataverse“仅不支持HEAD”，也没有证据证明Root的HEAD403必然意味着普通GET成功或失败。TDC官方实际实现使用GET，因此下一项正常验证应针对同一官方GET入口独立记录状态/redirect/Content-Type，而不是把HEAD作为唯一下载判据。[RFC9110 §9.3.2](https://www.rfc-editor.org/rfc/rfc9110.html#name-head)、[TDC下载实现](https://raw.githubusercontent.com/mims-harvard/TDC/c310c35f27e3f506411018ac43d97b8ba23ca652/tdc/utils/load.py)

Dataverse官方Access API支持普通文件GET和单段Range，但**本轮没有执行ZIP/Range body读取**。若Root另行执行正常有界网络/下载stage，应只走官方许可入口：无access/guestbook则遵循其正常流程，403/人机验证保留失败证据，不换代理、抓取cookie或绕过。归档HTTP200也须核ZIP magic、完整EOF/CRC、实际SHA及44成员守恒，HTML错误页不得接纳为ZIP。`format=original`官方说明仅适用于已ingest的tabular源，不能把给ZIP随意加参数当作已有新release。[Dataverse官方Access API](https://guides.dataverse.org/en/latest/api/dataaccess.html)

Drive的 `/file/d/.../view` 是浏览landing，HEAD其超时并没有实际检验blob GET。官方受授权下载方式是 `files.get` 的 `alt=media` 或实际返回的 `webContentLink`，先核`capabilities.canDownload`。元数据可返回name/mimeType/size/version/headRevisionId/MD5/SHA256，缺值如实pending；它们是文档定义，并非已取得上述两个file ID的实际值。本轮两个landing均工具不可访问，未尝试blob GET，未取得file-specific下载链接/权限/checksum，不能宣布可下载。[Drive下载指南](https://developers.google.com/workspace/drive/api/guides/manage-downloads)、[File字段定义](https://developers.google.com/workspace/drive/api/reference/rest/v3/files)

## Root可继续的最小项

1. TDC保留原4426004作为official GET候选，另做真实普通GET状态检查/有界归档获取；若仍授权/网络失败则pending，不用非官方HF净化表补齐44成员。
2. MARCEL保留两个原Drive ID；正常官方浏览/API权限路径取得真实file metadata及下载链接后再预算CPU下载/格式profile。没有本轮核准的新镜像URL，不能把推测的usercontent/uc URL当已成功的新源。
3. 三份归档实际SHA、全部原ID/原SMILES/graph-stereo核验和all-split/member覆盖均未闭合。本研究只补locator与字段依据，不升级identity来源接受状态；不要求用户重传任何已有可见文件。
