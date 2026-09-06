"""Conexion SQLite y creacion del esquema. Unico lugar que conoce SQL crudo."""
from __future__ import annotations

import shutil
import sqlite3
import time
import uuid

from .rutas import NOMBRE_ARCHIVO_BD, carpeta_datos_app, carpeta_datos_iniciales, ruta_base_datos

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS productos (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    categoria TEXT NOT NULL,
    precio INTEGER NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1,
    stock INTEGER NOT NULL DEFAULT 0,
    stock_minimo INTEGER NOT NULL DEFAULT 5,
    costo INTEGER NOT NULL DEFAULT 0,
    imagen_archivo TEXT,
    orden INTEGER NOT NULL DEFAULT 0,
    unidades_por_paca INTEGER NOT NULL DEFAULT 1,
    ultima_cantidad_pacas INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS movimientos_stock (
    id TEXT PRIMARY KEY,
    producto_id TEXT NOT NULL,
    nombre_producto TEXT NOT NULL,
    cantidad INTEGER NOT NULL,
    timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sesiones_caja (
    id TEXT PRIMARY KEY,
    cajero TEXT NOT NULL,
    abierta_en REAL NOT NULL,
    efectivo_inicial INTEGER NOT NULL,
    cerrada_en REAL
);

CREATE TABLE IF NOT EXISTS ventas (
    id TEXT PRIMARY KEY,
    sesion_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    total INTEGER NOT NULL,
    metodo_pago TEXT NOT NULL,
    efectivo_recibido INTEGER NOT NULL,
    cambio INTEGER NOT NULL,
    anulada INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (sesion_id) REFERENCES sesiones_caja(id)
);

CREATE TABLE IF NOT EXISTS venta_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id TEXT NOT NULL,
    producto_id TEXT NOT NULL,
    nombre TEXT NOT NULL,
    precio_unitario INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    FOREIGN KEY (venta_id) REFERENCES ventas(id)
);

CREATE TABLE IF NOT EXISTS cierres_caja (
    sesion_id TEXT PRIMARY KEY,
    cajero TEXT NOT NULL,
    abierta_en REAL NOT NULL,
    cerrada_en REAL NOT NULL,
    efectivo_inicial INTEGER NOT NULL,
    total_ventas INTEGER NOT NULL,
    total_efectivo INTEGER NOT NULL,
    total_tarjeta INTEGER NOT NULL,
    total_transferencia INTEGER NOT NULL,
    efectivo_esperado INTEGER NOT NULL,
    efectivo_contado INTEGER NOT NULL,
    diferencia INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS gastos (
    id TEXT PRIMARY KEY,
    sesion_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    total INTEGER NOT NULL,
    FOREIGN KEY (sesion_id) REFERENCES sesiones_caja(id)
);

CREATE TABLE IF NOT EXISTS gasto_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gasto_id TEXT NOT NULL,
    producto_id TEXT NOT NULL,
    nombre TEXT NOT NULL,
    costo_unitario INTEGER NOT NULL,
    cantidad INTEGER NOT NULL,
    FOREIGN KEY (gasto_id) REFERENCES gastos(id)
);

CREATE TABLE IF NOT EXISTS gastos_caja (
    id TEXT PRIMARY KEY,
    sesion_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    concepto TEXT NOT NULL,
    monto INTEGER NOT NULL,
    FOREIGN KEY (sesion_id) REFERENCES sesiones_caja(id)
);
"""

_PRODUCTOS_SEMILLA = [
    # Catalogo real de barra (reset 05/09/2026, planilla 5_09_2026.xlsx).
    # (nombre, categoria, precio, costo unitario, unidades por paca, stock inicial, pacas)
    ("Gatorade", "Sin alcohol", 12000, 3500, 12, 228, 19),
    ("Electrolit", "Sin alcohol", 20000, 7083, 12, 48, 4),
    ("Aguila", "Cervezas", 10000, 3125, 24, 96, 4),
    ("Club Colombia", "Cervezas", 10000, 3333, 24, 24, 1),
    ("Coronita", "Cervezas", 10000, 3125, 24, 120, 5),
    ("Smirnoff Botella", "Licores", 100000, 52000, 15, 45, 3),
    ("Red Bull", "Sin alcohol", 15000, 9500, 20, 20, 1),
    ("Amper", "Sin alcohol", 10000, 2833, 24, 24, 1),
    ("Smirnoff en Lata", "Licores", 15000, 7083, 24, 24, 1),
    ("Aguardiente Antioqueño", "Licores", 100000, 65000, 2, 2, 1),
    ("Ron Media", "Licores", 60000, 32000, 2, 2, 1),
    ("Four Loko", "Licores", 250000, 20400, 5, 5, 1),
    ("Tequila Olmeca", "Licores", 150000, 95000, 2, 2, 1),
    ("Tequila Jimador", "Licores", 150000, 95000, 2, 2, 1),
    ("Stella", "Cervezas", 10000, 3958, 24, 24, 1),
    ("Buchanan's", "Licores", 350000, 200000, 2, 2, 1),
    ("Agua", "Sin alcohol", 8000, 1000, 24, 456, 19),
]

_STOCK_MINIMO_SEMILLA = 10

# Columnas agregadas despues del primer lanzamiento: nombre -> definicion para ALTER TABLE.
_COLUMNAS_NUEVAS_PRODUCTOS = {
    "stock": "INTEGER NOT NULL DEFAULT 0",
    "stock_minimo": "INTEGER NOT NULL DEFAULT 5",
    "costo": "INTEGER NOT NULL DEFAULT 0",
    "imagen_archivo": "TEXT",
    "orden": "INTEGER NOT NULL DEFAULT 0",
    "unidades_por_paca": "INTEGER NOT NULL DEFAULT 1",
    "ultima_cantidad_pacas": "INTEGER NOT NULL DEFAULT 1",
}

# total_qr reusa la columna total_transferencia (ver repositorio_caja_sqlite);
# solo total_gastos_dmt es columna nueva de verdad.
_COLUMNAS_NUEVAS_CIERRES = {
    "total_gastos_dmt": "INTEGER NOT NULL DEFAULT 0",
    "total_gastos_caja": "INTEGER NOT NULL DEFAULT 0",
}


def obtener_conexion() -> sqlite3.Connection:
    conexion = sqlite3.connect(ruta_base_datos())
    conexion.execute("PRAGMA foreign_keys = ON")
    # WAL + synchronous NORMAL: evita fsync en cada commit. Con modo por
    # defecto (DELETE), cada venta hace 7+ commits (venta + items + stock
    # por producto) y cada uno bloquea con fsync -- se nota como lentitud
    # apenas hay varias ventas seguidas en un evento.
    conexion.execute("PRAGMA journal_mode = WAL")
    conexion.execute("PRAGMA synchronous = NORMAL")
    conexion.row_factory = sqlite3.Row
    return conexion


def _precargar_datos_iniciales_si_falta() -> None:
    """En un PC nuevo (sin BD todavia en %LOCALAPPDATA%) copia la BD e imagenes
    empaquetadas con la app, para que arranque con el catalogo/historial real
    en vez de con el semillero vacio. Si el usuario ya tiene datos, no toca nada."""
    destino_db = ruta_base_datos()
    if destino_db.exists():
        return
    origen = carpeta_datos_iniciales()
    origen_db = origen / NOMBRE_ARCHIVO_BD
    if not origen_db.exists():
        return
    shutil.copy2(origen_db, destino_db)
    origen_imagenes = origen / "imagenes"
    if origen_imagenes.is_dir():
        shutil.copytree(origen_imagenes, carpeta_datos_app() / "imagenes", dirs_exist_ok=True)


def inicializar_base_datos() -> None:
    _precargar_datos_iniciales_si_falta()
    conexion = obtener_conexion()
    try:
        conexion.executescript(_ESQUEMA)
        conexion.commit()
        _migrar_columnas_productos(conexion)
        _migrar_columnas_cierres(conexion)
        _sembrar_productos_si_vacio(conexion)
    finally:
        conexion.close()


def _migrar_columnas_productos(conexion: sqlite3.Connection) -> None:
    """Agrega columnas nuevas a bases de datos creadas antes de que existieran."""
    existentes = {fila["name"] for fila in conexion.execute("PRAGMA table_info(productos)")}
    orden_es_nueva = "orden" not in existentes
    for columna, definicion in _COLUMNAS_NUEVAS_PRODUCTOS.items():
        if columna not in existentes:
            conexion.execute(f"ALTER TABLE productos ADD COLUMN {columna} {definicion}")
    conexion.commit()
    if orden_es_nueva:
        # Bases viejas no tenian orden manual: se les asigna uno segun el
        # orden alfabetico que ya tenian, para que subir/bajar funcione de una.
        filas = conexion.execute("SELECT id FROM productos ORDER BY categoria, nombre").fetchall()
        conexion.executemany(
            "UPDATE productos SET orden = ? WHERE id = ?",
            [(i, fila["id"]) for i, fila in enumerate(filas)],
        )
        conexion.commit()


def _migrar_columnas_cierres(conexion: sqlite3.Connection) -> None:
    """Agrega columnas nuevas a bases de datos creadas antes de que existieran."""
    existentes = {fila["name"] for fila in conexion.execute("PRAGMA table_info(cierres_caja)")}
    for columna, definicion in _COLUMNAS_NUEVAS_CIERRES.items():
        if columna not in existentes:
            conexion.execute(f"ALTER TABLE cierres_caja ADD COLUMN {columna} {definicion}")
    conexion.commit()


def _sembrar_productos_si_vacio(conexion: sqlite3.Connection) -> None:
    total = conexion.execute("SELECT COUNT(*) AS n FROM productos").fetchone()["n"]
    if total > 0:
        return
    filas = [
        (uuid.uuid4().hex[:12], nombre, categoria, precio, 1, stock, _STOCK_MINIMO_SEMILLA,
         costo, unidades_por_paca, orden, pacas)
        for orden, (nombre, categoria, precio, costo, unidades_por_paca, stock, pacas)
        in enumerate(_PRODUCTOS_SEMILLA)
    ]
    conexion.executemany(
        """
        INSERT INTO productos (id, nombre, categoria, precio, activo, stock, stock_minimo,
                                costo, unidades_por_paca, orden, ultima_cantidad_pacas)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        filas,
    )
    conexion.commit()


def nuevo_id() -> str:
    return uuid.uuid4().hex[:12]


def marca_de_tiempo() -> float:
    return time.time()
