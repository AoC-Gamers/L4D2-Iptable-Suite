# Contenedores Docker y puertos publicados

La protección de servicios del host no implica autorización del tráfico a
contenedores. Usa `CONTAINER_POLICY=restrict` y grants `containers` de
[ACCESS_POLICY](../configuration/access-policy.md), con módulo de servicio seleccionado.
Cada permiso fija origen, IP pública original, puerto público, destino/puerto
interno, interfaces, protocolo y estado DNAT. No autoriza redes internas completas.

Antes de instalar, identifica por separado motor de la suite, frontend iptables
(nft/legacy) y backend de Docker. La [matriz canónica](../firewall/backends.md)
detalla cinco combinaciones probadas y rechazos; suite iptables + Docker nftables
no está soportado. No cambies alternativas/backends automáticamente.

## Componer y comprobar

Desde la raíz, sin root, validar el ejemplo ficticio (web y juego remapeados):

```sh
./nftables.rules.sh plan --env-file config/profiles/web.conf --profile web --profile games --set CONTAINER_POLICY=restrict --set ACCESS_POLICY=config/containers.example.json
```

Esto no consulta Docker ni comprueba que existan publicaciones. En instalación
confiable, desde cualquier directorio, con root y autorización de lectura del
destino, el diagnóstico siguiente **no abre ni recupera el journal**:

```sh
sudo /opt/l4d2-firewall/ipp.sh --backend iptables diagnose --set IPTABLES_FRONTEND=nft
```

El diagnóstico muestra versiones y estructura por familia. Para suite iptables
con Docker iptables, H1 exige FORWARD → DOCKER-USER único, incondicional y primero,
y hook propio primero allí. Si faltan cadenas o hay un ACCEPT previo, aplicar falla
antes de escribir; no repara ni reinicia Docker. En Docker nftables no hay
DOCKER-USER: nftables nativo integra una tabla propia con prioridad previa.
Un ACCEPT de cadena base nftables todavía puede ser descartado por otra cadena base.

Ensaya [tráfico publicado/retorno](../testing/docker.md) en VM y aplica con
[timer y rollback](../firewall/transactions.md). Si preflight falla, conserva
la política y diagnostica frontend/topología; no muevas reglas ajenas para ocultarlo.
Cambiar motor requiere retirada confirmada y [migración](../migration/README.md).

## Egreso y arranque

`docker_dns_egress` y `docker_monitor_egress` heredados se rechazan. Migra a grants
`forward` por origen/destino/interface/servicio, no a bypass por subred y puerto.
Suite nftables + Docker iptables rechaza esos grants por posible FORWARD DROP de
Docker: `ROUTED_POLICY=unmanaged` delega egreso y no acredita protección por la suite.
`SSH_DOCKER`, `TCP_DOCKER`, `UDP_DOCKER` no vacíos también se rechazan.

La matriz general prueba régimen normal. Reinicio/live-restore y reboot H3 solo
se ensayaron con suite nftables + Docker iptables/frontend nft, según
[aprobación](../security/approval.md). Integración [de arranque](../boot/README.md)
es opt-in y exige adaptar la unidad real, incluido orden de `ExecStop`, sin borrar
comandos del proveedor. La aplicación ordinaria no reinicia servicios.

Código: [engine.py](../../core/engine.py). Pruebas: [topología](../../tests/docker-topology-flows.py),
[daemon real](../../tests/vm/docker.py), [H3](../../tests/vm/closure_boot.py).
