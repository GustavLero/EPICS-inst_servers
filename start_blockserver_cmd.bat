REM @echo off

set MYDIRBLOCK=%~dp0
rEM call %MYDIRBLOCK%..\..\..\config_env_base.bat

REM %HIDEWINDOW% h

set EPICS_CAS_INTF_ADDR_LIST=127.0.0.1
set EPICS_CAS_BEACON_ADDR_LIST=127.255.255.255

set PYTHONUNBUFFERED=TRUE

set MYDIRGATE=%MYDIRBLOCK%..\..\..\gateway
if exist "%ICPSETTINGSDIR%/gwblock.pvlist" (
    set GWBLOCK_PVLIST=%ICPSETTINGSDIR%/gwblock.pvlist
) else (
    set GWBLOCK_PVLIST=%MYDIRGATE%\gwblock_dummy.pvlist
)

C:\Python36\python.exe %MYDIRBLOCK%\block_server.py -od %MYDIRBLOCK%..\..\..\iocstartup -sd %MYDIRBLOCK%\schema\ -cd %ICPCONFIGROOT% -scd %ICPINSTSCRIPTROOT% -pv %GWBLOCK_PVLIST% -f ISIS
