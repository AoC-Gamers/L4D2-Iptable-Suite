# Evidencia y límites de aceptación — 2026-10-11

Este informe conserva la entrega anterior. El [cierre H1–H3 del 12 de octubre](closure-plan-results.md)
amplía la evidencia con schema 2, topología Docker y barrera/readiness de arranque.
Los conteos de esta página pertenecen a su corrida histórica.

Base revisada: `aeabda7cbba25ecd94629797f5637a9a6987c147`, `main` inicialmente
limpio. Implementación en `security/modular-safe-apply`, entregada en `develop`.
La continuación partió de esa rama en
`6240a1c10ff3a0184feaec26c8e6d46d2e71988e`.
El `.env` local ignorado se conservó. No se aplicaron reglas ni se reiniciaron
Docker, redes, SSH o VPN del anfitrión.

## Entornos y aislamiento

La primera ejecución utilizó namespaces de usuario/red/montaje sobre Linux
`7.0.0-38-generic`, nftables `1.0.9`, iptables `1.8.10 (nf_tables)` y Python
`3.12.3`. El intento legacy falló por módulos ausentes: ese fallo se conserva
como evidencia histórica, no como aprobación.

La continuación empleó una VM QEMU/KVM **con kernel propio** y disco qcow2
superpuesto desechable. Ubuntu noble cloud image `20260926`, SHA256
`6a81c37564db9b1ee84e141922625e1d7c5b389b99bb3c572e0243607d5bb4d2`;
SHA256SUMS firmado verificado con el keyring Ubuntu cloud image, fingerprint
`D2EB44626FDDC30B513D5BB71A5D6C4C7DB87C81`. QEMU `8.2.2`; guest kernel
`6.8.0-142-generic`; systemd `255.4-1ubuntu8.17`; nftables `1.0.9`;
iptables/ip6tables `1.8.10`, frontends nft y legacy; OpenVPN `2.6.19`;
OpenSSL `3.0.13`; Docker Engine `29.8.2` (archivo estático oficial, SHA256
`995d1ef289677f74fd58d8d2c35727b6a4ee389c69db8638a3e42d0487aa5b0f`).

QEMU usa red de usuario, sin TAP/bridge del host, con SSH redirigido sólo a
loopback. Se cargaron módulos exclusivamente dentro del guest. Tráfico,
OpenVPN y Docker se ejecutan en namespaces de red/montaje anidados con `/run`
privado; Docker tiene socket, datos y procesos propios. Sólo el ensayo de
systemd/SSH/reboot opera sobre el firewall principal de esa VM desechable.
Los lanzadores exigen virtualización qemu/kvm y marcador root `0600` explícito.

## Resultados separados

| Capa | Ensayo reproducible | Resultado observado | Alcance |
|---|---|---|---|
| Unitarias | `test_core.py`, `test_geoip.py`, `test_transactions.py`, `test_configuration_audit.py`, `test_policy_audit.py` | 39 PASS | Parser, composición, tipos, confianza, plazos, datos y regresiones; sin demostrar kernel |
| Harness de SIGKILL / propiedad | `python3 -I tests/vm/test_transactions_harness.py` | 2 PASS | Ausencia de interbloqueo y comparación selectiva del propio ensayo; mocks |
| Runner VM | `python3 -I tests/vm/test_runner.py` | 13 PASS | Aislamiento de red/disco, token sin filtrar, exclusión de archivos privados y controles de transporte; mocks |
| Runner QEMU completo | `python3 -I tests/vm/run.py` | PASS, salida 0 | VM fresca, todas las fases obligatorias y limpieza legacy completadas; ningún SKIP aceptado |
| Watcher/HTTP | Scripts de pruebas y watcher-audit | PASS | Emisión, configuración y concurrencia simulada; no kernel |
| Generación | `bash tests/generate.sh` | 8 PASS | Cuatro perfiles, ambos motores, sin root |
| Comprobación kernel VM | `check-engine.py` mediante `isolated-run.sh --root-net`, matriz nft/legacy | 20 PASS | 10 candidatas por frontend, incluidos NAT/S2S |
| Integración/regresiones VM | `integration.py`, `transaction-flows.py`, `policy-flows.py`, matriz nft/legacy | 46 PASS | 17 + 2 + 4 casos por frontend; reglas reales, tráfico, recuperación y composición |
| Docker real | `tests/vm/docker.sh` | Cinco combinaciones soportadas PASS | DNAT TCP remapeado IPv4/IPv6, retorno, UDP independiente, conservación, idempotencia, egreso donde se administra |
| OpenVPN real | `tests/vm/clients.sh` | PASS ambos motores | TLS con certificados temporales, grants IPv4/IPv6, ruta S2S, alias DNAT y drop contado del origen no autorizado |
| GeoIP offline real | `tests/vm/geoip.sh` | PASS | ZIP `file://` → updater → CSV → nftables; tráfico permitido/denegado |
| systemd/SSH producción en guest | `tests/vm/transactions.py`, fases desde conexiones SSH distintas | PASS, incluidos dos reinicios completos | Confirmación desde SSH autenticado nuevo, SIGKILL postcommit, timeout sin confirmación, restore nftables y legacy IPv4/IPv6 |
| Sintaxis / ShellCheck / workflow | Bash/Python, ShellCheck 0.9.0 y actionlint 1.7.7 | PASS; 53 scripts Bash / 52 ShellCheck | No equivalen a ensayos de tráfico |
| CI remoto | Jobs separados, matriz nft/legacy y VM completa | Configurado | Su estado remoto se registra aparte; nunca inferido de la ejecución local |

Los casos POL incluyen también composición/timeout lógico; los 46 casos no son
46 flujos independientes de tráfico. nftables nativo se comprueba en ambas filas
de la matriz; no se contabiliza como un tercer frontend iptables. Los logs se
conservan bajo `tmp/vm/` (ignorado) y se copian a la entrega sin llaves ni tokens.
Detalles de Docker, clientes y transacciones: [vm-docker.md](vm-docker.md),
[vm-clients.md](vm-clients.md), [vm-transactions.md](vm-transactions.md).

## Ejecución del runner y fallos de preparación

Las pruebas manuales anteriores pasaron en la VM. Antes de aceptar el runner
nuevo se conservan también sus intentos fallidos: unitarias GeoIP y watcher
lanzadas como root, esquema cloud-init inválido, comprobación de propiedad sin
acceso al home privado y puerto loopback ocupado. Todos terminaron con salida
no cero.

Dos ejecuciones se interrumpieron deliberadamente para corregir los modos
ejecutables versionados y separar la cuenta unitaria de la cuenta con sudo.
Ninguna cuenta como aprobación. Un reintento posterior pasó todos los ensayos
de motor, tráfico, timer y ambos reinicios, pero el runner rechazó el nombre
JSON de la limpieza legacy; quedó fallido hasta corregir el contrato y añadir
una regresión.

Otra ejecución quedó interrumpida externamente antes del cierre. El runner y
QEMU terminaron, se conservó su log parcial y se retiraron sólo el overlay y
las credenciales temporales de esa ejecución. Tampoco se cuenta como aprobada.

Un reintento adicional falló porque la firma de conservación incluía los
contadores variables de cadenas builtin. Se normalizan sólo esos contadores;
las regresiones exigen que un cambio de política o regla ajena siga cambiando
la firma. Ese intento también permanece como fallo.

Se mantuvieron los controles de confianza del producto; los ajustes
corresponden al entorno y aislamiento de pruebas. La cuenta de cierre de
auditoría conserva sus diez IDs originales; las mejoras del harness nuevo no se
presentan como fallos preexistentes del producto.

La ejecución aceptada es `20261012T022119Z-164e7eae`, del 11 de octubre de
2026 (America/Santiago; final 02:27:59 UTC del día 12). Terminó con salida 0 y
`PASS runner completed all required validation cases; no SKIP case accepted`.
Incluyó la comparación corregida de reglas ajenas y ambas limpiezas. QEMU se
terminó y el directorio temporal quedó vacío: no quedan discos ni claves de
esa ejecución. El estado remoto de CI se registra aparte de esta aprobación
local completa.

## Implementado y probado con motor o tráfico real

Se comprueban configuración/ID/candidata inválidos sin cambios activos;
web/administración y routing IPv4/IPv6; idempotencia; SSH por origen; logging
acotado bajo ráfaga; UDP establecido alcanzando validaciones; A2S/login/SourceTV
sintéticos; timeout/SIGKILL/fallo tras commit IPv4 con recuperación; escritores
concurrentes; save/disable/load y retirada selectiva; conservación de reglas
ajenas incluso creadas mientras hay un cambio pendiente; gateway nativo sin
Docker; NAT sin permisos implícitos; protocolo TCP/UDP independiente; colisiones
de propiedad y Docker ausente rechazados antes de escribir.

La VM añade daemon Docker real en cinco combinaciones con publicaciones
IPv4/IPv6, clientes OpenVPN reales con TLS, S2S enrutado, GeoIP con datos sintéticos y SSH autenticado desde otra
conexión. El timer systemd de producción restaura tras SIGKILL y tras abandonar
el cambio pendiente. Dos reinicios completos con boot IDs distintos verifican
restauración nftables y después iptables-legacy IPv4/IPv6, mediante la unidad
real de arranque (Result=success, ActiveState=active) y digest persistido
idéntico. No se sustituyen estas pruebas por el watchdog de procesos del harness
original.

## Implementado, probado sólo de forma unitaria o lógica

Resolución DNS privilegiada cerrada ante fallos/respuestas fuera de CIDR: errores
inyectados mediante mocks, sin certificar un DNS externo real. Parser de
configuración y automatización, precedencia CLI/archivo, opciones retiradas,
metadata sin ejecutar módulos deshabilitados y reglas de duración del estado
incluyen cobertura unitaria. No toda combinación posible de opciones tiene
tráfico propio aunque su candidata sea aceptada por el kernel.

## Pendiente y riesgo residual

| Pendiente o límite | Evidencia que falta / riesgo residual |
|---|---|
| Clientes L4D2/SourceTV reales y descubrimiento completo | Hay paquetes A2S/login/TV sintéticos, no una sesión de jugadores ni cliente propietario. Validar con clientes/capturas representativos antes de desplegar juegos |
| Opciones OpenVPN aún sin tráfico propio | S2S con SNAT pasó comprobación kernel, pero el cliente S2S real ensayó NAT deshabilitado. TLS/S2S legacy no se ensayó; su NAT de servidor sí pasó tráfico de integración |
| PMTU representativo dentro de OpenVPN | La sesión TLS y los grants pasan, pero no se ensayaron tamaños/fragmentación/PMTU del túnel. Las ACL ICMP específicas requieren su propio ensayo |
| Otras versiones de Docker y escenarios de despliegue | IPv4/IPv6 publicado pasó en cinco combinaciones con Engine 29.8.2. No certifica otras versiones u overlays; el [cierre H1–H3](closure-plan-results.md) añade boot ordering solo para una combinación concreta; Swarm no está soportado por Docker nftables experimental |
| Exhaustión de todos los meters / logging durante horas | Hay capacidad efectiva, timeout y ráfagas reales; falta carga sostenida representativa. Los límites son por regla, no un presupuesto universal del host |
| Imagen GeoIP específica con datos MaxMind reales | El updater completo pasó con ZIP local sintético. No valida licencias, disponibilidad de descarga externa ni datos actuales de MaxMind |
| Atomicidad conjunta iptables | El motor hace commits por tabla/familia. Puede haber versiones mixtas hasta rollback; no restaura conexiones, conntrack, contadores ni tokens |
| Otros administradores concurrentes | El bloqueo serializa escritores de la suite, no programas externos. Los objetos registrados son de propiedad exclusiva; cambios ajenos fuera de ellos se conservan |

`--local` elige explícitamente operar sin watchdog remoto y requiere consola para
recuperar una interrupción. GeoIP reemplaza datos por archivo, no como una única
transacción multi-país. No se adoptan ni borran objetos heredados automáticamente.
Las comprobaciones sobre estas versiones no certifican cualquier host ni prometen
mitigar saturación del enlace.

## Auditoría iterativa

Tres agentes GPT-6 Luna con esfuerzo alto corrigieron **10 issues** desde
`148875e`, con una ronda cruzada final sin hallazgos nuevos confirmados. La
continuación con VM amplía la evidencia de integración; errores del harness nuevo
corregidos antes de su entrega no se cuentan como nuevos fallos del producto.
Registro de causas y regresiones: [iterative-audit.md](iterative-audit.md).
