"""Prepare the user-registered M2-based round4, without launching training."""
import json
from pathlib import Path
from phychem_mfm.phase1.p_recipe_plan import configuration

R=Path('/share/home/zixiao/descriptor_analysis');REPO=Path(__file__).resolve().parents[2]
ROOT=REPO/'configs/p_recipe/fixed_20261115';OUT=Path('/lfshome/zixiao/model_v31_20261105/P_RECIPE_20261113')
read=lambda p:json.loads(Path(p).read_text())
def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n')

def prepare():
 meta=read(R/'runs/p_recipe_20261113/D6_metadata.json');base=read(ROOT/'round3/M2.json')
 registry={x['registry_id']:x for x in read(REPO/'workflows/screening/registry/label_registry_v2.json')['entries']}
 view_fields={f['field_key']:f for f in read(base['training_view'])['fields']}
 enabled=set(meta['P_enabled']);prime=set(meta['Pprime_enabled']);common=sorted(enabled&prime)
 fields={f['name']:f for f in meta['fields'] if f['name'] in enabled|prime}
 by_id={}
 for f in fields.values():by_id.setdefault(f['registry_id'],[]).append(f)
 root=ROOT/'round4'
 pp=[]
 for name in common:
  f=fields[name];m=f['metadata'];v=view_fields[name]
  assert v['field_key']==name and v['registry_id']==f['registry_id'] and v['target_id']
  if m:assert m['field_key']==name and m['registry_id']==f['registry_id'] and m['target_id']==v['target_id']
  pp.append(dict(field=name,registry_id=f['registry_id'],component=m.get('component',v.get('preferred_schema_selector',{}).get('target')),
    target_id=v['target_id'],source_path=m.get('source_path',registry[f['registry_id']]['source_path']),unit=v['unit'],
    source_field=v.get('source_field',name),aggregation=v.get('aggregation'),selectors=v['selectors']))
 write(root/'PP_fields.json',dict(schema='P_RECIPE_PP_FIELD_INTERSECTION_V1',authority='docs/p_recipe/USER_DIRECTIVE_20261118.md',
   P_count=len(enabled),Pprime_count=len(prime),common_count=len(common),M2C_required=common!=sorted(enabled),fields=pp,
   alignment='Same field_key, registry_id/component and physical target_id from the shared training-view/schema. Only geometry source and the registered UFF A1 reference change.',
   training_view=base['training_view'],normalizations=base['normalizations']))
 specs=[('HOMO',61,671,'Same neutral gas-phase HOMO orbital energy in eV'),
        ('LUMO',63,672,'Same neutral gas-phase LUMO orbital energy in eV'),
        ('vertical_EA',49,751,'Same-geometry neutral vertical electron affinity, native EA sign, eV; PM7 charged-state difference and xTB delta-SCC EA'),
        ('vertical_IP',50,752,'Same-geometry neutral vertical ionization energy, native IP sign, eV; PM7 charged-state difference and xTB delta-SCC IP'),
        ('dipole',52,669,'Same neutral gas-phase Cartesian electric dipole in Debye; x/y/z retain one physical vector head')]
 pairs=[];paired=set()
 for quantity,left,right,definition in specs:
  a,b=registry[left],registry[right]
  assert all(a[k]==b[k] for k in ('charge','context','level','unit','geometry_context','electronic_context'))
  lf=sorted(by_id[left],key=lambda f:f['metadata']['component']);rf=sorted(by_id[right],key=lambda f:f['metadata']['component'])
  assert [f['metadata']['component'] for f in lf]==[f['metadata']['component'] for f in rf]
  assert len(lf)==len(rf) and all(f['name'] in enabled for f in lf+rf)
  pairs.append(dict(quantity=quantity,PM7_registry_id=left,xTB_registry_id=right,PM7_fields=[f['name'] for f in lf],xTB_fields=[f['name'] for f in rf],
    PM7_method=a['method'],xTB_method=b['method'],charge=a['charge'],solvent=a['context'],level=a['level'],unit=a['unit'],
    dimension=3 if a['level']=='molecule_vector' else 1,definition=definition,unit_or_sign_conversion='None; native target values and each field normalization remain unchanged',
    PM7_source_path=a['source_path'],xTB_source_path=b['source_path']))
  paired.update(f['name'] for f in lf+rf)
 reasons={331:'PM7 dielectric energy is not the same thermodynamic quantity as xTB Gsolv; unit conversion cannot establish an identity.',
          398:'PM7 dielectric energy is not the same thermodynamic quantity as xTB Gsolv; unit conversion cannot establish an identity.',
          459:'xTB Gsolv is not identified with the PM7 dielectric-energy term by the registry.',498:'xTB Gsolv is not identified with the PM7 dielectric-energy term by the registry.',
          68:'PM7 net atomic charges and xTB partial charges lack an explicit common population definition in the registry.',
          668:'xTB partial charges and PM7 net atomic charges lack an explicit common population definition in the registry.',
          40:'Generic PM7 bond-order population and xTB Wiberg index are not established as the same index by the registry.',
          677:'xTB Wiberg index has no registry-established identical PM7 index.',
          44:'Coulson-specific condensed Fukui and generic xTB Fukui lack a registry-defined common population convention.',
          45:'Coulson-specific condensed Fukui and generic xTB Fukui lack a registry-defined common population convention.',
          46:'Coulson-specific condensed Fukui and generic xTB Fukui lack a registry-defined common population convention.',
          712:'Generic xTB condensed Fukui and PM7 Coulson-specific Fukui lack a registry-defined common population convention.'}
 unpaired=[dict(field=name,registry_id=fields[name]['registry_id'],reason=reasons.get(fields[name]['registry_id'],'No unique enabled counterpart with the same definition, state, solvent, granularity, dimension and sign convention.')) for name in sorted(enabled-paired)]
 pair_path=root/'fidelity_pairs.json'
 write(pair_path,dict(schema='P_RECIPE_FIDELITY_PAIRS_V1',authority='docs/p_recipe/USER_DIRECTIVE_20261118.md',registry='workflows/screening/registry/label_registry_v2.json',
   evidence_sources=['workflows/wp5/scripts/wp5_engine_v2.py derived_quantities','workflows/wp5/scripts/wp5_parser.py','/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/scripts/wp4_parsers.py parse_xtb'],
   rules=['same physical quantity','same molecular/electronic state','same solvent','same granularity','same dimension and sign convention','no guessed conversion or ambiguous many-to-one mapping'],
   pairs=pairs,unpaired=unpaired,physical_head_pairs=len(pairs),field_pairs=sum(len(p['PM7_fields']) for p in pairs)))
 xtb_drop={n for p in pairs for n in p['xTB_fields']};perturbed={n for n in enabled if fields[n]['registry_id'] in (623,624,625)}
 weights={n:5 for n in enabled if fields[n]['registry_id'] in (624,625)}
 arms=['PP']+(['M2C'] if common!=sorted(enabled) else [])+['F2','X1','X2','F1'];configs=[];readiness={}
 for arm in arms:
  alias='Pprime' if arm=='PP' else arm
  c=configuration(base,{'A1','B3','B4'},run='fixed_20261115_round4_'+alias,round_number=4,arm=arm,samples=3000000)
  c['p_recipe']['gamma']=base['p_recipe']['gamma'];c['label_parameters']=str(OUT/'label_parameters/PM7_A1.json')
  c.update(fields=sorted(enabled),protocol_exception='USER_DIRECTIVE_20261118_REGISTERED_ROUND4',round4_baseline='M2_seed0_3M',round4_authority='docs/p_recipe/USER_DIRECTIVE_20261118.md')
  if arm=='PP':c.update(source='UFF',condition='Pprime',corpus=str(OUT/'corpus/Pprime_corpus.json'),label_parameters=str(OUT/'label_parameters/UFF_A1.json'),fields=common)
  elif arm=='M2C':c['fields']=common
  elif arm=='F2':c['fields']=sorted(enabled-xtb_drop)
  elif arm=='X1':c['fields']=sorted(enabled-perturbed)
  elif arm=='X2':c['p_recipe']['field_loss_multipliers']=weights
  elif arm=='F1':c['p_recipe'].update(fidelity_pairs=str(pair_path),method_embedding_dim=8)
  if arm not in ('PP','M2C'):c['components']=sorted(set(c['components'])|{arm})
  path=root/(alias+'.json');assert not Path(c['output']).exists(),'Inspect an existing run instead of overwriting its configuration'
  write(path,c);configs.append(str(path));readiness[arm]='WAITING_F1_IMPLEMENTATION_AND_ACCEPTANCE' if arm=='F1' else 'PREPARED_WAITING_FOR_C3'
 plan=dict(schema='P_RECIPE_REGISTERED_ROUND4_V1',status='REGISTERED_WAITING_FOR_C3',authority='docs/p_recipe/USER_DIRECTIVE_20261118.md',
   configurations=[],registered_configurations=configs,readiness_by_arm=readiness,baseline_configuration=str(ROOT/'round3/M2.json'),
   base_configuration=str(ROOT/'base.json'),study_revision=base['study_revision'],results_directory='results/p_recipe/fixed_20261115/round4',
   control_directory=str(R/'runs/p_recipe_20261113/fixed_20261115/round4'),screening_gpu_hour_limit=None,samples_per_run=3000000,
   training_priority=arms,requires_C3_complete_before_launch=True,fidelity_pairs=str(pair_path),PP_fields=str(root/'PP_fields.json'),
   M2C_required=common!=sorted(enabled),no_training_started=True)
 write(root/'plan.json',plan)
 print(json.dumps(dict(status=plan['status'],arms=arms,P_fields=len(enabled),PP_fields=len(common),M2C_required=plan['M2C_required'],physical_pairs=len(pairs),field_pairs=sum(len(p['PM7_fields']) for p in pairs),F2_fields=len(enabled-xtb_drop),X1_fields=len(enabled-perturbed),configurations_launched=0)),flush=True)
 return plan

if __name__=='__main__':prepare()
