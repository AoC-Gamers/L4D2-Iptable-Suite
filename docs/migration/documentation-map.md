# Integración de documentación y retirada de rutas antiguas

La documentación vigente usa una fuente canónica por funcionalidad. El 12 de
octubre de 2026, por decisión del mantenedor, se retiraron los informes archivados
y wrappers documentales después de revisar su contenido. Se eliminaron 52 avisos
de traslado, 14 informes/manuales y su índice, el README local redundante de logs
y el informe de la tarea de reorganización: **69 páginas**. Las rutas antiguas
dejan de resolver; actualiza bookmarks y enlaces externos desde el
[índice canónico](../README.md). No hay redirecciones ni avisos encadenados.

Este cambio parte de `1a47636` en `docs/feature-based-documentation`. No elimina
entrypoints ejecutables, componentes de logs/GeoIP, capturas ni pruebas. No cambia
políticas, valores de configuración, persistencia o comportamiento del firewall.
La actualización de los dos workflows a Node 24 se versiona por separado de la
integración documental.

## Evaluación del archivo retirado

Los nombres de origen siguientes pertenecían a `docs/archive/audits/` en
`1a47636`; no son rutas vigentes. Se integra información aplicable, sin trasladar
manuales completos ni diarios de ejecución a nuevas carpetas.

| Documento retirado | Evaluación y destino de la información útil |
|---|---|
| `2026-10-11-findings.md` | La matriz inicial describe código sustituido. Los contratos corregidos están en [configuración](../configuration/README.md), [migración funcional](README.md), [transacciones](../firewall/transactions.md) y [capacidades](../firewall/backends.md). No se presenta el estado inicial como defecto actual. |
| `2026-10-11-iterative-audit.md` | Diez IDs cerrados y cuenta acotada en [aprobación](../security/approval.md); causas/contratos y enlaces a regresiones en [testing](../testing/README.md#regresiones-conservadas). Rondas y logs intermedios quedan en Git. |
| `2026-10-11-results.md` | Entornos, run previo y fallos no contados como PASS en [aprobación](../security/approval.md); límites DNS, MaxMind, VPN, juego/carga y atomicidad en [limitaciones](../security/limitations.md). Los conteos antiguos no sustituyen al run del commit aprobado. |
| `2026-10-12-operational-status.md` | Resumen duplicado de resultados y pendientes: integrado en [aprobación](../security/approval.md) y [limitaciones](../security/limitations.md), sin otra página de estado paralelo. |
| `configuration-audit.md` | Selección vacía en [perfiles](../configuration/profiles.md); UID/GID GeoIP en [automatización](../automation/geoip.md); observación bajo lock en [watcher](../automation/public-ip-watch.md). Regresiones CFG conservadas. |
| `transaction-audit.md` | Deadline, fallo de armado sin restore innecesario, disable sin Docker, carga con kernel vacío y remove con ACL explícita en [transacciones](../firewall/transactions.md) y [persistencia](../firewall/persistence.md). Regresiones TX conservadas. |
| `policy-audit.md` | Tamaño y máximo de hashlimit explícitos en [configuración](../configuration/README.md); ensayo de capacidad y límites en [testing](../testing/README.md#regresiones-conservadas). No se infiere carga sostenida del ensayo de 24 orígenes. |
| `harness-audit.md` | Netns y montaje privado de `/run` para xtables.lock en [testing](../testing/README.md); helper y regresión HAR conservados. Los permisos fallidos de legacy inicial no acreditan aprobación. |
| `h1-docker-topology.md` | Salto único/incondicional/primero por familia, diagnóstico y retirada sin reparar reglas externas en [Docker](../docker/README.md), [motores](../firewall/backends.md) y [pruebas](../testing/docker.md). |
| `h2-canonical-state.md` | Traducción solo al ingresar, schema 2 y migración en memoria sin reabrir ACL/DNS ni alterar snapshot en [migración funcional](README.md), [configuración](../configuration/README.md) y [persistencia](../firewall/persistence.md). |
| `h3-boot-closure.md` | Barrera opt-in, readiness, recuperación, versiones y adaptación real de ExecStop en [arranque](../boot/README.md), [recuperación](../boot/recovery.md) y [migración](README.md). B01/B02 solo unitarios en aprobación/límites. |
| `h1-h3-plan-results.md` | Matriz de cierre, commits/runs y evidencia separada en [aprobación](../security/approval.md); fases y comprobaciones reproducibles en [H3 VM](../testing/boot.md) y [transacciones VM](../testing/transactions.md). El run de `0d20286` y sus 178 sondas siguen distinguidos del aprobado exacto y sus 354 intentos. |
| `legacy-log-analyzer.md` | Variables reales, seis informes, interpretación de fechas/eventos, permisos y diagnóstico integrados en [logs](../observability/log-summary.md). Se descartan prefijos rsyslog obsoletos, chmod público, bypass por estadísticas y umbrales universales no demostrados. |
| `legacy-venv-manager.md` | Menú, directorio venv, dependencias, efectos de instalación y `.env` raíz automático en [logs](../observability/log-summary.md). Se descartan promesas de sudo automático/multiplataforma y comandos duplicados o inconsistentes con el código. |

## Consolidación de puntos de entrada

Las fichas numeradas de `docs/modules/` se sustituyen por el
[catálogo de arquitectura](../architecture/modules.md). Las guías antiguas planas
se encuentran ahora por funcionalidad: [instalación](../getting-started/installation.md),
[configuración](../configuration/README.md), [firewall](../firewall/README.md),
[pruebas](../testing/README.md), [automatización](../automation/README.md) y
[logs](../observability/log-summary.md). También se retiraron los README de GeoIP
y logs que solo duplicaban esa navegación. Los README actuales aportan orientación
propia; no son wrappers de rutas anteriores.

El informe puntual de la reorganización se retiró después de conservar sus dos
observaciones funcionales, evidencia y riesgo residual en
[limitaciones](../security/limitations.md#incidencias-funcionales-pendientes).
No se corrigió código de producto dentro del cambio documental. Instrucciones de
agentes y CONTRIBUTING reflejan la estructura actual sin imponer mantener un archivo
paralelo. El verificador exige que todas las páginas sean alcanzables desde el índice,
sin excepciones de compatibilidad para avisos antiguos.

## Recuperar contexto histórico

Desde raíz del checkout, sin root, los siguientes comandos solo consultan Git:

```sh
git show 1a47636:docs/archive/audits/h1-h3-plan-results.md
git show 1a47636:docs/migration/documentation-review.md
git ls-tree -r --name-only 1a47636 -- docs/archive/audits docs/modules
```

Usa los originales para estudiar una ejecución pasada, no como recetas de despliegue.
Git conserva textos, fechas y fallos; los artifacts externos siguen sujetos a su
retención. La [aprobación](../security/approval.md) mantiene las referencias al commit
exacto, resultados separados por capa y sus límites. Esta limpieza no constituye
una nueva ejecución de motor/tráfico ni una nueva aceptación de seguridad.
