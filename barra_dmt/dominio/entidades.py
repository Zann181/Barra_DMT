"""Entidades del dominio: objetos de negocio puros, sin dependencias de UI ni de base de datos."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

METODOS_PAGO = ("Efectivo", "QR")

CATEGORIAS_BASE = ("Cervezas", "Cocteles", "Licores", "Sin alcohol", "Comida", "Snacks")


@dataclass
class Producto:
    id: str
    nombre: str
    categoria: str
    precio: int
    activo: bool = True
    stock: int = 0
    stock_minimo: int = 5
    costo: int = 0
    imagen_archivo: Optional[str] = None
    orden: int = 0
    unidades_por_paca: int = 1
    ultima_cantidad_pacas: int = 1


@dataclass
class MovimientoStock:
    id: str
    producto_id: str
    nombre_producto: str
    cantidad: int
    timestamp: float


@dataclass
class ItemVenta:
    producto_id: str
    nombre: str
    precio_unitario: int
    cantidad: int

    @property
    def subtotal(self) -> int:
        return self.precio_unitario * self.cantidad


@dataclass
class Venta:
    id: str
    sesion_id: str
    timestamp: float
    items: list[ItemVenta]
    total: int
    metodo_pago: str
    efectivo_recibido: int
    cambio: int
    anulada: bool = False


@dataclass
class ItemGasto:
    producto_id: str
    nombre: str
    costo_unitario: int
    cantidad: int

    @property
    def subtotal(self) -> int:
        return self.costo_unitario * self.cantidad


@dataclass
class Gasto:
    """Producto entregado a integrantes (DMT): no es ingreso, se contabiliza
    al valor de costo y descuenta stock igual que una venta."""
    id: str
    sesion_id: str
    timestamp: float
    items: list[ItemGasto]
    total: int


@dataclass
class GastoCaja:
    """Gasto en efectivo pagado desde la caja durante el turno (hielo, transporte,
    domicilio, etc.) -- a diferencia de Gasto (DMT), no esta ligado a un producto
    del catalogo, es solo un concepto libre + un monto."""
    id: str
    sesion_id: str
    timestamp: float
    concepto: str
    monto: int


@dataclass
class SesionCaja:
    id: str
    cajero: str
    abierta_en: float
    efectivo_inicial: int
    cerrada_en: Optional[float] = None


@dataclass
class CierreCaja:
    sesion_id: str
    cajero: str
    abierta_en: float
    cerrada_en: float
    efectivo_inicial: int
    total_ventas: int
    total_efectivo: int
    total_qr: int
    total_gastos_dmt: int
    total_gastos_caja: int
    efectivo_esperado: int
    efectivo_contado: int
    diferencia: int
