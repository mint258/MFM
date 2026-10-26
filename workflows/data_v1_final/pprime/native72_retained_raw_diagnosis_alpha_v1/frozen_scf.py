#!/usr/bin/env python3
"""Explicit SCF/SCC metadata from actual output bytes. No process-success inference.

scf_iterations is the sum of the software-reported iteration count for every
observed completed SCC/SCF stage. An unfinished/unquantified observed stage makes
the aggregate NULL. Configured max iterations and number of SCF calculations
are never accepted as measured iteration counts. Stage evidence is retained.
"""
from __future__ import annotations
import argparse, ast, hashlib, re
from pathlib import Path
VERSION='WP5_SCF_METADATA_V2'
SOURCES=[
 'https://openmopac.net/Manual/Formic_Acid_output.html',
 'https://openmopac.net/Manual/pl.html',
 'https://github.com/grimme-lab/xtb/issues/190',
 'https://github.com/grimme-lab/xtb/issues/694']
XTB_SUCCESS=re.compile(r'convergence criteria satisfied after\s+(\d+)\s+iterations?',re.I)
XTB_FAIL=re.compile(r'(?:self\s*consistent charge iterator did not converge|SCC\s+(?:IS\s+)?(?:FAILED|NOT CONVERGED)|SCC.{0,60}(?:failed to converge|did not converge)|SCF.{0,60}(?:failed to converge|did not converge))',re.I)
MOPAC_SUCCESS=re.compile(r'(?:SCF FIELD WAS ACHIEVED|SCF CONVERGED(?:\s+AFTER\s+\d+\s+ITERATIONS?)?)',re.I)
MOPAC_FAIL=re.compile(r'(?:SCF DOES NOT CONVERGE|SCF FAILED|SCF (?:IS |NOT )?NOT CONVERGED|UNABLE TO ACHIEVE (?:AN? )?SCF|UNABLE TO ACHIEVE SELF-CONSISTENCY)',re.I)
MOPAC_COUNT=re.compile(r'SCF CONVERGED\s+AFTER\s+(\d+)\s+ITERATIONS?',re.I)
TABLE_HEADER=re.compile(r'\biter\b.*\bdE\b.*\bRMSdq\b',re.I)
TABLE_ROW=re.compile(r'^\s*(\d+)\s+[-+]?\d+\.\d+(?:[EDed][-+]?\d+)?\s+[-+]?\d')
def _texts(files):
    if isinstance(files,dict):files=[{'name':k,'data':v} for k,v in files.items()]
    result={}
    for item in files or []:
        name=Path(item['name']).name;data=item.get('data')
        if isinstance(data,str):data=data.encode()
        if not isinstance(data,(bytes,bytearray)):continue
        if name in {'input.out','process.out','input.aux'}:
            result[name]=(bytes(data).decode('utf-8',errors='replace'),hashlib.sha256(data).hexdigest())
    return result
def _evidence(name,line,text,sha):
    return {'file':name,'line_1_based':line,'text':text.strip()[:500],'file_sha256':sha}
def extract_scf(calc_type,files,parsed_values=None,status=None,source_status=None):
    """Return canonical trace fields plus explicit evidence; parsed/status ignored.

    A signal after a converged electronic cycle can correctly yield converged
    True with CALCULATION_FAILED status. Missing markers produce NULL.
    MOPAC input.out is preferred over its duplicate process.out.
    """
    texts=_texts(files);xtb=str(calc_type).startswith('xtb_');stages=[];evidence=[]
    method='xTB_SCC' if xtb else 'MOPAC_conventional_SCF'
    name='process.out' if xtb else ('input.out' if 'input.out' in texts else 'process.out')
    definition='SUM_EXPLICIT_COUNTS_ALL_OBSERVED_STAGES; UNFINISHED_OR_UNQUANTIFIED_STAGE_NULL'
    if name not in texts:
        return {'scf_iterations':None,'converged':None,'method':method,
          'iteration_definition':definition,'stages':[],'evidence':[],
          'missing_reason':'ACTUAL_ELECTRONIC_ITERATION_OUTPUT_UNAVAILABLE','schema':VERSION}
    text,sha=texts[name];current=None
    for lineno,line in enumerate(text.splitlines(),1):
        ev=_evidence(name,lineno,line,sha)
        if xtb:
            if TABLE_HEADER.search(line):
                if current is not None and current['terminal'] is None:stages.append(current)
                current={'stage_index':len(stages)+1,'iterations':None,'converged':None,
                         'terminal':None,'table_last_iteration':None,'evidence':[ev]}
                continue
            if current is not None and current['terminal'] is None:
                hit=TABLE_ROW.match(line)
                if hit:current['table_last_iteration']=int(hit[1])
            good=XTB_SUCCESS.search(line);bad=XTB_FAIL.search(line)
            if not good and not bad:continue
            # Some valid outputs omit a table; the explicit terminal count
            # itself defines a stage. Repeated failure diagnostics do not
            # create another numerical stage.
            if current is None or current['terminal'] is not None:
                if bad and stages and stages[-1]['converged'] is False:
                    stages[-1]['evidence'].append(ev);evidence.append(ev);continue
                current={'stage_index':len(stages)+1,'iterations':None,'converged':None,
                         'terminal':None,'table_last_iteration':None,'evidence':[]}
            current['converged']=False if bad else True
            current['terminal']='FAILED_MARKER' if bad else 'CONVERGED_MARKER'
            current['iterations']=current['table_last_iteration'] if bad else int(good[1])
            current['evidence'].append(ev);evidence.append(ev);stages.append(current);current=None
        else:
            good=MOPAC_SUCCESS.search(line);bad=MOPAC_FAIL.search(line)
            if not good and not bad:continue
            count=MOPAC_COUNT.search(line)
            stages.append({'stage_index':len(stages)+1,'iterations':int(count[1]) if count else None,
                'converged':False if bad else True,'terminal':'FAILED_MARKER' if bad else 'CONVERGED_MARKER',
                'table_last_iteration':None,'evidence':[ev]})
            evidence.append(ev)
    if current is not None and current['terminal'] is None:stages.append(current)
    # MOPAC repeats achieved markers in summaries. Those are evidence of SCF,
    # not separate independently quantifiable iterations. Do not sum them.
    if not xtb and stages:
        explicit=[s['iterations'] for s in stages if s['iterations'] is not None]
        count=explicit[0] if len(explicit)==1 else None
        converged=False if any(s['converged'] is False for s in stages) else True
        definition='MOPAC_EXPLICIT_SCF_ITERATION_COUNT_ONLY; SCF_CALCULATIONS_AND_LIMITS_NOT_ITERATIONS'
    else:
        count=sum(s['iterations'] for s in stages) if stages and all(s['iterations'] is not None for s in stages) else None
        converged=False if any(s['converged'] is False for s in stages) else (True if stages and all(s['converged'] is True for s in stages) else None)
    missing=[]
    if not stages:missing.append('NO_EXPLICIT_SCF_SCC_TERMINAL_OR_ITERATION_TABLE')
    if count is None:missing.append('ITERATION_COUNT_NOT_FULLY_REPORTED')
    if converged is None:missing.append('CONVERGENCE_NOT_EXPLICITLY_REPORTED_FOR_ALL_OBSERVED_STAGES')
    return {'scf_iterations':count,'converged':converged,'method':method,
        'iteration_definition':definition,'stages':stages,'evidence':evidence,
        'missing_reason':';'.join(missing) or None,'schema':VERSION}
def check():
    def x(text,status='SUCCESS'):
        return extract_scf('xtb_vipea',[{'name':'process.out','data':text.encode()}],status=status)
    assert x('max. iterations 250')['scf_iterations'] is None
    assert x('normal termination of xtb')['converged'] is None
    a=x('*** convergence criteria satisfied after 7 iterations ***\n*** convergence criteria satisfied after 8 iterations ***')
    assert a['scf_iterations']==15 and a['converged'] is True and len(a['stages'])==2
    a=x('*** convergence criteria satisfied after 8 iterations ***\nSIGSEGV','CALCULATION_FAILED')
    assert a['converged'] is True
    a=x('iter E dE RMSdq gap\n1 -1.000 0.100 0.01\n2 -1.100 -0.100 0.02\nSelf consistent charge iterator did not converge')
    assert a['converged'] is False and a['scf_iterations']==2
    a=x('*** convergence criteria satisfied after 4 iterations ***\niter E dE RMSdq gap\n1 -2.000 0.100 0.01')
    assert a['converged'] is None and a['scf_iterations'] is None
    a=extract_scf('pm7_B',[{'name':n,'data':b'SCF FIELD WAS ACHIEVED\nSCF CALCULATIONS = 1'} for n in ('input.out','process.out')])
    assert a['converged'] is True and a['scf_iterations'] is None and len(a['stages'])==1
    assert extract_scf('pm7_B',[{'name':'input.out','data':b'UNABLE TO ACHIEVE SELF-CONSISTENCY'}])['converged'] is False
    assert x('SCC IS NOT CONVERGED')['converged'] is False
    a=extract_scf('pm7_B',[])
    assert a['converged'] is None and a['scf_iterations'] is None
    ast.parse(Path(__file__).read_text());print('SCF_METADATA_CHECK_PASS')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:check()
