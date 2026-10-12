# Estado de auditoría operativa

Esta página resume evidencia fechada, alcance y pendientes; no es una guía para
aplicar reglas. El índice de [documentación actual](README.md) enlaza configuración,
operación y pruebas. Para el registro de problemas corregidos, ver
[hallazgos](security/findings.md) y [auditoría iterativa](security/iterative-audit.md);
los comandos, versiones y límites de evidencia están en
[resultados](security/results.md).

## Cierre de issues

La auditoría cerró **10 issues identificados** con regresión: CFG-01..03, TX-01..05,
HAR-01 y POL-01. La última ronda de revisión cruzada, acotada a los flujos y
harnesses modificados, confirmó **0 nuevos hallazgos**. Esto no demuestra que no
existan fallos fuera del alcance o de las condiciones ensayadas.

## Evidencia fechada

En la continuación sobre VM QEMU/KVM desechable, con kernel propio y registrada
el 11 de octubre de 2026 en hora local, se reportaron:

- 54 pruebas unitarias, de harness y runner en conjunto.
- 20 comprobaciones de candidatas contra motores en kernel de VM.
- 46 casos de integración y regresión con reglas/tráfico de VM.
- 5 combinaciones con daemon Docker real, incluida publicación IPv4/IPv6.
- 2 reinicios completos de VM comprobando restauración desde la unidad de arranque.

El runner local fresco terminó con salida 0 y sin casos `SKIP` aceptados. La
evidencia detallada y los intentos fallidos/interrumpidos se conservan en
[results.md](security/results.md), [vm-docker.md](security/vm-docker.md),
[vm-clients.md](security/vm-clients.md) y
[vm-transactions.md](security/vm-transactions.md). Esos resultados están limitados
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

Consulta [capacidades](security/capabilities.md) y [resultados](security/results.md)
antes de extrapolar los ensayos a otro host. Para cambios operativos usa la
[guía operativa](operations-guide.md) y el flujo de
[aplicación transaccional](security/operations.md).
