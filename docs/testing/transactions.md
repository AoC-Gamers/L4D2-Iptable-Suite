# Prueba VM de transacciones y restauración

Los resultados citados son evidencia anterior, no una ejecución nueva de esta rama
documental. [Aprobación por commit](../security/approval.md) identifica la revisión
aceptada, las versiones y los límites de sus ensayos.

Esta prueba ejercita en una VM QEMU desechable el entrypoint nftables de
producción, el timer real de rollback, la confirmación desde una segunda sesión
SSH y la restauración de arranque de systemd. Después repite el ciclo de
restauración con iptables-legacy. Cambia el firewall y el estado de producción
**dentro del guest**; nunca la ejecutes contra el host.

Desde la raíz del checkout, la reproducción recomendada es:

```bash
python3 -I tests/vm/run.py
```

No requiere root en el host. El runner crea un overlay QEMU desechable, usa
conectividad user-mode con los puertos publicados solo en loopback y controla
los reboots desde fuera del guest. Requisitos, artefactos y límites comunes
están en [vm.md](vm.md); el diseño general de la VM está en
[`tests/vm/run.py`](../../tests/vm/run.py).

## Barreras de seguridad

Las fases internas son operaciones privilegiadas del guest: no ejecutes
manualmente `tests/vm/transactions.py` en el host. El helper solo continúa si
confirma que es root dentro de una VM QEMU/KVM, que PID 1 es systemd, que existe
el marcador root-owned modo `0600` `/run/l4d2-suite-vm.json` con el contenido
exacto `{"virtualization":"qemu","disposable":true}`, y que el suite
confiable está instalado en `/opt/l4d2-firewall`. También exige que la unidad de
producción cargada ejecute `core/fw.py boot-restore`.

Antes de `bootstrap`, `/var/lib/l4d2-firewall` debe carecer de
`current.json`, `pending.json` y `persisted.json`. Si encuentra estado, el
helper falla sin borrarlo ni sobrescribirlo. Herramientas ausentes, SSH fallido,
systemd no disponible, soporte insuficiente del kernel o estados de unidad
inesperados son fallos, nunca skips. El runner no modifica firewall, red,
servicios ni configuración SSH del host. Después de cada reboot, el runner
vuelve a verificar QEMU/KVM y recrea el marcador volátil antes de pedir la fase
siguiente.

## Secuencia

El runner coordina las fases como usuario, desde QEMU y por SSH; las fases de
`transactions.py` se ejecutan con privilegios dentro del guest.

| Etapa | Comprobación |
|---|---|
| `bootstrap` | Instala una política SSH mínima que permite el host de QEMU `10.0.2.2/32`, la confirma y guarda. Comprueba que política actual y persistida coinciden y que los objetos nftables existen; habilita la unidad real de arranque. |
| `arm-fresh-ssh` → `confirm-fresh-ssh TOKEN` | Desde la primera sesión SSH arma un cambio temporizado y valida el timer `l4d2-rollback-TOKEN.timer`. Se cierra esa sesión y se abre una segunda conexión TCP/SSH nueva, sin multiplexación; solo desde ella se confirma. El guest compara `SSH_CONNECTION` con la conexión aplicadora y luego guarda la candidata. |
| `arm-kill-worker` → `kill-committed-worker` → `verify-killed-worker-rollback` | Un worker usa `Store.apply_locked` y el watchdog systemd real. Un wrapper exclusivo del proceso de prueba deja que el motor aplique la candidata, registra un marcador y se detiene con el lock aún tomado. El helper comprueba que journal, predecesora y timer son durables y que la candidata está activa; después valida PID y envía `SIGKILL`. Tras vencer el plazo monotónico, la fase final exige restauración exacta de la predecesora y limpieza del journal pendiente. No simula caída del kernel ni corte de energía durante el commit Netfilter. |
| `arm-abandoned-session` → `verify-abandoned-rollback` | Arma otra aplicación temporizada y registra deadline/predecesora. Se abandona la sesión SSH sin confirmar; tras el plazo, desde consola se exige que el timer independiente quite el journal pendiente, registre el token de rollback y restaure la política y objetos exactos anteriores. |
| `prepare-reboot` → reboot → `post-reboot` → `cleanup` | El runner reinicia el guest, recrea el marcador y verifica que la política nftables persistida restauró byte por byte la política actual, que la unidad real terminó `Result=success` y sigue activa y que sus objetos registrados existen. Cleanup desactiva solo los objetos de la suite, deshabilita la unidad y quita la persistencia de prueba; retiene un marcador pequeño de secuencia para habilitar el ciclo legacy posterior. |
| `bootstrap-legacy` → `prepare-reboot-legacy` → reboot → `post-reboot-legacy` → `cleanup-legacy` | Solo se permite después del post-reboot y cleanup nftables. La política SSH solicita explícitamente `IPTABLES_FRONTEND=legacy`. Se comprueban frontend y hooks/cadenas antes y después del reboot. Cadenas ajenas o hooks movidos causan fallo; la prueba no cambia alternativas del sistema ni borra reglas no registradas. El cleanup compara una instantánea externa y retira solo cadenas/hooks registrados. |

Cada reboot altera exclusivamente el guest QEMU nuevo que lanzó el runner. La
firma de cleanup legacy normaliza los contadores volátiles de paquetes/bytes de
las declaraciones builtin; conserva sensibilidad a contenido de reglas,
declaraciones externas, políticas builtin y coincidencia exacta de hooks del
suite.

## Cobertura y límites de evidencia

El runner conserva resultados JSON por fase y logs del orquestador junto con la
identidad de la imagen, kernel, systemd, Netfilter y detalles SSH. No guardes
material de clave; sanea el token de confirmación después de completar el
ensayo. Un pass solo acredita la combinación exacta ensayada, no otro host,
orden de arranque o frontend.

La ejecución registrada pasó con kernel `6.8.0-142-generic`, systemd
`255.4-1ubuntu8.17`, nftables `1.0.9` e iptables `1.8.10`; el reboot
legacy resolvió `iptables-legacy` para IPv4 e IPv6. Pasaron la confirmación
SSH nueva, SIGKILL con rollback, abandono de sesión con rollback y ambas
restauraciones de arranque.

Límite importante: en la instantánea de cleanup legacy observada no había reglas
ni cadenas externas de usuario (cero reglas/cadenas ajenas; solo seis cadenas
builtin). Por ello ese resultado demuestra que la instantánea externa vacía no
cambió, pero no prueba por sí solo la conservación de reglas externas no
vacías. La matriz Docker independiente sí ejercita reglas externas no vacías,
pero es evidencia distinta. Tras cleanup, la unidad estaba deshabilitada pero
seguía activa hasta apagar el guest. Estos ensayos tampoco certifican integración
Docker, otros frontends iptables, otros sistemas operativos ni un firewall real
del host.

Antes de la VM, el runner ejecuta el test unitario de su harness. Puede correrse
aislado desde la raíz, sin root:

```bash
python3 -I tests/vm/test_transactions_harness.py
```

Ese test simula el límite store/proceso para comprobar publicación del manifiesto
y SIGKILL sin que el padre intente tomar el lock retenido por el worker; no
ejecuta comandos Netfilter. Procedimiento de autorización y límites de ejecución:
[aprobación](../security/approval.md).
