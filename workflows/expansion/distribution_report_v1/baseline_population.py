"""Metadata-only frozen baseline receipt to existing distribution population schema."""
import argparse
from pathlib import Path
from .io import load,reference,verify,write_new,need
from ..exact_nn_cached_v1.contracts import baseline_query


def prepare(receipt_path,output):
    q=load(receipt_path);baseline_query(q)
    artifact=lambda ref:{**ref,'format':'parquet'}
    result={'schema':'EXPANSION_DISTRIBUTION_POPULATION_V1','status':'COMPLETE',
        'population':'pubchem_1m','population_scope':'FULL_DECLARED_POPULATION','expected_molecules':1000000,
        'authority_reference':reference(receipt_path),'authority_count_pointer':'/sample_molecules',
        'authority_kind':'FROZEN_PREDECON_UNIFORM_BASELINE','is_sample':True,
        'sampling':{'uniform':True,'seed':q['sample_seed'],'source_status':'X_SCREENED_INTERNAL_FULLKEY_DEDUPLICATED'},
        'baseline_pool_phase':'BEFORE_V1_DOWNSTREAM_DECONTAMINATION_AND_NOVELTY',
        'raw_chemical_screen_reference':q['raw_chemical_screen_reference'],
        'internal_deduplicated_pool_reference':q['internal_deduplicated_pool_reference'],
        'membership':{'identity_column':'full_key','artifacts':[artifact(q['sample_membership'])]},
        'features':{'identity_column':'full_key','artifacts':[artifact(q['features'])]},
        'allow_additive_descriptor_completion':False,'original_sample_projection_reference':q['projection'],
        'sample_order_preserved':q['projection_order'],'source_endpoint':q.get('source_endpoint'),
        'source_uid':q.get('source_uid'),'sample_reselected_or_chemistry_recomputed':False}
    verify(q['features'])
    if Path(output).exists():
        need(load(output)==result,'Existing population manifest differs from the actual frozen baseline binding')
    else:
        write_new(output,result)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--baseline-receipt',required=True,type=Path)
    p.add_argument('--output',required=True,type=Path)
    a=p.parse_args();prepare(a.baseline_receipt,a.output)


if __name__=='__main__':main()
