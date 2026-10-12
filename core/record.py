"""Private generator protocol. Never invokes Netfilter."""
import json
import os
import sys
from pathlib import Path
args = sys.argv[1:]
if args[:2] == ['nft', '-f']:
    args = ['nft-file', Path(args[2]).read_text()]
with open(os.environ['SUITE_RECORD'], 'a', encoding='utf8') as f:
    f.write(json.dumps(args) + '\n')
