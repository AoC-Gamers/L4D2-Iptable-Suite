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
| DNS de whitelist | CIDRs permitidos, fallos y respuestas inesperadas cubiertos con mocks; no se ensayó resolución DNS privilegiada contra un proveedor externo real. |
| Datos GeoIP | Updater completo probado con ZIP offline sintético, no con licencia, descarga y base MaxMind actuales. Reemplaza cada archivo atómicamente; varios países no se actualizan en una transacción conjunta. |
| Atomicidad | nftables reemplaza tablas propias en una transacción; iptables confirma por tabla/familia, puede quedar mezcla transitoria. Rollback no recupera conntrack, NAT activo, contadores/tokens ni paquetes descartados. |
| Convivencia | Se conservan objetos y archivos ajenos probados; el bloqueo no controla otros administradores. Un `flush ruleset` externo puede borrar suite/guard. No escribir dentro de objetos propios ni usar restore global. |
| Vigilancia | Readiness comprueba boot ID/digest/kernel cuando se invoca; no es un monitor permanente que repare cambios externos. |
| Emulación | La corrida completa aprobada final usó KVM. Existe fallback TCG con presupuestos ampliados; no se atribuye una corrida completa final TCG a esa aceptación. |
| Persistencia ajena | Sentinels en kernel se comparan dentro del mismo boot; archivos ajenos entre boots. Un handle efímero no prueba conservación a través del reboot. |

Para aplicar: [transacciones](../firewall/transactions.md). Para arranque:
[preparación](../boot/README.md) y [recuperación](../boot/recovery.md).
La aceptación del destino requiere ensayar su configuración, versiones, topología,
servicios y arranque; no basta mantener SSH existente ni terminar scripts sin error.

## Incidencias funcionales pendientes

Detectadas al contrastar documentación y código el 12 de octubre de 2026,
sobre la base `93096de`. La limpieza documental no las corrige ni acredita una
nueva auditoría de seguridad.

**F-DOC-01 — inconsistencia reproducida en generación lógica, pendiente.**
[config.py](../../core/config.py) valida `OVPNS2S_ROUTER_ALIAS` reemplazando `;`
por `|`, mientras [compiler.py](../../core/compiler.py) separa pares por coma
y campos por `;`. Con IP ficticias `192.0.2.1|198.51.100.1`, `Configuration`
acepta el dato pero `generate` lanza `ValueError: not enough values to unpack
(expected 2, got 1)` en ambos motores. Con `192.0.2.1;198.51.100.1` ambos generan.
Se reprodujo importando los dos constructores como usuario sin root con
`tests/empty.conf`, solo `openvpn_sitetosite`, `tun0`, redes `192.0.2.0/24` y
`198.51.100.0/24`. No se consultó ni cambió Netfilter. La CLI pública validate
también genera: el fallo ocurre antes de aplicación, no demuestra bypass.
Riesgo residual: entrada admitida por el validador interno falla al componer;
requiere unificar gramática/error y regresión en cambio funcional separado.
La guía usa el formato actualmente consumido `real;alias` separado por coma,
y enlaza esta limitación. No se corrigió producto ni se creó issue público.

**F-DOC-02 — alcance de datos de Compose, observado; requiere decisión separada.**
[log-summary/docker-compose.yml](../../log-summary/docker-compose.yml) declara
`.env` propio y `../.env` del firewall en ambos servicios, exponiendo esas variables
al contenedor. No se inspeccionó su contenido ni se acredita filtración efectiva.
La guía advierte el alcance y la necesidad de archivo raíz; desacoplar esos inputs
requiere cambio funcional fuera de esta tarea. No se modificó Compose.
