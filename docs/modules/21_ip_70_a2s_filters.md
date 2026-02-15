Módulo 21 — ip_70_a2s_filters.sh

Descripción:
Este módulo aplica filtros específicos para consultas A2S (protocolo de consulta de servidores de juego, p. ej. Steam A2S) usando `iptables`. Normaliza y limita las consultas entrantes, aplica rate-limiting y protege contra amplificación o spam de consultas.

Contextos recomendados:
- Usar en servidores de juego que respondan a consultas públicas A2S para evitar abuso y altas tasas de peticiones.
- Aplicar límites por IP y mecanismos de caché en la aplicación cuando sea posible; ajustar umbrales mediante pruebas con tráfico real.
- Complementar con monitoreo y medidas a nivel de aplicación; no depender solamente del filtrado en el host.
