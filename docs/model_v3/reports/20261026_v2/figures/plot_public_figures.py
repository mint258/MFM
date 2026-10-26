"""Render two progress figures from the fixed public aggregate JSON only. No run at import."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def read(path):
    path=Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size>2<<20:
        raise ValueError('Bounded ordinary public aggregate required')
    return json.loads(path.read_text(encoding='utf-8'))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-dir',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True); args=parser.parse_args(argv)
    if not args.output_dir.is_absolute() or args.output_dir.exists(): raise ValueError('Fresh absolute figure directory required')
    a=read(args.input_dir/'data/a06_diagnostic.public.json'); c=read(args.input_dir/'data/c4_equivariance.public.json')
    rows=a['updates']; variants=c['variants']
    if ([row['update'] for row in rows]!=list(range(1,16)) or a['original_gate_status']!='FAILED_UNCHANGED'
        or a['scientific_acceptance'] is not False or a['original_relative_loss_threshold']!=.001
        or len(variants)!=7 or c['absolute_tolerance']!=1e-5 or c['relative_tolerance']!=0
        or c['scientific_selection_or_adoption'] is not False
        or any(row['threshold_pass_count_NOT_adoption']!=0 or row['case_count']!=48 for row in variants)):
        raise ValueError('Only the saved unchanged diagnostic scope can be plotted')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    args.output_dir.mkdir()
    x=[row['update'] for row in rows]
    figure,axes=plt.subplots(1,2,figsize=(9,3.5),layout='constrained')
    axes[0].plot(x,[row['reference_loss'] for row in rows],'.-',label='Reference')
    axes[0].plot(x,[row['free_fused_loss'] for row in rows],'.--',label='Free fused')
    axes[0].set(xlabel='Optimizer update',ylabel='Scalar loss (original normalization)',title='A06: all15 replay points')
    axes[0].legend(frameon=False)
    axes[1].plot(x,[row['relative_difference'] for row in rows],'.-',color='#b44b32')
    axes[1].axhline(.001,color='black',linestyle='--',linewidth=1,label='Original threshold0.001')
    axes[1].set(xlabel='Optimizer update',ylabel='abs(free-ref)/max(abs(ref),1e-12)',title='Original gate remains failed')
    axes[1].legend(frameon=False)
    for axis in axes: axis.grid(alpha=.2); axis.set_xticks([1,5,10,14,15])
    figure.savefig(args.output_dir/'A06_native_feedback_15updates.png',dpi=150); plt.close(figure)
    fields=('PD/p_dipole','PD/p_dipole_magnitude','PD/p_extensive')
    figure,axes=plt.subplots(1,3,figsize=(11,3.7),layout='constrained')
    for axis,field in zip(axes,fields):
        values=[]
        for variant in variants:
            found=[row for row in variant['fields'] if row['field']==field]
            if len(found)!=1 or found[0]['measurement_count']!=144: raise ValueError('Exact terminal denominator required')
            values.append(found[0]['maximum_absolute_error'])
        axis.bar(range(7),values,color=['#455b74','#7c8fa5','#688f77','#d69c57','#8eaf9b','#ddb886','#abb591'])
        axis.axhline(1e-5,color='black',linestyle='--',linewidth=1,label='Original abs tol1e-5')
        axis.set(title=field,xlabel='Variant (see JSON/README mapping)',ylabel='Max abs error (original output units)',
            xticks=list(range(7)),xticklabels=['V'+str(i) for i in range(7)])
        axis.ticklabel_format(axis='y',style='sci',scilimits=(0,0)); axis.grid(axis='y',alpha=.2)
        if field==fields[0]: axis.legend(frameon=False,fontsize=8)
    figure.suptitle('C4: 7 variants; each0/48 whole cases; poolFP64 reference only',fontsize=11)
    figure.savefig(args.output_dir/'C4_equivariance_7variants.png',dpi=150); plt.close(figure)
    outputs=[]
    for path in sorted(args.output_dir.glob('*.png')):
        raw=path.read_bytes()
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'): raise ValueError('Expected genuine PNG')
        outputs.append({'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    if len(outputs)!=2 or sum(row['bytes'] for row in outputs)>4<<20: raise ValueError('Two-PNG output budget exceeded')
    with (args.output_dir/'figure_manifest.json').open('x') as stream:
        json.dump({'status':'RENDERED_PENDING_ROOT_C0_AND_VISUAL_REVIEW','figures':outputs,
            'scientific_acceptance':False,'native_data_or_targets_accessed':False},stream,indent=2); stream.write('\n')
    return 0


if __name__=='__main__': raise SystemExit(main())
