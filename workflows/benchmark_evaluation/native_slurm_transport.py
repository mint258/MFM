"""Use the actual local Slurm controller for mutations; retry only refused read-only accounting."""
import shlex
import subprocess
import time

def native_control(args, *, runner=None, sleeper=None):
    if not isinstance(args,(list,tuple)) or not args or any(not isinstance(value,str) for value in args):
        raise ValueError("Explicit native Slurm argument list required")
    args=list(args);operation=args[0]
    if operation=="sacct":
        command=["ssh","-n","-o","BatchMode=yes","-o","ConnectTimeout=10","sonmi",shlex.join(args)]
        attempts=3
    elif operation=="sbatch":
        if "--parsable" not in args or "--hold" not in args:
            raise ValueError("Only held, native-ID-returning submissions are permitted")
        command=args;attempts=1
    elif operation=="scontrol":
        if len(args)!=3 or args[1]!="release" or not args[2].isdigit():
            raise ValueError("Only one recorded native held job may be released")
        command=args;attempts=1
    else:
        raise ValueError("Unregistered native Slurm transport operation")
    runner=subprocess.run if runner is None else runner
    sleeper=time.sleep if sleeper is None else sleeper
    for attempt in range(attempts):
        result=runner(command,text=True,capture_output=True,timeout=60)
        if result.returncode==0:return result.stdout.strip()
        error=subprocess.CalledProcessError(result.returncode,command,output=result.stdout,stderr=result.stderr)
        if (operation=="sacct" and result.returncode==255
            and "Connection refused" in (result.stderr or "") and attempt+1<attempts):
            sleeper(attempt+1)
        else:raise error
