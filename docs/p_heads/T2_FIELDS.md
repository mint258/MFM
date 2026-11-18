# T2 seed 0 生产者描述性字段附表

运行：`p_heads_T2_seed0`。直接转录既有3M生产者记录，没有重新评价、拟合、bootstrap或计算MAE。

CYP来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/scores.csv`。CYP不进入七任务主分。

| 读出 | 任务 | 原误差 | 随机参考误差 | score | 排除主分 |
| --- | --- | ---: | ---: | ---: | --- |
| R1 | cyp.3A4 | 0.4285714285714286 | 0.6857142857142857 | 0.37499999999999994 | True |
| R1 | cyp.2D6 | 0.42307692307692313 | 0.6153846153846154 | 0.31249999999999994 | True |
| R3 | cyp.3A4 | 0.4571428571428572 | 0.6 | 0.238095238095238 | True |
| R3 | cyp.2D6 | 0.5 | 0.6153846153846154 | 0.18750000000000006 | True |

逐字段原单位VAL来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/runtime/results/p_recipe/training/p_heads_T2_seed0/VAL_original_units_3000000.csv`。

| 字段 | 原单位MAE | 观察数 | 单位 |
| --- | ---: | ---: | --- |
| P.pm7_water.r407.value | 1.7635341487949574 | 2000 | kcal/mol |
| P.pm7_B.r52.y | 0.17586111574090318 | 2000 | Debye |
| P.pm7_B.r54.value | 275.9218600284515 | 2000 | eV |
| P.pm7_anion.r190.p | 0.015691812380591252 | 106325 | e |
| P.pm7_B.r58.value | 0.08337159571575699 | 318975 | kcal mol^-1 A^-1 |
| P.pm7_B.r46.value | 0.011316544073065642 | 106325 | e |
| P.pm7_B.r82.Dn | 0.044071557608752115 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_B.r68.value | 0.006417879928133304 | 106325 | e |
| P.pm7_B.r52.x | 0.23748857954632693 | 2000 | Debye |
| P.pm7_anion.r204.value | 3.6798963835977254 | 2000 | kcal/mol |
| P.pm7_B.r64.value | 0.009620212610748476 | 106325 | e |
| P.pm7_water.r399.x | 0.2878773542811396 | 2000 | Debye |
| P.pm7_water.r408.value | 0.06270645046234131 | 2000 | eV |
| P.pm7_B.r56.total | 0.039087865966737814 | 798283 | eV |
| P.pm7_cation.r265.z | 1.4489600265368354 | 2000 | Debye |
| P.xtb_singlepoint.r670.value | 0.0032565456108868034 | 2000 | Eh |
| P.xtb_singlepoint.r667.value | 0.027770731828646072 | 106325 | bohr^3 |
| P.xtb_vipea.r752.value | 0.043688224517684865 | 1999 | eV |
| P.pm7_B.r55.electron_electron | 0.5273781278630635 | 106325 | eV |
| P.pm7_B.r73.value.sigma | 0.08548242171918521 | 599051 | bond-order population |
| P.pm7_B.r60.value | 1.7588016411629033 | 2000 | kcal/mol |
| P.pm7_B.r39.s | 0.0030782077667322436 | 106325 | e |
| P.pm7_B.r83.value | 0.0750409526706091 | 2000 | eV |
| P.pm7_octanol.r332.x | 0.279310582856182 | 2000 | Debye |
| P.pm7_anion.r194.value | 1.8162250367943213 | 2000 | A^3 |
| P.xtb_ALPB_octanol.r460.value | 0.003284767782119985 | 2000 | Eh |
| P.pm7_B.r44.value | 0.015645603177800553 | 106325 | e |
| P.pm7_cation.r279.value | 0.018545208784469105 | 106325 | e |
| P.xtb_singlepoint.r669.y | 0.17692227560052562 | 2000 | Debye |
| P.pm7_B.r49.value | 0.1282979241932335 | 2000 | eV |
| P.pm7_B.r56.EE | 0.4485212212539253 | 798283 | eV |
| P.pm7_B.r56.EN | 1.0251428566284024 | 798283 | eV |
| P.pm7_B.r55.electron_nuclear | 1.824152616406227 | 106325 | eV |
| P.pm7_B.r55.total | 1.0005183644881115 | 106325 | eV |
| P.xtb_fod.r538.value | 0.013793986482585861 | 2000 | e |
| P.pm7_cation.r259.p | 0.016673170523575663 | 106325 | e |
| P.pm7_B.r56.NN | 0.5687061938849635 | 798283 | eV |
| P.pm7_B.r45.value | 0.01301810664485125 | 106325 | e |
| P.pm7_octanol.r326.s | 0.0030206983335545673 | 106325 | e |
| P.pm7_water.r393.p | 0.008067096675981109 | 106325 | e |
| P.pm7_octanol.r340.value | 1.7514935660844364 | 2000 | kcal/mol |
| P.xtb_vfukui.r712.f_plus | 0.0026610478220057544 | 106147 | e |
| P.pm7_B.r56.J | 0.02329673861936171 | 798283 | eV |
| P.pm7_B.r40.value | 0.00268903042221311 | 798283 | bond-order population |
| P.pm7_B.r82.charge_density_q_minus_Z | 0.33752272683543416 | 54838 | e |
| P.pm7_water.r399.z | 0.20321430643304483 | 2000 | Debye |
| P.pm7_anion.r193.value | 1.989811807894146 | 2000 | A^2 |
| P.xtb_singlepoint.r669.z | 0.1641963874424109 | 2000 | Debye |
| P.xtb_ALPB_octanol.r459.value | 0.0004321711520070835 | 2000 | Eh |
| P.xtb_ALPB_water.r498.value | 0.000734115117112649 | 2000 | Eh |
| P.xtb_singlepoint.r671.value | 0.06265821599960328 | 2000 | eV |
| P.pm7_water.r399.y | 0.23000035017402842 | 2000 | Debye |
| P.pm7_water.r413.value | 0.006707925895930686 | 106325 | e |
| P.pm7_octanol.r332.z | 0.19222800938156434 | 2000 | Debye |
| P.pm7_cation.r262.value | 1.989598659485473 | 2000 | A^2 |
| P.pm7_B.r82.De | 0.03937649715280888 | 54838 | 1/eV (source-dimensional inference) |
| P.xtb_fod.r537.value | 0.0007095180482981534 | 106325 | e |
| P.xtb_singlepoint.r666.value | 0.24049021009568633 | 106325 | Eh bohr^6 |
| P.pm7_cation.r265.x | 3.612645963616902 | 2000 | Debye |
| P.pm7_anion.r190.s | 0.0063553597025666105 | 106325 | e |
| P.pm7_cation.r259.s | 0.007099348734105135 | 106325 | e |
| P.pm7_octanol.r329.value | 1.9896174676282126 | 2000 | A^2 |
| P.xtb_singlepoint.r669.x | 0.25157048680220034 | 2000 | Debye |
| P.pm7_B.r52.z | 0.16005564132814107 | 2000 | Debye |
| P.pm7_octanol.r346.value | 0.006601890782482891 | 106325 | e |
| P.pm7_octanol.r330.value | 1.8166793939879027 | 2000 | A^3 |
| P.pm7_B.r53.value | 0.17950214693992886 | 2000 | kcal/mol |
| P.xtb_singlepoint.r677.value | 0.0044447196410746445 | 118841 | bond-order population |
| P.pm7_anion.r196.z | 1.1958353764057392 | 2000 | Debye |
| P.pm7_water.r397.value | 1.8168321638810818 | 2000 | A^3 |
| P.pm7_water.r393.s | 0.0030158916137483635 | 106325 | e |
| P.pm7_B.r84.value | 0.005864857460733248 | 106325 | bond-order population |
| P.pm7_water.r410.value | 0.05391596281727834 | 2000 | eV |
| P.pm7_water.r398.value | 0.023270571892637835 | 2000 | eV |
| P.xtb_vipea.r751.value | 0.06301557959662821 | 1999 | eV |
| P.pm7_B.r47.value | 0.35232162098696684 | 2000 | kcal/mol |
| P.pm7_B.r73.value.pi | 0.03326321569677468 | 197626 | bond-order population |
| P.pm7_cation.r273.value | 3.273829179760195 | 2000 | kcal/mol |
| P.pm7_anion.r196.y | 1.4124651722108246 | 2000 | Debye |
| P.pm7_octanol.r343.value | 0.052001612494925215 | 2000 | eV |
| P.xtb_vfukui.r712.f_minus | 0.0026229904759557604 | 106147 | e |
| P.pm7_octanol.r332.y | 0.2172559219833929 | 2000 | Debye |
| P.pm7_B.r63.value | 0.05906701566596166 | 2000 | eV |
| P.xtb_singlepoint.r668.value | 0.003505786061027546 | 106325 | e |
| P.pm7_anion.r196.x | 2.900446427461182 | 2000 | Debye |
| P.pm7_B.r48.value | 0.41407052168181274 | 2000 | kcal/mol |
| P.pm7_anion.r210.value | 0.01595470335425024 | 106325 | e |
| P.pm7_B.r41.value | 275.8930449381718 | 2000 | eV |
| P.xtb_ALPB_water.r499.value | 0.003322654276694344 | 2000 | Eh |
| P.pm7_octanol.r341.value | 0.060403064489364625 | 2000 | eV |
| P.pm7_B.r62.value | 0.09151390383235096 | 2000 | kcal/mol |
| P.pm7_B.r39.p | 0.00785462142088092 | 106325 | e |
| P.pm7_B.r43.value | 1.816442702475587 | 2000 | A^3 |
| P.pm7_water.r396.value | 1.9898338617998648 | 2000 | A^2 |
| P.xtb_vfukui.r712.f_radical | 0.0019079023055373818 | 106147 | e |
| P.pm7_B.r65.value | 0.0028720321989299177 | 797785 | e |
| P.pm7_B.r56.C | 0.02606618258934419 | 798283 | eV |
| P.pm7_B.r50.value | 0.1156403272151947 | 2000 | eV |
| P.pm7_cation.r263.value | 1.8164719885052416 | 2000 | A^3 |
| P.xtb_singlepoint.r672.value | 0.08876331167574972 | 2000 | eV |
| P.pm7_B.r61.value | 0.06310242867469787 | 2000 | eV |
| P.pm7_B.r42.value | 1.9904523955079572 | 2000 | A^2 |
| P.pm7_octanol.r326.p | 0.007817254267228286 | 106325 | e |
| P.pm7_B.r56.K | 0.010123871502295524 | 798283 | eV |
| P.pm7_cation.r265.y | 1.5880627555217652 | 2000 | Debye |
| P.pm7_octanol.r331.value | 0.018579704518286843 | 2000 | eV |
| P.xtb_perturbed_gradient.r624.value | 0.3029437972464473 | 318975 | eV A^-1 |
| P.xtb_perturbed_gradient.r625.value | 0.005870097914302921 | 318975 | Eh bohr^-1 |
| P.xtb_perturbed_gradient.r623.value | 0.03877140035887321 | 2000 | Eh |
