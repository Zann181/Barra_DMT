"""Ayudas de presentacion: formato de pesos colombianos y estilos ttk compartidos.

Paleta: minimalista neon verde sobre negro, al estilo del panel de control
DMT (fondo #000, acento #39ff14, texto blanco, paneles casi negros con
borde verde tenue).
"""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from PIL import Image, ImageTk

from ..infraestructura.rutas import carpeta_imagenes_productos

BG = "#000000"
SURFACE = "#0a0a0a"
SURFACE_2 = "#111111"
SURFACE_3 = "#1a1a1a"
BORDER = "#173318"
TEXT = "#ffffff"
TEXT_DIM = "#a1a1aa"
TEXT_FAINT = "#52525b"
EMERALD = "#10b981"
ACCENT = "#39ff14"
ACCENT_STRONG = "#6dff4d"
ACCENT_INK = "#000000"
SUCCESS = "#10b981"
DANGER = "#f87171"
DANGER_BG = "#1a0808"
WARNING = "#fbbf24"

SEMAFORO_VERDE = "#22c55e"
SEMAFORO_AMARILLO = "#facc15"
SEMAFORO_ROJO = "#ef4444"

FUENTE_BASE = ("Segoe UI", 10)
FUENTE_NEGRITA = ("Segoe UI Semibold", 10)
FUENTE_TITULO = ("Segoe UI Semibold", 15)
FUENTE_TOTAL = ("Cascadia Mono", 20, "bold")
FUENTE_MONO = ("Cascadia Mono", 10)
FUENTE_ETIQUETA = ("Segoe UI Semibold", 8)

CATEGORIA_COLOR = {
    "Cervezas": "#39ff14", "Cocteles": "#10b981", "Licores": "#22c55e",
    "Sin alcohol": "#4ade80", "Comida": "#86efac", "Snacks": "#65a30d",
}


def formato_cop(valor) -> str:
    return f"{int(round(float(valor))):,}".replace(",", ".")


def solo_digitos(texto: str) -> str:
    return "".join(ch for ch in texto if ch.isdigit())


class EntradaDinero(ttk.Entry):
    """Entry que se autoformatea con puntos de miles mientras el usuario escribe."""

    def __init__(self, maestro, valor_inicial: int = 0, **kw):
        self._var = tk.StringVar()
        super().__init__(maestro, textvariable=self._var, font=FUENTE_MONO, **kw)
        self._valor = 0
        self.establecer(valor_inicial)
        self._var.trace_add("write", self._on_change)

    def _on_change(self, *_):
        crudo = solo_digitos(self._var.get())
        self._valor = int(crudo) if crudo else 0
        formateado = formato_cop(self._valor) if crudo else ""
        if formateado != self._var.get():
            self._var.set(formateado)
            self.icursor(tk.END)

    def obtener(self) -> int:
        return self._valor

    def establecer(self, valor: int) -> None:
        self._valor = int(valor)
        self._var.set(formato_cop(valor) if valor else "")


def aplicar_estilos(raiz: tk.Tk) -> None:
    raiz.configure(bg=BG)
    estilo = ttk.Style(raiz)
    estilo.theme_use("clam")

    estilo.configure(".", background=SURFACE, foreground=TEXT, font=FUENTE_BASE,
                      fieldbackground=SURFACE_2, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
    estilo.configure("TFrame", background=SURFACE)
    estilo.configure("Fondo.TFrame", background=BG)
    estilo.configure("TLabel", background=SURFACE, foreground=TEXT)
    estilo.configure("Titulo.TLabel", background=SURFACE, foreground=TEXT, font=FUENTE_TITULO)
    estilo.configure("Sutil.TLabel", background=SURFACE, foreground=TEXT_FAINT, font=("Segoe UI", 9))
    estilo.configure("Etiqueta.TLabel", background=SURFACE, foreground=EMERALD, font=FUENTE_ETIQUETA)
    estilo.configure("Precio.TLabel", background=SURFACE, foreground=ACCENT, font=FUENTE_MONO)
    estilo.configure("Total.TLabel", background=SURFACE, foreground=TEXT, font=FUENTE_TOTAL)

    estilo.configure("TButton", background=SURFACE_2, foreground=TEXT, borderwidth=1,
                      focuscolor=ACCENT, padding=(12, 8))
    estilo.map("TButton", background=[("active", SURFACE_3)], bordercolor=[("focus", ACCENT)])

    estilo.configure("Accent.TButton", background=ACCENT, foreground=ACCENT_INK, padding=(12, 10),
                      font=FUENTE_NEGRITA)
    estilo.map("Accent.TButton", background=[("active", ACCENT_STRONG)])

    # Metodo de pago activo: fondo verde oscuro (no el verde neon pleno de
    # Accent) para que se note cual esta marcado sin encandilar.
    estilo.configure("MetodoActivo.TButton", background="#0e3a18", foreground=ACCENT,
                      padding=(12, 10), font=FUENTE_NEGRITA)
    estilo.map("MetodoActivo.TButton", background=[("active", "#155225")])

    estilo.configure("Peligro.TButton", background=SURFACE_2, foreground=DANGER)
    estilo.map("Peligro.TButton", background=[("active", SURFACE_3)])

    # Botones chicos (+/- y borrar de la cuenta actual) -- mismo estilo pero
    # con menos padding para que no se coman espacio en la fila del item.
    estilo.configure("Mini.TButton", background=SURFACE_2, foreground=TEXT, borderwidth=1,
                      padding=(2, 1), font=("Segoe UI", 8))
    estilo.map("Mini.TButton", background=[("active", SURFACE_3)])
    estilo.configure("MiniPeligro.TButton", background=SURFACE_2, foreground=DANGER, borderwidth=1,
                      padding=(2, 1), font=("Segoe UI", 8))
    estilo.map("MiniPeligro.TButton", background=[("active", SURFACE_3)])

    estilo.configure("TNotebook", background=BG, borderwidth=0)
    estilo.configure("TNotebook.Tab", background=SURFACE, foreground=TEXT_DIM,
                      padding=(16, 10), font=FUENTE_NEGRITA, borderwidth=0)
    estilo.map("TNotebook.Tab",
               background=[("selected", ACCENT)],
               foreground=[("selected", ACCENT_INK)])

    estilo.configure("TEntry", fieldbackground=SURFACE_2, foreground=TEXT, insertcolor=ACCENT,
                      bordercolor=BORDER, padding=6)
    estilo.map("TEntry", bordercolor=[("focus", ACCENT)])
    estilo.configure("TCombobox", fieldbackground=SURFACE_2, foreground=TEXT, background=SURFACE_2,
                      arrowcolor=ACCENT, bordercolor=BORDER, padding=6)
    raiz.option_add("*TCombobox*Listbox.background", SURFACE_2)
    raiz.option_add("*TCombobox*Listbox.foreground", TEXT)
    raiz.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
    raiz.option_add("*TCombobox*Listbox.selectForeground", ACCENT_INK)

    estilo.configure("Treeview", background=SURFACE_2, fieldbackground=SURFACE_2, foreground=TEXT,
                      rowheight=28, borderwidth=0, font=FUENTE_BASE)
    estilo.configure("Treeview.Heading", background=SURFACE_3, foreground=EMERALD,
                      font=("Segoe UI Semibold", 9), borderwidth=0)
    estilo.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", ACCENT_INK)])

    estilo.configure("TCheckbutton", background=SURFACE, foreground=TEXT)
    estilo.configure("TRadiobutton", background=SURFACE, foreground=TEXT)

    estilo.configure("Cat.TButton", background=SURFACE_2, foreground=TEXT_DIM, padding=(12, 6))
    estilo.map("Cat.TButton", background=[("active", SURFACE_3)])
    estilo.configure("CatActiva.TButton", background=SURFACE_3, foreground=ACCENT, padding=(12, 6))

    # Scrollbar por defecto de "clam" es gris clarito -- casi invisible sobre
    # el fondo negro. La hacemos ancha y con el thumb en verde acento para
    # que se note como un deslizador de verdad (ej. en la cuenta actual).
    estilo.configure("Desplazable.Vertical.TScrollbar", background=ACCENT, troughcolor=SURFACE_2,
                      bordercolor=SURFACE_2, arrowcolor=ACCENT_INK, gripcount=0, width=14)
    estilo.map("Desplazable.Vertical.TScrollbar", background=[("active", ACCENT_STRONG)])


_cache_miniaturas: dict[tuple, "ImageTk.PhotoImage"] = {}


def cargar_miniatura(nombre_archivo: str | None, tamano: tuple[int, int] = (64, 64)):
    """Carga y cachea una miniatura de imagen de producto. None si no hay imagen o no se puede leer."""
    if not nombre_archivo:
        return None
    clave = (nombre_archivo, *tamano)
    if clave in _cache_miniaturas:
        return _cache_miniaturas[clave]
    ruta = carpeta_imagenes_productos() / nombre_archivo
    if not ruta.exists():
        return None
    try:
        imagen = Image.open(ruta)
        imagen.thumbnail(tamano, Image.LANCZOS)
        foto = ImageTk.PhotoImage(imagen)
    except Exception:
        return None
    _cache_miniaturas[clave] = foto
    return foto


def cargar_miniatura_archivo(ruta: str | Path, tamano: tuple[int, int] = (64, 64)):
    """Miniatura sin cache a partir de una ruta arbitraria (preview antes de guardar)."""
    try:
        imagen = Image.open(ruta)
        imagen.thumbnail(tamano, Image.LANCZOS)
        return ImageTk.PhotoImage(imagen)
    except Exception:
        return None


def invalidar_miniatura(nombre_archivo: str | None) -> None:
    """Limpia el cache de una imagen (llamar tras cambiarla/borrarla)."""
    if not nombre_archivo:
        return
    for clave in [c for c in _cache_miniaturas if c[0] == nombre_archivo]:
        del _cache_miniaturas[clave]


class GraficoBarras(tk.Canvas):
    """Barras horizontales simples sobre un Canvas -- sin dependencias de graficos.

    Con datos_extra, dibuja una segunda barra mas delgada (otro color) debajo
    de cada barra principal, alineada por posicion con la lista de `datos`
    (se usa para marcar el gasto DMT sobre el grafico de top productos)."""

    ALTO_FILA = 26
    ANCHO_ETIQUETA = 150
    ANCHO_VALOR = 100

    def __init__(self, maestro, datos: list[tuple[str, float]], formato=str, color: str | None = None,
                 datos_extra: list[float] | None = None, color_extra: str | None = None,
                 formato_extra=None, **kw):
        self._datos = datos
        self._formato = formato
        self._color = color or ACCENT
        self._datos_extra = datos_extra
        self._color_extra = color_extra or WARNING
        self._formato_extra = formato_extra or formato
        alto = max(1, len(datos)) * self.ALTO_FILA + 12
        super().__init__(maestro, bg=SURFACE, highlightthickness=0, height=alto, **kw)
        self.bind("<Configure>", lambda _e: self._dibujar())
        self._dibujar()

    def actualizar(self, datos: list[tuple[str, float]], datos_extra: list[float] | None = None) -> None:
        self._datos = datos
        self._datos_extra = datos_extra
        self.configure(height=max(1, len(datos)) * self.ALTO_FILA + 12)
        self._dibujar()

    def _dibujar(self):
        self.delete("all")
        ancho_total = self.winfo_width() or 400
        if not self._datos:
            self.create_text(6, 14, anchor="w", text="Sin datos en este rango.",
                              fill=TEXT_FAINT, font=("Segoe UI", 9))
            return
        valores_extra = self._datos_extra or []
        maximo = max([valor for _, valor in self._datos] + list(valores_extra) + [0]) or 1
        ancho_barra_max = max(20, ancho_total - self.ANCHO_ETIQUETA - self.ANCHO_VALOR - 16)
        for i, (etiqueta, valor) in enumerate(self._datos):
            y0 = 6 + i * self.ALTO_FILA
            alto_barra = self.ALTO_FILA - 8
            y_centro = y0 + alto_barra / 2
            self.create_text(4, y_centro, anchor="w", text=etiqueta, fill=TEXT_DIM, font=("Segoe UI", 9))
            x0 = self.ANCHO_ETIQUETA
            valor_extra = valores_extra[i] if i < len(valores_extra) else 0

            if valores_extra:
                # Barra principal (mitad superior) + barra extra -- DMT -- (mitad inferior).
                alto_principal = max(4, round(alto_barra * 0.55))
                alto_secundaria = alto_barra - alto_principal - 1
                largo = int(ancho_barra_max * (valor / maximo)) if maximo else 0
                self.create_rectangle(x0, y0, x0 + max(largo, 2), y0 + alto_principal,
                                       fill=self._color, outline="")
                largo_extra = int(ancho_barra_max * (valor_extra / maximo)) if maximo and valor_extra else 0
                y1 = y0 + alto_principal + 1
                self.create_rectangle(x0, y1, x0 + max(largo_extra, 2 if valor_extra else 0), y1 + alto_secundaria,
                                       fill=self._color_extra, outline="")
                texto = self._formato(valor)
                if valor_extra:
                    texto += f"  ·  DMT {self._formato_extra(valor_extra)}"
                self.create_text(x0 + ancho_barra_max + 10, y_centro, anchor="w",
                                  text=texto, fill=TEXT, font=FUENTE_MONO)
            else:
                largo = int(ancho_barra_max * (valor / maximo)) if maximo else 0
                self.create_rectangle(x0, y0, x0 + max(largo, 2), y0 + alto_barra,
                                       fill=self._color, outline="")
                self.create_text(x0 + ancho_barra_max + 10, y_centro, anchor="w",
                                  text=self._formato(valor), fill=TEXT, font=FUENTE_MONO)


PALETA_SERIE = [ACCENT, EMERALD, WARNING, DANGER, "#22c55e", "#4ade80", "#65a30d", "#a3e635"]


class GraficoCircular(tk.Canvas):
    """Grafico circular (torta) con leyenda -- sin dependencias externas."""

    DIAMETRO = 140
    ALTO_FILA_LEYENDA = 20

    def __init__(self, maestro, datos: list[tuple[str, float]], formato=str, **kw):
        self._datos = datos
        self._formato = formato
        alto = max(self.DIAMETRO + 20, len(datos) * self.ALTO_FILA_LEYENDA + 20)
        super().__init__(maestro, bg=SURFACE, highlightthickness=0, height=alto, **kw)
        self.bind("<Configure>", lambda _e: self._dibujar())
        self._dibujar()

    def actualizar(self, datos: list[tuple[str, float]]) -> None:
        self._datos = datos
        self.configure(height=max(self.DIAMETRO + 20, len(datos) * self.ALTO_FILA_LEYENDA + 20))
        self._dibujar()

    def _dibujar(self):
        self.delete("all")
        total = sum(max(0, valor) for _, valor in self._datos)
        if not self._datos or not total:
            self.create_text(6, 14, anchor="w", text="Sin datos en este rango.",
                              fill=TEXT_FAINT, font=("Segoe UI", 9))
            return

        x0, y0 = 10, 10
        x1, y1 = x0 + self.DIAMETRO, y0 + self.DIAMETRO
        inicio = 90.0
        for i, (_etiqueta, valor) in enumerate(self._datos):
            if valor <= 0:
                continue
            extension = 360 * (valor / total)
            self.create_arc(x0, y0, x1, y1, start=inicio, extent=-extension,
                             fill=PALETA_SERIE[i % len(PALETA_SERIE)], outline=SURFACE, width=2)
            inicio -= extension

        leyenda_x = x1 + 20
        for i, (etiqueta, valor) in enumerate(self._datos):
            y = y0 + i * self.ALTO_FILA_LEYENDA
            color = PALETA_SERIE[i % len(PALETA_SERIE)]
            self.create_rectangle(leyenda_x, y + 3, leyenda_x + 10, y + 13, fill=color, outline="")
            porcentaje = (valor / total * 100) if total else 0
            texto = f"{etiqueta}  ·  {self._formato(valor)}  ({porcentaje:.0f}%)"
            self.create_text(leyenda_x + 16, y + 8, anchor="w", text=texto, fill=TEXT_DIM, font=("Segoe UI", 9))


class Tooltip:
    """Tooltip simple sobre un widget: aparece al pasar el mouse (con un
    pequeño retraso) y desaparece al salir -- no ocupa espacio fijo en el
    layout, a diferencia de una caja de aviso siempre visible."""

    def __init__(self, widget, texto: str, retraso_ms: int = 400):
        self._widget = widget
        self._texto = texto
        self._retraso = retraso_ms
        self._id_after = None
        self._ventana = None
        widget.bind("<Enter>", self._programar, add="+")
        widget.bind("<Leave>", self._ocultar, add="+")
        widget.bind("<ButtonPress>", self._ocultar, add="+")

    def _programar(self, _e=None):
        self._cancelar_pendiente()
        self._id_after = self._widget.after(self._retraso, self._mostrar)

    def _cancelar_pendiente(self):
        if self._id_after:
            self._widget.after_cancel(self._id_after)
            self._id_after = None

    def _mostrar(self):
        if self._ventana or not self._widget.winfo_exists():
            return
        x = self._widget.winfo_rootx()
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 6
        self._ventana = tk.Toplevel(self._widget)
        self._ventana.overrideredirect(True)
        try:
            self._ventana.attributes("-topmost", True)
        except tk.TclError:
            pass
        tk.Label(self._ventana, text=self._texto, bg=SURFACE_3, fg=TEXT, font=("Segoe UI", 9),
                  padx=10, pady=6, justify="left", wraplength=280,
                  highlightthickness=1, highlightbackground=WARNING).pack()
        self._ventana.geometry(f"+{x}+{y}")

    def _ocultar(self, _e=None):
        self._cancelar_pendiente()
        if self._ventana:
            self._ventana.destroy()
            self._ventana = None


def mostrar_error(raiz, mensaje: str) -> None:
    from tkinter import messagebox
    messagebox.showerror("No se pudo completar", mensaje, parent=raiz)


def confirmar(raiz, titulo: str, mensaje: str) -> bool:
    from tkinter import messagebox
    return messagebox.askyesno(titulo, mensaje, parent=raiz)


def avisar(raiz, mensaje: str) -> None:
    from tkinter import messagebox
    messagebox.showinfo("Barra DMT", mensaje, parent=raiz)
