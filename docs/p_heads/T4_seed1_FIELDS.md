# T4 seed 1 生产者描述性字段附表

运行：`p_heads_T4_seed1`。直接转录既有3M生产者记录，没有重新评价、拟合、bootstrap或计算MAE。

CYP来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/scores.csv`。CYP不进入七任务主分。

| 读出 | 任务 | 原误差 | 随机参考误差 | score | 排除主分 |
| --- | --- | ---: | ---: | ---: | --- |
| R1 | cyp.3A4 | 0.5428571428571429 | 0.6857142857142857 | 0.20833333333333323 | True |
| R1 | cyp.2D6 | 0.5 | 0.6153846153846154 | 0.18750000000000006 | True |
| R3 | cyp.3A4 | 0.5142857142857142 | 0.6 | 0.1428571428571429 | True |
| R3 | cyp.2D6 | 0.5 | 0.6153846153846154 | 0.18750000000000006 | True |

逐字段原单位VAL来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/runtime/results/p_recipe/training/p_heads_T4_seed1/VAL_original_units_3000000.csv`。

| 字段 | 原单位MAE | 观察数 | 单位 |
| --- | ---: | ---: | --- |
| P.xtb_vfukui.r712.f_radical | 0.0019581473019596074 | 106147 | e |
| P.pm7_octanol.r346.value | 0.00676862958291807 | 106325 | e |
| P.xtb_singlepoint.r666.value | 0.1775353259202763 | 106325 | Eh bohr^6 |
| P.pm7_B.r42.value | 2.063869128916654 | 2000 | A^2 |
| P.xtb_fod.r537.value | 0.0007390635573695606 | 106325 | e |
| P.pm7_octanol.r332.y | 0.21745325980265626 | 2000 | Debye |
| P.pm7_B.r61.value | 0.06342823457717896 | 2000 | eV |
| P.pm7_cation.r265.x | 3.619263510642806 | 2000 | Debye |
| P.pm7_B.r64.value | 0.009510847078502848 | 106325 | e |
| P.pm7_B.r73.value.sigma | 0.086282443875999 | 599051 | bond-order population |
| P.pm7_water.r399.x | 0.286888468268211 | 2000 | Debye |
| P.pm7_water.r397.value | 1.8378099509037977 | 2000 | A^3 |
| P.pm7_B.r58.value | 0.0833661322994053 | 318975 | kcal mol^-1 A^-1 |
| P.pm7_octanol.r331.value | 0.018811184146836024 | 2000 | eV |
| P.xtb_ALPB_octanol.r459.value | 0.00047540364256300584 | 2000 | Eh |
| P.pm7_octanol.r343.value | 0.053096533223048026 | 2000 | eV |
| P.xtb_vipea.r751.value | 0.06437066651601438 | 1999 | eV |
| P.pm7_water.r398.value | 0.02393415905578194 | 2000 | eV |
| P.pm7_octanol.r326.p | 0.008491147697574527 | 106325 | e |
| P.pm7_water.r396.value | 2.063398282595349 | 2000 | A^2 |
| P.pm7_B.r45.value | 0.013272684673049673 | 106325 | e |
| P.pm7_B.r49.value | 0.13464786866577924 | 2000 | eV |
| P.xtb_vipea.r752.value | 0.04479706221786125 | 1999 | eV |
| P.pm7_anion.r210.value | 0.015903678605473415 | 106325 | e |
| P.pm7_anion.r196.x | 3.10241595453264 | 2000 | Debye |
| P.pm7_B.r54.value | 308.01799444420345 | 2000 | eV |
| P.pm7_B.r60.value | 1.8009081387250472 | 2000 | kcal/mol |
| P.pm7_B.r56.NN | 0.3433014970955335 | 798283 | eV |
| P.pm7_B.r52.y | 0.17293656984512926 | 2000 | Debye |
| P.pm7_anion.r190.p | 0.016226464091694384 | 106325 | e |
| P.pm7_B.r55.electron_nuclear | 1.6456433153382308 | 106325 | eV |
| P.pm7_B.r68.value | 0.006879850096779214 | 106325 | e |
| P.pm7_octanol.r330.value | 1.838060208528317 | 2000 | A^3 |
| P.pm7_B.r56.J | 0.02244960664572461 | 798283 | eV |
| P.pm7_cation.r273.value | 3.2528290152747776 | 2000 | kcal/mol |
| P.pm7_B.r56.EE | 0.3931580328812979 | 798283 | eV |
| P.pm7_B.r48.value | 0.41292875370581095 | 2000 | kcal/mol |
| P.pm7_B.r40.value | 0.0027797726854327308 | 798283 | bond-order population |
| P.pm7_octanol.r332.x | 0.27676598908007144 | 2000 | Debye |
| P.pm7_octanol.r329.value | 2.062739751158418 | 2000 | A^2 |
| P.pm7_B.r55.total | 0.7088318578019132 | 106325 | eV |
| P.xtb_vfukui.r712.f_minus | 0.002698453936549333 | 106147 | e |
| P.pm7_B.r56.EN | 1.31516869954349 | 798283 | eV |
| P.pm7_cation.r259.s | 0.007028177587839679 | 106325 | e |
| P.xtb_ALPB_water.r499.value | 0.0034048405687549634 | 2000 | Eh |
| P.pm7_anion.r196.y | 1.4760419614602578 | 2000 | Debye |
| P.pm7_B.r83.value | 0.07645914227063276 | 2000 | eV |
| P.xtb_singlepoint.r670.value | 0.003325931744154943 | 2000 | Eh |
| P.pm7_octanol.r326.s | 0.0032438358945507963 | 106325 | e |
| P.pm7_B.r62.value | 0.09010481951174715 | 2000 | kcal/mol |
| P.pm7_B.r82.Dn | 0.045509808699693566 | 54838 | 1/eV (source-dimensional inference) |
| P.xtb_singlepoint.r669.x | 0.24140208109951344 | 2000 | Debye |
| P.pm7_cation.r279.value | 0.017605572215487576 | 106325 | e |
| P.pm7_octanol.r340.value | 1.7911062444038754 | 2000 | kcal/mol |
| P.pm7_B.r52.z | 0.16143449910338314 | 2000 | Debye |
| P.pm7_B.r47.value | 0.3498376285362184 | 2000 | kcal/mol |
| P.pm7_B.r39.p | 0.008891455802060058 | 106325 | e |
| P.xtb_singlepoint.r669.z | 0.16557068775093647 | 2000 | Debye |
| P.pm7_B.r50.value | 0.11374445366859436 | 2000 | eV |
| P.pm7_water.r399.z | 0.2062567364271381 | 2000 | Debye |
| P.pm7_anion.r194.value | 1.8387655767281954 | 2000 | A^3 |
| P.pm7_cation.r262.value | 2.0631550483989485 | 2000 | A^2 |
| P.pm7_cation.r265.z | 1.4017718458015005 | 2000 | Debye |
| P.pm7_cation.r259.p | 0.016710350912878043 | 106325 | e |
| P.xtb_singlepoint.r669.y | 0.1800152558262562 | 2000 | Debye |
| P.xtb_singlepoint.r667.value | 0.02963661952773291 | 106325 | bohr^3 |
| P.pm7_anion.r196.z | 1.2635707960739964 | 2000 | Debye |
| P.pm7_B.r56.K | 0.010666107757622698 | 798283 | eV |
| P.pm7_B.r73.value.pi | 0.033004392173917894 | 197626 | bond-order population |
| P.pm7_B.r56.C | 0.024192363296432453 | 798283 | eV |
| P.pm7_B.r46.value | 0.01132478885983056 | 106325 | e |
| P.pm7_B.r63.value | 0.059603954373305894 | 2000 | eV |
| P.pm7_cation.r265.y | 1.5981717005275131 | 2000 | Debye |
| P.pm7_B.r44.value | 0.015437378328285416 | 106325 | e |
| P.pm7_B.r41.value | 308.02117426957705 | 2000 | eV |
| P.pm7_B.r82.De | 0.04074214026735331 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_B.r53.value | 0.18972220475147425 | 2000 | kcal/mol |
| P.pm7_B.r39.s | 0.003293429469322278 | 106325 | e |
| P.pm7_water.r399.y | 0.22953068709140642 | 2000 | Debye |
| P.pm7_anion.r193.value | 2.063887457503103 | 2000 | A^2 |
| P.pm7_octanol.r332.z | 0.19707369644090067 | 2000 | Debye |
| P.pm7_B.r43.value | 1.8383320645778736 | 2000 | A^3 |
| P.pm7_B.r55.electron_electron | 0.5643775092067086 | 106325 | eV |
| P.pm7_anion.r190.s | 0.006671918773550217 | 106325 | e |
| P.pm7_B.r56.total | 0.03599230706806329 | 798283 | eV |
| P.xtb_singlepoint.r672.value | 0.08908630856033414 | 2000 | eV |
| P.xtb_singlepoint.r677.value | 0.0048189693450533515 | 118841 | bond-order population |
| P.pm7_B.r84.value | 0.006633477404401803 | 106325 | bond-order population |
| P.pm7_B.r52.x | 0.23390927757544705 | 2000 | Debye |
| P.pm7_water.r407.value | 1.7962186396207862 | 2000 | kcal/mol |
| P.xtb_vfukui.r712.f_plus | 0.0027652669702805856 | 106147 | e |
| P.pm7_cation.r263.value | 1.8383128323642097 | 2000 | A^3 |
| P.pm7_B.r82.charge_density_q_minus_Z | 0.3481895002806882 | 54838 | e |
| P.xtb_singlepoint.r668.value | 0.003841857327353987 | 106325 | e |
| P.pm7_octanol.r341.value | 0.06018906903266907 | 2000 | eV |
| P.pm7_anion.r204.value | 3.83036119775415 | 2000 | kcal/mol |
| P.pm7_water.r410.value | 0.05497560063343553 | 2000 | eV |
| P.xtb_ALPB_water.r498.value | 0.00077421529780105 | 2000 | Eh |
| P.pm7_water.r393.s | 0.0033782813107858063 | 106325 | e |
| P.pm7_water.r408.value | 0.0625908968448639 | 2000 | eV |
| P.pm7_water.r393.p | 0.008877162796635923 | 106325 | e |
| P.xtb_ALPB_octanol.r460.value | 0.0033548863441053706 | 2000 | Eh |
| P.xtb_fod.r538.value | 0.0141052623803339 | 2000 | e |
| P.pm7_B.r65.value | 0.0031320565416410903 | 797785 | e |
| P.pm7_water.r413.value | 0.006829182162775705 | 106325 | e |
| P.xtb_singlepoint.r671.value | 0.06635089874267579 | 2000 | eV |
| P.xtb_perturbed_gradient.r625.value | 0.005896638995439912 | 318975 | Eh bohr^-1 |
| P.xtb_perturbed_gradient.r624.value | 0.31023609722308376 | 318975 | eV A^-1 |
| P.xtb_perturbed_gradient.r623.value | 0.041512179711072184 | 2000 | Eh |
