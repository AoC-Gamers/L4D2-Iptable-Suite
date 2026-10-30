# OpenVPN servidor y site-to-site

La suite adapta el firewall; no instala/configura OpenVPN ni añade protocolos VPN.
Separa listener, acceso al host, acceso a redes remotas y NAT. El permiso NAT no
concede filtrado. Un host nativo puede ser gateway sin Docker mediante grants
`forward` y `ROUTED_POLICY=drop`.

## Servidor

El perfil [vpn-gateway.conf](../../config/profiles/vpn-gateway.conf) selecciona
`openvpn_server`. `OVPNSRV_PROTO=udp`, `OVPNSRV_PORT=1194`,
`OVPNSRV_INTERFACE=tun0`, `OVPNSRV_SUBNET=10.8.0.0/24` son defaults del módulo.
La LAN declarada por módulo es `192.168.1.0/24`; el ejemplo usa ficticiamente
`192.0.2.0/24` con `OVPNSRV_LAN_INTERFACE=lan0`, no un default universal.
NAT está desactivado; activarlo exige interfaz LAN explícita y familias compatibles.

[access.example.json](../../config/access.example.json) concede SSH a un
administrador VPN concreto y TCP/9100 a un monitor concreto de LAN. Los demás
puertos/subredes no se autorizan por pertenecer al túnel. Adaptar direcciones,
interfaces y grupos antes de aplicar. Listener publicado en Docker requiere grant
`containers` de `service=openvpn_server`; el túnel soportado debe correr en el host.
Se rechaza `OVPNSRV_DOCKER_INTERFACE` cuando no está vacío; los flags heredados
`OVPNSRV_LOG_ENABLED` y `OVPNS2S_LOG_ENABLED` deben permanecer en `false`.

## Site-to-site

`openvpn_sitetosite` es excluyente con servidor y requiere `OVPNS2S_INTERFACE`,
`OVPNS2S_LOCAL_SUBNETS`, `OVPNS2S_REMOTE_SUBNETS`. No existe perfil S2S automático.
`OVPNS2S_ENABLE_NAT=false`; si se activa, exige `OVPNS2S_LOCAL_INTERFACE`.
Alias `OVPNS2S_ROUTER_ALIAS` usa pares IPv4 `real;alias` separados por coma; SNAT es opt-in mediante
`OVPNS2S_ROUTER_ALIAS_SNAT` y exige `OVPNS2S_LOCAL_INTERFACE` incluso si NAT
general está desactivado. Al configurar alias IPv4, la lista de subredes remotas
usada por ese modo también debe ser solo IPv4; una lista con IPv6 falla al generar.
Redes de una adaptación NAT deben ser de igual familia,
no listas mixtas. Los permisos direccionales siguen declarándose aparte.


### Alias S2S limitado a TCP

`OVPNS2S_ROUTER_ALIAS_TCP_PORTS` restringe el DNAT de los alias S2S y su
SNAT opcional al protocolo TCP y a esos puertos. Requiere un alias IPv4 y
subredes remotas IPv4. Vacío conserva la traducción por dirección anterior;
no cambia los alias del módulo servidor ni el NAT general hacia la LAN.

Por ejemplo, con direcciones ficticias, `OVPNS2S_ROUTER_REAL_IP=192.0.2.1`,
`OVPNS2S_ROUTER_ALIAS_IP=198.51.100.200` y
`OVPNS2S_ROUTER_ALIAS_TCP_PORTS=80` solo traducen TCP/80 desde la interfaz
VPN y las fuentes remotas declaradas. NAT no concede filtrado: un gateway
VPN anterior necesita permitir el destino alias antes del DNAT y el host
traductor necesita el permiso de forwarding y retorno correspondiente.
No hace falta anunciar el alias por ARP si llega en tránsito por el túnel.

Validar/generar en aislamiento y aplicar mediante el núcleo transaccional,
con conexión administrativa nueva antes de confirmar. HTTP puede devolver
redirects al destino real; NAT no reescribe Host, Location ni cookies.

## Revisión y recuperación

Desde la raíz del checkout, sin root, el siguiente comando genera un plan con
valores ficticios del perfil; no configura túneles ni aplica reglas:

```sh
./nftables.rules.sh plan --env-file config/profiles/vpn-gateway.conf
```

Revisa los grants de host/forward y la ausencia de bypass completo. Aplica desde
instalación confiable con [confirmación y reversión](../firewall/transactions.md),
y verifica conexión nueva administrativa más servicio permitido/denegado desde
ambos lados del túnel. Si falla, distingue rutas/iroute, interfaz, listener y ACL;
no autorices todo FORWARD para reparar conectividad.

La [prueba de clientes](../testing/clients.md) usa TLS OpenVPN real en namespaces
anidados de una VM; no acredita unidades systemd OpenVPN del destino. PMTU, algunas
variantes SNAT y TLS legacy quedan fuera del alcance demostrado; consulta
[capacidades](../firewall/backends.md) y [limitaciones](../security/limitations.md).

Código: [config.py](../../core/config.py), [compiler.py](../../core/compiler.py).
Pruebas: [clients.py](../../tests/vm/clients.py), [check-engine.py](../../tests/check-engine.py).

Usa únicamente `real;alias,real;alias`, no `|`: aunque el validador interno lo
admite, la generación lo rechaza. Discrepancia de separadores: [incidencia documentalmente detectada](../security/limitations.md#incidencias-funcionales-pendientes).

## Gateway S2S junto a Docker iptables-nft

`OVPNS2S_ALLOW_LAN=true` es un permiso privilegiado **explícito**, independiente
de `OVPNS2S_ENABLE_NAT`. Autoriza todos los protocolos desde cada prefijo remoto
por el túnel hacia cada prefijo local por la interfaz LAN declarada; el retorno
solo corresponde a conexiones establecidas/relacionadas en dirección reply.
No concede un bypass al host ni acceso a otras subredes. Exige nftables nativo,
`openvpn_sitetosite`, `ROUTED_POLICY=unmanaged`, interfaces distintas y Docker
iptables con frontend nft. Otras combinaciones se rechazan antes de aplicar.
El modo sirve cuando el operador quiere conservar un gateway a la LAN completa,
incluido su router; para permisos más estrechos usa grants de routing en una
combinación soportada en [capacidades](../firewall/backends.md).

El escritor común inserta solamente sus reglas identificadas en DOCKER-USER y
las conserva en el journal de confirmación/rollback. La cadena debe existir:
no se crea ni se repara Docker. El reemplazo de tablas propias y de esas reglas
ocurre en un solo batch nftables. Readiness incluye su contenido. Desactivar o
revertir retira exclusivamente reglas registradas de la suite, sin vaciar la
cadena compartida ni modificar su política. Los bundles que las requieren usan
schema 3: versiones anteriores deben rechazarlos, no cargar solo las tablas.

El arranque necesita Docker antes del restore y los drop-ins de guard/restore
indicados en [arranque](../boot/README.md). Guardar el bundle no instala unidades.
Las reglas heredadas deben revisarse/retirarse explícitamente y el cargador antiguo
debe respaldarse y retirarse según su propiedad; no lo ejecutes junto al nuevo.
NAT sigue limitado a prefijos e interfaz declarados. Listas NAT mixtas IPv4/IPv6
siguen rechazadas; el opt-in no añade soporte a esa combinación.

Ensayo de gateway y NAT, solo root en la VM QEMU desechable preparada por el
[runner](../testing/vm.md), desde `/opt/l4d2-firewall`:

```sh
bash tests/vm/s2s-routing.sh
```

Prueba Docker iptables-nft real, TCP/retorno y masquerade VPN→LAN, ICMP al peer LAN,
denegación de destino fuera de LAN y de conexiones nuevas LAN→VPN, conservación
de reglas ajenas y retirada selectiva. No acredita túneles TLS ni el router real.

Ejemplo declarativo ficticio: [vpn-lan-docker.conf](../../config/profiles/vpn-lan-docker.conf).
Desde la raíz del checkout, sin root, `./nftables.rules.sh validate --env-file
config/profiles/vpn-lan-docker.conf` comprueba lógica y genera; no prueba el túnel
ni el motor. Reemplaza interfaces y prefijos antes de comprobar/aplicar. Este
ejemplo delega el tráfico de contenedores a Docker (`CONTAINER_POLICY=off`); combina
`ingress` y grants DNAT explícitos si también quieres restringir publicaciones.
