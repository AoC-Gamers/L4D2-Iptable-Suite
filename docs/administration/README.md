# Acceso administrativo SSH

`tcp_ssh` controla TCP nuevo por origen y puerto en ambos motores. Los paquetes
TCP establecidos mantienen la aceptación de retorno; el presupuesto de un origen
no consume el de los demás. No hay un límite SSH global adicional oculto.
Logs y descarte son independientes; agotar mensajes no vuelve aceptable el exceso.

| Clave | Default declarado | Decisión |
|---|---|---|
| `SSH_PORT` | `22` | Puerto/lista válida; evitar solapamiento web/TCP de juego |
| `SSH_RATE`, `SSH_BURST` | `60/minute` (nft), `60/min` (ip), `20` | Semántica equivalente por origen+puerto |
| `ADMIN_SOURCES` | vacío | Vacío: SSH público limitado; con IP/CIDR restringe fuentes |
| `SSH_METER_TIMEOUT` | `1m` | Puede ampliarse si se omite; debe cubrir recarga del burst |
| `STATE_CAPACITY` | `8192` | Capacidad por medidor/hashlimit, no estado ilimitado |

Usa [host-minimal.conf](../../config/profiles/host-minimal.conf), cuyos orígenes
administrativos son ficticios; otros perfiles pueden dejar SSH público. Confirma
puerto y familia antes de aplicar. Un grant `host` para administración confiable
omite controles públicos solo para su origen/destino/servicio; no concede bypass total.
`SSH_DOCKER` no vacío se rechaza: usa [grants Docker](../docker/README.md).

Desde raíz del checkout y sin root, genera un plan:

```sh
./nftables.rules.sh plan --env-file config/profiles/host-minimal.conf
```

Revisa fuentes/puertos/familias y límites. No prueba que SSH escuche ni que la nueva
conexión llegue. Aplica desde instalación confiable con [timer/confirmación](../firewall/transactions.md),
abre una conexión **nueva** desde otro equipo y confirma solo tras comprobarla.
Si falla, conserva consola y deja expirar o ejecuta rollback; para guard de arranque
usa [recuperación](../boot/recovery.md). No corrijas acceso abriendo INPUT completo.

Código: [compiler.py](../../core/compiler.py) y [módulo nft](../../modules/nf/nf_40_tcp_ssh.sh).
Pruebas: [policy-flows.py](../../tests/policy-flows.py), [integración](../../tests/integration.py).
Evidencia/agotamiento de estado: [límites](../security/limitations.md).
