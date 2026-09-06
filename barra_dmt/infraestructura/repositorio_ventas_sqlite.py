from __future__ import annotations

from typing import Optional

from ..dominio.entidades import ItemVenta, Venta
from ..dominio.repositorios import RepositorioVentas
from .conexion import obtener_conexion


class RepositorioVentasSQLite(RepositorioVentas):
    def agregar(self, venta: Venta) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                """
                INSERT INTO ventas (id, sesion_id, timestamp, total, metodo_pago, efectivo_recibido, cambio, anulada)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    venta.id, venta.sesion_id, venta.timestamp, venta.total,
                    venta.metodo_pago, venta.efectivo_recibido, venta.cambio, int(venta.anulada),
                ),
            )
            conexion.executemany(
                """
                INSERT INTO venta_items (venta_id, producto_id, nombre, precio_unitario, cantidad)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (venta.id, it.producto_id, it.nombre, it.precio_unitario, it.cantidad)
                    for it in venta.items
                ],
            )
            conexion.commit()
        finally:
            conexion.close()

    def agregar_con_ajuste_stock(self, venta: Venta, ajustes_stock: dict[str, int]) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                """
                INSERT INTO ventas (id, sesion_id, timestamp, total, metodo_pago, efectivo_recibido, cambio, anulada)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    venta.id, venta.sesion_id, venta.timestamp, venta.total,
                    venta.metodo_pago, venta.efectivo_recibido, venta.cambio, int(venta.anulada),
                ),
            )
            conexion.executemany(
                """
                INSERT INTO venta_items (venta_id, producto_id, nombre, precio_unitario, cantidad)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (venta.id, it.producto_id, it.nombre, it.precio_unitario, it.cantidad)
                    for it in venta.items
                ],
            )
            conexion.executemany(
                "UPDATE productos SET stock = stock + ? WHERE id = ?",
                [(delta, producto_id) for producto_id, delta in ajustes_stock.items()],
            )
            conexion.commit()
        finally:
            conexion.close()

    def listar(self) -> list[Venta]:
        conexion = obtener_conexion()
        try:
            filas = conexion.execute("SELECT * FROM ventas ORDER BY timestamp DESC").fetchall()
            return [_fila_a_venta(conexion, f) for f in filas]
        finally:
            conexion.close()

    def obtener(self, venta_id: str) -> Optional[Venta]:
        conexion = obtener_conexion()
        try:
            fila = conexion.execute("SELECT * FROM ventas WHERE id = ?", (venta_id,)).fetchone()
            return _fila_a_venta(conexion, fila) if fila else None
        finally:
            conexion.close()

    def marcar_anulada(self, venta_id: str) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute("UPDATE ventas SET anulada = 1 WHERE id = ?", (venta_id,))
            conexion.commit()
        finally:
            conexion.close()

    def eliminar(self, venta_id: str) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute("DELETE FROM venta_items WHERE venta_id = ?", (venta_id,))
            conexion.execute("DELETE FROM ventas WHERE id = ?", (venta_id,))
            conexion.commit()
        finally:
            conexion.close()

    def listar_por_sesion(self, sesion_id: str) -> list[Venta]:
        conexion = obtener_conexion()
        try:
            filas = conexion.execute(
                "SELECT * FROM ventas WHERE sesion_id = ? ORDER BY timestamp", (sesion_id,)
            ).fetchall()
            return [_fila_a_venta(conexion, f) for f in filas]
        finally:
            conexion.close()

    def eliminar_por_sesion(self, sesion_id: str) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                "DELETE FROM venta_items WHERE venta_id IN (SELECT id FROM ventas WHERE sesion_id = ?)",
                (sesion_id,),
            )
            conexion.execute("DELETE FROM ventas WHERE sesion_id = ?", (sesion_id,))
            conexion.commit()
        finally:
            conexion.close()


def _fila_a_venta(conexion, fila) -> Venta:
    items_filas = conexion.execute(
        "SELECT * FROM venta_items WHERE venta_id = ?", (fila["id"],)
    ).fetchall()
    items = [
        ItemVenta(
            producto_id=it["producto_id"],
            nombre=it["nombre"],
            precio_unitario=it["precio_unitario"],
            cantidad=it["cantidad"],
        )
        for it in items_filas
    ]
    return Venta(
        id=fila["id"],
        sesion_id=fila["sesion_id"],
        timestamp=fila["timestamp"],
        items=items,
        total=fila["total"],
        metodo_pago=fila["metodo_pago"],
        efectivo_recibido=fila["efectivo_recibido"],
        cambio=fila["cambio"],
        anulada=bool(fila["anulada"]),
    )
