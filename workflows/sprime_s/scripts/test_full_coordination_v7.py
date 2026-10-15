"""Concurrent ledger claims, partial continuation and stale-owner rejection; zero SCI."""
import concurrent.futures as cf,json,multiprocessing as mp,os,tempfile,shutil
from pathlib import Path
from prepare import ROOT,save
import full_dataset_v7 as coord

def init(path):coord.DB=Path(path)
def claims(task):
    worker=task;claimed=[]
    while True:
        row=coord.claim('fixture:'+str(worker),'fixture-job')
        if row is None:return claimed
        claimed.append(row[0])

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    target=ROOT/'reports'/('coordination_v7_fixture_'+os.environ['SLURM_JOB_ID']+'.sqlite')
    assert not target.exists();coord.DB=target
    db=coord.database();db.execute('CREATE TABLE chunks(id INTEGER PRIMARY KEY,file_group INTEGER,lo TEXT,hi TEXT,molecules INTEGER,predicted_seconds REAL,state TEXT,owner TEXT,job_id TEXT,receipt TEXT)')
    db.executemany('INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,?,?)',[(i,1,'a','z',5,float(i),'PENDING',None,None,None) for i in range(1,81)]);db.commit();db.close()
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=init,initargs=(str(target),)) as pool:
        rows=list(pool.map(claims,range(16)))
    ids=[i for r in rows for i in r];assert len(ids)==len(set(ids))==80 and set(ids)==set(range(1,81))
    db=coord.database();owner=db.execute('SELECT owner FROM chunks WHERE id=1').fetchone()[0];db.close()
    rejected=False
    segment={'segment_index':0,'group':1,'molecules':3,'conformers':12,'source_sha256':'FIXTURE_NOT_SCI','references':[]}
    try:coord.finish(1,'wrong-owner',segment)
    except AssertionError:rejected=True
    assert rejected and coord.finish(1,owner,segment)=='PENDING'
    row=coord.claim('resume-owner','fixture-resume-job');assert row[0]==1 and json.loads(row[-1])['molecules']==3
    segment={'segment_index':1,'group':1,'molecules':2,'conformers':8,'source_sha256':'FIXTURE_NOT_SCI','references':[]}
    assert coord.finish(1,'resume-owner',segment)=='DONE'
    db=coord.database();state,receipt=db.execute('SELECT state,receipt FROM chunks WHERE id=1').fetchone();db.close()
    final=json.loads(receipt);assert state=='DONE' and final['molecules']==5 and final['conformers']==20 and len(final['segments'])==2
    result={'status':'PASS','job_id':os.environ['SLURM_JOB_ID'],'workers':16,'concurrent_unique_claims':80,'duplicate_claims':0,'partial_continuation_closed':True,'stale_owner_rejected':True,'scientific_calculations':0,'production_queue_modified':False,'fixture':str(target)}
    save(ROOT/'reports/coordination_v7_test.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':main()
