"""Errores de negocio. La capa de presentacion los captura y los muestra al usuario."""


class ErrorDeNegocio(Exception):
    pass


class CajaCerradaError(ErrorDeNegocio):
    def __init__(self):
        super().__init__("La caja esta cerrada. Abrela antes de registrar ventas.")


class CajaYaAbiertaError(ErrorDeNegocio):
    def __init__(self):
        super().__init__("Ya hay una caja abierta en este turno.")


class CarritoVacioError(ErrorDeNegocio):
    def __init__(self):
        super().__init__("Agrega al menos un producto antes de cobrar.")


class EfectivoInsuficienteError(ErrorDeNegocio):
    def __init__(self, faltante: int):
        super().__init__(f"El efectivo recibido no cubre el total. Faltan ${faltante:,}".replace(",", "."))


class ProductoNoEncontradoError(ErrorDeNegocio):
    def __init__(self):
        super().__init__("El producto no existe o fue eliminado.")


class VentaNoEncontradaError(ErrorDeNegocio):
    def __init__(self):
        super().__init__("La venta no existe.")


class CierreNoEncontradoError(ErrorDeNegocio):
    def __init__(self):
        super().__init__("El turno no existe o ya fue eliminado.")
