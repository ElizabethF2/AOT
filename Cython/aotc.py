# Use Cython to AOT compile a given script and its dependencies to native binaries
# Designed to be embedded within a batch or shell script which will check when compilation is needed and will run the compiled code

import sys, os, subprocess, platform, re, shutil, ast, importlib.util, warnings, threading, queue, json, Cython.Compiler.Main

name = os.environ.get('AOT_NAME', 'main')
cache = os.environ.get('AOT_CACHE', '__aotcache__')
job_count = int(os.environ.get('AOT_JOBS', 8))
copy_original = int(os.environ.get('AOT_COPY_ORIGINAL', 0))
link_original = int(os.environ.get('AOT_LINK_ORIGINAL', 0))
delete_incomplete_packages = int(os.environ.get('AOT_DELETE_INCOMPLETE_PACKAGES', 0))
additional_packages = json.loads(os.environ.get('AOT_ADDITIONAL_PACKAGES', '[]'))

directories_to_delete = set()
machine = platform.uname().machine.lower()
work_queue = queue.Queue()
main_thread_done = False

def append_paths_to_env(name, paths):
  if type(paths) is str:
    paths = [paths]
  os.environ[name] = (';' if os.name == 'nt' else ':').join([os.environ.get(name, '')] + paths + [''])

def module_name_to_cache_path(module_name):
  path = os.path.join(cache, os.path.sep.join(module_name.split('.')))
  try:
    os.makedirs(os.path.dirname(path))
  except FileExistsError:
    pass
  return path

def get_compiler_function():
  vswhere = shutil.which('vswhere')
  if not vswhere:
    vswhere = shutil.which(os.path.expandvars('%ProgramFiles(x86)%/Microsoft Visual Studio/Installer/vswhere.exe'))
  if vswhere:
    base = sorted([i[17:].strip() for i in filter(lambda i: i.startswith('installationPath:'), subprocess.check_output(vswhere).decode().splitlines())])[-1]
    vcvarsall = os.path.join(base, 'VC\\Auxiliary\\Build\\vcvarsall.bat')

    append_paths_to_env('INCLUDE', os.path.join(os.path.dirname(sys.executable), 'include'))
    append_paths_to_env('LIB', os.path.join(os.path.dirname(sys.executable), 'libs'))

    def compile(name, shared=False):
      args = ['cmd', '/c', 'call', vcvarsall, machine, '&', 'cl']
      if shared:
        args += ['/LD', '/Fe:'+module_name_to_cache_path(name)+'.pyd']
      else:
        args += ['/Fe:'+os.path.join(cache, name+'.exe')]
      args += ['/Fo:'+os.path.join(cache, name+'.o'), os.path.join(cache, name+'.c')]
      subprocess.check_call(args)
    return compile

  gcc = os.environ.get('CC')
  if not gcc:
    gcc = shutil.which('gcc')
  if not gcc:
    gcc = shutil.which('clang')  
  if gcc:
    def compile(name, shared=False):
      args = ['gcc']
      if shared:
        args += ['-shared', '-o', module_name_to_cache_path(name)+'.so']
      else:
        args += ['-o', os.path.join(cache, name)]
      args = [os.path.join(cache, name)]
      subprocess.check_call(args)
    return compile

  raise Exception('No compatible compilers found')

def walk_dependencies_by_name(module_name, current_module=None):
  spec = None
  try:
    if current_module:
      spec = importlib.util.find_spec(current_module + '.' + module_name)
  except (ModuleNotFoundError, ValueError):
    pass
  try:
    if not spec:
      spec = importlib.util.find_spec(module_name)
  except (ModuleNotFoundError, ValueError):
    pass
  if spec and spec.has_location:
    name = spec.name
    if spec.submodule_search_locations and spec.origin.endswith('__init__.py'):
      name += '.__init__'
    walk_dependencies_by_path(spec.origin, name=name)

visited_dependencies = set()
visited_dependencies_lock = threading.Lock()
def walk_dependencies_by_path(module_path, name=None):
  # Avoid circular references and recompiling already compiled modules
  with visited_dependencies_lock:
    if module_path in visited_dependencies:
      return
    visited_dependencies.add(module_path)

  # Compile the current dependency as a shared object if it has a name
  if name:
    work_queue.put({'type': 'cythonize', 'name': name, 'module_path': module_path})
    return

  walk_dependencies_by_path_postbuild(module_path, name)

def walk_dependencies_by_path_postbuild(module_path, name):
  current_module = name[:name.rfind('.')] if name else None

  # Load and decode the source code file
  # Parse the PEP 263 encoding if one exists
  code = None
  with open(module_path, 'rb') as f:
    code_bytes = f.read()
    for line in code_bytes.splitlines()[:2]:
      match = re.match(b'^[ \t\f]*#.*?coding[:=][ \t]*([-_.a-zA-Z0-9]+)', line)
      if match:
        try:
          code = code_bytes.decode(match.group(1).decode())
          break
        except ValueError:
          pass
    if not code:
      try:
        code = code_bytes.decode()
      except ValueError:
        return

  # Parse the code and look for more dependencies
  for node in ast.walk(ast.parse(code)):
    if any((isinstance(node, i) for i in (ast.ImportFrom, ast.Import))):
      if hasattr(node, 'module') and node.module:
        walk_dependencies_by_name(node.module, current_module=current_module)
      for alias in node.names:
        walk_dependencies_by_name(alias.name, current_module=current_module)

def work_thread():
  while True:
    try:
      work_item = work_queue.get(timeout=1)
    except queue.Empty:
      if main_thread_done:
        return
      continue

    if work_item['type'] == 'main':
      sys.argv = ['', '--embed', '-'+str(sys.version_info.major), '-o', os.path.join(cache, name+'.c'), name+'.py']
      Cython.Compiler.Main.main(True)
      compile(name)
    elif work_item['type'] == 'cythonize':
      proc = subprocess.run([sys.executable, '-m', 'cython', '-'+str(sys.version_info.major), '-o', os.path.join(cache, work_item['name']+'.c'), work_item['module_path']])
      if proc.returncode != 0:
        warnings.warn('Couldn\'t compile ' + work_item['name'] + ', the original version will be used as a fallback')
        if copy_original:
          shutil.copy2(work_item['module_path'], module_name_to_cache_path(work_item['name'])+os.path.splitext(work_item['module_path'])[-1])
        elif link_original and work_item['name'].count('.') > 0:
          os.symlink(work_item['module_path'], module_name_to_cache_path(work_item['name'])+os.path.splitext(work_item['module_path'])[-1])
        if delete_incomplete_packages and work_item['name'].count('.') > 0:
          directories_to_delete.add(os.path.dirname(module_name_to_cache_path(work_item['name'])))
      else:
        work_queue.put({'type': 'compile', 'name': work_item['name'], 'module_path': work_item['module_path']})
    elif work_item['type'] == 'compile':
      compile(work_item['name'], shared=True)
      walk_dependencies_by_path_postbuild(work_item['module_path'], work_item['name'])
    elif work_item['type'] == 'named_dependency':
      walk_dependencies_by_name(work_item['name'])

def build():
  global compile, main_thread_done

  # Find the compiler
  compile = get_compiler_function()

  # Create the cache dir if it doesn't already exist
  try: os.makedirs(cache)
  except FileExistsError: pass

  # Start worker threads
  worker_threads = [threading.Thread(target=work_thread) for _ in range(job_count)]
  for thread in worker_threads:
    thread.start()

  # Queue building the main binary
  work_queue.put({'type': 'main'})

  # Compile dependencies asynchronously
  walk_dependencies_by_path(name+'.py')

  # If there are any additional packages, compile them asynchronously too
  for package in additional_packages:
    work_queue.put({'type': 'named_dependency', 'name': package})

  # Generate environment script
  if os.name == 'nt':
    with open(os.path.join(cache, 'env.bat'), 'w') as f:
      f.write('set PATH=%PATH%;'+os.path.join(os.path.dirname(sys.executable), 'DLLs')+';'+os.path.dirname(sys.executable)+';')

  # Wait for queued work to finish
  main_thread_done = True
  for thread in worker_threads:
    thread.join()

  # Cleanup intermediary files
  for root, dirs, files in os.walk(cache):
    for file in files:
      if os.path.splitext(file)[-1] in ('.exp', '.o', '.c', '.lib'):
        os.remove(os.path.join(root, file))
  for directory in directories_to_delete:
    shutil.rmtree(directory)

if __name__ == '__main__':
  build()
