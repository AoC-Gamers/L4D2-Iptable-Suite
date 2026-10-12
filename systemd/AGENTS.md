# Integración de arranque

Complementa [instrucciones raíz](../AGENTS.md). Lee [arranque](../docs/boot/README.md)
y [recuperación](../docs/boot/recovery.md) antes de cambiar unidades/drop-ins.

Las unidades son opt-in; guardar no habilita guard ni readiness. Mantén dependencia
obligatoria del consumidor, barrera antes de red/consumidores y restore antes de
liberarla. No sustituyas fallos por `ConditionPathExists` que omita la activación.
Para Docker, inspecciona la unidad real: guard en `ExecStop` debe preceder acciones
que paran el daemon, preservando las del proveedor. Verifica ciclos service/socket.

No instales/habilites/reinicies unidades en el host de acceso para comprobarlas.
Valida dependencias y reinicios reales en VM desechable. Separa diseño de unidades,
verificación estática y evidencia de reboot. Cambios de `Documentation=` son solo
referencias documentales; no aproveches el cambio para alterar orden/comandos.
