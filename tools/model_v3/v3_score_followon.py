"""Score one closed v3 follow-on group using the fixed paired decision rules."""
import argparse
import json
from pathlib import Path

from phychem_mfm.phase1.v3_followon_decisions import (
    lambda_k, fresh_confirmation, candidate_set, full_budget)
from phychem_mfm.phase1.v3_dev_evaluation_v2 import _json


def load_panels(mapping):
    return {candidate: {condition: json.loads(Path(path).read_text())
        for condition, path in conditions.items()} for candidate, conditions in mapping.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True)
    parser.add_argument('--results', required=True)
    parser.add_argument('--page', required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text())
    kind = manifest['kind']
    panels = load_panels(manifest['panels']) if kind != 'convergence' else None
    if kind == 'lambda_k':
        prior = json.loads(Path(manifest['T1_result']).read_text())
        if prior['provisional_latent'] != 'lite_rec':
            raise ValueError('Lambda/k experiments require actual A3 adoption')
        result = lambda_k(panels)
    elif kind == 'fresh_confirmation':
        prior = json.loads(Path(manifest['T1_result']).read_text())
        result = fresh_confirmation(panels['new'], panels['original'], prior['provisional_latent'])
    elif kind == 'candidate_set':
        result = candidate_set(panels, manifest['simplicity_order'])
    elif kind == 'convergence':
        curves = {condition: {int(samples): json.loads(Path(path).read_text())
            for samples, path in values.items()} for condition, values in manifest['curves'].items()}
        result = full_budget(curves)
    else:
        raise ValueError('Use a specified follow-on experiment group')
    result.update(group=manifest['group'], input_manifest=str(args.manifest),
        panel='v2', source_roles=['train', 'train_inner_validation'], downstream_TEST_read=False)
    _json(result, args.results)
    title = '# ' + manifest['group']
    lines = [title, '', 'Status: ' + result['status'], '',
        'Fixed taskbook-v3 paired molecule-group bootstrap: 1000 draws, seed20261025; equal tasks then equal conditions.',
        '', 'Source manifest: `' + str(args.manifest) + '`', '', '```json',
        json.dumps(result, indent=2, ensure_ascii=False), '```', '']
    page = Path(args.page)
    content = '\n'.join(lines)
    if page.exists() and page.read_text() != content:
        raise ValueError('Retain previous reports; use a new actual group/endpoint output')
    page.parent.mkdir(parents=True, exist_ok=True)
    if not page.exists():
        page.write_text(content)
    print(json.dumps(dict(status=result['status'], results=args.results)))


if __name__ == '__main__':
    main()
