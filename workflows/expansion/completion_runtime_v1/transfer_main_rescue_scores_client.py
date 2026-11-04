"""Windows client only: binary SSH IO for already closed Main rescue scores."""
import argparse,json,os,re,shutil,subprocess,threading
def drain(stream,target,limit):
    size=0
    while True:
        block=stream.read(65536)
        if not block:break
        if size<limit:target.append(block[:limit-size])
        size+=len(block)
def text(parts):return b''.join(parts).decode('utf-8','replace')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target-config',required=True);p.add_argument('--source-index',required=True);a=p.parse_args()
    if not re.fullmatch(r'/gfshome/alpha/codex_data_v1_20261026/control/pubchem_completion_environment_20261103/[A-Za-z0-9_.-]+\.json',a.target_config):
        raise ValueError('Literal Alpha IO config')
    if not re.fullmatch(r'/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/pubchem_alpha_return_20261103/[A-Za-z0-9_.-]+\.json',a.source_index):
        raise ValueError('Literal Main closed index')
    ssh='ssh.exe'if os.name=='nt'else'ssh';flags=subprocess.CREATE_NO_WINDOW if os.name=='nt'else 0
    target_cmd='/gfshome/alpha/codex_data_v1_20261026/software/pubchem_completion_20261103_venv/bin/python -I -B /gfshome/alpha/codex_data_v1_20261026/control/pubchem_completion_environment_20261103/main_rescue_score_transport_20261104_v1.py receive --config '+a.target_config
    target=subprocess.Popen([ssh,'-T','-o','BatchMode=yes','-o','ConnectTimeout=10','alpha@218.192.171.238',target_cmd],
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=flags)
    target_err=[];target_out=[];source_err=[]
    threads=[threading.Thread(target=drain,args=(target.stderr,target_err,16<<20),daemon=True)];threads[0].start()
    source=None
    try:
        ready=target.stdout.readline()
        if ready.strip()!=b'READY':
            target.wait();threads[0].join();raise RuntimeError('Alpha IO not ready: '+repr(ready)+' '+text(target_err))
        thread=threading.Thread(target=drain,args=(target.stdout,target_out,4<<20),daemon=True);thread.start();threads.append(thread)
        control='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/control/pubchem_alpha_return_20261103'
        py='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/software/pubchem_completion_20261103_venv/bin/python'
        script='/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/worktrees/pubchem_completion_20261103/workflows/expansion/completion_runtime_v1/main_rescue_score_transport.py'
        command='ssh -n -T -o BatchMode=yes -o StrictHostKeyChecking=yes -o HostKeyAlgorithms=ssh-ed25519 -o UserKnownHostsFile='+control+'/main16_verified_known_hosts_20261104 compute-0-16 '+py+' -I -B '+script+' send --index '+a.source_index
        source=subprocess.Popen([ssh,'-n','-T','-o','BatchMode=yes','-o','ConnectTimeout=10','descriptor-analysis-remote',command],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=flags)
        thread=threading.Thread(target=drain,args=(source.stderr,source_err,16<<20),daemon=True);thread.start();threads.append(thread)
        print(json.dumps(dict(event='BINARY_CLOSED_SCORE_COPY_STARTED',source_pid=source.pid,target_pid=target.pid)),flush=True)
        shutil.copyfileobj(source.stdout,target.stdin,length=1<<20);target.stdin.close()
        source.wait();target.wait()
        for thread in threads:thread.join()
        if source.returncode or target.returncode:
            raise RuntimeError('IO failed source='+str(source.returncode)+' target='+str(target.returncode)
                +' source_stderr='+text(source_err)+' target_stderr='+text(target_err))
        print(text(target_out),end='',flush=True);print('SOURCE_IO_STATUS '+text(source_err),flush=True)
    except BaseException:
        for process in(source,target):
            if process is not None and process.poll()is None:process.terminate();process.wait()
        for thread in threads:thread.join()
        print('SOURCE_IO_STDERR '+text(source_err),flush=True);print('TARGET_IO_STDERR '+text(target_err),flush=True)
        raise
if __name__=='__main__':main()
