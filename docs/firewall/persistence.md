# `ipp.sh`: administración y persistencia de la suite

Todos los ejemplos con ruta absoluta se pueden ejecutar desde cualquier directorio
en el destino/guest preparado, con root. Son una **referencia de operaciones**, no
una secuencia completa: `load`, `apply` y `disable` necesitan comprobar conexión
nueva y confirmar o revertir antes de comenzar otra operación. `boot-*` requiere
preparación opt-in y mantenimiento. No ejecutar la lista completa como script.

`ipp.sh` es una CLI para el mismo escritor, lock y journal que
[`nftables.rules.sh`](../../nftables.rules.sh) y [`iptables.rules.sh`](../../iptables.rules.sh).
Sin argumentos muestra ayuda. El backend por defecto es `nftables`; especifica
`--backend iptables` para el otro motor. La CLI no instala paquetes, cambia
alternativas, reinicia servicios ni edita persistencia global. Ver el
[índice de documentación](../README.md) para el flujo de instalación y uso. Los
ejemplos asumen instalación revisada en `/opt/l4d2-firewall` y datos en
`/etc/l4d2-firewall`, con las propiedades y permisos descritos en la guía operativa.

```sh
sudo /opt/l4d2-firewall/ipp.sh status
sudo /opt/l4d2-firewall/ipp.sh doctor
sudo /opt/l4d2-firewall/ipp.sh --backend iptables status
sudo /opt/l4d2-firewall/ipp.sh --backend iptables diagnose
sudo /opt/l4d2-firewall/ipp.sh save
sudo /opt/l4d2-firewall/ipp.sh load --timeout 120
sudo /opt/l4d2-firewall/ipp.sh ready
sudo /opt/l4d2-firewall/ipp.sh boot-prepare
sudo /opt/l4d2-firewall/ipp.sh boot-guard
sudo /opt/l4d2-firewall/ipp.sh boot-restore
sudo /opt/l4d2-firewall/ipp.sh apply --remove http_https_protect
sudo /opt/l4d2-firewall/ipp.sh apply --partial --only tcp_ssh --set SSH_RATE=30/minute
sudo /opt/l4d2-firewall/ipp.sh disable
sudo /opt/l4d2-firewall/ipp.sh confirm --token TOKEN --admin-verified
sudo /opt/l4d2-firewall/ipp.sh rollback
```

`status` muestra las políticas actual, pendiente y último rollback del directorio
de estado. `doctor` informa herramientas, versiones y objetos del motor. Estas
operaciones de lectura también procesan primero un journal vencido; si hay una
aplicación pendiente expirada, pueden iniciar su rollback antes de mostrar el
resultado. `check` valida una candidata contra el motor sin aplicarla, pero también
puede recuperar una transacción vencida.

`diagnose` consulta versiones, frontend y recorrido estructural de Docker sin
abrir el almacén ni ejecutar recuperación. Solo acepta la selección de backend
y, opcionalmente, `--set IPTABLES_FRONTEND=legacy|nft|auto`. `ready` comprueba la
política instalada en el arranque actual bajo el bloqueo, sin revertir cambios
vencidos; un journal pendiente produce indisponibilidad.

`save` requiere una política confirmada y la copia a
`/var/lib/l4d2-firewall/persisted.json`. `load` comprueba y vuelve a aplicar esa
política mediante el flujo temporizado de confirmación. `disable` retira solo los
objetos y hooks registrados como propios, conserva la política guardada y sigue
el mismo flujo temporal de aplicación/confirmación.

Las operaciones `apply` con cambios nuevos requieren la candidata generada,
comprobación del motor y watchdog systemd antes de modificar Netfilter. Se entrega
un token para probar una conexión administrativa nueva desde fuera del host y
confirmar con `--admin-verified`; el timeout revierte automáticamente. `rollback`
revierte una transacción pendiente de inmediato. `--local` evita el watchdog y
solo corresponde a una consola local; no es apropiado para una sesión remota.
Detalles, límites y el ejemplo completo están en [operaciones](transactions.md)
y la [guía operativa](../getting-started/installation.md).

Las actualizaciones `--partial --only` y `--remove` parten de una política
confirmada y recompilan una candidata completa. No aceptan `--env-file`; usa
`--set` solo para variables relacionadas con los módulos seleccionados. Al quitar
un módulo que tenga grants de contenedor, actualiza también `ACCESS_POLICY` con un
archivo que retire esos grants en la misma operación, por ejemplo:

```sh
sudo /opt/l4d2-firewall/ipp.sh apply --remove http_https_protect \
  --set ACCESS_POLICY=/etc/l4d2-firewall/access-without-web.json
```

Las dependencias deben permanecer completas. Para quitar juego, elimina juntos
sus módulos de validación, A2S y UDP. Para retirar toda la suite usa `disable`.

La persistencia pertenece solo a la suite. `save` y `load` no escriben
`/etc/nftables.conf`, `/etc/iptables/rules.v4` ni `rules.v6`, no adoptan objetos por
nombre y no restauran un ruleset global. La unidad
[`systemd/l4d2-firewall.service`](../../systemd/l4d2-firewall.service) es integración
de arranque opt-in. `boot-prepare` requiere una política aplicada, confirmada,
guardada y validada por `ready` en el boot actual. Después se instalan y habilitan
explícitamente las unidades de guardia y restauración, y se agregan dependencias
de readiness a cada servicio/socket protegido. Con Docker se revisan los drop-ins
y el orden real de `ExecStop`; no se copian a ciegas. Para desactivar o cambiar el
alcance preparado, detener los consumidores y ejecutar desde consola
`boot-disarm --local` antes de `disable` o la nueva preparación. El modo por defecto
no instala una barrera temprana. La evidencia VM anterior cubre restauración de la
política. La [evidencia H1–H3](../security/approval.md) prueba
además la barrera en reboots inválido/válido y reinicio Docker con live-restore,
en la combinación y con los límites allí registrados.
Consulta [guía de arranque](../boot/README.md) para el procedimiento y los límites.


## Retirada e instalación ajena

`disable` no exige Docker disponible; iptables permite deriva de versión para
retirar, pero conserva el frontend confirmado. No cambia políticas compartidas.
Una carga tras reboot admite ausencia total de cadenas propias; objetos presentes
parcialmente o hooks desplazados necesitan diagnóstico antes de aplicar.

Para desinstalar, desde consola y mantenimiento autorizado: detener consumidores,
revisar/deshabilitar las unidades/drop-ins opt-in de la suite y su timer watcher,
desarmar barrera si fue preparada, hacer `disable` y confirmar su retirada. Conservar
persistencia si se necesita `load`; para retirada definitiva, borrar solo archivos/
instalación/estado cuya propiedad de la suite esté demostrada y tras cancelar todo
pending. No se entrega limpieza global ni eliminación de reglas ambiguas heredadas.
Procedimiento de barrera: [recuperación](../boot/recovery.md); backend/frontend:
[migración](../migration/README.md). No eliminar archivos de otro administrador.
