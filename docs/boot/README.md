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

`check --accept-version-change` solo comprueba la candidata. Para conservar la
aceptación de una versión no evaluada, aplicar o cargar con esa opción en
mantenimiento, confirmar y ejecutar `save`. Un check no escribe la aceptación
persistente ni autoriza por sí solo el siguiente arranque.
