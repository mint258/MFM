# T1 seed 0 生产者描述性字段附表

运行：`p_heads_T1_seed0_sbatch`。直接转录既有3M生产者记录，没有重新评价、拟合、bootstrap或计算MAE。

CYP来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/scores.csv`。CYP不进入七任务主分。

| 读出 | 任务 | 原误差 | 随机参考误差 | score | 排除主分 |
| --- | --- | ---: | ---: | ---: | --- |
| R1 | cyp.3A4 | 0.4 | 0.6857142857142857 | 0.41666666666666663 | True |
| R1 | cyp.2D6 | 0.5384615384615384 | 0.6153846153846154 | 0.12500000000000008 | True |
| R3 | cyp.3A4 | 0.34285714285714286 | 0.6 | 0.42857142857142855 | True |
| R3 | cyp.2D6 | 0.6538461538461539 | 0.6153846153846154 | -0.06249999999999996 | True |

逐字段原单位VAL来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/runtime/results/p_recipe/training/p_heads_T1_seed0_sbatch/VAL_original_units_3000000.csv`。

| 字段 | 原单位MAE | 观察数 | 单位 |
| --- | ---: | ---: | --- |
| P.pm7_B.r83.value | 0.06966065232685373 | 2000 | eV |
| P.pm7_B.r50.value | 0.11386636304855347 | 2000 | eV |
| P.pm7_B.r65.value | 0.0029207999962784555 | 797785 | e |
| P.pm7_B.r60.value | 1.6376184151191695 | 2000 | kcal/mol |
| P.xtb_vfukui.r712.f_radical | 0.0017287819082992927 | 106147 | e |
| P.pm7_octanol.r330.value | 1.775742709722783 | 2000 | A^3 |
| P.pm7_anion.r196.z | 1.1818771731999005 | 2000 | Debye |
| P.pm7_B.r61.value | 0.06103894996643067 | 2000 | eV |
| P.pm7_B.r47.value | 0.33523290906893793 | 2000 | kcal/mol |
| P.pm7_cation.r263.value | 1.7753557856077173 | 2000 | A^3 |
| P.pm7_water.r407.value | 1.6314898701235128 | 2000 | kcal/mol |
| P.xtb_fod.r537.value | 0.0006350679170007081 | 106325 | e |
| P.pm7_B.r82.charge_density_q_minus_Z | 0.30362741627044715 | 54838 | e |
| P.xtb_vipea.r752.value | 0.040921694281818036 | 1999 | eV |
| P.pm7_B.r46.value | 0.010026090283981494 | 106325 | e |
| P.pm7_cation.r265.z | 1.3907037258406636 | 2000 | Debye |
| P.pm7_water.r413.value | 0.006409962986871406 | 106325 | e |
| P.pm7_B.r55.electron_electron | 0.4923213846894284 | 106325 | eV |
| P.pm7_B.r63.value | 0.05377627050425508 | 2000 | eV |
| P.xtb_singlepoint.r669.x | 0.23517688860889757 | 2000 | Debye |
| P.pm7_octanol.r329.value | 1.9524259956355012 | 2000 | A^2 |
| P.pm7_B.r55.electron_nuclear | 1.661711084772328 | 106325 | eV |
| P.pm7_octanol.r332.z | 0.18835266954894178 | 2000 | Debye |
| P.xtb_singlepoint.r677.value | 0.004569364142587331 | 118841 | bond-order population |
| P.pm7_B.r39.s | 0.0029472087137620085 | 106325 | e |
| P.pm7_anion.r210.value | 0.014158269565659222 | 106325 | e |
| P.pm7_anion.r196.x | 2.892511288833295 | 2000 | Debye |
| P.xtb_singlepoint.r670.value | 0.002979191984421394 | 2000 | Eh |
| P.pm7_octanol.r343.value | 0.04695529159553553 | 2000 | eV |
| P.pm7_B.r52.z | 0.1548684259845577 | 2000 | Debye |
| P.pm7_B.r64.value | 0.008738883296279469 | 106325 | e |
| P.pm7_B.r52.y | 0.16943863822537242 | 2000 | Debye |
| P.xtb_vipea.r751.value | 0.058768462882914846 | 1999 | eV |
| P.pm7_B.r52.x | 0.22129132474282961 | 2000 | Debye |
| P.pm7_B.r56.EN | 1.1330240178719775 | 798283 | eV |
| P.pm7_water.r410.value | 0.048476325439885844 | 2000 | eV |
| P.pm7_octanol.r332.x | 0.25844623251911253 | 2000 | Debye |
| P.pm7_anion.r190.p | 0.014131000031660844 | 106325 | e |
| P.pm7_B.r82.Dn | 0.03871675144636181 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_anion.r193.value | 1.9549034715247144 | 2000 | A^2 |
| P.pm7_cation.r259.s | 0.00626502251473702 | 106325 | e |
| P.pm7_cation.r259.p | 0.01483050657300046 | 106325 | e |
| P.pm7_anion.r194.value | 1.7761560820967839 | 2000 | A^3 |
| P.xtb_vfukui.r712.f_minus | 0.0023406917697309662 | 106147 | e |
| P.pm7_octanol.r326.p | 0.007242595238802491 | 106325 | e |
| P.pm7_B.r56.NN | 0.5444312005480212 | 798283 | eV |
| P.pm7_B.r82.De | 0.03573790334340828 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_cation.r262.value | 1.9539470901798421 | 2000 | A^2 |
| P.pm7_B.r56.EE | 0.4729325054293146 | 798283 | eV |
| P.xtb_singlepoint.r669.y | 0.1680354593831944 | 2000 | Debye |
| P.pm7_B.r53.value | 0.17075914333820238 | 2000 | kcal/mol |
| P.pm7_water.r399.y | 0.2223501588026993 | 2000 | Debye |
| P.xtb_ALPB_octanol.r460.value | 0.0029881826766254955 | 2000 | Eh |
| P.xtb_ALPB_octanol.r459.value | 0.0004013930441466541 | 2000 | Eh |
| P.xtb_ALPB_water.r498.value | 0.0006901649534733094 | 2000 | Eh |
| P.xtb_singlepoint.r669.z | 0.153506664489978 | 2000 | Debye |
| P.pm7_B.r68.value | 0.006326443982399423 | 106325 | e |
| P.xtb_fod.r538.value | 0.012381735563204158 | 2000 | e |
| P.pm7_octanol.r326.s | 0.0028063613348726997 | 106325 | e |
| P.pm7_B.r62.value | 0.08637264880345391 | 2000 | kcal/mol |
| P.pm7_cation.r273.value | 3.1619245576144035 | 2000 | kcal/mol |
| P.pm7_B.r45.value | 0.011379505808856863 | 106325 | e |
| P.pm7_octanol.r341.value | 0.057118067741394045 | 2000 | eV |
| P.pm7_B.r56.C | 0.02382828074689719 | 798283 | eV |
| P.pm7_B.r84.value | 0.005747380981494644 | 106325 | bond-order population |
| P.pm7_water.r393.p | 0.007513641691504998 | 106325 | e |
| P.pm7_B.r42.value | 1.9547480903337329 | 2000 | A^2 |
| P.pm7_water.r396.value | 1.9528312424280456 | 2000 | A^2 |
| P.pm7_water.r399.x | 0.27504941931937354 | 2000 | Debye |
| P.pm7_B.r56.J | 0.025180399439063427 | 798283 | eV |
| P.pm7_octanol.r340.value | 1.6260762182613566 | 2000 | kcal/mol |
| P.pm7_octanol.r346.value | 0.006329757189578963 | 106325 | e |
| P.pm7_B.r49.value | 0.12364595421092235 | 2000 | eV |
| P.pm7_anion.r196.y | 1.4119480882348725 | 2000 | Debye |
| P.pm7_B.r41.value | 282.1083816942323 | 2000 | eV |
| P.pm7_B.r56.K | 0.01076423335311645 | 798283 | eV |
| P.pm7_water.r408.value | 0.059075188398361206 | 2000 | eV |
| P.pm7_anion.r204.value | 3.5336759697323994 | 2000 | kcal/mol |
| P.pm7_anion.r190.s | 0.005812496657430943 | 106325 | e |
| P.xtb_ALPB_water.r499.value | 0.0030186136435463523 | 2000 | Eh |
| P.pm7_B.r44.value | 0.013445241889131623 | 106325 | e |
| P.pm7_B.r58.value | 0.08336667451974679 | 318975 | kcal mol^-1 A^-1 |
| P.pm7_octanol.r331.value | 0.017657223569171782 | 2000 | eV |
| P.pm7_cation.r265.x | 3.374169554723194 | 2000 | Debye |
| P.pm7_B.r55.total | 0.672812879725173 | 106325 | eV |
| P.pm7_water.r393.s | 0.0028633901990499882 | 106325 | e |
| P.pm7_B.r73.value.sigma | 0.08137754238770564 | 599051 | bond-order population |
| P.xtb_vfukui.r712.f_plus | 0.002334937004653058 | 106147 | e |
| P.pm7_B.r56.total | 0.03777247874823047 | 798283 | eV |
| P.pm7_B.r54.value | 282.14144809268095 | 2000 | eV |
| P.pm7_B.r39.p | 0.007276019620006852 | 106325 | e |
| P.xtb_singlepoint.r668.value | 0.003507791137506554 | 106325 | e |
| P.pm7_water.r398.value | 0.022237405853890613 | 2000 | eV |
| P.pm7_B.r73.value.pi | 0.030794502058958326 | 197626 | bond-order population |
| P.pm7_octanol.r332.y | 0.2094463542008307 | 2000 | Debye |
| P.xtb_singlepoint.r671.value | 0.0633243227005005 | 2000 | eV |
| P.pm7_water.r397.value | 1.7751709142271088 | 2000 | A^3 |
| P.xtb_singlepoint.r667.value | 0.027036127300787163 | 106325 | bohr^3 |
| P.pm7_water.r399.z | 0.19943271862430265 | 2000 | Debye |
| P.pm7_B.r40.value | 0.002790118618888868 | 798283 | bond-order population |
| P.xtb_singlepoint.r666.value | 0.21078986365879784 | 106325 | Eh bohr^6 |
| P.pm7_B.r48.value | 0.39578006554173567 | 2000 | kcal/mol |
| P.pm7_cation.r279.value | 0.015852903973019156 | 106325 | e |
| P.pm7_B.r43.value | 1.7751428481740477 | 2000 | A^3 |
| P.pm7_cation.r265.y | 1.5347436659782252 | 2000 | Debye |
| P.xtb_singlepoint.r672.value | 0.08024241597112268 | 2000 | eV |
| P.xtb_perturbed_gradient.r623.value | 0.03800042043608759 | 2000 | Eh |
| P.xtb_perturbed_gradient.r625.value | 0.005812992631933731 | 318975 | Eh bohr^-1 |
| P.xtb_perturbed_gradient.r624.value | 0.3038480897663591 | 318975 | eV A^-1 |
