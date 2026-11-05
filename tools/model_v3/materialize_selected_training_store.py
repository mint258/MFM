#!/usr/bin/env python3
"""Materialize only sealed TRAIN members with the original frozen decoder."""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / 'current'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selection-request', type=Path, required=True)
    parser.add_argument('--request-sha256', required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    from phychem_mfm.phase1.v3_dev_store import bound_json
    from phychem_mfm.phase1.v3_selected_training_store import (binding, write_json, load_context, verify_inventory,
        validate_selection_request, FrozenSelectedDecoder, publish_selected_store,
        MaterializationBudget, require_owned_cpu_allocation, close_context)
    output = require_owned_cpu_allocation(args.output_root); started = time.monotonic()
    decoder = None
    try:
        request = bound_json(args.selection_request, args.request_sha256)
        verify_inventory(request['source_files'])
        sources = bound_json(request['sources']['path'], request['sources']['sha256'])
        panel = bound_json(request['panel']['path'], request['panel']['sha256'])
        budget = MaterializationBudget(request['budgets'], output)
        context = load_context(sources, panel, budget.check)
        plan = validate_selection_request(context, request, panel)
        for dataset, ref in request['original_source_contracts'].items():
            binding_actual = binding(ref['path'])
            if binding_actual != ref:
                raise ValueError('Original metadata-contract artifact changed')
            authority = bound_json(ref['path'], ref['sha256'])
            if authority['contract'] != context['store'].contracts[dataset] or authority.get('targets_decoded') is not False:
                raise ValueError('Original metadata-contract source association differs')
        # Persist the verified label-free request binding in this new run before
        # any source target is decoded. No original file is rewritten.
        write_json(output / 'sealed_selection_binding.json', {'request': binding(args.selection_request),
            'selection_sha256': request['selection_sha256'], 'target_records_decoded_at_this_point': 0,
            'code_sha': request['code_sha'], 'preregistration_sha': request['preregistration_sha']})
        native_output = output / 'native_store'; native_output.mkdir()
        import torch
        torch.set_num_threads(1)
        decoder = FrozenSelectedDecoder(context, plan, budget.check); decoder.prepare()
        def close_source():
            close_context(context, decoder); verify_inventory(request['source_files'])
            if binding(args.selection_request)['sha256'] != args.request_sha256:
                raise ValueError('Sealed selection request changed during materialization')
            for key in ('sources', 'panel'):
                if binding(request[key]['path']) != request[key]:
                    raise ValueError('Bound source/panel configuration changed during materialization')
            budget.check(force=True)
        result = publish_selected_store(plan, context['native'], decoder.decode, output=native_output,
            request_ref=binding(args.selection_request), source_contracts=request['original_source_contracts'],
            definitions=context['definitions'], protocol=context['protocol'], workers=request['budgets']['workers'],
            check=budget.check, close_source=close_source)
        result.update(elapsed_seconds=time.monotonic()-started, actual_decoded_records=len(decoder.decoded),
            actual_workers=request['budgets']['workers'], torch_threads_per_worker=1,
            cpu_allocation=int(os.environ['SLURM_CPUS_PER_TASK']), job_id=os.environ['SLURM_JOB_ID'],
            selection_request_sha256=args.request_sha256, source_code_sha=request['code_sha'],
            preregistration_sha=request['preregistration_sha'], evaluation_or_training_performed=False)
        write_json(output / 'materialization_result.json', result); print(json.dumps(result))
    except BaseException as exc:
        write_json(output / 'FAILED.json', {'status': 'FAILED', 'exception_type': type(exc).__name__,
            'exception_chain': traceback.format_exc(), 'outer_target_records_decoded': 0,
            'attempted_selected_records': 0 if decoder is None else len(decoder.decoded),
            'elapsed_seconds': time.monotonic()-started})
        raise


if __name__ == '__main__':
    main()
