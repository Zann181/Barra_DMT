"""Analisis POS: agregaciones de ventas para el tablero de la pestaña Analisis.

No agrega SQL nuevo -- reutiliza los mismos repositorios que ya usan
ServicioVentas/ServicioProductos y agrega en Python, igual que hace
ServicioVentas.listar(solo_hoy=...).
"""
from __future__ import annotations

import datetime
import statistics
from typing import Optional

from ..dominio.entidades import Gasto, METODOS_PAGO, MovimientoStock, Producto, SesionCaja, Venta
from ..dominio.repositorios import (
    RepositorioCaja, RepositorioGastos, RepositorioMovimientosStock, RepositorioProductos,
    RepositorioVentas,
)


class ServicioAnalisis:
    def __init__(self, repo_ventas: RepositorioVentas, repo_productos: RepositorioProductos,
                 repo_movimientos: RepositorioMovimientosStock, repo_caja: RepositorioCaja,
                 repo_gastos: RepositorioGastos):
        self._repo_ventas = repo_ventas
        self._repo_productos = repo_productos
        self._repo_movimientos = repo_movimientos
        self._repo_caja = repo_caja
        self._repo_gastos = repo_gastos

    def _ventas_filtradas(self, desde: Optional[datetime.date], hasta: Optional[datetime.date],
                           sesion_id: Optional[str] = None) -> list[Venta]:
        ventas = [v for v in self._repo_ventas.listar() if not v.anulada]
        if sesion_id:
            ventas = [v for v in ventas if v.sesion_id == sesion_id]
        if desde:
            ventas = [v for v in ventas if datetime.datetime.fromtimestamp(v.timestamp).date() >= desde]
        if hasta:
            ventas = [v for v in ventas if datetime.datetime.fromtimestamp(v.timestamp).date() <= hasta]
        return ventas

    def _gastos_filtrados(self, desde: Optional[datetime.date], hasta: Optional[datetime.date],
                          sesion_id: Optional[str] = None) -> list[Gasto]:
        gastos = self._repo_gastos.listar()
        if sesion_id:
            gastos = [g for g in gastos if g.sesion_id == sesion_id]
        if desde:
            gastos = [g for g in gastos if datetime.datetime.fromtimestamp(g.timestamp).date() >= desde]
        if hasta:
            gastos = [g for g in gastos if datetime.datetime.fromtimestamp(g.timestamp).date() <= hasta]
        return gastos

    def total_gastado_dmt(self, desde: Optional[datetime.date] = None, hasta: Optional[datetime.date] = None,
                           sesion_id: Optional[str] = None) -> int:
        return sum(g.total for g in self._gastos_filtrados(desde, hasta, sesion_id))

    def gasto_dmt_por_producto(self, desde: Optional[datetime.date] = None,
                                hasta: Optional[datetime.date] = None,
                                sesion_id: Optional[str] = None) -> dict[str, dict]:
        """cantidad y valor (costo) entregado como DMT, agrupado por producto_id."""
        gastos = self._gastos_filtrados(desde, hasta, sesion_id)
        agregados: dict[str, dict] = {}
        for gasto in gastos:
            for item in gasto.items:
                fila = agregados.setdefault(item.producto_id, {"nombre": item.nombre, "cantidad": 0, "valor": 0})
                fila["cantidad"] += item.cantidad
                fila["valor"] += item.subtotal
        return agregados

    def turnos(self) -> list[SesionCaja]:
        """Sesiones de caja (abiertas y cerradas) para poblar el filtro de turno."""
        return sorted(self._repo_caja.listar_sesiones(), key=lambda s: s.abierta_en, reverse=True)

    def resumen(self, desde: Optional[datetime.date] = None, hasta: Optional[datetime.date] = None,
                sesion_id: Optional[str] = None) -> dict:
        ventas = self._ventas_filtradas(desde, hasta, sesion_id)
        costos = {p.id: p.costo for p in self._repo_productos.listar()}
        total_vendido = sum(v.total for v in ventas)
        n_ventas = len(ventas)
        unidades = sum(it.cantidad for v in ventas for it in v.items)
        utilidad = sum(
            (it.precio_unitario - costos.get(it.producto_id, 0)) * it.cantidad
            for v in ventas for it in v.items
        )
        return {
            "total_vendido": total_vendido,
            "n_ventas": n_ventas,
            "unidades": unidades,
            "ticket_promedio": (total_vendido / n_ventas) if n_ventas else 0,
            "utilidad": utilidad,
            "gasto_dmt": self.total_gastado_dmt(desde, hasta, sesion_id),
        }

    def estadisticas(self, desde: Optional[datetime.date] = None, hasta: Optional[datetime.date] = None,
                      sesion_id: Optional[str] = None) -> dict:
        """Media, mediana, desviacion estandar, minimo y maximo del ticket de venta."""
        ventas = self._ventas_filtradas(desde, hasta, sesion_id)
        totales = [v.total for v in ventas]
        n = len(totales)
        return {
            "n": n,
            "media": statistics.fmean(totales) if n else 0,
            "mediana": statistics.median(totales) if n else 0,
            "desviacion": statistics.stdev(totales) if n > 1 else 0,
            "minimo": min(totales) if n else 0,
            "maximo": max(totales) if n else 0,
        }

    def top_productos(self, desde: Optional[datetime.date] = None, hasta: Optional[datetime.date] = None,
                       n: int = 10, sesion_id: Optional[str] = None) -> list[dict]:
        ventas = self._ventas_filtradas(desde, hasta, sesion_id)
        agregados: dict[str, dict] = {}
        for venta in ventas:
            for item in venta.items:
                fila = agregados.setdefault(item.producto_id, {
                    "producto_id": item.producto_id, "nombre": item.nombre, "cantidad": 0, "ingresos": 0})
                fila["cantidad"] += item.cantidad
                fila["ingresos"] += item.subtotal
        return sorted(agregados.values(), key=lambda f: f["cantidad"], reverse=True)[:n]

    def ventas_por_categoria(self, desde: Optional[datetime.date] = None,
                              hasta: Optional[datetime.date] = None,
                              sesion_id: Optional[str] = None) -> list[dict]:
        ventas = self._ventas_filtradas(desde, hasta, sesion_id)
        categoria_por_producto = {p.id: p.categoria for p in self._repo_productos.listar()}
        agregados: dict[str, int] = {}
        for venta in ventas:
            for item in venta.items:
                categoria = categoria_por_producto.get(item.producto_id, "Otros")
                agregados[categoria] = agregados.get(categoria, 0) + item.subtotal
        filas = [{"categoria": categoria, "total": total} for categoria, total in agregados.items()]
        return sorted(filas, key=lambda f: f["total"], reverse=True)

    def ventas_por_metodo_pago(self, desde: Optional[datetime.date] = None,
                                hasta: Optional[datetime.date] = None,
                                sesion_id: Optional[str] = None) -> dict[str, int]:
        ventas = self._ventas_filtradas(desde, hasta, sesion_id)
        return {metodo: sum(v.total for v in ventas if v.metodo_pago == metodo) for metodo in METODOS_PAGO}

    def ventas_por_hora(self, desde: Optional[datetime.date] = None,
                         hasta: Optional[datetime.date] = None,
                         sesion_id: Optional[str] = None) -> list[int]:
        ventas = self._ventas_filtradas(desde, hasta, sesion_id)
        totales_por_hora = [0] * 24
        for venta in ventas:
            hora = datetime.datetime.fromtimestamp(venta.timestamp).hour
            totales_por_hora[hora] += venta.total
        return totales_por_hora

    def productos_stock_bajo(self) -> list[Producto]:
        return sorted(
            (p for p in self._repo_productos.listar() if p.activo and p.stock <= p.stock_minimo),
            key=lambda p: p.stock,
        )

    def reposiciones_stock(self, desde: Optional[datetime.date] = None,
                            hasta: Optional[datetime.date] = None) -> list[MovimientoStock]:
        return self._repo_movimientos.listar(desde, hasta)

    def total_repuesto_por_producto(self, desde: Optional[datetime.date] = None,
                                     hasta: Optional[datetime.date] = None) -> list[dict]:
        movimientos = self._repo_movimientos.listar(desde, hasta)
        agregados: dict[str, int] = {}
        for mov in movimientos:
            agregados[mov.nombre_producto] = agregados.get(mov.nombre_producto, 0) + mov.cantidad
        filas = [{"nombre": nombre, "cantidad": cantidad} for nombre, cantidad in agregados.items()]
        return sorted(filas, key=lambda f: f["cantidad"], reverse=True)
