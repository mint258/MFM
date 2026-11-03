"""Read actual original Main C0 accounting; never infer it from a receipt."""
import csv,io
from .runtime import need,read,verify


def closed_freeze(reference):
    value=read(reference)
    need(value['endpoint']=='202.38.247.57:22' and value['uid']==1278,'ORIGINAL_MAIN_ACCOUNTING_ENDPOINT_UID')
    raw_ref=value['raw_sacct_reference'];raw=verify(raw_ref).read_text()
    if value['schema']=='ROOT_ACTUAL_SLURM_PARENT_ACCOUNTING_V1':
        names=('JobIDRaw','JobName','State','ExitCode','NodeList','AllocCPUS','ElapsedRaw','Start','End','User')
        rows=list(csv.reader(io.StringIO(raw),delimiter='|'))
        need(len(rows)==1 and len(rows[0])==10,'ACTUAL_TEN_COLUMN_RAW_PARENT_ACCOUNTING')
        row=dict(zip(names,rows[0]))
        need(all(str(value[k])==row[k] for k in names) and row['User']=='zixiao','ALL_DECLARED_FIELDS_EQUAL_RAW')
    else:
        need(value['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and value['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
             and value['query_returncode']==0,'ACTUAL_CANONICAL_PARENT_ACCOUNTING')
        rows=[r for r in csv.DictReader(io.StringIO(raw),delimiter='|') if r.get('JobIDRaw')=='4525199']
        need(len(rows)==1,'ONE_EXACT_ORIGINAL_FREEZE_PARENT');row=rows[0]
        need(row['UID']=='1278','ACTUAL_RAW_FREEZE_UID')
        declared=[r for r in value['parents'] if str(r['job_id'])=='4525199']
        need(len(declared)==1 and declared[0]['state']==row['State'] and declared[0]['exit_code']==row['ExitCode']
             and int(declared[0]['alloc_cpus'])==int(row['AllocCPUS'])
             and int(declared[0]['elapsed_raw_seconds'])==int(row['ElapsedRaw']),'DECLARED_FREEZE_EQUALS_RAW')
    need(row['JobIDRaw']=='4525199' and row['State']=='COMPLETED' and row['ExitCode']=='0:0'
         and row['NodeList']=='compute-0-13' and int(row['AllocCPUS'])==16,'TRUE_CLOSED4525199_C0_16CPU13')
    return dict(job_id='4525199',state='COMPLETED',exit_code='0:0',node='compute-0-13',alloc_cpus=16,
                elapsed_raw_seconds=int(row['ElapsedRaw'])),raw_ref


def failed_metadata_parent(reference,job_id):
    value=read(reference)
    need(value['schema']=='ROOT_ACTUAL_SLURM_PARENT_ACCOUNTING_V1' and value['endpoint']=='202.38.247.57:22'
      and value['uid']==1278,'ACTUAL_FAILED_METADATA_PARENT_MAIN_AUTHORITY')
    names=('JobIDRaw','JobName','State','ExitCode','NodeList','AllocCPUS','ElapsedRaw','Start','End','User')
    raw_ref=value['raw_sacct_reference'];rows=list(csv.reader(io.StringIO(verify(raw_ref).read_text()),delimiter='|'))
    need(len(rows)==1 and len(rows[0])==10,'EXACT_RAW_FAILED_PARENT_ROW')
    row=dict(zip(names,rows[0]));need(all(str(value[k])==row[k] for k in names),'FAILED_PARENT_ALL_FIELDS_EQUAL_RAW')
    need(row['JobIDRaw']==str(job_id) and row['State']=='FAILED' and row['ExitCode']!='0:0'
      and row['User']=='zixiao' and int(row['AllocCPUS'])>=16,'TRUE_FAILED_PARENT_NOT_UPGRADED_TO_C0')
    return value,raw_ref
