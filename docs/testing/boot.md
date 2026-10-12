# Prueba VM del cierre de arranque H3

`tests/vm/closure_boot.py` valida el comportamiento fail-closed del guard,
restore y readiness durante fallos, reinicio de Docker y reboots reales. La
reproducción completa se orquesta desde la raíz del checkout con:

```bash
python3 -I tests/vm/run.py
```

No requiere root en el host. El runner posee el proceso QEMU, la clave SSH
efímera, las fronteras de reboot y las sondas externas. Solo el guest QEMU
desechable recibe cambios privilegiados. No ejecutes manualmente el helper
interno en el host. Para requisitos y artefactos compartidos, consulta
[vm.md](vm.md); los fuentes relevantes son
[`tests/vm/closure_boot.py`](../../tests/vm/closure_boot.py) y
[`tests/vm/run.py`](../../tests/vm/run.py).

## Safety gates y ownership

El helper se niega a continuar salvo que `DOCKER_HOST` esté ausente, el guest
sea QEMU/KVM con systemd como PID 1, exista el marcador root-owned modo `0600`
`/run/l4d2-suite-vm.json` con el JSON exacto
`{"virtualization":"qemu","disposable":true}`, y el suite confiable esté
instalado bajo `/opt/l4d2-firewall`. El runner instala las tres unidades reales
de protección/restauración/readiness; el helper compara sus bytes con las
plantillas confiables antes de usarlas. Una unidad local o un recurso de prueba
preexistente no se reemplaza: causa fallo.

El manifiesto root-owned registra los ficheros de transacción originales y
metadata de configuración, fixtures y ownership. La red de prueba registra por
boot el inode del namespace y el ifindex/MAC del veth. Nombres ocupados sin el
registro correspondiente se rechazan. Los ficheros se crean de forma exclusiva,
sin seguir symlinks, y sus hashes se comprueban antes de actualizar o borrar.
El sentinel nftables tiene nombre único, debe permanecer vacío y conservar su
metadata/handle durante cada boot; desaparece al reiniciar y solo se vuelve a
crear después de aprobar el restore de systemd. Son controles de los fixtures,
no evidencia de ownership del firewall del producto.

La unidad test-owned recrea el marcador antes de `network-pre.target` en cada
boot. La unidad de red fixture exige y sigue esa attestación, y configura el
veth antes del restore completo. Un socket protegido requiere tanto esa unidad
como readiness. Las fases post-reboot esperan hasta 180 segundos a que systemd
termine sus jobs sin iniciar unidades manualmente; luego vuelven a leer el
manifiesto para recuperar el ownership por-boot actualizado.

## Fases coordinadas por el runner

Estas fases se ejecutan dentro del guest con privilegios; el runner externo
coordina SSH, sondas, terminación de procesos y reboots.

| Fase | Alcance comprobado |
|---|---|
| `bootstrap` | Crea grant SSH de recuperación acotado y política nftables del host; instala fixture de red desechable ordenado entre guard y restore completo; habilita socket protegido, valida unidades y establece baseline `ready` activo. |
| `stage-guard` → `verify-ready` | Arma la barrera; comprueba que socket y sonda host del cliente veth están bloqueados mientras restore completo permanece activo. Luego ejecuta restore/readiness de producción, confirma liberación de la barrera y acceso del veth expresamente concedido. |
| `failure-cases` | Rechaza candidata inválida y estado persistido corrupto, ausente o no soportado. Simula `nft` temporalmente no disponible y comprueba barrera retenida/socket bloqueado. Un wrapper de prueba pausa tras instalar la barrera; el runner mata el proceso de restore y verifica rollback del journal vencido al snapshot previo vacío, manteniendo guard y readiness fallida hasta restaurar el binario y completar recovery. Los ficheros/binarios inyectados se restituyen en `finally`. |
| `calibrate-probe` | Inicia daemon Docker local de prueba, versión 29, con live-restore; construye una imagen local de eco TCP/UDP sin registry. Permite temporalmente solo el origen QEMU hostfwd y exige respuestas positivas `H3-CONTAINER` por TCP y `H3-UDP` por UDP antes de usar silencios como evidencia de bloqueo. |
| `restrict-probe` | Reduce grants TCP/UDP publicados al cliente veth: ambos probes del veth deben seguir respondiendo y ambos forwards externos QEMU deben quedar bloqueados. |
| `docker-restart` | Reinicia el servicio systemd Docker de prueba con `restart=always` y live-restore. Un `ExecStopPost` test-only comprueba que el `ExecStop` de producción armó la barrera antes de iniciar de nuevo. Durante la ventana de cuatro segundos, cada probe registra identidad del guard antes/después; una respuesta con guard presente en ambos extremos falla, incluso con rearme atómico. Una sonda que cruza la liberación se declara inconclusa. Se requieren al menos dos pares TCP/UDP bloqueados bajo una identidad estable del guard; luego el mismo contenedor debe responder ambos protocolos tras restore verificado. Se vigilan también ambos forwards externos. |
| `pre-failed-reboot` → reboot → `post-failed-reboot` | Guarda bytes exactos de la política válida, verifica baseline, arma barrera y cambia únicamente el schema persistido a `999`. El host observa el reboot real. La fase posterior exige boot ID nuevo, guard retenido, restore completo/Docker y socket inactivos, sondas host/veth bloqueadas y SSH nuevo todavía disponible. Restaura y verifica hash de los bytes originales, ejecuta recovery y exige probes positivos antes de seguir. |
| `pre-reboot` → reboot → `post-reboot` | Persiste la política válida y arma el guard antes del reboot. Después exige boot ID nuevo, resultados satisfactorios de guard/restore/readiness, veth recreado automáticamente, socket protegido iniciado automáticamente y probes TCP/UDP positivos del host y contenedor. No crea el veth ni inicia el socket desde la fase SSH. Los forwards externos sin autorización deben seguir bloqueados. |
| `cleanup` | Retira solo recursos Docker, drop-ins, unidad/script de red, fixtures service/socket y sentinel propiedad de H3. Desarma barrera/política y restaura los ficheros de transacción originales. Una fixture modificada se conserva y se reporta, no se elimina. Verifica disable correcto y ausencia de symlinks de enablement antes de retirar unidades. |

El fault-injection de SIGKILL envuelve el ejecutable `nft` del guest solo durante
esa fase; delega la transacción real a `nft` original y se pausa después del
commit. El helper envía SIGKILL al grupo completo y en `finally` restaura el
ejecutable byte por byte antes de comprobar la barrera y el journal. Para el
reboot fallido, la política conocida buena se conserva en el manifiesto; se
restaura su contenido exacto antes del reboot válido. Ambos reboots mantienen
sondas TCP/UDP externas durante la transición.

## Qué prueban las sondas y qué no

El servicio de eco es tráfico sintético, no un cliente L4D2 ni SourceTV real. La
sonda TCP exige bytes de aplicación porque SLIRP puede completar handshake TCP
en el host mientras el tráfico guest está bloqueado. Los puertos guest
`18482/tcp` y `18483/udp` se publican en loopback host, por defecto
`22464/tcp` y `22465/udp`; se pueden configurar en el runner.

El runner registra cada intento con etapa, timestamp, duración y hora de inicio.
Exige cobertura de todas las transiciones y que el intervalo entre inicios de
sondas del mismo protocolo no supere tres segundos. Las sondas corren en serie;
la pausa de 50 ms se suma a sus timeouts y no es su cadencia. Se requiere
control positivo del servicio antes de interpretar silencio durante una
transición. Es muestreo medido: no demuestra que una ventana de exposición
arbitrariamente breve sea imposible.

La evidencia aplica a una sola combinación fijada de Docker/backend/guest.
No demuestra compatibilidad con otras versiones o backends de Docker. La matriz
de combinaciones más amplia está en `tests/vm/docker.py`; los artefactos de
runtime pertenecen al runner y no a esta guía de diseño. Para aprobación y
límites de ejecución, consulta [aprobación](../security/approval.md) y
[arranque](../boot/README.md).
