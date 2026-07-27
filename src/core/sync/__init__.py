"""Modo offline del PDV (ADR-009): infraestructura del hub local de sucursal.

- `estado_conexion.py`: ¿el hub tiene camino a la nube?
- `contratos.py` + `registro.py`: qué entidades se replican hacia el hub.
- `exportador.py` / `importador.py`: lado nube y lado hub del pull.
- `cliente_nube.py`: el hub hablándole a la API de la nube como un cliente más.
- `motor.py` + `runner.py`: el ciclo (empujar, después jalar) y su proceso.
- `api/`: los endpoints que la nube expone a los hubs.

El motor no conoce ninguna entidad de negocio: cada módulo declara sus
recursos replicables en su `application/sincronizacion.py`.
"""
