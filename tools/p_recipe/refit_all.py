"""Complete the approved D4 correction on one actual native compute node."""
import argparse,subprocess,sys
from pathlib import Path
root=Path('/tmp/zixiao_p_recipe_D4_20261113');root.mkdir(exist_ok=True)
script=Path(__file__).with_name('refit_d4.py')
parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=8)
args=parser.parse_args()
for dataset in ('P_D','Pprime'):
 subprocess.run([sys.executable,'-B','-u',str(script),'--dataset',dataset,'--output',str(root/dataset),'--workers',str(args.workers)],check=True)
subprocess.run([sys.executable,'-B','-u',str(script),'--publish'],check=True)
