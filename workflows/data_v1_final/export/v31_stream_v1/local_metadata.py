"""Optional local metadata SQLite build; shared refs remain authoritative."""
import json,os,sqlite3,subprocess
from pathlib import Path
from ...labels.window2_normalization_v1 import io as I
from .disk_guard import from_plan
RUNTIME_KEY='_local_database_paths'


def public(result):return {k:v for k,v in result.items() if k!=RUNTIME_KEY}


def work_root(plan):
    shared=Path(plan['source_working_root'])
    if not plan.get('metadata_working_root'):return shared
    return Path(plan['metadata_working_root'])/shared.name


def runtime_result(result,plan):
    result=public(result);mapping={}
    configure_tmp(plan)
    if plan.get('metadata_working_root'):
        for key,stem in (('database','geometry_identities'),('orders_database','orders_and_d5')):
            checkpoint=work_root(plan)/(stem+'.build.json')
            if key not in result or not checkpoint.is_file():continue
            state=I.load(checkpoint)
            if state.get('phase')=='published' and state.get('result',{}).get(key)==result[key] and Path(state['physical_path']).is_file():
                mapping[result[key]['path']]=state['physical_path']
    return dict(result,**{RUNTIME_KEY:mapping}) if mapping else result


def database_path(index,key='database'):
    logical=index[key]['path'];physical=index.get(RUNTIME_KEY,{}).get(logical)
    return physical if physical and Path(physical).is_file() else logical


def configure_tmp(plan):
    if plan.get('metadata_working_root'):
        temporary=work_root(plan)/'sqlite_tmp';temporary.mkdir(parents=True,exist_ok=True)
        os.environ['SQLITE_TMPDIR']=str(temporary)


class MetadataBuild:
    """Progress is committed in the same transaction as each original ref.

    Legacy SQLite without this producer checkpoint is never adopted/inferred.
    No cache-size, synchronous, journal or scientific source rules are changed.
    """
    def __init__(self,plan,stem,inputs):
        self.guard=from_plan(plan,admit=False)
        self.plan=plan;self.shared_root=Path(plan['source_working_root']);self.root=work_root(plan)
        if self.guard:self.guard.wait(self.root,inodes_needed=4);self.guard.wait(self.shared_root,inodes_needed=4)
        self.shared_root.mkdir(parents=True,exist_ok=True);self.root.mkdir(parents=True,exist_ok=True)
        self.checkpoint=self.root/(stem+'.build.json');self.db=None
        frozen={'source_working_root':str(self.shared_root),'inputs':inputs}
        if self.checkpoint.is_file():
            self.state=I.load(self.checkpoint)
            if self.state['frozen']!=frozen:raise ValueError('METADATA_BUILD_FROZEN_INPUTS_CHANGED')
        else:
            candidate=self.shared_root/(stem+'.sqlite');number=0
            while candidate.exists() or candidate.with_name(candidate.name+'.partial').exists() or (self.root/candidate.name).exists():
                number+=1;candidate=self.shared_root/('%s_attempt_%03d.sqlite'%(stem,number))
            self.state={'frozen':frozen,'shared_path':str(candidate),'physical_path':str(self.root/candidate.name),'phase':'new'}
        self.shared=Path(self.state['shared_path']);self.physical=Path(self.state['physical_path'])
        configure_tmp(plan)

    @property
    def closed_result(self):
        return self.state.get('result') if self.state['phase'] in ('closed','published') else None

    def open(self,schema):
        if self.state['phase']=='building' and not self.physical.is_file():raise ValueError('LOCAL_METADATA_CHECKPOINT_DATABASE_MISSING')
        if self.guard:self.guard.wait(self.physical,inodes_needed=4)
        self.db=sqlite3.connect(self.physical)
        if self.state['phase']=='new':
            self.db.executescript(schema)
            self.db.execute('CREATE TABLE build_progress(stage TEXT,ref_ordinal INTEGER,reference TEXT,PRIMARY KEY(stage,ref_ordinal))')
            self.db.commit();self.state['phase']='building';I.save(self.checkpoint,self.state)
        self.done_refs={(stage,ordinal):json.loads(reference) for stage,ordinal,reference in self.db.execute('SELECT stage,ref_ordinal,reference FROM build_progress')}
        return self.db

    def done(self,stage,ordinal,reference):
        if (stage,ordinal) not in self.done_refs:return False
        if self.done_refs[(stage,ordinal)]!=reference:raise ValueError('METADATA_COMMITTED_REFERENCE_CHANGED')
        return True

    def commit(self,stage,ordinal,reference):
        if self.guard:self.guard.wait(self.physical,inodes_needed=2)
        self.db.execute('INSERT INTO build_progress VALUES(?,?,?)',(stage,ordinal,json.dumps(reference,sort_keys=True,separators=(',',':'))));self.db.commit()
        self.done_refs[(stage,ordinal)]=reference

    def close(self):
        if self.db is not None:self.db.close();self.db=None

    def finish(self,result,key):
        self.close()
        if self.closed_result is None:
            result=public(result);result[key]={'path':str(self.shared),'bytes':self.physical.stat().st_size}
            self.state.update(phase='closed',result=result);I.save(self.checkpoint,self.state)
        result=self.state['result'];reference=result[key]
        if self.shared!=self.physical and not self.shared.is_file():
            partial=self.shared.with_name(self.shared.name+'.partial')
            argv=['rsync','-a','--sparse','--',str(self.physical),str(partial)]
            if self.guard:self.guard.run(argv,partial,self.physical.stat().st_size,2)
            else:subprocess.run(argv,check=True)
            os.replace(partial,self.shared)
        if not self.shared.is_file() or self.shared.stat().st_size!=reference['bytes']:raise ValueError('CLOSED_METADATA_SHARED_PUBLICATION_SIZE_DIFFERS')
        if self.state['phase']!='published':self.state['phase']='published';I.save(self.checkpoint,self.state)
        return result