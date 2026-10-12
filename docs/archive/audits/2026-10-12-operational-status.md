# Estado de auditoría operativa

> Archivo histórico. Se conserva el contenido del informe/manual anterior; no es
> la guía operativa vigente. Consulta el [índice actual](../../README.md) y
> [la aprobación por commit](../../security/approval.md).

Esta página resume evidencia fechada, alcance y pendientes; no es una guía para
aplicar reglas. El índice de [documentación actual](../../README.md) enlaza configuración,
operación y pruebas. Para el registro de problemas corregidos, ver
[hallazgos](2026-10-11-findings.md) y [auditoría iterativa](2026-10-11-iterative-audit.md);
los comandos, versiones y límites de evidencia están en
[resultados históricos](2026-10-11-results.md) y el
[cierre H1–H3 del 12 de octubre](h1-h3-plan-results.md).

## Cierre de issues

La auditoría previa cerró **10 issues identificados** con regresión: CFG-01..03, TX-01..05,
HAR-01 y POL-01. La última ronda de revisión cruzada, acotada a los flujos y
harnesses modificados, confirmó **0 nuevos hallazgos**. Esto no demuestra que no
existan fallos fuera del alcance o de las condiciones ensayadas.

El plan posterior AOC-FW-IMP-003 implementó sus **tres hallazgos H1–H3**:
recorrido Docker demostrado, estado canónico schema 2 y barrera/readiness de
arranque. La revisión cruzada final no confirmó nuevos fallos funcionales en
ese alcance. Su [matriz por ID](h1-h3-plan-results.md) distingue
pruebas reales, unitarias y combinaciones no comprobadas.

## Evidencia fechada

La corrida aceptada `20261012T053512Z-f950c62d`, finalizada el 12 de octubre de
2026 UTC, pasó **118 casos Python unitarios/harness, 20 comprobaciones de kernel,
58 métodos de integración/regresión, cinco combinaciones Docker y cuatro
reboots**. El arranque H3 cubre una combinación Docker concreta, con fallos de
restore, socket protegido y sondas TCP/UDP; no certifica el arranque de las otras
cuatro. Ver [versiones, resultados y límites](h1-h3-plan-results.md).

La entrega anterior sobre VM QEMU/KVM desechable, con kernel propio y registrada
el 11 de octubre de 2026 en hora local, se reportaron:

- 54 pruebas unitarias, de harness y runner en conjunto.
- 20 comprobaciones de candidatas contra motores en kernel de VM.
- 46 casos de integración y regresión con reglas/tráfico de VM.
- 5 combinaciones con daemon Docker real, incluida publicación IPv4/IPv6.
- 2 reinicios completos de VM comprobando restauración desde la unidad de arranque.

El runner local fresco terminó con salida 0 y sin casos `SKIP` aceptados. La
evidencia detallada y los intentos fallidos/interrumpidos se conservan en
[results.md](2026-10-11-results.md), [vm-docker.md](../../testing/docker.md),
[vm-clients.md](../../testing/clients.md) y
[vm-transactions.md](../../testing/transactions.md). Esos resultados están limitados
a las versiones y topologías registradas. **No se afirma que el estado remoto de
CI esté actualmente verde**; su estado se debe consultar por separado.

## Pendientes y límites

- Clientes reales de L4D2/SourceTV y descubrimiento completo: se usaron paquetes
  sintéticos, no sesiones de clientes reales.
- OpenVPN: faltan tráfico real para algunas opciones NAT/SNAT y escenarios S2S;
  revisar el desglose de resultados para distinguir candidatas aceptadas por
  kernel de rutas probadas con tráfico.
- PMTU y fragmentación representativos dentro de OpenVPN requieren ensayo propio.
- Docker: las cinco combinaciones probadas no certifican otras versiones,
  overlays, Swarm ni otros órdenes de arranque.
- No se hizo prueba prolongada de saturación de todos los meters/logs ni descarga
  con licencia y datos actuales de MaxMind.
- La resolución DNS privilegiada se cubrió con fallos y respuestas simuladas; no
  demuestra comportamiento de un DNS externo en producción.
- iptables confirma por tabla y familia, sin atomicidad conjunta; el rollback no
  recupera conexiones, conntrack, contadores ni tokens. Un lock propio tampoco
  coordina administradores externos.

Consulta [capacidades](../../firewall/backends.md) y el [cierre H1–H3](h1-h3-plan-results.md)
antes de extrapolar los ensayos a otro host. Para cambios operativos usa la
[guía operativa](../../getting-started/installation.md) y el flujo de
[aplicación transaccional](../../firewall/transactions.md).
