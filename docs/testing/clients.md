# Pruebas de clientes en VM desechable

Los resultados citados son evidencia anterior, no una ejecución nueva de esta rama
documental. [Aprobación por commit](../security/approval.md) identifica la revisión
aceptada, las versiones y los límites de sus ensayos.

Estas pruebas amplían los flujos de red reales sin tocar el firewall del host
que lanza QEMU. Cada lanzador exige root y el marcador `/run/l4d2-suite-vm.json`,
propiedad de root y modo `0600`, con este contenido exacto:

```json
{"virtualization":"qemu","disposable":true}
```

También exige que `systemd-detect-virt --vm` informe `qemu` o `kvm`. Python
repite las comprobaciones; luego crea un namespace de red y montaje anidado y
verifica que su namespace de red difiere del guest. Las interfaces, rutas,
servicios y reglas de prueba se crean dentro de ese namespace. Un tmpfs privado
en `/run` mantiene aislado también `xtables.lock`. Si falta una condición, el
runner termina antes de iniciar OpenVPN, descargar datos o tocar Netfilter.

## OpenVPN real

`tests/vm/clients.sh` inicia el servidor OpenVPN en el namespace de prueba y un
cliente OpenVPN real dentro de un namespace de red remoto. OpenSSL genera una CA,
certificado de servidor y certificado de cliente temporales; no lee ni guarda
credenciales reales. El cliente recibe direcciones IPv4 e IPv6 y rutas a una LAN
de prueba. Para nftables e iptables, comprueba conexiones TCP permitidas por
dirección/interfaz, rechazo de otro puerto y una regla de alias del router que
hace DNAT al servidor LAN. El servicio de destino confirma que el flujo directo
conserva la dirección del cliente VPN.

Con esa sesión autenticada, el runner añade un host LAN detrás del cliente y
un `iroute` de OpenVPN para la subred remota. Comprueba tráfico encaminado por
el sitio remoto, el grant IPv4 `/32` y el DNAT de `OVPNS2S_ROUTER_ALIAS` hacia
el host LAN, también para nftables e iptables. El host remoto es un namespace
de red, no una segunda VM OpenVPN independiente.

Para probar la restricción de origen del grant sin depender de paquetes
spoofeados dentro del túnel, el cliente OpenVPN anuncia una ruta `iroute`
válida a una subred de sitio remoto. Un host real en otro namespace usa la
dirección `.2` autorizada para probar el acceso y el alias, y la `.3` no
autorizada para probar el rechazo. En este último caso se requiere que el
contador de drop de `forward` aumente; si el paquete no alcanza esa regla, la
prueba falla en vez de atribuir el rechazo al firewall.

La prueba no afirma validar una instalación de OpenVPN administrada por
systemd: lanza los binarios reales con configuraciones temporales. Tampoco mide
PMTU; la ACL de gateway que se prueba limita el permiso a TCP, así que una
prueba PMTU necesitaría una política ICMP separada para no confundir el rechazo
por política con el tratamiento de ICMP relacionado.

## GeoIP offline y tráfico

`tests/vm/geoip.sh` crea un ZIP pequeño de formato GeoLite2 CSV y ejecuta
`geoip-updater/run-update.sh` con una URL `file://`. No usa MaxMind, Internet,
licencias ni credenciales. Comprueba que el script produce los archivos
seleccionados y carga una política nftables real; sondas UDP con fuentes de los
CIDR sintéticos verifican que la lista denegada se bloquea y que otras fuentes
siguen pasando.

El paquete UDP de la prueba imita la forma inicial de una consulta A2S de Source
Engine. Es una sonda sintética, no un cliente L4D2 ni una validación del protocolo
de juego completo. Los flujos de `tests/policy-flows.py` también usan paquetes
de prueba para comprobar el filtro A2S.

## Ejecución y límites

Los comandos de este apartado son privilegiados **solo en el guest QEMU desechable**,
desde raíz de la instalación del guest. Inician clientes/túneles, generan archivos
y aplican políticas aisladas. Para reproducir sin operar manualmente como root,
usa [el runner completo](vm.md) desde raíz del checkout sin root anfitrión.

Dentro de la VM desechable, desde la raíz del checkout:

```bash
tests/vm/clients.sh
tests/vm/geoip.sh
```

Se requieren Python 3, systemd-detect-virt, OpenVPN, OpenSSL, iproute2,
iptables/ip6tables, nftables, `nsenter`, curl y permisos de root con soporte de
namespaces. El ejecutor imprime el resultado de cada backend y falla ante una
discrepancia; no se debe ejecutar en el host ni en una VM que contenga estado o
servicios que se necesiten conservar.

Validación ejecutada en VM QEMU desechable: Ubuntu con kernel
`6.8.0-142-generic`, OpenVPN `2.6.19`, nftables `1.0.9` e iptables
`1.8.10 (nf_tables)`. `clients.sh` pasó grants IPv4/IPv6, puerto denegado y
alias de gateway en ambos backends; también pasó ruta S2S, alias y aumento
comprobado del contador `forward` al denegar el origen remoto no autorizado en
ambos backends. `geoip.sh` pasó el flujo ZIP local → updater → CSV → política
nftables, con bloqueo de US y paso de AR/fuente no listada. `py_compile`,
`bash -n` y `git diff --check` también pasaron. GeoIP usa únicamente la sonda
UDP sintética descrita arriba; no valida un cliente L4D2 real.
