# Observabilidad y análisis de logs

Los eventos `FW_EVT` describen lo que las reglas registraron, sujeto a presupuestos
y flags de logging. No equivalen a todos los paquetes ni demuestran ausencia de
bloqueos. Los límites de mensajes son por regla y el descarte sigue activo al
agotarse logs; el volumen total también depende del número de reglas.

[La guía de logs](log-summary.md) es canónica para resumen ligero, informes
detallados y el gestor venv aún disponible. Configuración del analizador es
independiente de la configuración declarativa del firewall. No mezcles `LOGFILE`
y `RSYSLOG_CONF` con sus claves.

Para investigar conectividad empieza por [diagnóstico](../testing/diagnostics.md),
política efectiva, contadores y una sonda permitida/denegada controlada. Publica
solo resultados saneados; logs, candidatos y capturas pueden identificar usuarios
y topología interna. [SECURITY](../../SECURITY.md) explica límites de reporte.
