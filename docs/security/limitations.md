# Limitaciones vigentes y aceptación del destino

Estas restricciones acompañan a la [aprobación](approval.md) del commit `93096de`.
Un escenario sin ensayo no es por sí solo una vulnerabilidad confirmada; ausencia
de fallos observados tampoco garantiza otros servicios, cargas o versiones.

| Área | Alcance demostrado y condición pendiente |
|---|---|
| Activación de arranque | Opt-in: `save` no instala barrera/unidades. Preparar manifiesto y dependencias de readiness por consumidor; probar cada servicio/socket real. |
| Docker y systemd | Adaptar unidad real y ejecutar guard antes de las acciones que detienen Docker. No copiar `ExecStop`/drop-ins sin revisar comandos del proveedor y ciclos de dependencias. |
| Versiones | Guest Ubuntu Noble, kernel 6.8.0-142, nftables 1.0.9, iptables 1.8.10, systemd 255.4-1ubuntu8.17, Docker 29.8.2, OpenVPN 2.6.19. Otras versiones requieren nueva validación; aceptación iptables explícita nunca migra frontend. |
| Matriz Docker normal | Cinco combinaciones con ambos frontends, publicaciones remapeadas, retorno TCP, UDP independiente y reglas ajenas. No equivale a cinco ensayos de arranque. |
| H3 | Restart/live-restore/reboots solo suite nftables + Docker iptables/frontend nft. Otras combinaciones de arranque y cambios reales de versión/frontend no ensayados; B01/B02 son unitarios. |
| Sondas de arranque | TCP/UDP externos muestreados con controles positivos y gaps ≤3 s; no excluyen ventanas arbitrariamente breves ni certifican tráfico externo IPv6 durante reboot. |
| L4D2/SourceTV | Payloads sintéticos A2S/login/TV y UDP establecido. Faltan clientes reales, descubrimiento completo y sesiones representativas. Filtros opcionales requieren capturas propias. |
| VPN | TLS/rutas/alias ensayados; PMTU no probado, ni todas las variantes SNAT/TLS legacy. Regla sintácticamente aceptada no demuestra ese tráfico. |
| IPv6 | Web/SSH/grants dual ensayados. Juego iptables requiere bloqueo IPv6 explícito que puede impedir retornos salientes. GeoIP es IPv4; modo dual activo exige denegar UDP IPv6 de juego. No se desactiva IPv6. |
| Carga y estado | Capacidad/expiración de medidores limitadas y regresiones de agotamiento; no es un ensayo de carga sostenida de producción ni garantía frente a saturación de enlace/conntrack. Logging se limita por regla, no por un presupuesto universal. |
| Atomicidad | nftables reemplaza tablas propias en una transacción; iptables confirma por tabla/familia, puede quedar mezcla transitoria. Rollback no recupera conntrack, NAT activo, contadores/tokens ni paquetes descartados. |
| Convivencia | Se conservan objetos y archivos ajenos probados; el bloqueo no controla otros administradores. Un `flush ruleset` externo puede borrar suite/guard. No escribir dentro de objetos propios ni usar restore global. |
| Vigilancia | Readiness comprueba boot ID/digest/kernel cuando se invoca; no es un monitor permanente que repare cambios externos. |
| Emulación | La corrida completa aprobada final usó KVM. Existe fallback TCG con presupuestos ampliados; no se atribuye una corrida completa final TCG a esa aceptación. |
| Persistencia ajena | Sentinels en kernel se comparan dentro del mismo boot; archivos ajenos entre boots. Un handle efímero no prueba conservación a través del reboot. |

Para aplicar: [transacciones](../firewall/transactions.md). Para arranque:
[preparación](../boot/README.md) y [recuperación](../boot/recovery.md).
La aceptación del destino requiere ensayar su configuración, versiones, topología,
servicios y arranque; no basta mantener SSH existente ni terminar scripts sin error.
