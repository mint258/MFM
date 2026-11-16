"""Run the expressly requested M2 zero-training diagnosis."""
import argparse
from phychem_mfm.phase1.v31_overfit_diagnosis import phase0, finish_phase0_summary, classify_phase0

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--device', default='cuda')
    parser.add_argument('--finish-summary', action='store_true')
    parser.add_argument('--classify', action='store_true')
    args = parser.parse_args()
    if args.classify:
        classify_phase0(args.output)
    elif args.finish_summary:
        finish_phase0_summary(args.output)
    else:
        phase0(args.output, device=args.device)
