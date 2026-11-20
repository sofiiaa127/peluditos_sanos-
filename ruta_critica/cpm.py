"""Motor de grafos de Peluditos Sanos.

Cada enfermedad es un grafo dirigido y ponderado:
  - vértice  = etapa del tratamiento (con su duración en días)
  - arista   = "esta etapa requiere que termine aquella"

Funciones principales:
  - orden_topologico  -> Kahn (detecta ciclos)
  - calcular          -> ruta crítica (CPM): pasada adelante y atrás
  - dijkstra          -> ruta más corta de Consulta a Alta
  - buscar_ciclo      -> DFS que devuelve el ciclo encontrado (recaídas)
"""
import copy
import heapq
import json
from collections import deque, defaultdict
from dataclasses import dataclass

GRAVEDADES = ("leve", "moderada", "grave")


class CicloError(Exception):
    #Las dependencias forman un ciclo: no existe un orden válido.

    def __init__(self, atrapadas, ciclo=None):
        self.atrapadas = set(atrapadas)
        self.ciclo = ciclo or []
        detalle = " -> ".join(self.ciclo) if self.ciclo else ", ".join(sorted(self.atrapadas))
        super().__init__(f"Ciclo de dependencias (recaída): {detalle}")


@dataclass
class Resultado:
    inicio: int
    fin: int
    inicio_tardio: int
    fin_tardio: int

    @property
    def holgura(self) -> int:
        return self.inicio_tardio - self.inicio

    @property
    def es_critica(self) -> bool:
        return self.holgura == 0


# carga
def cargar_enfermedad(ruta: str) -> dict:
    #Lee el JSON completo de una enfermedad (nombre, color, actividades, recaída).
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)

#Devuelve solo las actividades del plan elegido según la gravedad.
def armar_plan(enfermedad: dict, gravedad: str = "leve", recaida: bool = False) -> dict:
    

    #Se quitan las opciones de otras gravedades. Si recaida=True se agrega la
    #etapa de recaída, que vuelve a la opción elegida y forma un CICLO.
    if gravedad not in GRAVEDADES:
        raise ValueError(f"Gravedad inválida: {gravedad}")
    todas = copy.deepcopy(enfermedad["actividades"])
    plan = {i: a for i, a in todas.items() if a.get("gravedad") in (None, gravedad)}
    for a in plan.values():
        a["requiere"] = [r for r in a["requiere"] if r in plan]

    if recaida and enfermedad.get("recaida"):
        r = enfermedad["recaida"]
        plan[r["id"]] = {"nombre": r["nombre"], "dias": r["dias"], "requiere": [r["desde"]]}
        opcion = next(i for i, a in plan.items() if a.get("gravedad") == gravedad)
        plan[opcion]["requiere"].append(r["id"])
    return plan


# grafos
def _sucesores(proyecto: dict) -> dict:
    suc = defaultdict(list)
    for act, datos in proyecto.items():
        for req in datos.get("requiere", []):
            suc[req].append(act)
    return suc


def buscar_ciclo(proyecto: dict) -> list[str]:
    #DFS con colores. Devuelve el ciclo como lista de IDs, o [] si no hay.
    suc = _sucesores(proyecto)
    BLANCO, GRIS, NEGRO = 0, 1, 2
    color = {a: BLANCO for a in proyecto}
    pila: list[str] = []

    def dfs(u):
        color[u] = GRIS
        pila.append(u)
        for v in suc[u]:
            if color[v] == GRIS:
                return pila[pila.index(v):] + [v]
            if color[v] == BLANCO:
                c = dfs(v)
                if c:
                    return c
        pila.pop()
        color[u] = NEGRO
        return []

    for a in proyecto:
        if color[a] == BLANCO:
            c = dfs(a)
            if c:
                return c
    return []


def orden_topologico(proyecto: dict) -> list[str]:
    #Algoritmo de Kahn. Lanza CicloError si hay ciclo.
    ids = set(proyecto)
    for act, datos in proyecto.items():
        for req in datos.get("requiere", []):
            if req not in ids:
                raise ValueError(f"La etapa '{act}' requiere un ID inexistente: '{req}'")

    grados = {a: len(d.get("requiere", [])) for a, d in proyecto.items()}
    suc = _sucesores(proyecto)
    cola = deque(a for a, g in grados.items() if g == 0)
    orden = []
    while cola:
        actual = cola.popleft()
        orden.append(actual)
        for s in suc[actual]:
            grados[s] -= 1
            if grados[s] == 0:
                cola.append(s)

    if len(orden) != len(proyecto):
        raise CicloError(ids - set(orden), buscar_ciclo(proyecto))
    return orden


def calcular(proyecto: dict) -> dict[str, Resultado]:
    #Ruta crítica (CPM). No modifica el proyecto.
    orden = orden_topologico(proyecto)
    res: dict[str, Resultado] = {}
    for act in orden:
        reqs = proyecto[act]["requiere"]
        inicio = max((res[r].fin for r in reqs), default=0)
        res[act] = Resultado(inicio, inicio + proyecto[act]["dias"], 0, 0)

    duracion = max((r.fin for r in res.values()), default=0)
    suc = _sucesores(proyecto)
    for act in reversed(orden):
        fin_t = min((res[s].inicio_tardio for s in suc[act]), default=duracion)
        r = res[act]
        res[act] = Resultado(r.inicio, r.fin, fin_t - proyecto[act]["dias"], fin_t)
    return res


def duracion_total(resultados: dict[str, Resultado]) -> int:
    return max((r.fin for r in resultados.values()), default=0)


def ruta_critica(resultados: dict[str, Resultado]) -> list[str]:
    criticas = [a for a, r in resultados.items() if r.es_critica]
    return sorted(criticas, key=lambda a: (resultados[a].inicio, a))

#Ruta más corta (en días) de origen a destino.
def dijkstra(proyecto: dict, origen: str, destino: str) -> tuple[int, list[str]]:
    

    #Peso de la arista u->v = días que dura u. Se ignoran las etapas
    #'paralelas' (no son un paso obligatorio del camino principal).
    suc = _sucesores({a: d for a, d in proyecto.items() if not d.get("paralela")})
    dist = {origen: 0}
    previo: dict[str, str] = {}
    heap = [(0, origen)]
    visitados = set()
    while heap:
        d, u = heapq.heappop(heap)
        if u in visitados:
            continue
        visitados.add(u)
        if u == destino:
            break
        for v in suc[u]:
            if proyecto[v].get("paralela"):
                continue
            nd = d + proyecto[u]["dias"]
            if nd < dist.get(v, float("inf")):
                dist[v], previo[v] = nd, u
                heapq.heappush(heap, (nd, v))
    if destino not in dist:
        raise ValueError(f"No hay camino de {origen} a {destino}")
    camino = [destino]
    while camino[-1] != origen:
        camino.append(previo[camino[-1]])
    return dist[destino] + proyecto[destino]["dias"], camino[::-1]
