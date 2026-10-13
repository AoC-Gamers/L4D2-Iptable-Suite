# Runner QEMU de validación completa

`tests/vm/run.py` prepara una VM Ubuntu Noble desechable y ejecuta allí las
pruebas de kernel, tráfico, clientes, GeoIP, Docker y recuperación de
transacciones. El runner no usa `sudo` ni cambia el firewall, interfaces,
servicios o daemon Docker del host. QEMU arranca como hijo del runner y se
termina únicamente ese proceso al salir.

## Límites y materiales

El runner descarga una imagen cloud de Ubuntu Noble con fecha fija y el archivo
estático de Docker 29.8.2. Verifica siempre el SHA-256 esperado, incluso cuando
se entregan archivos cacheados. La imagen original queda intacta: QEMU escribe
en un overlay QCOW2 privado que se elimina al terminar. La clave SSH Ed25519 se
genera por ejecución y se borra con los archivos temporales. No se guardan
credenciales reales ni tokens de confirmación en los logs.

La única conectividad del guest usa el backend `user` de QEMU (SLIRP), con un
forward SSH y sondas TCP/UDP enlazadas exclusivamente a `127.0.0.1`. No crea bridges,
TAPs ni sockets Docker del host. Usa KVM cuando
`/dev/kvm` es accesible; de lo contrario cae a TCG. Los dos modos tienen un
timeout de arranque acotado.

Cloud-init instala en el guest Python 3, Git, OpenVPN/OpenSSL, iproute2,
iptables/ip6tables, nftables, util-linux, kmod y SSH; el runner instala el Docker
estático verificado sin habilitar un servicio Docker. Empaqueta únicamente los
archivos de `git ls-files` (incluye archivos staged), excluye `.env` y nunca
barre archivos untracked arbitrarios. Los fuentes nuevos que deban probarse en
un checkout local deben estar staged o versionados. El producto se instala en
`/opt/l4d2-firewall` root-owned, sin escritura para grupo/otros, y se verifica
su confianza allí. El mismo archivo se extrae además en
`/home/suiteunit/l4d2-unit`, propiedad de una cuenta dedicada `suiteunit` sin
sudo, grupos administrativos ni clave SSH; su contraseña está bloqueada y su
shell de login es `nologin`. Antes de cada prueba un guard comprueba que no es
root y que `sudo -n true` falla. El runner valida el user-data con
`cloud-init schema --system` antes de esperar que termine cloud-init, siguiendo
el [schema oficial de cloud-init](https://raw.githubusercontent.com/canonical/cloud-init/main/cloudinit/config/schemas/schema-cloud-config-v1.json).
El runner instala las tres unidades de protección/restauración/readiness del
firewall y una unidad de prueba separada que recrea el marcador root-owned
`0600` después de cada reboot. El disco QCOW2 de trabajo tiene 12 GiB virtuales.
Los runners requieren acceso de red para descargar imagen, Docker y paquetes
apt; los casos GeoIP y Docker no acceden a servicios externos durante sus
pruebas funcionales.

## Ejecución local

Desde raíz del checkout, **sin root** en el host. Los comandos siguientes descargan
y preparan materiales, inician un guest efímero y ejecutan pruebas privilegiadas
solo dentro de él; no son checks estáticos. Las rutas `/cache/...` son ficticias y
opcionales; suministra archivos con los hashes esperados. El código probado debe
estar versionado/staged y los artefactos se escriben localmente.

Se requieren `qemu-system-x86_64`, `qemu-img`, `genisoimage`, `ssh`, `scp` y
`ssh-keygen` en `PATH`; no se requiere root. Una caché también se valida contra
los mismos hashes:

La fuente de URLs y SHA-256 fijados son las constantes `IMAGE_URL`,
`IMAGE_SHA256`, `DOCKER_URL` y `DOCKER_SHA256` de
[run.py](../../tests/vm/run.py); no se sustituyen por hashes descargados sin validar
durante una ejecución. Cambiar esos materiales requiere revisar la evidencia
de versiones y repetir los ensayos correspondientes.

```bash
python3 -I tests/vm/run.py
python3 -I tests/vm/run.py \
  --image /cache/noble-server-cloudimg-amd64.img \
  --docker-archive /cache/docker-29.8.2.tgz \
  --ssh-port 22462
```

Por defecto deja `runner.log`, `qemu.log`, `serial.log` y logs sanitizados
completos de stdout/stderr por caso en `tmp/vm-runner-artifacts/<run-id>/`;
el directorio de artefactos es privado y `runner.log` tiene modo `0600`. El
overlay, la clave privada, `known_hosts` y el seed cloud-init se borran. El
puerto SSH se puede cambiar si el default está ocupado. Para QEMU extraído manualmente se puede indicar
`--qemu-data-dir`/`QEMU_DATA_DIR` y `--bios`/`QEMU_BIOS_PATH`; el entorno
`QEMU_MODULE_DIR` y `LD_LIBRARY_PATH` heredado se respetan.

## Casos obligatorios

Antes de la matriz, una entrega heredada explícita se aplica con el watchdog
systemd de producción. Tres conexiones SSH separadas arman el cambio, comprueban
acceso nuevo y observan la expiración sin invocar recuperación. Se exige restaurar
la tabla anterior y dejar el registro vacío. El caso cambia la capacidad de un
medidor homónimo para comprobar la sustitución atómica; no usa reglas privadas.
Este caso histórico cubre una tabla `inet` y manifiesto schema 1; por sí solo no
valida schema 2 ni sustitución/restauración conjunta de tablas NAT `ip`/`ip6`.

El runner falla ante cualquier salida distinta de cero, incluyendo el código
`77` que un harness usa para indicar `SKIP`; esta matriz no puede reportar
éxito por omitir un caso. Ejecuta unit tests del core/configuración/GeoIP
(incluyendo core, GeoIP, configuración, política, transacciones, watcher,
generación y harness, todos como `suiteunit`), `check-engine`, tráfico,
transacciones y política real bajo `tests/isolated-run.sh` para los frontends
`nft` y `legacy`;
OpenVPN client/server y el actualizador GeoIP offline; y los cinco escenarios
Docker documentados: suite iptables con daemon iptables en ambos frontends,
suite nftables con daemon iptables en ambos frontends, y suite/daemon nftables.
La combinación suite iptables con backend Docker nftables se excluye porque el
contrato de política actual la rechaza.

Las pruebas de integración reservan 120 segundos para confirmación y concurrencia,
y 30 segundos para provocar una expiración real. El presupuesto empieza antes de
las escrituras del kernel; los antiguos plazos de 2 y 5 segundos podían vencer
durante una aplicación bajo TCG. La recuperación se observa mediante el journal
del watchdog, con una espera máxima de 90 segundos, en lugar de suponer que un
`sleep` breve implica restauración completa. La prueba de concurrencia exige un
único cambio pendiente todavía vigente y que el segundo escritor sea rechazado
por ese motivo. Cada bloque de integración tiene un límite de 20 minutos; los
otros bloques de kernel mantienen 10 minutos. Ningún timeout se convierte en éxito.

Finalmente conduce las fases de transacción de producción mediante conexiones
SSH nuevas sin multiplexación: apply/confirmación en otra conexión, worker
committed terminado con SIGKILL, expiración del timer tras pérdida de sesión,
reboot y restore systemd de nftables; repite el reboot/restore con
iptables-legacy y limpia el estado de prueba. Cada reboot cambia exclusivamente
el guest QEMU que este proceso lanzó.

Después ejecuta [el cierre H3](boot.md): barrera temprana,
readiness con política real, fallos de persistencia/binario, SIGKILL antes de
rollback a vacío, socket protegido y Docker con `restart=always`/`live-restore`.
Las sondas externas se calibran contra una respuesta del contenedor antes de
retirar su autorización y observar reinicio del daemon y reboot. Los timestamps
quedan en `external-probes.json`; `external-probe-summary.json` registra el
intervalo máximo y la duración por protocolo. El runner exige muestras TCP y
UDP durante cada transición y falla si el intervalo entre inicios de sondas
del mismo protocolo supera tres segundos. Las sondas se ejecutan en serie:
la pausa de 50 ms se añade a sus timeouts y no define su cadencia. Se exige
respuesta de aplicación: un handshake TCP de SLIRP no demuestra que el
contenedor recibió tráfico. Este muestreo no prueba ausencia de exposición
de duración arbitrariamente pequeña.

## CI y evidencia

`.github/workflows/vm.yml` ejecuta primero pruebas offline del propio runner,
instala QEMU, `genisoimage` y OpenSSH client en Ubuntu 24.04, ejecuta el runner
y publica los logs incluso si falla. En esa VM desechable de GitHub, si existe
`/dev/kvm`, el workflow concede acceso mediante ACL exclusivamente al usuario
del job; QEMU continúa sin root. Si el dispositivo no existe, ejecuta la misma
matriz completa bajo TCG. La disponibilidad de virtualización anidada no está
garantizada por [GitHub](https://docs.github.com/en/actions/concepts/runners/github-hosted-runners).
Este permiso no se aplica al host de desarrollo mediante `run.py`.
El job tiene un límite global de cuatro
horas para permitir TCG cuando KVM no está disponible. El reporte demuestra sólo los hashes de
imagen/Docker, kernel, systemd y backends ejercitados; no sustituye una prueba
de firewall en el host del desarrollador ni afirma que la sonda UDP sintética
sea un cliente L4D2 real.

La evidencia aprobada de ingreso de contenedores se limita al caso dual-stack de
suite nftables con Docker `29.8.2`/iptables-nft descrito en
[Docker real](docker.md). No se debe inferir de esa corrida evidencia de tráfico
para otros backends o frontends. En un ensayo separado de `OVPNS2S_ALLOW_LAN`, la
suite nftables con Docker iptables-nft real pasó tráfico IPv4 TCP, masquerade
VPN→LAN e ICMP al peer LAN, y rechazó destinos fuera de LAN y conexiones nuevas
LAN→VPN; también pasó rollback, idempotencia y conservación de reglas ajenas.
Esto no acredita TLS ni topología de router real.

Las nueve pruebas nuevas de `tests/legacy-flows.py` pasaron en kernel nftables y
cubren el handover schema 2 de la tabla de filtro más tablas NAT IPv4/IPv6:
fallo de candidata y handle NAT obsoleto sin cambios parciales, reemplazo en un
solo batch, expiración tras matar al aplicador con restauración de filtro/NAT y
preservación de objetos ajenos, confirmación, reapply e `disable` selectivo. Estas
pruebas verifican ciclo de vida de objetos; no prueban traducción de paquetes NAT.
El ensayo focalizado `valpo1-a6e1fe2bf5` cerró con **dos reboots guest PASS**.
El reboot válido comprobó `ready`, TCP/masquerade/ICMP y el orden de dos reglas
compartidas S2S antes de la regla ajena. El reboot inválido rechazó schema `999`
en `ExecStartPost` de Docker, dejó inactiva la dependencia `l4d2-firewall.service` y `ready` falló con
guard-drop; luego se recuperó SSH nuevo, se restauró exactamente la política
persistida buena y el reinicio de Docker del guest recuperó el flujo y la regla
ajena. El helper usado es privado/operacional, no un nuevo gate de CI. Los intentos
previos fallaron por fixtures del arnés corregidas después y no se cuentan como
PASS ni como defectos del producto. No hubo CI remoto ni ensayo productivo.
Entorno y límites por revisión en [aprobación](../security/approval.md).
