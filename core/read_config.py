#!/usr/bin/python3
"""NUL-delimited declarative values for operational shell scripts; never eval."""
import argparse
import os
from pathlib import Path
import sys
sys.dont_write_bytecode = True

# Verify additional privileged Python code before importing any project module.
# The entrypoint itself must already be trusted by its caller.
if os.geteuid() == 0:
    import stat
    install_root = Path(__file__).resolve().parents[1]
    isolated = Path('/proc/self/uid_map').read_text().strip().split() != ['0', '0', '4294967295']
    for code_path in [install_root, install_root / 'core', *(install_root / 'core').rglob('*')]:
        for item in [code_path, *code_path.parents]:
            info = item.lstat()
            directory = stat.S_ISDIR(info.st_mode)
            owner = info.st_uid == 0 or (isolated and directory and info.st_uid == 65534)
            sticky = directory and owner and bool(info.st_mode & stat.S_ISVTX)
            if stat.S_ISLNK(info.st_mode) or not ((owner and not info.st_mode & 0o022) or sticky):
                print(f'ERROR: untrusted privileged code path: {item}', file=sys.stderr)
                sys.exit(2)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.config import assignments, trusted, PolicyError, require
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('path')
p.add_argument('--allowed', default='')
p.add_argument('--trusted-path', action='store_true')
p.add_argument('--private-directory', action='store_true', help='Reject writable/sticky state-directory ancestors')
a=p.parse_args()
try:
    if os.geteuid()==0:
        trusted(a.path)
        if a.private_directory:
            path=Path(a.path).absolute()
            require(path.is_dir(), 'State parent must be a directory')
            require(all(not p.lstat().st_mode & 0o022 for p in [path,*path.parents]), 'State directory ancestors must not be writable by group/others')
    if a.trusted_path:
        sys.exit(0)
    values=assignments(Path(a.path).read_text())
    if a.allowed:
        require(set(values)<=set(a.allowed.split(',')), 'Unknown operational configuration keys')
    for k,v in values.items():
        sys.stdout.buffer.write(k.encode()+b'\0'+v.encode()+b'\0')
except (PolicyError, OSError, ValueError) as e:
    print('ERROR:',e,file=sys.stderr);sys.exit(2)
