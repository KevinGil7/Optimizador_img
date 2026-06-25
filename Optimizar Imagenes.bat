@echo off
REM Lanza la aplicacion de escritorio del Optimizador de Imagenes (sin consola).
cd /d "%~dp0"

REM Intenta con el lanzador 'pyw' (incluido con Python en Windows), luego 'pythonw'.
where pyw >nul 2>nul && ( start "" pyw "optimizar_imagenes_app.py" & exit /b )
where pythonw >nul 2>nul && ( start "" pythonw "optimizar_imagenes_app.py" & exit /b )

echo No se encontro Python en esta PC.
echo Instalalo gratis desde https://www.python.org/downloads/
echo (marca "Add python.exe to PATH" al instalar) y vuelve a intentar.
pause
