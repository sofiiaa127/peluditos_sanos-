import pytest
from ruta_critica.triaje import ColaPrioridad


def test_grave_se_atiende_antes_que_leve():
    c = ColaPrioridad()
    c.encolar("Luna", "Gato", "Digestivo", "leve")
    c.encolar("Max", "Perro", "Respiratorio", "grave")
    assert c.atender().nombre == "Max"


def test_orden_completo_por_gravedad():
    c = ColaPrioridad()
    for n, g in [("A", "leve"), ("B", "moderada"), ("C", "grave"), ("D", "leve"), ("E", "grave")]:
        c.encolar(n, "Perro", "Digestivo", g)
    assert [c.atender().nombre for _ in range(5)] == ["C", "E", "B", "A", "D"]


def test_empate_respeta_orden_de_llegada():
    c = ColaPrioridad()
    for n in ["Uno", "Dos", "Tres"]:
        c.encolar(n, "Gato", "Dermatológico", "moderada")
    assert [c.atender().nombre for _ in range(3)] == ["Uno", "Dos", "Tres"]


def test_ver_siguiente_no_saca():
    c = ColaPrioridad()
    c.encolar("Toby", "Perro", "Antiparasitario", "grave")
    assert c.ver_siguiente().nombre == "Toby"
    assert len(c) == 1


def test_cola_vacia():
    with pytest.raises(IndexError):
        ColaPrioridad().atender()


def test_gravedad_invalida():
    with pytest.raises(ValueError):
        ColaPrioridad().encolar("Kira", "Gato", "Digestivo", "urgente")
