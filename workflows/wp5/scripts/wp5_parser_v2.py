#!/usr/bin/env python3
"""WP5 parser2: native printed PM7 hydrogen-bond contribution fallback only."""
from __future__ import annotations
import argparse,ast,copy,hashlib,importlib.util,json,math,re,struct,tempfile,os,stat,shutil
from pathlib import Path
BASE_PATH=Path(__file__).with_name('wp5_parser.py')
BASE_SHA='aafa3c2808ccfa3a6bcea49f9807563351f0252e5e9f7cd57d86e40ddc291aa3'
if hashlib.sha256(BASE_PATH.read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('FROZEN_BASE_PARSER_SOURCE_CHANGED')
_spec=importlib.util.spec_from_file_location('wp5_parser2_frozen_base',BASE_PATH)
_BASE=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_BASE)
FLOAT,f,scalar,triangle,indexed_table=_BASE.FLOAT,_BASE.f,_BASE.scalar,_BASE.triangle,_BASE.indexed_table
read_aux,sigma_pi_entries=_BASE.read_aux,_BASE.sigma_pi_entries
EH_TO_EV,BOHR_TO_A,AU_DIPOLE_TO_DEBYE=_BASE.EH_TO_EV,_BASE.BOHR_TO_A,_BASE.AU_DIPOLE_TO_DEBYE
ELEMENTS,DELETED_FIELDS,decimal_places,d4_table,project_values=_BASE.ELEMENTS,_BASE.DELETED_FIELDS,_BASE.decimal_places,_BASE.d4_table,_BASE.project_values
HB_FIELD='hydrogen_bond_energy_kcal_mol'
HB_SUMMARY=re.compile(r'^\s*Total contribution from hydrogen bonds:\s*('+FLOAT+r')\s+disp\.\s*:\s*'+FLOAT+r'\s+Tot:\s*'+FLOAT+r'\s+kcal/mol\s*$',re.I|re.M)
HB_OLD=re.compile(r'HYDROGEN BOND(?:ING)? ENERGY\s*=\s*('+FLOAT+r')')
LAST_CONTEXT={}

def context():return copy.deepcopy(LAST_CONTEXT)

def hydrogen_bond_fallback(values,text):
    """No inferred zeros: existing scalar wins; complete actual printed line only."""
    existing=values.get(HB_FIELD);old=HB_OLD.search(text)
    if existing is not None:
        return {'producer':'FROZEN_LEGACY_HYDROGEN_BOND_ENERGY_ASSIGNMENT','field':HB_FIELD,
                'source_token':old.group(1) if old else None,'fallback_applied':False,'unit':'kcal/mol',
                'rounding_decimal_places':decimal_places(old.group(1)) if old else None}
    hit=HB_SUMMARY.search(text)
    if hit is None:
        return {'producer':'NATIVE_NUMERIC_HB_SUMMARY_NOT_EMITTED_OR_INVALID','field':HB_FIELD,
                'source_token':None,'fallback_applied':False,'unit':'kcal/mol','rounding_decimal_places':None}
    token=hit.group(1)
    try:value=f(token)
    except ValueError as exc:
        if str(exc)!='Nonfinite numerical output':raise
        value=None
    if value is None or not math.isfinite(value):
        return {'producer':'NATIVE_HB_SUMMARY_NONFINITE','field':HB_FIELD,'source_token':token,
                'fallback_applied':False,'unit':'kcal/mol','rounding_decimal_places':None}
    values[HB_FIELD]=value
    return {'producer':'MOPAC_TOTAL_CONTRIBUTION_FROM_HYDROGEN_BONDS_SUMMARY','field':HB_FIELD,
            'source_token':token,'source_line':text[:hit.start()].count('\n')+1,'fallback_applied':True,
            'unit':'kcal/mol','rounding_decimal_places':decimal_places(token)}

def parse_mopac(directory,symbols,pair_indices=None,reconstruct_mulliken=False):
    global LAST_CONTEXT
    # Preserve native invoke's selective AUX reader/sparse sigma-pi hooks.
    _BASE.read_aux=read_aux;_BASE.sigma_pi_entries=sigma_pi_entries
    values=_BASE.parse_mopac(directory,symbols,pair_indices=pair_indices,reconstruct_mulliken=reconstruct_mulliken)
    text=(Path(directory)/'input.out').read_text(errors='replace')
    proof=hydrogen_bond_fallback(values,text);LAST_CONTEXT=copy.deepcopy(_BASE.context())
    LAST_CONTEXT['hydrogen_bond_energy_source']=proof
    if proof['rounding_decimal_places'] is not None:LAST_CONTEXT.setdefault('rounding_decimal_places',{})[HB_FIELD]=proof['rounding_decimal_places']
    return values

def parse_xtb(directory,symbols):
    global LAST_CONTEXT
    values=_BASE.parse_xtb(directory,symbols);LAST_CONTEXT=copy.deepcopy(_BASE.context());return values

def check():
    ast.parse(Path(__file__).read_text());_BASE.check()
    actual='                    Total contribution from hydrogen bonds:         0.000 disp.:   -6.169 Tot:    -6.169 kcal/mol\n'
    other={'dispersion_energy_kcal_mol':-6.169,'signed_zero':-0.0,'array':[1.25,None]}
    baseline={HB_FIELD:None,**copy.deepcopy(other)}
    values=copy.deepcopy(baseline);proof=hydrogen_bond_fallback(values,actual)
    assert values[HB_FIELD]==0.0 and proof['fallback_applied'] and proof['rounding_decimal_places']==3
    for key in other:assert repr(values[key])==repr(baseline[key])
    assert struct.pack('>d',values['signed_zero'])==struct.pack('>d',baseline['signed_zero'])
    values={HB_FIELD:-3.5};proof=hydrogen_bond_fallback(values,'HYDROGEN BOND ENERGY = -3.500\n'+actual)
    assert values[HB_FIELD]==-3.5 and not proof['fallback_applied'] and proof['rounding_decimal_places']==3
    values={HB_FIELD:None};proof=hydrogen_bond_fallback(values,actual.replace('0.000','-1.250').replace('-6.169 kcal/mol','-7.419 kcal/mol'))
    assert values[HB_FIELD]==-1.25 and proof['fallback_applied']
    for invalid in ('* DISP - PRINT DISPERSION AND HYDROGEN BOND ENERGIES\n',actual.replace('0.000','*****'),actual.replace('kcal/mol','eV'),actual.replace('Tot:    -6.169','Tot:    *****')):
        values={HB_FIELD:None};proof=hydrogen_bond_fallback(values,invalid);assert values[HB_FIELD] is None and not proof['fallback_applied']
    values={HB_FIELD:None};proof=hydrogen_bond_fallback(values,actual.replace('0.000','1E999'));assert values[HB_FIELD] is None and not proof['fallback_applied']
    # Exercise the wrapper and forwarding path without invoking any computation.
    parent=Path(__file__).parent.parent/'tests';parent.mkdir(exist_ok=True)
    folder=Path(tempfile.mkdtemp(prefix='hb_parser2_fixture_'+str(os.getuid())+'_',dir=parent));prior=_BASE.parse_mopac
    try:
        (folder/'input.out').write_text(actual)
        _BASE.parse_mopac=lambda *args,**kwargs:copy.deepcopy(baseline)
        values=parse_mopac(folder,['H']);assert values[HB_FIELD]==0.0 and values['dispersion_energy_kcal_mol']==baseline['dispersion_energy_kcal_mol']
        assert context()['rounding_decimal_places'][HB_FIELD]==3
    finally:
        _BASE.parse_mopac=prior
        if folder.resolve().parent!=parent.resolve() or not folder.name.startswith('hb_parser2_fixture_'+str(os.getuid())+'_'):raise ValueError('Fixture cleanup scope differs')
        for path in [folder,*folder.rglob('*')]:
            info=path.lstat()
            if info.st_uid!=os.getuid() or not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):raise ValueError('Fixture cleanup owner/type differs')
        shutil.rmtree(folder)
    print(json.dumps({'status':'NATIVE_HB_SUMMARY_FALLBACK_PRIORITY_NULL_PRECISION_FIXTURE_PASS','changed_physical_fields':[HB_FIELD],
        'dispersion_changed':False,'QM_started':False,'LMDB_opened':False,'base_parser_sha256':BASE_SHA}))
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');args=parser.parse_args()
    if args.check:check()
