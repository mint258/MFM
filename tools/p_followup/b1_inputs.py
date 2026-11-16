from resources import load,guard
import pyarrow.parquet as pq
if __name__=='__main__':
 guard(force=True,lustre=True)
 m=load('/lfshome/zixiao/data_v1_20261025/D6_full_physical_index_20261105_v3/manifest.json')
 for k in ['identity_database','original_P_records','original_Pprime_records']:print(k,m.get(k))
 c=load('/share/home/zixiao/descriptor_analysis/MFM_p_followup_20261117/configs/p_followup/C_dedup.json');d=load(c['root']+'/manifest.json');print('conformers',d['conformers'])
 files=load(m['files_reference']['path']);f=next(v for v in files if v['family']=='pm7_neutral');q=pq.ParquetFile(f['reference']['path'],pre_buffer=False)
 table=q.read_row_group(0,columns=['record_id','molecule_id','calc_type','total_atoms','numeric_issues']+['values.list.element.'+v for v in ['registry_id','kind','f64','i64','boolean','text']],use_threads=False)
 print('projection',table.column_names,'rows',len(table),'cell_keys',list(table.slice(0,1).to_pylist()[0]['values'][0]));q.close()