# T5 seed 0 生产者描述性字段附表

运行：`p_heads_T5_seed0`。直接转录既有3M生产者记录，没有重新评价、拟合、bootstrap或计算MAE。

CYP来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/scores.csv`。CYP不进入七任务主分。

| 读出 | 任务 | 原误差 | 随机参考误差 | score | 排除主分 |
| --- | --- | ---: | ---: | ---: | --- |
| R1 | cyp.3A4 | 0.4285714285714286 | 0.6857142857142857 | 0.37499999999999994 | True |
| R1 | cyp.2D6 | 0.6538461538461539 | 0.6153846153846154 | -0.06249999999999996 | True |
| R3 | cyp.3A4 | 0.5142857142857142 | 0.6 | 0.1428571428571429 | True |
| R3 | cyp.2D6 | 0.5384615384615384 | 0.6153846153846154 | 0.12500000000000008 | True |

逐字段原单位VAL来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/runtime/results/p_recipe/training/p_heads_T5_seed0/VAL_original_units_3000000.csv`。

| 字段 | 原单位MAE | 观察数 | 单位 |
| --- | ---: | ---: | --- |
| P.xtb_ALPB_water.r499.value | 0.003778213394201856 | 2000 | Eh |
| P.pm7_anion.r193.value | 2.267420975245056 | 2000 | A^2 |
| P.pm7_B.r61.value | 0.07040310955047607 | 2000 | eV |
| P.pm7_B.r54.value | 2466.03627635416 | 2000 | eV |
| P.xtb_ALPB_octanol.r459.value | 0.0005237199485244991 | 2000 | Eh |
| P.xtb_vfukui.r712.f_minus | 0.002896125939127816 | 106147 | e |
| P.pm7_B.r82.De | 0.04538786235174932 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_B.r42.value | 2.2668036794639423 | 2000 | A^2 |
| P.pm7_B.r58.value | 0.08337012256839565 | 318975 | kcal mol^-1 A^-1 |
| P.pm7_water.r410.value | 0.061454019341283125 | 2000 | eV |
| P.xtb_singlepoint.r666.value | 0.30344806882148345 | 106325 | Eh bohr^6 |
| P.pm7_cation.r265.y | 1.7052758097941114 | 2000 | Debye |
| P.pm7_water.r397.value | 1.927760257157954 | 2000 | A^3 |
| P.pm7_anion.r190.p | 0.017048146082265726 | 106325 | e |
| P.pm7_B.r82.Dn | 0.05066867564774316 | 54838 | 1/eV (source-dimensional inference) |
| P.xtb_singlepoint.r667.value | 0.029004552878409647 | 106325 | bohr^3 |
| P.pm7_anion.r204.value | 4.290264801523946 | 2000 | kcal/mol |
| P.pm7_B.r52.z | 0.17197560244872512 | 2000 | Debye |
| P.pm7_B.r39.s | 0.003296604274778458 | 106325 | e |
| P.xtb_singlepoint.r677.value | 0.004663248720608104 | 118841 | bond-order population |
| P.pm7_B.r60.value | 1.991509234996264 | 2000 | kcal/mol |
| P.pm7_B.r43.value | 1.9271607897159369 | 2000 | A^3 |
| P.pm7_cation.r262.value | 2.2670627409283357 | 2000 | A^2 |
| P.pm7_B.r41.value | 2466.0650799992313 | 2000 | eV |
| P.pm7_B.r56.K | 0.011072944050734177 | 798283 | eV |
| P.pm7_octanol.r329.value | 2.2667427485136966 | 2000 | A^2 |
| P.pm7_B.r56.total | 0.03715654145454552 | 798283 | eV |
| P.pm7_octanol.r332.x | 0.302029141232837 | 2000 | Debye |
| P.pm7_octanol.r330.value | 1.9285210022284667 | 2000 | A^3 |
| P.pm7_water.r399.y | 0.24329213035153224 | 2000 | Debye |
| P.pm7_B.r82.charge_density_q_minus_Z | 0.39350776038020824 | 54838 | e |
| P.pm7_cation.r273.value | 3.6200579304157947 | 2000 | kcal/mol |
| P.pm7_B.r68.value | 0.007356954232231373 | 106325 | e |
| P.pm7_B.r44.value | 0.016416426162800885 | 106325 | e |
| P.pm7_B.r52.y | 0.18625405397493158 | 2000 | Debye |
| P.pm7_B.r73.value.sigma | 0.09135566918922997 | 599051 | bond-order population |
| P.pm7_B.r40.value | 0.0027894938963449606 | 798283 | bond-order population |
| P.pm7_water.r399.x | 0.31534420172160027 | 2000 | Debye |
| P.pm7_octanol.r331.value | 0.021304813095945837 | 2000 | eV |
| P.pm7_B.r47.value | 0.39608425370346806 | 2000 | kcal/mol |
| P.pm7_B.r65.value | 0.0029627695819887984 | 797785 | e |
| P.xtb_vfukui.r712.f_plus | 0.0029952572648249995 | 106147 | e |
| P.pm7_anion.r196.x | 3.476782537031526 | 2000 | Debye |
| P.pm7_octanol.r340.value | 1.9907258590789705 | 2000 | kcal/mol |
| P.pm7_anion.r194.value | 1.927822582939277 | 2000 | A^3 |
| P.pm7_B.r73.value.pi | 0.03535851091091881 | 197626 | bond-order population |
| P.xtb_fod.r538.value | 0.01509788507920023 | 2000 | e |
| P.pm7_anion.r196.z | 1.3912997803544858 | 2000 | Debye |
| P.pm7_B.r39.p | 0.008593402868603191 | 106325 | e |
| P.pm7_B.r55.electron_nuclear | 1.7223830853272628 | 106325 | eV |
| P.pm7_octanol.r326.s | 0.0032358813554910445 | 106325 | e |
| P.xtb_ALPB_octanol.r460.value | 0.0037703712289705003 | 2000 | Eh |
| P.pm7_anion.r196.y | 1.642524006856489 | 2000 | Debye |
| P.pm7_anion.r210.value | 0.01736725685800381 | 106325 | e |
| P.pm7_water.r393.s | 0.0033556553624025545 | 106325 | e |
| P.pm7_B.r84.value | 0.005433828085695971 | 106325 | bond-order population |
| P.pm7_cation.r265.z | 1.5546076570621226 | 2000 | Debye |
| P.pm7_B.r48.value | 0.46721436944155664 | 2000 | kcal/mol |
| P.pm7_water.r399.z | 0.2240327941910946 | 2000 | Debye |
| P.pm7_octanol.r332.z | 0.21191917613730765 | 2000 | Debye |
| P.xtb_ALPB_water.r498.value | 0.0008700662478967193 | 2000 | Eh |
| P.pm7_octanol.r341.value | 0.06426734066009522 | 2000 | eV |
| P.xtb_singlepoint.r669.z | 0.17745976552332285 | 2000 | Debye |
| P.pm7_B.r52.x | 0.25384229091111776 | 2000 | Debye |
| P.pm7_cation.r259.p | 0.017317685724327823 | 106325 | e |
| P.pm7_B.r46.value | 0.012193289810044913 | 106325 | e |
| P.xtb_singlepoint.r668.value | 0.003940019882699183 | 106325 | e |
| P.xtb_singlepoint.r672.value | 0.10336319166328758 | 2000 | eV |
| P.pm7_B.r55.electron_electron | 0.5359086034075389 | 106325 | eV |
| P.pm7_B.r45.value | 0.01457552156119746 | 106325 | e |
| P.pm7_B.r56.J | 0.023772247414601783 | 798283 | eV |
| P.xtb_vipea.r751.value | 0.07898774071790608 | 1999 | eV |
| P.pm7_B.r50.value | 0.12474375700950623 | 2000 | eV |
| P.xtb_singlepoint.r669.y | 0.1919817575109555 | 2000 | Debye |
| P.pm7_cation.r259.s | 0.007345162893838387 | 106325 | e |
| P.pm7_B.r56.EE | 0.3713883206787951 | 798283 | eV |
| P.xtb_singlepoint.r671.value | 0.0778278636932373 | 2000 | eV |
| P.pm7_water.r398.value | 0.027240256730866604 | 2000 | eV |
| P.pm7_octanol.r332.y | 0.23045491341804153 | 2000 | Debye |
| P.pm7_water.r413.value | 0.0073709636695409335 | 106325 | e |
| P.pm7_B.r49.value | 0.1522188012470433 | 2000 | eV |
| P.pm7_cation.r263.value | 1.9277746878124964 | 2000 | A^3 |
| P.pm7_water.r393.p | 0.00817710209013349 | 106325 | e |
| P.pm7_B.r56.NN | 0.6002125467052748 | 798283 | eV |
| P.pm7_B.r56.EN | 0.963445919671377 | 798283 | eV |
| P.xtb_singlepoint.r669.x | 0.2782182131105219 | 2000 | Debye |
| P.pm7_cation.r265.x | 3.9196035179721656 | 2000 | Debye |
| P.pm7_B.r55.total | 0.8806508256462414 | 106325 | eV |
| P.pm7_octanol.r326.p | 0.008580625019801131 | 106325 | e |
| P.pm7_B.r53.value | 0.20005474104554188 | 2000 | kcal/mol |
| P.pm7_B.r83.value | 0.0849173139688615 | 2000 | eV |
| P.xtb_vipea.r752.value | 0.049295341449716555 | 1999 | eV |
| P.pm7_B.r63.value | 0.06967394449285348 | 2000 | eV |
| P.pm7_water.r407.value | 2.001324874601341 | 2000 | kcal/mol |
| P.xtb_singlepoint.r670.value | 0.003739572885012329 | 2000 | Eh |
| P.pm7_cation.r279.value | 0.018866713011601137 | 106325 | e |
| P.pm7_B.r62.value | 0.0998519725664668 | 2000 | kcal/mol |
| P.pm7_B.r56.C | 0.025358053582210497 | 798283 | eV |
| P.pm7_octanol.r343.value | 0.05938623734935391 | 2000 | eV |
| P.pm7_octanol.r346.value | 0.00728134667354177 | 106325 | e |
| P.xtb_vfukui.r712.f_radical | 0.0021321411446002278 | 106147 | e |
| P.pm7_water.r396.value | 2.2664231355908426 | 2000 | A^2 |
| P.pm7_water.r408.value | 0.06721287989616394 | 2000 | eV |
| P.pm7_B.r64.value | 0.010091026898074663 | 106325 | e |
| P.xtb_fod.r537.value | 0.0007756911492656558 | 106325 | e |
| P.pm7_anion.r190.s | 0.007006254599510909 | 106325 | e |
| P.xtb_perturbed_gradient.r625.value | 0.006380376355687064 | 318975 | Eh bohr^-1 |
| P.xtb_perturbed_gradient.r624.value | 0.3371927302077557 | 318975 | eV A^-1 |
| P.xtb_perturbed_gradient.r623.value | 0.039060270950395125 | 2000 | Eh |
