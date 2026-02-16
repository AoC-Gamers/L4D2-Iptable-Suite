Módulo 11 — nf_finalize.sh

Descripción:
Este módulo ejecuta el cierre del backend `nftables`: emite el resumen final de aplicación y confirma parámetros operativos relevantes (`TYPECHAIN`, `TVSERVERPORTS`, `ENABLE_TCP_PROTECT`).

Contextos recomendados:
- Ejecutar siempre al final para tener trazabilidad clara del estado final.
- Mantenerlo no destructivo y centrado en cierre/reporting.
- Útil para diagnóstico rápido post-apply en despliegues y troubleshooting.

Notas:
- Ruta actual del módulo: `modules/nf_finalize.sh` (módulo raíz).
- El loader le da prioridad de ejecución final por sufijo `_finalize.sh`.
