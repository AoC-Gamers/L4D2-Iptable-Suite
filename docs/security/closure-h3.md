# Cierre H3 — barrera explícita y disponibilidad durante el arranque

La restauración de una política guardada ya tiene un estado de disponibilidad
por arranque y una barrera temprana opcional. El CLI expone `boot-prepare`,
`boot-guard`, `boot-restore`, `ready` y `boot-disarm`; los comandos de arranque
usan solo la política confirmada y guardada, sin aceptar configuración nueva.

## Preparar y operar la barrera

`boot-prepare` requiere que la política activa esté aplicada, confirmada y
guardada, y que `ready` valide el boot ID, el digest de la política y los
objetos del kernel en este arranque. Se puede preparar recuperación por consola
sin grants o un archivo root-owned con grants SSH acotados. Cada grant limita
fuente, dirección destino, interfaz de entrada y puertos incluidos en `SSH_PORT`.
Los servicios de contenedor sin SSH de host usan recuperación por consola.

```sh
sudo /opt/l4d2-firewall/ipp.sh apply --env-file /etc/l4d2-firewall/host.conf
# Desde una conexión nueva, confirmar según el flujo temporizado.
sudo /opt/l4d2-firewall/ipp.sh confirm --token TOKEN --admin-verified
sudo /opt/l4d2-firewall/ipp.sh save
sudo /opt/l4d2-firewall/ipp.sh ready
sudo /opt/l4d2-firewall/ipp.sh boot-prepare
# Alternativa: --recovery-file /etc/l4d2-firewall/boot-recovery.json
```

Usa `--backend iptables` de forma consistente si la política usa ese motor. La
barrera temprana es una tabla nftables independiente, por lo que **también
requiere `nft` y soporte nftables del kernel cuando el motor de la política sea
iptables-legacy**. Se instala en hooks inet con prioridad `-310`, antes de las
cadenas habituales del filtro. El guard no se activa al instalar el paquete ni
por guardar una política: la integración de unidades es opt-in.

`boot-guard` arma la barrera registrada; `boot-restore` la reanuda, restaura la
política persistida, comprueba disponibilidad y solo entonces retira el guard.
`ready` falla si el journal sigue pendiente, el boot ID no coincide, cambió la
política o su fingerprint del kernel, se movió un hook administrado o la barrera
sigue activa. La tabla de guard tiene manifiesto y propiedad independientes de
los snapshots normales; un rollback de la suite no debe eliminarla.

Para cambiar o retirar el alcance preparado, detén primero los servicios
protegidos y trabaja desde consola:

```sh
sudo /opt/l4d2-firewall/ipp.sh boot-disarm --local
sudo /opt/l4d2-firewall/ipp.sh disable --local
```

`boot-disarm --local` no desactiva servicios ni cambia la política por sí mismo;
requiere mantenimiento local y elimina únicamente la barrera propia registrada.
Después se puede cambiar el alcance, aplicar/confirmar/guardar y volver a
`boot-prepare`. No dejes las unidades de barrera habilitadas al reiniciar sin un
manifiesto preparado: el arranque falla cerrado y los servicios dependientes no
deben iniciar. Los cambios que conservan exactamente el alcance de la barrera
pueden actualizar su digest mediante `save`.

## Integración systemd opt-in

Instala y habilita explícitamente `l4d2-firewall-guard.service` y
`l4d2-firewall.service`. El primero instala la barrera antes de
`network-pre.target`; el segundo depende del guard y ejecuta `boot-restore`.
`l4d2-firewall-ready.service` se activa como requisito de cada servicio/socket
protegido mediante los drop-ins de [systemd/examples](../../systemd/examples/).
La suite no enumera ni detiene automáticamente servicios del host. Solo los
servicios y sockets que se configuran para requerir readiness quedan cubiertos.

El ejemplo Docker añade una dependencia opcional para ordenar la restauración
después del daemon y proteger `live-restore`: `ExecStartPre` rearma el guard,
`ExecStartPost` restaura la política y `ExecStop` lo rearma antes de detener el
daemon. **No copies ese drop-in sin inspeccionar `systemctl cat docker.service`.**
`ExecStop=` puede contener varios comandos y un drop-in puede añadir el nuevo
comando después de los existentes. Si el guard queda después del comando que
detiene Docker, la ventana no está protegida. Prepara un override que ejecute
`boot-guard` antes de las acciones existentes, conserva esas acciones en el
orden necesario y ensaya inicio, parada y reinicio con la configuración exacta
del host. No borres ni reemplaces a ciegas los `ExecStop` del proveedor.

No agregues `ConditionPathExists=` a las unidades de restauración o guardia para
“hacerlas opcionales”: una condición falsa puede dejar una unidad omitida en vez
de una activación fallida y romper la dependencia que debe detener consumidores.
La integración es opcional porque no se instala/habilita por defecto, no porque
falte un archivo de estado.

## Versiones, alcance y evidencia

La transición automática evaluada cubre iptables/ip6tables **1.8.10**; variaciones
de cadena de proveedor con esa versión siguen la identidad evaluada. Otras
versiones requieren mantenimiento explícito con `--accept-version-change` en
`check`, `apply` o `load`. Esa opción no acepta un cambio de frontend ni una
mezcla IPv4/IPv6. Una versión no evaluada durante `boot-restore` deja la barrera
activa; revisa y acepta la transición antes del siguiente reinicio.

Las pruebas unitarias H3 usan mocks para verificar identidad de arranque,
fingerprints, ownership, recuperación y compatibilidad; no aplican reglas.
La prueba de arranque/reinicio y la integración systemd/Docker H3 en VM siguen
pendientes. No se afirma evidencia de reboot para esta barrera. La matriz de
pruebas anteriores de la suite no cubre automáticamente H3.
