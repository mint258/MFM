"""Bind a frozen P experiment to the producer-published original S240k inputs."""
import argparse
import importlib.util
import json
from pathlib import Path


def bind_configuration(template, binding, output):
    configuration=json.loads(Path(template).read_text())
    manifest=json.loads(Path(binding).read_text())
    membership=manifest.get('membership_binding',{})
    if (manifest.get('schema')!='ORIGINAL_S240K_SHARED_D6_PD_INPUT_BINDING_V1'
            or manifest.get('status')!='READY' or not manifest.get('root')
            or membership.get('unique_molecules')!=configuration['expected_molecules']
            or membership.get('rows_filtered_or_replaced')!=0
            or membership.get('original_subset_order_preserved') is not True
            or manifest.get('intersection_applied') is not False or manifest.get('subset_replaced') is not False):
        raise ValueError('Wait for the producer-published original S240k READY binding')
    if configuration['condition']!='P' or configuration.get('root') is not None:
        raise ValueError('This entry binds an unchanged root-null P template')
    inputs=manifest['bindings']['P']
    for key in ('training_view','normalizations','subset_path','source'):
        if configuration[key]!=inputs[key]:
            raise ValueError(f'Published input differs from the frozen template: {key}')
    if inputs.get('root')!=manifest['root']:
        raise ValueError('Published condition/root binding differs')
    configuration['root']=inputs['root']
    output=Path(output)
    if output.exists():
        if json.loads(output.read_text())!=configuration:
            raise ValueError('Existing execution configuration differs; preserve it')
        return configuration
    spec=importlib.util.spec_from_file_location('bound_config_disk',Path(__file__).resolve().parents[2]/'current/phychem_mfm/phase1/v2_disk.py')
    disk=importlib.util.module_from_spec(spec);spec.loader.exec_module(disk)
    disk.save_metadata_json(configuration,output)
    return configuration


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template',required=True)
    parser.add_argument('--binding',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    value=bind_configuration(args.template,args.binding,args.output)
    print(json.dumps(dict(candidate=value['candidate'],root=value['root'],configuration=args.output)),flush=True)
