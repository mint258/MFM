"""Bounded scalar/header JSON reduction of the closed3505 local-operator cohort."""
from __future__ import annotations
import argparse
import csv
import hashlib
import itertools
import io
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import time

BASE=Path('/share/home/zixiao/descriptor_analysis')
HERE=Path(__file__).absolute().parent
PRODUCER=BASE/'runs/model_v3_20261026/encoder_local_op_precision_v1_source'
CAPTURE=BASE/'runs/model_v3_20261025/encoder_local_op_precision_GPU_v1_4523505'
MANIFEST=CAPTURE/'CAPTURE_MANIFEST.json'
ROOT_CLOSURE=BASE/'runs/model_v3_20261026/encoder_local_op_precision_GPU_4523505_Root_metadata_closure_v1.json'
INPUT_LIMIT=64 << 20
OUTPUT_LIMIT=128 << 20
TERMS=('F32_D','F64_same_actual_input_D','arithmetic_residual','base_local_error','moved_local_error')
TARGETS=TERMS[:3]
TRANSFORMS=('general_rotation','translation_only','other_rotation_and_translation')
FACTORS=tuple(itertools.product(('C1-0','C1-a','C1-b'),('two','three'),
    ('H1_fixed','H1_learned','H2_fixed','H3_fixed'),(20261026,20261027)))
FIELDS=('PD__p_extensive','PD__p_intensive','PD__d_intensive','PD__d_binary','PD__d_atom',
    'PD__p_pair','PD__p_gradient','PD__p_dipole','PD__p_dipole_magnitude','S__noise',
    'S__coordinate','S__element_logits','S__clean_bond_logits')
TERMINALS={prefix+'__'+field for prefix in ('original','transform0','transform1','transform2') for field in FIELDS}


def need(ok,message):
    if not ok:raise ValueError(message)


def canon(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)


def integer(value,minimum=0):
    need(type(value) is int and value>=minimum,'Finite non-boolean integer required')
    return value


def number(value):
    need(type(value) in (int,float) and math.isfinite(value),'Finite non-boolean scalar required')
    return float(value)


def digest(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None,'Exact raw SHA256 required')
    return value


def unique_pairs(items):
    result={}
    for key,value in items:
        need(key not in result,'Duplicate JSON key');result[key]=value
    return result


class Inputs:
    def __init__(self):self.refs={};self.identities={};self.started=time.monotonic()
    def tick(self):need(time.monotonic()-self.started<180,'Metadata analysis deadline180s exceeded')
    def read(self,path,expected=None,maximum=2 << 20):
        self.tick();path=Path(path)
        need(path.is_absolute() and str(path)==os.path.normpath(path),'Absolute normalized input path required')
        for parent in (path,*path.parents):need(not parent.is_symlink(),'Input symlink/ancestor forbidden')
        a=path.lstat();need(stat.S_ISREG(a.st_mode) and a.st_uid==os.getuid() and a.st_nlink==1
            and 0<a.st_size<=maximum,'Owned bounded ordinary metadata/source required')
        if str(path) not in self.refs:
            need(sum(r['bytes'] for r in self.refs.values())+a.st_size<=INPUT_LIMIT,'Selected metadata exceeds64MiB')
        raw=path.read_bytes();b=path.lstat()
        need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'Input changed while reading')
        ref={'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
        if expected is not None:
            need(set(expected)=={'path','bytes','sha256'} and type(expected['bytes']) is int
                and expected['bytes']>0 and digest(expected['sha256']) and canon(ref)==canon(expected),'Bound raw input differs')
        need(str(path) not in self.refs or self.refs[str(path)]==ref,'Repeated input reference conflicts')
        self.refs[str(path)]=ref;self.identities[str(path)]=(a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)
        return ref,raw
    def json(self,path,expected=None,maximum=2 << 20):
        ref,raw=self.read(path,expected,maximum)
        return json.loads(raw,object_pairs_hook=unique_pairs,
            parse_constant=lambda value:(_ for _ in ()).throw(ValueError('Nonfinite JSON constant'))),ref
    def after(self):
        before=dict(self.refs);identities=dict(self.identities)
        for path,ref in before.items():
            self.read(path,ref)
            a=Path(path).lstat()
            need(identities[path]==(a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns),'Input identity changed')
        return dict(self.refs)


def source_gate(inputs,sha):
    pins,pin=inputs.json(HERE/'source_pins.json')
    need(pin['sha256']==digest(sha) and pins['schema']=='model_v3_encoder_local_op_metadata_sources_v1','Frozen reducer source required')
    need({row['file'] for row in pins['files']}=={'reducer.py','METHOD.md'} and len(pins['files'])==2,'Exact two reducer leaves required')
    for row in pins['files']:
        need(Path(row['file']).name==row['file'],'Flat source leaf required')
        inputs.read(HERE/row['file'],{'path':str(HERE/row['file']),'bytes':row['bytes'],'sha256':row['sha256']})
    for ref in pins['producer_sources']+pins['support_sources']:inputs.read(ref['path'],ref)
    return pin,pins['root_actual_closure']


def root_gate(inputs,sha,manifest_ref,expected):
    closure,ref=inputs.json(ROOT_CLOSURE,expected,maximum=4 << 20)
    need(ref['sha256']==digest(sha),'Explicit Root actual closure rawSHA differs')
    need(closure['schema']=='model_v3_encoder_local_op_GPU_Root_closure_v1'
        and closure['status']=='ACTUAL_C0_FULL48_LOCAL_CAPTURE_SOURCE_AND_RESOURCE_CLOSED'
        and closure['job_id']=='4523505' and canon(closure['capture_manifest'])==canon(manifest_ref),'Actual Root3505 closure differs')
    expected_counts={'cases':48,'encoder_forwards':192,'original_terminal_controls':2496,
        'local_module_replay_calls':5312,'local_F64_reference_calls':5312,'local_operator_observations':4368,
        'physics_passed':21,'physics_failed':27}
    need(canon(closure['counts'])==canon(expected_counts),'Root closed matrix counts differ')
    account=closure['actual_parent']
    need(type(account['returncode']) is int and account['returncode']==0 and type(account['stdout']) is str
        and account['argv']==['sacct','-n','-P','-j','4523505','--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],
        'Root actual parent accounting command differs')
    parents=[line.split('|') for line in account['stdout'].splitlines() if line.split('|')[0]=='4523505']
    need(len(parents)==1 and len(parents[0])==7 and parents[0][1:4]==['zixiao','COMPLETED','0:0']
        and parents[0][4].isdigit() and parents[0][5:] == ['16','compute-0-21'],'Root actual Slurm parent is not exactC0')
    limits={'CPU':16,'RAM_MiB':32768,'RSS_bytes':30064771072,'child_seconds':1100,
        'artifact_bytes':134217728,'whole_bytes':2147483648,'private_bytes':2147483648}
    need(canon(closure['resource_limits'])==canon(limits),'Original GPU resource envelope differs')
    need(all(closure[key] is False for key in ('physics_adoption','H0_API_changed','C4_acceptance_changed','reference_outputs_injected'))
        and integer(closure['full_FP64_encoder_forwards'])==0
        and closure['local_reference_scope']=='INDEPENDENT_REAL_FORMULA_ALGORITHM_AND_FP64_NOT_DTYPE_ONLY','Root scientific scope differs')
    need(canon(closure['source_pins'])==canon(inputs.refs[str(PRODUCER/'source_pins_v1.json')])
        and canon(closure['execution_request'])==canon(inputs.refs[str(PRODUCER/'execution_request_v1.json')]),'Root producer source/request differs')
    before,_=inputs.read(closure['source_before']['path'],closure['source_before'])
    after,_=inputs.read(closure['source_after']['path'],closure['source_after'])
    need(before['bytes']==after['bytes'] and before['sha256']==after['sha256']
        and integer(closure['current_source_metadata_rawrefs_verified'],1)==1354,'Root producer source snapshots differ')
    complete,_=inputs.json(closure['capture_complete']['path'],closure['capture_complete'])
    need(complete['schema']=='model_v3_encoder_local_op_complete_v1' and canon(complete['manifest'])==canon(manifest_ref),'Actual capture COMPLETE differs')
    supervisor,_=inputs.json(closure['supervisor']['path'],closure['supervisor'])
    need(supervisor['job_id']=='4523505' and supervisor['status']=='COMPLETED' and type(supervisor['exit_code']) is int
        and supervisor['exit_code']==0 and supervisor['first_failure'] is None and supervisor['retirement'] is None
        and supervisor['remaining_recorded_processes_before_retirement']==[] and supervisor['private_storage_cleanup_errors']==[]
        and supervisor['foreign_gpu_processes_signalled'] is False and supervisor['private_storage_final']['first_sampling_failure'] is None,
        'Actual GPU supervisor/cleanup closure differs')
    census=closure['closed_control_output_census'];private=closure['private_storage_sampled']
    need(census['output_root']==str(CAPTURE) and census['cap_bytes']==2 << 30
        and 0<=number(census['conservative_total_bytes'])<=2 << 30 and census['uses_original_owned_output_bytes'] is True
        and private['budget_bytes']==2 << 30 and private['first_sampling_failure'] is None
        and integer(closure['observed_foreign_GPU_records'])==0,'Root closed output/private observation differs')
    need(len(closure['capture_cases'])==48,'Root must independently bind all48 case JSON refs')
    return ref,closure


def topology(distance):
    names={f'layer{i}.{suffix}' for i in range(6) for suffix in ('norm1','norm2','attn','ffn')}
    names.add('out_norm')
    if distance=='C1-0':names.update(f'layer{i}.distance_mlp' for i in range(6))
    else:names.add('shared_pair_encoder')
    ports={name:2 if (distance=='C1-0' and name.endswith('.attn')) or name=='shared_pair_encoder' else 1 for name in names}
    return names,ports


def scalar_record(value):
    need(type(value) is dict and set(value)=={'rows','channels','components','maxabs','squared_sum','rms','argmax','signed_at_argmax'},'Saved scalar record schema differs')
    rows=integer(value['rows'],1);channels=integer(value['channels'],1);components=integer(value['components'],1)
    need(rows*channels==components,'Saved denominator differs')
    maximum=number(value['maxabs']);squared=number(value['squared_sum']);rms=number(value['rms']);signed=number(value['signed_at_argmax'])
    need(maximum>=0 and squared>=0 and rms>=0 and abs(signed)==maximum,'Saved max/sign differs')
    need(math.isclose(rms,math.sqrt(squared/components),rel_tol=1e-12,abs_tol=1e-14),'Saved RMS/squared population differs')
    index=value['argmax'];need(type(index) is list and len(index)==2,'Typed argmax required')
    need(integer(index[0])<rows and integer(index[1])<channels,'Argmax outside actual population')
    return components


def close(a,b):return math.isclose(number(a),number(b),rel_tol=0,abs_tol=1e-10)


def operator_family(module):return module.split('.',1)[1] if module.startswith('layer') else module


def expected_class(module,distance):
    if module.endswith(('norm1','norm2')) or module=='out_norm':return 'LayerNorm'
    if module.endswith('.ffn'):return 'DenseFFN'
    if module.endswith('.attn'):return 'DenseGeoSelfAttention' if distance=='C1-0' else 'SharedPairAttention'
    return 'TiledDistanceMLP' if module.endswith('.distance_mlp') else 'SharedGaussianPairEncoder'


def column_names():
    keys=['case_id','distance_bias','views','head_policy','weight_seed','operator_class','module','module_family',
        'layer','port','transform','population','rows','channels','components','native_nodes','native_nodes_by_graph',
        'signed_closure_maxabs','capture_sha256','local_sha256','input_drift_json']
    for term in TERMS:keys.extend(term+'__'+k for k in ('maxabs','rms','squared_sum','argmax_row','argmax_channel','signed_at_argmax'))
    for target in TARGETS:keys.extend(target+'__at__'+k for k in ('physical_row','channel_or_head',*TERMS))
    return keys


def process_case(case,local,row,writer,groups,counters):
    factors=case['case'];distance,views,head,seed=(factors[k] for k in ('distance_bias','views','head_policy','weight_seed'))
    need(type(seed) is int and (distance,views,head,seed) in FACTORS,'Exact four-factor case required')
    identity=f'{distance}__{views}__{head}__seed{seed}'
    need(case['schema']=='model_v3_encoder_local_op_case_v1' and case['case_id']==row['case_id']==identity,'Case identity differs')
    need(case['packed'] is None and case['same_forward_control'] is True,'Only saved scalar/header local-op case admitted')
    need(case['centered_lineage']=='fresh_centered_local_op_run_baseline1838_header_gate','Fresh centered lineage differs')
    need(all(row[k] is True for k in ('baseline_H0_bitwise','local_replay_bitwise','external1838_terminal_control_passed')),'Manifest per-case replay gates differ')
    h0=case['baseline1838_H0_controls'];need(len(h0)==4 and [integer(x['role']) for x in h0]==[0,1,2,3],'All four H0 roles required')
    for item in h0:need(item['bitwise_value_SHA_equal'] is True and canon(item['actual'])==canon(item['baseline1838']),'Baseline H0 replay differs')
    terminal=case['external1838_terminal_control'];names=[x['array'] for x in terminal['arrays']]
    need(terminal['scope']=='ALL52_ACTUAL1838_EXTERNAL_TERMINALS' and len(names)==52 and set(names)==TERMINALS
        and terminal['passed'] is True and all(x['bitwise_equal'] is True for x in terminal['arrays']),'Complete external terminal gate differs')
    need(type(row['physics_passed']) is bool and case['original_measurement']['passed'] is row['physics_passed']
        and terminal['baseline_physics_passed'] is row['physics_passed'] and terminal['new_physics_passed'] is row['physics_passed'],'Original physical matrix differs')
    need([x['name'] for x in case['transforms']]==list(TRANSFORMS),'All original transforms required')
    modules,ports=topology(distance);controls=local['module_controls']
    need(len(controls)==len(modules) and {x['module'] for x in controls}==modules,'All original local modules required')
    class_by_module={}
    for control in controls:
        name=control['module'];cls=control['state_mapping']['original_class'];class_by_module[name]=cls
        need(cls==expected_class(name,distance) and control['state_mapping']['scope']=='INDEPENDENT_REAL_FORMULA_ALGORITHM_AND_FP64_NOT_DTYPE_ONLY','Reference algorithm/precision scope differs')
        roles=control['roles'];need(len(roles)==4,'Complete original plus three moved roles required')
        for role in roles:
            replay=role['replay'];context=role['context']
            need(len(replay)==ports[name] and all(x['bitwise_equal'] is True and canon(x['original'])==canon(x['replayed']) for x in replay),'Full raw local replay differs')
            need(context['training'] is False and context['grad_enabled'] is False and context['inference_mode'] is True
                and context['autocast_cuda'] is False and context['replay_uses_original_input_objects'] is True
                and context['hooks_removed_before_replay'] is True,'Actual local replay context differs')
    observations=local['observations'];expected={(name,port,t) for name in modules for port in range(ports[name]) for t in TRANSFORMS}
    actual=[(o['module'],integer(o['port']),o['transform']) for o in observations]
    need(len(actual)==len(expected) and len(set(actual))==len(actual) and set(actual)==expected,'Missing/duplicate port-transform observations')
    need(local['all_local_F32_replays_bitwise'] is True and integer(local['F64_encoder_forwards'])==0
        and local['reference_outputs_injected'] is False and local['local_module_count']==len(modules)
        and local['module_calls_per_role']==len(modules),'Saved local coverage/gates differ')
    need(row['local_module_count']==len(modules) and row['local_operator_observations']==len(observations),'Manifest/case local counts differ')
    for o in observations:
        name=o['module'];layer=None if name in ('out_norm','shared_pair_encoder') else int(name[5])
        need(o['layer'] is None if layer is None else type(o['layer']) is int and o['layer']==layer,'Layer identity differs')
        need(o['whole_model_cause_or_causal_layer_ranking'] is False,'Saved scope cannot claim whole-model causality')
        population=o['population'];stats=o['statistics'];need(set(stats)==set(TERMS),'All five signed terms required')
        count=scalar_record(stats[TERMS[0]])
        for term in TERMS[1:]:need(scalar_record(stats[term])==count and stats[term]['rows']==stats[TERMS[0]]['rows'] and stats[term]['channels']==stats[TERMS[0]]['channels'],'Unlike term populations')
        need(integer(population['rows'],1)==stats[TERMS[0]]['rows'] and integer(population['channels'],1)==stats[TERMS[0]]['channels'],'Actual saved population differs')
        native=integer(population['native_nodes'],1);by_graph=population['native_nodes_by_graph']
        need(len(by_graph)==(6 if views=='two' else 9) and sum(integer(x,1) for x in by_graph)==native
            and native==(88 if views=='two' else 132),'Actual native physical-view population differs')
        closure=number(o['signed_closure_maxabs']);need(0<=closure<=1e-10,'Saved signed closure exceeds original bound')
        same=o['same_component'];need(set(same)=={t+'_argmax' for t in TARGETS},'Three same-component extrema required')
        for target in TARGETS:
            at=same[target+'_argmax'];values=at['signed_tuple']
            need(set(values)==set(TERMS) and [integer(at['physical_row']),integer(at['channel_or_head'])]==stats[target]['argmax'],'Same-component identity differs')
            for value in values.values():number(value)
            need(values[target]==stats[target]['signed_at_argmax'],'Target signed extrema differs')
            need(close(values['F32_D']-values['F64_same_actual_input_D'],values['arithmetic_residual'])
                and close(values['moved_local_error']-values['base_local_error'],values['arithmetic_residual']),'Same-component signed algebra differs')
        for drift in o['input_drift']:
            scalar_record(drift['physical_input_drift'])
            need(drift['kind'] in ('node','pair','position') and drift['law']==('x@R+t' if drift['kind']=='position' else 'invariant'),'Saved actual-input transformation law differs')
        out={'case_id':identity,**factors,'operator_class':class_by_module[name],'module':name,'module_family':operator_family(name),
            'layer':'' if layer is None else layer,'port':o['port'],'transform':o['transform'],'population':population['population'],
            'rows':population['rows'],'channels':population['channels'],'components':count,'native_nodes':native,
            'native_nodes_by_graph':canon(by_graph),'signed_closure_maxabs':closure,'capture_sha256':row['capture_case']['sha256'],
            'local_sha256':case['local_module_statistics']['sha256'],'input_drift_json':canon(o['input_drift'])}
        for term in TERMS:
            statrow=stats[term]
            out.update({term+'__'+k:statrow[k] for k in ('maxabs','rms','squared_sum','signed_at_argmax')})
            out[term+'__argmax_row'],out[term+'__argmax_channel']=statrow['argmax']
        for target in TARGETS:
            at=same[target+'_argmax'];out.update({target+'__at__'+k:at[k] for k in ('physical_row','channel_or_head')})
            out.update({target+'__at__'+k:v for k,v in at['signed_tuple'].items()})
        writer.writerow(out)
        key=canon({'distance_bias':distance,'views':views,'operator_class':class_by_module[name],'module':name,
            'module_family':operator_family(name),'layer':layer,'port':o['port'],'transform':o['transform'],'population':population})
        group=groups.setdefault(key,{'cases':[],'terms':{t:[] for t in TERMS},'max_closure':0})
        group['cases'].append(identity);group['max_closure']=max(group['max_closure'],closure)
        for term in TERMS:group['terms'][term].append(stats[term])
    counters['observations']+=len(observations);counters['module_calls']+=4*len(modules)
    counters['H0_controls']+=4;counters['external_terminals']+=52;counters['physics_passed']+=row['physics_passed']


def aggregate(groups):
    result=[]
    for key,value in sorted(groups.items()):
        members=value['cases'];need(len(members)==8 and len(set(members))==8,'Each exact group must cover all four heads and two seeds')
        terms={}
        for term,rows in value['terms'].items():
            components=sum(row['components'] for row in rows);squared=math.fsum(row['squared_sum'] for row in rows)
            terms[term]={'observations':len(rows),'components':components,'squared_sum':squared,
                'pooled_rms':math.sqrt(squared/components),'maxabs':max(row['maxabs'] for row in rows)}
        result.append({**json.loads(key),'case_count':len(members),'member_case_ids':sorted(members),
            'terms':terms,'max_signed_closure':value['max_closure']})
    return result


def artifacts(output):
    refs=[]
    for path in sorted(output.iterdir()):
        a=path.lstat();need(stat.S_ISREG(a.st_mode) and not path.is_symlink() and a.st_uid==os.getuid() and a.st_nlink==1,'Owned regular output required')
        refs.append({'path':str(path),'bytes':a.st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    need(sum(r['bytes'] for r in refs)<=OUTPUT_LIMIT,'Metadata artifacts exceed128MiB')
    return refs


def write_bytes(path,raw):
    used=sum(p.lstat().st_size for p in path.parent.iterdir())
    need(used+len(raw)<=OUTPUT_LIMIT,'Selected metadata artifacts exceed128MiB')
    with path.open('xb') as stream:stream.write(raw)


def write_json(path,value):
    write_bytes(path,(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode())


class LimitedCSV:
    def __init__(self,stream):self.stream=stream;self.size=0
    def write(self,text):
        raw=text.encode('utf-8');need(self.size+len(raw)<=OUTPUT_LIMIT,'CSV exceeds128MiB')
        self.size+=len(raw);return self.stream.write(text)


def plots(output,groups,inputs):
    scratch=Path('/tmp')/('mv3n_'+os.environ['SLURM_JOB_ID'])
    need(os.environ.get('TMPDIR')==str(scratch) and scratch.is_dir() and not scratch.is_symlink()
        and scratch.stat().st_uid==os.getuid(),'Original supervised private scratch required for plotting cache')
    config=scratch/'matplotlib';config.mkdir(mode=0o700)
    os.environ['MPLCONFIGDIR']=str(config)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FixedLocator,FuncFormatter,NullFormatter

    def readable_ticks(coordinate):
        low,high=sorted(float(value) for value in coordinate.get_view_interval())
        need(math.isfinite(low) and math.isfinite(high) and low<high,'Finite original view interval required')
        visible=sorted({float(value) for value in coordinate.get_major_locator()()
            if math.isfinite(float(value)) and low<=float(value)<=high})
        if len(visible)>4:
            indices={round(index*(len(visible)-1)/3) for index in range(4)}
            if 0.0 in visible:
                zero=visible.index(0.0)
                if zero not in indices:
                    replace=min(indices-{0,len(visible)-1},key=lambda index:(abs(index-zero),index))
                    indices.remove(replace);indices.add(zero)
            coordinate.set_major_locator(FixedLocator([visible[index] for index in sorted(indices)]))
        elif not visible:
            transform=coordinate.get_transform()
            left,right=(float(value) for value in transform.transform([low,high]))
            positions=transform.inverted().transform([left+fraction*(right-left) for fraction in (.12,.50,.88)])
            ticks=[float(value) for value in positions]
            need(len(set(ticks))==3 and all(math.isfinite(value) and low<=value<=high for value in ticks),
                'Three distinct in-range transformed ticks required')
            coordinate.set_major_locator(FixedLocator(ticks))
            coordinate.set_major_formatter(FuncFormatter(lambda value,position:format(value,'.2e')))
        # With one to four visible majors, keep the original locator and formatter.
        coordinate.set_minor_formatter(NullFormatter())
    facets={}
    for row in groups:
        p=row['population']
        key=(row['operator_class'],row['module_family'],row['port'],p['population'],p['rows'],p['channels'])
        facets.setdefault(key,[]).append(row)
    need(0<len(facets)<=32,'Bounded homogeneous plot facet count required')
    colors=dict(zip(TRANSFORMS,('tab:blue','tab:orange','tab:green')))
    markers={'C1-0':'o','C1-a':'s','C1-b':'^'}
    for index,(xterm,yterm) in enumerate(((TERMS[0],TERMS[1]),(TERMS[1],TERMS[2])),1):
        inputs.tick();cols=4;rows=math.ceil(len(facets)/cols)
        fig,axes=plt.subplots(rows,cols,figsize=(16,3.1*rows),squeeze=False)
        for axis,(key,values) in zip(axes.flat,sorted(facets.items())):
            for row in values:
                axis.scatter(row['terms'][xterm]['pooled_rms'],row['terms'][yterm]['pooled_rms'],s=12,
                    color=colors[row['transform']],marker=markers[row['distance_bias']],alpha=.65)
            axis.set_xscale('symlog',linthresh=1e-16);axis.set_yscale('symlog',linthresh=1e-16)
            for coordinate in (axis.xaxis,axis.yaxis):
                readable_ticks(coordinate)
            axis.set_title('%s / %s / port%s\n%s rows%s channels%s'%key,fontsize=8)
            axis.grid(alpha=.2)
        for axis in list(axes.flat)[len(facets):]:axis.set_visible(False)
        fig.supxlabel(xterm+' pooled RMS');fig.supylabel(yterm+' pooled RMS')
        fig.suptitle('Fixed48 cohort; same operator/port/population per panel. Algorithm + FP64 contrast.\n'
            'Color: general rotation / translation / combined. Marker: C1-0 circle, C1-a square, C1-b triangle.\n'
            'Each point retains one layer + transform + C1; pools four heads x two seeds by squared sums.',fontsize=9)
        fig.tight_layout(rect=(.025,.025,1,.95));buffer=io.BytesIO();fig.savefig(buffer,format='png',dpi=120)
        write_bytes(output/f'contrast_{index}.png',buffer.getvalue());buffer.close()
        plt.close(fig);inputs.tick();artifacts(output)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root-closure-sha256',required=True)
    parser.add_argument('--source-pins-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--expected-node',required=True)
    parser.add_argument('--no-plots',action='store_true')
    args=parser.parse_args();inputs=Inputs()
    need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID','').isdigit() and os.environ.get('SLURM_JOB_PARTITION')=='cpu'
        and os.environ.get('SLURM_CPUS_PER_TASK')=='16' and os.environ.get('CUDA_VISIBLE_DEVICES')==''
        and socket.gethostname().split('.')[0]==args.expected_node,'Actual owned CPU16 allocation required')
    source_pin,expected_closure=source_gate(inputs,args.source_pins_sha256)
    manifest,mref=inputs.json(MANIFEST)
    need(canon(manifest['source_pins'])==canon(inputs.refs[str(PRODUCER/'source_pins_v1.json')])
        and canon(manifest['request'])==canon(inputs.refs[str(PRODUCER/'execution_request_v1.json')]),'Actual producer request/source refs differ')
    root_ref,closed=root_gate(inputs,args.root_closure_sha256,mref,expected_closure)
    need(manifest['schema']=='model_v3_encoder_local_op_manifest_v1' and manifest['status']=='CAPTURE_COMPLETE'
        and manifest['job_id']=='4523505' and manifest['failure'] is None and manifest['source_before_after_equal'] is True,'Complete bound3505 capture required')
    need(all(manifest[k] is True for k in ('all_baseline_H0_bitwise','all_local_replays_bitwise','external1838_terminal_replay_passed'))
        and integer(manifest['full_FP64_encoder_forwards'])==0 and manifest['reference_outputs_injected'] is False
        and manifest['physics_adoption'] is False,'Original replay/reference scope differs')
    need(manifest['encoder_forwards']==manifest['completed_case_encoder_forwards']==192
        and manifest['local_module_replay_calls']==manifest['local_F64_reference_calls']==5312
        and manifest['local_operator_observations']==4368 and manifest['physics_case_passed']==21,'Complete original matrix counts differ')
    expected=[f'{a}__{b}__{c}__seed{d}' for a,b,c,d in FACTORS]
    need([x['case_id'] for x in manifest['cases']]==expected,'Exact ordered48 factor population required')
    output=args.output.absolute();need(str(output).startswith(str(BASE/'runs')+'/') and not os.path.lexists(output),'Fresh model-owned output required')
    for parent in output.parents:need(not parent.is_symlink(),'Output symlink ancestor forbidden')
    output.mkdir(mode=0o700)
    counters={'observations':0,'module_calls':0,'H0_controls':0,'external_terminals':0,'physics_passed':0};groups={}
    with (output/'observations.csv').open('x',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(LimitedCSV(stream),fieldnames=column_names());writer.writeheader()
        for index,row in enumerate(manifest['cases']):
            inputs.tick();case_path=CAPTURE/f'case_{index:02d}'/'CAPTURE_CASE.json'
            need(row['capture_case']['path']==str(case_path),'Exact case metadata path differs')
            case,_=inputs.json(case_path,row['capture_case']);local_path=case_path.parent/'LOCAL_MODULES.json'
            need(case['local_module_statistics']['path']==str(local_path),'Exact local scalar metadata path differs')
            local,_=inputs.json(local_path,case['local_module_statistics'])
            independent=closed['capture_cases'][index]
            need(independent['case_id']==case['case_id'] and canon(independent['case'])==canon(case['case'])
                and canon(independent['capture_case'])==canon(row['capture_case'])
                and canon(independent['local_module_statistics'])==canon(case['local_module_statistics'])
                and all(independent['controls'][key] is True for key in
                    ('baseline_H0_bitwise','external1838_terminal_control_passed','local_replay_bitwise')),
                'Root independently closed case/source refs differ')
            process_case(case,local,row,writer,groups,counters);stream.flush()
            need((output/'observations.csv').stat().st_size<=OUTPUT_LIMIT,'CSV exceeds output budget')
            del case,local
    need(counters=={'observations':4368,'module_calls':5312,'H0_controls':192,'external_terminals':2496,'physics_passed':21},'Whole cohort reduction incomplete')
    pooled=aggregate(groups)
    write_json(output/'summary.json',{'schema':'model_v3_encoder_local_op_scalar_aggregate_v1',
        'status':'COMPLETE_METADATA_ANALYSIS_PENDING_OUTER_CPU_C0','scope':'FIXED48_LOCAL_ALGORITHM_AND_FP64_CONTRAST_ONLY',
        'root_actual_GPU_closure':root_ref,'capture_manifest':mref,'reducer_source_pins':source_pin,
        'counts':{**counters,'F64_reference_calls':5312,'cases':48,'physics_failed':27},'groups':pooled,
        'missing_operator_population':'NA; absent ports are never zero-filled','scientific_adoption':False,
        'whole_model_causal_ranking':False,'precision_only_contrast':False,'H0_API_change':False,
        'physical_threshold_applied_to_local_ports':False})
    if not args.no_plots:plots(output,pooled,inputs)
    before=dict(inputs.refs);after=inputs.after();need(before==after,'Complete selected source/input before-after differs')
    write_json(output/'INPUT_SOURCE_BINDINGS.json',{'schema':'model_v3_encoder_local_op_metadata_input_bindings_v1',
        'before':before,'after':after,'all_raw_refs_equal':True,'selected_unique_bytes':sum(x['bytes'] for x in before.values()),
        'input_limit_bytes':INPUT_LIMIT,'raw_ref_scope':'selected JSON and own/producer interpretation source only; no NPZ/SDK/model weights opened'})
    prior=artifacts(output)
    write_json(output/'COMPLETE.json',{'schema':'model_v3_encoder_local_op_metadata_complete_v1',
        'status':'ANALYSIS_CHILD_COMPLETE_PENDING_ROOT_CPU_TERMINAL','job_id':os.environ['SLURM_JOB_ID'],
        'artifacts':prior,'observations':4368,'input_bytes':sum(x['bytes'] for x in before.values()),
        'output_limit_bytes':OUTPUT_LIMIT,'elapsed_seconds':time.monotonic()-inputs.started})
    artifacts(output);inputs.tick()
    return 0


if __name__=='__main__':raise SystemExit(main())
