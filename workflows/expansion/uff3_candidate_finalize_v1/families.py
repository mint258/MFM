"""Full-family saved-F64 parity and source identity, not descriptor recomputation."""
import json
from pathlib import Path
from ..alpha_runtime_v1.common import need
from ..uff3_candidate_v1 import core as C
from . import validation as V,closed,storage


def no_f32(t,pa):
    if pa.types.is_float32(t):return False
    if pa.types.is_list(t)or pa.types.is_large_list(t)or pa.types.is_fixed_size_list(t):return no_f32(t.value_type,pa)
    if pa.types.is_struct(t):return all(no_f32(f.type,pa)for f in t)
    return True


def scan(db,refs,guard):
    import pyarrow as pa
    import pyarrow.parquet as pq
    db.execute('CREATE TABLE observed(mid VARCHAR,record_id VARCHAR,family VARCHAR,payload_hash VARCHAR,names_json VARCHAR,mask_json VARCHAR,geometry_sha VARCHAR,energy_hash VARCHAR,native_id BIGINT,atom_order_sha VARCHAR)')
    catalog=[]
    db.execute('CREATE INDEX fact_mid ON facts(mid)')
    for i,ref in enumerate(refs):
        family=ref['family'];need(family in('D20','D3','geometry','source_status','validity_masks'),'Original delivered family set only')
        path=Path(ref['path']);closed.verify_stream(ref);before=closed.frame(path.lstat())
        table=pq.ParquetFile(path)
        need(all(no_f32(f.type,pa)for f in table.schema_arrow),'New delivered numerical family must not contain float32')
        n=0
        if family!='validity_masks':
            for batch in table.iter_batches(batch_size=512,use_threads=False):
                insert=[];rows=batch.to_pylist();mids=list({r['molecule_id']for r in rows})
                lookup={r[0]:r[1:]for r in db.execute('SELECT mid,cid,full_key,stream,stream_rank,pubchem_version,once_key,packet_sha,wp5_key FROM facts WHERE mid IN('+','.join('?'for _ in mids)+')',mids).fetchall()}
                for r in rows:
                    mid=r['molecule_id'];rid=r['record_id']
                    actual=lookup.get(mid)
                    need(actual==(r['pubchem_cid'],r['full_key'],r['stream'],r['stream_rank'],r['pubchem_version'],r['task_id'],r['producer_packet_sha256'],r['wp5_key'])
                        and r['dataset_version']=='v2_candidate'and r['training_eligible']is False,
                        'Every actual family row binds frozen CID/key/stream/rank/PubChem/source once/packet SHA')
                    h=names=mask=geo=energy=atom=None;native=None
                    if family=='D20':
                        need(rid==mid+':graph'and r['conformer_id']is None,'One graph record, never inferred D20 success')
                        h=V.numeric_hash(r['values_float64']);names=C.canonical(r['descriptor_names']).decode();mask=C.canonical(r['valid_mask']).decode()
                    elif family=='D3':
                        need(rid==mid+':uff:'+str(r['conformer_id']),'Actual physical D3 record ID')
                        h=V.numeric_hash([r[name]for name in V.D3_NAMES])
                    elif family=='geometry':
                        need(rid==mid+':uff:'+str(r['conformer_id'])and r['PM7_pointer']is None and r['PM7_HOF']is None and r['PM7_RMSD']is None,'No PM7 reference fabricated for new UFF')
                        geo=C.geometry_sha(r['atomic_numbers'],r['positions_A']);need(geo==r['geometry_sha256'],'Actual F64 coordinates and atomic order SHA')
                        energy=V.numeric_hash(r['uff_energy_kcal_mol']);native=r['native_candidate_id'];atom=r['atom_order_sha256']
                    else:
                        need(rid==mid and r['conformer_id']is None,'All failed/unknown/sparse source status retained')
                        h=V.status_hash(dict(state=r['state'],actual_conformers=r['actual_conformers'],desired_conformers=r['desired_conformers'],
                            insufficient_conformers=r['insufficient_conformers'],generation_count_unknown=r['generation_count_unknown'],
                            cache_complete=r['cache_complete'],orders=json.loads(r['orders_json']),generation_order=json.loads(r['generation_order_json']),error=r['error']))
                    insert.append((mid,rid,family,h,names,mask,geo,energy,native,atom));n+=1
                db.executemany('INSERT INTO observed VALUES(?,?,?,?,?,?,?,?,?,?)',insert);guard.check()
        else:n=table.metadata.num_rows
        need(before==closed.frame(path.lstat()),'Closed family changed during typed parity readback')
        catalog.append((str(path),family,ref['bytes'],ref['sha256'],n))
        storage.add(db,[storage.fact(path,'UFF_D_FAMILY_DATA'),storage.fact(path.parent,'FAMILY_DIRECTORY_METADATA')])
        if i%64==0:guard.check(True)
    db.execute('CREATE TABLE family_catalog(path VARCHAR,family VARCHAR,bytes BIGINT,sha256 VARCHAR,rows BIGINT)')
    db.executemany('INSERT INTO family_catalog VALUES(?,?,?,?,?)',catalog)


def compare(db):
    need(db.execute("SELECT count(*)FROM(SELECT family,record_id FROM observed GROUP BY ALL HAVING count(*)<>1)").fetchone()[0]==0,'No duplicate delivered graph/conformer/status record')
    need(db.execute("SELECT count(*)FROM observed WHERE family='D20'").fetchone()[0]==2500000
        and db.execute("SELECT count(*)FROM observed WHERE family='source_status'").fetchone()[0]==2500000,
        'D20 family row once and source-status once for every source; validity is reported separately')
    for family,field in (('D20','d20_hash'),('source_status','status_hash')):
        need(db.execute("SELECT count(*)FROM facts f LEFT JOIN observed o ON f.mid=o.mid AND o.family=? WHERE o.mid IS NULL OR o.payload_hash IS DISTINCT FROM f."+field,(family,)).fetchone()[0]==0,
             'Full saved packet/family F64 or status parity: '+family)
    need(db.execute("SELECT count(*)FROM facts f JOIN observed o ON f.mid=o.mid AND o.family='D20' WHERE o.names_json IS DISTINCT FROM f.d20_names OR o.mask_json IS DISTINCT FROM f.d20_mask").fetchone()[0]==0,'D20 original names/masks without reordering')
    for family in ('D3','geometry'):
        need(db.execute('SELECT count(*)FROM expected_conformers').fetchone()[0]==db.execute('SELECT count(*)FROM observed WHERE family=?',(family,)).fetchone()[0],'Actual delivered conformer census: '+family)
        if family=='D3':bad='o.payload_hash IS DISTINCT FROM e.d3_hash'
        else:bad='o.geometry_sha IS DISTINCT FROM e.geometry_sha OR o.energy_hash IS DISTINCT FROM e.energy_hash OR o.native_id IS DISTINCT FROM e.native_id OR o.atom_order_sha IS DISTINCT FROM e.atom_order_sha'
        need(db.execute('SELECT count(*)FROM expected_conformers e LEFT JOIN observed o ON e.record_id=o.record_id AND o.family=? WHERE o.mid IS NULL OR '+bad,(family,)).fetchone()[0]==0,'Full coordinate/D3/native ID/F64 parity: '+family)