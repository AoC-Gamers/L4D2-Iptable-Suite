Módulo 10 — nf_70_a2s_filters.sh

Descripción:
Este módulo implementa filtros específicos para consultas A2S (protocolo de consulta de servidores de juegos, p. ej. Steam A2S) en `nftables`. Normaliza y limita las consultas entrantes, aplica rate-limiting y protege contra amplificación o spam de consultas.

Contextos recomendados:
- Usar en servidores de juego que respondan a consultas públicas A2S para evitar abuso y altas tasas de peticiones.
- Aplicar límites por IP y mecanismos de cacheo en la aplicación cuando sea posible; probar reglas con tráfico de prueba para afinar umbrales.
- No eliminar otras protecciones de aplicación: combinar con validaciones a nivel de aplicación y monitoreo.
