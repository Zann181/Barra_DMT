from __future__ import annotations

from typing import Optional

from ..dominio.entidades import CierreCaja, SesionCaja
from ..dominio.repositorios import RepositorioCaja
from .conexion import obtener_conexion


class RepositorioCajaSQLite(RepositorioCaja):
    def sesion_abierta(self) -> Optional[SesionCaja]:
        conexion = obtener_conexion()
        try:
            fila = conexion.execute(
                "SELECT * FROM sesiones_caja WHERE cerrada_en IS NULL ORDER BY abierta_en DESC LIMIT 1"
            ).fetchone()
            return _fila_a_sesion(fila) if fila else None
        finally:
            conexion.close()

    def abrir_sesion(self, sesion: SesionCaja) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                """
                INSERT INTO sesiones_caja (id, cajero, abierta_en, efectivo_inicial, cerrada_en)
                VALUES (?, ?, ?, ?, NULL)
                """,
                (sesion.id, sesion.cajero, sesion.abierta_en, sesion.efectivo_inicial),
            )
            conexion.commit()
        finally:
            conexion.close()

    def cerrar_sesion(self, sesion_id: str, cerrada_en: float) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                "UPDATE sesiones_caja SET cerrada_en = ? WHERE id = ?", (cerrada_en, sesion_id)
            )
            conexion.commit()
        finally:
            conexion.close()

    def guardar_cierre(self, cierre: CierreCaja) -> None:
        conexion = obtener_conexion()
        try:
            # total_tarjeta ya no se usa (solo quedan Efectivo/QR): se guarda en 0.
            # total_qr reutiliza la columna total_transferencia para no tener que
            # migrar cierres viejos.
            conexion.execute(
                """
                INSERT INTO cierres_caja (
                    sesion_id, cajero, abierta_en, cerrada_en, efectivo_inicial,
                    total_ventas, total_efectivo, total_tarjeta, total_transferencia,
                    efectivo_esperado, efectivo_contado, diferencia, total_gastos_dmt, total_gastos_caja
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cierre.sesion_id, cierre.cajero, cierre.abierta_en, cierre.cerrada_en,
                    cierre.efectivo_inicial, cierre.total_ventas, cierre.total_efectivo,
                    0, cierre.total_qr, cierre.efectivo_esperado,
                    cierre.efectivo_contado, cierre.diferencia, cierre.total_gastos_dmt,
                    cierre.total_gastos_caja,
                ),
            )
            conexion.commit()
        finally:
            conexion.close()

    def listar_cierres(self) -> list[CierreCaja]:
        conexion = obtener_conexion()
        try:
            filas = conexion.execute(
                "SELECT * FROM cierres_caja ORDER BY cerrada_en DESC"
            ).fetchall()
            return [_fila_a_cierre(f) for f in filas]
        finally:
            conexion.close()

    def listar_sesiones(self) -> list[SesionCaja]:
        conexion = obtener_conexion()
        try:
            filas = conexion.execute("SELECT * FROM sesiones_caja ORDER BY abierta_en DESC").fetchall()
            return [_fila_a_sesion(f) for f in filas]
        finally:
            conexion.close()

    def obtener_sesion(self, sesion_id: str) -> Optional[SesionCaja]:
        conexion = obtener_conexion()
        try:
            fila = conexion.execute("SELECT * FROM sesiones_caja WHERE id = ?", (sesion_id,)).fetchone()
            return _fila_a_sesion(fila) if fila else None
        finally:
            conexion.close()

    def actualizar_sesion(self, sesion: SesionCaja) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                "UPDATE sesiones_caja SET cajero = ?, abierta_en = ?, efectivo_inicial = ?, cerrada_en = ? "
                "WHERE id = ?",
                (sesion.cajero, sesion.abierta_en, sesion.efectivo_inicial, sesion.cerrada_en, sesion.id),
            )
            conexion.commit()
        finally:
            conexion.close()

    def eliminar_sesion(self, sesion_id: str) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute("DELETE FROM sesiones_caja WHERE id = ?", (sesion_id,))
            conexion.commit()
        finally:
            conexion.close()

    def obtener_cierre(self, sesion_id: str) -> Optional[CierreCaja]:
        conexion = obtener_conexion()
        try:
            fila = conexion.execute(
                "SELECT * FROM cierres_caja WHERE sesion_id = ?", (sesion_id,)
            ).fetchone()
            return _fila_a_cierre(fila) if fila else None
        finally:
            conexion.close()

    def actualizar_cierre(self, cierre: CierreCaja) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute(
                """
                UPDATE cierres_caja SET cajero = ?, abierta_en = ?, cerrada_en = ?, efectivo_inicial = ?,
                    total_ventas = ?, total_efectivo = ?, total_transferencia = ?,
                    efectivo_esperado = ?, efectivo_contado = ?, diferencia = ?, total_gastos_dmt = ?,
                    total_gastos_caja = ?
                WHERE sesion_id = ?
                """,
                (
                    cierre.cajero, cierre.abierta_en, cierre.cerrada_en, cierre.efectivo_inicial,
                    cierre.total_ventas, cierre.total_efectivo,
                    cierre.total_qr, cierre.efectivo_esperado, cierre.efectivo_contado,
                    cierre.diferencia, cierre.total_gastos_dmt, cierre.total_gastos_caja, cierre.sesion_id,
                ),
            )
            conexion.commit()
        finally:
            conexion.close()

    def eliminar_cierre(self, sesion_id: str) -> None:
        conexion = obtener_conexion()
        try:
            conexion.execute("DELETE FROM cierres_caja WHERE sesion_id = ?", (sesion_id,))
            conexion.commit()
        finally:
            conexion.close()


def _fila_a_sesion(fila) -> SesionCaja:
    return SesionCaja(
        id=fila["id"],
        cajero=fila["cajero"],
        abierta_en=fila["abierta_en"],
        efectivo_inicial=fila["efectivo_inicial"],
        cerrada_en=fila["cerrada_en"],
    )


def _fila_a_cierre(fila) -> CierreCaja:
    return CierreCaja(
        sesion_id=fila["sesion_id"],
        cajero=fila["cajero"],
        abierta_en=fila["abierta_en"],
        cerrada_en=fila["cerrada_en"],
        efectivo_inicial=fila["efectivo_inicial"],
        total_ventas=fila["total_ventas"],
        total_efectivo=fila["total_efectivo"],
        total_qr=fila["total_transferencia"],
        total_gastos_dmt=fila["total_gastos_dmt"],
        total_gastos_caja=fila["total_gastos_caja"],
        efectivo_esperado=fila["efectivo_esperado"],
        efectivo_contado=fila["efectivo_contado"],
        diferencia=fila["diferencia"],
    )
