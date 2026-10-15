"""Bounded read-only keyset observations. No source BEGIN or sidecar ownership."""
import collections,json,pathlib,sqlite3,time

def scan_queue_readonly(path,chunk_rows=512,statement_seconds=30.0,on_chunk=None):
    if chunk_rows<1 or statement_seconds<=0:raise ValueError('INVALID_SCAN_BOUND')
    started=time.time();clock_start=time.monotonic();chunks=0;visited=0;last=None;max_sql=0.0;eof_reached=False
    counts=collections.defaultdict(lambda:[0,0]);durable=collections.defaultdict(lambda:[0,0])
    rates=collections.defaultdict(lambda:[0,0]);first=None
    connection=sqlite3.connect(pathlib.Path(path).resolve().as_uri()+'?mode=ro',uri=True,
        timeout=1.0,isolation_level=None)
    connection.row_factory=sqlite3.Row
    def query(sql,parameters=()):
        nonlocal max_sql
        before=time.monotonic();until=before+statement_seconds;cursor=None
        connection.set_progress_handler(lambda:int(time.monotonic()>=until),100)
        try:
            cursor=connection.execute(sql,parameters)
            result=cursor.fetchall()
            if time.monotonic()>=until:raise TimeoutError('OBSERVER_CHUNK_WALL_BUDGET_EXCEEDED')
            return result
        finally:
            if cursor is not None:cursor.close()
            connection.set_progress_handler(None,0)
            max_sql=max(max_sql,time.monotonic()-before)
            if connection.in_transaction:raise RuntimeError('OBSERVER_UNEXPECTED_OPEN_TRANSACTION')
    try:
        query('PRAGMA query_only=ON')
        meta=dict(query('SELECT key,value FROM meta'))
        nodes=dict(query('SELECT task_id,node FROM tasks'))
        while True:
            if last is None:
                rows=query('SELECT molecule_id,task_id,file_group,state,record_count,counts_json FROM molecules ORDER BY molecule_id LIMIT ?',(chunk_rows,))
            else:
                rows=query('SELECT molecule_id,task_id,file_group,state,record_count,counts_json FROM molecules WHERE molecule_id>? ORDER BY molecule_id LIMIT ?',(last,chunk_rows))
            if not rows:
                eof_reached=True;break
            # The SELECT is finalized before JSON parsing or callbacks. Each
            # row's state/counts_json belong to the same short read snapshot.
            for row in rows:
                molecule=row['molecule_id']
                if last is not None and molecule<=last:raise ValueError('NON_INCREASING_MOLECULE_PRIMARY_KEY')
                if first is None:first=molecule
                last=molecule;visited+=1
                task=row['task_id'];records=row['record_count'];state=row['state']
                if task not in nodes:raise ValueError('OBSERVED_MOLECULE_TASK_NOT_REGISTERED')
                if not isinstance(records,int) or isinstance(records,bool) or records<0:raise ValueError('INVALID_RECORD_COUNT')
                counts[(nodes[task],row['file_group'],state)][0]+=1
                counts[(nodes[task],row['file_group'],state)][1]+=records
                if row['counts_json'] is not None:
                    values=json.loads(row['counts_json'])
                    if not isinstance(values,dict):raise ValueError('INVALID_TASK_COUNTS_JSON')
                    durable[state][0]+=1;durable[state][1]+=records
                    for task_name,value in values.items():
                        if not isinstance(value,dict):raise ValueError('INVALID_TASK_COUNTS_VALUE')
                        success=value.get('success');total=value.get('total')
                        if any(not isinstance(x,int) or isinstance(x,bool) or x<0 for x in (success,total)) or success>total:
                            raise ValueError('INVALID_TASK_SUCCESS_TOTAL')
                        rates[task_name][0]+=success;rates[task_name][1]+=total
            chunks+=1
            if on_chunk is not None:on_chunk(chunks,last)
    finally:connection.close()
    ended=time.time()
    return {'meta':meta,
        'counts':[{'node':n,'file_group':g,'state':s,'molecules':v[0],'records':v[1]} for (n,g,s),v in sorted(counts.items())],
        'durable_states':[{'state':s,'molecules':v[0],'records':v[1]} for s,v in sorted(durable.items())],
        'task_success_rates':[{'calc_type':n,'success':v[0],'total':v[1]} for n,v in sorted(rates.items())],
        'scan_interval':{'schema':'WP5_QUEUE_KEYSET_INTERVAL_V1','scan_start_epoch':started,
            'scan_end_epoch':ended,'elapsed_seconds':time.monotonic()-clock_start,
            'chunk_rows':chunk_rows,'chunk_count':chunks,'statement_wall_budget_seconds':statement_seconds,
            'maximum_statement_seconds':max_sql,'molecules_visited_once':visited,
            'first_molecule_id':first,'last_molecule_id':last,
            'snapshot_semantics':'One short autocommit SELECT per chunk; one row per immutable molecule primary key; not an atomic whole-database instant.',
            'row_state_and_counts_json_same_snapshot':True,'source_BEGIN_used':False,
            'source_connection_closed':True,'partial_counts_published':False,'full_primary_key_scan_EOF':eof_reached,
            'projection_semantics':'All cost measured after scan; COMPLETE observed during scan can undercount end-of-scan COMPLETE, conservatively inflating cost projection during ordinary phase completion. Retry transitions remain explicitly interval-observed.',
            'progress_handler_limitation':'SQLite progress checks interrupt VM work after deadline; an OS uninterruptible IO wait can outlast the deadline until IO returns.'}}
