"""Puertos del dominio: contratos que la infraestructura debe implementar.

La capa de aplicacion depende solo de estas interfaces, nunca de SQLite directamente.
Eso permite cambiar el motor de almacenamiento sin tocar los casos de uso.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from .entidades import CierreCaja, Gasto, GastoCaja, MovimientoStock, Producto, SesionCaja, Venta


class RepositorioProductos(ABC):
    @abstractmethod
    def listar(self) -> list[Producto]: ...

    @abstractmethod
    def obtener(self, producto_id: str) -> Optional[Producto]: ...

    @abstractmethod
    def guardar(self, producto: Producto) -> None: ...

    @abstractmethod
    def eliminar(self, producto_id: str) -> None: ...


class RepositorioVentas(ABC):
    @abstractmethod
    def agregar(self, venta: Venta) -> None: ...

    @abstractmethod
    def agregar_con_ajuste_stock(self, venta: Venta, ajustes_stock: dict[str, int]) -> None:
        """Como agregar(), pero aplica los deltas de stock (producto_id -> delta)
        en la misma transaccion. Evita abrir una conexion y hacer un commit por
        cada linea del carrito."""
        ...

    @abstractmethod
    def listar(self) -> list[Venta]: ...

    @abstractmethod
    def obtener(self, venta_id: str) -> Optional[Venta]: ...

    @abstractmethod
    def marcar_anulada(self, venta_id: str) -> None: ...

    @abstractmethod
    def eliminar(self, venta_id: str) -> None: ...

    @abstractmethod
    def listar_por_sesion(self, sesion_id: str) -> list[Venta]: ...

    @abstractmethod
    def eliminar_por_sesion(self, sesion_id: str) -> None: ...


class RepositorioGastos(ABC):
    @abstractmethod
    def agregar(self, gasto: Gasto) -> None: ...

    @abstractmethod
    def agregar_con_ajuste_stock(self, gasto: Gasto, ajustes_stock: dict[str, int]) -> None:
        """Como agregar(), pero aplica los deltas de stock (producto_id -> delta)
        en la misma transaccion. Evita abrir una conexion y hacer un commit por
        cada linea del carrito."""
        ...

    @abstractmethod
    def listar(self) -> list[Gasto]: ...

    @abstractmethod
    def listar_por_sesion(self, sesion_id: str) -> list[Gasto]: ...

    @abstractmethod
    def eliminar_por_sesion(self, sesion_id: str) -> None: ...


class RepositorioGastosCaja(ABC):
    """Gastos en efectivo pagados desde la caja (hielo, transporte, etc.),
    no ligados a productos del catalogo -- ver GastoCaja."""

    @abstractmethod
    def agregar(self, gasto: GastoCaja) -> None: ...

    @abstractmethod
    def listar(self) -> list[GastoCaja]: ...

    @abstractmethod
    def listar_por_sesion(self, sesion_id: str) -> list[GastoCaja]: ...

    @abstractmethod
    def eliminar(self, gasto_id: str) -> None: ...

    @abstractmethod
    def eliminar_por_sesion(self, sesion_id: str) -> None: ...

    @abstractmethod
    def conceptos_usados(self) -> list[str]:
        """Conceptos distintos ya usados alguna vez, mas recientes primero --
        para que el formulario los recuerde y no haya que volver a escribirlos."""
        ...


class RepositorioMovimientosStock(ABC):
    @abstractmethod
    def agregar(self, movimiento: MovimientoStock) -> None: ...

    @abstractmethod
    def listar(self, desde=None, hasta=None) -> list[MovimientoStock]: ...

    @abstractmethod
    def eliminar_todo(self) -> None: ...


class RepositorioCaja(ABC):
    @abstractmethod
    def sesion_abierta(self) -> Optional[SesionCaja]: ...

    @abstractmethod
    def abrir_sesion(self, sesion: SesionCaja) -> None: ...

    @abstractmethod
    def cerrar_sesion(self, sesion_id: str, cerrada_en: float) -> None: ...

    @abstractmethod
    def guardar_cierre(self, cierre: CierreCaja) -> None: ...

    @abstractmethod
    def listar_cierres(self) -> list[CierreCaja]: ...

    @abstractmethod
    def listar_sesiones(self) -> list[SesionCaja]: ...

    @abstractmethod
    def obtener_sesion(self, sesion_id: str) -> Optional[SesionCaja]: ...

    @abstractmethod
    def actualizar_sesion(self, sesion: SesionCaja) -> None: ...

    @abstractmethod
    def eliminar_sesion(self, sesion_id: str) -> None: ...

    @abstractmethod
    def obtener_cierre(self, sesion_id: str) -> Optional[CierreCaja]: ...

    @abstractmethod
    def actualizar_cierre(self, cierre: CierreCaja) -> None: ...

    @abstractmethod
    def eliminar_cierre(self, sesion_id: str) -> None: ...
