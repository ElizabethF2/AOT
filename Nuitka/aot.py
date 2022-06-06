# A simple AOT shim
# Will use Nuitka to compile the script specified in the variable 'name' if any .py have changed since last compilation or if a build has never been run
# To save disk space and runtime memory, the compiled script is linked against shared libraries in the existing Python install

import os, sys, glob, subprocess, importlib.util

name = 'Game_Release_Checker'
bin = os.path.join(name+'.dist', name+ ('.exe' if os.name == 'nt' else ''))

try: last_compile_time = os.path.getmtime(bin)
except FileNotFoundError: last_compile_time = -1

for fname in glob.iglob('*.py', recursive=True):
  if os.path.getmtime(fname) >= last_compile_time:
    subprocess.check_output([sys.executable, '-m', 'nuitka', '--follow-stdlib', '--follow-imports', '--include-module=aot_dependencies', '--standalone', '--remove-output', name+'.py'])
    for fname in filter(lambda i: os.path.splitext(i)[-1] in ('.dll', '.so', '.pyd', '.pem') or '.so.' in os.path.basename(i), glob.iglob(name+'.dist/**', recursive=True)):
      os.remove(fname)
      if os.path.splitext(fname)[-1] == '.pyd':
        os.symlink(importlib.util.find_spec('.'.join(os.path.splitext(fname)[0].split(os.path.sep)[1:])).origin, fname)
      elif os.path.splitext(fname)[-1] == '.so' or '.so.' in fname:
        try: os.symlink(importlib.util.find_spec('.'.join(fname[:fname.rfind('.so')].split(os.path.sep)[1:])).origin, fname)
        except AttributeError: pass
    break

os.environ['PATH'] += (';' if os.name == 'nt' else ':').join(['']+sys.path+[''])
sys.exit(subprocess.run([bin] + sys.argv).returncode)
