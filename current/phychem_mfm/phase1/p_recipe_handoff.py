"""Publish complete P checkpoints, then acknowledge a cooperative handoff."""
import json,os
from pathlib import Path
from .v2_disk import save_checkpoint

def atomic_json(path,value):
 path=Path(path);temporary=path.with_name(path.name+'.tmp.'+str(os.getpid()))
 with temporary.open('x') as stream:
  stream.write(json.dumps(value,indent=2)+'\n');stream.flush();os.fsync(stream.fileno())
 os.replace(temporary,path)

def publish_checkpoint(payload,path):
 path=Path(path)
 if path.exists():raise FileExistsError('Immutable checkpoint already exists: '+str(path))
 temporary=path.with_name(path.name+'.writing.'+str(os.getpid()))
 save_checkpoint(payload,temporary)
 with temporary.open('rb') as stream:os.fsync(stream.fileno())
 # A final *.pt name always denotes a closed, complete save, never a partial.
 os.link(temporary,path);temporary.unlink()

def read_request(configuration):
 path=configuration.get('handoff_request')
 if not path or not Path(path).is_file():return None
 request=json.loads(Path(path).read_text())
 if request.get('run')!=configuration['run'] or request.get('action')!='SAVE_AND_EXIT':
  raise ValueError('Handoff request does not identify this training run')
 return request

def publish_ack(configuration,request,checkpoint,clock):
 ack=dict(request_id=request['request_id'],job_id=request['job_id'],checkpoint=str(checkpoint),clock=clock,run=configuration['run'])
 atomic_json(configuration['handoff_ack'],ack);return ack
