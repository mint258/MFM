# B3 seed 1 生产者描述性字段附表

运行：`p_heads_B3_seed1`。直接转录既有3M生产者记录，没有重新评价、拟合、bootstrap或计算MAE。

CYP来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/scores.csv`。CYP不进入七任务主分。

| 读出 | 任务 | 原误差 | 随机参考误差 | score | 排除主分 |
| --- | --- | ---: | ---: | ---: | --- |
| R1 | cyp.3A4 | 0.48571428571428577 | 0.6857142857142857 | 0.2916666666666666 | True |
| R1 | cyp.2D6 | 0.5769230769230769 | 0.6153846153846154 | 0.06250000000000014 | True |
| R3 | cyp.3A4 | 0.4285714285714286 | 0.6 | 0.28571428571428564 | True |
| R3 | cyp.2D6 | 0.5769230769230769 | 0.6153846153846154 | 0.06250000000000014 | True |

逐字段原单位VAL来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/runtime/results/p_recipe/training/p_heads_B3_seed1/VAL_original_units_3000000.csv`。

| 字段 | 原单位MAE | 观察数 | 单位 |
| --- | ---: | ---: | --- |
| P.pm7_octanol.r343.value | 0.053691454061299736 | 2000 | eV |
| P.pm7_octanol.r331.value | 0.01917377829454903 | 2000 | eV |
| P.pm7_cation.r279.value | 0.01762972921471628 | 106325 | e |
| P.pm7_B.r56.J | 0.022686367485766624 | 798283 | eV |
| P.pm7_B.r47.value | 0.35612397264013257 | 2000 | kcal/mol |
| P.xtb_singlepoint.r677.value | 0.004859165161592403 | 118841 | bond-order population |
| P.pm7_B.r41.value | 292.79063789567056 | 2000 | eV |
| P.pm7_B.r44.value | 0.015228226130579987 | 106325 | e |
| P.pm7_water.r407.value | 1.9108401461991331 | 2000 | kcal/mol |
| P.pm7_B.r52.y | 0.17649423652346014 | 2000 | Debye |
| P.pm7_water.r413.value | 0.006951905799530197 | 106325 | e |
| P.pm7_B.r62.value | 0.08748903708297069 | 2000 | kcal/mol |
| P.pm7_octanol.r332.z | 0.19611374564585277 | 2000 | Debye |
| P.pm7_B.r50.value | 0.11891531324386596 | 2000 | eV |
| P.pm7_B.r54.value | 292.86350226521813 | 2000 | eV |
| P.pm7_B.r63.value | 0.059241476577386494 | 2000 | eV |
| P.pm7_octanol.r326.p | 0.00784418895640935 | 106325 | e |
| P.pm7_B.r49.value | 0.12921122276652022 | 2000 | eV |
| P.pm7_B.r60.value | 1.9239669920228037 | 2000 | kcal/mol |
| P.pm7_anion.r196.z | 1.2312850236786763 | 2000 | Debye |
| P.pm7_B.r61.value | 0.0670668158531189 | 2000 | eV |
| P.pm7_B.r56.total | 0.03772246478555926 | 798283 | eV |
| P.pm7_B.r39.s | 0.003228471519076457 | 106325 | e |
| P.pm7_B.r73.value.pi | 0.03388226191612938 | 197626 | bond-order population |
| P.pm7_B.r55.electron_electron | 0.576523104833626 | 106325 | eV |
| P.pm7_B.r56.NN | 0.5320182116234801 | 798283 | eV |
| P.pm7_anion.r204.value | 3.7608889381637263 | 2000 | kcal/mol |
| P.pm7_B.r84.value | 0.006396789698776794 | 106325 | bond-order population |
| P.pm7_B.r53.value | 0.186214863712681 | 2000 | kcal/mol |
| P.xtb_singlepoint.r671.value | 0.06812720346450805 | 2000 | eV |
| P.pm7_B.r55.total | 0.8253611522142169 | 106325 | eV |
| P.xtb_singlepoint.r672.value | 0.09021584179345518 | 2000 | eV |
| P.pm7_water.r396.value | 2.105038023128731 | 2000 | A^2 |
| P.xtb_vipea.r752.value | 0.04589534628802744 | 1999 | eV |
| P.pm7_B.r82.Dn | 0.04559162694105153 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_cation.r259.s | 0.006771631602424749 | 106325 | e |
| P.pm7_water.r393.s | 0.0030959551059131815 | 106325 | e |
| P.pm7_water.r393.p | 0.00798735696015682 | 106325 | e |
| P.xtb_singlepoint.r666.value | 0.17814672877304755 | 106325 | Eh bohr^6 |
| P.pm7_B.r40.value | 0.00285711035087722 | 798283 | bond-order population |
| P.pm7_octanol.r326.s | 0.0030198504530679973 | 106325 | e |
| P.pm7_water.r399.z | 0.2048636819740641 | 2000 | Debye |
| P.pm7_cation.r265.y | 1.6145143477301171 | 2000 | Debye |
| P.pm7_cation.r273.value | 3.3824130161267023 | 2000 | kcal/mol |
| P.pm7_anion.r190.p | 0.015556840943625864 | 106325 | e |
| P.xtb_fod.r537.value | 0.0007462604310001894 | 106325 | e |
| P.pm7_water.r399.y | 0.23239979109400882 | 2000 | Debye |
| P.pm7_B.r42.value | 2.10700117957436 | 2000 | A^2 |
| P.pm7_B.r82.De | 0.04081814507277081 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_water.r399.x | 0.3034036051396979 | 2000 | Debye |
| P.pm7_octanol.r329.value | 2.104569571554174 | 2000 | A^2 |
| P.pm7_B.r39.p | 0.0077055929989050115 | 106325 | e |
| P.xtb_ALPB_octanol.r460.value | 0.0034416876802326967 | 2000 | Eh |
| P.pm7_B.r58.value | 0.08337181006781072 | 318975 | kcal mol^-1 A^-1 |
| P.pm7_B.r46.value | 0.011182808956822837 | 106325 | e |
| P.pm7_water.r410.value | 0.05577918213432713 | 2000 | eV |
| P.pm7_anion.r196.y | 1.4644639943971998 | 2000 | Debye |
| P.pm7_octanol.r332.y | 0.22243265324947425 | 2000 | Debye |
| P.pm7_anion.r190.s | 0.006412330473167263 | 106325 | e |
| P.pm7_water.r398.value | 0.02430155998996184 | 2000 | eV |
| P.pm7_cation.r259.p | 0.01661575941143388 | 106325 | e |
| P.xtb_vfukui.r712.f_radical | 0.001928371688992863 | 106147 | e |
| P.pm7_B.r45.value | 0.013018035115666704 | 106325 | e |
| P.xtb_vfukui.r712.f_plus | 0.0027080049529138025 | 106147 | e |
| P.xtb_ALPB_water.r498.value | 0.0007524956410665471 | 2000 | Eh |
| P.pm7_anion.r193.value | 2.105946372690755 | 2000 | A^2 |
| P.pm7_B.r64.value | 0.009629446375401134 | 106325 | e |
| P.pm7_anion.r194.value | 1.8448370180650577 | 2000 | A^3 |
| P.pm7_B.r56.C | 0.024432238622840254 | 798283 | eV |
| P.pm7_B.r65.value | 0.003014190854768743 | 797785 | e |
| P.xtb_vfukui.r712.f_minus | 0.0026737390870469483 | 106147 | e |
| P.pm7_B.r83.value | 0.08117406115502598 | 2000 | eV |
| P.pm7_cation.r263.value | 1.8455578018775904 | 2000 | A^3 |
| P.pm7_octanol.r332.x | 0.2894548780724872 | 2000 | Debye |
| P.xtb_singlepoint.r669.x | 0.2550949521465809 | 2000 | Debye |
| P.pm7_water.r397.value | 1.8448743362196667 | 2000 | A^3 |
| P.pm7_cation.r265.z | 1.4245622334603687 | 2000 | Debye |
| P.xtb_ALPB_water.r499.value | 0.003493111770756325 | 2000 | Eh |
| P.xtb_singlepoint.r669.y | 0.17933536620790982 | 2000 | Debye |
| P.pm7_B.r56.EN | 1.399135045417475 | 798283 | eV |
| P.pm7_octanol.r341.value | 0.06405343723297119 | 2000 | eV |
| P.pm7_octanol.r346.value | 0.006908529464506356 | 106325 | e |
| P.pm7_water.r408.value | 0.06662736105918884 | 2000 | eV |
| P.pm7_cation.r262.value | 2.1062511129302957 | 2000 | A^2 |
| P.xtb_singlepoint.r670.value | 0.0034340005698926747 | 2000 | Eh |
| P.pm7_anion.r210.value | 0.01578792723773207 | 106325 | e |
| P.xtb_singlepoint.r667.value | 0.029095977620183792 | 106325 | bohr^3 |
| P.pm7_B.r68.value | 0.007056965937166075 | 106325 | e |
| P.xtb_singlepoint.r668.value | 0.0038232814893893003 | 106325 | e |
| P.pm7_B.r48.value | 0.4205482741193076 | 2000 | kcal/mol |
| P.xtb_fod.r538.value | 0.014430323872620597 | 2000 | e |
| P.pm7_B.r52.z | 0.16076902575631902 | 2000 | Debye |
| P.xtb_singlepoint.r669.z | 0.1661049225059105 | 2000 | Debye |
| P.pm7_octanol.r340.value | 1.908939995172674 | 2000 | kcal/mol |
| P.pm7_B.r55.electron_nuclear | 1.7167329423017792 | 106325 | eV |
| P.pm7_B.r52.x | 0.24508116272626648 | 2000 | Debye |
| P.pm7_cation.r265.x | 3.6653149431238417 | 2000 | Debye |
| P.xtb_vipea.r751.value | 0.06610968438616109 | 1999 | eV |
| P.pm7_B.r82.charge_density_q_minus_Z | 0.3486498460755654 | 54838 | e |
| P.pm7_octanol.r330.value | 1.844659052481035 | 2000 | A^3 |
| P.pm7_anion.r196.x | 2.9971116302493463 | 2000 | Debye |
| P.pm7_B.r56.EE | 0.4634554375065473 | 798283 | eV |
| P.pm7_B.r43.value | 1.8456531200911515 | 2000 | A^3 |
| P.pm7_B.r73.value.sigma | 0.08709769932799652 | 599051 | bond-order population |
| P.pm7_B.r56.K | 0.01015766164180746 | 798283 | eV |
| P.xtb_ALPB_octanol.r459.value | 0.0004487511926656482 | 2000 | Eh |
| P.xtb_perturbed_gradient.r625.value | 0.005898121865869262 | 318975 | Eh bohr^-1 |
| P.xtb_perturbed_gradient.r624.value | 0.3183521523249025 | 318975 | eV A^-1 |
| P.xtb_perturbed_gradient.r623.value | 0.04292691823104136 | 2000 | Eh |
