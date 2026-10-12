# Migración documental e inventario

Inventario previo al traslado: 12 de octubre de 2026. Rama de partida `main`,
commit `93096dea2d7854a4d580a0b4922d5d1426c8149e`, idéntico a la base aprobada.
Los dos workflows tenían modificaciones locales de Node 24: se conservan fuera
de los commits documentales. No se abrió ni modificó `.env` ni archivos ignorados.
No había instrucciones `AGENTS.md`, `AGENT.md`, `CLAUDE.md` o `GEMINI.md` versionadas
ni instrucciones de agentes en los ancestros de la instalación inspeccionados.

Esta tabla migra documentación, no configuración, estado ni reglas del firewall.
Para esas operaciones consultar [la migración funcional](README.md).
Las rutas antiguas conservan avisos directos, sin cadenas de traslado.
Las referencias entrantes se obtuvieron de los Markdown versionados y del escaneo
con `rg` de scripts, Makefile, configuración, unidades y workflows antes de mover.

| Ruta anterior | Tema y público | Estado previo | Destino canónico | Acción | Referencias entrantes relevantes |
|---|---|---|---|---|---|
| `README.md` | L4D2 Iptable Suite; operadores | vigente | `README.md` | conservar y actualizar | `docs/README.md`, `docs/ai-compat-check.md`, `docs/ipp.md`, `docs/iptables.rules.md`, `docs/modular-loader-architecture.md` |
| `docs/README.md` | Documentación del funcionamiento actual; operadores | vigente | `docs/README.md` | conservar y actualizar | `README.md`, `docs/ai-compat-check.md`, `docs/ipp.md`, `docs/iptables.rules.md`, `docs/modular-loader-architecture.md` |
| `docs/ai-compat-check.md` | Revisión de compatibilidad asistida: Docker y Netfilter; operadores | vigente | `docs/testing/diagnostics.md` | mover + aviso | `README.md`, `docs/README.md` |
| `docs/configuration.md` | Configuración, perfiles y permisos; operadores | vigente | `docs/configuration/README.md` | mover + aviso | `README.md`, `docs/README.md`, `docs/ai-compat-check.md`, `docs/modular-loader-architecture.md`, `docs/operations-guide.md` |
| `docs/ipp.md` | `ipp.sh`: administración y persistencia de la suite; operadores | vigente | `docs/firewall/persistence.md` | mover + aviso | `README.md`, `docs/README.md`, `docs/modular-loader-architecture.md`, `docs/operations-guide.md`, `log-summary/docs/iptable.loggin.md` |
| `docs/iptables.rules.md` | Backend iptables: comportamiento actual; operadores | vigente | `docs/firewall/iptables.md` | mover + aviso | `log-summary/docs/iptable.loggin.md`, `log-summary/docs/venv.loggin.md` |
| `docs/modular-loader-architecture.md` | Arquitectura modular y contrato del generador; operadores | vigente | `docs/architecture/README.md` | mover + aviso | `README.md`, `docs/README.md` |
| `docs/modules/01_preload.md` | `preload.sh` — compatibilidad retirada; mantenedores | vigente; disperso | `docs/architecture/modules.md#preloadsh` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/02_postload.md` | `postload.sh` — helper heredado; mantenedores | vigente; disperso | `docs/architecture/modules.md#postloadsh` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/03_chain_setup.md` | `chain_setup` — núcleo obligatorio; mantenedores | vigente; disperso | `docs/architecture/modules.md#chain-setup` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/04_whitelist.md` | `whitelist` — bypass privilegiado al host; mantenedores | vigente; disperso | `docs/architecture/modules.md#whitelist` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/05_allowlist_ports.md` | `allowlist_ports` — puertos adicionales al host; mantenedores | vigente; disperso | `docs/architecture/modules.md#allowlist-ports` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/06_openvpn.md` | OpenVPN — adaptación de firewall; mantenedores | vigente; disperso | `docs/architecture/modules.md#openvpn` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/07_tcp_ssh.md` | `tcp_ssh` — servicio SSH del host; mantenedores | vigente; disperso | `docs/architecture/modules.md#tcp-ssh` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/08_http_https_protect.md` | `http_https_protect` — HTTP/HTTPS; mantenedores | vigente; disperso | `docs/architecture/modules.md#http-https-protect` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/09_l4d2_udp_base.md` | `l4d2_udp_base` — estado UDP de juego; mantenedores | vigente; disperso | `docs/architecture/modules.md#l4d2-udp-base` | consolidar + aviso | `docs/modules/README.md`, `docs/source-query-bypass-policy.md` |
| `docs/modules/10_l4d2_packet_validation.md` | `l4d2_packet_validation` — validación UDP; mantenedores | vigente; disperso | `docs/architecture/modules.md#l4d2-packet-validation` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/11_l4d2_a2s_filters.md` | `l4d2_a2s_filters` — consultas UDP Source; mantenedores | vigente; disperso | `docs/architecture/modules.md#l4d2-a2s-filters` | consolidar + aviso | `docs/modules/README.md`, `docs/source-query-bypass-policy.md` |
| `docs/modules/12_finalize.md` | `finalize` — núcleo obligatorio; mantenedores | vigente; disperso | `docs/architecture/modules.md#finalize` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/13_ip_loopback.md` | `loopback` — núcleo obligatorio; mantenedores | vigente; disperso | `docs/architecture/modules.md#loopback` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/14_ip_l4d2_tcpfilter_chain.md` | `l4d2_tcpfilter_chain` — alias de compatibilidad; mantenedores | vigente; disperso | `docs/architecture/modules.md#l4d2-tcpfilter-chain` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/15_l4d2_tcp_protect.md` | `l4d2_tcp_protect` — TCP de juego/RCON; mantenedores | vigente; disperso | `docs/architecture/modules.md#l4d2-tcp-protect` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/16_docker_dns_egress.md` | `docker_dns_egress` — retirado, requiere migración; mantenedores | vigente; disperso | `docs/architecture/modules.md#docker-dns-egress` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/17_docker_monitor_egress.md` | `docker_monitor_egress` — retirado, requiere migración; mantenedores | vigente; disperso | `docs/architecture/modules.md#docker-monitor-egress` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/18_geo_country_filter.md` | `geo_country_filter` — GeoIP IPv4 para UDP de juego; mantenedores | vigente; disperso | `docs/architecture/modules.md#geo-country-filter` | consolidar + aviso | `docs/modules/README.md` |
| `docs/modules/README.md` | Módulos y composición actual; mantenedores | vigente; disperso | `docs/architecture/modules.md` | consolidar + aviso | `README.md`, `docs/README.md`, `docs/ai-compat-check.md`, `docs/ipp.md`, `docs/iptables.rules.md` |
| `docs/operational-audit.md` | Estado de auditoría operativa; mantenedores | histórico | `docs/archive/audits/2026-10-12-operational-status.md` | mover + aviso | `README.md`, `docs/README.md`, `docs/security/findings.md` |
| `docs/operations-guide.md` | Guía operativa; operadores | vigente | `docs/getting-started/installation.md` | mover + aviso | `README.md`, `docs/README.md`, `docs/ipp.md`, `docs/operational-audit.md` |
| `docs/public-ip-watch.md` | Vigilancia de IP pública; operadores | vigente | `docs/automation/public-ip-watch.md` | mover + aviso | `README.md`, `docs/README.md` |
| `docs/security/boot-protection.md` | Protección de arranque; operadores | vigente | `docs/boot/README.md` | mover + aviso | `docs/README.md`, `docs/security/capabilities.md`, `docs/security/closure-plan-results.md`, `docs/security/migration.md`, `docs/security/operations.md` |
| `docs/security/capabilities.md` | Capacidades y convivencia; operadores | vigente | `docs/firewall/backends.md` | mover + aviso | `README.md`, `docs/README.md`, `docs/ai-compat-check.md`, `docs/configuration.md`, `docs/iptables.rules.md` |
| `docs/security/closure-h1.md` | Cierre H1: recorrido iptables hacia Docker; mantenedores | histórico | `docs/archive/audits/h1-docker-topology.md` | mover + aviso | sin enlace entrante detectado |
| `docs/security/closure-h2.md` | Cierre H2 — configuración canónica y migración de estado; mantenedores | histórico | `docs/archive/audits/h2-canonical-state.md` | mover + aviso | sin enlace entrante detectado |
| `docs/security/closure-h3-testing.md` | H3 boot-closure VM test; operadores | vigente | `docs/testing/boot.md` | mover + aviso | `docs/security/vm-runner.md` |
| `docs/security/closure-h3.md` | Cierre H3 — barrera explícita y disponibilidad durante el arranque; mantenedores | histórico | `docs/archive/audits/h3-boot-closure.md` | mover + aviso | `README.md`, `docs/README.md`, `docs/ipp.md`, `docs/security/boot-protection.md`, `docs/security/capabilities.md` |
| `docs/security/closure-plan-results.md` | Resultados del plan AOC-FW-IMP-003 — H1–H3; mantenedores | histórico | `docs/archive/audits/h1-h3-plan-results.md` | mover + aviso | `README.md`, `docs/README.md`, `docs/ipp.md`, `docs/operational-audit.md`, `docs/security/boot-protection.md` |
| `docs/security/configuration-audit.md` | Auditoría de selección y automatización; mantenedores | histórico | `docs/archive/audits/configuration-audit.md` | mover + aviso | `docs/security/iterative-audit.md` |
| `docs/security/findings.md` | Matriz inicial — 2026-10-11; mantenedores | histórico | `docs/archive/audits/2026-10-11-findings.md` | mover + aviso | `docs/operational-audit.md` |
| `docs/security/harness-audit.md` | HAR-01: aislamiento del lock de xtables; mantenedores | histórico | `docs/archive/audits/harness-audit.md` | mover + aviso | sin enlace entrante detectado |
| `docs/security/iterative-audit.md` | Auditoría iterativa de flujos; mantenedores | histórico | `docs/archive/audits/2026-10-11-iterative-audit.md` | mover + aviso | `docs/README.md`, `docs/operational-audit.md`, `docs/security/results.md` |
| `docs/security/migration.md` | Migración desde aeabda7; operadores | vigente | `docs/migration/README.md` | mover + aviso | `README.md`, `docs/README.md`, `docs/ai-compat-check.md`, `docs/configuration.md`, `docs/iptables.rules.md` |
| `docs/security/operations.md` | Operación del núcleo transaccional; operadores | vigente | `docs/firewall/transactions.md` | mover + aviso | `README.md`, `docs/README.md`, `docs/ai-compat-check.md`, `docs/configuration.md`, `docs/ipp.md` |
| `docs/security/policy-audit.md` | Auditoría de política efectiva; mantenedores | histórico | `docs/archive/audits/policy-audit.md` | mover + aviso | `docs/security/iterative-audit.md` |
| `docs/security/results.md` | Evidencia y límites de aceptación — 2026-10-11; mantenedores | histórico | `docs/archive/audits/2026-10-11-results.md` | mover + aviso | `README.md`, `docs/README.md`, `docs/ai-compat-check.md`, `docs/ipp.md`, `docs/iptables.rules.md` |
| `docs/security/transaction-audit.md` | Revisión del ciclo transaccional; mantenedores | histórico | `docs/archive/audits/transaction-audit.md` | mover + aviso | `docs/security/iterative-audit.md` |
| `docs/security/vm-clients.md` | Pruebas de clientes en VM desechable; operadores | vigente | `docs/testing/clients.md` | mover + aviso | `docs/operational-audit.md`, `docs/security/iterative-audit.md`, `docs/security/results.md` |
| `docs/security/vm-docker.md` | Validación con Docker real en VM QEMU; operadores | vigente | `docs/testing/docker.md` | mover + aviso | `docs/operational-audit.md`, `docs/security/capabilities.md`, `docs/security/iterative-audit.md`, `docs/security/results.md` |
| `docs/security/vm-runner.md` | Runner QEMU de validación completa; operadores | vigente | `docs/testing/vm.md` | mover + aviso | `README.md`, `docs/README.md`, `docs/security/closure-plan-results.md` |
| `docs/security/vm-transactions.md` | QEMU transaction and boot integration exercise; operadores | vigente | `docs/testing/transactions.md` | mover + aviso | `docs/operational-audit.md`, `docs/security/findings.md`, `docs/security/iterative-audit.md`, `docs/security/results.md` |
| `docs/source-query-bypass-policy.md` | Política de clasificación y bypass para consultas Source; operadores | vigente | `docs/l4d2/source-queries.md` | mover + aviso | `docs/modules/11_l4d2_a2s_filters.md` |
| `geoip-updater/README.md` | Actualizador GeoIP; operadores | vigente | `docs/automation/geoip.md` | mover + aviso | `README.md`, `docs/README.md`, `docs/ai-compat-check.md`, `docs/ipp.md`, `docs/iptables.rules.md` |
| `log-summary/docs/iptable.loggin.md` | iptable.loggin.py - Sistema de Logging y Análisis de Ataques; mantenedores | sustituido; histórico | `docs/archive/audits/legacy-log-analyzer.md` | mover + aviso | `log-summary/docs/venv.loggin.md` |
| `log-summary/docs/log-summary-container.md` | Contenedor de Resumen de Logs (Resúmenes Rápidos de Ataques); operadores | vigente | `docs/observability/log-summary.md` | mover + aviso | `README.md`, `docs/README.md` |
| `log-summary/docs/venv.loggin.md` | log-summary/venv.loggin.sh - Gestor de Entorno Virtual para iptable.loggin.py; mantenedores | sustituido; histórico | `docs/archive/audits/legacy-venv-manager.md` | mover + aviso | `log-summary/docs/iptable.loggin.md` |

## Referencias y material fuera de Markdown

| Ruta | Tema/público y estado | Destino/acción | Referencias relevantes |
|---|---|---|---|
| `example.env` | Ejemplo declarativo vigente; operadores | Corregir únicamente comentarios a configuración, migración y persistencia | README/configuración |
| `systemd/l4d2-firewall{,-guard,-ready}.service` | Unidades opt-in vigentes | Solo `Documentation=` hacia `docs/boot/README.md` | Guía de arranque |
| `systemd/l4d2-public-ip-watch.service` | Watcher vigente | Solo `Documentation=` hacia `docs/automation/public-ip-watch.md` | Automatización |
| `systemd/examples/`, timer watcher | Ejemplos vigentes | Conservar comandos, orden y dependencias; enlazar desde arranque/automatización | Sin otras rutas Markdown a corregir |
| `ipp.sh` | CLI vigente | Corregir solo referencia documental en ayuda | `docs/firewall/transactions.md` |
| `tests/vm/transactions.py`, `closure_boot.py` | Arnés vigente | Solo rutas en docstrings a `docs/testing/transactions.md`, `boot.md` | No cambiar aserciones |
| `Makefile` | Operación/pruebas vigentes | Conservar; explicar efectos de targets en guías | No contiene rutas Markdown |
| `.github/workflows/*.yml` | CI vigente + Node 24 local pendiente | Conservar sin incluir cambios locales en commits | No contiene rutas Markdown |
| `config/`, ejemplos de updater/log-summary | Ejemplos vigentes | Conservar valores efectivos y enlazar como fuente | Referencia de configuración |
| `scripts/`, `core/`, `modules/` restantes | Código vigente | Conservar; no hay otras referencias documentales que trasladar | Guías por responsabilidad |
| `log-summary/summary_example/` | Capturas de salida de ejemplo | Conservar como muestras, no evidencia de ejecución actual | Observabilidad |
| `reports/live-captures/` | Capturas versionadas | Conservar; no inspeccionar/publicar su contenido en esta tarea | No usar como aprobación de clientes reales |
| Instrucciones de agentes | Ausentes al partir | Crear raíz y `docs/AGENTS.md`; reglas particulares en `tests/` y `systemd/` | CONTRIBUTING y testing/boot |
| Licencia separada | No se encontró archivo versionado de licencia | Conservar créditos del README; no inventar una licencia | SirPlease/IPTables y comunidad |

## Decisiones de estructura

Se consolidan las dieciocho fichas numeradas en `architecture/modules.md`, con
anclas estables por ID y enlaces a guías operativas. Los avisos conservan las rutas
numeradas publicadas. Las fichas no se mantienen como dieciocho manuales paralelos.
Servidor y site-to-site caben en una guía `vpn/README.md`; SourceTV comparte guía
con GameServer, con sección propia. Instalación y transacciones tienen públicos
distintos: pasos del operador frente a contrato técnico de aplicación/recuperación.
Los diseños de ensayos VM siguen vigentes en `testing/`; sus resultados fechados
permanecen en el archivo, sin actualizar su alcance a partir de nuevas corridas.
Los manuales anteriores de logs/venv se archivan como referencia de esa documentación,
no como declaración de retirada del analizador, que continúa disponible.

Al versionar los traslados se normalizaron espacios finales de los dos manuales
legacy y una línea vacía final del catálogo. Son ajustes de formato; las fechas,
comandos históricos, resultados y afirmaciones se conservan sin cambios de fondo.
