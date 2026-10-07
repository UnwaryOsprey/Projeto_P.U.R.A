.venv\Scripts\python.exe -m pura --open@echo off
setlocal
cd /d "%~dp0"
echo ==============================================
echo   P.U.R.A. - iniciando (sem Docker)
echo ==============================================

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (
  where python >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo.
  echo Python nao encontrado.
  echo Instale em https://www.python.org/downloads/ e marque "Add python.exe to PATH".
  goto fim
)

if not exist ".venv\Scripts\python.exe" (
  echo Criando ambiente virtual...
  %PY% -m venv .venv
  if errorlevel 1 goto erro
)

if not exist ".venv\.instalado" (
  echo Instalando dependencias ^(so na primeira vez, pode levar 1-2 minutos^)...
  ".venv\Scripts\python.exe" -m pip install --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -e .
  if errorlevel 1 goto erro
  echo ok> ".venv\.instalado"
)

if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo Abrindo o painel no navegador. Para parar, feche esta janela ou pressione Ctrl+C.
".venv\Scripts\python.exe" -m pura --open %*
goto fim

:erro
echo.
echo Ocorreu um erro. Veja a mensagem acima.

:fim
echo.
pause
