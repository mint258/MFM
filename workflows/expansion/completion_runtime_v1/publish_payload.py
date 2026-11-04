"""Export checked Git source blobs for the connected GitHub app.

This is a metadata operation on the server. No credentials or scientific data
are exported. The connected app creates matching Git trees and a non-forced
leased branch update; the final tree must equal the checked local Git tree.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ALLOWED = ('workflows/data_v1_final/', 'workflows/expansion/', 'configs/data_v1/',
           'docs/data_v1/', 'docs/expansion/', 'docs/interfaces/')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--base-execution-commit', required=True)
    parser.add_argument('--base-public-commit', required=True)
    parser.add_argument('--base-tree', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    repo = args.repository.resolve()
    def git(*values):
        return subprocess.check_output(['git', *values], cwd=repo)
    base_tree = git('rev-parse', args.base_execution_commit + '^{tree}').decode().strip()
    if base_tree != args.base_tree:
        raise RuntimeError('Public base tree does not match the known local execution tree')
    head = git('rev-parse', 'HEAD').decode().strip()
    tree = git('rev-parse', 'HEAD^{tree}').decode().strip()
    if git('status', '--porcelain').strip():
        raise RuntimeError('Only a clean committed source tree may be published')
    check = subprocess.run(['python', 'tools/check_repository.py'], cwd=repo,
                           capture_output=True, text=True)
    if check.returncode:
        raise RuntimeError('Required repository check failed: ' + check.stdout + check.stderr)
    evidence = json.loads(check.stdout)
    if evidence.get('status') != 'PASS' or evidence.get('errors'):
        raise RuntimeError('Actual required checker did not pass')
    if git('rev-parse', 'HEAD^{tree}').decode().strip() != tree or git('status', '--porcelain').strip():
        raise RuntimeError('Source changed while checking')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'repository_check.json').write_text(json.dumps(evidence, indent=2) + '\n')
    names = [value.decode() for value in git('diff', '--name-only', '--no-renames', '-z',
              args.base_execution_commit, head).split(b'\0') if value]
    entries = []
    for name in names:
        if not (name.startswith(ALLOWED) or name in ('.gitattributes', 'AGENTS.md')):
            raise RuntimeError('Out-of-scope source path: ' + name)
        info = git('ls-tree', head, '--', name).decode().strip()
        if not info:
            entries.append(dict(path=name, mode='100644', type='blob', sha=None))
            continue
        mode, kind, remainder = info.split(' ', 2)
        oid, actual_name = remainder.split('\t')
        if actual_name != name or kind != 'blob' or mode not in ('100644', '100755'):
            raise RuntimeError('Only literal regular source blobs may be published')
        content = git('cat-file', 'blob', oid)
        if len(content) > 2 << 20:
            raise RuntimeError('Large data are not published through source Git')
        if hashlib.sha1(('blob ' + str(len(content)) + '\0').encode() + content).hexdigest() != oid:
            raise RuntimeError('Source Git object digest mismatch')
        text = content.decode('utf-8')
        if text.encode('utf-8') != content:
            raise RuntimeError('Only exact UTF-8 source blobs are accepted')
        entries.append(dict(path=name, mode=mode, type='blob', content=text))
    chunks, pending, size = [], [], 0
    def save(values):
        path = args.output / ('chunk_%03d.json' % len(chunks))
        raw = (json.dumps(dict(tree_elements=values), ensure_ascii=False) + '\n').encode()
        path.write_bytes(raw)
        chunks.append(dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    for entry in entries:
        n = len(json.dumps(entry, ensure_ascii=False).encode())
        if pending and size + n > 180000:
            save(pending)
            pending, size = [], 0
        pending.append(entry)
        size += n
    if pending:
        save(pending)
    manifest = dict(schema='PUBCHEM_CHECKED_SOURCE_PUBLICATION_PAYLOAD_V1',
        repository_full_name='mint258/MFM', base_execution_commit=args.base_execution_commit,
        expected_public_parent=args.base_public_commit, base_tree_sha=base_tree,
        execution_commit=head, expected_final_tree_sha=tree, files=len(entries),
        chunks=chunks, source_only=True, scientific_dataset_complete=False,
        repository_checker=evidence)
    path = args.output / 'manifest.json'
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(dict(manifest=str(path), files=len(entries), chunks=len(chunks),
                         checked_local_tree=tree)))


if __name__ == '__main__':
    main()
