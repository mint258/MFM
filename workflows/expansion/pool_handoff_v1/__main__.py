"""Existing allocated parent only; no scheduler or scientific rescreening."""
import argparse
from .runtime import load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    args = parser.parse_args()
    action = load(args.plan)['action']
    if action == 'merge':
        from .merge import run
    elif action == 'filter':
        from .filter import run
    elif action == 'baseline':
        from .baseline import run
    elif action == 'query_projection':
        from .query import run
    else:
        raise ValueError('Unknown admitted stage: ' + str(action))
    run(args.plan)


if __name__ == '__main__':
    main()
