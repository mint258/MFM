"""Depict already-frozen cases; no new pair or statistical selection."""
import pickle
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from rdkit import Chem
from rdkit.Chem import Draw
from stage0_cohort import R,O,load,guard
from stage3_information import rotation
B=R/'MFM_p_data_information';OUT=B/'results/p_data_information'
def main():
 guard();cov=load(OUT/'coverage.json');panel=load(O/'panel.json')['TRAIN'];byid={r['molecule_id']:r for r in panel};pairs=load(O/'pairs.json')['TRAIN'];case=cov['cases']['TRAIN'][0];row=byid[case['molecule_id']]
 with (O/'samples/TRAIN'/(str(row['pilot_index'])+'.pkl')).open('rb') as stream:samples=pickle.load(stream)
 a,b=samples[case['a']],samples[case['b']];x=a['pos'].astype(float);y=b['pos'].astype(float);heavy=a['Z']>1;x-=x[heavy].mean(0);y-=y[heavy].mean(0);x=x@rotation(a['pos'],b['pos'],heavy)
 fig=plt.figure(figsize=(12,4.7));ax=fig.add_subplot(122,projection='3d');bonds=np.asarray(row['bonds']);bonds=bonds.T if bonds.shape[0]==2 else bonds
 for xyz,color,label in [(x,'#126782','Native record A'),(y,'#dc7b23','Native record B')]:
  ax.scatter(*xyz[heavy].T,c=color,s=18,label=label)
  for i,j in bonds:
   if heavy[i] and heavy[j]:ax.plot(*xyz[[i,j]].T,color=color,lw=1,alpha=.7)
 combined=np.concatenate([x[heavy],y[heavy]]);lo=combined.min(0);hi=combined.max(0);center=(lo+hi)/2;radius=max((hi-lo).max()/2,1)*1.1
 for setter,c in zip([ax.set_xlim,ax.set_ylim,ax.set_zlim],center):setter(c-radius,c+radius)
 ax.set_box_aspect((1,1,1));ax.set_xlabel('x / A');ax.set_ylabel('y / A');ax.set_zlabel('z / A');ax.legend(fontsize=8,loc='upper left');ax.set_title(case['molecule_id']+'\nHeavy atoms; proper alignment; source correspondence',fontsize=10)
 iso=None
 for c in cov['cases']['TRAIN']:
  iso=next((p for p in pairs['isomer'] if c['molecule_id'] in [p['a'],p['b']]),None)
  if iso:break
 if iso:
  for j,mid in enumerate([iso['a'],iso['b']]):
   ax2=fig.add_axes([.035+j*.235,.24,.225,.55]);ax2.imshow(Draw.MolToImage(Chem.MolFromSmiles(byid[mid]['stereo']),size=(450,360)));ax2.axis('off');ax2.set_title(mid,fontsize=9)
  fig.text(.265,.84,'Existing same-formula group of a frozen case\n2D connectivity sketches',ha='center',fontsize=10)
 fig.suptitle('Frozen structural examples (labels did not select these cases)',fontsize=12);fig.savefig(OUT/'structure_examples.svg',bbox_inches='tight');fig.savefig(OUT/'structure_examples.png',dpi=150,bbox_inches='tight');plt.close(fig)
 print('FROZEN_STRUCTURE_EXAMPLES_DONE')
if __name__=='__main__':main()