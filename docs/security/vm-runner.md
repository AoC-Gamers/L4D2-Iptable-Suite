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
forward SSH enlazado exclusivamente a `127.0.0.1`. No crea bridges, TAPs,
sockets Docker del host ni forwards de otros servicios. Usa KVM cuando
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
El runner instala la unidad de
arranque del firewall y una unidad guard que recrea el marcador root-owned
`0600` después de cada reboot. El disco QCOW2 de trabajo tiene 12 GiB virtuales.
Los runners requieren acceso de red para descargar imagen, Docker y paquetes
apt; los casos GeoIP y Docker no acceden a servicios externos durante sus
pruebas funcionales.

## Ejecución local

Se requieren `qemu-system-x86_64`, `qemu-img`, `genisoimage`, `ssh`, `scp` y
`ssh-keygen` en `PATH`; no se requiere root. Una caché también se valida contra
los mismos hashes:

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

Finalmente conduce las fases de transacción de producción mediante conexiones
SSH nuevas sin multiplexación: apply/confirmación en otra conexión, worker
committed terminado con SIGKILL, expiración del timer tras pérdida de sesión,
reboot y restore systemd de nftables; repite el reboot/restore con
iptables-legacy y limpia el estado de prueba. Cada reboot cambia exclusivamente
el guest QEMU que este proceso lanzó.

## CI y evidencia

`.github/workflows/vm.yml` ejecuta primero pruebas offline del propio runner,
instala QEMU, `genisoimage` y OpenSSH client en Ubuntu 24.04, ejecuta el runner
y publica los logs incluso si falla. El job tiene un límite global de cuatro
horas para permitir TCG cuando KVM no está disponible. El reporte demuestra sólo los hashes de
imagen/Docker, kernel, systemd y backends ejercitados; no sustituye una prueba
de firewall en el host del desarrollador ni afirma que la sonda UDP sintética
sea un cliente L4D2 real.
