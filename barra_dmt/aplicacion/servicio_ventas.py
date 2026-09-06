from __future__ import annotations

from typing import Optional

from ..dominio.entidades import ItemVenta, Venta
from ..dominio.excepciones import (
    CajaCerradaError,
    CarritoVacioError,
    EfectivoInsuficienteError,
    ProductoNoEncontradoError,
    VentaNoEncontradaError,
)
from ..dominio.repositorios import RepositorioCaja, RepositorioProductos, RepositorioVentas
from ..infraestructura.conexion import marca_de_tiempo, nuevo_id


class LineaCarrito:
    def __init__(self, producto_id: str, nombre: str, precio_unitario: int, cantidad: int):
        self.producto_id = producto_id
        self.nombre = nombre
        self.precio_unitario = precio_unitario
        self.cantidad = cantidad

    @property
    def subtotal(self) -> int:
        return self.precio_unitario * self.cantidad


class ServicioVentas:
    def __init__(self, repo_ventas: RepositorioVentas, repo_caja: RepositorioCaja, repo_productos: RepositorioProductos):
        self._repo_ventas = repo_ventas
        self._repo_caja = repo_caja
        self._repo_productos = repo_productos

    def registrar_venta(self, lineas: list[LineaCarrito], metodo_pago: str, efectivo_recibido: int) -> Venta:
        sesion = self._repo_caja.sesion_abierta()
        if not sesion:
            raise CajaCerradaError()
        if not lineas:
            raise CarritoVacioError()

        total = sum(l.subtotal for l in lineas)
        if metodo_pago == "Efectivo" and efectivo_recibido < total:
            raise EfectivoInsuficienteError(total - efectivo_recibido)

        recibido = efectivo_recibido if metodo_pago == "Efectivo" else total
        cambio = (recibido - total) if metodo_pago == "Efectivo" else 0

        venta = Venta(
            id=nuevo_id(), sesion_id=sesion.id, timestamp=marca_de_tiempo(),
            items=[ItemVenta(l.producto_id, l.nombre, l.precio_unitario, l.cantidad) for l in lineas],
            total=total, metodo_pago=metodo_pago, efectivo_recibido=recibido, cambio=cambio,
        )
        ajustes_stock: dict[str, int] = {}
        for linea in lineas:
            ajustes_stock[linea.producto_id] = ajustes_stock.get(linea.producto_id, 0) - linea.cantidad
        self._repo_ventas.agregar_con_ajuste_stock(venta, ajustes_stock)
        return venta

    def advertencias_stock(self, lineas: list[LineaCarrito]) -> list[str]:
        advertencias = []
        for linea in lineas:
            producto = self._repo_productos.obtener(linea.producto_id)
            if producto and linea.cantidad > producto.stock:
                advertencias.append(
                    f"{producto.nombre}: quedan {producto.stock}, pediste {linea.cantidad}")
        return advertencias

    def _restaurar_stock(self, venta: Venta) -> None:
        for item in venta.items:
            producto = self._repo_productos.obtener(item.producto_id)
            if not producto:
                continue
            producto.stock += item.cantidad
            self._repo_productos.guardar(producto)

    def listar(self, solo_hoy: bool = False) -> list[Venta]:
        ventas = self._repo_ventas.listar()
        if solo_hoy:
            import datetime
            hoy = datetime.date.today()
            ventas = [v for v in ventas if datetime.datetime.fromtimestamp(v.timestamp).date() == hoy]
        return ventas

    def anular(self, venta_id: str) -> Venta:
        venta = self._repo_ventas.obtener(venta_id)
        if not venta:
            raise VentaNoEncontradaError()
        self._repo_ventas.marcar_anulada(venta_id)
        venta.anulada = True
        self._restaurar_stock(venta)
        return venta

    def eliminar(self, venta_id: str) -> None:
        venta = self._repo_ventas.obtener(venta_id)
        if not venta:
            raise VentaNoEncontradaError()
        if not venta.anulada:
            self._restaurar_stock(venta)
        self._repo_ventas.eliminar(venta_id)

    def producto_o_error(self, producto_id: str):
        producto = self._repo_productos.obtener(producto_id)
        if not producto:
            raise ProductoNoEncontradoError()
        return producto
