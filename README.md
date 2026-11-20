# Peluditos Sanos: Ruta crítica de tratamientos veterinarios

App de escritorio en Python (`tkinter`) que modela los tratamientos de mascotas como grafos
dirigidos y ponderados .

Cuatro pestañas: una por enfermedad: **Antiparasitario, Respiratorio, Dermatológico y Digestivo**.

## Qué hace
- **Sala de espera (cola de prioridad)**: en `ruta_critica/triaje.py` se atiende primero al más grave; si empatan, al que llegó antes. Al atender, se abre su tratamiento con la ruta crítica.
- **Ruta crítica (CPM)** con orden topológico (Kahn): días hasta el alta, inicio/fin y holgura de cada etapa.
- **Gravedad** (leve / moderada / grave): elige una de las 3 opciones de tratamiento.
- **Dijkstra**: ruta más corta de Consulta a Alta (68 d, 45 d, 54 d y 27 d, como en el diagrama).
- **DFS**: detecta ciclos. Marca *Simular recaída* para ver cómo una recaída crea un ciclo y el alta ya no se puede fechar.
- Editar días de una etapa, `+1` / `-1`, restablecer y cargar otro JSON.

## Ejecutar
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   
pip install -r requirements.txt
pytest          # pruebas automáticas
python app.py   # aplicación
```

## Formato del JSON (carpeta `datos/`)
```json
{
  "nombre": "Digestivo", "color": "#0ea5e9", "unidad": "día",
  "actividades": {
    "CON": {"nombre": "Consulta", "dias": 3, "requiere": []},
    "DBL": {"nombre": "Dieta blanda", "dias": 5, "requiere": ["EXH"], "gravedad": "leve", "costo": "$"},
    "PRO": {"nombre": "Probióticos", "dias": 7, "requiere": ["DBL"], "paralela": true}
  },
  "recaida": {"id": "RDG", "nombre": "Recaída digestiva", "dias": 3, "desde": "CDG"}
}
```
