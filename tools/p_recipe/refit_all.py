"""Complete the approved D4 correction on one actual native compute node."""
import subprocess,sys
from pathlib import Path
root=Path('/tmp/zixiao_p_recipe_D4_20261113');root.mkdir(exist_ok=True)
script=Path(__file__).with_name('refit_d4.py')
for dataset in ('P_D','Pprime'):
 subprocess.run([sys.executable,'-B','-u',str(script),'--dataset',dataset,'--output',str(root/dataset),'--workers','8'],check=True)
subprocess.run([sys.executable,'-B','-u',str(script),'--publish'],check=True)