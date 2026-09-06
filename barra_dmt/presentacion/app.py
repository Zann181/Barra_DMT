"""Capa de presentacion: ventana Tkinter que consume los servicios de aplicacion.

No contiene SQL ni reglas de negocio -- solo arma la interfaz y llama a la
capa de aplicacion, igual que lo haria un controlador web.
"""
from __future__ import annotations

import datetime
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from ..aplicacion.servicio_analisis import ServicioAnalisis
from ..aplicacion.servicio_caja import ServicioCaja
from ..aplicacion.servicio_exportacion import ServicioExportacion
from ..aplicacion.servicio_gastos import ServicioGastos
from ..aplicacion.servicio_productos import ServicioProductos
from ..aplicacion.servicio_pronostico import ServicioPronostico
from ..aplicacion.servicio_ventas import LineaCarrito, ServicioVentas
from ..dominio.entidades import METODOS_PAGO
from ..dominio.excepciones import ErrorDeNegocio
from ..infraestructura.conexion import inicializar_base_datos
from ..infraestructura.repositorio_caja_sqlite import RepositorioCajaSQLite
from ..infraestructura.repositorio_gastos_sqlite import RepositorioGastosSQLite
from ..infraestructura.repositorio_gastos_caja_sqlite import RepositorioGastosCajaSQLite
from ..infraestructura.repositorio_movimientos_stock_sqlite import RepositorioMovimientosStockSQLite
from ..infraestructura.repositorio_productos_sqlite import RepositorioProductosSQLite
from ..infraestructura.repositorio_ventas_sqlite import RepositorioVentasSQLite
from ..infraestructura.rutas import ruta_base_datos
from . import utilidades_ui as ui
from .recursos_splash import LOGO_ICONO_B64, LOGO_MARCA_AGUA_B64, LOGO_MARCA_B64, LOGO_SPLASH_B64

_RUTA_ICONO_ICO = Path(__file__).resolve().parent / "logo.ico"


def _aplicar_icono_ventana(ventana: tk.Misc) -> None:
    """iconphoto() solo cambia el icono chico de la ventana -- en Windows la
    barra de tareas y el alt-tab toman el icono de iconbitmap() con un .ico
    real (via el mecanismo nativo de Win32), asi que hay que poner los dos."""
    if _RUTA_ICONO_ICO.exists():
        try:
            ventana.iconbitmap(default=str(_RUTA_ICONO_ICO))
        except tk.TclError:
            pass

OPCIONES_TICKET = (*METODOS_PAGO, "DMT")


class MarcoDesplazable(ttk.Frame):
    """Frame con scroll vertical, para grillas de productos largas."""

    def __init__(self, maestro, **kw):
        super().__init__(maestro, **kw)
        self.canvas = tk.Canvas(self, bg=ui.SURFACE, highlightthickness=0)
        barra = ttk.Scrollbar(self, orient="vertical", style="Desplazable.Vertical.TScrollbar",
                               command=self.canvas.yview)
        self.interior = ttk.Frame(self.canvas)
        self.interior.bind("<Configure>", self._al_cambiar_interior)
        self._ventana = self.canvas.create_window((0, 0), window=self.interior, anchor="nw")
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self._ventana, width=e.width))
        self.canvas.configure(yscrollcommand=barra.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        for widget in (self.canvas, self.interior):
            widget.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._rueda))
            widget.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _al_cambiar_interior(self, _evento):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        # Enter/Leave no burbujean a traves de widgets hijos en Tk: sin esto,
        # la rueda del mouse solo scrollea sobre huecos vacios del fondo, no
        # sobre botones/filas que cubren casi toda el area (ej. el carrito).
        self._habilitar_rueda_recursivo(self.interior)

    def _habilitar_rueda_recursivo(self, widget):
        widget.bind("<MouseWheel>", self._rueda)
        for hijo in widget.winfo_children():
            self._habilitar_rueda_recursivo(hijo)

    def _rueda(self, evento):
        self.canvas.yview_scroll(int(-evento.delta / 120), "units")


class AplicacionBarra:
    COLUMNAS_GRILLA = 4

    def __init__(self, raiz: tk.Tk):
        self.raiz = raiz
        ui.aplicar_estilos(raiz)
        raiz.title("Barra DMT · Caja")
        raiz.geometry("1240x780")
        raiz.minsize(1000, 640)
        _aplicar_icono_ventana(raiz)
        self._imagen_icono = tk.PhotoImage(data=LOGO_ICONO_B64)
        raiz.iconphoto(True, self._imagen_icono)
        self._imagen_marca_agua = tk.PhotoImage(data=LOGO_MARCA_AGUA_B64)

        inicializar_base_datos()
        repo_movimientos = RepositorioMovimientosStockSQLite()
        self.servicio_productos = ServicioProductos(RepositorioProductosSQLite(), repo_movimientos)
        repo_ventas = RepositorioVentasSQLite()
        repo_caja = RepositorioCajaSQLite()
        repo_gastos = RepositorioGastosSQLite()
        repo_gastos_caja = RepositorioGastosCajaSQLite()
        self.servicio_ventas = ServicioVentas(repo_ventas, repo_caja, RepositorioProductosSQLite())
        self.servicio_gastos = ServicioGastos(repo_gastos, repo_caja, RepositorioProductosSQLite())
        self.servicio_caja = ServicioCaja(repo_caja, repo_ventas, repo_gastos, repo_gastos_caja)
        self.servicio_analisis = ServicioAnalisis(
            repo_ventas, RepositorioProductosSQLite(), repo_movimientos, repo_caja, repo_gastos)
        self.servicio_pronostico = ServicioPronostico(repo_ventas, RepositorioProductosSQLite(), repo_caja)
        self.servicio_exportacion = ServicioExportacion(
            self.servicio_caja, self.servicio_analisis, self.servicio_pronostico, repo_ventas)

        self.carrito: list[LineaCarrito] = []
        self.categoria_activa = "Todas"
        self.busqueda_venta = ""
        self.busqueda_productos = ""
        self.orden_productos = "manual"
        self.orden_productos_desc = False
        self.columnas_grilla = self.COLUMNAS_GRILLA
        self.orden_venta = "manual"
        self.metodo_pago = "Efectivo"
        self.filtro_historial = "hoy"
        self.rango_analisis = "todo"
        self.turno_analisis = "todos"
        self.mostrar_ayuda_stats = False
        self.granularidad_pronostico = "dia"
        self.horizonte_pronostico = 30

        self._construir_shell()
        self.renderizar_todo()

    # ---------------------------------------------------------- shell
    def _construir_shell(self):
        encabezado = ttk.Frame(self.raiz, style="Fondo.TFrame", padding=(16, 12))
        encabezado.pack(fill="x")

        marca = ttk.Frame(encabezado, style="Fondo.TFrame")
        marca.pack(side="left")
        self._imagen_marca = tk.PhotoImage(data=LOGO_MARCA_B64)
        tk.Label(marca, image=self._imagen_marca, bg=ui.BG, bd=0,
                  highlightthickness=0).pack(side="left", padx=(0, 8))
        tk.Label(marca, text="BARRA DMT", bg=ui.BG, fg=ui.TEXT,
                  font=("Segoe UI", 17, "bold")).pack(side="left")
        tk.Label(marca, text="  CAJA", bg=ui.BG, fg=ui.EMERALD,
                  font=("Segoe UI Semibold", 10)).pack(side="left")

        self.etiqueta_estado = tk.Label(encabezado, bg=ui.SURFACE, fg=ui.TEXT_DIM,
                                         font=("Segoe UI", 9, "bold"), padx=12, pady=6)
        self.etiqueta_estado.pack(side="right")

        self.ruta_bd_var = tk.StringVar(value=f"BD: {ruta_base_datos()}")
        tk.Label(self.raiz, textvariable=self.ruta_bd_var, bg=ui.BG, fg=ui.TEXT_FAINT,
                  font=("Segoe UI", 8), anchor="w", padx=16).pack(fill="x", side="bottom")

        self.notebook = ttk.Notebook(self.raiz)
        self.tab_venta = ttk.Frame(self.notebook, padding=14)
        self.tab_productos = ttk.Frame(self.notebook, padding=14)
        self.tab_historial = ttk.Frame(self.notebook, padding=14)
        self.tab_analisis = ttk.Frame(self.notebook, padding=14)
        self.tab_pronostico = ttk.Frame(self.notebook, padding=14)
        self.tab_caja = ttk.Frame(self.notebook, padding=14)
        self.notebook.add(self.tab_venta, text="Venta")
        self.notebook.add(self.tab_productos, text="Productos")
        self.notebook.add(self.tab_historial, text="Historial")
        self.notebook.add(self.tab_analisis, text="Analisis")
        self.notebook.add(self.tab_pronostico, text="Pronostico")
        self.notebook.add(self.tab_caja, text="Caja")
        self.notebook.pack(fill="both", expand=True, padx=14, pady=(0, 4))

        # Cada pestaña se reconstruye solo cuando el usuario la mira -- si se
        # redibujaran las 5 (incluyendo graficos de Analisis) en cada click
        # del carrito, la app se sentia lenta y con parpadeo constante.
        self._renderizadores_tab = {
            self.tab_venta: lambda: self._renderizar_venta(self._sesion_actual),
            self.tab_productos: self._renderizar_productos,
            self.tab_historial: self._renderizar_historial,
            self.tab_analisis: self._renderizar_analisis,
            self.tab_pronostico: self._renderizar_pronostico,
            self.tab_caja: lambda: self._renderizar_caja(self._sesion_actual),
        }
        self._tabs_pendientes: set = set()
        self._sesion_actual = None
        self._insignias_stock: dict = {}
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._refrescar_tab_activa())

    def _limpiar(self, contenedor):
        for hijo in contenedor.winfo_children():
            hijo.destroy()

    def renderizar_todo(self):
        sesion = self.servicio_caja.sesion_actual()
        self._sesion_actual = sesion
        if sesion:
            self.etiqueta_estado.configure(text=f"● CAJA ABIERTA · {sesion.cajero}", fg=ui.SUCCESS)
        else:
            self.etiqueta_estado.configure(text="● CAJA CERRADA", fg=ui.DANGER)
        # Todas quedan pendientes; solo se redibuja de una la que esta activa
        # ahora mismo -- las demas se ponen al dia recien cuando se abren.
        self._tabs_pendientes = set(self._renderizadores_tab)
        self._refrescar_tab_activa()

    def _refrescar_tab_activa(self):
        actual = self.notebook.nametowidget(self.notebook.select())
        if actual not in self._tabs_pendientes:
            return
        self._tabs_pendientes.discard(actual)
        self._renderizadores_tab[actual]()

    # ============================================================ VENTA
    def _renderizar_venta(self, sesion):
        self._limpiar(self.tab_venta)
        if not sesion:
            centro = ttk.Frame(self.tab_venta)
            centro.place(relx=0.5, rely=0.42, anchor="center")
            tk.Label(centro, text="🔒", bg=ui.SURFACE, font=("Segoe UI", 30)).pack(pady=(0, 10))
            ttk.Label(centro, text="La caja esta cerrada", style="Titulo.TLabel").pack()
            ttk.Label(centro, text="Abrela desde la pestaña Caja para empezar a vender.",
                       style="Sutil.TLabel").pack(pady=(4, 14))
            ttk.Button(centro, text="Ir a Caja", style="Accent.TButton",
                       command=lambda: self.notebook.select(self.tab_caja)).pack()
            return

        self.tab_venta.columnconfigure(0, weight=1)
        self.tab_venta.columnconfigure(1, weight=0)

        # Fila 1: buscador + orden, juntos en la misma fila para no gastar
        # espacio vertical extra.
        fila_busqueda = ttk.Frame(self.tab_venta)
        fila_busqueda.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        ttk.Label(fila_busqueda, text="Buscar:", style="Etiqueta.TLabel").pack(side="left", padx=(0, 6))
        entrada_busqueda = ttk.Entry(fila_busqueda, width=32)
        entrada_busqueda.insert(0, self.busqueda_venta)
        entrada_busqueda.pack(side="left")
        entrada_busqueda.bind("<KeyRelease>", lambda e: self._filtrar_venta(entrada_busqueda.get()))

        ttk.Label(fila_busqueda, text="Ordenar:", style="Etiqueta.TLabel").pack(side="left", padx=(18, 6))
        for valor, etiqueta in (("manual", "Manual"), ("stock", "Stock"), ("categoria", "Categoria")):
            estilo = "CatActiva.TButton" if valor == self.orden_venta else "Cat.TButton"
            ttk.Button(fila_busqueda, text=etiqueta, style=estilo,
                       command=lambda v=valor: self._elegir_orden(v)).pack(side="left", padx=4)

        # Fila 2: categorias (izquierda, todo el ancho disponible) + control de columnas (derecha).
        barra_superior = ttk.Frame(self.tab_venta)
        barra_superior.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        columnas_frame = ttk.Frame(barra_superior)
        columnas_frame.pack(side="right")
        ttk.Label(columnas_frame, text="Por fila:", style="Etiqueta.TLabel").pack(side="left", padx=(0, 6))
        ttk.Button(columnas_frame, text="−", width=2,
                   command=lambda: self._ajustar_columnas_grilla(-1)).pack(side="left")
        self._etiqueta_columnas_grilla = tk.Label(
            columnas_frame, text=str(self.columnas_grilla), bg=ui.SURFACE, fg=ui.TEXT,
            font=ui.FUENTE_MONO, width=2, anchor="center")
        self._etiqueta_columnas_grilla.pack(side="left", padx=4)
        ttk.Button(columnas_frame, text="+", width=2,
                   command=lambda: self._ajustar_columnas_grilla(1)).pack(side="left")

        filtros = ttk.Frame(barra_superior)
        filtros.pack(side="left", fill="x", expand=True)
        categorias = ["Todas"] + self.servicio_productos.categorias()
        for cat in categorias:
            estilo = "CatActiva.TButton" if cat == self.categoria_activa else "Cat.TButton"
            ttk.Button(filtros, text=cat, style=estilo,
                       command=lambda c=cat: self._elegir_categoria(c)).pack(side="left", padx=4)

        self._marco_grilla_venta = MarcoDesplazable(self.tab_venta)
        self._marco_grilla_venta.grid(row=2, column=0, sticky="nsew", padx=(0, 14))
        self.tab_venta.rowconfigure(2, weight=1)
        self._llenar_grilla_venta()

        self._panel_ticket_widget = self._panel_ticket(self.tab_venta)
        self._panel_ticket_widget.grid(row=2, column=1, sticky="ns")

    def _refrescar_ticket(self):
        """Redibuja solo el panel de cuenta actual, sin tocar la grilla de
        productos (que reconsulta la BD y recrea todas las tarjetas). Al
        agregar/quitar items del carrito solo cambia el ticket -- redibujar
        la grilla completa en cada click era lo que se sentia lento/con
        parpadeo en eventos con clicks rapidos."""
        if not getattr(self, "_panel_ticket_widget", None) or not self._panel_ticket_widget.winfo_exists():
            self.renderizar_todo()
            return
        self._panel_ticket_widget.destroy()
        self._panel_ticket_widget = self._panel_ticket(self.tab_venta)
        self._panel_ticket_widget.grid(row=2, column=1, sticky="ns")

    def _llenar_grilla_venta(self):
        contenedor = self._marco_grilla_venta.interior
        self._limpiar(contenedor)
        self._insignias_stock = {}

        productos = [p for p in self.servicio_productos.listar() if p.activo]
        if self.categoria_activa != "Todas":
            productos = [p for p in productos if p.categoria == self.categoria_activa]
        texto_busqueda = self.busqueda_venta.strip().lower()
        if texto_busqueda:
            productos = [p for p in productos if texto_busqueda in p.nombre.lower()]

        if self.orden_venta == "stock":
            productos = sorted(productos, key=lambda p: (p.stock, p.nombre.lower()))
        elif self.orden_venta == "categoria":
            productos = sorted(productos, key=lambda p: (p.categoria.lower(), p.nombre.lower()))
        # "manual": se deja el orden que ya trae listar() (columna orden).

        if not productos:
            ttk.Label(contenedor, text="No hay productos que coincidan.",
                       style="Sutil.TLabel").grid(row=0, column=0, padx=10, pady=20)
        else:
            for col in range(self.columnas_grilla):
                contenedor.columnconfigure(col, weight=1, uniform="prod")
            for i, producto in enumerate(productos):
                self._tarjeta_producto(contenedor, producto).grid(
                    row=i // self.columnas_grilla, column=i % self.columnas_grilla,
                    sticky="nsew", padx=8, pady=12)

    def _elegir_orden(self, orden):
        self.orden_venta = orden
        self.renderizar_todo()

    def _ajustar_columnas_grilla(self, delta):
        nuevo = max(2, min(6, self.columnas_grilla + delta))
        if nuevo == self.columnas_grilla:
            return
        self.columnas_grilla = nuevo
        if hasattr(self, "_etiqueta_columnas_grilla"):
            self._etiqueta_columnas_grilla.configure(text=str(self.columnas_grilla))
        self._llenar_grilla_venta()

    def _filtrar_venta(self, texto):
        self.busqueda_venta = texto
        self._llenar_grilla_venta()

    def _elegir_categoria(self, cat):
        self.categoria_activa = cat
        self.renderizar_todo()

    def _avatar_producto(self, maestro, producto, tamano, bg_fondo):
        """Miniatura de imagen si el producto tiene una cargada; si no, un cuadro
        con la inicial del nombre sobre el color de su categoria, para que
        todas las filas/tarjetas queden con el mismo icono a la izquierda."""
        miniatura = ui.cargar_miniatura(producto.imagen_archivo, (tamano, tamano))
        if miniatura:
            etiqueta = tk.Label(maestro, image=miniatura, bg=bg_fondo)
            etiqueta.image = miniatura
            return etiqueta

        color = ui.CATEGORIA_COLOR.get(producto.categoria, ui.ACCENT)
        contenedor = tk.Frame(maestro, width=tamano, height=tamano, bg=color)
        contenedor.pack_propagate(False)
        letra = producto.nombre.strip()[:1].upper() if producto.nombre.strip() else "?"
        tk.Label(contenedor, text=letra, bg=color, fg=ui.ACCENT_INK,
                  font=("Segoe UI Semibold", max(10, int(tamano * 0.4)), "bold")).pack(expand=True)
        return contenedor

    def _texto_color_stock(self, producto):
        if producto.stock <= 0:
            return "Agotado", ui.SEMAFORO_ROJO
        if producto.stock <= producto.stock_minimo:
            return f"Quedan {producto.stock}", ui.SEMAFORO_AMARILLO
        return f"Quedan {producto.stock}", ui.SEMAFORO_VERDE

    def _tarjeta_producto(self, maestro, producto):
        color = ui.CATEGORIA_COLOR.get(producto.categoria, ui.ACCENT)
        tarjeta = tk.Frame(maestro, bg=ui.SURFACE, cursor="hand2", highlightthickness=1,
                            highlightbackground=ui.BORDER, highlightcolor=ui.BORDER)
        tk.Frame(tarjeta, bg=color, width=4).pack(side="left", fill="y")
        cuerpo = tk.Frame(tarjeta, bg=ui.SURFACE, padx=12, pady=16)
        cuerpo.pack(side="left", fill="both", expand=True)

        self._avatar_producto(cuerpo, producto, 96, ui.SURFACE).pack(anchor="w", pady=(0, 12))

        tk.Label(cuerpo, text=producto.nombre, bg=ui.SURFACE, fg=ui.TEXT,
                  font=("Segoe UI", 10, "bold"), wraplength=160, justify="left", anchor="w").pack(fill="x", pady=(0, 6))
        tk.Label(cuerpo, text=producto.categoria.upper(), bg=ui.SURFACE, fg=ui.EMERALD,
                  font=("Segoe UI Semibold", 8), anchor="w").pack(fill="x", pady=(0, 10))
        tk.Label(cuerpo, text=f"$ {ui.formato_cop(producto.precio)}", bg=ui.SURFACE, fg=ui.ACCENT,
                  font=ui.FUENTE_MONO, anchor="w").pack(fill="x")

        texto_stock, color_stock = self._texto_color_stock(producto)

        insignia = tk.Label(tarjeta, text=texto_stock, bg=color_stock, fg=ui.ACCENT_INK,
                             font=("Segoe UI", 8, "bold"), padx=7, pady=3)
        insignia.place(relx=1.0, rely=0.0, x=-5, y=5, anchor="ne")
        self._insignias_stock[producto.id] = insignia

        def click(_e=None):
            self._agregar_al_carrito(producto)

        def resaltar(_e=None):
            tarjeta.configure(highlightbackground=ui.ACCENT, highlightcolor=ui.ACCENT)

        def quitar_resalte(_e=None):
            tarjeta.configure(highlightbackground=ui.BORDER, highlightcolor=ui.BORDER)

        for widget in (tarjeta, cuerpo, insignia, *cuerpo.winfo_children()):
            widget.bind("<Button-1>", click)
            widget.bind("<Enter>", resaltar)
            widget.bind("<Leave>", quitar_resalte)
        return tarjeta

    def _agregar_al_carrito(self, producto):
        for linea in self.carrito:
            if linea.producto_id == producto.id:
                linea.cantidad += 1
                break
        else:
            self.carrito.append(LineaCarrito(producto.id, producto.nombre, producto.precio, 1))
        self._refrescar_ticket()

    def _panel_ticket(self, maestro):
        total = sum(l.subtotal for l in self.carrito)

        panel = tk.Frame(maestro, bg=ui.SURFACE, width=380, highlightthickness=1,
                          highlightbackground=ui.BORDER)
        panel.pack_propagate(False)

        # Marca de agua: se crea primero para quedar debajo del resto del
        # contenido (Tk apila los widgets nuevos por encima de los viejos).
        tk.Label(panel, image=self._imagen_marca_agua, bg=ui.SURFACE, bd=0,
                  highlightthickness=0).place(relx=0.5, rely=0.42, anchor="center")

        encabezado = tk.Frame(panel, bg=ui.SURFACE, padx=16, pady=16)
        encabezado.pack(fill="x", side="top")
        tk.Label(encabezado, text="Cuenta actual", bg=ui.SURFACE, fg=ui.TEXT,
                  font=("Segoe UI Semibold", 13)).pack(side="left")
        ttk.Button(encabezado, text="Vaciar", command=self._vaciar_carrito).pack(side="right")

        # El boton de cobrar se reserva ANTES del cuerpo con scroll para que
        # nunca quede oculto, sin importar cuanto crezca el contenido de arriba.
        pie = tk.Frame(panel, bg=ui.SURFACE, padx=16)
        pie.pack(fill="x", side="bottom", pady=(0, 16))
        if self.metodo_pago == "DMT":
            costo_dmt = sum(l.cantidad * self._costo_producto(l.producto_id) for l in self.carrito)
            texto_boton = f"Registrar DMT · costo $ {ui.formato_cop(costo_dmt)}"
        else:
            texto_boton = f"Cobrar $ {ui.formato_cop(total)}"
        boton_cobrar = ttk.Button(pie, text=texto_boton, style="Accent.TButton",
                                   command=lambda: self._cobrar(entrada_efectivo))
        boton_cobrar.pack(fill="x", ipady=4)
        if not self.carrito:
            boton_cobrar.state(["disabled"])

        cuerpo_scroll = MarcoDesplazable(panel)
        cuerpo_scroll.pack(fill="both", expand=True, side="top")
        contenedor = cuerpo_scroll.interior
        contenedor.configure(padding=(16, 0, 16, 0))

        lista_carrito = ttk.Frame(contenedor)
        lista_carrito.pack(fill="x", pady=(4, 10))
        if not self.carrito:
            ttk.Label(lista_carrito, text="El carrito esta vacio.", style="Sutil.TLabel").pack(
                anchor="w", pady=10)
        else:
            for linea in self.carrito:
                self._fila_carrito(lista_carrito, linea).pack(fill="x", pady=3)

        linea_total = tk.Frame(contenedor, bg=ui.SURFACE)
        linea_total.pack(fill="x", pady=(4, 12))
        tk.Label(linea_total, text="Total", bg=ui.SURFACE, fg=ui.TEXT_DIM,
                  font=("Segoe UI", 10)).pack(side="left")
        tk.Label(linea_total, text=f"$ {ui.formato_cop(total)}", bg=ui.SURFACE, fg=ui.TEXT,
                  font=ui.FUENTE_TOTAL).pack(side="right")

        ttk.Label(contenedor, text="METODO DE PAGO", style="Etiqueta.TLabel").pack(anchor="w")
        metodos_frame = ttk.Frame(contenedor)
        metodos_frame.pack(fill="x", pady=(4, 10))
        for metodo in OPCIONES_TICKET:
            estilo = "MetodoActivo.TButton" if metodo == self.metodo_pago else "TButton"
            boton_metodo = ttk.Button(metodos_frame, text=metodo, style=estilo,
                       command=lambda m=metodo: self._elegir_metodo(m))
            boton_metodo.pack(side="left", expand=True, fill="x", padx=2)
            if metodo == "DMT":
                ui.Tooltip(boton_metodo, "⚠ No es una venta: se entrega a integrantes del equipo. "
                           "Se registra como gasto al valor de costo (no al de venta) y descuenta "
                           "el stock igual que una venta.")

        entrada_efectivo = None
        etiqueta_cambio = None
        if self.metodo_pago == "Efectivo":
            ttk.Label(contenedor, text="EFECTIVO RECIBIDO", style="Etiqueta.TLabel").pack(anchor="w")
            # Se autocompleta con el total: el cajero solo la cambia si recibe otro monto.
            entrada_efectivo = ui.EntradaDinero(contenedor, total)
            entrada_efectivo.pack(fill="x", pady=(4, 8))
            etiqueta_cambio = tk.Label(contenedor, bg=ui.SURFACE_2, fg=ui.TEXT, font=("Segoe UI", 10),
                                        anchor="w", padx=10, pady=6)
            etiqueta_cambio.pack(fill="x", pady=(0, 10))

            def refrescar_cambio(*_):
                cambio = entrada_efectivo.obtener() - total
                if cambio >= 0:
                    etiqueta_cambio.configure(text=f"Cambio: $ {ui.formato_cop(cambio)}", fg=ui.SUCCESS)
                else:
                    etiqueta_cambio.configure(text=f"Falta: $ {ui.formato_cop(-cambio)}", fg=ui.DANGER)

            entrada_efectivo.bind("<KeyRelease>", refrescar_cambio)
            refrescar_cambio()

        advertencias = self.servicio_ventas.advertencias_stock(self.carrito)
        if advertencias:
            caja_advertencia = tk.Frame(contenedor, bg=ui.SURFACE_2, highlightthickness=1,
                                         highlightbackground=ui.WARNING, padx=10, pady=8)
            caja_advertencia.pack(fill="x", pady=(0, 10))
            tk.Label(caja_advertencia, text="⚠ STOCK INSUFICIENTE", bg=ui.SURFACE_2, fg=ui.WARNING,
                      font=("Segoe UI Semibold", 8), anchor="w").pack(fill="x")
            for mensaje in advertencias:
                tk.Label(caja_advertencia, text=mensaje, bg=ui.SURFACE_2, fg=ui.TEXT_DIM,
                          font=("Segoe UI", 9), anchor="w", justify="left", wraplength=340).pack(fill="x", pady=(2, 0))

        return panel

    def _fila_carrito(self, maestro, linea):
        fila = tk.Frame(maestro, bg=ui.SURFACE_2, highlightthickness=1,
                         highlightbackground=ui.BORDER, padx=8, pady=6)

        encabezado = tk.Frame(fila, bg=ui.SURFACE_2)
        encabezado.pack(fill="x")
        producto = self.servicio_productos.obtener(linea.producto_id)
        if producto:
            self._avatar_producto(encabezado, producto, 28, ui.SURFACE_2).pack(side="left", padx=(0, 8))
        tk.Label(encabezado, text=linea.nombre, bg=ui.SURFACE_2, fg=ui.TEXT,
                  font=("Segoe UI", 9, "bold"), anchor="w", wraplength=130,
                  justify="left").pack(side="left", fill="x", expand=True)

        controles = tk.Frame(fila, bg=ui.SURFACE_2)
        controles.pack(fill="x", pady=(6, 0))

        pid = linea.producto_id
        ttk.Button(controles, text="−", width=2, style="Mini.TButton",
                   command=lambda: self._ajustar_cantidad(pid, -1)).pack(side="left")
        tk.Label(controles, text=str(linea.cantidad), bg=ui.SURFACE_2, fg=ui.TEXT,
                  font=ui.FUENTE_MONO, width=3, anchor="center").pack(side="left", padx=4)
        ttk.Button(controles, text="+", width=2, style="Mini.TButton",
                   command=lambda: self._ajustar_cantidad(pid, 1)).pack(side="left")
        tk.Label(controles, text=f"$ {ui.formato_cop(linea.subtotal)}", bg=ui.SURFACE_2, fg=ui.ACCENT,
                  font=ui.FUENTE_MONO, anchor="e").pack(side="left", expand=True, fill="x", padx=(10, 4))
        ttk.Button(controles, text="🗑", width=2, style="MiniPeligro.TButton",
                   command=lambda: self._ajustar_cantidad(pid, None)).pack(side="right")
        return fila

    def _ajustar_cantidad(self, producto_id, delta):
        if delta is None:
            self.carrito = [l for l in self.carrito if l.producto_id != producto_id]
        else:
            for linea in self.carrito:
                if linea.producto_id == producto_id:
                    linea.cantidad += delta
                    if linea.cantidad <= 0:
                        self.carrito = [l for l in self.carrito if l.producto_id != producto_id]
                    break
        self._refrescar_ticket()

    def _vaciar_carrito(self):
        self.carrito = []
        self._refrescar_ticket()

    def _elegir_metodo(self, metodo):
        self.metodo_pago = metodo
        self._refrescar_ticket()

    def _actualizar_stock_tarjetas(self, ids_productos):
        """Actualiza solo la insignia de stock de las tarjetas afectadas, sin
        reconsultar ni reconstruir toda la grilla."""
        for pid in ids_productos:
            insignia = self._insignias_stock.get(pid)
            if not insignia or not insignia.winfo_exists():
                continue
            producto = self.servicio_productos.obtener(pid)
            if not producto:
                continue
            texto, color = self._texto_color_stock(producto)
            insignia.configure(text=texto, bg=color)

    def _refrescar_tras_venta(self, ids_productos_afectados):
        """Tras una venta/gasto solo cambia el stock: actualiza en el momento
        las insignias de la grilla activa (siempre Venta durante el cobro) y
        deja las demas pestañas (Caja, Historial) pendientes para cuando se
        abran. Antes esto llamaba a renderizar_todo(), que reconsultaba todos
        los productos y reconstruia toda la grilla en cada venta -- se sentia
        lento con varias ventas seguidas."""
        self._tabs_pendientes = set(self._renderizadores_tab) - {self.tab_venta}
        self._actualizar_stock_tarjetas(ids_productos_afectados)

    def _costo_producto(self, producto_id):
        try:
            return self.servicio_productos.obtener(producto_id).costo
        except ErrorDeNegocio:
            return 0

    def _cobrar(self, entrada_efectivo):
        if self.metodo_pago == "DMT":
            try:
                gasto = self.servicio_gastos.registrar(self.carrito)
            except ErrorDeNegocio as e:
                ui.mostrar_error(self.raiz, str(e))
                return
            ids_afectados = {l.producto_id for l in self.carrito}
            self.carrito = []
            self._refrescar_ticket()
            self._refrescar_tras_venta(ids_afectados)
            self._mostrar_toast("✓ DMT registrado", ui.EMERALD, gasto.items, "Gasto (costo)", gasto.total)
            return

        recibido = entrada_efectivo.obtener() if entrada_efectivo else 0
        try:
            venta = self.servicio_ventas.registrar_venta(self.carrito, self.metodo_pago, recibido)
        except ErrorDeNegocio as e:
            ui.mostrar_error(self.raiz, str(e))
            return
        ids_afectados = {l.producto_id for l in self.carrito}
        self.carrito = []
        self._refrescar_ticket()
        self._refrescar_tras_venta(ids_afectados)
        self._mostrar_toast("✓ Venta registrada", ui.SUCCESS, venta.items, venta.metodo_pago, venta.total)

    def _mostrar_toast(self, titulo, color_titulo, items, pie_etiqueta, pie_valor):
        """Notificacion no invasiva (no bloquea, no roba foco) que se desvanece sola.
        Sirve tanto para el recibo de una venta como para el de un registro DMT --
        ambos traen items con .cantidad/.nombre/.subtotal."""
        ventana = tk.Toplevel(self.raiz)
        ventana.overrideredirect(True)
        ventana.attributes("-alpha", 0.0)
        try:
            ventana.attributes("-topmost", True)
        except tk.TclError:
            pass
        contenedor = tk.Frame(ventana, bg=ui.SURFACE, highlightthickness=1,
                               highlightbackground=ui.ACCENT, padx=18, pady=14)
        contenedor.pack()

        tk.Label(contenedor, text=titulo, bg=ui.SURFACE, fg=color_titulo,
                  font=("Segoe UI Semibold", 11)).pack(anchor="w", pady=(0, 8))

        for it in items:
            fila = tk.Frame(contenedor, bg=ui.SURFACE)
            fila.pack(fill="x")
            tk.Label(fila, text=f"{it.cantidad}x {it.nombre}", bg=ui.SURFACE, fg=ui.TEXT_DIM,
                      font=ui.FUENTE_MONO, anchor="w").pack(side="left")
            tk.Label(fila, text=f"$ {ui.formato_cop(it.subtotal)}", bg=ui.SURFACE, fg=ui.TEXT_DIM,
                      font=ui.FUENTE_MONO, anchor="e").pack(side="right", padx=(16, 0))

        tk.Frame(contenedor, bg=ui.BORDER, height=1).pack(fill="x", pady=8)
        fila_total = tk.Frame(contenedor, bg=ui.SURFACE)
        fila_total.pack(fill="x")
        tk.Label(fila_total, text=pie_etiqueta, bg=ui.SURFACE, fg=ui.TEXT_DIM,
                  font=("Segoe UI", 9)).pack(side="left")
        tk.Label(fila_total, text=f"$ {ui.formato_cop(pie_valor)}", bg=ui.SURFACE, fg=ui.TEXT,
                  font=("Segoe UI Semibold", 14)).pack(side="right")

        ventana.update_idletasks()
        ancho, alto = ventana.winfo_width(), ventana.winfo_height()
        x = self.raiz.winfo_rootx() + self.raiz.winfo_width() - ancho - 28
        y = self.raiz.winfo_rooty() + self.raiz.winfo_height() - alto - 28
        ventana.geometry(f"{ancho}x{alto}+{x}+{y}")

        self._animar_toast(ventana)

    def _animar_toast(self, ventana, paso=0, entrada=8, espera=140, salida=14):
        """0..entrada: aparece. entrada..entrada+espera: se queda quieta. resto: se apaga."""
        if not ventana.winfo_exists():
            return
        if paso <= entrada:
            ventana.attributes("-alpha", paso / entrada)
        elif paso > entrada + espera:
            restantes = (entrada + espera + salida) - paso
            if restantes <= 0:
                ventana.destroy()
                return
            ventana.attributes("-alpha", restantes / salida)
        ventana.after(25, lambda: self._animar_toast(ventana, paso + 1, entrada, espera, salida))

    # ============================================================ PRODUCTOS
    def _renderizar_productos(self):
        self._limpiar(self.tab_productos)
        titulos = ttk.Frame(self.tab_productos)
        titulos.pack(fill="x", pady=(0, 8), anchor="w")
        ttk.Label(titulos, text="Productos", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(titulos, text="Catalogo de la barra. Precios en pesos colombianos.",
                   style="Sutil.TLabel").pack(anchor="w")

        barra_acciones = ttk.Frame(self.tab_productos)
        barra_acciones.pack(fill="x", pady=(0, 4), anchor="w")
        ttk.Button(barra_acciones, text="Añadir producto", style="Accent.TButton",
                   command=self._abrir_creacion_producto).pack(side="left", padx=(0, 8))
        ttk.Button(barra_acciones, text="Reposicion masiva", style="Accent.TButton",
                   command=self._abrir_reposicion_masiva).pack(side="left", padx=(0, 8))
        ttk.Button(barra_acciones, text="Reiniciar stock", style="Peligro.TButton",
                   command=self._confirmar_reiniciar_stock).pack(side="left", padx=(0, 8))
        ttk.Button(barra_acciones, text="Vaciar historial de reposiciones", style="Peligro.TButton",
                   command=self._confirmar_vaciar_historial_movimientos).pack(side="left")

        fila_busqueda = ttk.Frame(self.tab_productos)
        fila_busqueda.pack(fill="x", pady=(8, 10))
        ttk.Label(fila_busqueda, text="Buscar:", style="Etiqueta.TLabel").pack(side="left", padx=(0, 6))
        entrada_busqueda = ttk.Entry(fila_busqueda, width=32)
        entrada_busqueda.insert(0, self.busqueda_productos)
        entrada_busqueda.pack(side="left")
        entrada_busqueda.bind("<KeyRelease>", lambda e: self._filtrar_productos(entrada_busqueda.get()))

        tk.Label(fila_busqueda, text="Ordenar por:", bg=ui.SURFACE, fg=ui.EMERALD,
                  font=ui.FUENTE_ETIQUETA).pack(side="left", padx=(20, 6))
        opciones_orden = (("manual", "Manual"), ("stock", "Stock ▲▼"), ("categoria", "Categoria ▲▼"))
        for i, (campo, texto) in enumerate(opciones_orden):
            activo = self.orden_productos == campo
            color = ui.ACCENT if activo else ui.TEXT_DIM
            etiqueta = tk.Label(fila_busqueda, text=texto, bg=ui.SURFACE, fg=color,
                                  font=("Segoe UI Semibold", 9), cursor="hand2")
            etiqueta.pack(side="left")
            etiqueta.bind("<Button-1>", lambda e, c=campo: self._elegir_orden_productos(c))
            if i < len(opciones_orden) - 1:
                tk.Label(fila_busqueda, text=" | ", bg=ui.SURFACE, fg=ui.TEXT_FAINT).pack(side="left")

        self._marco_productos = MarcoDesplazable(self.tab_productos)
        self._marco_productos.pack(fill="both", expand=True)
        self._llenar_lista_productos()

    def _llenar_lista_productos(self):
        contenedor = self._marco_productos.interior
        self._limpiar(contenedor)

        productos = self.servicio_productos.listar()
        texto_busqueda = self.busqueda_productos.strip().lower()
        if texto_busqueda:
            productos = [p for p in productos if texto_busqueda in p.nombre.lower()]

        if self.orden_productos == "stock":
            productos.sort(key=lambda p: p.stock, reverse=self.orden_productos_desc)
        elif self.orden_productos == "categoria":
            productos.sort(key=lambda p: p.categoria.lower(), reverse=self.orden_productos_desc)

        if not productos:
            mensaje = "No hay productos que coincidan." if texto_busqueda else \
                'Todavia no hay productos. Usa "Añadir producto".'
            ttk.Label(contenedor, text=mensaje, style="Sutil.TLabel").pack(anchor="w", padx=4, pady=20)
        else:
            # Cuanto de ese stock es lo repuesto manualmente, para mostrar
            # "base+repuesto" en vez de un solo numero total (solo visual --
            # las ventas y el descuento de stock siguen usando el total real).
            extra_por_producto: dict[str, int] = {}
            for movimiento in self.servicio_analisis.reposiciones_stock():
                extra_por_producto[movimiento.producto_id] = (
                    extra_por_producto.get(movimiento.producto_id, 0) + movimiento.cantidad)

            # Reordenar con las flechas solo tiene sentido en orden manual --
            # con un sort por stock/categoria activo, se desactivan para no
            # confundir (el swap seria contra el orden manual invisible).
            permitir_reordenar = self.orden_productos == "manual"
            for i, producto in enumerate(productos):
                self._fila_producto(contenedor, producto, es_primero=(i == 0),
                                     es_ultimo=(i == len(productos) - 1),
                                     stock_extra=extra_por_producto.get(producto.id, 0),
                                     permitir_reordenar=permitir_reordenar).pack(fill="x", pady=3)

    def _filtrar_productos(self, texto):
        self.busqueda_productos = texto
        self._llenar_lista_productos()

    def _elegir_orden_productos(self, campo):
        if campo == "manual":
            self.orden_productos = "manual"
            self.orden_productos_desc = False
        elif self.orden_productos == campo:
            self.orden_productos_desc = not self.orden_productos_desc
        else:
            self.orden_productos = campo
            self.orden_productos_desc = False
        self._renderizar_productos()

    def _confirmar_reiniciar_stock(self):
        if ui.confirmar(self.raiz, "Reiniciar stock",
                         "Esto pone el stock de TODOS los productos en 0. Queda registrado en "
                         "movimientos de stock. ¿Continuar?"):
            self.servicio_productos.reiniciar_todo_stock()
            ui.avisar(self.raiz, "Stock reiniciado a 0.")
            self._llenar_lista_productos()

    def _confirmar_vaciar_historial_movimientos(self):
        if ui.confirmar(self.raiz, "Vaciar historial de reposiciones",
                         "Esto borra permanentemente el registro de reposiciones de stock "
                         "(no toca el stock actual de los productos ni las ventas). ¿Continuar?"):
            self.servicio_productos.vaciar_historial_movimientos()
            ui.avisar(self.raiz, "Historial de reposiciones vaciado.")
            self._llenar_lista_productos()

    def _fila_producto(self, maestro, producto, es_primero, es_ultimo, stock_extra=0, permitir_reordenar=True):
        color_borde = ui.SEMAFORO_ROJO if not producto.activo else ui.BORDER
        fila = tk.Frame(maestro, bg=ui.SURFACE_2, highlightthickness=2, highlightbackground=color_borde,
                         padx=10, pady=8)

        self._avatar_producto(fila, producto, 44, ui.SURFACE_2).pack(side="left", padx=(0, 10))

        info = tk.Frame(fila, bg=ui.SURFACE_2)
        info.pack(side="left", fill="x", expand=True)
        linea_nombre = tk.Frame(info, bg=ui.SURFACE_2)
        linea_nombre.pack(fill="x", anchor="w")
        color_nombre = ui.SEMAFORO_ROJO if not producto.activo else ui.TEXT
        tk.Label(linea_nombre, text=producto.nombre, bg=ui.SURFACE_2, fg=color_nombre,
                  font=("Segoe UI", 10, "bold")).pack(side="left")
        if not producto.activo:
            tk.Label(linea_nombre, text="INACTIVO", bg=ui.SURFACE_2, fg=ui.SEMAFORO_ROJO,
                      font=("Segoe UI Semibold", 8, "bold")).pack(side="left", padx=(8, 0))
        tk.Label(info, text=f"{producto.categoria}  ·  $ {ui.formato_cop(producto.precio)}",
                  bg=ui.SURFACE_2, fg=ui.TEXT_DIM, font=("Segoe UI", 9)).pack(anchor="w")

        # Muestra "base+repuesto" (ej. 60+30) cuando hubo reposiciones, para ver
        # de un vistazo cuanto era el stock original y cuanto entro despues.
        # El numero que se usa para vender/alertar sigue siendo producto.stock.
        stock_base = producto.stock - stock_extra
        if stock_extra > 0 and stock_base > 0:
            valor_stock = f"{stock_base}+{stock_extra}"
        else:
            valor_stock = str(producto.stock)

        if producto.stock <= 0:
            texto_stock, color_stock = "Agotado", ui.SEMAFORO_ROJO
        elif producto.stock <= producto.stock_minimo:
            texto_stock, color_stock = f"Stock: {valor_stock}", ui.SEMAFORO_AMARILLO
        else:
            texto_stock, color_stock = f"Stock: {valor_stock}", ui.SEMAFORO_VERDE
        tk.Label(fila, text=texto_stock, bg=color_stock, fg=ui.ACCENT_INK,
                  font=("Segoe UI", 8, "bold"), padx=7, pady=3).pack(side="left", padx=(0, 10))

        pid = producto.id
        botones = tk.Frame(fila, bg=ui.SURFACE_2)
        botones.pack(side="right")

        boton_subir = ttk.Button(botones, text="▲", width=3, command=lambda: self._mover_producto(pid, -1))
        boton_subir.pack(side="left", padx=1)
        if es_primero or not permitir_reordenar:
            boton_subir.state(["disabled"])
        boton_bajar = ttk.Button(botones, text="▼", width=3, command=lambda: self._mover_producto(pid, 1))
        boton_bajar.pack(side="left", padx=1)
        if es_ultimo or not permitir_reordenar:
            boton_bajar.state(["disabled"])

        ttk.Button(botones, text="✎", width=3,
                   command=lambda: self._abrir_edicion_producto(pid)).pack(side="left", padx=1)
        ttk.Button(botones, text="📦+", width=4,
                   command=lambda: self._abrir_reposicion_stock(pid)).pack(side="left", padx=1)
        ttk.Button(botones, text="⏻", width=3,
                   command=lambda: self._cambiar_estado_producto(pid)).pack(side="left", padx=1)
        ttk.Button(botones, text="🗑", width=3, style="Peligro.TButton",
                   command=lambda: self._eliminar_producto(pid)).pack(side="left", padx=1)

        return fila

    def _mover_producto(self, producto_id, delta):
        self.servicio_productos.mover_orden(producto_id, delta)
        self.renderizar_todo()

    def _abrir_creacion_producto(self):
        ventana = tk.Toplevel(self.raiz)
        ventana.title("Añadir producto")
        ventana.configure(bg=ui.SURFACE, padx=20, pady=16)
        ventana.transient(self.raiz)

        ttk.Label(ventana, text="Nombre", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_nombre = ttk.Entry(ventana, width=30)
        entrada_nombre.pack(fill="x", pady=(2, 10))

        ttk.Label(ventana, text="Categoria", style="Etiqueta.TLabel").pack(anchor="w")
        categorias = self.servicio_productos.categorias() or list(ui.CATEGORIA_COLOR.keys())
        combo_categoria = ttk.Combobox(ventana, values=categorias)
        combo_categoria.set(categorias[0] if categorias else "")
        combo_categoria.pack(fill="x", pady=(2, 10))

        ttk.Label(ventana, text="Precio", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_precio = ui.EntradaDinero(ventana, 0)
        entrada_precio.pack(fill="x", pady=(2, 10))

        ttk.Label(ventana, text="Costo", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_costo = ui.EntradaDinero(ventana, 0)
        entrada_costo.pack(fill="x", pady=(2, 10))

        ttk.Label(ventana, text="Stock inicial", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_stock = ui.EntradaDinero(ventana, 0)
        entrada_stock.pack(fill="x", pady=(2, 10))

        ttk.Label(ventana, text="Imagen", style="Etiqueta.TLabel").pack(anchor="w")
        fila_imagen = ttk.Frame(ventana)
        fila_imagen.pack(fill="x", pady=(2, 16))
        imagen_elegida = {"ruta": None}
        etiqueta_preview = tk.Label(fila_imagen, bg=ui.SURFACE_2, fg=ui.TEXT_FAINT,
                                     text="Sin imagen", width=10, anchor="center")
        etiqueta_preview.pack(side="left", padx=(0, 10))

        def elegir_imagen():
            ruta = filedialog.askopenfilename(
                title="Elegir imagen del producto",
                filetypes=[("Imagenes", "*.png *.jpg *.jpeg *.gif *.webp *.bmp")])
            if not ruta:
                return
            imagen_elegida["ruta"] = ruta
            miniatura = ui.cargar_miniatura_archivo(ruta, (40, 40))
            if miniatura:
                etiqueta_preview.configure(image=miniatura, text="")
                etiqueta_preview.image = miniatura

        ttk.Button(fila_imagen, text="Elegir imagen...", command=elegir_imagen).pack(side="left")

        def crear():
            nombre = entrada_nombre.get().strip()
            if not nombre:
                ui.mostrar_error(self.raiz, "Escribe un nombre de producto.")
                return
            producto = self.servicio_productos.crear(
                nombre, combo_categoria.get() or "Otros", entrada_precio.obtener(),
                stock=entrada_stock.obtener(), costo=entrada_costo.obtener())
            if imagen_elegida["ruta"]:
                self.servicio_productos.establecer_imagen(producto.id, Path(imagen_elegida["ruta"]))
            ventana.destroy()
            self.renderizar_todo()

        ttk.Button(ventana, text="Crear producto", style="Accent.TButton", command=crear).pack(fill="x")
        ventana.grab_set()

    def _abrir_edicion_producto(self, producto_id):
        try:
            producto = self.servicio_productos.obtener(producto_id)
        except ErrorDeNegocio:
            return

        ventana = tk.Toplevel(self.raiz)
        ventana.title("Editar producto")
        ventana.configure(bg=ui.SURFACE, padx=20, pady=16)
        ventana.transient(self.raiz)

        ttk.Label(ventana, text="Nombre", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_nombre = ttk.Entry(ventana, width=30)
        entrada_nombre.insert(0, producto.nombre)
        entrada_nombre.pack(fill="x", pady=(2, 10))

        ttk.Label(ventana, text="Categoria", style="Etiqueta.TLabel").pack(anchor="w")
        combo_categoria = ttk.Combobox(ventana, values=self.servicio_productos.categorias())
        combo_categoria.set(producto.categoria)
        combo_categoria.pack(fill="x", pady=(2, 10))

        ttk.Label(ventana, text="Precio", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_precio = ui.EntradaDinero(ventana, producto.precio)
        entrada_precio.pack(fill="x", pady=(2, 10))

        ttk.Label(ventana, text="Costo", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_costo = ui.EntradaDinero(ventana, producto.costo)
        entrada_costo.pack(fill="x", pady=(2, 10))

        fila_stock = ttk.Frame(ventana)
        fila_stock.pack(fill="x", pady=(2, 10))
        columna_stock = ttk.Frame(fila_stock)
        columna_stock.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Label(columna_stock, text="Stock", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_stock = ui.EntradaDinero(columna_stock, producto.stock)
        entrada_stock.pack(fill="x")
        columna_minimo = ttk.Frame(fila_stock)
        columna_minimo.pack(side="left", fill="x", expand=True, padx=(6, 0))
        ttk.Label(columna_minimo, text="Stock minimo", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_stock_minimo = ui.EntradaDinero(columna_minimo, producto.stock_minimo)
        entrada_stock_minimo.pack(fill="x")

        ttk.Label(ventana, text="Imagen", style="Etiqueta.TLabel").pack(anchor="w")
        fila_imagen = ttk.Frame(ventana)
        fila_imagen.pack(fill="x", pady=(2, 16))
        imagen_elegida = {"ruta": None, "quitar": False}
        miniatura_actual = ui.cargar_miniatura(producto.imagen_archivo, (40, 40))
        etiqueta_preview = tk.Label(fila_imagen, bg=ui.SURFACE_2, fg=ui.TEXT_FAINT, anchor="center")
        if miniatura_actual:
            etiqueta_preview.configure(image=miniatura_actual)
            etiqueta_preview.image = miniatura_actual
        else:
            etiqueta_preview.configure(text="Sin imagen", width=10)
        etiqueta_preview.pack(side="left", padx=(0, 10))

        def cambiar_imagen():
            ruta = filedialog.askopenfilename(
                title="Elegir imagen del producto",
                filetypes=[("Imagenes", "*.png *.jpg *.jpeg *.gif *.webp *.bmp")])
            if not ruta:
                return
            imagen_elegida["ruta"] = ruta
            imagen_elegida["quitar"] = False
            miniatura = ui.cargar_miniatura_archivo(ruta, (40, 40))
            if miniatura:
                etiqueta_preview.configure(image=miniatura, text="")
                etiqueta_preview.image = miniatura

        def quitar_imagen():
            imagen_elegida["ruta"] = None
            imagen_elegida["quitar"] = True
            etiqueta_preview.configure(image="", text="Sin imagen")
            etiqueta_preview.image = None

        ttk.Button(fila_imagen, text="Cambiar imagen", command=cambiar_imagen).pack(side="left")
        ttk.Button(fila_imagen, text="Quitar", command=quitar_imagen).pack(side="left", padx=(6, 0))

        def guardar():
            self.servicio_productos.actualizar(
                producto.id, entrada_nombre.get(), combo_categoria.get(), entrada_precio.obtener(),
                stock=entrada_stock.obtener(), stock_minimo=entrada_stock_minimo.obtener(),
                costo=entrada_costo.obtener())
            if imagen_elegida["ruta"]:
                self.servicio_productos.establecer_imagen(producto.id, Path(imagen_elegida["ruta"]))
                ui.invalidar_miniatura(producto.imagen_archivo)
            elif imagen_elegida["quitar"]:
                self.servicio_productos.quitar_imagen(producto.id)
                ui.invalidar_miniatura(producto.imagen_archivo)
            ventana.destroy()
            self.renderizar_todo()

        ttk.Button(ventana, text="Guardar cambios", style="Accent.TButton", command=guardar).pack(fill="x")
        ventana.grab_set()

    def _abrir_reposicion_stock(self, producto_id):
        try:
            producto = self.servicio_productos.obtener(producto_id)
        except ErrorDeNegocio:
            return

        ventana = tk.Toplevel(self.raiz)
        ventana.title("Reponer stock")
        ventana.configure(bg=ui.SURFACE, padx=20, pady=16)
        ventana.transient(self.raiz)
        ventana.resizable(False, False)

        ttk.Label(ventana, text=producto.nombre, style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(ventana, text=f"Stock actual: {producto.stock}", style="Sutil.TLabel").pack(
            anchor="w", pady=(0, 14))

        ttk.Label(ventana, text="UNIDADES POR PACA", style="Etiqueta.TLabel").pack(anchor="w")
        fila_paca = ttk.Frame(ventana)
        fila_paca.pack(fill="x", pady=(4, 14))
        ttk.Button(fila_paca, text="−", width=3,
                   command=lambda: ajustar_unidades_paca(-1)).pack(side="left")
        entrada_unidades_paca = ui.EntradaDinero(fila_paca, producto.unidades_por_paca or 1, width=8)
        entrada_unidades_paca.pack(side="left", padx=6)
        ttk.Button(fila_paca, text="+", width=3,
                   command=lambda: ajustar_unidades_paca(1)).pack(side="left")
        ttk.Label(fila_paca, text="unidades trae cada paca de este producto", style="Sutil.TLabel").pack(
            side="left", padx=(8, 0))

        ttk.Label(ventana, text="CANTIDAD DE PACAS QUE ENTRARON", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_pacas = ui.EntradaDinero(ventana, producto.ultima_cantidad_pacas or 1)
        entrada_pacas.pack(fill="x", pady=(4, 10))

        etiqueta_total = tk.Label(ventana, bg=ui.SURFACE_2, fg=ui.TEXT, font=("Segoe UI", 10),
                                    anchor="w", padx=10, pady=6)
        etiqueta_total.pack(fill="x", pady=(0, 16))

        def refrescar_total(*_):
            total = entrada_pacas.obtener() * max(1, entrada_unidades_paca.obtener())
            etiqueta_total.configure(text=f"Total a agregar: {total} unidades", fg=ui.SUCCESS)

        def ajustar_unidades_paca(delta):
            entrada_unidades_paca.establecer(max(1, entrada_unidades_paca.obtener() + delta))
            refrescar_total()

        entrada_pacas.bind("<KeyRelease>", refrescar_total)
        entrada_unidades_paca.bind("<KeyRelease>", refrescar_total)
        refrescar_total()

        def agregar_stock():
            pacas = entrada_pacas.obtener()
            if pacas <= 0:
                ui.mostrar_error(self.raiz, "Ingresa al menos una paca.")
                return
            self.servicio_productos.reponer_por_paca(
                producto.id, entrada_unidades_paca.obtener(), pacas)
            ventana.destroy()
            self.renderizar_todo()

        ttk.Button(ventana, text="Agregar al stock", style="Accent.TButton",
                   command=agregar_stock).pack(fill="x")
        ventana.grab_set()

    def _abrir_reposicion_masiva(self):
        """Grilla estilo hoja de calculo: unidades por paca + pacas para TODOS los productos a la vez."""
        productos = sorted((p for p in self.servicio_productos.listar() if p.activo),
                            key=lambda p: p.nombre)
        if not productos:
            ui.avisar(self.raiz, "No hay productos activos para reponer.")
            return

        ventana = tk.Toplevel(self.raiz)
        ventana.title("Reposicion masiva de stock")
        ventana.configure(bg=ui.SURFACE)
        ventana.geometry("820x640")
        ventana.minsize(700, 400)
        ventana.transient(self.raiz)

        ttk.Label(ventana, text="Reposicion masiva de stock", style="Titulo.TLabel").pack(
            anchor="w", padx=16, pady=(14, 0))
        ttk.Label(ventana, wraplength=880, style="Sutil.TLabel", text=(
            "Completa unidades por paca y cuantas pacas entraron por producto. Deja en 0 las pacas "
            "de los productos que no repones hoy.")).pack(anchor="w", padx=16, pady=(2, 10))

        marco = MarcoDesplazable(ventana)
        marco.pack(fill="both", expand=True, padx=16, pady=(0, 8))
        tabla = marco.interior

        for col, texto in enumerate(("Producto", "Stock actual", "Unidades x paca",
                                      "Pacas a agregar", "Total a agregar")):
            celda = tk.Frame(tabla, bg=ui.SURFACE_3, highlightthickness=1, highlightbackground=ui.BORDER)
            celda.grid(row=0, column=col, sticky="nsew")
            tk.Label(celda, text=texto, bg=ui.SURFACE_3, fg=ui.EMERALD,
                      font=("Segoe UI Semibold", 9), padx=8, pady=6).pack(anchor="w")

        filas_estado = []
        for i, producto in enumerate(productos, start=1):
            bg_fila = ui.SURFACE_2 if i % 2 == 0 else ui.SURFACE

            celda_nombre = tk.Frame(tabla, bg=bg_fila, highlightthickness=1, highlightbackground=ui.BORDER)
            celda_nombre.grid(row=i, column=0, sticky="nsew")
            tk.Label(celda_nombre, text=producto.nombre, bg=bg_fila, fg=ui.TEXT, font=("Segoe UI", 9),
                      padx=8, pady=5, anchor="w").pack(fill="x")

            celda_stock = tk.Frame(tabla, bg=bg_fila, highlightthickness=1, highlightbackground=ui.BORDER)
            celda_stock.grid(row=i, column=1, sticky="nsew")
            tk.Label(celda_stock, text=str(producto.stock), bg=bg_fila, fg=ui.TEXT_DIM,
                      font=ui.FUENTE_MONO).pack(pady=5)

            celda_unidades = tk.Frame(tabla, bg=bg_fila, highlightthickness=1, highlightbackground=ui.BORDER)
            celda_unidades.grid(row=i, column=2, sticky="nsew")
            entrada_unidades = ui.EntradaDinero(celda_unidades, producto.unidades_por_paca or 1, width=8)
            entrada_unidades.pack(padx=6, pady=4)

            celda_pacas = tk.Frame(tabla, bg=bg_fila, highlightthickness=1, highlightbackground=ui.BORDER)
            celda_pacas.grid(row=i, column=3, sticky="nsew")
            entrada_pacas = ui.EntradaDinero(celda_pacas, 0, width=8)
            entrada_pacas.pack(padx=6, pady=4)

            celda_total = tk.Frame(tabla, bg=bg_fila, highlightthickness=1, highlightbackground=ui.BORDER)
            celda_total.grid(row=i, column=4, sticky="nsew")
            etiqueta_total = tk.Label(celda_total, text="0 u", bg=bg_fila, fg=ui.TEXT_FAINT,
                                        font=ui.FUENTE_MONO)
            etiqueta_total.pack(pady=5)

            def refrescar_total(_e=None, eu=entrada_unidades, ep=entrada_pacas, et=etiqueta_total):
                total = max(0, eu.obtener()) * max(0, ep.obtener())
                et.configure(text=f"{total} u", fg=ui.SUCCESS if total else ui.TEXT_FAINT)

            entrada_unidades.bind("<KeyRelease>", refrescar_total)
            entrada_pacas.bind("<KeyRelease>", refrescar_total)
            filas_estado.append((producto, entrada_unidades, entrada_pacas))

        pie = ttk.Frame(ventana)
        pie.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Button(pie, text="Cancelar", command=ventana.destroy).pack(
            side="left", fill="x", expand=True, padx=(0, 6))

        def aplicar():
            aplicados = 0
            for producto, entrada_unidades, entrada_pacas in filas_estado:
                pacas = entrada_pacas.obtener()
                if pacas <= 0:
                    continue
                unidades = max(1, entrada_unidades.obtener())
                self.servicio_productos.reponer_por_paca(producto.id, unidades, pacas)
                aplicados += 1
            ventana.destroy()
            if aplicados:
                ui.avisar(self.raiz, f"Stock repuesto en {aplicados} producto(s).")
            self.renderizar_todo()

        ttk.Button(pie, text="Aplicar reposicion", style="Accent.TButton",
                   command=aplicar).pack(side="left", fill="x", expand=True, padx=(6, 0))
        ventana.grab_set()

    def _cambiar_estado_producto(self, producto_id):
        self.servicio_productos.cambiar_estado(producto_id)
        self.renderizar_todo()

    def _eliminar_producto(self, producto_id):
        try:
            producto = self.servicio_productos.obtener(producto_id)
        except ErrorDeNegocio:
            return
        if ui.confirmar(self.raiz, "Eliminar producto", f'¿Eliminar "{producto.nombre}"?'):
            self.servicio_productos.eliminar(producto_id)
            self.renderizar_todo()

    # ============================================================ HISTORIAL
    def _renderizar_historial(self):
        self._limpiar(self.tab_historial)
        ttk.Label(self.tab_historial, text="Historial de ventas", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(self.tab_historial, text="Resumen y detalle de las ventas registradas.",
                   style="Sutil.TLabel").pack(anchor="w", pady=(0, 12))

        filtros = ttk.Frame(self.tab_historial)
        filtros.pack(fill="x", pady=(0, 12))
        for clave, etiqueta in (("hoy", "Hoy"), ("todo", "Todo el historial")):
            estilo = "Accent.TButton" if self.filtro_historial == clave else "TButton"
            ttk.Button(filtros, text=etiqueta, style=estilo,
                       command=lambda c=clave: self._elegir_filtro_historial(c)).pack(side="left", padx=(0, 8))

        ventas = self.servicio_ventas.listar(solo_hoy=(self.filtro_historial == "hoy"))
        ventas.sort(key=lambda v: v.timestamp, reverse=True)
        validas = [v for v in ventas if not v.anulada]
        total_vendido = sum(v.total for v in validas)
        dia_filtro = datetime.date.today() if self.filtro_historial == "hoy" else None
        por_metodo = self.servicio_analisis.ventas_por_metodo_pago(desde=dia_filtro, hasta=dia_filtro)
        gasto_dmt = self.servicio_analisis.total_gastado_dmt(desde=dia_filtro, hasta=dia_filtro)

        tarjetas = ttk.Frame(self.tab_historial)
        tarjetas.pack(fill="x", pady=(0, 14))
        datos_tarjetas = [
            ("Total vendido", f"$ {ui.formato_cop(total_vendido)}"),
            ("N° de ventas", str(len(validas))),
            ("Efectivo", f"$ {ui.formato_cop(por_metodo['Efectivo'])}"),
            ("QR", f"$ {ui.formato_cop(por_metodo['QR'])}"),
            ("Gastado en DMT", f"$ {ui.formato_cop(gasto_dmt)}"),
        ]
        for etiqueta, valor in datos_tarjetas:
            caja = tk.Frame(tarjetas, bg=ui.SURFACE_2, padx=14, pady=10, highlightthickness=1,
                             highlightbackground=ui.BORDER)
            caja.pack(side="left", fill="x", expand=True, padx=4)
            tk.Label(caja, text=etiqueta.upper(), bg=ui.SURFACE_2, fg=ui.EMERALD,
                      font=("Segoe UI Semibold", 8)).pack(anchor="w")
            tk.Label(caja, text=valor, bg=ui.SURFACE_2, fg=ui.TEXT, font=("Consolas", 14, "bold")).pack(anchor="w")

        columnas = ("hora", "resumen", "metodo", "total", "estado")
        arbol = ttk.Treeview(self.tab_historial, columns=columnas, show="headings", height=14)
        for clave, texto, ancho in (("hora", "Hora", 70), ("resumen", "Productos", 340),
                                     ("metodo", "Metodo", 110), ("total", "Total", 110), ("estado", "Estado", 90)):
            arbol.heading(clave, text=texto)
            arbol.column(clave, width=ancho, anchor="w" if clave == "resumen" else "center")
        for venta in ventas:
            resumen = ", ".join(f"{it.cantidad}x {it.nombre}" for it in venta.items)
            hora = datetime.datetime.fromtimestamp(venta.timestamp).strftime("%H:%M")
            arbol.insert("", "end", iid=venta.id, values=(
                hora, resumen, venta.metodo_pago, f"$ {ui.formato_cop(venta.total)}",
                "Anulada" if venta.anulada else "OK"))
        arbol.pack(fill="both", expand=True)
        arbol.bind("<Double-1>", lambda e: self._abrir_detalle_venta(arbol, ventas))

    def _elegir_filtro_historial(self, clave):
        self.filtro_historial = clave
        self.renderizar_todo()

    def _abrir_detalle_venta(self, arbol, ventas):
        seleccion = arbol.selection()
        if not seleccion:
            return
        venta = next((v for v in ventas if v.id == seleccion[0]), None)
        if not venta:
            return

        ventana = tk.Toplevel(self.raiz)
        ventana.title("Detalle de venta")
        ventana.configure(bg=ui.SURFACE, padx=20, pady=16)
        ventana.transient(self.raiz)

        marca_tiempo = datetime.datetime.fromtimestamp(venta.timestamp).strftime("%d/%m/%Y %H:%M")
        tk.Label(ventana, text=marca_tiempo, bg=ui.SURFACE, fg=ui.TEXT_FAINT).pack(anchor="w", pady=(0, 8))
        for it in venta.items:
            fila = tk.Frame(ventana, bg=ui.SURFACE)
            fila.pack(fill="x")
            tk.Label(fila, text=f"{it.cantidad}x {it.nombre}", bg=ui.SURFACE, fg=ui.TEXT_DIM,
                      font=ui.FUENTE_MONO).pack(side="left")
            tk.Label(fila, text=f"$ {ui.formato_cop(it.subtotal)}", bg=ui.SURFACE, fg=ui.TEXT_DIM,
                      font=ui.FUENTE_MONO).pack(side="right")
        tk.Frame(ventana, bg=ui.BORDER, height=1).pack(fill="x", pady=10)
        fila_total = tk.Frame(ventana, bg=ui.SURFACE)
        fila_total.pack(fill="x", pady=(0, 14))
        tk.Label(fila_total, text="Total", bg=ui.SURFACE, fg=ui.TEXT, font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(fila_total, text=f"$ {ui.formato_cop(venta.total)}", bg=ui.SURFACE, fg=ui.TEXT,
                  font=("Consolas", 14, "bold")).pack(side="right")

        if venta.anulada:
            tk.Label(ventana, text="VENTA ANULADA", bg=ui.DANGER, fg="#fff",
                      font=("Segoe UI", 9, "bold"), pady=6).pack(fill="x", pady=(0, 10))
        else:
            def anular():
                if ui.confirmar(self.raiz, "Anular venta", "¿Anular esta venta? Se descuenta de los totales."):
                    self.servicio_ventas.anular(venta.id)
                    ventana.destroy()
                    self.renderizar_todo()
            ttk.Button(ventana, text="Anular venta", style="Peligro.TButton", command=anular).pack(fill="x", pady=(0, 8))

        def eliminar():
            if ui.confirmar(self.raiz, "Eliminar venta",
                             "Esto borra la venta del historial de forma permanente. No se puede "
                             "deshacer. ¿Continuar?"):
                self.servicio_ventas.eliminar(venta.id)
                ventana.destroy()
                self.renderizar_todo()
        ttk.Button(ventana, text="Eliminar venta", style="Peligro.TButton", command=eliminar).pack(
            fill="x", pady=(0, 8))

        ttk.Button(ventana, text="Cerrar", command=ventana.destroy).pack(fill="x")
        ventana.grab_set()

    # ============================================================ ANALISIS
    def _elegir_rango_analisis(self, rango):
        self.rango_analisis = rango
        self.renderizar_todo()

    def _rango_fechas_analisis(self):
        hoy = datetime.date.today()
        if self.rango_analisis == "7d":
            return hoy - datetime.timedelta(days=6), hoy
        if self.rango_analisis == "30d":
            return hoy - datetime.timedelta(days=29), hoy
        return None, None

    def _etiqueta_turno(self, sesion):
        fecha = datetime.datetime.fromtimestamp(sesion.abierta_en).strftime("%d/%m %H:%M")
        estado = " (abierto)" if sesion.cerrada_en is None else ""
        return f"{fecha} · {sesion.cajero}{estado}"

    def _elegir_turno_analisis(self, evento=None):
        etiqueta = self._combo_turno.get()
        self.turno_analisis = self._mapa_turnos.get(etiqueta, "todos")
        self.renderizar_todo()

    def _elegir_turno_abierto(self):
        sesion = self.servicio_caja.sesion_actual()
        if not sesion:
            ui.avisar(self.raiz, "No hay ningun turno abierto en este momento.")
            return
        self.turno_analisis = sesion.id
        self.rango_analisis = "todo"
        self.renderizar_todo()

    def _alternar_ayuda_stats(self):
        self.mostrar_ayuda_stats = not self.mostrar_ayuda_stats
        self.renderizar_todo()

    def _fila_ayuda_stat(self, maestro, termino, explicacion):
        fila = tk.Frame(maestro, bg=ui.SURFACE_2, padx=10, pady=8)
        fila.pack(fill="x", pady=2)
        tk.Label(fila, text=termino, bg=ui.SURFACE_2, fg=ui.ACCENT,
                  font=("Segoe UI Semibold", 9), anchor="w").pack(anchor="w")
        tk.Label(fila, text=explicacion, bg=ui.SURFACE_2, fg=ui.TEXT_DIM, font=("Segoe UI", 9),
                  anchor="w", justify="left", wraplength=340).pack(anchor="w", pady=(2, 0))

    def _tarjeta_kpi(self, maestro, etiqueta, valor, fila, columna):
        caja = tk.Frame(maestro, bg=ui.SURFACE_2, padx=14, pady=10, highlightthickness=1,
                         highlightbackground=ui.BORDER)
        caja.grid(row=fila, column=columna, sticky="nsew", padx=4, pady=4)
        tk.Label(caja, text=etiqueta.upper(), bg=ui.SURFACE_2, fg=ui.EMERALD,
                  font=("Segoe UI Semibold", 8)).pack(anchor="w")
        tk.Label(caja, text=valor, bg=ui.SURFACE_2, fg=ui.TEXT, font=("Consolas", 14, "bold")).pack(anchor="w")

    def _panel_grafico(self, maestro, fila, columna, titulo):
        panel = tk.Frame(maestro, bg=ui.SURFACE, padx=12, pady=12, highlightthickness=1,
                          highlightbackground=ui.BORDER)
        panel.grid(row=fila, column=columna, sticky="nsew", padx=6, pady=6)
        ttk.Label(panel, text=titulo, style="Etiqueta.TLabel").pack(anchor="w", pady=(0, 8))
        return panel

    def _renderizar_analisis(self):
        self._limpiar(self.tab_analisis)
        ttk.Label(self.tab_analisis, text="Analisis", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(self.tab_analisis, text="Rendimiento de ventas, productos e inventario.",
                   style="Sutil.TLabel").pack(anchor="w", pady=(0, 12))

        # -------- fila de filtros: rango de fechas + turno --------
        filtros = ttk.Frame(self.tab_analisis)
        filtros.pack(fill="x", pady=(0, 12))

        filtros_fecha = ttk.Frame(filtros)
        filtros_fecha.pack(side="left")
        sesion_abierta = self.servicio_caja.sesion_actual()
        estilo_turno_abierto = ("Accent.TButton"
                                 if sesion_abierta and self.turno_analisis == sesion_abierta.id
                                 else "TButton")
        ttk.Button(filtros_fecha, text="Turno abierto", style=estilo_turno_abierto,
                   command=self._elegir_turno_abierto).pack(side="left", padx=(0, 8))
        for clave, etiqueta in (("7d", "7 dias"), ("30d", "30 dias"), ("todo", "Todo")):
            estilo = "Accent.TButton" if self.rango_analisis == clave else "TButton"
            ttk.Button(filtros_fecha, text=etiqueta, style=estilo,
                       command=lambda c=clave: self._elegir_rango_analisis(c)).pack(side="left", padx=(0, 8))

        filtro_turno = ttk.Frame(filtros)
        filtro_turno.pack(side="left", padx=(20, 0))
        ttk.Label(filtro_turno, text="Turno:", style="Etiqueta.TLabel").pack(side="left", padx=(0, 6))
        turnos = self.servicio_analisis.turnos()
        self._mapa_turnos = {self._etiqueta_turno(s): s.id for s in turnos}
        valores_turno = ["Todos los turnos"] + list(self._mapa_turnos.keys())
        self._combo_turno = ttk.Combobox(filtro_turno, values=valores_turno, state="readonly", width=32)
        etiqueta_actual = next((et for et, sid in self._mapa_turnos.items() if sid == self.turno_analisis), None)
        self._combo_turno.set(etiqueta_actual or "Todos los turnos")
        self._combo_turno.pack(side="left")
        self._combo_turno.bind("<<ComboboxSelected>>", self._elegir_turno_analisis)

        sesion_id = self.turno_analisis if self.turno_analisis != "todos" else None
        desde, hasta = self._rango_fechas_analisis()
        resumen = self.servicio_analisis.resumen(desde, hasta, sesion_id)
        stats = self.servicio_analisis.estadisticas(desde, hasta, sesion_id)

        contenedor = MarcoDesplazable(self.tab_analisis)
        contenedor.pack(fill="both", expand=True)
        raiz = contenedor.interior

        # -------- grid de KPIs (3 columnas x 2 filas) --------
        grilla_kpi = tk.Frame(raiz, bg=ui.SURFACE)
        grilla_kpi.pack(fill="x", pady=(0, 8))
        for col in range(3):
            grilla_kpi.columnconfigure(col, weight=1, uniform="kpi")
        datos_kpi = [
            ("Total vendido", f"$ {ui.formato_cop(resumen['total_vendido'])}"),
            ("N° de ventas", str(resumen["n_ventas"])),
            ("Unidades vendidas", str(resumen["unidades"])),
            ("Ticket promedio", f"$ {ui.formato_cop(stats['media'])}"),
            ("Desviacion estandar", f"$ {ui.formato_cop(stats['desviacion'])}"),
            ("Utilidad estimada", f"$ {ui.formato_cop(resumen['utilidad'])}"),
            ("Gastado en DMT (costo)", f"$ {ui.formato_cop(resumen['gasto_dmt'])}"),
        ]
        for i, (etiqueta, valor) in enumerate(datos_kpi):
            self._tarjeta_kpi(grilla_kpi, etiqueta, valor, fila=i // 3, columna=i % 3)

        # -------- grid principal de graficos (2 columnas x 2 filas) --------
        grilla_graficos = tk.Frame(raiz, bg=ui.SURFACE)
        grilla_graficos.pack(fill="both", expand=True, pady=(10, 0))
        grilla_graficos.columnconfigure(0, weight=1, uniform="graf")
        grilla_graficos.columnconfigure(1, weight=1, uniform="graf")

        panel_top = self._panel_grafico(grilla_graficos, 0, 0, "Top productos")
        top = self.servicio_analisis.top_productos(desde, hasta, n=10, sesion_id=sesion_id)
        gasto_por_producto = self.servicio_analisis.gasto_dmt_por_producto(desde, hasta, sesion_id=sesion_id)
        datos_top = [(f"{i + 1}. {fila['nombre']}", fila["cantidad"]) for i, fila in enumerate(top)]
        datos_dmt = [gasto_por_producto.get(fila["producto_id"], {}).get("cantidad", 0) for fila in top]
        if any(datos_dmt):
            leyenda = ttk.Frame(panel_top)
            leyenda.pack(fill="x", pady=(0, 4))
            tk.Frame(leyenda, bg=ui.ACCENT, width=10, height=10).pack(side="left", padx=(2, 4))
            ttk.Label(leyenda, text="Vendidos", style="Sutil.TLabel").pack(side="left", padx=(0, 12))
            tk.Frame(leyenda, bg=ui.WARNING, width=10, height=10).pack(side="left", padx=(2, 4))
            ttk.Label(leyenda, text="DMT (gasto)", style="Sutil.TLabel").pack(side="left")
        ui.GraficoBarras(panel_top, datos_top, formato=lambda v: f"{int(v)} u",
                          datos_extra=datos_dmt).pack(fill="x")

        panel_cat = self._panel_grafico(grilla_graficos, 0, 1, "Ventas por categoria")
        categorias = self.servicio_analisis.ventas_por_categoria(desde, hasta, sesion_id=sesion_id)
        datos_cat = [(fila["categoria"], fila["total"]) for fila in categorias]
        ui.GraficoCircular(panel_cat, datos_cat, formato=lambda v: f"$ {ui.formato_cop(v)}").pack(fill="x")

        panel_horas = self._panel_grafico(grilla_graficos, 1, 0, "Ventas por hora")
        horas = self.servicio_analisis.ventas_por_hora(desde, hasta, sesion_id=sesion_id)
        datos_horas = [(f"{h:02d}:00", total) for h, total in enumerate(horas) if total > 0]
        ui.GraficoBarras(panel_horas, datos_horas, formato=lambda v: f"$ {ui.formato_cop(v)}",
                          color=ui.ACCENT_STRONG).pack(fill="x")

        panel_metodo = self._panel_grafico(grilla_graficos, 1, 1, "Ventas por metodo de pago")
        por_metodo = self.servicio_analisis.ventas_por_metodo_pago(desde, hasta, sesion_id=sesion_id)
        datos_metodo = [(metodo, total) for metodo, total in por_metodo.items()]
        ui.GraficoCircular(panel_metodo, datos_metodo, formato=lambda v: f"$ {ui.formato_cop(v)}").pack(fill="x")

        # -------- grid secundario: stock repuesto + estadisticas detalladas --------
        grilla_secundaria = tk.Frame(raiz, bg=ui.SURFACE)
        grilla_secundaria.pack(fill="both", expand=True, pady=(0, 0))
        grilla_secundaria.columnconfigure(0, weight=1, uniform="graf")
        grilla_secundaria.columnconfigure(1, weight=1, uniform="graf")

        panel_repuesto = self._panel_grafico(grilla_secundaria, 0, 0, "Stock repuesto por producto")
        repuesto = self.servicio_analisis.total_repuesto_por_producto(desde, hasta)
        datos_repuesto = [(fila["nombre"], fila["cantidad"]) for fila in repuesto]
        ui.GraficoBarras(panel_repuesto, datos_repuesto, formato=lambda v: f"{int(v)} u",
                          color=ui.WARNING).pack(fill="x")

        panel_stats = tk.Frame(grilla_secundaria, bg=ui.SURFACE, padx=12, pady=12, highlightthickness=1,
                                highlightbackground=ui.BORDER)
        panel_stats.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)
        encabezado_stats = tk.Frame(panel_stats, bg=ui.SURFACE)
        encabezado_stats.pack(fill="x", pady=(0, 8))
        ttk.Label(encabezado_stats, text="Estadisticas del ticket de venta", style="Etiqueta.TLabel").pack(
            side="left")
        ttk.Button(encabezado_stats, text="?", width=2,
                   command=self._alternar_ayuda_stats).pack(side="left", padx=(6, 0))

        if self.mostrar_ayuda_stats:
            caja_ayuda = tk.Frame(panel_stats, bg=ui.SURFACE_2, highlightthickness=1,
                                   highlightbackground=ui.BORDER)
            caja_ayuda.pack(fill="x", pady=(0, 10))
            self._fila_ayuda_stat(caja_ayuda, "Media (promedio)",
                "Suma todas las ventas y reparte en partes iguales. Muestra cuanto habria gastado "
                "cada cliente si todos hubieran gastado lo mismo. Una venta muy grande puede inflarla.")
            self._fila_ayuda_stat(caja_ayuda, "Mediana",
                "El ticket \"de la mitad\": la mitad de los clientes gasto menos que eso, la otra "
                "mitad gasto mas. Mas real que el promedio cuando hay una venta muy grande o muy chica.")
            self._fila_ayuda_stat(caja_ayuda, "Desviacion estandar",
                "Que tan parejo o disparejo gasta la gente. Numero bajo = casi todos gastan parecido. "
                "Numero alto = hay de todo, ventas chicas y grandes mezcladas, mas impredecible.")

        filas_stats = [
            ("Media (promedio)", f"$ {ui.formato_cop(stats['media'])}"),
            ("Mediana", f"$ {ui.formato_cop(stats['mediana'])}"),
            ("Desviacion estandar", f"$ {ui.formato_cop(stats['desviacion'])}"),
            ("Minimo", f"$ {ui.formato_cop(stats['minimo'])}"),
            ("Maximo", f"$ {ui.formato_cop(stats['maximo'])}"),
            ("N° de tickets", str(stats["n"])),
        ]
        if stats["n"] == 0:
            ttk.Label(panel_stats, text="Sin ventas en este rango.", style="Sutil.TLabel").pack(anchor="w")
        else:
            for etiqueta, valor in filas_stats:
                fila_stat = tk.Frame(panel_stats, bg=ui.SURFACE_2, padx=10, pady=6, highlightthickness=1,
                                      highlightbackground=ui.BORDER)
                fila_stat.pack(fill="x", pady=2)
                tk.Label(fila_stat, text=etiqueta, bg=ui.SURFACE_2, fg=ui.TEXT_DIM,
                          font=("Segoe UI", 9)).pack(side="left")
                tk.Label(fila_stat, text=valor, bg=ui.SURFACE_2, fg=ui.TEXT,
                          font=ui.FUENTE_MONO).pack(side="right")

        # -------- grid inferior: alertas de stock + ultimas reposiciones --------
        grilla_inferior = tk.Frame(raiz, bg=ui.SURFACE)
        grilla_inferior.pack(fill="both", expand=True)
        grilla_inferior.columnconfigure(0, weight=1, uniform="graf")
        grilla_inferior.columnconfigure(1, weight=1, uniform="graf")

        panel_alertas = self._panel_grafico(grilla_inferior, 0, 0, "Alertas de stock bajo")
        bajos = self.servicio_analisis.productos_stock_bajo()
        if not bajos:
            ttk.Label(panel_alertas, text="Todo el inventario esta en buen nivel.",
                       style="Sutil.TLabel").pack(anchor="w")
        else:
            for producto in bajos:
                color = ui.DANGER if producto.stock <= 0 else ui.WARNING
                fila_stock = tk.Frame(panel_alertas, bg=ui.SURFACE_2, padx=10, pady=6, highlightthickness=1,
                                       highlightbackground=ui.BORDER)
                fila_stock.pack(fill="x", pady=2)
                tk.Label(fila_stock, text=producto.nombre, bg=ui.SURFACE_2, fg=ui.TEXT,
                          font=("Segoe UI", 9)).pack(side="left")
                tk.Label(fila_stock, text=f"Stock: {producto.stock}", bg=ui.SURFACE_2, fg=color,
                          font=("Segoe UI Semibold", 9)).pack(side="right")

        panel_reposiciones = self._panel_grafico(grilla_inferior, 0, 1, "Ultimas reposiciones")
        movimientos = self.servicio_analisis.reposiciones_stock(desde, hasta)[:8]
        if not movimientos:
            ttk.Label(panel_reposiciones, text="No se registraron reposiciones en este rango.",
                       style="Sutil.TLabel").pack(anchor="w")
        else:
            for movimiento in movimientos:
                fecha = datetime.datetime.fromtimestamp(movimiento.timestamp).strftime("%d/%m %H:%M")
                fila_mov = tk.Frame(panel_reposiciones, bg=ui.SURFACE_2, padx=10, pady=6, highlightthickness=1,
                                     highlightbackground=ui.BORDER)
                fila_mov.pack(fill="x", pady=2)
                tk.Label(fila_mov, text=f"{fecha}  ·  {movimiento.nombre_producto}", bg=ui.SURFACE_2,
                          fg=ui.TEXT, font=("Segoe UI", 9)).pack(side="left")
                positivo = movimiento.cantidad >= 0
                texto_cantidad = f"+{movimiento.cantidad}" if positivo else str(movimiento.cantidad)
                tk.Label(fila_mov, text=texto_cantidad, bg=ui.SURFACE_2,
                          fg=ui.SEMAFORO_VERDE if positivo else ui.DANGER,
                          font=("Segoe UI Semibold", 9)).pack(side="right")

    # ============================================================ PRONOSTICO
    def _elegir_granularidad_pronostico(self, clave):
        self.granularidad_pronostico = clave
        self.horizonte_pronostico = {"dia": 30, "semana": 12, "mes": 3}[clave]
        self._renderizar_pronostico()

    def _renderizar_pronostico(self):
        self._limpiar(self.tab_pronostico)
        ttk.Label(self.tab_pronostico, text="Pronostico", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(self.tab_pronostico,
                   text="Stock recomendado para el proximo evento, margen por producto y proyeccion de ventas.",
                   style="Sutil.TLabel").pack(anchor="w", pady=(0, 12))

        contenedor = MarcoDesplazable(self.tab_pronostico)
        contenedor.pack(fill="both", expand=True)
        raiz = contenedor.interior

        # --- Stock recomendado para el proximo evento ---
        ttk.Label(raiz, text="Stock recomendado · proximo evento", style="Etiqueta.TLabel").pack(
            anchor="w", pady=(0, 6))
        recomendaciones = self.servicio_pronostico.pronostico_proximo_evento()
        columnas = ("producto", "stock", "recomendado", "pacas", "fuente")
        arbol = ttk.Treeview(raiz, columns=columnas, show="headings",
                              height=min(18, max(4, len(recomendaciones))))
        arbol.heading("producto", text="Producto"); arbol.column("producto", width=220)
        arbol.heading("stock", text="Stock actual"); arbol.column("stock", width=100, anchor="e")
        arbol.heading("recomendado", text="Recomendado (u)"); arbol.column("recomendado", width=130, anchor="e")
        arbol.heading("pacas", text="Pacas a pedir"); arbol.column("pacas", width=110, anchor="e")
        arbol.heading("fuente", text="Base del calculo"); arbol.column("fuente", width=200)
        for r in recomendaciones:
            fuente_txt = (f"Promedio de {r.eventos_considerados} evento(s)" if r.fuente == "historial"
                          else "Sin historial (ultima reposicion)")
            arbol.insert("", "end", values=(r.nombre, r.stock_actual, r.recomendado_unidades,
                                             r.recomendado_pacas, fuente_txt))
        arbol.pack(fill="x", pady=(0, 4))
        if recomendaciones and all(r.fuente == "sin_historial" for r in recomendaciones):
            ttk.Label(raiz, wraplength=760, style="Sutil.TLabel", text=(
                "Aun no hay ningun evento cerrado con ventas registradas: la recomendacion usa la "
                "ultima reposicion cargada por producto. En cuanto cierres el primer evento real con "
                "ventas, el calculo pasa a usar el consumo historico real."
            )).pack(anchor="w", pady=(4, 16))
        else:
            ttk.Frame(raiz).pack(pady=(0, 8))

        # --- Proyeccion de ventas ---
        ttk.Label(raiz, text="Proyeccion de ventas", style="Etiqueta.TLabel").pack(anchor="w", pady=(8, 6))
        filtros = ttk.Frame(raiz)
        filtros.pack(fill="x", pady=(0, 10))
        for clave, etiqueta in (("dia", "Diario"), ("semana", "Semanal"), ("mes", "Mensual")):
            estilo = "Accent.TButton" if self.granularidad_pronostico == clave else "TButton"
            ttk.Button(filtros, text=etiqueta, style=estilo,
                       command=lambda c=clave: self._elegir_granularidad_pronostico(c)).pack(side="left", padx=(0, 8))

        proyeccion = self.servicio_pronostico.proyeccion_ventas(self.granularidad_pronostico,
                                                                 self.horizonte_pronostico)
        if proyeccion.datos_insuficientes:
            ttk.Label(raiz, wraplength=760, style="Sutil.TLabel", text=(
                f"Datos insuficientes para proyectar ({proyeccion.periodos_disponibles} periodo(s) con ventas "
                "reales registradas). Hacen falta al menos 2 periodos con ventas para calcular una tendencia."
            )).pack(anchor="w", pady=(0, 16))
        else:
            ttk.Label(raiz, text="Historico:", style="Sutil.TLabel").pack(anchor="w")
            datos_hist = [(p.etiqueta, p.total) for p in proyeccion.historico[-12:]]
            ui.GraficoBarras(raiz, datos_hist, formato=lambda v: f"$ {ui.formato_cop(v)}").pack(
                fill="x", pady=(4, 10))
            ttk.Label(raiz, text=f"Proyectado ({proyeccion.horizonte} periodo(s) hacia adelante):",
                       style="Sutil.TLabel").pack(anchor="w")
            datos_proy = [(p.etiqueta, p.total) for p in proyeccion.proyectado]
            ui.GraficoBarras(raiz, datos_proy, formato=lambda v: f"$ {ui.formato_cop(v)}",
                              color=ui.WARNING).pack(fill="x", pady=(4, 16))

        # --- Margen por producto ---
        ttk.Label(raiz, text="Margen por producto", style="Etiqueta.TLabel").pack(anchor="w", pady=(8, 6))
        margenes = self.servicio_pronostico.margen_por_producto()
        if any(m["costo_sin_definir"] for m in margenes):
            ttk.Label(raiz, wraplength=760, style="Sutil.TLabel", text=(
                "Advertencia: hay productos sin costo cargado (costo = 0) -- su margen mostrado no es "
                "real hasta que definas el costo en la pestaña Productos."
            )).pack(anchor="w", pady=(0, 8))
        columnas_m = ("producto", "precio", "costo", "margen_pct")
        arbol_m = ttk.Treeview(raiz, columns=columnas_m, show="headings",
                                height=min(18, max(4, len(margenes))))
        arbol_m.heading("producto", text="Producto"); arbol_m.column("producto", width=220)
        arbol_m.heading("precio", text="Precio"); arbol_m.column("precio", width=120, anchor="e")
        arbol_m.heading("costo", text="Costo"); arbol_m.column("costo", width=120, anchor="e")
        arbol_m.heading("margen_pct", text="Margen %"); arbol_m.column("margen_pct", width=100, anchor="e")
        for m in margenes:
            arbol_m.insert("", "end", values=(m["nombre"], f"$ {ui.formato_cop(m['precio'])}",
                                               f"$ {ui.formato_cop(m['costo'])}", f"{m['margen_pct']:.0f}%"))
        arbol_m.pack(fill="x", pady=(0, 16))

    # ============================================================ CAJA
    def _renderizar_caja(self, sesion):
        self._limpiar(self.tab_caja)
        encabezado = ttk.Frame(self.tab_caja)
        encabezado.pack(fill="x")
        titulos = ttk.Frame(encabezado)
        titulos.pack(side="left", fill="x", expand=True)
        ttk.Label(titulos, text="Caja", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(titulos, text="Apertura, arqueo y cierre de turno.",
                   style="Sutil.TLabel").pack(anchor="w", pady=(0, 14))
        ttk.Button(encabezado, text="📊 Exportar historico + analisis + pronostico (Excel)",
                   style="Accent.TButton", command=self._exportar_reporte_historico).pack(
            side="right", anchor="n", pady=(2, 0))

        cuerpo = ttk.Frame(self.tab_caja)
        cuerpo.pack(fill="both", expand=True)
        cuerpo.columnconfigure(0, weight=1)
        cuerpo.columnconfigure(1, weight=1)

        panel_izq = tk.Frame(cuerpo, bg=ui.SURFACE, padx=18, pady=18, highlightthickness=1,
                              highlightbackground=ui.BORDER)
        panel_izq.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        if not sesion:
            tk.Label(panel_izq, text="Abrir caja", bg=ui.SURFACE, fg=ui.TEXT,
                      font=("Segoe UI Semibold", 13)).pack(anchor="w", pady=(0, 4))
            tk.Label(panel_izq, text="Registra el cajero y el efectivo inicial.", bg=ui.SURFACE,
                      fg=ui.TEXT_FAINT, font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 14))

            ttk.Label(panel_izq, text="CAJERO", style="Etiqueta.TLabel").pack(anchor="w")
            entrada_cajero = ttk.Entry(panel_izq)
            entrada_cajero.insert(0, "Cajero")
            entrada_cajero.pack(fill="x", pady=(4, 12))

            ttk.Label(panel_izq, text="EFECTIVO INICIAL", style="Etiqueta.TLabel").pack(anchor="w")
            entrada_inicial = ui.EntradaDinero(panel_izq, 0)
            entrada_inicial.pack(fill="x", pady=(4, 16))

            def abrir():
                self.servicio_caja.abrir_caja(entrada_cajero.get(), entrada_inicial.obtener())
                ui.avisar(self.raiz, "Caja abierta.")
                self.renderizar_todo()

            ttk.Button(panel_izq, text="Abrir caja", style="Accent.TButton", command=abrir).pack(fill="x", ipady=4)
        else:
            contenedor_izq = MarcoDesplazable(panel_izq)
            contenedor_izq.pack(fill="both", expand=True)
            panel_izq = contenedor_izq.interior

            totales = self.servicio_caja.calcular_totales(sesion)
            abierta_desde = datetime.datetime.fromtimestamp(sesion.abierta_en).strftime("%H:%M")
            datos = [
                ("Cajero", sesion.cajero), ("Abierta desde", abierta_desde),
                ("Efectivo inicial", f"$ {ui.formato_cop(sesion.efectivo_inicial)}"),
                ("Ventas del turno", str(totales.cantidad_ventas)),
                ("Total vendido", f"$ {ui.formato_cop(totales.total_ventas)}"),
                ("Gastado en DMT", f"$ {ui.formato_cop(totales.total_gastos_dmt)}"),
                ("Gastado en caja", f"$ {ui.formato_cop(totales.total_gastos_caja)}"),
                ("Efectivo esperado", f"$ {ui.formato_cop(totales.efectivo_esperado)}"),
            ]
            grilla = tk.Frame(panel_izq, bg=ui.SURFACE)
            grilla.pack(fill="x", pady=(0, 16))
            for i, (etiqueta, valor) in enumerate(datos):
                celda = tk.Frame(grilla, bg=ui.SURFACE_2, padx=12, pady=8, highlightthickness=1,
                                  highlightbackground=ui.BORDER)
                celda.grid(row=i // 2, column=i % 2, sticky="nsew", padx=4, pady=4)
                tk.Label(celda, text=etiqueta.upper(), bg=ui.SURFACE_2, fg=ui.EMERALD,
                          font=("Segoe UI Semibold", 8)).pack(anchor="w")
                tk.Label(celda, text=valor, bg=ui.SURFACE_2, fg=ui.TEXT, font=("Consolas", 12, "bold")).pack(anchor="w")
            grilla.columnconfigure(0, weight=1)
            grilla.columnconfigure(1, weight=1)

            ttk.Label(panel_izq, text="GASTOS DE CAJA DEL TURNO", style="Etiqueta.TLabel").pack(
                anchor="w", pady=(0, 6))
            gastos_caja = self.servicio_caja.listar_gastos_caja_sesion(sesion.id)
            if not gastos_caja:
                ttk.Label(panel_izq, text="Sin gastos registrados en este turno.",
                           style="Sutil.TLabel").pack(anchor="w", pady=(0, 10))
            else:
                for gasto in gastos_caja:
                    fila_gasto = tk.Frame(panel_izq, bg=ui.SURFACE_2, padx=8, pady=5,
                                           highlightthickness=1, highlightbackground=ui.BORDER)
                    fila_gasto.pack(fill="x", pady=2)
                    tk.Label(fila_gasto, text=gasto.concepto, bg=ui.SURFACE_2, fg=ui.TEXT,
                              font=("Segoe UI", 9)).pack(side="left")
                    ttk.Button(fila_gasto, text="🗑", width=3, style="Peligro.TButton",
                               command=lambda g=gasto: self._eliminar_gasto_caja(g)).pack(side="right")
                    tk.Label(fila_gasto, text=f"$ {ui.formato_cop(gasto.monto)}", bg=ui.SURFACE_2,
                              fg=ui.DANGER, font=ui.FUENTE_MONO).pack(side="right", padx=(0, 10))
                ttk.Frame(panel_izq).pack(pady=(0, 4))

            ttk.Button(panel_izq, text="➕ Añadir gasto", style="Accent.TButton",
                       command=lambda: self._abrir_registro_gasto_caja(sesion)).pack(
                fill="x", ipady=4, pady=(0, 8))

            ttk.Button(panel_izq, text="Cerrar caja (arqueo)", style="Peligro.TButton",
                       command=lambda: self._abrir_arqueo(sesion, totales)).pack(fill="x", ipady=4, pady=(0, 8))

            fila_acciones = ttk.Frame(panel_izq)
            fila_acciones.pack(fill="x")
            ttk.Button(fila_acciones, text="Editar caja",
                       command=lambda: self._abrir_edicion_sesion(sesion)).pack(
                side="left", fill="x", expand=True, padx=(0, 4))
            ttk.Button(fila_acciones, text="Cancelar apertura", style="Peligro.TButton",
                       command=lambda: self._cancelar_sesion_actual()).pack(
                side="left", fill="x", expand=True, padx=(4, 0))
            ttk.Button(panel_izq, text="📊 Exportar esta caja (Excel)",
                       command=lambda: self._exportar_caja_abierta(sesion)).pack(
                fill="x", pady=(8, 0))

        panel_der = tk.Frame(cuerpo, bg=ui.SURFACE, padx=18, pady=18, highlightthickness=1,
                              highlightbackground=ui.BORDER)
        panel_der.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        tk.Label(panel_der, text="Turnos anteriores", bg=ui.SURFACE, fg=ui.TEXT,
                  font=("Segoe UI Semibold", 13)).pack(anchor="w", pady=(0, 10))

        cierres = self.servicio_caja.listar_cierres()
        if not cierres:
            ttk.Label(panel_der, text="Aun no hay turnos cerrados.", style="Sutil.TLabel").pack(anchor="w")
        else:
            columnas = ("fecha", "cajero", "diferencia")
            arbol = ttk.Treeview(panel_der, columns=columnas, show="headings", height=12)
            arbol.heading("fecha", text="Fecha"); arbol.column("fecha", width=110)
            arbol.heading("cajero", text="Cajero"); arbol.column("cajero", width=120)
            arbol.heading("diferencia", text="Diferencia"); arbol.column("diferencia", width=110, anchor="e")
            for cierre in sorted(cierres, key=lambda c: c.cerrada_en, reverse=True):
                fecha = datetime.datetime.fromtimestamp(cierre.cerrada_en).strftime("%d/%m %H:%M")
                signo = "+" if cierre.diferencia >= 0 else ""
                arbol.insert("", "end", iid=cierre.sesion_id,
                             values=(fecha, cierre.cajero, f"{signo}{ui.formato_cop(cierre.diferencia)}"))
            arbol.pack(fill="both", expand=True)

            fila_acciones_hist = ttk.Frame(panel_der)
            fila_acciones_hist.pack(fill="x", pady=(8, 0))
            ttk.Button(fila_acciones_hist, text="Editar turno",
                       command=lambda: self._editar_turno_seleccionado(arbol)).pack(
                side="left", fill="x", expand=True, padx=(0, 4))
            ttk.Button(fila_acciones_hist, text="Eliminar turno", style="Peligro.TButton",
                       command=lambda: self._eliminar_turno_seleccionado(arbol)).pack(
                side="left", fill="x", expand=True, padx=(4, 0))
            ttk.Button(panel_der, text="📊 Exportar turno seleccionado (Excel)",
                       command=lambda: self._exportar_turno_seleccionado(arbol)).pack(
                fill="x", pady=(6, 0))

    def _abrir_registro_gasto_caja(self, sesion):
        ventana = tk.Toplevel(self.raiz)
        ventana.title("Añadir gasto")
        ventana.configure(bg=ui.SURFACE, padx=22, pady=18)
        ventana.transient(self.raiz)
        ventana.resizable(False, False)

        ttk.Label(ventana, text="Añadir gasto de caja", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(ventana, text="Sale del efectivo del turno (hielo, transporte, domicilio, etc.).",
                   style="Sutil.TLabel").pack(anchor="w", pady=(0, 14))

        ttk.Label(ventana, text="CONCEPTO", style="Etiqueta.TLabel").pack(anchor="w")
        # Combobox editable (no readonly): sugiere conceptos ya usados antes para
        # no tener que volver a escribirlos, pero deja escribir uno nuevo igual.
        conceptos = self.servicio_caja.conceptos_gastos_caja()
        combo_concepto = ttk.Combobox(ventana, values=conceptos, width=30)
        combo_concepto.pack(fill="x", pady=(4, 12))
        combo_concepto.focus_set()

        ttk.Label(ventana, text="MONTO", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_monto = ui.EntradaDinero(ventana, 0)
        entrada_monto.pack(fill="x", pady=(4, 16))

        def guardar():
            concepto = combo_concepto.get().strip()
            if not concepto:
                ui.mostrar_error(self.raiz, "Escribe o elige un concepto para el gasto.")
                return
            monto = entrada_monto.obtener()
            if monto <= 0:
                ui.mostrar_error(self.raiz, "El monto debe ser mayor a 0.")
                return
            try:
                self.servicio_caja.registrar_gasto_caja(concepto, monto)
            except ErrorDeNegocio as e:
                ui.mostrar_error(self.raiz, str(e))
                return
            ventana.destroy()
            self.renderizar_todo()

        ttk.Button(ventana, text="Guardar gasto", style="Accent.TButton",
                   command=guardar).pack(fill="x", ipady=4)
        ventana.grab_set()

    def _eliminar_gasto_caja(self, gasto):
        if not ui.confirmar(self.raiz, "Eliminar gasto",
                             f'¿Eliminar el gasto "{gasto.concepto}" de $ {ui.formato_cop(gasto.monto)}?'):
            return
        self.servicio_caja.eliminar_gasto_caja(gasto.id)
        self.renderizar_todo()

    def _abrir_arqueo(self, sesion, totales):
        ventana = tk.Toplevel(self.raiz)
        ventana.title("Arqueo de caja")
        ventana.configure(bg=ui.SURFACE, padx=22, pady=18)
        ventana.transient(self.raiz)

        ttk.Label(ventana, text="Arqueo de caja", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(ventana, text="Cuenta el efectivo fisico para cerrar el turno.",
                   style="Sutil.TLabel").pack(anchor="w", pady=(0, 12))

        for etiqueta, valor in (
            ("Efectivo inicial", sesion.efectivo_inicial),
            ("Ventas en efectivo", totales.total_efectivo),
            ("Ventas por QR", totales.total_qr),
            ("Gastado en DMT (costo)", totales.total_gastos_dmt),
            ("Gastos de caja", -totales.total_gastos_caja),
        ):
            fila = tk.Frame(ventana, bg=ui.SURFACE)
            fila.pack(fill="x")
            tk.Label(fila, text=etiqueta, bg=ui.SURFACE, fg=ui.TEXT_DIM).pack(side="left")
            tk.Label(fila, text=f"$ {ui.formato_cop(valor)}", bg=ui.SURFACE, fg=ui.TEXT_DIM,
                      font=ui.FUENTE_MONO).pack(side="right")

        fila_esperado = tk.Frame(ventana, bg=ui.SURFACE)
        fila_esperado.pack(fill="x", pady=(8, 14))
        tk.Label(fila_esperado, text="Efectivo esperado", bg=ui.SURFACE, fg=ui.TEXT,
                  font=("Segoe UI", 11, "bold")).pack(side="left")
        tk.Label(fila_esperado, text=f"$ {ui.formato_cop(totales.efectivo_esperado)}", bg=ui.SURFACE, fg=ui.TEXT,
                  font=("Consolas", 13, "bold")).pack(side="right")

        ttk.Label(ventana, text="EFECTIVO CONTADO", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_contado = ui.EntradaDinero(ventana, totales.efectivo_esperado)
        entrada_contado.pack(fill="x", pady=(4, 8))

        etiqueta_diff = tk.Label(ventana, bg=ui.SURFACE_2, fg=ui.TEXT, font=("Segoe UI", 10),
                                  anchor="w", padx=10, pady=6)
        etiqueta_diff.pack(fill="x", pady=(0, 14))

        def refrescar(*_):
            diferencia = entrada_contado.obtener() - totales.efectivo_esperado
            if diferencia == 0:
                etiqueta_diff.configure(text="Cuadra exacto", fg=ui.SUCCESS)
            elif diferencia > 0:
                etiqueta_diff.configure(text=f"Sobrante: $ {ui.formato_cop(diferencia)}", fg=ui.SUCCESS)
            else:
                etiqueta_diff.configure(text=f"Faltante: $ {ui.formato_cop(-diferencia)}", fg=ui.DANGER)

        entrada_contado.bind("<KeyRelease>", refrescar)
        refrescar()

        botones = ttk.Frame(ventana)
        botones.pack(fill="x")
        ttk.Button(botones, text="Cancelar", command=ventana.destroy).pack(side="left", fill="x", expand=True, padx=(0, 6))

        def confirmar_cierre():
            self.servicio_caja.cerrar_caja(entrada_contado.obtener())
            ventana.destroy()
            ui.avisar(self.raiz, "Caja cerrada correctamente.")
            self.renderizar_todo()

        ttk.Button(botones, text="Confirmar cierre", style="Peligro.TButton",
                   command=confirmar_cierre).pack(side="left", fill="x", expand=True, padx=(6, 0))
        ventana.grab_set()

    def _abrir_edicion_sesion(self, sesion):
        ventana = tk.Toplevel(self.raiz)
        ventana.title("Editar caja abierta")
        ventana.configure(bg=ui.SURFACE, padx=22, pady=18)
        ventana.transient(self.raiz)

        ttk.Label(ventana, text="Editar caja abierta", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(ventana, text="CAJERO", style="Etiqueta.TLabel").pack(anchor="w", pady=(12, 0))
        entrada_cajero = ttk.Entry(ventana)
        entrada_cajero.insert(0, sesion.cajero)
        entrada_cajero.pack(fill="x", pady=(4, 12))

        ttk.Label(ventana, text="EFECTIVO INICIAL", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_inicial = ui.EntradaDinero(ventana, sesion.efectivo_inicial)
        entrada_inicial.pack(fill="x", pady=(4, 16))

        def guardar():
            self.servicio_caja.editar_sesion_actual(entrada_cajero.get(), entrada_inicial.obtener())
            ventana.destroy()
            ui.avisar(self.raiz, "Caja actualizada.")
            self.renderizar_todo()

        ttk.Button(ventana, text="Guardar", style="Accent.TButton", command=guardar).pack(fill="x", ipady=4)
        ventana.grab_set()

    def _cancelar_sesion_actual(self):
        if not ui.confirmar(self.raiz, "Cancelar apertura",
                             "Esto borra el turno abierto Y todas sus ventas registradas de forma "
                             "permanente. No se puede deshacer. ¿Continuar?"):
            return
        try:
            self.servicio_caja.cancelar_sesion_actual()
            ui.avisar(self.raiz, "Apertura cancelada.")
            self.renderizar_todo()
        except ErrorDeNegocio as e:
            ui.mostrar_error(self.raiz, str(e))

    def _editar_turno_seleccionado(self, arbol):
        seleccion = arbol.selection()
        if not seleccion:
            ui.avisar(self.raiz, "Selecciona un turno de la lista primero.")
            return
        sesion_id = seleccion[0]
        cierre = next((c for c in self.servicio_caja.listar_cierres() if c.sesion_id == sesion_id), None)
        if not cierre:
            return
        self._abrir_edicion_cierre(cierre)

    def _abrir_edicion_cierre(self, cierre):
        ventana = tk.Toplevel(self.raiz)
        ventana.title("Editar turno")
        ventana.configure(bg=ui.SURFACE, padx=22, pady=18)
        ventana.transient(self.raiz)

        ttk.Label(ventana, text="Editar turno cerrado", style="Titulo.TLabel").pack(anchor="w")
        fecha = datetime.datetime.fromtimestamp(cierre.cerrada_en).strftime("%d/%m/%Y %H:%M")
        ttk.Label(ventana, text=f"Cerrado el {fecha}", style="Sutil.TLabel").pack(anchor="w", pady=(0, 12))

        ttk.Label(ventana, text="CAJERO", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_cajero = ttk.Entry(ventana)
        entrada_cajero.insert(0, cierre.cajero)
        entrada_cajero.pack(fill="x", pady=(4, 12))

        ttk.Label(ventana, text="EFECTIVO CONTADO", style="Etiqueta.TLabel").pack(anchor="w")
        entrada_contado = ui.EntradaDinero(ventana, cierre.efectivo_contado)
        entrada_contado.pack(fill="x", pady=(4, 16))

        def guardar():
            self.servicio_caja.editar_cierre(cierre.sesion_id, entrada_cajero.get(), entrada_contado.obtener())
            ventana.destroy()
            ui.avisar(self.raiz, "Turno actualizado.")
            self.renderizar_todo()

        ttk.Button(ventana, text="Guardar", style="Accent.TButton", command=guardar).pack(fill="x", ipady=4)
        ventana.grab_set()

    def _eliminar_turno_seleccionado(self, arbol):
        seleccion = arbol.selection()
        if not seleccion:
            ui.avisar(self.raiz, "Selecciona un turno de la lista primero.")
            return
        sesion_id = seleccion[0]
        if not ui.confirmar(self.raiz, "Eliminar turno",
                             "Esto borra el turno del historial Y todas sus ventas registradas de "
                             "forma permanente. No se puede deshacer. ¿Continuar?"):
            return
        try:
            self.servicio_caja.eliminar_cierre(sesion_id)
            ui.avisar(self.raiz, "Turno eliminado.")
            self.renderizar_todo()
        except ErrorDeNegocio as e:
            ui.mostrar_error(self.raiz, str(e))

    # ---------------------------------------------------------- exportar a Excel
    def _pedir_ruta_excel(self, nombre_sugerido: str) -> Optional[str]:
        return filedialog.asksaveasfilename(
            title="Exportar a Excel", defaultextension=".xlsx",
            filetypes=[("Libro de Excel", "*.xlsx")], initialfile=nombre_sugerido) or None

    def _exportar_caja_abierta(self, sesion):
        fecha = datetime.datetime.fromtimestamp(sesion.abierta_en).strftime("%Y%m%d_%H%M")
        ruta = self._pedir_ruta_excel(f"caja_{fecha}_{sesion.cajero}.xlsx")
        if not ruta:
            return
        totales = self.servicio_caja.calcular_totales(sesion)
        try:
            self.servicio_exportacion.exportar_reporte_caja_abierta(Path(ruta), sesion, totales)
        except OSError as e:
            ui.mostrar_error(self.raiz, f"No se pudo exportar el reporte: {e}")
            return
        ui.avisar(self.raiz, "Reporte de caja exportado.")

    def _exportar_turno_seleccionado(self, arbol):
        seleccion = arbol.selection()
        if not seleccion:
            ui.avisar(self.raiz, "Selecciona un turno de la lista primero.")
            return
        sesion_id = seleccion[0]
        cierre = next((c for c in self.servicio_caja.listar_cierres() if c.sesion_id == sesion_id), None)
        if not cierre:
            return
        fecha = datetime.datetime.fromtimestamp(cierre.cerrada_en).strftime("%Y%m%d_%H%M")
        ruta = self._pedir_ruta_excel(f"caja_{fecha}_{cierre.cajero}.xlsx")
        if not ruta:
            return
        try:
            self.servicio_exportacion.exportar_reporte_caja_cerrada(Path(ruta), cierre)
        except OSError as e:
            ui.mostrar_error(self.raiz, f"No se pudo exportar el reporte: {e}")
            return
        ui.avisar(self.raiz, "Reporte de caja exportado.")

    def _exportar_reporte_historico(self):
        fecha = datetime.datetime.now().strftime("%Y%m%d_%H%M")
        ruta = self._pedir_ruta_excel(f"historico_barra_dmt_{fecha}.xlsx")
        if not ruta:
            return
        try:
            self.servicio_exportacion.exportar_reporte_historico(Path(ruta))
        except OSError as e:
            ui.mostrar_error(self.raiz, f"No se pudo exportar el reporte: {e}")
            return
        ui.avisar(self.raiz, "Reporte historico exportado.")


def _mostrar_pantalla_carga(raiz):
    """Ventana sin bordes, fondo negro, con el logo circular centrado en la
    pantalla. Se muestra mientras se inicializa la BD y se construye toda la
    UI (que es lo que tarda), y se cierra apenas la app queda lista."""
    splash = tk.Toplevel(raiz)
    splash.overrideredirect(True)
    splash.configure(bg=ui.BG)
    try:
        splash.attributes("-topmost", True)
    except tk.TclError:
        pass

    imagen = tk.PhotoImage(data=LOGO_SPLASH_B64)
    splash._imagen_logo = imagen  # referencia viva -- si no, tkinter la recolecta
    tk.Label(splash, image=imagen, bg=ui.BG, bd=0, highlightthickness=0).pack()

    splash.update_idletasks()
    ancho, alto = imagen.width(), imagen.height()
    x = (splash.winfo_screenwidth() - ancho) // 2
    y = (splash.winfo_screenheight() - alto) // 2
    splash.geometry(f"{ancho}x{alto}+{x}+{y}")
    splash.update()
    return splash


def iniciar_aplicacion():
    raiz = tk.Tk()
    raiz.withdraw()
    splash = _mostrar_pantalla_carga(raiz)
    AplicacionBarra(raiz)
    splash.destroy()
    raiz.deiconify()
    raiz.mainloop()
