"""Publication artifacts from closed aggregate results and <=12 frozen cases."""
import argparse,collections
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from stage0_cohort import R,O,load
B=R/'MFM_p_data_information';OUT=B/'results/p_data_information'
def phase3():
 data=load(OUT/'conditional_information.json');fields=load(B/'configs/p_data_information/fields.json')['fields'];energy=[f for f in fields if f['level']=='molecule' and any(k in str(f['source_path']) for k in ('heat_of_formation','total_energy','energy_Eh'))];wanted=[]
 source_path=OUT/'source_scalar_authority.json';source_points=None
 if source_path.exists():
  source=load(source_path);data={'roles':{role:{'composition_composition':levels['composition'],'isomer_isomer':levels['isomer'],'conformer_core':levels['conformer_core']} for role,levels in source['roles'].items()}}
  import pickle
  with (O/'source_graph_scalars.pkl').open('rb') as stream:source_points=pickle.load(stream)
 for task in ['pm7_B','xtb_singlepoint']:
  candidates=[f for f in energy if f['field_key'].startswith('P.'+task+'.') and data['roles']['TRAIN']['conformer_core'][f['field_key']]['median'] is not None]
  candidates.sort(key=lambda f:(not any(p in str(f['source_path']) for p in ('heat_of_formation','total_energy')),f['field_key']))
  found=candidates[0] if candidates else None
  if found:wanted.append(found)
 fig,axs=plt.subplots(1,max(1,len(wanted)),figsize=(11,4),squeeze=False)
 for ax,f in zip(axs.flat,wanted):
  name=f['field_key']
  for offset,role,color in [(-.12,'TRAIN','#126782'),(.12,'VAL','#dc7b23')]:
   med=[];lo=[];hi=[]
   for key in ['composition_composition','isomer_isomer','conformer_core']:
    s=data['roles'][role][key][name];m=s['median'];ci=s['ci95'];med.append(m if m is not None else np.nan);lo.append(m-ci[0] if ci else 0);hi.append(ci[1]-m if ci else 0)
   ax.errorbar(np.arange(3)+offset,med,yerr=[lo,hi],fmt='o',capsize=3,label=role,color=color)
  ax.set_xticks(range(3),['Across composition','Same formula','Same molecule'],rotation=15);ax.set_yscale('log');ax.set_ylabel('Absolute difference ('+str(f['unit'])+')');ax.set_title(name);ax.legend()
 fig.suptitle('Original WP5 scalars: independent-unit median and 95% bootstrap interval\nSource calculation/printing precision unresolved; no noise cutoff assumed',fontsize=11);fig.tight_layout();fig.savefig(OUT/'conditional_amplitudes.svg');fig.savefig(OUT/'conditional_amplitudes.png',dpi=150);plt.close(fig)
 cov=load(OUT/'coverage.json');fig,ax=plt.subplots(figsize=(7,3));roles=list(cov['roles']);x=np.arange(len(roles));ax.bar(x-.18,[cov['roles'][r]['records'] for r in roles],.36,label='Allowed records',color='#a7c9dd');ax.bar(x+.18,[cov['roles'][r]['representatives'] for r in roles],.36,label='0.5 A representatives',color='#126782');ax.set_xticks(x,roles);ax.set_ylabel('Count');ax.legend();fig.tight_layout();fig.savefig(OUT/'coverage.svg');plt.close(fig)
 if wanted:
  f=wanted[0];name=f['field_key'];fig,axs=plt.subplots(1,2,figsize=(12,4));isomer_shown=False;case_number=0
  for role,color in [('TRAIN','#126782'),('VAL','#dc7b23')]:
   graph=load(O/'source_graph_summaries.json')[role] if source_path.exists() else load(O/('graph_summaries_'+role+'.json'));cases=cov['cases'][role]
   for case in cases:
    case_number+=1
    mid=case['molecule_id'];pa=next((p for p in load(O/'panel.json')[role] if p['molecule_id']==mid),None)
    if pa is None:continue
    import pickle
    with (O/'samples'/role/(str(pa['pilot_index'])+'.pkl')).open('rb') as stream:s=pickle.load(stream)
    a,b=s[case['a']]['targets'].get(name),s[case['b']]['targets'].get(name)
    va=source_points[role][mid][case['native_record_id_a']].get(name) if source_points is not None else (float(a.raw.flat[0]) if a is not None else None);vb=source_points[role][mid][case['native_record_id_b']].get(name) if source_points is not None else (float(b.raw.flat[0]) if b is not None else None)
    if a is not None and b is not None and a.valid.all() and b.valid.all() and va is not None and vb is not None:axs[0].scatter(case['heavy_rmsd'],abs(va-vb),c=color);axs[0].annotate(str(case_number),(case['heavy_rmsd'],abs(va-vb)),xytext=(8+18*((case_number-1)%3),8+12*((case_number-1)%2)),textcoords='offset points',fontsize=7,arrowprops=dict(arrowstyle='-',lw=.4,color=color))
    if not isomer_shown:
     pair=next((p for p in load(O/'pairs.json')[role]['isomer'] if mid in (p['a'],p['b'])),None)
     if pair:
      ids=[pair['a'],pair['b']]
      for i,mid2 in enumerate(ids):
       g=graph[mid2].get(name)
       if g and g['median'] is not None:axs[1].errorbar(i,g['median'],yerr=[[g['median']-g['minimum']],[g['maximum']-g['median']]],fmt='o',capsize=4,color=color)
      axs[1].set_xticks(range(2),ids,rotation=15);axs[1].set_title('Frozen-case molecule and its same-formula partner\nMedian and observed conformer range (not thermodynamics)',fontsize=9);isomer_shown=True
  axs[0].margins(x=.18,y=.24);axs[0].set_xlabel('Heavy-atom RMSD (A)');axs[0].set_ylabel('Original scalar difference ('+str(f['unit'])+')');axs[0].set_title('Preselected cases; IDs follow coverage.json order\nBlue TRAIN / orange VAL; no monotonicity assumed',fontsize=9)
  axs[1].set_ylabel('Original scalar value ('+str(f['unit'])+')');fig.suptitle(name);fig.tight_layout();fig.savefig(OUT/'structure_cases.svg');fig.savefig(OUT/'structure_cases.png',dpi=150);plt.close(fig)

def phase4():
 data=load(OUT/'family_complementarity.json');fig,axs=plt.subplots(1,2,figsize=(12,5))
 r=data['roles']['TRAIN']['conformer'];families=r['families'];m=np.full((len(families),len(families)),np.nan)
 for v in r['conditional_correlations']:
  if v['conditional_distance_correlation'] is not None:m[families.index(v['family_a']),families.index(v['family_b'])]=v['conditional_distance_correlation']
 im=axs[0].imshow(np.ma.masked_invalid(m),vmin=-1,vmax=1,cmap='coolwarm');axs[0].set_xticks(range(len(families)),families,rotation=90);axs[0].set_yticks(range(len(families)),families);axs[0].set_title('Pilot conditional family-distance correlation\nUncalibrated; not independent information');fig.colorbar(im,ax=axs[0],shrink=.6)
 axs[1].imshow(np.zeros_like(m),cmap='Greys',vmin=0,vmax=1);axs[1].set_xticks(range(len(families)),families,rotation=90);axs[1].set_yticks(range(len(families)),families);axs[1].set_title('Unique calibrated complementarity: UNKNOWN\nNo matched calculation-error controls')
 fig.tight_layout();fig.savefig(OUT/'family_matrix.svg');fig.savefig(OUT/'family_matrix.png',dpi=150);plt.close(fig)
 fig,ax=plt.subplots(figsize=(8,4));labels=[];total=[];common=[]
 for role,levels in data['roles'].items():
  for level in ['composition','isomer','conformer']:labels.append(role+' '+level);total.append(levels[level]['candidate_pairs']);common.append(levels[level]['common_all_family_pairs'])
 x=np.arange(len(labels));ax.bar(x,total,color='#b9cfdf',label='Candidate pairs');ax.bar(x,common,color='#126782',label='All eligible families comparable');ax.set_xticks(x,labels,rotation=25,ha='right');ax.legend();ax.set_ylabel('Pairs (not independent units)');fig.tight_layout();fig.savefig(OUT/'pair_coverage.svg');fig.savefig(OUT/'pair_coverage.png',dpi=150);plt.close(fig)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('stage',type=int,choices=[3,4]);a=p.parse_args();phase3() if a.stage==3 else phase4()
