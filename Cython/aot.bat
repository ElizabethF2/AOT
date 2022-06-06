@echo OFF
rem AOT bootstraper as a Windows Batch script
rem This script trades portability for speed by avoiding launching python on every launch but the first

set AOT_NAME=Game_Release_Checker
set AOT_CACHE=__aotcache__

if not exist "%AOT_CACHE%\env.bat" goto compilation_required

cscript //nologo //e:vbscript aot_check_mtimes.vbs "%AOT_CACHE%"
if %ERRORLEVEL% EQU 0 goto skip_compilation

:compilation_required
py aotc.py
rmdir /S /Q %AOT_CACHE%\http

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
call %AOT_CACHE%\env.bat
%AOT_CACHE%\%AOT_NAME%.exe %*
