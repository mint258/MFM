#!/usr/bin/env python3
"""WP5 parser: pinned numerical semantics, transactional header-scoped D4."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import sys
sys.dont_write_bytecode=True
LEGACY_PATH=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010/scripts/wp4_parsers.py')
LEGACY_SHA='66938afa8d3d7b7f51e8922c875c0987687a865a97cb1591d6f6c511b38098e0'
if hashlib.sha256(LEGACY_PATH.read_bytes()).hexdigest()!=LEGACY_SHA:raise ValueError('FROZEN_PARSER_SOURCE_SHA_DIFFERS')
_spec=importlib.util.spec_from_file_location('wp5_pinned_numerics',LEGACY_PATH)
_LEGACY=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_LEGACY)
FLOAT=_LEGACY.FLOAT
EH_TO_EV,BOHR_TO_A,AU_DIPOLE_TO_DEBYE=_LEGACY.EH_TO_EV,_LEGACY.BOHR_TO_A,_LEGACY.AU_DIPOLE_TO_DEBYE
f,scalar,triangle,indexed_table=_LEGACY.f,_LEGACY.scalar,_LEGACY.triangle,_LEGACY.indexed_table
read_aux,sigma_pi_entries=_LEGACY.read_aux,_LEGACY.sigma_pi_entries
ELEMENTS={'H':1,'B':5,'C':6,'N':7,'O':8,'F':9,'Si':14,'P':15,'S':16,'Cl':17,'Se':34,'Br':35,'I':53}
LAST_CONTEXT={}
DELETED_FIELDS={'polar_blocks','static_polar_block','STATIC_finite_field_tensors_bohr3'}
def context():return dict(LAST_CONTEXT)
def decimal_places(token):
    number=token.lower().replace('d','e');mantissa,_,power=number.partition('e')
    return max(0,len(mantissa.partition('.')[2])-int(power or 0))
def d4_table(text,symbols):
    """Only a complete declared atomic D4 table can populate either array."""
    lines=text.splitlines();tables=[];errors=[]
    for start,line in enumerate(lines):
        if not ('covcn' in line.lower() and re.search(r'\bC6(?:AA)?\b',line,re.I) and re.search(r'\bq\b',line)):continue
        rows=[];tokens_record=[];started=False;invalid=False
        for candidate in lines[start+1:]:
            tokens=candidate.split()
            if not tokens or not tokens[0].isdigit():
                if started:break
                continue
            started=True
            if len(tokens)!=7 or not tokens[1].isdigit():invalid=True;break
            index=int(tokens[0])-1
            if index!=len(rows) or index>=len(symbols) or tokens[2]!=symbols[index] or int(tokens[1])!=ELEMENTS.get(tokens[2]):invalid=True;break
            try:values=tuple(f(value) for value in tokens[3:7])
            except ValueError:invalid=True;break
            rows.append(values);tokens_record.append(tokens)
            if len(rows)==len(symbols):break
        if invalid or len(rows)!=len(symbols):errors.append('D4_HEADER_TABLE_INVALID_OR_INCOMPLETE');continue
        tables.append((rows,tokens_record))
    if not tables:return None,errors
    rows,tokens=tables[-1]
    return {'charges_e':[row[1] for row in rows],'D4_atomic_C6_au':[row[2] for row in rows],
      'D4_atomic_alpha_bohr3':[row[3] for row in rows],
      'rounding_decimal_places':{'charges_e':min(decimal_places(t[4]) for t in tokens),
        'D4_atomic_C6_au':min(decimal_places(t[5]) for t in tokens),'D4_atomic_alpha_bohr3':min(decimal_places(t[6]) for t in tokens)},
      'complete_tables':len(tables)},errors

def parse_mopac(directory,symbols,pair_indices=None,reconstruct_mulliken=False):
    global LAST_CONTEXT
    _LEGACY.read_aux=read_aux;_LEGACY.sigma_pi_entries=sigma_pi_entries
    result=_LEGACY.parse_mopac(directory,symbols,pair_indices=pair_indices,reconstruct_mulliken=reconstruct_mulliken)
    suppressed=[];kept=[]
    for line in result.get('property_failure_lines',[]):
        (suppressed if re.search(r'polarizability|\bPOLAR\b',line,re.I) else kept).append(line)
    result['property_failure_lines']=kept
    for name in DELETED_FIELDS:result.pop(name,None)
    LAST_CONTEXT={'family':'mopac','artifacts_present':sorted(path.name for path in Path(directory).iterdir() if path.is_file()),
      'source_deleted_scope_diagnostics':suppressed,'rounding_decimal_places':{},'D4_errors':[]}
    return result

def parse_xtb(directory,symbols):
    global LAST_CONTEXT
    directory=Path(directory);text=(directory/'process.out').read_text(errors='replace')
    result=_LEGACY.parse_xtb(directory,symbols)
    # Override both arrays together, never keep partial appends from legacy.
    table,errors=d4_table(text,symbols)
    result['D4_atomic_C6_au']=table['D4_atomic_C6_au'] if table else []
    result['D4_atomic_alpha_bohr3']=table['D4_atomic_alpha_bohr3'] if table else []
    rounding={}
    if table and result.get('charges_e') is None:
        result['charges_e']=table['charges_e'];rounding['charges_e']=table['rounding_decimal_places']['charges_e']
    if table:rounding.update({key:value for key,value in table['rounding_decimal_places'].items() if key!='charges_e'})
    # xTB without retained JSON: stdout dipole is in atomic units and must use
    # the same conversion constant. Precision is recorded for the regression.
    if result.get('dipole_Debye') is None and 'molecular dipole:' in text:
        part=text.split('molecular dipole:')[-1]
        match=re.search(r'full:\s*('+FLOAT+r')\s+('+FLOAT+r')\s+('+FLOAT+r')',part)
        if match:
            result['dipole_Debye']=[f(value)*AU_DIPOLE_TO_DEBYE for value in match.groups()]
            rounding['dipole_Debye']=min(decimal_places(value) for value in match.groups())
    if result.get('homo_eV') is None or result.get('lumo_eV') is None:
        for name,marker in (('homo_eV','HOMO'),('lumo_eV','LUMO')):
            rows=[line for line in text.splitlines() if re.search(r'\('+marker+r'\)',line)]
            for line in rows[-1:]:
                tokens=line.split();numbers=[token for token in tokens if re.fullmatch(FLOAT,token)]
                if len(numbers)>=3:
                    result[name]=f(numbers[-1]);rounding[name]=decimal_places(numbers[-1])
    for name in ('frequencies_cm_inverse','IR_km_mol','ZPE_Eh','enthalpy_Eh','thermo_tot_H_cal_mol_Cp_cal_mol_K_S_cal_mol_K_S_J_mol_K'):result.pop(name,None)
    LAST_CONTEXT={'family':'xtb','artifacts_present':sorted(path.name for path in directory.iterdir() if path.is_file()),
      'rounding_decimal_places':rounding,'D4_errors':errors,'D4_complete_tables':table['complete_tables'] if table else 0,
      'source_deleted_scope_diagnostics':[]}
    return result

def project_values(task,values):
    keep={
      'xtb_singlepoint':('energy_Eh','dipole_Debye','charges_e','D4_atomic_C6_au','D4_atomic_alpha_bohr3','molecular_quadrupole_traceless_au','wiberg_pairs','homo_eV','lumo_eV'),
      'xtb_vipea':('IP_eV','EA_eV'),'xtb_vfukui':('fukui',),'xtb_ALPB_water':('energy_Eh','Gsolv_Eh'),
      'xtb_ALPB_octanol':('energy_Eh','Gsolv_Eh'),'xtb_fod':('NFOD_e','FOD_atom_e'),
      'xtb_perturbed_gradient':('energy_Eh','gradient_Eh_bohr','forces_eV_A','positions_A','elements','perturb_seed','perturb_sigma_A')}
    if task in keep:return {name:values[name] for name in (*keep[task],'method','version','warnings') if name in values}
    return {name:value for name,value in values.items() if name not in DELETED_FIELDS}

def check():
    import ast;ast.parse(Path(__file__).read_text())
    actual=' # Z covCN q C6AA alpha(0)\n 1 6 C 4.0 -.25 10.50 2.00\n 2 1 H 1.0 .25 1.20 .70\n\n 1 6 C 2 1 H 1.999 (max)\n'
    table,errors=d4_table(actual,['C','H']);assert table['D4_atomic_C6_au']==[10.5,1.2] and table['D4_atomic_alpha_bohr3']==[2.,.7]
    malformed=actual.replace('1.20 .70','1.20 nan');table,_=d4_table(malformed,['C','H']);assert table is None
    without_header=actual.split('\n\n')[-1];table,_=d4_table(without_header,['C','H']);assert table is None
    print('WP5_PARSER_AST_AND_TRANSACTIONAL_D4_FIXTURE_PASS_NO_QM')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:check()
