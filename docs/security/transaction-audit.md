# Revisión del ciclo transaccional

Alcance: `core/store.py`, `core/engine.py`, `core/fw.py`, carga de política y
restauración de objetos registrados. Fecha: 2026-10-11. Los cambios de kernel
de validación se ejecutan sólo dentro de `tests/isolated-run.sh`.

## Hallazgos y correcciones

| ID | Hallazgo | Resolución |
|---|---|---|
| TX-01 | `disable` rechazaba retirar objetos propios cuando la política confirmada tenía grants de contenedor/ruta y Docker faltaba o se detectaba con iptables. | `preflight` omite requisitos de integración Docker para una candidata desactivada; conserva verificaciones de backend/frontend y propiedad. Probado con ambos backends en namespace; el caso nftables incluye grant de forwarding y detección Docker iptables sintética. |
| TX-02 | `--remove --set ACCESS_POLICY=...` ignoraba la ACL nueva y podía impedir retirar un servicio aún referido por grants. | La operación de retirada usa el ACL explícito si se pasó; sin override conserva el ACL ya confirmado. Las actualizaciones `--partial` siguen sin aceptar cambios a configuración global. Prueba unitaria de retirada junto a la ACL que elimina la referencia. |
| TX-03 | El plazo empezaba antes de aplicar, pero un comando de motor podía seguir ejecutándose mientras el watchdog esperaba el lock. | Las transacciones de aplicación reciben el deadline monotónico; los comandos se limitan al tiempo restante, `iptables-restore` reduce su espera de lock y falla antes de comenzar si queda menos de un segundo. Si la aplicación alcanza el deadline, se revierte y no se entrega token de confirmación. Una reversión puede tardar más que el plazo si el propio kernel/lock está atascado; el plazo limita la aplicación, no promete tiempo máximo para recuperar el kernel. |
| TX-04 | Al arrancar con estado confirmado persistente y kernel sin reglas, `iptables` confundía ausencia total de objetos con hook externo movido y bloqueaba `load`. | Si no existe ninguna cadena registrada, se permite reconstruir la política completa. Si queda algún objeto suite presente, el hook debe seguir en primera posición. Probado: restauración en ambos motores y rechazo unitario de hook movido con objeto presente. |
| TX-05 | Si fallaba el armado del watchdog, el manejo común de excepciones reescribía el snapshot del firewall aunque la candidata nunca se hubiese aplicado. | La ruta de fallo anterior al inicio de ejecución borra sólo el journal pendiente. La inyección de fallo verifica que no se invoque el escritor y que no quede `pending`. |

La comprobación de versiones iptables sigue activa para cambios de política.
Al desactivar se permite drift de versión dentro del mismo frontend:
el código sigue consultando el binario/frontend guardado y no acepta resolver
otro backend. Esto permite retirar nombres ya registrados tras una actualización
del paquete sin relajar la selección del motor.

## Regresiones

- `python3 -I tests/test_transactions.py`: 8 pruebas unitarias/fault-injection.
- `bash tests/isolated-run.sh tests/transaction-flows.py`: 2 pruebas de kernel,
  ambas con nftables e iptables en namespace desechable.
- `python3 -m compileall -q core tests/test_transactions.py tests/transaction-flows.py`
  y `git diff --check`.

La prueba no simula una pérdida real de alimentación ni un bloqueo permanente del
kernel o del lock. La unidad systemd de producción y el reboot completo mantienen
los límites ya declarados en `results.md`.
