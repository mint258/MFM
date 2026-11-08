"""Execute one user-specified M2 diagnostic experiment; no baseline rerun."""
import argparse
from phychem_mfm.phase1.v31_overfit_diagnosis import run_controlled

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixed-path',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--experiment',choices=('E1','E2','E3','E4'),required=True)
    parser.add_argument('--updates',type=int,required=True)
    parser.add_argument('--output-parameterization',choices=('raw','normalized'),default='normalized')
    parser.add_argument('--clip',type=float,default=1.)
    parser.add_argument('--lr',type=float,default=3e-4)
    parser.add_argument('--family')
    parser.add_argument('--head-hidden-dim',type=int,default=64)
    parser.add_argument('--resume')
    run_controlled(**vars(parser.parse_args()))
