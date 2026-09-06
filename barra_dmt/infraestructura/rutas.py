"""Rutas de archivos de la aplicacion.

La base de datos SQLite vive en el perfil del usuario de Windows
(%LOCALAPPDATA%\\BarraDMT\\barra_dmt.db), no junto al .exe. Asi funciona
sin permisos de administrador y sobrevive a que el usuario mueva o
reemplace el ejecutable.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

NOMBRE_CARPETA_APP = "BarraDMT"
NOMBRE_ARCHIVO_BD = "barra_dmt.db"


def carpeta_datos_app() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        base = str(Path.home())
    carpeta = Path(base) / NOMBRE_CARPETA_APP
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def ruta_base_datos() -> Path:
    return carpeta_datos_app() / NOMBRE_ARCHIVO_BD


def carpeta_imagenes_productos() -> Path:
    carpeta = carpeta_datos_app() / "imagenes"
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def ruta_ejecutable() -> Path:
    """Carpeta donde vive el .exe (o el script) cuando corre empaquetado con PyInstaller."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parents[2]
