#!/bin/bash

SCRIPT=$(readlink -f ${BASH_SOURCE[0]})
SCRIPTPATH=`dirname "$SCRIPT"`
MYDIR=$SCRIPTPATH

# Ensure environment is set up
if [ -z "$EPICS_ROOT" ]; then
    . $MYDIR/../../../config_env_base.sh
fi

# kill procservs that manage process, which in turn terminates the process

PIDFILE="$EPICS_ROOT/EPICS_BLOCKSVR.pid"
if [ -r "$PIDFILE" ]; then
    CSPID=`cat $PIDFILE`
    echo "Killing blockserver procServ with PID $CSPID"
    kill $CSPID
    rm $PIDFILE
else
    echo "Blockserver procServ is not running (or $PIDFILE not readable)"
fi

