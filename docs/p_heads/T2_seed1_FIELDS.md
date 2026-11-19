# T2 seed 1 生产者描述性字段附表

运行：`p_heads_T2_seed1`。直接转录既有3M生产者记录，没有重新评价、拟合、bootstrap或计算MAE。

CYP来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/scores.csv`。CYP不进入七任务主分。

| 读出 | 任务 | 原误差 | 随机参考误差 | score | 排除主分 |
| --- | --- | ---: | ---: | ---: | --- |
| R1 | cyp.3A4 | 0.37142857142857144 | 0.6857142857142857 | 0.4583333333333333 | True |
| R1 | cyp.2D6 | 0.5384615384615384 | 0.6153846153846154 | 0.12500000000000008 | True |
| R3 | cyp.3A4 | 0.48571428571428577 | 0.6 | 0.19047619047619035 | True |
| R3 | cyp.2D6 | 0.5384615384615384 | 0.6153846153846154 | 0.12500000000000008 | True |

逐字段原单位VAL来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/runtime/results/p_recipe/training/p_heads_T2_seed1/VAL_original_units_3000000.csv`。

| 字段 | 原单位MAE | 观察数 | 单位 |
| --- | ---: | ---: | --- |
| P.pm7_octanol.r346.value | 0.006888519119621523 | 106325 | e |
| P.pm7_B.r56.NN | 0.442196386583006 | 798283 | eV |
| P.pm7_water.r398.value | 0.024403518499778943 | 2000 | eV |
| P.xtb_vipea.r752.value | 0.04524747677717643 | 1999 | eV |
| P.pm7_octanol.r332.y | 0.22344206660450436 | 2000 | Debye |
| P.pm7_octanol.r326.p | 0.008319412750158482 | 106325 | e |
| P.pm7_octanol.r343.value | 0.05248501547192427 | 2000 | eV |
| P.pm7_B.r50.value | 0.1175246775150299 | 2000 | eV |
| P.pm7_B.r52.y | 0.18042991044727386 | 2000 | Debye |
| P.pm7_water.r399.x | 0.29397083895874676 | 2000 | Debye |
| P.pm7_B.r56.EE | 0.4115515610763756 | 798283 | eV |
| P.pm7_anion.r210.value | 0.01641666730943385 | 106325 | e |
| P.pm7_B.r60.value | 1.812616112200389 | 2000 | kcal/mol |
| P.pm7_B.r56.C | 0.02644364439121022 | 798283 | eV |
| P.pm7_cation.r273.value | 3.368944839541372 | 2000 | kcal/mol |
| P.pm7_anion.r196.y | 1.441825835733791 | 2000 | Debye |
| P.pm7_cation.r279.value | 0.018255026981890063 | 106325 | e |
| P.pm7_B.r83.value | 0.07719227228832455 | 2000 | eV |
| P.pm7_water.r393.p | 0.00850423743489796 | 106325 | e |
| P.pm7_B.r68.value | 0.006676969951966159 | 106325 | e |
| P.xtb_vfukui.r712.f_plus | 0.002712405422787214 | 106147 | e |
| P.pm7_B.r56.J | 0.02360405399276572 | 798283 | eV |
| P.pm7_B.r56.K | 0.010320095817870387 | 798283 | eV |
| P.xtb_singlepoint.r668.value | 0.0036144789403593034 | 106325 | e |
| P.pm7_octanol.r332.x | 0.2824986701731104 | 2000 | Debye |
| P.pm7_B.r62.value | 0.08964224059925983 | 2000 | kcal/mol |
| P.xtb_singlepoint.r666.value | 0.17243411164213118 | 106325 | Eh bohr^6 |
| P.pm7_B.r56.total | 0.03912485716941825 | 798283 | eV |
| P.pm7_octanol.r341.value | 0.0634560296535492 | 2000 | eV |
| P.pm7_cation.r265.y | 1.6329398097159282 | 2000 | Debye |
| P.pm7_cation.r265.z | 1.4740118156203534 | 2000 | Debye |
| P.pm7_B.r52.z | 0.1695122616554545 | 2000 | Debye |
| P.pm7_B.r73.value.pi | 0.03284441420111816 | 197626 | bond-order population |
| P.xtb_ALPB_octanol.r460.value | 0.0035026603552055988 | 2000 | Eh |
| P.pm7_water.r396.value | 1.8863108330771985 | 2000 | A^2 |
| P.pm7_water.r407.value | 1.8193389063251133 | 2000 | kcal/mol |
| P.xtb_ALPB_octanol.r459.value | 0.0004540204152981987 | 2000 | Eh |
| P.xtb_singlepoint.r672.value | 0.09299168733600527 | 2000 | eV |
| P.pm7_B.r45.value | 0.013207271197113417 | 106325 | e |
| P.pm7_B.r56.EN | 1.3180690890992652 | 798283 | eV |
| P.pm7_octanol.r340.value | 1.8089854942259058 | 2000 | kcal/mol |
| P.xtb_ALPB_water.r498.value | 0.0007821244598889614 | 2000 | Eh |
| P.pm7_water.r399.y | 0.23728607273986563 | 2000 | Debye |
| P.xtb_vfukui.r712.f_minus | 0.0026941378766996192 | 106147 | e |
| P.pm7_anion.r194.value | 1.8164428229714817 | 2000 | A^3 |
| P.pm7_B.r73.value.sigma | 0.08541688333316243 | 599051 | bond-order population |
| P.xtb_singlepoint.r669.x | 0.25567904621741033 | 2000 | Debye |
| P.pm7_water.r397.value | 1.8166897563016742 | 2000 | A^3 |
| P.pm7_water.r410.value | 0.05471294475220202 | 2000 | eV |
| P.pm7_water.r393.s | 0.0031129427004387426 | 106325 | e |
| P.xtb_singlepoint.r670.value | 0.003466259635563084 | 2000 | Eh |
| P.pm7_B.r61.value | 0.06614119267463683 | 2000 | eV |
| P.xtb_fod.r538.value | 0.014709419743649789 | 2000 | e |
| P.pm7_B.r48.value | 0.4291495370312779 | 2000 | kcal/mol |
| P.pm7_B.r52.x | 0.24450914192794151 | 2000 | Debye |
| P.pm7_anion.r196.x | 3.031375550152225 | 2000 | Debye |
| P.pm7_cation.r259.p | 0.017014230565760742 | 106325 | e |
| P.pm7_octanol.r332.z | 0.2095519077104982 | 2000 | Debye |
| P.pm7_B.r55.electron_electron | 0.58355922842065 | 106325 | eV |
| P.xtb_singlepoint.r671.value | 0.06514340877532959 | 2000 | eV |
| P.pm7_B.r65.value | 0.0030673960239717213 | 797785 | e |
| P.pm7_octanol.r326.s | 0.0030279457123453916 | 106325 | e |
| P.pm7_cation.r259.s | 0.006873361829474705 | 106325 | e |
| P.pm7_anion.r190.p | 0.01604491706591563 | 106325 | e |
| P.pm7_water.r399.z | 0.22135428401868557 | 2000 | Debye |
| P.pm7_octanol.r329.value | 1.8865921259529486 | 2000 | A^2 |
| P.pm7_cation.r265.x | 3.7092535419014747 | 2000 | Debye |
| P.xtb_singlepoint.r669.z | 0.17608235404931474 | 2000 | Debye |
| P.pm7_B.r54.value | 250.83598530223736 | 2000 | eV |
| P.pm7_B.r55.electron_nuclear | 1.6977000197269987 | 106325 | eV |
| P.pm7_B.r41.value | 250.7997140266322 | 2000 | eV |
| P.xtb_singlepoint.r677.value | 0.00475011804463342 | 118841 | bond-order population |
| P.pm7_B.r55.total | 0.8224800100310842 | 106325 | eV |
| P.pm7_B.r39.s | 0.0031935211240390372 | 106325 | e |
| P.pm7_B.r39.p | 0.008287736074926711 | 106325 | e |
| P.pm7_B.r63.value | 0.058548098921455675 | 2000 | eV |
| P.pm7_B.r84.value | 0.006344958870320664 | 106325 | bond-order population |
| P.xtb_fod.r537.value | 0.000755080409573066 | 106325 | e |
| P.xtb_singlepoint.r669.y | 0.1850006191676148 | 2000 | Debye |
| P.pm7_B.r46.value | 0.011386416415362356 | 106325 | e |
| P.pm7_B.r49.value | 0.1297584169319307 | 2000 | eV |
| P.pm7_B.r82.charge_density_q_minus_Z | 0.3390791826524516 | 54838 | e |
| P.pm7_B.r42.value | 1.885850135366544 | 2000 | A^2 |
| P.xtb_ALPB_water.r499.value | 0.003469810516953185 | 2000 | Eh |
| P.pm7_anion.r193.value | 1.8859988050435395 | 2000 | A^2 |
| P.pm7_B.r82.De | 0.039761210144615075 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_water.r413.value | 0.00698172122533813 | 106325 | e |
| P.pm7_octanol.r330.value | 1.8159615239622164 | 2000 | A^3 |
| P.pm7_B.r40.value | 0.0028566452223151803 | 798283 | bond-order population |
| P.pm7_B.r64.value | 0.010117191069005842 | 106325 | e |
| P.pm7_B.r47.value | 0.36370929771843097 | 2000 | kcal/mol |
| P.pm7_anion.r204.value | 3.6882736145051838 | 2000 | kcal/mol |
| P.pm7_cation.r263.value | 1.8165043645132257 | 2000 | A^3 |
| P.pm7_B.r43.value | 1.8168815947003092 | 2000 | A^3 |
| P.pm7_B.r58.value | 0.08336880657063375 | 318975 | kcal mol^-1 A^-1 |
| P.pm7_B.r44.value | 0.015551453015833668 | 106325 | e |
| P.pm7_water.r408.value | 0.06569210481643677 | 2000 | eV |
| P.pm7_anion.r196.z | 1.2190632784153568 | 2000 | Debye |
| P.pm7_B.r82.Dn | 0.044203050384285264 | 54838 | 1/eV (source-dimensional inference) |
| P.xtb_vfukui.r712.f_radical | 0.0019296645818079323 | 106147 | e |
| P.pm7_octanol.r331.value | 0.019411302368830204 | 2000 | eV |
| P.xtb_vipea.r751.value | 0.06483424370862653 | 1999 | eV |
| P.pm7_anion.r190.s | 0.00656164001022651 | 106325 | e |
| P.pm7_B.r53.value | 0.1599671455755613 | 2000 | kcal/mol |
| P.pm7_cation.r262.value | 1.8871334020437873 | 2000 | A^2 |
| P.xtb_singlepoint.r667.value | 0.030223941114575 | 106325 | bohr^3 |
| P.xtb_perturbed_gradient.r625.value | 0.005966970560880439 | 318975 | Eh bohr^-1 |
| P.xtb_perturbed_gradient.r624.value | 0.32005440056315193 | 318975 | eV A^-1 |
| P.xtb_perturbed_gradient.r623.value | 0.042151379733103574 | 2000 | Eh |
