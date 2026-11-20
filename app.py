"""Peluditos Sanos - Ruta crítica de tratamientos veterinarios.

Ejecutar:  python app.py
"""
import copy
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from ruta_critica.cpm import (
    CicloError, armar_plan, buscar_ciclo, calcular, cargar_enfermedad,
    dijkstra, duracion_total, ruta_critica,
)
from ruta_critica.triaje import ColaPrioridad, PRIORIDAD

# ------------------------------------------------------------ paleta
FONDO = "#f5f3ff"
TARJETA = "#ffffff"
TEXTO = "#1e1b4b"
SUAVE = "#6b7280"
BORDE = "#e5e7eb"
HEADER_1, HEADER_2 = "#06b6d4", "#c026d3"   # degradado del encabezado
COLOR_GRAVEDAD = {"leve": "#10b981", "moderada": "#f59e0b", "grave": "#ef4444"}
ROJO_CICLO = "#dc2626"
FUENTE = "Segoe UI"

ENFERMEDADES = [
    ("datos/antiparasitario.json", "Antiparasitario"),
    ("datos/respiratorio.json", "Respiratorio"),
    ("datos/dermatologico.json", "Dermatológico"),
    ("datos/digestivo.json", "Digestivo"),
]


def aclarar(hex_color: str, factor: float) -> str:
    """Mezcla un color con blanco (factor 0 = igual, 1 = blanco)."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    r, g, b = (int(c + (255 - c) * factor) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def mezclar(c1: str, c2: str, t: float) -> str:
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(x + (y - x) * t):02x}" for x, y in zip(a, b))


class Tarjeta(tk.Frame):
    """Cajita blanca con un título de color y un valor grande."""

    def __init__(self, padre, titulo, color):
        super().__init__(padre, bg=TARJETA, highlightbackground=color, highlightthickness=2)
        tk.Label(self, text=titulo.upper(), bg=color, fg="white",
                 font=(FUENTE, 9, "bold"), pady=3).pack(fill="x")
        self.valor = tk.Label(self, text="-", bg=TARJETA, fg=TEXTO,
                              font=(FUENTE, 15, "bold"), pady=2)
        self.valor.pack(fill="x")
        self.detalle = tk.Label(self, text="", bg=TARJETA, fg=SUAVE, font=(FUENTE, 9),
                                wraplength=260, justify="center", pady=4)
        self.detalle.pack(fill="x", padx=6)

    def poner(self, valor, detalle="", color=TEXTO):
        self.valor.config(text=valor, fg=color)
        self.detalle.config(text=detalle)


class PestanaEnfermedad(tk.Frame):
    def __init__(self, padre, ruta_json):
        super().__init__(padre, bg=FONDO)
        self.enfermedad = cargar_enfermedad(ruta_json)
        self.color = self.enfermedad["color"]
        self.gravedad = tk.StringVar(value="leve")
        self.recaida = tk.BooleanVar(value=False)
        self.proyecto = {}
        self.resultados = {}
        self._crear_widgets()
        self.restablecer()

    # ---------------------------------------------------- interfaz
    def _crear_widgets(self):
        c = self.color
        # Título de la enfermedad
        cab = tk.Frame(self, bg=FONDO)
        cab.pack(fill="x", padx=16, pady=(12, 4))
        self.lbl_titulo = tk.Label(cab, bg=FONDO, fg=c, font=(FUENTE, 17, "bold"))
        self.lbl_titulo.pack(side="left")
        self.lbl_desc = tk.Label(cab, bg=FONDO, fg=SUAVE, font=(FUENTE, 10))
        self.lbl_desc.pack(side="left", padx=10, pady=(6, 0))
        ttk.Button(cab, text="Cargar JSON...", command=self.cargar_archivo).pack(side="right", padx=4)
        ttk.Button(cab, text="Restablecer", command=self.restablecer).pack(side="right", padx=4)

        # Controles: gravedad + recaída
        ctrl = tk.Frame(self, bg=aclarar(c, 0.88), highlightbackground=aclarar(c, 0.5), highlightthickness=1)
        ctrl.pack(fill="x", padx=16, pady=4)
        tk.Label(ctrl, text="Gravedad de la mascota:", bg=ctrl["bg"], fg=TEXTO,
                 font=(FUENTE, 10, "bold")).pack(side="left", padx=(12, 6), pady=8)
        for g in ("leve", "moderada", "grave"):
            tk.Radiobutton(ctrl, text=f"● {g.capitalize()}", value=g, variable=self.gravedad,
                           command=self.restablecer, bg=ctrl["bg"], fg=COLOR_GRAVEDAD[g],
                           selectcolor=TARJETA, activebackground=ctrl["bg"],
                           font=(FUENTE, 10, "bold"), indicatoron=False, relief="flat",
                           padx=10, pady=3, bd=0, cursor="hand2").pack(side="left", padx=3)
        tk.Checkbutton(ctrl, text="Simular recaída (crea un ciclo)", variable=self.recaida,
                       command=self.recalcular, bg=ctrl["bg"], fg=ROJO_CICLO,
                       activebackground=ctrl["bg"], font=(FUENTE, 10, "bold"),
                       cursor="hand2").pack(side="right", padx=12)

        # Tarjetas de resumen
        fila = tk.Frame(self, bg=FONDO)
        fila.pack(fill="x", padx=16, pady=6)
        self.t_duracion = Tarjeta(fila, "Días hasta el alta", c)
        self.t_ruta = Tarjeta(fila, "Ruta crítica (CPM)", ROJO_CICLO)
        self.t_dijkstra = Tarjeta(fila, "Ruta más corta (Dijkstra)", "#4f46e5")
        self.t_ciclo = Tarjeta(fila, "Ciclos (DFS)", "#0f766e")
        for i, t in enumerate((self.t_duracion, self.t_ruta, self.t_dijkstra, self.t_ciclo)):
            fila.columnconfigure(i, weight=1, uniform="t")
            t.grid(row=0, column=i, sticky="nsew", padx=5)

        # Tabla
        marco = tk.Frame(self, bg=FONDO)
        marco.pack(fill="both", expand=True, padx=16, pady=4)
        cols = ("id", "nombre", "requiere", "dias", "inicio", "fin", "holgura", "tipo")
        self.tree = ttk.Treeview(marco, columns=cols, show="headings", height=9, style="Vet.Treeview")
        titulos = {"id": "ID", "nombre": "Etapa", "requiere": "Requiere", "dias": "Días",
                   "inicio": "Día inicio", "fin": "Día fin", "holgura": "Holgura", "tipo": "Tipo"}
        anchos = {"id": 60, "nombre": 240, "requiere": 150, "tipo": 170}
        for col, txt in titulos.items():
            self.tree.heading(col, text=txt)
            self.tree.column(col, width=anchos.get(col, 80), anchor="w" if col == "nombre" else "center")
        self.tree.tag_configure("critica", foreground=ROJO_CICLO, font=(FUENTE, 10, "bold"))
        self.tree.tag_configure("par", background=aclarar(c, 0.93))
        self.tree.tag_configure("impar", background=TARJETA)
        barra = ttk.Scrollbar(marco, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=barra.set)
        self.tree.pack(side="left", fill="both", expand=True)
        barra.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._al_seleccionar)

        # Edición
        ed = tk.Frame(self, bg=TARJETA, highlightbackground=BORDE, highlightthickness=1)
        ed.pack(fill="x", padx=16, pady=4)
        tk.Label(ed, text="Editar etapa:", bg=TARJETA, fg=TEXTO,
                 font=(FUENTE, 10, "bold")).pack(side="left", padx=(12, 4), pady=8)
        self.lbl_sel = tk.Label(ed, text="Ninguna seleccionada", bg=TARJETA, fg=SUAVE,
                                font=(FUENTE, 10), width=34, anchor="w")
        self.lbl_sel.pack(side="left", padx=4)
        tk.Label(ed, text="Días:", bg=TARJETA, fg=TEXTO, font=(FUENTE, 10)).pack(side="left", padx=4)
        self.spin = ttk.Spinbox(ed, from_=0, to=365, width=6)
        self.spin.pack(side="left", padx=4)
        ttk.Button(ed, text="Aplicar cambios", command=self.aplicar_cambio).pack(side="left", padx=4)
        ttk.Button(ed, text="+1 día", command=lambda: self.sumar(1)).pack(side="left", padx=4)
        ttk.Button(ed, text="-1 día", command=lambda: self.sumar(-1)).pack(side="left", padx=4)

        # Diagrama de Gantt
        self.canvas = tk.Canvas(self, bg=TARJETA, height=260, highlightthickness=1,
                                highlightbackground=BORDE)
        self.canvas.pack(fill="both", expand=True, padx=16, pady=(4, 14))
        self.mensaje_ciclo = None
        self.canvas.bind("<Configure>", lambda e: self._dibujar_gantt())

    # ---------------------------------------------------- lógica
    def restablecer(self):
        self.lbl_titulo.config(text=self.enfermedad["nombre"])
        self.lbl_desc.config(text=self.enfermedad.get("descripcion", ""))
        self.base = armar_plan(self.enfermedad, self.gravedad.get())
        self.proyecto = copy.deepcopy(self.base)
        self.recalcular()

    def _plan_actual(self):
        """El plan editado, más la recaída si está activada."""
        plan = copy.deepcopy(self.proyecto)
        if self.recaida.get() and self.enfermedad.get("recaida"):
            r = self.enfermedad["recaida"]
            plan[r["id"]] = {"nombre": r["nombre"], "dias": r["dias"], "requiere": [r["desde"]]}
            opcion = next(i for i, a in plan.items() if a.get("gravedad"))
            plan[opcion]["requiere"].append(r["id"])
        return plan

    def recalcular(self):
        plan = self._plan_actual()
        alta = next(i for i, a in plan.items() if a["nombre"].startswith("Alta"))
        try:
            dias_min, camino = dijkstra(plan, "CON", alta)
            self.t_dijkstra.poner(f"{dias_min} días", " → ".join(camino))
        except Exception as e:
            self.t_dijkstra.poner("—", str(e))

        ciclo = buscar_ciclo(plan)
        if ciclo:
            nombres = " → ".join(plan[a]["nombre"] for a in ciclo)
            self.t_ciclo.poner("¡Ciclo!", nombres, ROJO_CICLO)
        else:
            self.t_ciclo.poner("Sin ciclos", "El plan avanza sin repetir etapas", "#0f766e")

        try:
            self.resultados = calcular(plan)
        except CicloError as e:
            self.resultados = {}
            self.t_duracion.poner("∞", "Con una recaída el alta no se puede fechar", ROJO_CICLO)
            self.t_ruta.poner("No existe", "Hay un ciclo: no hay orden válido de etapas", ROJO_CICLO)
            self._llenar_tabla(plan, ciclo=set(e.ciclo))
            self.mensaje_ciclo = str(e)
            self._dibujar_gantt()
            return
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        self.mensaje_ciclo = None
        total = duracion_total(self.resultados)
        criticas = ruta_critica(self.resultados)
        opcion = next((a for a in plan.values() if a.get("gravedad")), {})
        self.t_duracion.poner(f"{total} días", f"Opción: {opcion.get('nombre', '')} · {opcion.get('costo', '')}",
                              self.color)
        self.t_ruta.poner(f"{len(criticas)} etapas", " → ".join(criticas), ROJO_CICLO)
        self._llenar_tabla(plan)
        self._dibujar_gantt()

    def _llenar_tabla(self, plan, ciclo=frozenset()):
        self.tree.delete(*self.tree.get_children())
        orden = sorted(plan, key=lambda a: (self.resultados[a].inicio, a)) if self.resultados else list(plan)
        for n, act in enumerate(orden):
            d = plan[act]
            reqs = ", ".join(d["requiere"]) or "(ninguna)"
            if d.get("gravedad"):
                tipo = f"Tratamiento {d['gravedad']} {d.get('costo', '')}"
            elif d.get("paralela"):
                tipo = "En paralelo"
            elif act == self.enfermedad.get("recaida", {}).get("id"):
                tipo = "Recaída (vuelve atrás)"
            else:
                tipo = "Etapa fija"
            tags = ["par" if n % 2 else "impar"]
            if self.resultados:
                r = self.resultados[act]
                valores = (act, d["nombre"], reqs, d["dias"], r.inicio, r.fin, r.holgura, tipo)
                if r.es_critica:
                    tags.append("critica")
            else:
                valores = (act, d["nombre"], reqs, d["dias"], "—", "—", "—", tipo)
                if act in ciclo:
                    tags.append("critica")
            self.tree.insert("", "end", iid=act, values=valores, tags=tags)

    def _seleccion(self):
        sel = self.tree.selection()
        if not sel or sel[0] not in self.proyecto:
            messagebox.showwarning("Aviso", "Selecciona una etapa de la tabla.")
            return None
        return sel[0]

    def _al_seleccionar(self, _):
        sel = self.tree.selection()
        if sel and sel[0] in self.proyecto:
            d = self.proyecto[sel[0]]
            self.lbl_sel.config(text=f"[{sel[0]}] {d['nombre']}", fg=TEXTO)
            self.spin.set(d["dias"])

    def aplicar_cambio(self):
        act = self._seleccion()
        if not act:
            return
        try:
            valor = int(self.spin.get())
            if valor < 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Escribe un número entero de días (0 o más).")
            return
        self.proyecto[act]["dias"] = valor
        self.recalcular()
        self.tree.selection_set(act)

    def sumar(self, delta):
        act = self._seleccion()
        if not act:
            return
        self.proyecto[act]["dias"] = max(0, self.proyecto[act]["dias"] + delta)
        self.spin.set(self.proyecto[act]["dias"])
        self.recalcular()
        self.tree.selection_set(act)

    def cargar_archivo(self):
        ruta = filedialog.askopenfilename(filetypes=[("Archivos JSON", "*.json")])
        if not ruta:
            return
        try:
            nueva = cargar_enfermedad(ruta)
            calcular(armar_plan(nueva, "leve"))
        except Exception as e:
            messagebox.showerror("Error al cargar JSON", str(e))
            return
        self.enfermedad = nueva
        self.restablecer()

    # ---------------------------------------------------- Gantt
    def _dibujar_gantt(self):
        mensaje = self.mensaje_ciclo
        cv = self.canvas
        cv.delete("all")
        w, h = cv.winfo_width(), cv.winfo_height()
        if w < 100 or h < 60:
            return
        if mensaje:
            cv.create_text(w / 2, h / 2 - 14, text="No se puede dibujar el calendario",
                           font=(FUENTE, 14, "bold"), fill=ROJO_CICLO)
            cv.create_text(w / 2, h / 2 + 14, text=mensaje, font=(FUENTE, 10), fill=SUAVE,
                           width=w - 60)
            return
        if not self.resultados:
            return
        total = duracion_total(self.resultados) or 1
        plan = self._plan_actual()
        izq, der, arriba = 230, 30, 42
        ancho = w - izq - der
        acts = sorted(self.resultados, key=lambda a: (self.resultados[a].inicio, a))
        alto = max(min((h - arriba - 30) / len(acts), 30), 14)
        px = lambda t: izq + t * ancho / total

        cv.create_text(14, 16, text="Calendario del tratamiento (días)", anchor="w",
                       font=(FUENTE, 11, "bold"), fill=TEXTO)
        # leyenda
        lx = w - der
        for txt, col, dash in (("Holgura", "#e5e7eb", (3, 2)), ("Etapa normal", self.color, None),
                               ("Ruta crítica", ROJO_CICLO, None)):
            tw = len(txt) * 8
            cv.create_text(lx, 16, text=txt, anchor="e", font=(FUENTE, 9), fill=SUAVE)
            cv.create_rectangle(lx - tw - 20, 10, lx - tw - 6, 22, fill=col, outline=SUAVE if dash else "",
                                dash=dash)
            lx -= tw + 40

        # cuadrícula
        paso = max(1, round(total / 12 / 5) * 5) if total > 20 else 1
        for t in list(range(0, total + 1, paso)) + [total]:
            x = px(t)
            cv.create_line(x, arriba - 6, x, arriba + alto * len(acts), fill="#f1f5f9")
            cv.create_text(x, arriba - 14, text=str(t), font=(FUENTE, 8), fill=SUAVE)

        for i, act in enumerate(acts):
            r = self.resultados[act]
            y = arriba + i * alto
            if i % 2:
                cv.create_rectangle(0, y, w, y + alto, fill=aclarar(self.color, 0.95), outline="")
            cv.create_text(izq - 10, y + alto / 2, anchor="e", font=(FUENTE, 9),
                           text=f"{act}  {plan[act]['nombre'][:26]}",
                           fill=ROJO_CICLO if r.es_critica else TEXTO)
            if r.holgura > 0:
                cv.create_rectangle(px(r.fin), y + 5, px(r.fin_tardio), y + alto - 5,
                                    fill="#f3f4f6", outline="#cbd5e1", dash=(3, 2))
            col = ROJO_CICLO if r.es_critica else self.color
            x0, x1 = px(r.inicio), max(px(r.fin), px(r.inicio) + 3)
            cv.create_rectangle(x0, y + 3, x1, y + alto - 3, fill=col, outline=mezclar(col, "#000000", 0.2))
            if x1 - x0 > 22:
                cv.create_text(x0 + 5, y + alto / 2, text=f"{r.fin - r.inicio}d", anchor="w",
                               font=(FUENTE, 8, "bold"), fill="white")


class PestanaSalaEspera(tk.Frame):
    """Sala de espera con triaje: se atiende primero al más grave (cola de prioridad)."""

    def __init__(self, padre, app):
        super().__init__(padre, bg=FONDO)
        self.app = app
        self.cola = ColaPrioridad()
        self._crear_widgets()
        for datos in (("Luna", "Gato", "Digestivo", "leve"),
                      ("Rocky", "Perro", "Respiratorio", "grave"),
                      ("Coco", "Conejo", "Dermatológico", "moderada"),
                      ("Max", "Perro", "Antiparasitario", "leve")):
            self.cola.encolar(*datos)
        self.refrescar()

    def _crear_widgets(self):
        tk.Label(self, text="Sala de espera · Triaje", bg=FONDO, fg="#7c3aed",
                 font=(FUENTE, 17, "bold")).pack(anchor="w", padx=16, pady=(12, 0))
        tk.Label(self, text="Cola de prioridad (montículo mínimo): grave → moderada → leve. "
                 "Si empatan, entra primero quien llegó antes.", bg=FONDO, fg=SUAVE,
                 font=(FUENTE, 10)).pack(anchor="w", padx=16)

        form = tk.Frame(self, bg="#ede9fe", highlightbackground="#c4b5fd", highlightthickness=1)
        form.pack(fill="x", padx=16, pady=8)
        self.nombre = tk.StringVar()
        self.especie = tk.StringVar(value="Perro")
        self.enfermedad = tk.StringVar(value=ENFERMEDADES[0][1])
        self.gravedad = tk.StringVar(value="leve")
        def etiqueta(t):
            tk.Label(form, text=t, bg=form["bg"], fg=TEXTO, font=(FUENTE, 10, "bold")).pack(side="left", padx=(12, 4), pady=10)
        etiqueta("Nombre:")
        ttk.Entry(form, textvariable=self.nombre, width=14).pack(side="left")
        etiqueta("Especie:")
        ttk.Combobox(form, textvariable=self.especie, width=8, state="readonly",
                     values=["Perro", "Gato", "Conejo", "Ave", "Otro"]).pack(side="left")
        etiqueta("Enfermedad:")
        ttk.Combobox(form, textvariable=self.enfermedad, width=14, state="readonly",
                     values=[n for _, n in ENFERMEDADES]).pack(side="left")
        etiqueta("Gravedad:")
        for g in PRIORIDAD:
            tk.Radiobutton(form, text=f"● {g.capitalize()}", value=g, variable=self.gravedad,
                           bg=form["bg"], fg=COLOR_GRAVEDAD[g], selectcolor=TARJETA,
                           activebackground=form["bg"], font=(FUENTE, 10, "bold"),
                           indicatoron=False, relief="flat", padx=8, pady=3, bd=0,
                           cursor="hand2").pack(side="left", padx=2)
        ttk.Button(form, text="+ Ingresar a la sala", command=self.ingresar).pack(side="left", padx=12)

        fila = tk.Frame(self, bg=FONDO)
        fila.pack(fill="x", padx=16, pady=4)
        self.t_siguiente = Tarjeta(fila, "Siguiente en ser atendido", "#7c3aed")
        self.t_espera = Tarjeta(fila, "Mascotas esperando", "#06b6d4")
        self.t_ultimo = Tarjeta(fila, "Último atendido", "#10b981")
        for i, t in enumerate((self.t_siguiente, self.t_espera, self.t_ultimo)):
            fila.columnconfigure(i, weight=1, uniform="s")
            t.grid(row=0, column=i, sticky="nsew", padx=5)

        tk.Button(self, text="🩺  Atender siguiente paciente", command=self.atender,
                  bg="#7c3aed", fg="white", activebackground="#6d28d9", activeforeground="white",
                  font=(FUENTE, 12, "bold"), bd=0, padx=16, pady=8, cursor="hand2").pack(pady=8)

        cols = ("pos", "nombre", "especie", "enfermedad", "gravedad", "prioridad", "turno")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=12, style="Vet.Treeview")
        for c, t in zip(cols, ("Puesto", "Mascota", "Especie", "Enfermedad", "Gravedad", "Prioridad", "Llegada")):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=150 if c in ("nombre", "enfermedad") else 100, anchor="center")
        for g, col in COLOR_GRAVEDAD.items():
            self.tree.tag_configure(g, background=aclarar(col, 0.82), foreground=TEXTO)
        self.tree.pack(fill="both", expand=True, padx=16, pady=(4, 14))

    def ingresar(self):
        try:
            self.cola.encolar(self.nombre.get(), self.especie.get(), self.enfermedad.get(), self.gravedad.get())
        except ValueError as e:
            messagebox.showwarning("Falta información", str(e))
            return
        self.nombre.set("")
        self.refrescar()

    def atender(self):
        if not len(self.cola):
            messagebox.showinfo("Sala vacía", "No hay mascotas esperando.")
            return
        p = self.cola.atender()
        self.t_ultimo.poner(p.nombre, f"{p.especie} · {p.enfermedad} · {p.gravedad}", COLOR_GRAVEDAD[p.gravedad])
        self.refrescar()
        self.app.abrir_tratamiento(p)

    def refrescar(self):
        self.tree.delete(*self.tree.get_children())
        for i, p in enumerate(self.cola.en_orden(), 1):
            self.tree.insert("", "end", tags=(p.gravedad,), values=(
                i, p.nombre, p.especie, p.enfermedad, p.gravedad.capitalize(), p.prioridad, f"#{p.turno}"))
        s = self.cola.ver_siguiente()
        if s:
            self.t_siguiente.poner(s.nombre, f"{s.enfermedad} · {s.gravedad}", COLOR_GRAVEDAD[s.gravedad])
        else:
            self.t_siguiente.poner("—", "Sala vacía")
        self.t_espera.poner(str(len(self.cola)))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Peluditos Sanos · Ruta crítica de tratamientos")
        self.geometry("1250x900")
        self.minsize(1000, 700)
        self.configure(bg=FONDO)
        self._estilos()

        # Encabezado con degradado
        enc = tk.Canvas(self, height=78, highlightthickness=0)
        enc.pack(fill="x")

        def pintar(_=None):
            enc.delete("all")
            w = enc.winfo_width()
            for x in range(0, w, 4):
                enc.create_rectangle(x, 0, x + 4, 78, fill=mezclar(HEADER_1, HEADER_2, x / max(w, 1)), outline="")
            for cx, cy, rr in ((w - 120, 30, 16), (w - 80, 22, 10), (w - 60, 44, 10), (w - 100, 54, 10)):
                enc.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=mezclar(HEADER_2, "#ffffff", 0.45), outline="")
            enc.create_text(24, 30, text="Peluditos Sanos", anchor="w", fill="white", font=(FUENTE, 24, "bold"))
            enc.create_text(26, 60, text="Tratamientos médicos de mascotas a largo plazo · triaje, grafos, ruta crítica, Dijkstra y ciclos",
                            anchor="w", fill="white", font=(FUENTE, 10))
        enc.bind("<Configure>", pintar)

        tk.Label(self, text="Peluditos Sanos solo orienta sobre etapas y plazos. El plan real lo define siempre el veterinario.",
                 bg="#fdf2f8", fg="#9d174d", font=(FUENTE, 9, "bold"), pady=5).pack(fill="x", side="bottom")

        libro = ttk.Notebook(self, style="Vet.TNotebook")
        libro.pack(fill="both", expand=True)
        self.libro = libro
        libro.add(PestanaSalaEspera(libro, self), text="  🐾 Sala de espera  ")
        self.pestanas = {}
        for i, (ruta, nombre) in enumerate(ENFERMEDADES, 1):
            self.pestanas[nombre] = PestanaEnfermedad(libro, ruta)
            libro.add(self.pestanas[nombre], text=f"  {i}. {nombre}  ")

    def abrir_tratamiento(self, paciente):
        """Al atender un paciente se abre su enfermedad con su gravedad y se calcula la ruta crítica."""
        pest = self.pestanas[paciente.enfermedad]
        pest.gravedad.set(paciente.gravedad)
        pest.recaida.set(False)
        pest.restablecer()
        self.libro.select(pest)


    def _estilos(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Vet.TNotebook", background=FONDO, borderwidth=0)
        s.configure("Vet.TNotebook.Tab", font=(FUENTE, 10, "bold"), padding=(12, 6),
                    background="#e0e7ff", foreground=TEXTO)
        s.map("Vet.TNotebook.Tab", background=[("selected", TARJETA)], foreground=[("selected", "#7c3aed")])
        s.configure("Vet.Treeview", font=(FUENTE, 10), rowheight=26, background=TARJETA,
                    fieldbackground=TARJETA, foreground=TEXTO, borderwidth=0)
        s.configure("Vet.Treeview.Heading", font=(FUENTE, 10, "bold"), background="#ede9fe",
                    foreground="#4c1d95", relief="flat", padding=6)
        s.map("Vet.Treeview", background=[("selected", "#c4b5fd")], foreground=[("selected", TEXTO)])
        s.configure("TButton", font=(FUENTE, 9, "bold"), padding=(10, 4), background="#ede9fe",
                    foreground="#4c1d95", borderwidth=0)
        s.map("TButton", background=[("active", "#ddd6fe")])


if __name__ == "__main__":
    App().mainloop()
