from __future__ import annotations

import shutil
from pathlib import Path

from ..dominio.entidades import CATEGORIAS_BASE, MovimientoStock, Producto
from ..dominio.excepciones import ProductoNoEncontradoError
from ..dominio.repositorios import RepositorioMovimientosStock, RepositorioProductos
from ..infraestructura.conexion import marca_de_tiempo, nuevo_id
from ..infraestructura.rutas import carpeta_imagenes_productos


class ServicioProductos:
    def __init__(self, repositorio: RepositorioProductos, repo_movimientos: RepositorioMovimientosStock):
        self._repo = repositorio
        self._repo_movimientos = repo_movimientos

    def listar(self, solo_activos: bool = False) -> list[Producto]:
        productos = self._repo.listar()
        if solo_activos:
            productos = [p for p in productos if p.activo]
        return productos

    def categorias(self) -> list[str]:
        vistas = {p.categoria for p in self._repo.listar()}
        ordenadas = [c for c in CATEGORIAS_BASE if c in vistas]
        extra = sorted(vistas - set(CATEGORIAS_BASE))
        return ordenadas + extra

    def obtener(self, producto_id: str) -> Producto:
        producto = self._repo.obtener(producto_id)
        if not producto:
            raise ProductoNoEncontradoError()
        return producto

    def crear(self, nombre: str, categoria: str, precio: int,
              stock: int = 0, stock_minimo: int = 5, costo: int = 0) -> Producto:
        orden_maximo = max((p.orden for p in self._repo.listar()), default=-1)
        producto = Producto(
            id=nuevo_id(), nombre=nombre.strip(), categoria=categoria.strip(), precio=int(precio), activo=True,
            stock=int(stock), stock_minimo=int(stock_minimo), costo=int(costo), orden=orden_maximo + 1,
        )
        self._repo.guardar(producto)
        return producto

    def actualizar(self, producto_id: str, nombre: str, categoria: str, precio: int,
                    stock: int | None = None, stock_minimo: int | None = None, costo: int | None = None) -> Producto:
        producto = self._repo.obtener(producto_id)
        if not producto:
            raise ProductoNoEncontradoError()
        producto.nombre = nombre.strip()
        producto.categoria = categoria.strip()
        producto.precio = int(precio)
        if stock is not None:
            producto.stock = int(stock)
        if stock_minimo is not None:
            producto.stock_minimo = int(stock_minimo)
        if costo is not None:
            producto.costo = int(costo)
        self._repo.guardar(producto)
        return producto

    def ajustar_stock(self, producto_id: str, cantidad_delta: int) -> Producto:
        producto = self._repo.obtener(producto_id)
        if not producto:
            raise ProductoNoEncontradoError()
        producto.stock += int(cantidad_delta)
        self._repo.guardar(producto)
        self._repo_movimientos.agregar(MovimientoStock(
            id=nuevo_id(), producto_id=producto.id, nombre_producto=producto.nombre,
            cantidad=int(cantidad_delta), timestamp=marca_de_tiempo(),
        ))
        return producto

    def reponer_por_paca(self, producto_id: str, unidades_por_paca: int, cantidad_pacas: int) -> Producto:
        """Repone stock en pacas: guarda el tamaño de paca y la cantidad para la proxima vez."""
        producto = self._repo.obtener(producto_id)
        if not producto:
            raise ProductoNoEncontradoError()
        producto.unidades_por_paca = max(1, int(unidades_por_paca))
        producto.ultima_cantidad_pacas = max(1, int(cantidad_pacas))
        self._repo.guardar(producto)
        return self.ajustar_stock(producto_id, producto.unidades_por_paca * producto.ultima_cantidad_pacas)

    def reiniciar_todo_stock(self) -> None:
        for producto in self._repo.listar():
            if producto.stock != 0:
                self.ajustar_stock(producto.id, -producto.stock)

    def vaciar_historial_movimientos(self) -> None:
        """Borra el log de reposiciones de stock por completo (no afecta el stock actual)."""
        self._repo_movimientos.eliminar_todo()

    def mover_orden(self, producto_id: str, delta: int) -> None:
        productos = sorted(self._repo.listar(), key=lambda p: p.orden)
        indice = next((i for i, p in enumerate(productos) if p.id == producto_id), None)
        if indice is None:
            raise ProductoNoEncontradoError()
        vecino = indice + (1 if delta > 0 else -1)
        if vecino < 0 or vecino >= len(productos):
            return
        actual, otro = productos[indice], productos[vecino]
        actual.orden, otro.orden = otro.orden, actual.orden
        self._repo.guardar(actual)
        self._repo.guardar(otro)

    def establecer_imagen(self, producto_id: str, ruta_origen: Path) -> Producto:
        producto = self._repo.obtener(producto_id)
        if not producto:
            raise ProductoNoEncontradoError()
        ruta_origen = Path(ruta_origen)
        self._borrar_imagen_actual(producto)
        destino = carpeta_imagenes_productos() / f"{producto.id}{ruta_origen.suffix.lower()}"
        shutil.copyfile(ruta_origen, destino)
        producto.imagen_archivo = destino.name
        self._repo.guardar(producto)
        return producto

    def quitar_imagen(self, producto_id: str) -> Producto:
        producto = self._repo.obtener(producto_id)
        if not producto:
            raise ProductoNoEncontradoError()
        self._borrar_imagen_actual(producto)
        producto.imagen_archivo = None
        self._repo.guardar(producto)
        return producto

    def _borrar_imagen_actual(self, producto: Producto) -> None:
        if not producto.imagen_archivo:
            return
        anterior = carpeta_imagenes_productos() / producto.imagen_archivo
        anterior.unlink(missing_ok=True)

    def cambiar_estado(self, producto_id: str) -> Producto:
        producto = self._repo.obtener(producto_id)
        if not producto:
            raise ProductoNoEncontradoError()
        producto.activo = not producto.activo
        self._repo.guardar(producto)
        return producto

    def eliminar(self, producto_id: str) -> None:
        self._repo.eliminar(producto_id)
