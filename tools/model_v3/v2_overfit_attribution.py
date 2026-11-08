"""Plan the listed family probes or compose the final133-row diagnosis."""
import argparse
from phychem_mfm.phase1.v31_overfit_attribution import plan_families,plan_probe,build_attribution

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('plan-families','plan-probe','finish'))
    p.add_argument('--phase0')
    p.add_argument('--e2',action='append')
    p.add_argument('--plan')
    p.add_argument('--index',type=int)
    p.add_argument('--output')
    a=p.parse_args()
    if a.action=='plan-families':
        plan_families(a.phase0,a.e2,a.output)
    elif a.action=='plan-probe':
        plan_probe(a.plan,a.index)
    else:
        build_attribution(a.plan,a.output)
