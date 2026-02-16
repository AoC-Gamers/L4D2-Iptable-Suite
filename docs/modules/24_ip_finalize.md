Módulo 24 — ip_finalize.sh

Descripción:
Este módulo realiza el cierre del backend `iptables`: aplica reglas de cierre de política por defecto (`INPUT/FORWARD DROP`, `OUTPUT ACCEPT` según contexto), ejecuta verificación/recuperación de cadenas Docker cuando corresponde y emite un resumen operativo final.

Contextos recomendados:
- Ejecutar siempre al final de la secuencia de módulos `ip_*`.
- Útil para confirmar de forma explícita el estado final aplicado y variables críticas de operación.
- Mantenerlo enfocado en consolidación y reporting final, evitando reglas de negocio nuevas aquí.

Notas:
- Ruta actual del módulo: `modules/ip_finalize.sh` (módulo raíz).
- El loader le da prioridad de ejecución final por sufijo `_finalize.sh`.
