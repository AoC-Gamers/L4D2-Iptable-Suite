# Protección de arranque

La protección de arranque es una integración **opt-in**. Guardar una política no
instala ni activa las unidades y no habilita automáticamente la barrera temprana.
Solo quedan cubiertos los servicios y sockets configurados explícitamente para
requerir `l4d2-firewall-ready.service`.

## Preparación

Los comandos siguientes son mutaciones root desde cualquier directorio mediante
rutas absolutas de la instalación confiable. Su destino es el host preparado en
mantenimiento, después de ensayar en VM; no el anfitrión de desarrollo. El archivo
`/etc/.../boot-recovery.json` es un ejemplo a crear a partir del input versionado.
Si algo falla, conservar barrera y usar [recuperación](recovery.md).

Desde la instalación confiable `/opt/l4d2-firewall`, el flujo es:

1. Aplicar una política, probar una conexión administrativa nueva, confirmar y
   guardarla.
2. Ejecutar `ready` y confirmar que el kernel de este arranque contiene la
   política administrada.
3. Ejecutar `boot-prepare`, opcionalmente con `--recovery-file` para grants SSH
   de recuperación limitados a fuente, destino, interfaz y puertos `SSH_PORT`.
   Sin archivo, la recuperación es por consola.
4. Instalar/habilitar las unidades de guardia y restauración, más los drop-ins
   de cada servicio/socket protegido. Los ejemplos están en
   [`systemd/examples`](../../systemd/examples).

```sh
sudo /opt/l4d2-firewall/ipp.sh save
sudo /opt/l4d2-firewall/ipp.sh ready
sudo /opt/l4d2-firewall/ipp.sh boot-prepare \
  --recovery-file /etc/l4d2-firewall/boot-recovery.json
# Tras revisar las unidades existentes y el inventario protegido:
sudo install -m 0644 /opt/l4d2-firewall/systemd/l4d2-firewall-guard.service /etc/systemd/system/
sudo install -m 0644 /opt/l4d2-firewall/systemd/l4d2-firewall.service /etc/systemd/system/
sudo install -m 0644 /opt/l4d2-firewall/systemd/l4d2-firewall-ready.service /etc/systemd/system/
# Instalar los drop-ins revisados para cada servicio/socket y, si aplica, Docker.
sudo systemctl daemon-reload
sudo systemd-analyze verify l4d2-firewall-guard.service l4d2-firewall.service l4d2-firewall-ready.service
sudo systemctl enable l4d2-firewall-guard.service l4d2-firewall.service
```

Estos comandos son de instalación manual en mantenimiento autorizado: no
sobrescribas unidades locales existentes sin revisar y respaldar su contenido.
`enable` programa el arranque siguiente; no aplica la barrera en ese momento.
Ensaya primero la secuencia completa en una VM representativa y conserva consola.

La recuperación SSH exige `HOST_SERVICES=true`, seleccionar `tcp_ssh` y declarar
sus puertos en `SSH_PORT`. Si SSH debe permanecer privado, configura
`ADMIN_SOURCES` con las fuentes administrativas autorizadas antes de aplicar,
confirmar y guardar. Seleccionar el módulo con `ADMIN_SOURCES` vacío habilita SSH
público limitado. Un bypass existente no sustituye estos requisitos del manifiesto.
El servicio/socket SSH usado para recuperar un restore fallido debe poder iniciar
sin requerir `l4d2-firewall-ready.service`; de lo contrario, el puerto permitido por
la barrera no tendrá servidor. La excepción de recuperación solo concede el TCP
declarado por fuente, destino e interfaz. Ensaya una conexión nueva con persistencia
inválida, además del arranque válido.

Usa `--backend iptables` si la política confirmada usa iptables. La barrera es
una tabla nftables `inet` independiente, con prioridad `-310`; requiere `nft` y
soporte nftables incluso con la política iptables-legacy.

## Arranque y recuperación

`l4d2-firewall-guard.service` instala la barrera antes de `network-pre.target`.
Si `nftables.service` está habilitado, el guard se ordena después de su carga
inicial, sin activarlo como dependencia. Un reload/stop externo que ejecute
`flush ruleset` puede borrar toda protección: no está cubierto por el bloqueo
de la suite. Revisa esos gestores antes de habilitar la integración; la suite
no modifica sus unidades ni sus archivos.
`l4d2-firewall.service` requiere esa barrera, restaura la política persistida y
la verifica. `l4d2-firewall-ready.service` comprueba boot ID, digest de política
y fingerprint del kernel antes de que cada consumidor protegido pueda iniciar.
`boot-restore` mantiene la barrera ante errores. El ejemplo `.socket` desactiva sus dependencias automáticas y conserva
inicialización/shutdown explícitos para evitar el ciclo sockets.target →
basic.target → Docker → readiness → socket. Revisa ese ajuste con
`systemd-analyze verify` en la VM representativa. No añadas `ConditionPathExists=`
para omitir restauración cuando falta persistencia: configura una dependencia
obligatoria para que el consumidor falle al no obtener readiness.

Para una parada o reinicio de Docker, el ejemplo usa `boot-guard` en `ExecStop`
para proteger contenedores con `live-restore`. Inspecciona siempre
`systemctl cat docker.service`: el drop-in puede agregar el `ExecStop` después de
las acciones existentes. El comando de guardia debe ir antes de detener el
daemon, conservando las acciones del proveedor en un orden ensayado. No borres ni
reemplaces directivas existentes a ciegas.

Antes de `disable` o de cambiar el alcance preparado, detén los consumidores y,
desde consola, ejecuta `boot-disarm --local`. Después aplica, confirma, guarda,
comprueba `ready` y prepara de nuevo el manifiesto antes de reactivar la barrera.
No reinicies con las unidades de guardia habilitadas y un manifiesto ausente.

La aceptación de versión `--accept-version-change` en `check`, `apply` o `load`
no permite cambiar frontend ni mezclar IPv4/IPv6. Solo iptables/ip6tables 1.8.10
está evaluado automáticamente; una versión no evaluada necesita aceptación en
mantenimiento antes del siguiente `boot-restore`, o la barrera permanece activa.

`check --accept-version-change` solo comprueba la candidata. Para conservar la
aceptación de una versión no evaluada, aplicar o cargar con esa opción en
mantenimiento, confirmar y ejecutar `save`. Un check no escribe la aceptación
persistente ni autoriza por sí solo el siguiente arranque.

La integración H3 pasó en la VM desechable descrita en el [registro de aprobación](../security/approval.md):
fallos de restore, reboot inválido/válido y reinicio Docker con live-restore. Esa
evidencia cubre una combinación Docker concreta; ensaya las unidades del destino.
El [diseño del ensayo H3](../testing/boot.md) detalla las comprobaciones; las unidades son
[`l4d2-firewall-guard.service`](../../systemd/l4d2-firewall-guard.service),
[`l4d2-firewall.service`](../../systemd/l4d2-firewall.service) y
[`l4d2-firewall-ready.service`](../../systemd/l4d2-firewall-ready.service).

Referencias para adaptar la integración: [systemd v255](https://github.com/systemd/systemd/blob/v255/man/systemd.unit.xml),
[network-pre.target](https://systemd.io/NETWORK_ONLINE/),
[políticas de reinicio Docker](https://docs.docker.com/engine/containers/start-containers-automatically/)
y [live-restore](https://docs.docker.com/engine/daemon/live-restore/).
Son fuentes de los contratos del proveedor, no evidencia de una prueba del destino.

## Retirar un cargador heredado exclusivo de la suite

Si `nftables.service` carga la política anterior, guardar la nueva no cambia ese
arranque. Revisa y respalda primero el archivo cargado, sus includes, la unidad y
sus drop-ins. Si también pertenecen a otros administradores, conserva su cargador
y coordina una integración selectiva. El procedimiento siguiente solo corresponde
a un cargador cuya configuración completa se haya confirmado como propia de la suite.

Deshabilitar sin `--now` conserva el servicio actual y sus reglas, pero no elimina
un `ExecStop=nft flush ruleset`. Para retirar ese cargador sin ejecutar el flush ni
volver a cargar su archivo, un drop-in local revisado puede vaciar sus comandos:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/true
ExecReload=
ExecStop=
```

Instálalo como root en un archivo nuevo dentro de
`/etc/systemd/system/nftables.service.d/`, conservando el original respaldado.
Ejecuta `systemctl daemon-reload`, verifica los comandos efectivos con
`systemctl show nftables.service -p ExecStart -p ExecReload -p ExecStop` y deshabilita
el cargador con `systemctl disable nftables.service`, sin detenerlo. Habilita guard
y restore según la preparación anterior. No reinicies ni recargues servicios del
destino para probarlo: ensaya esta transición y el fallo de persistencia en una VM.
El archivo heredado puede conservarse como respaldo; deja de ser la fuente activa
de arranque. Las actualizaciones ordinarias usan aplicar, confirmar y `save`.

Las listas de comandos se reinician mediante asignaciones vacías y `disable` no
implica parar sin `--now`, según los contratos de
[systemd.service v257](https://github.com/systemd/systemd/blob/v257/man/systemd.service.xml)
y [systemctl v257](https://github.com/systemd/systemd/blob/v257/man/systemctl.xml).
No instales este drop-in de forma genérica en gestores compartidos.

Una unidad heredada propia de la suite puede tener `PartOf=docker.service` u
otras dependencias de reinicio. Esas dependencias no se eliminan asignando una
lista vacía en un drop-in: para retirarlas hay que reemplazar la unidad completa
por una definición local inerte y revisada, conservando el original en el respaldo.
Este caso solo corresponde a una unidad exclusiva de la suite, nunca a la unidad
Docker del proveedor. Revisa también todos sus drop-ins: se ordenan por nombre y
uno posterior puede volver a añadir `ExecStartPost`. La anulación de comandos debe
quedar después de esos archivos y cubrir start/pre/post, reload, stop/post y
conditions según el inventario. Tras `daemon-reload`, comprueba `PartOf`, los
comandos efectivos y el estado activo antes de deshabilitar sin parada.

El contrato de dependencias está documentado en
[systemd.unit v257](https://github.com/systemd/systemd/blob/v257/man/systemd.unit.xml).
La retirada de una unidad propia acoplada se ensayó además en el guest QEMU del
[registro de evidencia](../security/approval.md), manteniendo activo su estado
oneshot y conservando PID/inicio de Docker; no se reinició el daemon para probarlo.
