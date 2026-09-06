from __future__ import annotations

from typing import Optional

from ..dominio.entidades import Producto
from ..dominio.repositorios import RepositorioProductos
from .conexion import obtener_conexion


class RepositorioProductosSQLite(RepositorioProductos):
    def listar(self) -> list[Producto]:
        conexion = obtener_conexion()
        try:
            filas = conexion.execute(
                "SELECT * FROM productos ORDER BY orden, categoria, nombre"
            ).fetchall()
            return [_fila_a_producto(f) for f in filas]
        finally:
            conexion.close()

    def obtener(self, producto_id: str) -> Optional[Producto]:
        conexion = obtener_conexion()
        try:
            fila = conexion.execute(
                "SELECT * FROM productos WHERE id = ?", (producto_id,)
            ).fetchone()
            return _fila_a_producto(fila) if fila else None
        finally:
            conexion.close()

    def guardar(self, producto: Producto) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                """
                INSERT INTO productos
                    (id, nombre, categoria, precio, activo, stock, stock_minimo, costo, imagen_archivo, orden,
                     unidades_por_paca, ultima_cantidad_pacas)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    nombre = excluded.nombre,
                    categoria = excluded.categoria,
                    precio = excluded.precio,
                    activo = excluded.activo,
                    stock = excluded.stock,
                    stock_minimo = excluded.stock_minimo,
                    costo = excluded.costo,
                    imagen_archivo = excluded.imagen_archivo,
                    orden = excluded.orden,
                    unidades_por_paca = excluded.unidades_por_paca,
                    ultima_cantidad_pacas = excluded.ultima_cantidad_pacas
                """,
                (
                    producto.id, producto.nombre, producto.categoria, producto.precio, int(producto.activo),
                    producto.stock, producto.stock_minimo, producto.costo, producto.imagen_archivo,
                    producto.orden, producto.unidades_por_paca, producto.ultima_cantidad_pacas,
                ),
            )
            conexion.commit()
        finally:
            conexion.close()

    def eliminar(self, producto_id: str) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute("DELETE FROM productos WHERE id = ?", (producto_id,))
            conexion.commit()
        finally:
            conexion.close()


def _fila_a_producto(fila) -> Producto:
    return Producto(
        id=fila["id"],
        nombre=fila["nombre"],
        categoria=fila["categoria"],
        precio=fila["precio"],
        activo=bool(fila["activo"]),
        stock=fila["stock"],
        stock_minimo=fila["stock_minimo"],
        costo=fila["costo"],
        imagen_archivo=fila["imagen_archivo"],
        orden=fila["orden"],
        unidades_por_paca=fila["unidades_por_paca"],
        ultima_cantidad_pacas=fila["ultima_cantidad_pacas"],
    )
