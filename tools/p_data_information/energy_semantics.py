"""Register native PM7 energy definitions and check their published algebraic sum.
No new fit, source label, comparison pair, or QM calculation.
"""
import pickle,collections
import numpy as np
from stage0_cohort import R,O,load,save
B=R/'MFM_p_data_information';OUT=B/'results/p_data_information'
def main():
 with (O/'source_graph_scalars.pkl').open('rb') as stream:source=pickle.load(stream)
 result={}
 for role,molecules in source.items():
  residual=[]
  for records in molecules.values():
   for values in records.values():
    a,b,c=[values.get(n) for n in ['P.pm7_B.r83.value','P.pm7_B.r54.value','P.pm7_B.r41.value']]
    if all(v is not None for v in [a,b,c]):residual.append(abs(a-b-c))
  result[role]=dict(comparable_records=len(residual),median_absolute_native_sum_residual_eV=float(np.median(residual)) if residual else None,p90_absolute_native_sum_residual_eV=float(np.quantile(residual,.9)) if residual else None,max_observed_absolute_native_sum_residual_eV=max(residual) if residual else None,interpretation='Residual of separately parsed/rounded native outputs; not a calculation noise bound or independent-property evidence')
 definition=dict(PM7_native_total_energy='E_electronic + E_nuclear',PM7_heat_of_formation='E_electronic + E_nuclear - E_isolated_atoms + E_atomization + E_bits',E_bits='Hydrogen-bond and dispersion contributions',scope='Native MOPAC PM7 outputs; heat of formation and native TOTAL ENERGY must not be treated as identical up to unit conversion/elemental constants alone',source='https://openmopac.net/Manual/SCF_calc_hof.html')
 save(OUT/'energy_semantics.json',dict(definition=definition,native_sum_check=result,new_QM_calls=0,normalization_refit=False))
 f=load(B/'configs/p_data_information/fields.json')
 for item in f['fields']:
  if item['field_key'] in ['P.pm7_B.r60.value','P.pm7_B.r83.value','P.pm7_B.r54.value','P.pm7_B.r41.value']:item['energy_definition_note']=definition
 save(B/'configs/p_data_information/fields.json',f)
 joint=load(OUT/'family_complementarity.json');joint['documented_energy_relations']=dict(definition=definition,check=result,not_unique_information_claim=True);save(OUT/'family_complementarity.json',joint)
 (B/'docs/p_data_information/ENERGY_DEFINITIONS.md').write_text('''# 原生能量字段的定义区别\n\n按[MOPAC官方生成热定义](https://openmopac.net/Manual/SCF_calc_hof.html)，原生TOTAL ENERGY包含电子与核排斥部分；生成热还包括原子参考/原子化项与氢键、色散项E_bits。后两项可随几何改变。因此同组成时也不能只作单位换算就把生成热构象差与原生TOTAL ENERGY构象差视为重复。两者都不是本报告可以任意改称的“分子结合能”。\n\n在固定P字段中，r83（原生total_energy_eV）、r54（electronic_energy_eV）与r41（core_core_repulsion_eV）有程序定义层的代数关系；已有F64解析值的求和残差在energy_semantics.json。分项分别打印/解析后的不为零残差不构成新的独立物理信息，也不能将样本最大残差当作SCF误差界。r60生成热的附加项不能由减元素参考自动消除。\n\n这补充了阶段0的物理语义与阶段4的代数关系列表；未修改注册表、启用字段、生产目标、mask或D4/A1，也未新增计算/拟合。全域计算与物理方法准确性仍未建立。\n''')
 print('ENERGY_SEMANTICS_CLOSED',result,flush=True)
if __name__=='__main__':main()