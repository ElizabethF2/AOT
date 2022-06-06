@echo OFF
rem A port of aot.py as a Windows Batch script
rem This script trades portability for speed by avoiding launching python on every launch but the first
rem See the original, aot.py, for details

set NAME=Game_Release_Checker

if not exist "%NAME%.dist\env.bat" goto compilation_required

cscript //nologo //e:vbscript aot_check_mtimes.vbs "%NAME%"
if %ERRORLEVEL% EQU 0 goto skip_compilation

:compilation_required
py -m nuitka --follow-stdlib --follow-imports --include-module=aot_dependencies --standalone --remove-output %NAME%.py
py -c "exec('import os, glob, importlib.util;\nfor fname in filter(lambda i: os.path.splitext(i)[-1] in (\'.dll\', \'.pyd\', \'.pem\'), glob.iglob(\'%NAME%.dist/**\', recursive=True)):\n  os.remove(fname)\n  if os.path.splitext(fname)[-1] == \'.pyd\':\n    os.symlink(importlib.util.find_spec(\'.\'.join(os.path.splitext(fname)[0].split(os.path.sep)[1:])).origin, fname)')"
py -c "import sys;f = open('%NAME%.dist\env.bat', 'w'); f.write(';'.join(['set PATH='+chr(37)+'PATH'+chr(37)]+sys.path+['']))"

:skip_compilation
rem Get args, preserve quotes
set args=%1
shift
:next_arg
if [%1] == [] goto do_run
set args=%args% %1
shift
goto next_arg

:do_run
call %NAME%.dist\env.bat
%NAME%.dist\%NAME%.exe %*
