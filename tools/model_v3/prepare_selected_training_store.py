#!/usr/bin/env python3
"""Seal a target-free original-source TRAIN selection; do not decode labels."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(ROOT / 'current'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, default=ROOT / 'configs/model_v3/existing_downstream_sources_v1.json')
    parser.add_argument('--sources-sha256', required=True)
    parser.add_argument('--panel', type=Path, default=ROOT / 'configs/dev_panel_v1.json')
    parser.add_argument('--panel-sha256', required=True)
    parser.add_argument('--code-sha', required=True)
    parser.add_argument('--preregistration-sha', required=True)
    parser.add_argument('--output-root', type=Path, required=True)
    args = parser.parse_args()
    from phychem_mfm.phase1.v3_dev_store import bound_json
    from phychem_mfm.phase1.v3_selected_training_store import (binding, write_json, load_context,
        source_inventory, verify_inventory, make_selection_request, MaterializationBudget,
        require_owned_cpu_allocation, close_context)
    output = require_owned_cpu_allocation(args.output_root); started = time.monotonic()
    try:
        sources = bound_json(args.sources, args.sources_sha256)
        panel = bound_json(args.panel, args.panel_sha256)
        sources_ref, panel_ref = binding(args.sources), binding(args.panel)
        if sources_ref['sha256'] != args.sources_sha256 or panel_ref['sha256'] != args.panel_sha256:
            raise ValueError('Source/panel changed after initial byte binding')
        budget = MaterializationBudget(sources['budgets'], output)
        inventory = source_inventory()
        context = load_context(sources, panel, budget.check)
        request = make_selection_request(context, panel_ref, sources_ref,
            code_sha=args.code_sha, preregistration_sha=args.preregistration_sha, inventory=inventory)
        contracts = {}
        for dataset, contract in context['store'].contracts.items():
            contracts[dataset] = write_json(output / ('original_source_contract_'+dataset+'.json'), {
                'schema': 'model_v3_original_TRAIN_metadata_contract_v1', 'targets_decoded': False,
                'source_membership': context['source_refs']['membership_summary'], 'contract': contract})
        request['original_source_contracts'] = contracts
        close_context(context); verify_inventory(inventory); budget.check(force=True)
        if binding(args.sources) != sources_ref or binding(args.panel) != panel_ref:
            raise ValueError('Source/panel configuration changed while preparing selection')
        request_ref = write_json(output / 'selection_request.json', request)
        result = {'status': 'FROZEN_LABEL_FREE_SELECTION', 'request': request_ref, 'target_records_decoded': 0,
            'selected_counts': {d: len(rows) for d, rows in request['selection']['records'].items()},
            'elapsed_seconds': time.monotonic()-started}
        write_json(output / 'preparation_result.json', result); print(json.dumps(result))
    except BaseException as exc:
        write_json(output / 'FAILED.json', {'status': 'FAILED', 'exception_type': type(exc).__name__,
            'exception_chain': traceback.format_exc(), 'target_records_decoded': 0,
            'elapsed_seconds': time.monotonic()-started})
        raise


if __name__ == '__main__':
    main()
