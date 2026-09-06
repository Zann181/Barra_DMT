"""Pronosticos de negocio: stock recomendado para el proximo evento, margen por
producto y proyeccion de demanda/ventas por periodo.

No agrega dependencias externas (numpy/pandas) -- la app se empaqueta con
PyInstaller y solo declara pyinstaller y Pillow en requirements.txt. Todo el
calculo (promedios, regresion lineal simple) se hace en Python puro.

Un "evento" se modela como un turno de caja cerrado (CierreCaja): agrupa las
ventas de una sesion, que es la unidad natural de consumo en una barra que
opera por eventos en vez de horario continuo.
"""
from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Literal, Optional

from ..dominio.entidades import CierreCaja, Producto, Venta
from ..dominio.repositorios import RepositorioCaja, RepositorioProductos, RepositorioVentas

Granularidad = Literal["dia", "semana", "mes"]

# Tope de periodos permitidos por granularidad (~5 anios), para que un horizonte
# mal ingresado no dispare un calculo interminable.
_TOPE_PERIODOS = {"dia": 1825, "semana": 260, "mes": 60}

_COLCHON_SEGURIDAD_DEFECTO = 0.15  # 15% extra sobre el promedio historico de consumo


@dataclass
class RecomendacionProducto:
    producto_id: str
    nombre: str
    unidades_por_paca: int
    stock_actual: int
    recomendado_unidades: int
    recomendado_pacas: int
    fuente: str  # "historial" | "sin_historial"
    eventos_considerados: int


@dataclass
class PuntoSerie:
    etiqueta: str
    total: float


@dataclass
class Proyeccion:
    granularidad: Granularidad
    horizonte: int
    historico: list[PuntoSerie]
    proyectado: list[PuntoSerie]
    datos_insuficientes: bool
    periodos_disponibles: int


class ServicioPronostico:
    def __init__(self, repo_ventas: RepositorioVentas, repo_productos: RepositorioProductos,
                 repo_caja: RepositorioCaja):
        self._repo_ventas = repo_ventas
        self._repo_productos = repo_productos
        self._repo_caja = repo_caja

    # ------------------------------------------------------------ margen
    def margen_por_producto(self) -> list[dict]:
        filas = []
        for p in self._repo_productos.listar():
            margen_abs = p.precio - p.costo
            margen_pct = (margen_abs / p.precio * 100) if p.precio else 0.0
            filas.append({
                "producto_id": p.id,
                "nombre": p.nombre,
                "categoria": p.categoria,
                "precio": p.precio,
                "costo": p.costo,
                "margen_abs": margen_abs,
                "margen_pct": margen_pct,
                "costo_sin_definir": p.costo == 0,
            })
        return sorted(filas, key=lambda f: f["margen_pct"])

    # ------------------------------------------------------------ eventos historicos
    def _eventos_cerrados(self) -> list[CierreCaja]:
        return sorted(self._repo_caja.listar_cierres(), key=lambda c: c.cerrada_en)

    def consumo_por_evento(self) -> list[dict]:
        """Unidades vendidas por producto en cada turno cerrado (proxy de evento)."""
        eventos = self._eventos_cerrados()
        todas_ventas = [v for v in self._repo_ventas.listar() if not v.anulada]
        ventas_por_sesion: dict[str, list[Venta]] = {}
        for v in todas_ventas:
            ventas_por_sesion.setdefault(v.sesion_id, []).append(v)

        resultado = []
        for cierre in eventos:
            consumo: dict[str, int] = {}
            for venta in ventas_por_sesion.get(cierre.sesion_id, []):
                for item in venta.items:
                    consumo[item.producto_id] = consumo.get(item.producto_id, 0) + item.cantidad
            resultado.append({
                "sesion_id": cierre.sesion_id,
                "cerrada_en": cierre.cerrada_en,
                "consumo_por_producto": consumo,
            })
        return resultado

    # ------------------------------------------------------------ stock proximo evento
    def pronostico_proximo_evento(self, n_eventos_referencia: Optional[int] = None,
                                   colchon_seguridad: float = _COLCHON_SEGURIDAD_DEFECTO) -> list[RecomendacionProducto]:
        """Stock recomendado para el proximo evento por producto.

        Con historial (>=1 turno cerrado con ventas): promedio de consumo de los
        ultimos N eventos + colchon de seguridad.
        Sin historial: cae al ultimo valor de reposicion por paca cargado en el
        producto (unidades_por_paca * ultima_cantidad_pacas), que es la mejor
        estimacion disponible hasta que se registre el primer evento real.
        """
        eventos = self.consumo_por_evento()
        if n_eventos_referencia:
            eventos = eventos[-n_eventos_referencia:]
        eventos_con_datos = [e for e in eventos if e["consumo_por_producto"]]

        recomendaciones = []
        for producto in self._repo_productos.listar():
            consumos = [e["consumo_por_producto"].get(producto.id, 0) for e in eventos_con_datos]
            if consumos:
                promedio = sum(consumos) / len(consumos)
                recomendado_unidades = round(promedio * (1 + colchon_seguridad))
                fuente = "historial"
            else:
                # Sin eventos con ventas registradas: la unica senal confiable es
                # el stock real que ya se cargo para el proximo evento.
                recomendado_unidades = producto.stock
                fuente = "sin_historial"

            upp = max(1, producto.unidades_por_paca)
            recomendado_pacas = -(-recomendado_unidades // upp)  # redondeo hacia arriba
            recomendaciones.append(RecomendacionProducto(
                producto_id=producto.id,
                nombre=producto.nombre,
                unidades_por_paca=upp,
                stock_actual=producto.stock,
                recomendado_unidades=recomendado_unidades,
                recomendado_pacas=recomendado_pacas,
                fuente=fuente,
                eventos_considerados=len(consumos) if consumos else 0,
            ))
        return sorted(recomendaciones, key=lambda r: r.nombre)

    # ------------------------------------------------------------ proyeccion ventas / demanda
    def _etiqueta_periodo(self, fecha: datetime.date, granularidad: Granularidad) -> str:
        if granularidad == "dia":
            return fecha.isoformat()
        if granularidad == "semana":
            anio, semana, _ = fecha.isocalendar()
            return f"{anio}-W{semana:02d}"
        return f"{fecha.year}-{fecha.month:02d}"

    def _serie_historica(self, granularidad: Granularidad, valores_por_fecha: list[tuple[datetime.date, float]]) -> list[PuntoSerie]:
        agregados: dict[str, float] = {}
        for fecha, valor in valores_por_fecha:
            etiqueta = self._etiqueta_periodo(fecha, granularidad)
            agregados[etiqueta] = agregados.get(etiqueta, 0) + valor
        return [PuntoSerie(etiqueta=k, total=v) for k, v in sorted(agregados.items())]

    def _proyectar(self, historico: list[PuntoSerie], horizonte: int) -> list[PuntoSerie]:
        """Regresion lineal simple (minimos cuadrados) sobre el indice de periodo."""
        n = len(historico)
        if n < 2:
            promedio = historico[0].total if n == 1 else 0.0
            return [PuntoSerie(etiqueta=f"+{i + 1}", total=max(0.0, promedio)) for i in range(horizonte)]

        xs = list(range(n))
        ys = [p.total for p in historico]
        media_x = sum(xs) / n
        media_y = sum(ys) / n
        numerador = sum((x - media_x) * (y - media_y) for x, y in zip(xs, ys))
        denominador = sum((x - media_x) ** 2 for x in xs)
        pendiente = numerador / denominador if denominador else 0.0
        intercepto = media_y - pendiente * media_x

        return [
            PuntoSerie(etiqueta=f"+{i + 1}", total=max(0.0, intercepto + pendiente * (n + i)))
            for i in range(horizonte)
        ]

    def proyeccion_ventas(self, granularidad: Granularidad = "dia", horizonte: int = 30) -> Proyeccion:
        horizonte = max(1, min(horizonte, _TOPE_PERIODOS.get(granularidad, 60)))
        ventas = [v for v in self._repo_ventas.listar() if not v.anulada]
        valores = [(datetime.datetime.fromtimestamp(v.timestamp).date(), float(v.total)) for v in ventas]
        historico = self._serie_historica(granularidad, valores)
        proyectado = self._proyectar(historico, horizonte)
        return Proyeccion(
            granularidad=granularidad, horizonte=horizonte, historico=historico, proyectado=proyectado,
            datos_insuficientes=len(historico) < 2, periodos_disponibles=len(historico),
        )

    def demanda_por_producto(self, producto_id: str, granularidad: Granularidad = "dia",
                              horizonte: int = 30) -> Proyeccion:
        horizonte = max(1, min(horizonte, _TOPE_PERIODOS.get(granularidad, 60)))
        ventas = [v for v in self._repo_ventas.listar() if not v.anulada]
        valores = []
        for v in ventas:
            fecha = datetime.datetime.fromtimestamp(v.timestamp).date()
            cantidad = sum(it.cantidad for it in v.items if it.producto_id == producto_id)
            if cantidad:
                valores.append((fecha, float(cantidad)))
        historico = self._serie_historica(granularidad, valores)
        proyectado = self._proyectar(historico, horizonte)
        return Proyeccion(
            granularidad=granularidad, horizonte=horizonte, historico=historico, proyectado=proyectado,
            datos_insuficientes=len(historico) < 2, periodos_disponibles=len(historico),
        )
