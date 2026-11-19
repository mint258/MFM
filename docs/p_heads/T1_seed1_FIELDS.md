# T1 seed 1 生产者描述性字段附表

运行：`p_heads_T1_seed1`。直接转录既有3M生产者记录，没有重新评价、拟合、bootstrap或计算MAE。

CYP来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/scores.csv`。CYP不进入七任务主分。

| 读出 | 任务 | 原误差 | 随机参考误差 | score | 排除主分 |
| --- | --- | ---: | ---: | ---: | --- |
| R1 | cyp.3A4 | 0.5142857142857142 | 0.6857142857142857 | 0.25000000000000006 | True |
| R1 | cyp.2D6 | 0.5769230769230769 | 0.6153846153846154 | 0.06250000000000014 | True |
| R3 | cyp.3A4 | 0.4285714285714286 | 0.6 | 0.28571428571428564 | True |
| R3 | cyp.2D6 | 0.5384615384615384 | 0.6153846153846154 | 0.12500000000000008 | True |

逐字段原单位VAL来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/runtime/results/p_recipe/training/p_heads_T1_seed1/VAL_original_units_3000000.csv`。

| 字段 | 原单位MAE | 观察数 | 单位 |
| --- | ---: | ---: | --- |
| P.xtb_vfukui.r712.f_radical | 0.0017486326571219345 | 106147 | e |
| P.pm7_B.r56.K | 0.010644912246921068 | 798283 | eV |
| P.pm7_B.r56.EE | 0.41500602981211926 | 798283 | eV |
| P.pm7_anion.r194.value | 1.799213860910479 | 2000 | A^3 |
| P.pm7_cation.r265.z | 1.4406411399429198 | 2000 | Debye |
| P.pm7_B.r68.value | 0.006660906293392953 | 106325 | e |
| P.pm7_B.r56.EN | 1.2314791587397846 | 798283 | eV |
| P.pm7_B.r43.value | 1.7998537285449205 | 2000 | A^3 |
| P.xtb_ALPB_water.r498.value | 0.0007364176031509973 | 2000 | Eh |
| P.pm7_water.r398.value | 0.022768849605305418 | 2000 | eV |
| P.xtb_fod.r538.value | 0.01304713881441849 | 2000 | e |
| P.pm7_water.r408.value | 0.06204160261154175 | 2000 | eV |
| P.xtb_ALPB_octanol.r459.value | 0.0004366189030088288 | 2000 | Eh |
| P.pm7_B.r61.value | 0.06230116963386536 | 2000 | eV |
| P.pm7_B.r73.value.sigma | 0.08195180988042428 | 599051 | bond-order population |
| P.pm7_anion.r190.p | 0.014845538974480996 | 106325 | e |
| P.pm7_B.r52.x | 0.23235288201015647 | 2000 | Debye |
| P.pm7_B.r64.value | 0.009052079489818326 | 106325 | e |
| P.pm7_octanol.r332.y | 0.21741327017522416 | 2000 | Debye |
| P.pm7_anion.r196.y | 1.4000565256240078 | 2000 | Debye |
| P.xtb_vipea.r751.value | 0.06137800781833629 | 1999 | eV |
| P.pm7_B.r55.electron_nuclear | 1.5659606739974656 | 106325 | eV |
| P.pm7_B.r52.z | 0.16131046547907682 | 2000 | Debye |
| P.pm7_B.r55.total | 0.7574344856106139 | 106325 | eV |
| P.pm7_B.r83.value | 0.06879805179080421 | 2000 | eV |
| P.xtb_singlepoint.r670.value | 0.003123453995249367 | 2000 | Eh |
| P.pm7_water.r410.value | 0.04967109407171665 | 2000 | eV |
| P.xtb_singlepoint.r669.x | 0.23972199329530122 | 2000 | Debye |
| P.pm7_water.r393.p | 0.008019171397692452 | 106325 | e |
| P.pm7_anion.r196.x | 2.94205137312827 | 2000 | Debye |
| P.pm7_B.r39.s | 0.0030610294390251685 | 106325 | e |
| P.xtb_singlepoint.r671.value | 0.06294518280029297 | 2000 | eV |
| P.pm7_B.r46.value | 0.010243078529965734 | 106325 | e |
| P.pm7_B.r48.value | 0.4010825760102881 | 2000 | kcal/mol |
| P.pm7_B.r52.y | 0.17546590662823291 | 2000 | Debye |
| P.pm7_B.r53.value | 0.1771822488833466 | 2000 | kcal/mol |
| P.pm7_B.r42.value | 2.0501983506869297 | 2000 | A^2 |
| P.pm7_B.r39.p | 0.007676601511133494 | 106325 | e |
| P.pm7_water.r399.z | 0.20503281186771347 | 2000 | Debye |
| P.pm7_water.r396.value | 2.0490904132657746 | 2000 | A^2 |
| P.xtb_vipea.r752.value | 0.04281228730057167 | 1999 | eV |
| P.pm7_cation.r273.value | 3.151181447819398 | 2000 | kcal/mol |
| P.pm7_water.r399.y | 0.23060608854563908 | 2000 | Debye |
| P.pm7_octanol.r332.x | 0.2766259222957306 | 2000 | Debye |
| P.xtb_singlepoint.r667.value | 0.027646655879411983 | 106325 | bohr^3 |
| P.pm7_B.r56.J | 0.024121520689246802 | 798283 | eV |
| P.pm7_anion.r196.z | 1.1917011665661121 | 2000 | Debye |
| P.pm7_octanol.r331.value | 0.018047665860012205 | 2000 | eV |
| P.pm7_water.r393.s | 0.0029429769415085156 | 106325 | e |
| P.pm7_octanol.r343.value | 0.04778717163984402 | 2000 | eV |
| P.xtb_singlepoint.r668.value | 0.0036319669482030906 | 106325 | e |
| P.pm7_octanol.r332.z | 0.19576962934830225 | 2000 | Debye |
| P.pm7_B.r62.value | 0.08135714375743838 | 2000 | kcal/mol |
| P.pm7_octanol.r329.value | 2.0483402610328953 | 2000 | A^2 |
| P.xtb_ALPB_octanol.r460.value | 0.0031268605893578715 | 2000 | Eh |
| P.pm7_B.r65.value | 0.0030362123341017783 | 797785 | e |
| P.pm7_octanol.r326.s | 0.0028823639358208373 | 106325 | e |
| P.pm7_B.r82.De | 0.03561870008002431 | 54838 | 1/eV (source-dimensional inference) |
| P.xtb_singlepoint.r672.value | 0.08415572077129037 | 2000 | eV |
| P.pm7_anion.r210.value | 0.01461852349736399 | 106325 | e |
| P.pm7_B.r60.value | 1.6269168566043921 | 2000 | kcal/mol |
| P.pm7_cation.r263.value | 1.8001595493720701 | 2000 | A^3 |
| P.pm7_water.r397.value | 1.798859375894455 | 2000 | A^3 |
| P.pm7_B.r82.charge_density_q_minus_Z | 0.30320376730251936 | 54838 | e |
| P.pm7_B.r56.C | 0.024348649775836312 | 798283 | eV |
| P.pm7_B.r73.value.pi | 0.030526759338495243 | 197626 | bond-order population |
| P.pm7_B.r56.total | 0.03967392823611864 | 798283 | eV |
| P.xtb_vfukui.r712.f_plus | 0.0024052826813329184 | 106147 | e |
| P.pm7_B.r84.value | 0.006439559714754357 | 106325 | bond-order population |
| P.pm7_cation.r259.s | 0.006279725363583613 | 106325 | e |
| P.xtb_ALPB_water.r499.value | 0.0031844632435241815 | 2000 | Eh |
| P.pm7_B.r41.value | 277.9123956014003 | 2000 | eV |
| P.pm7_B.r56.NN | 0.4098041019239676 | 798283 | eV |
| P.pm7_B.r63.value | 0.05461012775966083 | 2000 | eV |
| P.pm7_B.r55.electron_electron | 0.5675926609900371 | 106325 | eV |
| P.xtb_singlepoint.r669.y | 0.17208241927394557 | 2000 | Debye |
| P.pm7_water.r399.x | 0.2888164831028553 | 2000 | Debye |
| P.pm7_anion.r190.s | 0.005968973629619833 | 106325 | e |
| P.xtb_singlepoint.r669.z | 0.15761875325918664 | 2000 | Debye |
| P.xtb_singlepoint.r666.value | 0.1628749500441041 | 106325 | Eh bohr^6 |
| P.pm7_octanol.r326.p | 0.007917141510498207 | 106325 | e |
| P.pm7_B.r82.Dn | 0.038481558939651474 | 54838 | 1/eV (source-dimensional inference) |
| P.xtb_vfukui.r712.f_minus | 0.002399864057437415 | 106147 | e |
| P.pm7_octanol.r346.value | 0.00661571237741756 | 106325 | e |
| P.xtb_singlepoint.r677.value | 0.004863313074368747 | 118841 | bond-order population |
| P.pm7_cation.r259.p | 0.01574286148565224 | 106325 | e |
| P.pm7_cation.r265.x | 3.516998252723599 | 2000 | Debye |
| P.pm7_B.r50.value | 0.11308833122253419 | 2000 | eV |
| P.pm7_octanol.r340.value | 1.6215339009547844 | 2000 | kcal/mol |
| P.pm7_water.r407.value | 1.6263271250348088 | 2000 | kcal/mol |
| P.pm7_B.r49.value | 0.1272434602403955 | 2000 | eV |
| P.pm7_B.r47.value | 0.3396050150874475 | 2000 | kcal/mol |
| P.pm7_water.r413.value | 0.006708452920607399 | 106325 | e |
| P.pm7_B.r58.value | 0.08336924668144823 | 318975 | kcal mol^-1 A^-1 |
| P.pm7_B.r54.value | 277.97134052152023 | 2000 | eV |
| P.pm7_cation.r279.value | 0.0162631737315436 | 106325 | e |
| P.pm7_anion.r193.value | 2.0505076849296016 | 2000 | A^2 |
| P.pm7_B.r44.value | 0.01377619503423138 | 106325 | e |
| P.pm7_octanol.r341.value | 0.05950307536125183 | 2000 | eV |
| P.pm7_cation.r265.y | 1.6122936169215536 | 2000 | Debye |
| P.pm7_B.r40.value | 0.0029681622122826588 | 798283 | bond-order population |
| P.xtb_fod.r537.value | 0.0006636155294510683 | 106325 | e |
| P.pm7_anion.r204.value | 3.553459160613382 | 2000 | kcal/mol |
| P.pm7_octanol.r330.value | 1.7991376808828985 | 2000 | A^3 |
| P.pm7_cation.r262.value | 2.0492011702652038 | 2000 | A^2 |
| P.pm7_B.r45.value | 0.011776774420717038 | 106325 | e |
| P.xtb_perturbed_gradient.r623.value | 0.04152092019407884 | 2000 | Eh |
| P.xtb_perturbed_gradient.r625.value | 0.005860896934216771 | 318975 | Eh bohr^-1 |
| P.xtb_perturbed_gradient.r624.value | 0.31136977655269066 | 318975 | eV A^-1 |
