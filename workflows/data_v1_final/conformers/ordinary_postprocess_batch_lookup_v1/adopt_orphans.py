"""Adopt closed readonly outputs into new control metadata, never old files."""
import os
import pathlib
import stat
from workflows.data_v1_final.conformers.postprocess_day_v1 import contract as C, statistics
from . import io as I, resume_closed as R


def adopt(ctx, db, value, descriptors, output_directory):
    """Run only in an actually admitted CPU context after prior native terminal.

    db is the new parent's original cache.setup connection: roster is an exact
    frozen closed-Parquet view, not an active or previous mutable database.
    Return the actual positive adoption JSON reference after exclusive close.
    """
    C.need(os.getuid() == 1278 and ctx.proof['request']['cpus'] == 16, 'ACTUAL_MAIN_ADMITTED_CPU16_READER')
    old, root, native = R.inspect_parent(ctx, value)
    import pyarrow as pa
    import pyarrow.parquet as pq
    known = set()
    for reference in value['catalog_part_references']:
        C.need(pathlib.Path(reference['path']).parent == root / 'catalog_parts', 'ORIGINAL_CLOSED_CATALOG_ONLY')
        for batch in pq.ParquetFile(ctx.require(reference)).iter_batches(batch_size=1024):
            known.update(pathlib.Path(row['packet_reference']['path']) for row in batch.to_pylist())
    closed, interrupted, unresolved = [], [], []
    observed_packets = set(known)
    for path in sorted((root / 'claims').iterdir()):
        ctx.check()
        reference = None
        claim = None
        try:
            info = path.lstat()
            C.need(stat.S_ISREG(info.st_mode) and info.st_uid == 1278 and not path.is_symlink()
                   and path.suffix == '.json', 'ORIGINAL_OWN_REGULAR_CLAIM')
            reference = ctx.reference(path)
            claim = R.check_claim(ctx, value, reference)
            packet_path = root / 'molecules' / (claim['key'] + '.json.gz')
            if packet_path in known:
                continue
            if not packet_path.exists():
                # A terminal resource/cancellation interruption of readonly
                # work is not a completed result or a new native permission.
                entry = dict(molecule_id=claim['molecule_id'], claim_reference=reference,
                             status='RESOURCE_INTERRUPTED_READONLY', scientific_result_observed=False,
                             continuation_requires_identical_frozen_inputs=True, new_Native_permission=False)
                for kind, folder, suffix in (('start_reference', 'starts', '.json'),
                                             ('progress_reference', 'progress', '.jsonl')):
                    candidate = root / folder / (claim['key'] + suffix)
                    entry[kind] = ctx.reference(candidate) if candidate.exists() else None
                interrupted.append(entry)
                continue
            observed_packets.add(packet_path)
            packet_ref = ctx.reference(packet_path)
            packet = statistics.packet(ctx, packet_ref)
            row = dict(molecule_id=packet['molecule_id'], packet_reference=packet_ref,
                       status=packet['status'], cache_origin=packet.get('cache_origin'),
                       geometry_status=(packet.get('cache') or {}).get('status'),
                       d7_closed=packet.get('d7') is not None, runtime=packet['runtime'], claim_reference=reference)
            R.check_closed_row(ctx, value, row)
            closed.append(dict(molecule_id=claim['molecule_id'], catalog_row=row))
        except Exception as error:
            item = dict(status='PRESERVED_READONLY_SOURCE_OR_SCIENTIFIC_UNKNOWN', path=str(path),
                        claim_reference=reference, error=repr(error), automatic_retry=False)
            # A claim failure is evidence, not an accepted or completed packet.
            if claim is not None and reference is not None and claim.get('key') == path.stem:
                item['molecule_id'] = claim['molecule_id']
                candidate = root / 'molecules' / (claim['key'] + '.json.gz')
                if candidate.exists():
                    item['path'] = str(candidate)
                    observed_packets.add(candidate)
            unresolved.append(item)
    for path in sorted((root / 'molecules').iterdir()):
        if path not in observed_packets:
            unresolved.append(dict(status='PRESERVED_UNCLAIMED_OR_UNREGISTERED_OUTPUT_UNKNOWN', path=str(path),
                                   automatic_retry=False, error='NO_VALID_ORIGINAL_CLAIM_BINDING'))
    wanted = {r['molecule_id'] for r in [*closed, *interrupted]}
    membership = {}
    if wanted:
        db.register('orphan_adoption_mids', pa.table({'molecule_id': sorted(wanted)}))
        try:
            rows = db.execute('SELECT r.molecule_id,r.file_group,r.shard_index FROM roster r '
                              'JOIN orphan_adoption_mids m USING(molecule_id)').fetchall()
        finally:
            db.unregister('orphan_adoption_mids')
        for mid, group, shard in rows:
            C.need(mid not in membership, 'ONE_FROZEN_ROSTER_MEMBERSHIP_PER_PRIOR_MID')
            membership[mid] = group, shard
        C.need(set(membership) == wanted, 'ALL_ADOPTED_OR_INTERRUPTED_MIDS_IN_ORIGINAL_FROZEN_ROSTER')
    ordinals = {(d['file_group'], d['shard_index']): n for n, d in enumerate(descriptors)}
    C.need(len(ordinals) == len(descriptors), 'ORIGINAL_DESCRIPTOR_KEYS_UNIQUE')
    for item in [*closed, *interrupted]:
        ordinal = ordinals[membership[item['molecule_id']]]
        item.update(descriptor_ordinal=ordinal, descriptor=descriptors[ordinal])
    original_unknowns = []
    if value.get('receipt_reference'):
        receipt = ctx.read(value['receipt_reference'], 32 << 20)
        C.need(str(receipt['job_id']) == str(value['actual_parent_job_id'])
               and receipt['plan_reference'] == value['plan_reference'], 'ACTUAL_ORIGINAL_RECEIPT_UNKNOWN_EVIDENCE')
        original_unknowns = receipt.get('unknown', [])
    if value.get('failure_reference'):
        failure = ctx.read(value['failure_reference'], 32 << 20)
        C.need(str(failure['job_id']) == str(value['actual_parent_job_id']), 'SAME_ORIGINAL_FAILURE_OWNER')
        # A positively preserved operator interruption is not scientific retry.
        # Any other unresolved original exception remains UNKNOWN/HOLD; this
        # adopter does not invent a generic resource-vs-science classifier.
        if failure.get('error') != 'KeyboardInterrupt()':
            original_unknowns.append(dict(status='PRESERVED_ORIGINAL_FAILURE_UNKNOWN',
                                         original_failure_reference=value['failure_reference'],
                                         error=failure.get('error'), automatic_retry=False))
    base = C.meta(ctx.plan['cache_plan_reference'])
    output = pathlib.Path(output_directory)
    C.need(output.is_absolute() and C.ROOT / 'control' in output.parents and '..' not in output.parts
           and root not in output.parents and not output.exists()
           and not any(p.is_symlink() for p in (output, *output.parents)), 'FRESH_NEW_CONTROL_ADOPTION_DIRECTORY_ONLY')
    manifest = dict(schema='ORDINARY_CLOSED_ORPHAN_ADOPTION_V1', source_parent_job_id=str(value['actual_parent_job_id']),
                    prior_plan_reference=value['plan_reference'], prior_startup_proof_reference=value['startup_proof_reference'],
                    prior_accounting_reference=value['accounting_reference'], actual_parent_accounting=native,
                    frozen_roster_reference=base['whole_molecule_roster'],
                    original_catalog_part_references=value['catalog_part_references'],
                    original_checkpoint_references=value['checkpoint_references'],
                    actual_reader=dict(job_id=ctx.job_id, uid=os.getuid(), node=ctx.proof['request']['node']),
                    closed_orphans=sorted(closed, key=lambda r: (r['descriptor_ordinal'], r['molecule_id'])),
                    resource_interrupted_readonly=sorted(interrupted, key=lambda r: (r['descriptor_ordinal'], r['molecule_id'])),
                    original_unknowns=original_unknowns, unresolved_existing_outputs=unresolved,
                    original_receipt_reference=value.get('receipt_reference'),
                    original_failure_reference=value.get('failure_reference'),
                    old_output_or_checkpoint_rewritten=False, new_UFF_calls=0, new_QM_calls=0,
                    new_PM7_or_RMSD_calls=0, old_history_or_unknowns_cleared=False)
    raw = C.canonical(manifest) + b'\n'
    ctx.check()
    C.need(ctx.written + ctx.workspace() + sum(ctx.reserved.values()) + len(raw) + (64 << 20) <= ctx.cap,
           'EXISTING_ACTUAL_OUTPUT_BUDGET_COVERS_ADOPTION_METADATA')
    output.mkdir(parents=True, mode=0o700)
    reference = I.OLD.PIO.exclusive(output / 'adoption.json', raw)
    ctx.written += reference['bytes']  # No outside-output quota credit.
    return reference
