"""Small source/metadata operations; never read scientific data bodies."""
import datetime,hashlib,json,os,pathlib,re,socket,subprocess,stat
ROOT=pathlib.Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025')
REPO=ROOT/'repository';PROJECT=ROOT.parent.parent;PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'

def need(ok,message):
    if not ok:raise ValueError(message)

def read_small(path):
    p=pathlib.Path(path);need(p.is_absolute() and '..' not in p.parts and not p.is_symlink(),'LITERAL_METADATA')
    with p.open('rb') as f:
        st=os.fstat(f.fileno());need(stat.S_ISREG(st.st_mode) and st.st_size<=2*1024**2,'SMALL_METADATA_ONLY')
        b=f.read(2*1024**2+1);after=os.fstat(f.fileno())
    need(len(b)==st.st_size and (st.st_ino,st.st_mtime_ns,st.st_size)==(after.st_ino,after.st_mtime_ns,after.st_size),'METADATA_CHANGED')
    return b

def pin(path):
    b=read_small(path);return {'path':str(path),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()}

def load(path):return json.loads(read_small(path))
def write_new(path,obj):
    raw=(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode();need(len(raw)<2*1024**2,'SMALL_METADATA_OUTPUT')
    path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    return pin(path)
def fields(text):return dict(re.findall(r'(\w+)=([^\s]+)',text))
def query(argv):
    r=subprocess.run(argv,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=45)
    need(r.returncode==0,'QUERY_FAILED:'+repr({'argv':argv,'returncode':r.returncode,'stderr':r.stderr}));return r.stdout

def on_login():need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi','ROOT_LOGIN_METADATA_ONLY')
def now():return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
def uid(job):return int(re.fullmatch(r'[^()]+\((\d+)\)',job['UserId'])[1])
def quota_free(raw):
    rows=[s.split() for s in raw.splitlines() if s.strip().startswith('/')];need(len(rows)==1,'EXACT_QUOTA_ROW')
    vals=[int(v.rstrip('*')) for v in rows[0][1:4]];limits=[v for v in vals[1:] if v>0]
    need(limits,'KNOWN_QUOTA_LIMIT');return (min(limits)-vals[0])*1024

def memory_mib(value):
    m=re.fullmatch(r'(\d+)([KMGTP]?)',value);need(m,'EXACT_MEMORY_UNIT')
    return int(m[1])*{'K':1/1024,'M':1,'G':1024,'T':1024**2,'P':1024**3}[m[2] or 'M']
