#!/bin/sh

# A port of aot.py as a Bash script
# This script trades portability for speed by avoiding launching python on every launch but the first
# See the original, aot.py, for details

NAME=Game_Release_Checker

if [ ! -z "$(find . -newer "$NAME.dist/env.sh" -iname "*.py" 2>&1)" ]; then
  python -m nuitka --follow-stdlib --follow-imports --include-module=aot_dependencies --standalone --remove-output $NAME.py
  python -c "exec('import os, glob, importlib.util;\nfor fname in filter(lambda i: os.path.splitext(i)[-1] in (\'.so\', \'.pem\') or \'.so.\' in os.path.basename(i), glob.iglob(\'$NAME.dist/**\', recursive=True)):\n  os.remove(fname)\n  if os.path.splitext(fname)[-1] == \'.so\' or \'.so.\' in fname:\n    try: os.symlink(importlib.util.find_spec(\'.\'.join(fname[:fname.rfind(\'.so\')].split(os.path.sep)[1:])).origin, fname)\n    except AttributeError: pass')"
  python -c "import sys;f = open('$NAME.dist/env.sh', 'w'); f.write(':'.join(['export PATH='+chr(36)+'PATH']+sys.path+['']))"
fi

. $NAME.dist/env.sh
$NAME.dist/$NAME "$@"
