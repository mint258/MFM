"""One sampled original-Parquet replay with row-group-directed raw IO."""
import bisect
from .resource import ObjectProxy, clone
from workflows.data_v1_final.export.pilot_family_D3_census_resume_v3 import source as X, verify as V


class TargetedRawRows(X.RawRows):
    """Original FD/frame/128-MiB checks; start at the requested footer row group."""

    def get(self, index):
        X.C.need(type(index) is int and 0 <= index < self.expected_rows,
                 'ACTUAL_QA_PARQUET_PHYSICAL_ROW_RANGE')
        if not hasattr(self, '_qa_group_ends'):
            self._qa_group_ends = []
            total = 0
            for group in range(self.pq.num_row_groups):
                total += self.pq.metadata.row_group(group).num_rows
                self._qa_group_ends.append(total)
            X.C.need(total == self.expected_rows, 'ACTUAL_QA_FOOTER_ROW_GROUP_TOTAL')
            self._qa_group = None
        group = bisect.bisect_right(self._qa_group_ends, index)
        if group != self._qa_group:
            start = self._qa_group_ends[group - 1] if group else 0
            self.iterator = self.pq.iter_batches(batch_size=16, row_groups=[group], use_threads=False)
            self.batch = None
            self.batch_lo = self.batch_hi = start
            self._qa_group = group
        return super().get(index)


def replay(work, context=None):
    """Original field reconstruction/bit comparison, only raw IO is localized.

    work has the original (typed_part_reference, sample_items) shape. Expected
    item['packed'] must come from the actual sampled output's F64 authority;
    its training arrays receive one original F32 comparison in the sample loop.
    """
    private = ObjectProxy(X, RawRows=TargetedRawRows, CTX=X.CTX if context is None else context)
    return clone(V.replay, X=private)(work)
