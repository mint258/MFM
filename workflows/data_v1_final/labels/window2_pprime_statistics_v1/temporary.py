"""Explicit temporary placement with the existing disk/quota protection policy."""
import contextlib,json,os,tempfile,threading,time
from pathlib import Path

KEYS=('temporary_root','temporary_spill_limit_bytes','disk_protection')

def specification(plan):return {key:plan[key] for key in KEYS}

class Runtime:
    def __init__(self,spec,guard):self.spec=spec;self.guard=guard;self.root=Path(spec['temporary_root']).absolute()
    def wait(self,path=None):self.guard.wait(self.root if path is None else path)
    def sqlite(self,connection,path):
        def progress():
            self.wait()
            if path is not None:self.wait(path)
            return 0
        connection.set_progress_handler(progress,10000)
        return connection
    def duckdb_settings(self,connection):
        self.wait();directory=self.root/('duckdb_'+os.environ.get('SLURM_JOB_ID','metadata')+'_'+str(os.getpid()))
        self.guard.check(directory,inodes_needed=1);directory.mkdir(exist_ok=True)
        quote=lambda value:"'"+str(value).replace("'","''")+"'"
        connection.execute('SET temp_directory='+quote(directory))
        connection.execute('SET max_temp_directory_size='+quote(str(self.spec['temporary_spill_limit_bytes'])+'B'))
        return directory
    @contextlib.contextmanager
    def duckdb(self,connection):
        self.duckdb_settings(connection);stop=threading.Event();failed=[]
        def monitor():
            while not stop.wait(min(self.guard.poll,0.25)):
                try:self.guard.check(self.root)
                except Exception as error:
                    failed.append(error);connection.interrupt();return
        thread=threading.Thread(target=monitor,daemon=True);thread.start()
        try:yield connection
        finally:
            stop.set();thread.join()
            if failed:raise failed[0]

def activate(plan,admit=True):
    from workflows.data_v1_final.export.v31_stream_v1 import disk_guard as D
    spec=specification(plan);root=Path(spec['temporary_root']).absolute()
    if str(root) in ('/tmp','/var/tmp') or str(root).startswith(('/tmp/','/var/tmp/')):
        raise D.DiskUnavailable('ROOT_TMP_TEMPORARY_PATH_FORBIDDEN')
    limit=spec['temporary_spill_limit_bytes']
    if type(limit) is not int or limit<=0:raise D.DiskUnavailable('EXPLICIT_POSITIVE_TEMP_SPILL_BUDGET_REQUIRED')
    while True:
        try:
            guard=D.from_plan(spec,required=True,admit=admit);target=guard.target(root)
            if target['facts']['root_filesystem']:raise D.DiskUnavailable('ROOT_FILESYSTEM_TEMPORARY_PATH_FORBIDDEN')
            if limit>target['budget']['peak_additional_bytes']:raise D.DiskUnavailable('SPILL_LIMIT_NOT_COVERED_BY_DECLARED_PEAK')
            break
        except D.DiskUnavailable as error:
            if not str(error).startswith(('DISK_RESERVE_REACHED','ACCOUNT_QUOTA_RESERVE_REACHED','ACCOUNT_QUOTA_SNAPSHOT_UNKNOWN','TARGET_CAPACITY_UNKNOWN','TARGET_MOUNT_UNKNOWN')):raise
            print(json.dumps({'phase':'TEMPORARY_STORAGE_WAIT','reason':str(error),'no_temp_write_started':True}),flush=True)
            time.sleep(float(spec['disk_protection'].get('poll_seconds',1)))
        except (OSError,ValueError,__import__('subprocess').CalledProcessError) as error:
            print(json.dumps({'phase':'TEMPORARY_STORAGE_WAIT','reason':repr(error),'no_temp_write_started':True}),flush=True);time.sleep(1)
    guard.wait(root,inodes_needed=1);root.mkdir(parents=True,exist_ok=True)
    for name in ('TMPDIR','TMP','TEMP','SQLITE_TMPDIR'):os.environ[name]=str(root)
    tempfile.tempdir=str(root)
    return Runtime(spec,guard)
