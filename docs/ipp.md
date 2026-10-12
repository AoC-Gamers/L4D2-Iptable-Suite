# `ipp.sh`: administración y persistencia de la suite

`ipp.sh` es una CLI para el mismo escritor, lock y journal que
[`nftables.rules.sh`](../nftables.rules.sh) y [`iptables.rules.sh`](../iptables.rules.sh).
Sin argumentos muestra ayuda. El backend por defecto es `nftables`; especifica
`--backend iptables` para el otro motor. La CLI no instala paquetes, cambia
alternativas, reinicia servicios ni edita persistencia global. Ver el
[índice de documentación](README.md) para el flujo de instalación y uso. Los
ejemplos asumen instalación revisada en `/opt/l4d2-firewall` y datos en
`/etc/l4d2-firewall`, con las propiedades y permisos descritos en la guía operativa.

```sh
sudo /opt/l4d2-firewall/ipp.sh status
sudo /opt/l4d2-firewall/ipp.sh doctor
sudo /opt/l4d2-firewall/ipp.sh --backend iptables status
sudo /opt/l4d2-firewall/ipp.sh save
sudo /opt/l4d2-firewall/ipp.sh load --timeout 120
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
Detalles, límites y el ejemplo completo están en [operaciones](security/operations.md)
y la [guía operativa](operations-guide.md).

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
[`systemd/l4d2-firewall.service`](../systemd/l4d2-firewall.service) es integración
de arranque opcional: se instala y habilita aparte, y su orden respecto de Docker
debe ensayarse en la VM del destino. La unidad por sí sola no prueba persistencia
tras reinicio; la restauración de esta versión sí se ensayó en VM con dos
reinicios, como detalla [vm-transactions.md](security/vm-transactions.md). Eso
no certifica el orden de arranque de otro host o su integración con Docker.
