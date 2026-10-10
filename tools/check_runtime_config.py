"""Print non-secret configuration status without starting any adapter."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from src.adapters.runtime_config import ConfigurationError,load_runtime_config


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('base',type=Path,nargs='?',default=ROOT/'config/runtime.example.json')
    parser.add_argument('--override',type=Path)
    parser.add_argument('--definition-root',type=Path)
    args=parser.parse_args()
    try:config=load_runtime_config(args.base,override_path=args.override,definition_root=args.definition_root)
    except ConfigurationError as exc:print(str(exc),file=sys.stderr);return 1
    print(json.dumps(config.safe_summary(),sort_keys=True));return 0


if __name__=='__main__':raise SystemExit(main())
