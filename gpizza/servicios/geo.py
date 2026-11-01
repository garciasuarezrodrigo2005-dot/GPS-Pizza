"""Cálculos geográficos sencillos para el mapa del cliente (boceto 5: "Llega en ~12 min")."""
from math import asin, cos, radians, sin, sqrt

RADIO_TIERRA_KM = 6371.0
VELOCIDAD_MOTO_KMH = 25.0   # velocidad promedio en ciudad
FACTOR_CALLES = 1.3          # las calles no van en línea recta


def coordenadas_validas(latitud, longitud) -> bool:
    try:
        return -90 <= float(latitud) <= 90 and -180 <= float(longitud) <= 180
    except (TypeError, ValueError):
        return False


def distancia_km(lat1, lon1, lat2, lon2) -> float:
    """Fórmula de Haversine: distancia en línea recta sobre la esfera terrestre."""
    lat1, lon1, lat2, lon2 = map(lambda v: radians(float(v)), (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 2 * RADIO_TIERRA_KM * asin(sqrt(a))


def minutos_estimados(lat1, lon1, lat2, lon2) -> int:
    km = distancia_km(lat1, lon1, lat2, lon2) * FACTOR_CALLES
    return max(1, round(km / VELOCIDAD_MOTO_KMH * 60))
