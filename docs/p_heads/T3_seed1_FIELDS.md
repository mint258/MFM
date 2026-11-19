# T3 seed 1 生产者描述性字段附表

运行：`p_heads_T3_seed1_attempt2`。直接转录既有3M生产者记录，没有重新评价、拟合、bootstrap或计算MAE。

CYP来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/scores.csv`。CYP不进入七任务主分。

| 读出 | 任务 | 原误差 | 随机参考误差 | score | 排除主分 |
| --- | --- | ---: | ---: | ---: | --- |
| R1 | cyp.3A4 | 0.4571428571428572 | 0.6857142857142857 | 0.33333333333333326 | True |
| R1 | cyp.2D6 | 0.5384615384615384 | 0.6153846153846154 | 0.12500000000000008 | True |
| R3 | cyp.3A4 | 0.34285714285714286 | 0.6 | 0.42857142857142855 | True |
| R3 | cyp.2D6 | 0.5384615384615384 | 0.6153846153846154 | 0.12500000000000008 | True |

逐字段原单位VAL来源：`/share/home/zixiao/descriptor_analysis/runs/p_heads_20261117/runtime/results/p_recipe/training/p_heads_T3_seed1_attempt2/VAL_original_units_3000000.csv`。

| 字段 | 原单位MAE | 观察数 | 单位 |
| --- | ---: | ---: | --- |
| P.pm7_octanol.r332.z | 0.20505786377121693 | 2000 | Debye |
| P.pm7_octanol.r346.value | 0.007081040563304465 | 106325 | e |
| P.pm7_B.r54.value | 303.2399502898349 | 2000 | eV |
| P.pm7_water.r397.value | 1.882725636510883 | 2000 | A^3 |
| P.pm7_octanol.r331.value | 0.020543734178767162 | 2000 | eV |
| P.xtb_ALPB_water.r498.value | 0.000892100214863246 | 2000 | Eh |
| P.pm7_B.r49.value | 0.13659632335961214 | 2000 | eV |
| P.pm7_B.r47.value | 0.382958155356199 | 2000 | kcal/mol |
| P.pm7_B.r39.s | 0.003303479803553083 | 106325 | e |
| P.pm7_B.r62.value | 0.08963992450180162 | 2000 | kcal/mol |
| P.pm7_anion.r210.value | 0.01596946196210708 | 106325 | e |
| P.xtb_singlepoint.r669.x | 0.26232286182051756 | 2000 | Debye |
| P.xtb_ALPB_octanol.r459.value | 0.0005127276909625858 | 2000 | Eh |
| P.pm7_B.r40.value | 0.0028992014697282985 | 798283 | bond-order population |
| P.xtb_singlepoint.r666.value | 0.19933810359711876 | 106325 | Eh bohr^6 |
| P.pm7_B.r60.value | 1.9977300435320642 | 2000 | kcal/mol |
| P.pm7_B.r43.value | 1.8840065935135426 | 2000 | A^3 |
| P.pm7_cation.r265.x | 3.7024965309205 | 2000 | Debye |
| P.xtb_singlepoint.r671.value | 0.07187135219573974 | 2000 | eV |
| P.pm7_B.r58.value | 0.08337241718375159 | 318975 | kcal mol^-1 A^-1 |
| P.xtb_vipea.r752.value | 0.04816233294793759 | 1999 | eV |
| P.pm7_water.r393.s | 0.0031815826486425625 | 106325 | e |
| P.xtb_singlepoint.r667.value | 0.03088691689002214 | 106325 | bohr^3 |
| P.pm7_anion.r196.x | 3.120170412736552 | 2000 | Debye |
| P.xtb_fod.r538.value | 0.01507214422608985 | 2000 | e |
| P.xtb_singlepoint.r672.value | 0.09839069812651724 | 2000 | eV |
| P.pm7_water.r398.value | 0.026186332508467355 | 2000 | eV |
| P.pm7_octanol.r343.value | 0.05793632591491769 | 2000 | eV |
| P.pm7_B.r52.y | 0.18459639204695122 | 2000 | Debye |
| P.pm7_B.r56.EN | 1.3325120433843844 | 798283 | eV |
| P.pm7_B.r56.NN | 0.4300728777060757 | 798283 | eV |
| P.pm7_B.r46.value | 0.01129722450596014 | 106325 | e |
| P.xtb_vfukui.r712.f_radical | 0.00197218608556234 | 106147 | e |
| P.pm7_B.r83.value | 0.08508194785579752 | 2000 | eV |
| P.pm7_B.r44.value | 0.015392531619193045 | 106325 | e |
| P.xtb_ALPB_water.r499.value | 0.0036289540729954658 | 2000 | Eh |
| P.xtb_singlepoint.r677.value | 0.004984880273735708 | 118841 | bond-order population |
| P.pm7_water.r399.x | 0.3053228158269776 | 2000 | Debye |
| P.pm7_water.r393.p | 0.008349812204539847 | 106325 | e |
| P.pm7_water.r399.y | 0.2376892717028968 | 2000 | Debye |
| P.pm7_cation.r262.value | 2.221743935923544 | 2000 | A^2 |
| P.pm7_cation.r265.z | 1.4835095388374757 | 2000 | Debye |
| P.pm7_anion.r196.y | 1.4546798047636402 | 2000 | Debye |
| P.pm7_B.r42.value | 2.221925727066466 | 2000 | A^2 |
| P.pm7_B.r82.Dn | 0.04638845114079309 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_anion.r194.value | 1.8836409370140983 | 2000 | A^3 |
| P.pm7_B.r53.value | 0.19880011441455236 | 2000 | kcal/mol |
| P.xtb_singlepoint.r669.y | 0.18919583569982934 | 2000 | Debye |
| P.pm7_octanol.r330.value | 1.8835944994490426 | 2000 | A^3 |
| P.pm7_cation.r273.value | 3.5909956787637034 | 2000 | kcal/mol |
| P.pm7_water.r410.value | 0.05913239197772054 | 2000 | eV |
| P.pm7_water.r396.value | 2.221467553984784 | 2000 | A^2 |
| P.xtb_singlepoint.r669.z | 0.17265171535045373 | 2000 | Debye |
| P.pm7_B.r84.value | 0.006377006736385831 | 106325 | bond-order population |
| P.pm7_anion.r204.value | 3.977107834065003 | 2000 | kcal/mol |
| P.pm7_anion.r196.z | 1.2655045303805965 | 2000 | Debye |
| P.pm7_water.r413.value | 0.007159271272194391 | 106325 | e |
| P.xtb_singlepoint.r670.value | 0.0035926640737680166 | 2000 | Eh |
| P.pm7_B.r65.value | 0.0031158694995918348 | 797785 | e |
| P.pm7_water.r407.value | 1.9905068850256633 | 2000 | kcal/mol |
| P.pm7_anion.r190.p | 0.01584378175228981 | 106325 | e |
| P.pm7_anion.r190.s | 0.006572499756193038 | 106325 | e |
| P.pm7_octanol.r332.x | 0.29460929497983307 | 2000 | Debye |
| P.pm7_B.r82.De | 0.04138950985462214 | 54838 | 1/eV (source-dimensional inference) |
| P.pm7_octanol.r341.value | 0.0683230550289154 | 2000 | eV |
| P.pm7_B.r56.J | 0.02275950023137426 | 798283 | eV |
| P.pm7_octanol.r329.value | 2.2212802987452402 | 2000 | A^2 |
| P.pm7_B.r52.z | 0.16664178633476331 | 2000 | Debye |
| P.pm7_cation.r259.p | 0.016663779365282017 | 106325 | e |
| P.xtb_fod.r537.value | 0.0007550909264018934 | 106325 | e |
| P.pm7_B.r73.value.pi | 0.03370056914333371 | 197626 | bond-order population |
| P.xtb_vipea.r751.value | 0.06898501668883168 | 1999 | eV |
| P.pm7_B.r61.value | 0.07341711616516114 | 2000 | eV |
| P.xtb_vfukui.r712.f_minus | 0.002715900072191117 | 106147 | e |
| P.pm7_cation.r279.value | 0.017833347007850407 | 106325 | e |
| P.xtb_ALPB_octanol.r460.value | 0.0036037457004285223 | 2000 | Eh |
| P.pm7_B.r55.electron_electron | 0.6276457046491243 | 106325 | eV |
| P.pm7_water.r399.z | 0.21492581858724588 | 2000 | Debye |
| P.pm7_B.r52.x | 0.2503093122391801 | 2000 | Debye |
| P.pm7_cation.r263.value | 1.8836695614781631 | 2000 | A^3 |
| P.pm7_B.r56.EE | 0.4718095581888414 | 798283 | eV |
| P.xtb_singlepoint.r668.value | 0.003919364391039751 | 106325 | e |
| P.pm7_B.r50.value | 0.12357174205780029 | 2000 | eV |
| P.pm7_B.r41.value | 303.26991622168634 | 2000 | eV |
| P.pm7_B.r64.value | 0.009782513676033125 | 106325 | e |
| P.pm7_B.r55.total | 0.8522272798646738 | 106325 | eV |
| P.pm7_B.r82.charge_density_q_minus_Z | 0.35623760480989425 | 54838 | e |
| P.xtb_vfukui.r712.f_plus | 0.0027562072932316955 | 106147 | e |
| P.pm7_B.r45.value | 0.013092341585918035 | 106325 | e |
| P.pm7_B.r39.p | 0.008044811887388478 | 106325 | e |
| P.pm7_B.r73.value.sigma | 0.08747804177513345 | 599051 | bond-order population |
| P.pm7_B.r56.K | 0.010509747447798827 | 798283 | eV |
| P.pm7_B.r68.value | 0.007223339005380316 | 106325 | e |
| P.pm7_octanol.r326.s | 0.0031149881827307116 | 106325 | e |
| P.pm7_cation.r259.s | 0.006868399381917868 | 106325 | e |
| P.pm7_B.r63.value | 0.06766020602968638 | 2000 | eV |
| P.pm7_octanol.r326.p | 0.008007516324127698 | 106325 | e |
| P.pm7_anion.r193.value | 2.222126591027798 | 2000 | A^2 |
| P.pm7_B.r56.total | 0.03933568531169075 | 798283 | eV |
| P.pm7_cation.r265.y | 1.6666447571426688 | 2000 | Debye |
| P.pm7_octanol.r332.y | 0.22780404243734664 | 2000 | Debye |
| P.pm7_B.r55.electron_nuclear | 1.7358262836010967 | 106325 | eV |
| P.pm7_B.r56.C | 0.025076011510680504 | 798283 | eV |
| P.pm7_octanol.r340.value | 1.9822626990053427 | 2000 | kcal/mol |
| P.pm7_water.r408.value | 0.07038673281669616 | 2000 | eV |
| P.pm7_B.r48.value | 0.45269273033884333 | 2000 | kcal/mol |
| P.xtb_perturbed_gradient.r625.value | 0.005994307758135341 | 318975 | Eh bohr^-1 |
| P.xtb_perturbed_gradient.r623.value | 0.04104708234367202 | 2000 | Eh |
| P.xtb_perturbed_gradient.r624.value | 0.31926839916224115 | 318975 | eV A^-1 |
