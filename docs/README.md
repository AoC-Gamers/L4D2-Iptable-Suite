# Documentación de la suite

Empieza por tu objetivo. Las guías vigentes explican el comportamiento del núcleo
actual; el registro de aprobación identifica la evidencia fechada, separada de
los pasos operativos. Los ejemplos de configuración están en [`config/`](../config/) y
[`example.env`](../example.env), sin datos reales ni secretos.

| Objetivo | Recorrido |
|---|---|
| Primer despliegue | [Comenzar](getting-started/README.md) → [instalar y verificar](getting-started/installation.md) |
| Elegir permisos | [Configuración](configuration/README.md) → [perfiles](configuration/profiles.md) → [ACL](configuration/access-policy.md) → [referencia de variables](configuration/reference.md) |
| Proteger servicios | [SSH](administration/README.md), [web](web/README.md), [L4D2 y SourceTV](l4d2/README.md), [consultas Source](l4d2/source-queries.md) |
| Integrar redes | [Docker](docker/README.md), [VPN servidor/site-to-site](vpn/README.md) |
| Aplicar o recuperar | [Flujo de firewall](firewall/README.md), [transacciones](firewall/transactions.md), [persistencia y retirada](firewall/persistence.md) |
| Proteger el arranque | [Guardia y readiness](boot/README.md), [recuperación](boot/recovery.md) |
| Automatizar o analizar | [Automatización](automation/README.md), [IP pública](automation/public-ip-watch.md), [GeoIP](automation/geoip.md), [observabilidad](observability/README.md) |
| Desarrollar y verificar | [Arquitectura](architecture/README.md), [catálogo de módulos](architecture/modules.md), [pruebas](testing/README.md), [VM](testing/vm.md) |
| Diagnosticar compatibilidad | [Consulta pasiva y comprobaciones](testing/diagnostics.md), [matriz de motores](firewall/backends.md) |
| Revisar aceptación | [Seguridad](security/README.md), [aprobación](security/approval.md), [límites y pendientes](security/limitations.md) |
| Migrar | [Configuración/estado/firewall](migration/README.md), [mapa de rutas documentales](migration/documentation-map.md) |

Para contribuir: [CONTRIBUTING](../CONTRIBUTING.md). Para agentes:
[instrucciones raíz](../AGENTS.md) y [convenciones documentales](AGENTS.md).

[README del proyecto](../README.md) · [Integración y eliminación de rutas antiguas](migration/documentation-map.md).
