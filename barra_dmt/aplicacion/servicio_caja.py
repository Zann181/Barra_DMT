from __future__ import annotations

from typing import Optional

from ..dominio.entidades import CierreCaja, GastoCaja, SesionCaja
from ..dominio.excepciones import CajaCerradaError, CajaYaAbiertaError, CierreNoEncontradoError
from ..dominio.repositorios import RepositorioCaja, RepositorioGastos, RepositorioGastosCaja, RepositorioVentas
from ..infraestructura.conexion import marca_de_tiempo, nuevo_id


class TotalesSesion:
    def __init__(self, total_ventas: int, total_efectivo: int, total_qr: int,
                 total_gastos_dmt: int, total_gastos_caja: int, cantidad_ventas: int,
                 efectivo_esperado: int):
        self.total_ventas = total_ventas
        self.total_efectivo = total_efectivo
        self.total_qr = total_qr
        self.total_gastos_dmt = total_gastos_dmt
        self.total_gastos_caja = total_gastos_caja
        self.cantidad_ventas = cantidad_ventas
        self.efectivo_esperado = efectivo_esperado


class ServicioCaja:
    def __init__(self, repo_caja: RepositorioCaja, repo_ventas: RepositorioVentas,
                 repo_gastos: RepositorioGastos, repo_gastos_caja: RepositorioGastosCaja):
        self._repo_caja = repo_caja
        self._repo_ventas = repo_ventas
        self._repo_gastos = repo_gastos
        self._repo_gastos_caja = repo_gastos_caja

    def sesion_actual(self) -> Optional[SesionCaja]:
        return self._repo_caja.sesion_abierta()

    def abrir_caja(self, cajero: str, efectivo_inicial: int) -> SesionCaja:
        if self._repo_caja.sesion_abierta():
            raise CajaYaAbiertaError()
        sesion = SesionCaja(
            id=nuevo_id(), cajero=cajero.strip() or "Cajero",
            abierta_en=marca_de_tiempo(), efectivo_inicial=int(efectivo_inicial),
        )
        self._repo_caja.abrir_sesion(sesion)
        return sesion

    def calcular_totales(self, sesion: SesionCaja) -> TotalesSesion:
        ventas = [v for v in self._repo_ventas.listar_por_sesion(sesion.id) if not v.anulada]
        total_efectivo = sum(v.total for v in ventas if v.metodo_pago == "Efectivo")
        total_qr = sum(v.total for v in ventas if v.metodo_pago == "QR")
        total_gastos_dmt = sum(g.total for g in self._repo_gastos.listar_por_sesion(sesion.id))
        total_gastos_caja = sum(g.monto for g in self._repo_gastos_caja.listar_por_sesion(sesion.id))
        return TotalesSesion(
            total_ventas=total_efectivo + total_qr,
            total_efectivo=total_efectivo,
            total_qr=total_qr,
            total_gastos_dmt=total_gastos_dmt,
            total_gastos_caja=total_gastos_caja,
            cantidad_ventas=len(ventas),
            # Los gastos de caja salen del efectivo fisico -- se restan de lo esperado.
            efectivo_esperado=sesion.efectivo_inicial + total_efectivo - total_gastos_caja,
        )

    def cerrar_caja(self, efectivo_contado: int) -> CierreCaja:
        sesion = self._repo_caja.sesion_abierta()
        if not sesion:
            raise CajaCerradaError()
        totales = self.calcular_totales(sesion)
        cerrada_en = marca_de_tiempo()
        cierre = CierreCaja(
            sesion_id=sesion.id, cajero=sesion.cajero, abierta_en=sesion.abierta_en,
            cerrada_en=cerrada_en, efectivo_inicial=sesion.efectivo_inicial,
            total_ventas=totales.total_ventas, total_efectivo=totales.total_efectivo,
            total_qr=totales.total_qr, total_gastos_dmt=totales.total_gastos_dmt,
            total_gastos_caja=totales.total_gastos_caja,
            efectivo_esperado=totales.efectivo_esperado, efectivo_contado=int(efectivo_contado),
            diferencia=int(efectivo_contado) - totales.efectivo_esperado,
        )
        self._repo_caja.guardar_cierre(cierre)
        self._repo_caja.cerrar_sesion(sesion.id, cerrada_en)
        return cierre

    def listar_cierres(self) -> list[CierreCaja]:
        return self._repo_caja.listar_cierres()

    def editar_sesion_actual(self, cajero: str, efectivo_inicial: int) -> SesionCaja:
        sesion = self._repo_caja.sesion_abierta()
        if not sesion:
            raise CajaCerradaError()
        sesion.cajero = cajero.strip() or "Cajero"
        sesion.efectivo_inicial = int(efectivo_inicial)
        self._repo_caja.actualizar_sesion(sesion)
        return sesion

    def cancelar_sesion_actual(self) -> None:
        sesion = self._repo_caja.sesion_abierta()
        if not sesion:
            raise CajaCerradaError()
        self._repo_ventas.eliminar_por_sesion(sesion.id)
        self._repo_gastos.eliminar_por_sesion(sesion.id)
        self._repo_gastos_caja.eliminar_por_sesion(sesion.id)
        self._repo_caja.eliminar_sesion(sesion.id)

    def registrar_gasto_caja(self, concepto: str, monto: int) -> GastoCaja:
        sesion = self._repo_caja.sesion_abierta()
        if not sesion:
            raise CajaCerradaError()
        gasto = GastoCaja(
            id=nuevo_id(), sesion_id=sesion.id, timestamp=marca_de_tiempo(),
            concepto=concepto.strip() or "Gasto", monto=int(monto),
        )
        self._repo_gastos_caja.agregar(gasto)
        return gasto

    def listar_gastos_caja_sesion(self, sesion_id: str) -> list[GastoCaja]:
        return self._repo_gastos_caja.listar_por_sesion(sesion_id)

    def conceptos_gastos_caja(self) -> list[str]:
        """Conceptos ya usados antes, para que el formulario los recuerde."""
        return self._repo_gastos_caja.conceptos_usados()

    def eliminar_gasto_caja(self, gasto_id: str) -> None:
        self._repo_gastos_caja.eliminar(gasto_id)

    def editar_cierre(self, sesion_id: str, cajero: str, efectivo_contado: int) -> CierreCaja:
        cierre = self._repo_caja.obtener_cierre(sesion_id)
        if not cierre:
            raise CierreNoEncontradoError()
        cierre.cajero = cajero.strip() or cierre.cajero
        cierre.efectivo_contado = int(efectivo_contado)
        cierre.diferencia = cierre.efectivo_contado - cierre.efectivo_esperado
        self._repo_caja.actualizar_cierre(cierre)
        sesion = self._repo_caja.obtener_sesion(sesion_id)
        if sesion:
            sesion.cajero = cierre.cajero
            self._repo_caja.actualizar_sesion(sesion)
        return cierre

    def eliminar_cierre(self, sesion_id: str) -> None:
        cierre = self._repo_caja.obtener_cierre(sesion_id)
        if not cierre:
            raise CierreNoEncontradoError()
        self._repo_ventas.eliminar_por_sesion(sesion_id)
        self._repo_gastos.eliminar_por_sesion(sesion_id)
        self._repo_gastos_caja.eliminar_por_sesion(sesion_id)
        self._repo_caja.eliminar_cierre(sesion_id)
        self._repo_caja.eliminar_sesion(sesion_id)
