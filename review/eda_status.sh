#!/usr/bin/env bash
ps -eo pid,ppid,args | grep -E 'magic|klayout|netgen|apt-get|setup_eda|run_layout' | grep -v grep
