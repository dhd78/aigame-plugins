@echo off
setlocal
REM Build with Visual Studio x86 toolchain.

call "C:\Program Files\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars32.bat"
if errorlevel 1 exit /b 1

cl /nologo /LD /MT /O2 /std:c++17 /EHsc ^
  /I sdk ^
  src\senren_bridge_v3.cpp sdk\tp_stub.cpp ^
  /link ws2_32.lib user32.lib ^
  /Fe:senren_bridge_v3.2.dll
if errorlevel 1 exit /b 1

cl /nologo /MT /O2 src\injector.cpp /Fe:injector.exe
if errorlevel 1 exit /b 1

echo OK
