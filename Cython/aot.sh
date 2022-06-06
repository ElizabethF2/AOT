#!/bin/sh

# AOT bootstraper as a Bash script
# This script trades portability for speed by avoiding launching python on every launch but the first

AOT_NAME=Game_Release_Checker
AOT_CACHE=__aotcache__

if [ ! -z "$(find . -newer "$AOT_CACHE/$AOT_NAME" -iname "*.py" 2>&1)" ]; then
  python aotc.py
  rm -rf $AOT_CACHE/http
fi

$AOT_CACHE/$AOT_NAME "$@"
