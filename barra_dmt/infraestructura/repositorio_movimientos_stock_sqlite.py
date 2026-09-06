from __future__ import annotations

import datetime
from typing import Optional

from ..dominio.entidades import MovimientoStock
from ..dominio.repositorios import RepositorioMovimientosStock
from .conexion import obtener_conexion


class RepositorioMovimientosStockSQLite(RepositorioMovimientosStock):
    def agregar(self, movimiento: MovimientoStock) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                """
                INSERT INTO movimientos_stock (id, producto_id, nombre_producto, cantidad, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (movimiento.id, movimiento.producto_id, movimiento.nombre_producto,
                 movimiento.cantidad, movimiento.timestamp),
            )
            conexion.commit()
        finally:
            conexion.close()

    def listar(self, desde: Optional[datetime.date] = None,
               hasta: Optional[datetime.date] = None) -> list[MovimientoStock]:
        conexion = obtener_conexion()
        try:
            filas = conexion.execute(
                "SELECT * FROM movimientos_stock ORDER BY timestamp DESC"
            ).fetchall()
            movimientos = [_fila_a_movimiento(f) for f in filas]
            if desde:
                movimientos = [m for m in movimientos
                               if datetime.datetime.fromtimestamp(m.timestamp).date() >= desde]
            if hasta:
                movimientos = [m for m in movimientos
                               if datetime.datetime.fromtimestamp(m.timestamp).date() <= hasta]
            return movimientos
        finally:
            conexion.close()

    def eliminar_todo(self) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute("DELETE FROM movimientos_stock")
            conexion.commit()
        finally:
            conexion.close()


def _fila_a_movimiento(fila) -> MovimientoStock:
    return MovimientoStock(
        id=fila["id"],
        producto_id=fila["producto_id"],
        nombre_producto=fila["nombre_producto"],
        cantidad=fila["cantidad"],
        timestamp=fila["timestamp"],
    )
