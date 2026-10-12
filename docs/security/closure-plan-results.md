# Resultados del plan AOC-FW-IMP-003 — H1–H3

Plan versión 1.0, 12 de octubre de 2026. Base verificada:
`9e1d1eb5aeb31d648a598543546386a1fb024686`. Se trabajó directamente en `main`
por instrucción expresa del operador, conservando el `.env` local ignorado.
No se aplicaron reglas ni se reiniciaron servicios del anfitrión.

Los **tres hallazgos del plan** quedaron implementados, con evidencia de kernel
y tráfico en el alcance descrito. Esto no certifica todas las combinaciones de
versiones, servicios o entornos. B01–B02 conservan límites de evidencia explícitos.
La revisión cruzada final de los agentes GPT-6 Luna, esfuerzo alto, no encontró
nuevos fallos funcionales confirmados dentro del alcance revisado.

## Hallazgos, cambios y regresiones

| Hallazgo / estado inicial | Consecuencia confirmada | Archivos y solución | Evidencia |
|---|---|---|---|
| H1 — Confirmado, condicionado por topología | Un ACCEPT anterior en FORWARD evita DOCKER-USER. | `core/engine.py`: parseo estructural; salto único, incondicional y primero por familia, hook propio primero; diagnóstico pasivo en `core/fw.py`. No reordena reglas ajenas. | `test_docker_topology.py`, `docker-topology-flows.py`; topología válida y rechazo sin cambios de topología insegura. |
| H2 — Confirmado | Reinterpretar TYPECHAIN al recomponer estado válido produce conflictos o cambia dimensiones. | `core/config.py`, `compiler.py`, `schema.py`, `fw.py`, `store.py`: traducción solo al ingresar, schema 2 canónico, migración en memoria y ACL efectiva sin reabrir paths/DNS. | `test_h2.py`, `h2-flows.py`; apply/save/load/partial/remove en ambos motores, host activo/desactivado, grants y snapshot conservados. |
| H3 — Confirmado, operativo | Un restore fallido puede dejar cargas activas sin política comprobada; el archivo persistido no acredita el kernel actual. | `core/boot.py`, `engine.py`, `store.py`, `fw.py`, unidades y ejemplos `systemd/`: barrera independiente, readiness por boot ID/digest/fingerprint y dependencias explícitas. | `test_boot.py`, `boot-flows.py`, `tests/vm/closure_boot.py`; fallos inducidos, SIGKILL, Docker, dos reboots H3 y cleanup. |

H1: `18484f5`. H2: `0bb84b6`, `5b19a84`, `f7464bf`. H3: `8852e4f`;
endurecimiento final del arnés: `4197239`, `e0ab4d8`, `4b7ba5b`, `44f9185`, `0d20286`. Se corrigieron también, dentro de
estos bloques, los defaults VPN que reinyectaban TYPECHAIN, la colisión con el
nombre reservado `inet l4d2_boot_guard` y el orden respecto de la carga inicial
opcional de `nftables.service`. Las mejoras y fallos del arnés se registran
aparte; no se suman artificialmente al conteo de tres hallazgos del plan.

## Ejecución aceptada y entorno

Corrida **`20261012T053512Z-f950c62d`**, salida **0**, final **2026-10-12T05:46:18+00:00**:
`PASS runner completed all required validation cases; no SKIP case accepted`.
El código ensayado corresponde a `0d20286`; el manifiesto de la entrega compara
103 archivos de código, configuración, unidades y pruebas con el archivo enviado
a la VM. Los cambios posteriores de cierre son documentales.

Ubuntu Noble cloud image `20260926`, SHA-256
`6a81c37564db9b1ee84e141922625e1d7c5b389b99bb3c572e0243607d5bb4d2`;
QEMU/KVM 8.2.2, kernel guest `6.8.0-142-generic`, systemd
`255.4-1ubuntu8.17`, Python `3.12`, nftables `1.0.9`, iptables/ip6tables
`1.8.10` con frontends nft y legacy, OpenVPN `2.6.19`, Docker `29.8.2`.
Docker estático oficial, SHA-256
`995d1ef289677f74fd58d8d2c35727b6a4ee389c69db8638a3e42d0487aa5b0f`.

La VM tiene kernel propio, disco superpuesto desechable y red SLIRP con forwards
solo en loopback. Motor/tráfico se prueban además en namespaces anidados. El
runner no toca interfaces, daemon Docker ni firewall del host. Al salir termina
solo su hijo QEMU y elimina overlay y credenciales temporales; conserva logs
saneados, sin `.env`, claves privadas ni tokens de confirmación.

| Capa | Resultado / alcance |
|---|---|
| Producto unitario | 76 PASS; configuración, composición, migración, propiedad, versiones, readiness. No demuestra Netfilter. |
| Harness unitario | TX 2 + H3 21 + cleanup 4 + runner 15 = 42 PASS. Total Python: **118**, de los cuales 103 corren también como cuenta sin sudo en la VM. |
| Watcher / HTTP / generación | PASS; 8 candidatas generadas sin root. |
| Comprobación kernel | **20 PASS**, diez candidatas por frontend, incluido NAT/S2S. |
| Integración / regresiones kernel | **58 métodos PASS**: 46 existentes + H1 8 + H2 2 + guard 2, matriz nft/legacy. H2 y guard contienen subcasos para ambos motores y familias. No son 58 sesiones independientes. |
| Docker real | **5 combinaciones PASS**, DNAT remapeado, retorno, TCP/UDP independiente, idempotencia y reglas ajenas. |
| OpenVPN / GeoIP | PASS; clientes TLS reales y ZIP offline sintético, manteniendo los límites de [resultados previos](results.md). |
| TX systemd / SSH | PASS; conexión administrativa nueva, watchdog, SIGKILL, expiración y dos reboots con restauración nftables y legacy IPv4/IPv6. |
| H3 systemd / Docker / reboots | PASS; fases obligatorias, un reinicio Docker y dos reboots H3 (persistencia inválida y válida), socket, recuperación SSH, guard y cleanup. |
| Sintaxis / lint | Bash 53 archivos, ShellCheck 0.9.0 (52 scripts; exclusión histórica del venv), Python y actionlint 1.7.7 PASS. `systemd-analyze verify` PASS en la VM sobre unidades instaladas. |
| CI remoto | Estado independiente de esta corrida local; consultar el run asociado al commit publicado. Ningún SKIP acredita éxito. |

## Matriz de aceptación del plan

**Real** significa motor, tráfico o proceso/filesystem según se indique;
**unitario** significa lógica o mocks. No se intercambian esas evidencias.

| ID | Resultado y prueba concreta |
|---|---|
| D01 | Real: topología válida, instalación/recarga y fuente autorizada/denegada; `docker-topology-flows.py::test_valid_topology_routes_only_authorized_source`. |
| D02 | Real: ACCEPT previo rechazado sin mover reglas; `test_forward_accept_before_docker_is_rejected_without_writes`. |
| D03–D04 | Unitario: condiciones, goto, prefijos desconocidos, duplicados, comentarios lookalike y familias/cadenas ausentes; `test_docker_topology.py`. No se atribuye tráfico a cada variante del parser. |
| D05 | Real: hook desplazado rechazado conservando regla externa; `test_moved_suite_hook_is_rejected_without_reordering_foreign_rule`. |
| D06 | Real: los cuatro métodos H1 pasan con iptables-nft y legacy 1.8.10; ambas familias se inspeccionan. La matriz Docker real es evidencia complementaria, no una versión distinta de iptables. |
| D07 | Unitario y real: nft nativo sin requisito DOCKER-USER; disable/retirada sin Docker y conservación de objetos ajenos. |
| C01–C02 | Real: cuatro subcasos H2 por frontend (dos motores × host activo/desactivado), ACL restrict y ciclo completo CLI. |
| C03 | Real: retirada con grant dependiente rechazada sin cambios; retirada coherente con ACL actualizada aceptada, `h2-flows.py`. |
| C04 | Unitario: TYPECHAIN válido, contradictorio y traducción única; `test_h2.py`. |
| C05 | Unitario y real: current/persisted/pending schema 1 migrados, ACL/frontend/snapshot conservados y rollback; `test_h2.py`, `h2-flows.py`. |
| C06 | Real de proceso/filesystem: SIGKILL antes del reemplazo atómico conserva bytes de current/pending y snapshot; `test_interrupted_schema_migration_preserves_original_file_and_pending_snapshot`. Esquemas inválidos fallan cerrados. Este caso no demuestra kernel ni pérdida eléctrica. |
| C07 | Unitario y real: partial de tasa conserva dimensiones, grants y permisos; sin volver a resolver DNS/reabrir ACL normalizada. |
| B01 | **Solo unitario**: clasificador de versión/vendor, aceptación de mantenimiento y metadata. No se ejecutaron binarios de otra versión real. |
| B02 | **Solo unitario**: rechazo de cambio frontend o mezcla IPv4/IPv6. Se probaron ambos frontends reales por separado, pero no un reboot con binarios deliberadamente mezclados. |
| B03 | Real VM: candidata inválida y nft temporalmente ausente; readiness/socket denegados y guard comprobado con el ejecutable original mientras el nombre normal sigue ausente; recuperación válida. |
| B04 | Real VM: persistencia ausente/corrupta/desconocida en activación; reboot con schema 999 conserva guard, bloquea socket/contenedor y permite SSH nuevo de recuperación. Bytes válidos restaurados exactamente antes del siguiente arranque. |
| B05 | Real VM: socket dependiente de readiness, probes veth bloqueados con guard y positivos tras restore; arranque válido automático sin recrear red/socket desde el chequeo SSH. El monitor externo continuo se limita a las publicaciones del contenedor. |
| B06–B07 | Real VM: Docker restart=always/live-restore, reinicio sin prearmar guard, comprobación ExecStop antes del siguiente inicio y retraso controlado de cuatro segundos. Un reboot falla cerrado y otro restaura el mismo contenedor, TCP/UDP. **Una combinación H3**, no cinco. |
| B08 | Real VM: SIGKILL tras commit del guard y antes de recuperar journal vencido; rollback previo vacío no retira barrera; persistencia restaurada antes de liberarla. |
| B09 | Real VM: SSH nuevo, confirmación/watchdog, recuperación, dos reboots TX y dos H3 con boot IDs distintos. Se comparan reglas ajenas dentro de cada boot y archivos ajenos entre boots. |
| B10 | Real VM: disarm/disable y cleanup selectivos, archivos ajenos intactos; reemplazos/colisiones de fixtures se cubren de forma unitaria. Modificados se preservan y reportan. |

Las fases H3 y sus logs son `bootstrap`, `stage-guard`, `verify-ready`,
`failure-cases`, `calibrate-probe`, `restrict-probe`, `docker-restart`,
`pre-failed-reboot`, `post-failed-reboot`, `pre-reboot`, `post-reboot`, `cleanup`.
El arranque inválido observó **l4d2-firewall.service: inactive/dead, Result=success; docker.service: failed/failed, Result=exit-code; guard activo=True; socket activo=False**. El arranque válido observó
**running**. Los boot IDs y diagnósticos están en los logs de fase.
En el arranque inválido, Docker falló en su restauración y el requisito impidió
iniciar la unidad completa. Su `Result=success` con `inactive/dead` no acredita
una ejecución exitosa: readiness falló, el socket quedó inactivo y el guard
permaneció instalado.

El reinicio Docker verificó **6 pares TCP/UDP bloqueados** con
identidad de guard estable durante cada par.

El monitor registró **89 intentos TCP** y **89 UDP**, con **0
respuestas no autorizadas**. Intervalos máximos entre inicios: TCP
**0.953 s**, UDP **0.952 s**. El runner exige cobertura de cada transición
y gaps ≤3 s. La pausa de 50 ms no es la cadencia: se añade a los timeouts.
SLIRP puede completar el handshake TCP localmente; se exigen bytes de aplicación.
El muestreo no descarta exposición arbitrariamente breve ni certifica tráfico
externo IPv6 durante los reboots; IPv6 sí pasa los ensayos de kernel/namespaces.

## Intentos anteriores

Ningún intento fallido o interrumpido se contabiliza como aceptación. Se conservan
los logs privados saneados bajo `tmp/vm-runner-artifacts/`. Los intentos detectaron
el default VPN TYPECHAIN (producto, corregido), y problemas del ensayo: restaurar
nft antes de la aserción negativa, comprobar tras SSH antes de finalizar jobs de
systemd, una expectativa de error H2 desactualizada y propiedad incompleta de
fixtures y un digest de ACL actualizado que se sobrescribía al guardar fase.
Tres corridas se interrumpieron deliberadamente para incorporar el
harness congelado. Una observación de respuesta durante Docker restart quedó
inconclusa por no medir el guard después de la sonda: se instrumentaron ambos
extremos, rearme atómico y pares estables, sin contar aquella corrida como PASS.
Otro intento detectó una comparación de handles efímeros del sentinel tras reboot;
se corrigió conservando la comparación exacta dentro del mismo boot y rechazando
objetos añadidos o tablas preexistentes. La revisión focalizada corrigió también
la pérdida de metadata de red al guardar un manifest leído antes de terminar los
jobs de arranque y la falta de comprobación de disable en cleanup. Si falla una aserción después
de recrear el sentinel pero antes de guardar su handle nuevo, la limpieza puede
conservarlo por falta de propiedad registrada; el runner destruye igualmente
su VM y no contabiliza ese intento como PASS.
El siguiente intento alcanzó restore/readiness en el arranque válido pero falló
porque la unidad temprana de red precedía al marcador QEMU del ensayo. Se ordenó
el marcador antes de network-pre y se añadió la dependencia explícita, sin
omitir el gate. La corrida aceptada se ejecutó desde una VM fresca.

## Uso, migración, reversión y límites restantes

Consultar [operación y rollback](operations.md), [migración de código/estado](migration.md),
[protección opt-in](boot-protection.md), [capacidades](capabilities.md) y
[reproducción QEMU](vm-runner.md). Ejemplos públicos: `config/profiles/`,
`config/boot-recovery.example.json`, `systemd/examples/`. La barrera usa nftables
también con política iptables-legacy; no se instala automáticamente al guardar.
`check --accept-version-change` solo comprueba la candidata. Para conservar una
aceptación de versión no evaluada hay que aplicar o cargar con esa opción en
mantenimiento, confirmar y ejecutar `save`; un check por sí solo no modifica
la metadata persistente ni autoriza el siguiente arranque.

- **No probado por la matriz del entorno:** otra versión real de iptables,
  binarios de familias mezclados y las otras cuatro combinaciones Docker durante
  reboot H3. H3 cubre suite nftables + Docker iptables/frontend nft 1.8.10;
  los reboots TX cubren además política iptables-legacy sin Docker.
- **Pendiente de despliegue:** ensayar la unidad Docker concreta del destino,
  colocar el guard antes de cualquier ExecStop existente y configurar dependencias
  de todos los servicios/socket protegidos. Una unidad no integrada no queda
  acreditada por readiness. No se desplegó en producción.
- **Convivencia:** un gestor externo que haga flush ruleset después del guard
  puede borrar protección. Se ordena después de la carga inicial de
  nftables.service si está habilitado; no se modifica ni se controla ese gestor.
  El lock serializa solo escritores de la suite. `ready` comprueba el kernel
  al invocarse; no es un vigilante continuo que detenga cargas ante cambios
  externos posteriores.
- **Conservación:** el sentinel inerte del ensayo se compara dentro de cada boot;
  desaparece al reboot y solo se recrea después de verificar restore. No demuestra
  persistencia de reglas ajenas entre boots. La limpieza TX legacy compara una
  firma ajena vacía; la conservación de reglas no vacías se ensaya en las matrices
  de tráfico/Docker. Sí se comparan los bytes/metadatos de
  `/etc/nftables.conf` y `/etc/iptables/rules.v6` durante toda la secuencia.
- **Garantías:** iptables sigue sin atomicidad conjunta entre tablas/familias.
  El rollback no restaura conntrack, contadores ni conexiones. SIGKILL no sustituye
  pruebas de pérdida eléctrica del almacenamiento.
- **Fuera del cierre:** clientes L4D2/SourceTV completos, PMTU VPN representativo,
  otros escenarios VPN y campañas de carga sostenida. Hay probes de juego
  sintéticos; no se promete mitigar saturación del enlace.

No degradar a código antiguo conservando schema 2 o unidades nuevas sin revisar:
respaldar y restaurar código, estado compatible y unidades como un conjunto,
con consumidores detenidos y consola de recuperación. No convertir el journal
pendiente manualmente ni eliminar la barrera para hacer pasar una restauración.

Fuentes oficiales consultadas el 12 de octubre de 2026:
[Docker/iptables](https://docs.docker.com/engine/network/firewall-iptables/),
[restart policies](https://docs.docker.com/engine/containers/start-containers-automatically/),
[live-restore](https://docs.docker.com/engine/daemon/live-restore/),
[systemd v255](https://github.com/systemd/systemd/blob/v255/man/systemd.unit.xml),
[network-pre](https://systemd.io/NETWORK_ONLINE/),
[nftables](https://netfilter.org/projects/nftables/manpage.html).
