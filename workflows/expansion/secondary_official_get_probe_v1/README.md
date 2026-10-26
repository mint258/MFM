# 三原官方URL的有界GET观察

ZIP检查先读最多65557B的EOCD尾部，再允许最多16MiB中央目录；ZIP64/多磁盘或超界只保留原body并pending，避免ZipFile构造时无界分配。

Alpha独立入口 `code/official_get_probe_v1/run.py`，module `official_get_probe_v1.run --plan ABS --startup-proof ABS`。唯一key=`official_three_get_probe_alpha_v1`；analysis/pilot=false/performance_profile=false/16CPU/no_mem/整分钟且120<wall≤3600/whole256MiB。只按contracts.SPECS顺序请求TDC4426004、原MARCEL Drugs DriveID、原Kraken DriveID，不增加镜像、usercontent/uc候选URL、代理或身份接受。所有冻结旧source保留。

5个纯HTTP seam方法在实际allocation中、任何requests import/真实network前执行，必须全PASS且无skip/error/expected failure；保存实际sourcepin/transcript/count。使用注入的fake response，覆盖完整ZIP+CRC/长度伪magic/Range忽略和exactcap/403及读中断/标准redirect+206total+softSTOP；不访问真实数据或旧suite。

实际网络使用 `requests.Session(trust_env=False).get(stream=True,verify=True)`，禁环境proxy和.netrc隐式auth，auth=None、零重试、每hop清除cookie状态；GET/stream方法语义与官码一致，不声称HTTP报文字节相同。只加MARCEL固定Range。标准HTTPS Location最多5跳，allow_redirects=False后按标准Location手动跟随：避免requests自动redirect提前无界读完中间response.content；中间body直接关闭、不下载，明确记录未保留。非HTTPS/userinfo/缺Location/超限保留当前有界响应并停止该源，不换源或确认绕过。只保存redirect hostname，不保存Location查询、cookie、auth/fullheaders或异常字符串/URL。

TDC原URL上限128MiB，Drive两landing各Range首1MiB；若忽略Range仍只读到该上限关闭，绝不解析身份或pickle。raw.read(decode_content=False)保留HTTP实体字节、无透明Content-Encoding解码；若服务器返回编码wrapper，不能把解码假设当原ZIP。按Content-Length和真实空read EOF区分响应完整；恰好到cap不做多1byte探测，即使长度恰等cap也保守PARTIAL。CL错误、读中断和softSTOP都只partialSHA，不伪EOF。

元数据HTTP白名单仅status、GET、MIME token、数字CL、解析后的Content-Range、host、bytes/hash及partial/EOF状态，不输出其它header。原始最终HTTP实体保存在.response.bin（403/404/HTML也不隐藏）；不能取得response的网络错误只记异常类型，无自动retry。MARCEL一律不准archivecomplete，即便小HTML全响应也仅whole-response hash。没有获得新的file-specific下载权限/Archive URL，三原landing失败仍原样失败。

TDC只有200+真实EOF+长度一致+ZIP magic，再对完整已存ZIP核目录/每entry EOF/CRC才给archive_whole_sha256。CRC只流读解压bytes，不解码CSV、不提取原身份或写解压文件；最多256entry/总解压1GiB/单entry128MiB/name4096B、不接受加密，超界或CRC错误保留原body且archive接受PENDING。完整HTTP实体SHA与完整archiveSHA分字段；不宣称44成员或原ID/stereo覆盖。归档构件实际SHA只由本次CPU产生。

plan schema=`SECONDARY_OFFICIAL_THREE_GET_PROBE_PLAN_V1`，startup=`SECONDARY_OFFICIAL_THREE_GET_PROBE_STARTUP_V1`，stage=`OFFICIAL_THREE_URL_BOUNDED_GET_ONLY_NO_IDENTITY`，scope_mode=`EXACT_OFFICIAL_THREE_URL_GET_PROBE_NO_FULL_RELEASE`。scope_parameters精确contracts.PARAMETERS，primary8argv、独立Alpha UID1264/fresh120s/actualgate/job/script/sourcepins/200GB与scope7全pendingcap门槛保留。软件RSS2GiB/MemAvailable4GiB/output256MiB/wall留120s只停下一request/hop，读中的response自然关闭，无kill、无自动续跑。

基本plan字段沿v16 README及既有readonly协议；新增/明确：

- `locator_catalog_reference`：Root原42335B/SHAac77dff2ceef3d1b177765c7338e29aa094f0e8074c1f58d2249e3f42b5b45dd catalog的Alpha原字节copy；`origin_locator_catalog_reference=contracts.ORIGIN_CATALOG`，仅路径角色不同，内容不重写。
- `research_reference`：Root研究8668B/SHAec9b9a996b5374fe66f5ba0cee3a6529ebca20b8ebc89c1d1992cbd3b147b745的Alpha原字节copy；`origin_research_reference=contracts.ORIGIN_RESEARCH`。
- 两件是SourceRefs+ParentEvidence，data_references=[]。必须保留原catalog的HEAD locator/commit/text refs，再由新source发GET；不能改旧catalog的method或伪payloadSHA。
- `resource_authority_reference,cost_decision_reference,root_review_reference`为真实Root批准小pins；SourceRefs含本6source、原catalog/研究copies、所有base queue py及v16全部py/md。输出严格新 `AlphaRoot/artifacts/official_get_probe_v1/<tag>`。

HTTP403/非2xx、TDC未取得完整ZIP、网络/资源失败，receipt和原有界body留存并exit3；这不授权重试。纯观察成功C0也不表示MARCEL下载成功或identity接受。Root读实际结果后另决定是否有任何full GET；本scope不能变通成新full任务。
