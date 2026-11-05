"""Private original-writer IO: target granularity and F64 source annotations."""
import hashlib
from .resource import ObjectProxy, clone
from . import native_io
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import writer as W


class TrainingWriter(W.B.Writer):
    """Original training codec; complete native annotations live in F64 authority."""

    def write_batch(self, records):
        training = []
        for metadata, arrays in records:
            value = dict(metadata)
            annotations = value.pop('source_projection_annotations', None)
            if annotations is not None:
                authority = metadata['permanent_F64_sidecar_record']
                value['source_projection_annotations_authority'] = dict(
                    schema='PERMANENT_F64_SOURCE_PROJECTION_ANNOTATIONS_REFERENCE_V1',
                    file_name=authority['file_name'], record_id=authority['record_id'],
                    annotations_sha256=hashlib.sha256(W.CODEC.canonical_json(annotations)).hexdigest(),
                    complete_native_F64_annotations_retained=True)
            training.append((value, arrays))
        return super().write_batch(training)


class Sidecar(W.Sidecar):
    """Close/count once; no independent full F64 payload readback scan."""

    def finish(self):
        self.db.commit()
        count = self.db.execute('SELECT count(*) FROM authority').fetchone()[0]
        W.C.need(count == self.count, 'ACTUAL_F64_AUTHORITY_ROW_COUNT')
        self.db.close()
        self.db = None
        return dict(reference=W.I.pin(self.path), records=count, dtype='float64', immutable=True,
                    full_payload_second_scan_performed=False)


class AnnotationIO:
    def __init__(self, compiled, metadata_factory):
        self.targets = set(compiled['physical_targets']) | set(compiled['ordered_record_targets'])
        self.metadata_factory = metadata_factory
        self.by_target = {}

    def metadata(self, db, geometry):
        self.by_target = {}
        return self.metadata_factory(db, geometry)

    def reason_annotations(self, packed):
        original = W.S.reason_annotations(packed)
        ids = set(original) & self.targets
        W.C.need(len(ids) == 1, 'ONE_STAGED_TARGET_REASON_GRANULARITY_NOT_NATIVE_METADATA')
        tid = next(iter(ids))
        W.C.need(tid not in self.by_target, 'NO_NATIVE_ANNOTATION_OVERWRITE_BETWEEN_TARGETS')
        self.by_target[tid] = {key: value for key, value in original.items() if key != tid}
        return {tid: original[tid]}

    def annotate(self, metadata, arrays, schema, policy, member_bindings):
        value = W.V.annotate(metadata, arrays, schema, policy, member_bindings)
        W.C.need(set(self.by_target) == set(metadata['permanent_source_locators']) ==
                 set(metadata['reason_granularity']), 'ALL_NATIVE_ANNOTATIONS_RETAINED_PER_ACTUAL_TARGET')
        value['source_projection_annotations'] = dict(self.by_target)
        return value


def write(db, root, compiled, policy, plan, proof, budget, *, metadata_factory=None):
    """Original W.write bytecode with annotation-only IO bindings.

    D5 supplies its diagnostic metadata function. Future D3 callers retain
    original W.metadata. Values, masks, indices, locators, ordered records,
    native scientific functions, sidecar arrays and training casts are original.
    """
    annotations = AnnotationIO(compiled, metadata_factory or W.metadata)
    geometry_arrays = clone(W.geometry_arrays,
        T=ObjectProxy(W.T, native_bonds=native_io.native_bonds))
    function = clone(W.write, metadata=annotations.metadata,
        geometry_arrays=geometry_arrays,
        Sidecar=Sidecar,
        S=ObjectProxy(W.S, reason_annotations=annotations.reason_annotations),
        V=ObjectProxy(W.V, annotate=annotations.annotate),
        B=ObjectProxy(W.B, Writer=TrainingWriter))
    return function(db, root, compiled, policy, plan, proof, budget)
