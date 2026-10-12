# Documentación del funcionamiento actual

Estas guías describen el núcleo transaccional y los dos motores actuales. Para
instalaciones anteriores, empezar por la migración. Los informes de auditoría
conservan resultados fechados; los comandos operativos están en las guías de uso.

| Necesidad | Guía |
|---|---|
| Comenzar sin privilegios | [README principal](../README.md) |
| Elegir perfiles, familias y permisos | [Configuración](configuration.md) |
| Preparar instalación, aplicar y confirmar | [Guía operativa](operations-guide.md) |
| Entender transacciones y rollback | [Operación del núcleo](security/operations.md) |
| Guardar, restaurar y retirar objetos propios | [ipp.sh](ipp.md) |
| Migrar reglas y opciones anteriores | [Migración](security/migration.md) |
| Comparar motores, IPv6 y Docker | [Capacidades](security/capabilities.md) |
| Revisar o desarrollar módulos | [Arquitectura](modular-loader-architecture.md), [catálogo](modules/README.md) |
| Automatizar IP pública y GeoIP | [Watcher](public-ip-watch.md), [GeoIP](../geoip-updater/README.md) |
| Ejecutar pruebas | [Validación](ai-compat-check.md), [VM desechable](security/vm-runner.md) |
| Consultar evidencia y pendientes | [Auditoría](operational-audit.md), [resultados](security/results.md), [issues](security/iterative-audit.md) |

Los ejemplos están en [`config/`](../config/) y [`example.env`](../example.env).
Sus direcciones/interfaces deben adaptarse al destino. El
[análisis de logs](../log-summary/docs/log-summary-container.md) tiene configuración
separada; sus variables no pertenecen al archivo del firewall.
