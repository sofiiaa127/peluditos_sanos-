#Cola de prioridad para la sala de espera de Peluditos Sanos (triaje).

#Se implementa a mano como un (min-heap) guardado en una lista:
#el padre de la posición i está en (i - 1) // 2
#sus hijos están en 2*i + 1 y 2*i + 2
#la raíz (posición 0) siempre es el paciente MÁS urgente

#Prioridad: grave = 1, moderada = 2, leve = 3  (número menor = se atiende antes).
#Empate: si tienen la misma gravedad, se atiende primero quien llegó antes (turno).


from dataclasses import dataclass

PRIORIDAD = {"grave": 1, "moderada": 2, "leve": 3}


@dataclass
class Paciente:
    nombre: str
    especie: str
    enfermedad: str      
    gravedad: str        
    turno: int = 0       # orden de llegada (lo asigna la cola)

    @property
    def prioridad(self) -> int:
        return PRIORIDAD[self.gravedad]

    def clave(self):
        #Lo que se compara en el min-heap: (prioridad, turno).
        return (self.prioridad, self.turno)


class ColaPrioridad:
    def __init__(self):
        self._heap: list[Paciente] = []
        self._turno = 0

    # operaciones
    def encolar(self, nombre, especie, enfermedad, gravedad) -> Paciente:
        gravedad = gravedad.lower()
        if gravedad not in PRIORIDAD:
            raise ValueError(f"Gravedad desconocida: {gravedad}")
        if not nombre.strip():
            raise ValueError("El paciente necesita un nombre")
        self._turno += 1
        p = Paciente(nombre.strip(), especie, enfermedad, gravedad, self._turno)
        self._heap.append(p)                 # 1) se pone al final
        self._subir(len(self._heap) - 1)     # 2) sube mientras sea más urgente que su padre
        return p

    def atender(self) -> Paciente:
        if not self._heap:
            raise IndexError("La sala de espera está vacía")
        raiz = self._heap[0]
        ultimo = self._heap.pop()
        if self._heap:
            self._heap[0] = ultimo           # el último pasa a la raíz
            self._bajar(0)                   # y baja hasta su lugar
        return raiz

    def ver_siguiente(self):
        return self._heap[0] if self._heap else None

    def en_orden(self) -> list[Paciente]:
        """Lista de espera ordenada (sin modificar la cola)."""
        return sorted(self._heap, key=Paciente.clave)

    def __len__(self):
        return len(self._heap)

    # min-heap
    def _subir(self, i):
        while i > 0:
            padre = (i - 1) // 2
            if self._heap[i].clave() < self._heap[padre].clave():
                self._heap[i], self._heap[padre] = self._heap[padre], self._heap[i]
                i = padre
            else:
                break

    def _bajar(self, i):
        n = len(self._heap)
        while True:
            menor = i
            for hijo in (2 * i + 1, 2 * i + 2):
                if hijo < n and self._heap[hijo].clave() < self._heap[menor].clave():
                    menor = hijo
            if menor == i:
                break
            self._heap[i], self._heap[menor] = self._heap[menor], self._heap[i]
            i = menor
