# Auditoría iterativa de flujos

Este registro conserva rondas históricas y sus entornos. La sección final
[continuación con kernel propio](#continuación-con-kernel-propio) amplía la
evidencia inicial. El [cierre posterior H1–H3](closure-plan-results.md) registra
la evidencia aceptada del 12 de octubre y sus límites; los
[resultados anteriores](results.md) conservan esta entrega histórica.

Fecha: 2026-10-11. Punto de partida: `148875e272783e24cdd517d818f7f7992a24ab76`,
rama `security/modular-safe-apply`, sin cambios locales versionados al comenzar.
Tres agentes GPT-6 Luna con esfuerzo alto revisan configuración/automatización,
política y transacciones. El coordinador revisa los cambios y repite las pruebas.

Los identificadores agrupan causas, no cada variante o prueba del mismo fallo.
El cierre exige una corrección y una regresión reproducible. Las limitaciones
anteriores de `results.md` no se cuentan como issues nuevos resueltos.

## Registro de hallazgos

| ID | Consecuencia confirmada | Corrección / regresión |
|---|---|---|
| CFG-01 | `--only ''` seleccionaba un perfil pese a ser una selección CLI vacía explícita. | Distinguir ausencia de selección y selección vacía; cobertura CLI/composición. |
| CFG-02 | GeoIP en Compose ejecutaba como root sobre un checkout del usuario y los controles de confianza rechazaban configuración/destino. | Ejecutar con UID/GID propietario del volumen, conservando controles de confianza. |
| CFG-03 | El watcher leía estado antes del bloqueo y podía repetir recarga/hook después de otro proceso. | Serializar observación, lectura, comparación, recarga, hook y escritura; dos procesos sincronizados. |
| TX-01 | Desactivar exigía integración Docker aun cuando sólo debía retirar objetos registrados. | Omitir requisitos de integración para desactivación; conservar verificaciones de propiedad/motor. |
| TX-02 | Retirar un módulo ignoraba `--set ACCESS_POLICY=...` explícito e impedía retirar sus grants en la misma candidata. | Usar ACL nueva explícita; conservar ACL confirmada en ausencia de override. |
| TX-03 | Un comando de aplicación podía sobrepasar el plazo mientras el watchdog esperaba el bloqueo del escritor. | Presupuesto monotónico por comando; restaurar si expira antes de entregar confirmación. |
| TX-04 | La recarga iptables con estado persistente y kernel vacío rechazaba los hooks ausentes como si hubieran sido desplazados. | Permitir reconstrucción cuando no quedan cadenas registradas; mantener rechazo de hooks desplazados con objetos presentes. |
| TX-05 | Fallar al armar watchdog reescribía reglas activas aunque la candidata nunca se hubiera ejecutado. | Borrar sólo el journal si no comenzó ejecución; inyectar fallo y comprobar cero llamadas al escritor. |
| HAR-01 | El harness aislaba la red pero compartía `/run/xtables.lock` con el host: posible contención entre pruebas y administración externa. | Montar tmpfs privado en `/run` dentro del namespace de montaje y comprobar identidad distinta antes de ejecutar motores. |
| POL-01 | iptables ignoraba de hecho capacidades pequeñas del estado por origen: el kernel elevaba `htable-max` al tamaño implícito de la tabla hash. Con capacidad 16 aceptaba 24 orígenes, mientras nftables sólo aceptaba 16. | Emitir también tamaño de tabla explícito; comprobar capacidad por tráfico real web/juego TCP en ambos motores. |

**Cierre: 10 issues corregidos, 0 nuevos hallazgos confirmados en la ronda final.**
Detalles y comandos: `transaction-audit.md`, `configuration-audit.md` y
`policy-audit.md`. No se afirma que sea imposible encontrar fallos fuera del
alcance o las condiciones probadas.

## Rondas y evidencia de cierre

| Ronda | Trabajo | Nuevos issues confirmados |
|---|---|---|
| R1 | Lectura y reproducciones de selección, automatizaciones, aplicación, recuperación y propiedad; revisión del coordinador. | 8 (CFG-01..03, TX-01..05) |
| R2 | Correcciones y regresiones; pruebas adversariales de capacidad, grants y protocolos; revisión del aislamiento. | 2 (POL-01, HAR-01) |
| R3 | Revisiones cruzadas configuración ↔ transacciones ↔ política; inspección del coordinador y suite integrada. | 0 |

| Grupo | Archivos principales | Evidencia final |
|---|---|---|
| CFG-01 | `core/config.py` | CLI real sin privilegios: selección vacía no carga perfil; ausencia conserva fallback. |
| CFG-02 | `Makefile`, `geoip-updater/{docker-compose.yml,run-update.sh,.env.example}` | Configuración Compose offline y guard de propiedad en contenedor Debian sin red; unitarias. No ejecución completa de descarga/CSV. |
| CFG-03 | `scripts/network/public-ip-watch.sh` | Dos procesos con barrera y WAN/DDNS/firewall simulados: una comprobación, una recarga y un hook. |
| TX-01, TX-04 | `core/engine.py` | 2 casos de motor aislado, ambos backends: desactivar sin integración y cargar con kernel vacío. No equivale a reboot de VM. |
| TX-02 | `core/fw.py` | ACL nueva y retirada de servicio en una configuración recompuesta; unitaria. |
| TX-03, TX-05 | `core/{engine.py,store.py}` | Deadline/subprocess real acotado, wait ajustado y fallos inyectados; 8 unitarias TX en total. No se reproduce un kernel bloqueado. |
| POL-01 | `core/compiler.py` | 3 unitarias y capacidad efectiva con paquetes: 16 aceptados/8 bloqueados en web y juego TCP, ambos motores. |
| HAR-01 | `tests/isolated-run.sh` | Verificaciones de namespace y `/run` privado antes de todos los ensayos de kernel repetidos. |

El coordinador repitió: **39 unitarias** (21 núcleo, 3 GeoIP, 8 TX, 4 CFG,
3 POL), pruebas de watcher/HTTP y carrera, **8 generaciones**, **10 comprobaciones
de motor** y **23 casos en entorno aislado** (17 integración existente, 2 TX y 4
POL). Los casos POL incluyen también composición/timeout lógico; no todos son
ensayos de tráfico. ShellCheck 0.9.0 pasó sobre 49 scripts, Bash syntax sobre 50,
además de compileall, diff-check y actionlint 1.7.7. Sólo se excluyó de ShellCheck
el helper histórico `log-summary/venv.loggin.sh`, como en la entrega anterior.

Linux `7.0.0-38-generic`, nftables `1.0.9`, iptables `1.8.10 (nf_tables)`,
Python `3.12.3`. Los jobs nuevos de CI son obligatorios y respetan el frontend
solicitado; una dependencia o permiso ausente produce fallo, no skip aprobado.
No se ejecutó CI remoto. Los logs finales están en `tmp/iterative-audit/` y se
copian a la entrega de evidencia.

## Limitaciones de la primera ejecución

iptables-legacy sigue sin aprobarse localmente: el nuevo intento desde namespace
de usuario falla leyendo `/proc/net/ip_tables_names`; el intento anterior en
contenedor no tenía `ip6_tables`. No se cargaron módulos en el host para evitarlo.
Siguen pendientes Docker daemon real, timer systemd de producción, reboot completo
y clientes reales de SSH/L4D2/VPN, según `results.md`. El smoke de identidad GeoIP
no prueba su descarga/generación completa dentro de la imagen específica.

## Aislamiento del harness

La ruta de lock es una propiedad del filesystem, no del namespace de red.
Se confirmó con el manual instalado de iptables 1.8.10, sección `LOCK FILE`, y
la [documentación upstream de Netfilter sobre xtables.lock](https://git.netfilter.org/iptables/log/configure.ac?showmsg=1).
La comparación de dispositivo/inodo de `/run` falla si no se separó el montaje.
No se creó ni adquirió intencionalmente un lock del host para reproducir el fallo.
La regresión ejecuta motores sólo después de comprobar red y montaje privados.

Un plazo limita cuánto puede continuar la aplicación; no garantiza un tiempo
máximo de restauración si el kernel o un administrador externo bloquean el motor.
Los mocks de fallos y concurrencia no demuestran aceptación de reglas ni tráfico.

## Continuación con kernel propio

La continuación solicitada añade una VM QEMU/KVM desechable, Ubuntu noble imagen
20260926, kernel `6.8.0-142-generic`. La matriz completa pasa con iptables-nft y
legacy: **20 comprobaciones de candidatas y 46 casos de integración/regresión**.
El fallo legacy del entorno anterior se conserva como histórico; ya no limita
esta evidencia sobre el kernel nuevo. No se cargaron módulos en el anfitrión.

Cinco combinaciones con Docker Engine 29.8.2 real pasan DNAT remapeado IPv4/IPv6, retorno,
separación TCP/UDP, conservación e idempotencia; el egreso se verifica cuando
la suite lo administra. OpenVPN 2.6.19 con PKI temporal pasa grants v4/v6,
routing S2S y alias, con drop contado del origen no autorizado. El updater GeoIP
completo pasa usando ZIP local sintético y tráfico nftables real.

El timer systemd de producción pasa rollback tras SIGKILL postcommit y timeout
sin confirmación. Una nueva conexión SSH autenticada confirma la candidata.
Dos reinicios completos pasan restore nftables e iptables-legacy v4/v6 con
unidad real, boot IDs distintos y digest idéntico. Los detalles se registran en
`vm-transactions.md`.
Revisión cruzada del harness y pruebas nuevas no confirmaron issues adicionales
del producto. Los errores del código de pruebas nuevo se corrigieron antes de
entregarlo; no inflan la cuenta de **10 issues corregidos**.

Los límites actuales sustituyen a los de la ejecución inicial y están en
[results.md](results.md), [vm-clients.md](vm-clients.md) y
[vm-docker.md](vm-docker.md). Tráfico sintético de juego no certifica clientes
L4D2/SourceTV reales; tampoco se afirma un ensayo de carga prolongado.

El runner completo terminó aprobado en una VM fresca:
`20261012T022119Z-164e7eae`, salida 0, sin SKIP, con ambas limpiezas posteriores
a reboot. Se conserva la evidencia de los intentos fallidos e interrumpidos;
las mejoras del harness no inflan los diez IDs de auditoría cerrados. La última
revisión cruzada del código final confirmó cero issues adicionales.
