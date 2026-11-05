"""Exact linear percentiles/Spearman with original NumPy/SciPy objects."""
import collections,gzip,hashlib,json,math,pathlib
from . import contract as C

def packet(ctx,ref):
    path=ctx.require(ref,drain=True)
    with gzip.open(path,'rb') as f:raw=f.read((256<<20)+1);C.need(len(raw)<=256<<20 and f.read(1)==b'','FULL_BOUNDED_GZIP_EOF_CRC')
    v=json.loads(raw)
    for row in v.get('cache',{}).get('pm7',[]):C.need(ctx.geometry_sha(v['cache']['atomic_numbers'],row['coordinates'])==row['geometry_sha256'],'ACTUAL_FLOAT64_GEOMETRY_READBACK')
    return v

def linear_percentiles(values):
    import numpy as np
    return {str(p):float(np.percentile(values,p,method='linear')) for p in (0,25,50,75,90,95,99,100)} if len(values) else {}

class Collector:
    def __init__(self,ctx,db):
        self.ctx,self.db=ctx,db;self.orders=[];self.witnesses=[];self.part=0;self.orders_refs=[];self.witness_refs=[];self.cross_count=0;self.missing=collections.Counter();self.nulls=0
        db.execute('CREATE TABLE results(molecule_id VARCHAR PRIMARY KEY,common BOOLEAN,pm7_complete BOOLEAN,d7_complete BOOLEAN,pm7_n BIGINT,pm7_unique BIGINT,uff_n BIGINT,uff_unique BIGINT,heavy BIGINT,rotatable BIGINT,rings BIGINT,hof_complete BOOLEAN,hof_range DOUBLE,packet_json VARCHAR,source_role VARCHAR,effective_role VARCHAR)')
        self.cross=ctx.out/'cross_rmsd.float64';self.cross.open('xb').close()
    def add(self,ref,expected_mid,common):
        import numpy as np
        value=packet(self.ctx,ref);C.need(value['molecule_id']==expected_mid,'ACTUAL_PACKET_EXPECTED_MID');cache=value.get('cache',{});d7=value.get('d7')
        complete=cache.get('status','').startswith('PM7_GEOMETRY_CACHE_COMPLETE');source=d7 if d7 else cache
        self.db.execute('INSERT INTO results VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',[expected_mid,common,complete,d7 is not None,
          cache.get('pm7_count'),cache.get('pm7_unique'),d7.get('uff_sprime_count') if d7 else None,d7.get('uff_sprime_unique') if d7 else None,
          source.get('heavy_atoms'),source.get('rotatable_bonds'),source.get('rings'),cache.get('hof_range_complete',False),cache.get('hof_range_kcal_mol'),C.canonical(ref).decode(),value.get('source_role'),value.get('effective_role')])
        for v in cache.get('hof_by_record',{}).values():
            if not v['valid']:self.missing[v['reason']]+=1
            self.nulls+=int(bool(v['convergence_null_review']))
        if d7:
            pairs=np.asarray(d7['cross_rmsd_A'],dtype='<f8');C.need(np.isfinite(pairs).all() and np.all(pairs>=0),'FINITE_ORIGINAL_CROSS_RMSD_FLOAT64')
            raw=pairs.tobytes()
            C.need(self.ctx.written+self.ctx.workspace()+sum(self.ctx.reserved.values())+len(raw)+(64<<20)<=self.ctx.cap,'CROSS_DATA_ACCOUNTED_IN_SAME_PARENT_CAP')
            with self.cross.open('ab') as f:f.write(raw);f.flush();__import__('os').fsync(f.fileno())
            self.ctx.written+=len(raw);self.cross_count+=pairs.size
        if complete and common:
            sources={'pm7':cache['orders']};ids={'pm7':cache['record_ids']};hashes={'pm7':{r['conformer_id']:r['geometry_sha256'] for r in cache['pm7']}}
            if d7:sources['uff_sprime']=d7['orders']['uff_sprime'];ids['uff_sprime']=d7['cross_uff_sprime_ids'];hashes['uff_sprime']=d7['geometry_hashes']['uff_sprime']
            for source,orders in sources.items():
                mapping={v:source+':'+hashlib.sha256((v if source=='pm7' else expected_mid+':'+str(v)).encode()).hexdigest() for v in ids[source]}
                for kind in ('fixed_random','energy','diversity'):
                    order=orders[kind]
                    if order is None:continue
                    C.need(len(order)==len(set(order))==len(mapping) and set(order)==set(mapping),'COMPLETE_ORIGINAL_ORDER_PERMUTATION')
                    self.orders.extend({'molecule_id':expected_mid,'geometry_source':source,'order_type':kind,'rank':rank,'geometry_id':mapping[native],
                      'native_record_id':str(native) if source=='pm7' else None,'sprime_conf_idx':native if source=='uff_sprime' else None,
                      'source_packet_reference_json':C.canonical(ref).decode(),'common_population':common} for rank,native in enumerate(order))
                for native,gid in mapping.items():
                    self.witnesses.append({'molecule_id':expected_mid,'geometry_source':source,'geometry_id':gid,'geometry_sha256':hashes[source][str(native)] if source=='uff_sprime' else hashes[source][native],
                      'native_record_id':str(native) if source=='pm7' else None,'sprime_conf_idx':native if source=='uff_sprime' else None,
                      'source_packet_reference_json':C.canonical(ref).decode(),'common_population':common})
        if len(self.orders)>=50000:self.flush()
        self.db.commit()
    def flush(self):
        import pyarrow as pa
        if self.orders:
            self.orders_refs.append(self.ctx.write_parquet_new(self.ctx.out/'orders'/('part-%06d.parquet'%self.part),pa.Table.from_pylist(self.orders)));self.orders=[]
        if self.witnesses:
            self.witness_refs.append(self.ctx.write_parquet_new(self.ctx.out/'geometry_witnesses'/('part-%06d.parquet'%self.part),pa.Table.from_pylist(self.witnesses)));self.witnesses=[]
        self.part+=1
    def report(self,expected_common):
        import numpy as np
        from scipy.stats import spearmanr
        self.flush();rows=self.db.execute('SELECT count(*),count(*) FILTER(WHERE pm7_complete),count(*) FILTER(WHERE common),count(*) FILTER(WHERE d7_complete) FROM results').fetchone()
        report={'schema':'CONFORMER_FULL_SOURCE_AND_COMMON_STATISTICS_V1','expected_PM7_population_molecules':1220466,'observed_molecule_packets':rows[0],
          'PM7_geometry_complete_molecules':rows[1],'expected_common_molecules':expected_common,'observed_common_molecules':rows[2],
          'complete_common_PM7_Sprime_pairs':rows[3],'hof_missing_reason_counts':dict(self.missing),'hof_NULL_convergence_review_records':self.nulls,
          'geometry_generation_or_QM_or_UFF_calls':0,'original_PM7_initial_N_policy':'NOT_FOUND_WITH_BOUNDED_SOURCE_SEARCH_PROVENANCE',
          'original_N_history_source_review':'docs/data_v1/d7_remaining_path_source_audit_20261027_v1.md','unique_counts':{},'correlations':{},
          'order_tables':self.orders_refs,'geometry_readback_witness_tables':self.witness_refs,'Root_final_release':False,'N1_extra_geometry_domain_included':False,
          'source_and_effective_role_counts':[{'source_role':a,'effective_role':b,'molecules':n} for a,b,n in self.db.execute('SELECT source_role,effective_role,count(*) FROM results GROUP BY ALL ORDER BY ALL').fetchall()]}
        for source,n,u,condition in [('pm7','pm7_n','pm7_unique','pm7_complete'),('pm7_common','pm7_n','pm7_unique','pm7_complete AND common'),('uff_sprime','uff_n','uff_unique','d7_complete')]:
            data=self.db.execute('SELECT '+n+','+u+',heavy,rotatable,rings FROM results WHERE '+condition).fetchnumpy();v=data[u];denom=len(v)
            hist=dict(collections.Counter(map(str,v.tolist())));total=sum(map(int,data[n])) if denom else 0
            report['unique_counts'][source]={'histogram':hist,'denominator_molecules':denom,'fractions_ge_2_5_10':{str(k):int(np.count_nonzero(v>=k))/denom if denom else None for k in (2,5,10)},
              'duplicate_conformer_fraction':1-int(np.sum(v))/total if total else None,'molecules_with_duplicates_fraction':int(np.count_nonzero(v<data[n]))/denom if denom else None,
              'scope':'ORIGINAL_PM7_SUPERSET' if source=='pm7' else ('COMMON_PM7' if source=='pm7_common' else 'COMMON_ORDINARY_SPRIME')}
            for feature in ('heavy','rotatable','rings'):
                x=data[feature];rho=float(spearmanr(x,v).statistic) if denom and len(set(x))>1 and len(set(v))>1 else None
                report['correlations'][source+'_unique_vs_'+feature]={'spearman_rho':rho if rho is not None and math.isfinite(rho) else None,'n':denom,'undefined_if_constant':rho is None}
        if self.cross_count*8<=self.ctx.plan['exact_quantile_memory_bound_bytes']:
            a=np.memmap(self.cross,dtype='<f8',mode='r',shape=(self.cross_count,)) if self.cross_count else np.array([],dtype='<f8')
            report['cross_rmsd_A_quantiles']=linear_percentiles(a);report['cross_rmsd_A_pairs']=self.cross_count
        else:report['cross_rmsd_A_quantiles']=None;report['cross_quantile_status']='PENDING_EXACT_QUANTILE_MEMORY_BOUND_NOT_APPROXIMATED'
        ranges=self.db.execute('SELECT hof_range FROM results WHERE hof_complete AND common').fetchnumpy()['hof_range'];report['complete_canonical_hof_range_quantiles_kcal_mol']=linear_percentiles(ranges)
        report['canonical_hof_complete_common_molecules']=len(ranges);report['energy_units']='kcal/mol'
        report['PM7_full_source_cache_complete']=rows[0]==rows[1]==1220466
        report['ordinary_Common_D7_geometry_complete']=expected_common is not None and rows[2]==rows[3]==expected_common
        report['three_order_Common_release_eligible']=report['ordinary_Common_D7_geometry_complete'] and len(ranges)==expected_common and report.get('cross_rmsd_A_quantiles') is not None
        return report
