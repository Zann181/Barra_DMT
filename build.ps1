# Genera BarraDMT.exe en la raiz del proyecto (junto a arrancar.bat): un solo
# archivo portable, sin necesidad de instalar Python.
# Uso: powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"

python -m pip install --quiet --upgrade -r requirements.txt

pyinstaller --noconfirm --clean --onefile --windowed `
    --name "BarraDMT" `
    --icon "barra_dmt\presentacion\logo.ico" `
    --add-data "barra_dmt\datos_iniciales;datos_iniciales" `
    --distpath "." `
    run.py

Write-Host ""
Write-Host "Listo: BarraDMT.exe" -ForegroundColor Green
Write-Host "Copialo a cualquier PC con Windows y ejecutalo con doble clic. No necesita instalar nada."
