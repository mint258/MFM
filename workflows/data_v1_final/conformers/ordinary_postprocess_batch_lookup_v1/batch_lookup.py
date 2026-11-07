"""Original per-MID SELECTs over one descriptor's identical metadata rows."""
from workflows.data_v1_final.conformers.postprocess_day_v1 import contract as C


class DescriptorLookup:
    SOURCES = ('all_roles', 'final_common', 'uff_sources')
    QUERIES = {
        'SELECT source_role,effective_role FROM all_roles WHERE molecule_id=?':
            'SELECT source_role,effective_role FROM descriptor_all_roles WHERE molecule_id=?',
        'SELECT * FROM final_common WHERE molecule_id=?':
            'SELECT * FROM descriptor_final_common WHERE molecule_id=?',
        'SELECT * FROM uff_sources WHERE molecule_id=? ORDER BY sprime_conf_idx':
            'SELECT * FROM descriptor_uff_sources WHERE molecule_id=? ORDER BY sprime_conf_idx',
    }

    def __init__(self, db):
        self.db = db
        self.mids = set()

    def prepare(self, metas):
        import pyarrow as pa
        self.mids = {m['molecule_id'] for m in metas}
        C.need(len(self.mids) == len(metas), 'ORIGINAL_DESCRIPTOR_UNIQUE_MIDS')
        self.db.register('descriptor_lookup_mids', pa.table({'molecule_id': sorted(self.mids)}))
        try:
            for source in self.SOURCES:
                target = 'descriptor_' + source
                self.db.execute('DROP TABLE IF EXISTS ' + target)
                # s.* retains every original column, name, order and SQL type.
                # Full source views remain unchanged for all other consumers.
                self.db.execute('CREATE TEMP TABLE ' + target + ' AS SELECT s.* FROM ' + source +
                                ' s JOIN descriptor_lookup_mids b USING(molecule_id)')
                self.db.execute('CREATE INDEX ' + target + '_mid ON ' + target + '(molecule_id)')
        finally:
            self.db.unregister('descriptor_lookup_mids')

    def execute(self, sql, parameters=None):
        replacement = self.QUERIES.get(sql)
        if replacement is not None:
            C.need(parameters is not None and len(parameters) == 1 and parameters[0] in self.mids,
                   'ONLY_CURRENT_ORIGINAL_DESCRIPTOR_LOOKUP')
            sql = replacement
        return self.db.execute(sql) if parameters is None else self.db.execute(sql, parameters)

    def __getattr__(self, name):
        return getattr(self.db, name)
