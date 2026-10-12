# Aprobación con observaciones — 12 de octubre de 2026

> Aprobado con observaciones dentro del alcance implementado y probado.
> La aceptación operativa de cada despliegue requiere validar su configuración,
> versiones, servicios e integración de arranque.

Decisión de cierre técnico del alcance revisado, no certificación externa.
**Commit aprobado:** `93096dea2d7854a4d580a0b4922d5d1426c8149e`.
Los cambios documentales posteriores no reciben automáticamente una nueva
aceptación funcional. No se hizo una nueva auditoría de seguridad al reorganizar.

## Cierre H1–H3

| Hallazgo | Estado dentro del alcance | Código y regresiones |
|---|---|---|
| H1: ruta efectiva Docker | Implementado/probado: preflight estructural por familia exige FORWARD→DOCKER-USER primero, único, incondicional, y hook propio primero; rechaza sin mover reglas externas | [engine.py](../../core/engine.py), [diagnose en fw.py](../../core/fw.py), [unitarios](../../tests/test_docker_topology.py), [tráfico](../../tests/docker-topology-flows.py) |
| H2: normalización y estado | Implementado/probado: traducción TYPECHAIN solo input, schema 2, migración en memoria, ACL parseada durable, partial/remove sin reinterpretar ni reabrir rutas | [config.py](../../core/config.py), [schema.py](../../core/schema.py), [store.py](../../core/store.py), [unitarios](../../tests/test_h2.py), [ciclo real](../../tests/h2-flows.py) |
| H3: arranque comprobado | Implementado/probado con integración opt-in: barrera independiente, boot ID/digest/fingerprint y readiness antes de consumidores; restore fallido conserva guard | [boot.py](../../core/boot.py), [unidades](../../systemd/), [unitarios](../../tests/test_boot.py), [tráfico guard](../../tests/boot-flows.py), [VM H3](../../tests/vm/closure_boot.py) |

## Trazabilidad de los cierres anteriores

Los informes completos anteriores se retiraron del árbol documental tras integrar
sus contratos vigentes en las guías. Se conservan en Git, revisión `1a47636`;
el [mapa de integración](../migration/documentation-map.md) identifica sus destinos.
Estos datos describen ensayos anteriores, no nuevas ejecuciones del HEAD actual:

| Hito | Evidencia histórica y límite |
|---|---|
| Revisión inicial, 2026-10-11 | Base `aeabda7cbba25ecd94629797f5637a9a6987c147`: aplicación destructiva, selección/composición, permisos y persistencia corregidos; contratos actuales en configuración, firewall y capacidades. |
| Auditoría iterativa desde `148875e272783e24cdd517d818f7f7992a24ab76` | Diez issues cerrados: CFG-01..03, TX-01..05, POL-01 y HAR-01. La última ronda acotada confirmó cero nuevos hallazgos; no demuestra ausencia universal de defectos. [Regresiones](../testing/README.md#regresiones-conservadas). |
| VM `20261012T022119Z-164e7eae` | Salida 0 sin SKIP, 20 comprobaciones de motor, 46 métodos de integración/regresión, cinco combinaciones Docker y dos reboots TX. No incluía el cierre posterior H3. |
| H1–H3, VM `20261012T053512Z-f950c62d` sobre `0d20286` | Salida 0 sin SKIP: 118 casos Python, 20 comprobaciones kernel, 58 métodos de integración/regresión, cinco combinaciones Docker y cuatro reboots. H3 registró 178 sondas (89 TCP + 89 UDP), cero respuestas no autorizadas, gaps máximos 0.953/0.952 s. No es el run del commit aprobado. |

La primera validación en namespaces sobre kernel `7.0.0-38-generic`, nftables
1.0.9 e iptables-nft 1.8.10 no pudo ejecutar legacy por permisos/módulos del
entorno. Tampoco acreditó Docker real ni reboots. Las corridas QEMU posteriores
con kernel propio ampliaron ese alcance; no convierten el intento fallido en PASS.
Los intentos de preparación fallidos o interrumpidos, las correcciones de
fixtures, orden de arranque y comparación de handles del arnés no se contabilizan
como ejecuciones aprobadas ni inflan la cuenta de issues del producto.

Después de la corrida sobre `0d20286`, se corrigieron los presupuestos temporales
del arnés (`72f8371`) y el acceso KVM del runner CI (`93096de`). La siguiente
ejecución del commit exacto se registra por separado y sustenta esta decisión.

## Evidencia del commit exacto

Reconsulta de API GitHub: **2026-10-12**, ambos runs `head_sha=93096dea…`,
`conclusion=success`:

- [Firewall validation, run 38214356935](https://github.com/AoC-Gamers/L4D2-Iptable-Suite/actions/runs/38214356935), terminado `2026-10-12T06:52:42Z`.
- [Disposable QEMU validation, run 38214356944](https://github.com/AoC-Gamers/L4D2-Iptable-Suite/actions/runs/38214356944), terminado `2026-10-12T07:04:50Z`.

El runner QEMU reportó salida satisfactoria completa a `07:04:46Z`, run-id
`20261012T064855Z-02d23fec`, sin SKIP aceptado. Artifact `qemu-validation-logs`
no estaba expirado al verificar; fecha de expiración anunciada `2026-10-26T07:04:46Z`.
Los enlaces a runs conservan metadata; **no garantizan retención de logs** después
de expirar el artifact. Si ya no está disponible, reproducir con el runner y
registrar nueva evidencia, sin inventar el contenido perdido.

| Capa | Resultado y límite |
|---|---|
| Revisión estática | Sintaxis Bash, Python y ShellCheck en CI aprobados; no prueban kernel/tráfico |
| Unitarios/mocks | 118 casos Python (103 guest + 15 runner anfitrión), incluyendo contratos del producto y arneses; no equivalen a 118 sesiones de tráfico |
| Generación | Candidatas de perfiles/servicios aprobadas sin privilegios; sin prometer conectividad |
| Comprobación motor | 20 comprobaciones kernel, diez por frontend; incluye variantes NAT/S2S cuya comprobación no acredita todos sus flujos |
| Tráfico aislado | 58 métodos de integración/regresión kernel, incluidos subcasos; SSH/web v4/v6, UDP establecido/A2S/TV sintéticos, independencia TCP/UDP, rollback/concurrencia/conservación |
| Daemons/clientes reales | Cinco combinaciones Docker en régimen normal, OpenVPN TLS y actualizador GeoIP con ZIP sintético offline; no cliente L4D2/SourceTV real ni base MaxMind actual |
| VM/systemd/reboots | Timer de producción, SIGKILL, abandono de sesión, conexión SSH nueva; dos reboots TX y dos H3 (cuatro total), persistencia válida/inválida, socket y Docker live-restore |
| Destino | No se validó cada configuración productiva; queda aceptación operativa por despliegue |

Entorno QEMU/KVM: Ubuntu Noble imagen `20260926`, kernel guest
`6.8.0-142-generic`, systemd `255.4-1ubuntu8.17`, Python 3.12, nftables 1.0.9,
iptables/ip6tables 1.8.10 (nft y legacy), OpenVPN 2.6.19, Docker 29.8.2.
Hashes fijados de imagen/Docker y reproducción: [runner VM](../testing/vm.md).
Se ejecutó KVM; no se acredita con este run una matriz final completa TCG.

H3 midió **354 intentos externos: 177 TCP y 177 UDP**, cero respuestas de aplicación
no autorizadas. Gaps máximos entre inicios: TCP `0.952676718 s`, UDP `0.952838911 s`.
La regla de cobertura exige ≤3 s, con controles positivos. No descarta ventanas
arbitrariamente breves ni certifica tráfico externo IPv6 durante reboots.
La combinación de arranque H3 fue **suite nftables + Docker iptables/frontend nft**;
las otras cuatro combinaciones solo tienen la evidencia Docker normal.

## Ensayo adicional de arneses en Debian 13

El **2026-10-12**, sobre fuentes de `3c34108aa0513479edb0266a48d734ced44ab1da`,
se corrigió el staging con `umask 0002` heredada: permisos privados, Python sin
cachés iniciales y exclusión de archivos no versionados. Tres nuevas regresiones
del wrapper usan herramientas simuladas; no acreditan el kernel. ShellCheck
0.9.0, sintaxis Bash, generación y regresiones unitarias/documentales pertinentes
pasaron localmente con Python 3.12.3. La nueva regresión también pasó con 3.13.5.

Los fuentes de los ocho scripts de ensayo afectados/utilizados se cotejaron por
SHA-256 contra ese commit. En una copia temporal, como usuario sin privilegios,
con namespaces de usuario/red/mount y `/run` privado, se ejecutó
`tests/isolated-run.sh --accept-version-change` para `check-engine.py`,
`integration.py`, `transaction-flows.py`, `policy-flows.py`,
`docker-topology-flows.py`, `h2-flows.py` y `boot-flows.py`, con
`SUITE_TEST_FRONTEND=nft` y máscara inicial `0002`.

Entorno: Debian 13, kernel `6.12.107+deb13-amd64`, Python 3.13.5,
nftables 1.1.3 e iptables/ip6tables 1.8.11 (`nf_tables`). Resultado final:
**10 comprobaciones de motor y 29 métodos de integración/regresión aprobados**
(17+2+4+4+1+1), ambos motores de la suite. Incluye tráfico sintético IPv4/IPv6,
SIGKILL, watchdog de proceso, concurrencia y conservación de objetos ajenos.
El ensayo de arranque comprueba el rechazo tras rollback a vacío y recuperación
mediante aceptación manual, según [testing](../testing/README.md).

Los intentos `legacy` fallaron por permisos al leer `/proc/net/ip_tables_names`;
no se cuentan como PASS ni amplían la matriz aprobada. Tampoco se ejecutaron
Docker real, QEMU, watchdog systemd o reboots en este ensayo. La copia instalada
y el firewall del anfitrión no se modificaron. Esta evidencia limitada no aprueba
iptables 1.8.11 para todos los flujos ni acredita una migración productiva remota.
Los errores intermedios corregidos del arnés no se cuentan como nuevos defectos
de la política del producto. No hubo un nuevo run de CI remoto en este cierre.

## Entrega heredada y nueva validación del 2026-10-12

La [entrega explícita](../migration/legacy-handover.md) añade una migración
acotada de una tabla `inet` propia: manifiesto revisado, comprobación de candidata
y snapshot, transacción única, bloqueo/journal comunes y watchdog independiente.
El rechazo ordinario de tablas sin registro ya era correcto y se conserva.

| Hallazgo del bloque | Resultado y regresión |
|---|---|
| Borrar por handle conserva conjuntos en la caché de evaluación de nft e impide cambiar capacidades | Confirmado y corregido en `core/legacy.py`: `delete` por handle seguido de `destroy` por nombre en el mismo lote. Capacidad 65535→8192 y handle obsoleto probados contra kernel; un handle inválido conserva la tabla de reemplazo |
| Bootstrap H3 unitario consulta rutas reales cuando ya existe el estado root `0700` | Confirmado y corregido en `tests/vm/test_boot_harness.py`: fixture temporal para constantes derivadas de STATE y unidades; regresión de todas las rutas inspeccionadas |
| Prueba de módulo deshabilitado modifica fuentes compartidos y deja código tras ejecuciones simultáneas | Confirmado y corregido en `tests/test_core.py`: catálogo de módulos privado por prueba, sin modificar el checkout |

Son **tres defectos corregidos durante este bloque**, además del flujo de migración.
Los commits funcionales son `520a0ca` y `49128a8`; `7ee3280` aísla la prueba de
módulo deshabilitado y `1a73761` añade comprobación real de la CLI `check`.

El run QEMU/KVM **`20261012T221315Z-30ceac7f`** terminó con código 0, sin SKIP.
Sus 184 fuentes empaquetados se cotejaron byte a byte contra
`0b56de79e089d1e32939f45189286a716b264d65`; SHA-256 del archivo:
`87dde3f4d103c62f9971cfad416a8d73f4b42f4eea94e5365c8f14262c949e68`.
Se aprobaron **112 métodos unitarios** como usuario sin privilegios,
**20 comprobaciones de motor**, **70 métodos kernel/tráfico** entre ambos
frontends, cinco combinaciones Docker, clientes OpenVPN, GeoIP offline, entrega
heredada con timer systemd/SSH nuevo y **cuatro reboots exclusivamente del guest**.
Versiones: Ubuntu Noble `20260926`, kernel `6.8.0-142-generic`, Python 3.12,
systemd `255.4-1ubuntu8.17`, nftables 1.0.9, iptables 1.8.10 (nft/legacy),
OpenVPN 2.6.19 y Docker 29.8.2. Logs locales sanitizados:
`tmp/vm-runner-artifacts/20261012T221315Z-30ceac7f/`.

H3 registró **328 intentos: 164 TCP y 164 UDP**, sin respuestas de aplicación no
autorizadas; gaps máximos de inicio `0.952194309 s` y `0.952269390 s`.
Conserva el límite de muestreo y la única combinación de arranque H3 descritos
arriba. Los dos runs anteriores interrumpido/fallido no acreditan la matriz completa.

Los únicos cambios de código posteriores a ese archivo QEMU son las dos pruebas
de `7ee3280`/`1a73761`; producto, unidades y reglas son idénticos. La primera pasó
sus 21 métodos localmente con Python 3.12.3; la segunda pasó los seis métodos de
`legacy-flows.py` en namespaces usuario/red/mount, `/run` privado y Debian 13,
kernel `6.12.107+deb13-amd64`, Python 3.13.5, nftables 1.1.3 e iptables 1.8.11/nft.
Una candidata del destino con copia de su tabla heredada también pasó aplicación,
expiración/restauración, confirmación, idempotencia y tráfico sintético dual en
ese aislamiento. ShellCheck 0.9.0 y sintaxis Bash de los scripts versionados,
generación y checks documentales pasaron localmente.

En el destino se instaló `1a73761` en `/opt`, root-owned, mediante Git y se
comprobó con nftables 1.1.3 antes de aplicar. La entrega se confirmó desde SSH
autenticado nuevo por un salto externo y el host de respaldo, con timer de 600 s;
la política quedó guardada y `ready` verificó el kernel. Cinco tablas Docker
ajenas conservaron su huella y el daemon mantuvo PID/inicio; configuración y
persistencia global no cambiaron. Una consulta A2S al servidor activo respondió
antes/después desde el origen privilegiado: acredita ese recorrido, no los
limitadores públicos. No hubo reboot ni reinicio de servicios del anfitrión.

**Pendiente operativo:** la integración de arranque nueva no se habilitó en ese
destino; su servicio nftables conserva la persistencia anterior. Guardar la nueva
política no cambia ese comportamiento. El watcher carece de verificador externo
configurado y rechaza recargas desatendidas. Las comprobaciones aisladas no
acreditan cada cliente real, carga sostenida ni toda ruta externa del destino.

## Condiciones y nueva revisión

Lee [limitaciones vigentes](limitations.md) antes de aceptar un destino. En especial:
opt-in de barrera/unidades y consumidores, orden real de Docker/ExecStop, conservación
frente a escritores externos, atomicidad parcial iptables, B01/B02 solo unitarios,
clientes reales de juego, PMTU/variantes VPN y carga sostenida pendientes.

Cambios de reglas, defaults, ACL, composición, schema, ownership, motor/frontend,
versiones, watchdog/rollback, unidades/orden de arranque, topología o servicios
requieren reevaluar el alcance afectado. `--accept-version-change` registra una
decisión explícita de mantenimiento; no sustituye pruebas ni migra frontend.
Equivalencia documental se revisa aparte mediante diff y checks; no vuelve a
etiquetar un run histórico como ejecución de otro HEAD.
