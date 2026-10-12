# Entrega explícita de una tabla nftables heredada

El flujo opt-in sustituye una tabla `inet` de filtrado **íntegramente propiedad
de la suite** por una política nueva del mismo nombre. Exige servicios del host,
contenedores desactivados, `ROUTED_POLICY=unmanaged`, sin NAT y sin política actual
ni barrera registrada. No importa iptables ni layouts compartidos/ambiguos.
`--acknowledge-legacy-ownership` declara la revisión y propiedad exclusiva de
**todos** los objetos; el manifiesto identifica contenido y handle, no prueba
propiedad. La aplicación ordinaria sigue rechazando objetos sin registro.

Desde una instalación root-owned en `/opt/l4d2-firewall`, los siguientes comandos
root leen la tabla y escriben metadata privada. Nombres/rutas son ficticios:

```sh
sudo nft -s list table inet firewall_main
sudo sh -c 'umask 077; /opt/l4d2-firewall/ipp.sh legacy-inventory --legacy-table firewall_main > /root/legacy-reviewed.json'
```

Revisar reglas, acreditar propiedad, conservar copias privadas de tabla/persistencia
y ensayar la candidata con una copia de las reglas en VM/namespace desechable.
`legacy-inventory` es pasivo: no carga configuración ni abre/recupera estado.
El handle y manifiesto son propios del kernel: inventariar nuevamente el destino.
Cambios de reglas/ACL o reemplazo de tabla abortan; contadores y elementos de
conjuntos dinámicos no constituyen cambios de política.

Comprobar y aplicar desde esa instalación confiable, tras el ensayo y revisión,
con configuración root confiable y una ventana de diez minutos:

```sh
sudo /opt/l4d2-firewall/ipp.sh check --env-file /etc/l4d2-firewall/server.conf \
  --legacy-manifest /root/legacy-reviewed.json --acknowledge-legacy-ownership
sudo /opt/l4d2-firewall/ipp.sh apply --env-file /etc/l4d2-firewall/server.conf \
  --legacy-manifest /root/legacy-reviewed.json --acknowledge-legacy-ownership --timeout 600
```

`check` puede recuperar un journal anterior expirado; no aplica la candidata.
El núcleo comprueba candidata y snapshot restaurable con `nft -c`, conserva el
snapshot en el journal y arma el watchdog systemd común antes de escribir.
Vuelve a cotejar la tabla y ejecuta eliminación por handle y creación en un solo
`nft -f`. Dentro del mismo lote, `destroy table` por nombre después de la
eliminación por handle invalida la caché de evaluación de nft: permite reemplazar
medidores homónimos con otra capacidad. Un handle obsoleto hace fallar todo el
lote, incluido ese `destroy`; no se divide la operación. Requiere que el motor
acepte esa sintaxis en `check`; se ensaya con nftables 1.0.9 y 1.1.3.
El fallo/expiración restaura exclusivamente esa tabla y deja `current`
vacío como antes. No se permite `--local`. Tras una reversión se recrea la tabla:
el manifiesto anterior deja de ser válido, aunque las reglas coincidan.

Probar una conexión SSH autenticada **nueva**, sin multiplexación, y los servicios
declarados; desde ella confirmar y guardar:

```sh
sudo /opt/l4d2-firewall/ipp.sh confirm --token TOKEN --admin-verified
sudo /opt/l4d2-firewall/ipp.sh save
```

Si falla el acceso, dejar vencer el timer; si aún hay acceso, `ipp.sh rollback`
revierte inmediatamente. Al confirmar, las operaciones posteriores son ordinarias.
Un proxy SSH comprobado es una ruta de respaldo, pero atraviesa el mismo firewall:
no equivale a consola independiente. Conservar consola fuera de banda cuando
exista y evaluar el riesgo residual de depender solo de rutas de red. El timer
no garantiza recuperación ante fallo del kernel, systemd o del motor.

No borrar `/etc/nftables.conf` ni instalar cron/reboot para recuperar el cambio.
El timer sobrevive al aplicador y a SSH, **no a un reboot**. Conservar persistencia
anterior durante mantenimiento conserva su política al arrancar, si ese
comportamiento estaba verificado. `save` no instala la integración de
[arranque](../boot/README.md): hasta completar y ensayar ese paso, el próximo
boot puede cargar las reglas anteriores. Esta entrega no modifica archivos de
persistencia, servicios ni reglas de otras tablas.

El lock no controla otros administradores. Huella y handle reducen carreras,
pero no impiden cambios ajenos dentro de la misma tabla entre cotejo y commit.
Exigir uso exclusivo y coordinar escritores; no se detienen servicios solos.
Rollback no conserva contadores, tokens ni estado conntrack/NAT.

Referencias oficiales: [nft(8)](https://netfilter.org/projects/nftables/manpage.html)
y [systemd-run(1)](https://www.freedesktop.org/software/systemd/man/latest/systemd-run.html).
Código: [legacy.py](../../core/legacy.py), [escritor](../../core/store.py).
Regresiones: [unitarias](../../tests/test_legacy.py),
[kernel/tráfico aislado](../../tests/legacy-flows.py),
[systemd y SSH nuevo en QEMU](../../tests/vm/legacy_handover.py).
