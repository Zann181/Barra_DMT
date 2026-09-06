from __future__ import annotations

from ..dominio.entidades import GastoCaja
from ..dominio.repositorios import RepositorioGastosCaja
from .conexion import obtener_conexion


class RepositorioGastosCajaSQLite(RepositorioGastosCaja):
    def agregar(self, gasto: GastoCaja) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                "INSERT INTO gastos_caja (id, sesion_id, timestamp, concepto, monto) VALUES (?, ?, ?, ?, ?)",
                (gasto.id, gasto.sesion_id, gasto.timestamp, gasto.concepto, gasto.monto),
            )
            conexion.commit()
        finally:
            conexion.close()

    def listar(self) -> list[GastoCaja]:
        conexion = obtener_conexion()
        try:
            filas = conexion.execute("SELECT * FROM gastos_caja ORDER BY timestamp DESC").fetchall()
            return [_fila_a_gasto(f) for f in filas]
        finally:
            conexion.close()

    def listar_por_sesion(self, sesion_id: str) -> list[GastoCaja]:
        conexion = obtener_conexion()
        try:
            filas = conexion.execute(
                "SELECT * FROM gastos_caja WHERE sesion_id = ? ORDER BY timestamp", (sesion_id,)
            ).fetchall()
            return [_fila_a_gasto(f) for f in filas]
        finally:
            conexion.close()

    def eliminar(self, gasto_id: str) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute("DELETE FROM gastos_caja WHERE id = ?", (gasto_id,))
            conexion.commit()
        finally:
            conexion.close()

    def eliminar_por_sesion(self, sesion_id: str) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute("DELETE FROM gastos_caja WHERE sesion_id = ?", (sesion_id,))
            conexion.commit()
        finally:
            conexion.close()

    def conceptos_usados(self) -> list[str]:
        conexion = obtener_conexion()
        try:
            filas = conexion.execute(
                "SELECT concepto, MAX(timestamp) AS ultimo FROM gastos_caja "
                "GROUP BY concepto ORDER BY ultimo DESC"
            ).fetchall()
            return [f["concepto"] for f in filas]
        finally:
            conexion.close()


def _fila_a_gasto(fila) -> GastoCaja:
    return GastoCaja(
        id=fila["id"], sesion_id=fila["sesion_id"], timestamp=fila["timestamp"],
        concepto=fila["concepto"], monto=fila["monto"],
    )
