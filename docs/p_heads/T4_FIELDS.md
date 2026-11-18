# T4 seed 0 生产者描述性字段附表

运行：`p_heads_T4_seed0`。直接转录既有3M生产者记录，没有重新评价、拟合、bootstrap或计算MAE。

CYP来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/scores.csv`。CYP不进入七任务主分。

| 读出 | 任务 | 原误差 | 随机参考误差 | score | 排除主分 |
| --- | --- | ---: | ---: | ---: | --- |
| R1 | cyp.3A4 | 0.4571428571428572 | 0.6857142857142857 | 0.33333333333333326 | True |
| R1 | cyp.2D6 | 0.5384615384615384 | 0.6153846153846154 | 0.12500000000000008 | True |
| R3 | cyp.3A4 | 0.37142857142857144 | 0.6 | 0.38095238095238093 | True |
| R3 | cyp.2D6 | 0.5769230769230769 | 0.6153846153846154 | 0.06250000000000014 | True |

逐字段原单位VAL来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/runtime/results/p_recipe/training/p_heads_T4_seed0/VAL_original_units_3000000.csv`。

| 字段 | 原单位MAE | 观察数 | 单位 |
| --- | ---: | ---: | --- |
| P.pm7_water.r410.value | 0.05012471335440932 | 2000 | eV |
| P.pm7_cation.r265.z | 1.4247941971968394 | 2000 | Debye |
| P.pm7_octanol.r326.p | 0.007618375898963167 | 106325 | e |
| P.xtb_ALPB_water.r499.value | 0.0031614429835299307 | 2000 | Eh |
| P.pm7_water.r408.value | 0.06126731276512146 | 2000 | eV |
| P.pm7_B.r63.value | 0.05542352921926067 | 2000 | eV |
| P.pm7_octanol.r331.value | 0.018684798962544557 | 2000 | eV |
| P.xtb_ALPB_octanol.r460.value | 0.0031075157814734844 | 2000 | Eh |
| P.pm7_B.r82.Dn | 0.0432052617501195 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_water.r398.value | 0.023543044721453375 | 2000 | eV |
| P.pm7_B.r83.value | 0.0714865889152847 | 2000 | eV |
| P.pm7_B.r46.value | 0.011364299552995007 | 106325 | e |
| P.pm7_octanol.r341.value | 0.05904608845710754 | 2000 | eV |
| P.pm7_B.r44.value | 0.015431025173677393 | 106325 | e |
| P.pm7_B.r54.value | 316.7809755031898 | 2000 | eV |
| P.pm7_B.r52.y | 0.17573022834997393 | 2000 | Debye |
| P.xtb_singlepoint.r670.value | 0.0031166427955914636 | 2000 | Eh |
| P.pm7_anion.r193.value | 2.0476886037216975 | 2000 | A^2 |
| P.pm7_B.r47.value | 0.3549222848198012 | 2000 | kcal/mol |
| P.xtb_singlepoint.r669.y | 0.17506808687144804 | 2000 | Debye |
| P.xtb_singlepoint.r666.value | 0.20936347882859208 | 106325 | Eh bohr^6 |
| P.pm7_B.r55.total | 0.7657433376473706 | 106325 | eV |
| P.pm7_cation.r259.s | 0.007152742939277899 | 106325 | e |
| P.xtb_singlepoint.r672.value | 0.08417682726588101 | 2000 | eV |
| P.pm7_B.r56.EN | 1.1263431381282552 | 798283 | eV |
| P.pm7_B.r84.value | 0.00564139639100775 | 106325 | bond-order population |
| P.pm7_B.r48.value | 0.41748926324855745 | 2000 | kcal/mol |
| P.xtb_vfukui.r712.f_minus | 0.002619733959613079 | 106147 | e |
| P.pm7_B.r56.NN | 0.5353756179472885 | 798283 | eV |
| P.pm7_B.r82.charge_density_q_minus_Z | 0.33410975233236767 | 54838 | e |
| P.pm7_water.r396.value | 2.0480807307775297 | 2000 | A^2 |
| P.pm7_water.r407.value | 1.6620279971965102 | 2000 | kcal/mol |
| P.pm7_B.r45.value | 0.013210056554257313 | 106325 | e |
| P.pm7_octanol.r330.value | 1.7922497636574504 | 2000 | A^3 |
| P.pm7_octanol.r329.value | 2.0479433308432213 | 2000 | A^2 |
| P.pm7_anion.r196.y | 1.4322064589565853 | 2000 | Debye |
| P.pm7_B.r61.value | 0.06152412271499634 | 2000 | eV |
| P.pm7_octanol.r346.value | 0.006633747188414981 | 106325 | e |
| P.pm7_water.r393.s | 0.0030678176941547623 | 106325 | e |
| P.xtb_singlepoint.r669.x | 0.2524773373436765 | 2000 | Debye |
| P.pm7_cation.r263.value | 1.7924201377172548 | 2000 | A^3 |
| P.pm7_cation.r273.value | 3.1769801331497844 | 2000 | kcal/mol |
| P.xtb_ALPB_water.r498.value | 0.0007452187232260846 | 2000 | Eh |
| P.xtb_singlepoint.r671.value | 0.06307250499725342 | 2000 | eV |
| P.pm7_B.r43.value | 1.7922984127994617 | 2000 | A^3 |
| P.pm7_B.r62.value | 0.08379159565837253 | 2000 | kcal/mol |
| P.pm7_anion.r194.value | 1.7923455550210932 | 2000 | A^3 |
| P.pm7_water.r399.x | 0.2959530152416555 | 2000 | Debye |
| P.pm7_B.r52.z | 0.1565752426273357 | 2000 | Debye |
| P.pm7_B.r56.C | 0.024293086741229854 | 798283 | eV |
| P.pm7_cation.r262.value | 2.047980982204617 | 2000 | A^2 |
| P.pm7_B.r52.x | 0.2501016522211794 | 2000 | Debye |
| P.pm7_water.r397.value | 1.7922181363651932 | 2000 | A^3 |
| P.pm7_water.r413.value | 0.006717713744717467 | 106325 | e |
| P.xtb_fod.r537.value | 0.0007032565469191379 | 106325 | e |
| P.pm7_anion.r204.value | 3.5820089144989398 | 2000 | kcal/mol |
| P.pm7_B.r55.electron_nuclear | 1.7077143081210513 | 106325 | eV |
| P.pm7_B.r42.value | 2.0490696550577314 | 2000 | A^2 |
| P.xtb_singlepoint.r677.value | 0.0044072269699665925 | 118841 | bond-order population |
| P.pm7_anion.r190.p | 0.015540687741040343 | 106325 | e |
| P.pm7_octanol.r343.value | 0.0481430145876875 | 2000 | eV |
| P.xtb_singlepoint.r667.value | 0.02928462055972288 | 106325 | bohr^3 |
| P.xtb_vfukui.r712.f_plus | 0.0026668853991135767 | 106147 | e |
| P.pm7_octanol.r326.s | 0.003057614680657296 | 106325 | e |
| P.pm7_B.r68.value | 0.006723843943604756 | 106325 | e |
| P.pm7_B.r65.value | 0.002919087581281775 | 797785 | e |
| P.pm7_water.r393.p | 0.00765091419360118 | 106325 | e |
| P.pm7_B.r40.value | 0.002608340773390975 | 798283 | bond-order population |
| P.pm7_B.r49.value | 0.1282247968694719 | 2000 | eV |
| P.pm7_cation.r265.y | 1.625019316742575 | 2000 | Debye |
| P.pm7_B.r56.total | 0.03769716648281378 | 798283 | eV |
| P.pm7_B.r56.EE | 0.4232058944349738 | 798283 | eV |
| P.pm7_B.r53.value | 0.18563425052610463 | 2000 | kcal/mol |
| P.pm7_cation.r265.x | 3.5272673535866197 | 2000 | Debye |
| P.pm7_octanol.r340.value | 1.650489161546849 | 2000 | kcal/mol |
| P.pm7_B.r56.J | 0.023804482479047543 | 798283 | eV |
| P.pm7_B.r50.value | 0.11249070477485656 | 2000 | eV |
| P.pm7_B.r55.electron_electron | 0.4933589745860029 | 106325 | eV |
| P.pm7_B.r60.value | 1.6495814127845139 | 2000 | kcal/mol |
| P.pm7_B.r56.K | 0.009782928983266317 | 798283 | eV |
| P.pm7_B.r39.s | 0.0032210342401396436 | 106325 | e |
| P.xtb_vipea.r751.value | 0.06271726121693168 | 1999 | eV |
| P.pm7_octanol.r332.y | 0.21782011878420598 | 2000 | Debye |
| P.pm7_anion.r190.s | 0.006504922241932528 | 106325 | e |
| P.pm7_B.r73.value.pi | 0.033380582071322495 | 197626 | bond-order population |
| P.pm7_B.r41.value | 316.82144997746497 | 2000 | eV |
| P.pm7_anion.r196.x | 3.0074430997544694 | 2000 | Debye |
| P.xtb_singlepoint.r669.z | 0.16051383687194903 | 2000 | Debye |
| P.pm7_B.r73.value.sigma | 0.08607122771294132 | 599051 | bond-order population |
| P.pm7_B.r64.value | 0.00922843399133584 | 106325 | e |
| P.pm7_cation.r259.p | 0.016438942269356202 | 106325 | e |
| P.pm7_octanol.r332.x | 0.2914741327180527 | 2000 | Debye |
| P.pm7_octanol.r332.z | 0.1936967398102861 | 2000 | Debye |
| P.xtb_vfukui.r712.f_radical | 0.0018993937392010976 | 106147 | e |
| P.pm7_anion.r210.value | 0.01578961509335752 | 106325 | e |
| P.pm7_anion.r196.z | 1.2158377944115781 | 2000 | Debye |
| P.xtb_ALPB_octanol.r459.value | 0.00043301145282973917 | 2000 | Eh |
| P.pm7_water.r399.z | 0.20597598545026266 | 2000 | Debye |
| P.xtb_vipea.r752.value | 0.04337764704686633 | 1999 | eV |
| P.pm7_B.r39.p | 0.007643366316515167 | 106325 | e |
| P.xtb_fod.r538.value | 0.013329231431946385 | 2000 | e |
| P.pm7_cation.r279.value | 0.017707824441784724 | 106325 | e |
| P.pm7_B.r82.De | 0.03918254768810563 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_water.r399.y | 0.23095224252965998 | 2000 | Debye |
| P.pm7_B.r58.value | 0.08336880651319327 | 318975 | kcal mol^-1 A^-1 |
| P.xtb_singlepoint.r668.value | 0.0037009659765098613 | 106325 | e |
| P.xtb_perturbed_gradient.r624.value | 0.3071900151123815 | 318975 | eV A^-1 |
| P.xtb_perturbed_gradient.r623.value | 0.0379263013321923 | 2000 | Eh |
| P.xtb_perturbed_gradient.r625.value | 0.005835055816212854 | 318975 | Eh bohr^-1 |
