# 矢量与四极矩参考系：隔离审计 v1

状态：代码与预声明参数准备；未运行新的QM。此目录及新配置不修改已登记的P′2000构象驱动、配置、源parquet或原LMDB。审计几何不进入正式P′、共同人群或训练导出。

## 输入、schema与入口

配置：`configs/data_v1/pprime/vector_frame_audit_v1.json`，schema=`PPRIME_VECTOR_FRAME_AUDIT_V1`，固定proper rotation、平移、单位、容差、2–4分子和全部来源引用。配置还固定原P′配置和3个已登记父helper的SHA，原12任务协议/关键词/软件版本不变。

`prepare_v1.py` 仅在compute20的16CPU/64G Slurm allocation读取Root实际闭合的P′准备包，从其中充足且已验证的分子选择2–4个≤80原子的来源。尽可能覆盖烃、CNO、P/S/Si、Se；缺失层明确报告，补选其它支持元素。每分子取原PM7与固定顺序首UFF两种几何。先以原只读reader复核payload和原子次序，再生成新控制输入，绝不调用QM。

```bash
python -B workflows/data_v1_final/pprime/vector_audit/prepare_v1.py \
  --config configs/data_v1/pprime/vector_frame_audit_v1.json \
  --pilot-config configs/data_v1/pprime/pilot_v1.json \
  --prepared-pprime /absolute/artifacts/pprime/prepared_v1 \
  --prepared-pprime-sha256 <prepared.json的实际SHA> \
  --root-preflight <Root提交器intent或receipt> \
  --output /absolute/artifacts/vector_frame_audit/<new-prepared-dir>
```

`prepared.json`状态=`VECTOR_AUDIT_INPUTS_PREPARED_QM_NOT_STARTED`，绑定`cases.json`和新的全覆盖audit membership。每case含原子序列、来源记录、源几何、arm/condition、传给旧invoke的坐标、实际渲染坐标、全部输入文件的字节/SHA。全包36–72个未来单调用控制，16个线程并行生成输入。新输入正文作为隔离审计复现材料保存，不改变正式P′的no-input raw策略。

未来Root实际审阅和资源批准后，`run_v1.py --execute --config ... --pilot-config ... --prepared ... --prepared-sha256 ... --root-preflight ... --output <new-run-dir>`才能在14–19节点运行；模板为16CPU/64G/≤2h。无自动sbatch、无学校服务器或全量提交。所有控制调用均保留完整输出raw，输入另外保存；随后才清理本次节点scratch。每case实际结果和父worker退出信息独立留存。`run_closed.json`仅表示执行收尾，不是参考系验收。

`evaluate_v1.py --config ... --run <closed-run-dir> --output <new-report.json>`只读取已保留结果；失败、不完整、低信号、坐标重定向、原点或分量不一致分别报告，不改原标签。

## 受控几何与判据

行坐标约定为`X_rot=X@R.T`，矢量`v_rot=R@v`，张量`Q_rot=R@Q@R.T`；绕程序Cartesian原点旋转。R由固定四元数(1,2,3,4)/sqrt(30)得到，行列式+1；固定平移为(0.317,-0.419,0.233)Å。

四个旋转条件为PM7 B、xTB SP(clean)、原扰动梯度(noisy)、SP(同一noisy几何)；每条件base/rotated两arm，再加一次clean SP平移控制。前者三种原任务的参数/关键词均不改。gradient两arm复用同record_id，因此噪声seed相同；旋转arm的名义输入预补偿噪声，使旧invoke按原sigma=0.1Å加噪后，真实输入严格是原noisy几何的proper rotation。noisy SP与gradient的真实输入逐坐标一致，补充SP没有独立输出坐标块的证据缺口。不得把这些审计输入当正式P′扰动配方或样本。

独立reader从MOPAC AUX读取输出坐标、元素次序、dipole与3N梯度，从xTB gradient读取Bohr坐标及梯度，从原JSON读取dipole，从stdout读取r674的full六分量。源输出坐标与实际input.xyz直接比较；若仅proper Kabsch可对齐则明确记录发生重定向，不自动旋回标签。SP的坐标证据限于相同实际输入的gradient控制，不能声称SP自有输出坐标已经独立验证。

单位：PM7 dipole为Debye、梯度为kcal/(mol·Å)；xTB梯度为Eh/bohr，冻结force为`-gradient×27.211386245988/0.529177210903` eV/Å，代数验收2e-12绝对+相对。xTB JSON dipole按原parser常数2.541746473转Debye。舍入误差由源token最后打印位的半ULP（含指数）计算；旋转后用绝对旋转矩阵传播，再加配置中预声明的绝对/相对数值余量。低信号不升级为方向验收PASS，实际差异不事后扩容差。

r674顺序始终为xx,xy,yy,xz,yz,zz，保存全部6项，不删列或投影去迹。对称矩阵由编码定义构造，不能把镜像填充当独立的yx/zx/zy观测。trace与打印舍入上界比较；用RQRᵀ检验旋转，用固定平移检验原点。对xTB的3/2 traceless定义，中性分子即使dipole非零仍有`Q(r+a)=Q(r)+3/2(aμᵀ+μaᵀ)-(a·μ)I`；程序中性命令和源图均核对，a需转Bohr。不能假设四极矩平移不变。

## 一手来源与局限

- [MOPAC23.0.3输出源码](https://github.com/openmopac/mopac/blob/490725eac356e0e75037f37bdd2db343d6bc9e09/src/output/to_screen.F90)同时写出AUX坐标、三分量dipole和梯度；[官方GRADIENTS说明](https://openmopac.net/Manual/gradients.html)定义梯度单位。这里只确定输出语义，实际轴由新输出验证。
- [xTB6.7.1 gradient writer](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/io/writer/turbomole.f90)在同一文件写出mol坐标和梯度；[JSON writer](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/main/json.F90)定义dipole的三分量atomic units。
- [xTB multipole源码](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/aespot.f90)的molmom明确六分量顺序、程序xyz原点及3/2去迹定义；[属性输出调用](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/main/property.F90)传入当前mol几何。
- [axis路径](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/prog/main.F90)允许条件重定向；[默认设置](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/setparam.f90)并非实际运行证明。[legacy换算模块](https://github.com/grimme-lab/xtb/blob/26b28010e805f7d1aeeef39813feb473e69cc4be/src/mctc/convert.f90)的autoaa=0.52917726、autoev=27.21138505，与冻结parser常数有差别；实际XYZ reader还可能走mctc-lib。因此保留原始Bohr坐标，预声明两种已知Å换算假设分别匹配真实输入，不把微小常数差误报轴旋转，也不修改既有force或标签数值。
- [上游issue1470](https://github.com/grimme-lab/xtb/issues/1470)是2026-10-20第三方提交的未解决GFN2梯度报告，本项目未复现。这里保留net-gradient和torque诊断，不擅改程序/加tblite；旋转协变通过也不等于有限差分导数正确。

这些测试只覆盖所选分子的PM7 B和xTB GFN2输出，不认证全部语料、PM7离子/溶剂dipole或其它程序版本。任何实际矛盾先报告Root；原始数据不变。

## 验证入口

`python -B workflows/data_v1_final/pprime/vector_audit/test_v1.py --config configs/data_v1/pprime/vector_frame_audit_v1.json`包含8项受控测试：proper rotation/反射拒绝、旋转噪声实际输入、坐标重定向、错误矢量帧拒绝、AUX顺序、Bohr及force符号、六分量旋转/trace、独立点电荷重算的平移公式。它禁止外部child，不打开LMDB或运行QM；实际执行状态由Root日志给出，本文不预先宣称通过。
