# Aplicación del firewall

El flujo común es configuración → selección → validación → generación → check del
motor → journal/watchdog → aplicación → conexión nueva → confirmación o rollback.
Se administran solo objetos registrados; los puntos de integración compartidos son
mínimos y verificables. El bloqueo propio no coordina escritores externos.

| Necesidad | Documento |
|---|---|
| Ejecutar el primer cambio | [Instalación](../getting-started/installation.md) |
| Entender plazos, fallos, propiedad y atomicidad | [Transacciones](transactions.md) |
| Elegir motor/familias y compatibilidad Docker | [Matriz de capacidades](backends.md), [particularidades iptables](iptables.md) |
| Guardar, cargar, recomponer o retirar | [Persistencia y ciclo de vida](persistence.md) |
| Recuperar barrera de arranque | [Recuperación](../boot/recovery.md) |

`validate`, `generate` y `plan` son lógicos; `check` exige privilegios y puede
recuperar un journal vencido. Para inspección estrictamente pasiva usar `diagnose`
o consultas directas de solo lectura, según [diagnóstico](../testing/diagnostics.md).
