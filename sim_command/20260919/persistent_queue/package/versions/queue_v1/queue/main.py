import argparse
from qservice import start,serve

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','serve']);parser.add_argument('--node',choices=['A','B'],required=True)
    args=parser.parse_args()
    raise SystemExit(start(args.node) if args.action=='start' else serve(args.node))
