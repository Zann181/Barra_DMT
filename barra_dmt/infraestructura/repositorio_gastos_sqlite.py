from __future__ import annotations

from ..dominio.entidades import Gasto, ItemGasto
from ..dominio.repositorios import RepositorioGastos
from .conexion import obtener_conexion


class RepositorioGastosSQLite(RepositorioGastos):
    def agregar(self, gasto: Gasto) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                "INSERT INTO gastos (id, sesion_id, timestamp, total) VALUES (?, ?, ?, ?)",
                (gasto.id, gasto.sesion_id, gasto.timestamp, gasto.total),
            )
            conexion.executemany(
                """
                INSERT INTO gasto_items (gasto_id, producto_id, nombre, costo_unitario, cantidad)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (gasto.id, it.producto_id, it.nombre, it.costo_unitario, it.cantidad)
                    for it in gasto.items
                ],
            )
            conexion.commit()
        finally:
            conexion.close()

    def agregar_con_ajuste_stock(self, gasto: Gasto, ajustes_stock: dict[str, int]) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                "INSERT INTO gastos (id, sesion_id, timestamp, total) VALUES (?, ?, ?, ?)",
                (gasto.id, gasto.sesion_id, gasto.timestamp, gasto.total),
            )
            conexion.executemany(
                """
                INSERT INTO gasto_items (gasto_id, producto_id, nombre, costo_unitario, cantidad)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (gasto.id, it.producto_id, it.nombre, it.costo_unitario, it.cantidad)
                    for it in gasto.items
                ],
            )
            conexion.executemany(
                "UPDATE productos SET stock = stock + ? WHERE id = ?",
                [(delta, producto_id) for producto_id, delta in ajustes_stock.items()],
            )
            conexion.commit()
        finally:
            conexion.close()

    def listar(self) -> list[Gasto]:
        conexion = obtener_conexion()
        try:
            filas = conexion.execute("SELECT * FROM gastos ORDER BY timestamp DESC").fetchall()
            return [_fila_a_gasto(conexion, f) for f in filas]
        finally:
            conexion.close()

    def listar_por_sesion(self, sesion_id: str) -> list[Gasto]:
        conexion = obtener_conexion()
        try:
            filas = conexion.execute(
                "SELECT * FROM gastos WHERE sesion_id = ? ORDER BY timestamp", (sesion_id,)
            ).fetchall()
            return [_fila_a_gasto(conexion, f) for f in filas]
        finally:
            conexion.close()

    def eliminar_por_sesion(self, sesion_id: str) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                "DELETE FROM gasto_items WHERE gasto_id IN (SELECT id FROM gastos WHERE sesion_id = ?)",
                (sesion_id,),
            )
            conexion.execute("DELETE FROM gastos WHERE sesion_id = ?", (sesion_id,))
            conexion.commit()
        finally:
            conexion.close()


def _fila_a_gasto(conexion, fila) -> Gasto:
    items_filas = conexion.execute(
        "SELECT * FROM gasto_items WHERE gasto_id = ?", (fila["id"],)
    ).fetchall()
    items = [
        ItemGasto(
            producto_id=it["producto_id"],
            nombre=it["nombre"],
            costo_unitario=it["costo_unitario"],
            cantidad=it["cantidad"],
        )
        for it in items_filas
    ]
    return Gasto(
        id=fila["id"],
        sesion_id=fila["sesion_id"],
        timestamp=fila["timestamp"],
        items=items,
        total=fila["total"],
    )
