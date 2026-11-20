import pytest
from ruta_critica.cpm import (
    CicloError, armar_plan, buscar_ciclo, calcular, cargar_enfermedad,
    dijkstra, duracion_total, orden_topologico, ruta_critica,
)

ENF = ["antiparasitario", "respiratorio", "dermatologico", "digestivo"]
ALTAS = {"antiparasitario": "ALA", "respiratorio": "ALR", "dermatologico": "ALD", "digestivo": "ALG"}


def cargar(nombre):
    return cargar_enfermedad(f"datos/{nombre}.json")


@pytest.mark.parametrize("nombre", ENF)
def test_orden_respeta_dependencias(nombre):
    plan = armar_plan(cargar(nombre), "moderada")
    pos = {a: i for i, a in enumerate(orden_topologico(plan))}
    for act, d in plan.items():
        for req in d["requiere"]:
            assert pos[req] < pos[act]


@pytest.mark.parametrize("nombre,dias", [
    ("antiparasitario", 68), ("respiratorio", 45), ("dermatologico", 54), ("digestivo", 27)])
def test_dijkstra_coincide_con_el_diagrama(nombre, dias):
    enf = cargar(nombre)
    total, camino = dijkstra(enf["actividades"], "CON", ALTAS[nombre])
    assert total == dias
    assert camino[0] == "CON" and camino[-1] == ALTAS[nombre]


def test_ruta_critica_antiparasitario_leve():
    r = calcular(armar_plan(cargar("antiparasitario"), "leve"))
    assert duracion_total(r) == 68
    assert ruta_critica(r) == ["CON", "EXM", "PLN", "IDP", "PAS", "EXC", "ALA"]
    assert r["REF"].holgura == 15


def test_gravedad_cambia_la_duracion():
    enf = cargar("antiparasitario")
    assert duracion_total(calcular(armar_plan(enf, "grave"))) == 98
    assert duracion_total(calcular(armar_plan(enf, "moderada"))) == 83


def test_plan_solo_tiene_una_opcion():
    plan = armar_plan(cargar("digestivo"), "grave")
    assert "HSU" in plan and "DBL" not in plan and "MED" not in plan


def test_retraso_en_critica_retrasa_el_alta():
    plan = armar_plan(cargar("digestivo"), "leve")
    plan["CDG"]["dias"] += 4
    assert duracion_total(calcular(plan)) == 31


def test_retraso_dentro_de_la_holgura_no_afecta():
    plan = armar_plan(cargar("digestivo"), "leve")
    plan["PRO"]["dias"] += 5  # holgura de 7
    assert duracion_total(calcular(plan)) == 27


@pytest.mark.parametrize("nombre", ENF)
def test_recaida_forma_ciclo(nombre):
    plan = armar_plan(cargar(nombre), "leve", recaida=True)
    ciclo = buscar_ciclo(plan)
    assert ciclo and ciclo[0] == ciclo[-1]
    with pytest.raises(CicloError):
        calcular(plan)


def test_sin_recaida_no_hay_ciclo():
    assert buscar_ciclo(armar_plan(cargar("respiratorio"), "grave")) == []


def test_dependencia_inexistente():
    plan = armar_plan(cargar("respiratorio"), "leve")
    plan["COR"]["requiere"] = ["ZZZ"]
    with pytest.raises(ValueError):
        calcular(plan)
