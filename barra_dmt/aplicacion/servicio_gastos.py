from __future__ import annotations

from ..dominio.entidades import Gasto, ItemGasto
from ..dominio.excepciones import CajaCerradaError, CarritoVacioError
from ..dominio.repositorios import RepositorioCaja, RepositorioGastos, RepositorioProductos
from ..infraestructura.conexion import marca_de_tiempo, nuevo_id


class ServicioGastos:
    """Productos entregados a integrantes (DMT): no es ingreso, se registra
    como gasto al valor de costo y descuenta stock igual que una venta."""

    def __init__(self, repo_gastos: RepositorioGastos, repo_caja: RepositorioCaja,
                 repo_productos: RepositorioProductos):
        self._repo_gastos = repo_gastos
        self._repo_caja = repo_caja
        self._repo_productos = repo_productos

    def registrar(self, lineas) -> Gasto:
        sesion = self._repo_caja.sesion_abierta()
        if not sesion:
            raise CajaCerradaError()
        if not lineas:
            raise CarritoVacioError()

        items = []
        for linea in lineas:
            producto = self._repo_productos.obtener(linea.producto_id)
            costo_unitario = producto.costo if producto else 0
            items.append(ItemGasto(linea.producto_id, linea.nombre, costo_unitario, linea.cantidad))

        gasto = Gasto(
            id=nuevo_id(), sesion_id=sesion.id, timestamp=marca_de_tiempo(),
            items=items, total=sum(it.subtotal for it in items),
        )
        ajustes_stock: dict[str, int] = {}
        for linea in lineas:
            ajustes_stock[linea.producto_id] = ajustes_stock.get(linea.producto_id, 0) - linea.cantidad
        self._repo_gastos.agregar_con_ajuste_stock(gasto, ajustes_stock)
        return gasto
