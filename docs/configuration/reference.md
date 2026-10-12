# Referencia de configuración y defaults

Fuente de este inventario: [core/config.py](../../core/config.py) y metadata literal
versionada de [modules/ip](../../modules/ip/) y [modules/nf](../../modules/nf/),
base `93096de`. Los valores se conservan como están declarados; no son una
configuración operativa recomendada ni todos se incorporan a cada perfil.
Ejemplos canónicos: [config](../../config/) y [example.env](../../example.env).

CLI `--set` > archivo > defaults; el entorno exportado no configura el firewall.
Ausente recibe default, vacío explícito conserva vacío y falla si es obligatorio.
La selección, tipos y dependencias se validan antes de generar. No ejecutar el
archivo como shell. Ver [formato](README.md), [perfiles](profiles.md) y [ACL](access-policy.md).

## Tipos y restricciones comunes

| Tipo | Restricción real |
|---|---|
| Booleano | Solo `true` / `false`, sin conversión implícita |
| IP/CIDR/lista | `ipaddress` con prefijo canónico (`strict=True`), familias compatibles; listas separadas por coma/punto y coma/espacio según campo |
| Puerto/lista | 1..65535, coma y rangos `inicio:fin`, inicio ≤ fin; máximo 15 entradas multiport, rango cuenta dos; `OVPNSRV_PORT` es un solo número |
| Interfaz | Nombre exacto 1..15 caracteres `[a-zA-Z0-9_.:-]`, sin comodín |
| Tasa SSH/web | Entero positivo de hasta seis dígitos `/s`, `/sec`, `/second`, `/min`, `/minute`, `/hour`, `/day`; normalizada por backend |
| Tasa/ráfaga numérica | Entero 0..1000000; SSH/web burst >0; juego puede usar 0 para desactivar clases donde el generador lo admite |
| Duración | Entero positivo de hasta cinco dígitos + `s/m/h/d/w`; medidores de recarga/establecido ≤24h y mínimos derivados |
| Prefijo log/alias host | `[A-Za-z0-9_ :.=/-]`, máximo 28 caracteres; no es lenguaje nft libre |
| Nombre de tabla | Letra inicial + letras/números/underscore, máximo 31; `l4d2_boot_guard` reservado; familia solo `inet` |
| Ruta | Datos/código/verificador privilegiados root, ancestros confiables sin escritura de grupo/otros ni symlinks; relativas de ACL/GeoIP desde instalación |
| Alias router | Direcciones IPv4 sin prefijo; lista `real;alias` separada por coma; con alias solo subredes remotas IPv4; SNAT requiere interfaz |

Reglas específicas complementan la tabla: puertos GameServer/TV no se solapan;
TCP SSH/web/juego/allowlist tampoco; VPN server y S2S son excluyentes.
No existe compatibilidad shell ni fallback automático.

## Núcleo

| Variable | Tipo | Default declarado | Alcance/restricción |
|---|---|---|---|
| `PROFILE` | perfil/lista | `host-minimal` | selección mínima; valores en profiles.md |
| `MODULES_ONLY` | IDs/lista | `` (vacío) | vacío usa perfil; CLI --only vacío elige núcleo |
| `MODULES_EXCLUDE` | IDs/lista | `` (vacío) | no excluye núcleo |
| `FAMILY_POLICY` | enum | `dual` | dual / ipv4-block-ipv6; juego iptables exige segundo |
| `NF_TABLE_NAME` | identificador | `firewall_main` | propiedad exclusiva; nombre reservado excluido |
| `NF_TABLE_FAMILY` | enum | `inet` | solo inet |
| `HOST_SERVICES` | booleano | `true` | servicios del host, independiente de routing |
| `ROUTED_POLICY` | enum | `drop` | drop / unmanaged; grants forward requieren drop |
| `CONTAINER_POLICY` | enum | `off` | off / restrict; grants containers requieren restrict |
| `DOCKER_BACKEND` | enum | `auto` | auto / iptables / nftables / none; expectativa diagnóstico |
| `IPTABLES_FRONTEND` | enum | `auto` | auto / nft / legacy; selecciona binarios, no alternativas |
| `ACCESS_POLICY` | ruta JSON | `` (vacío) | se parsea y vacía ruta en estado schema 2; ACL por separado |
| `PRIVILEGED_BYPASS` | booleano | `false` | bypass al host exige whitelist seleccionado |
| `STATE_CAPACITY` | entero | `8192` | 16..65535 entradas por medidor/hashlimit |
| `SSH_METER_TIMEOUT` | duración | `1m` | mínimo de recarga; puede ampliarse si ausente |
| `ADMIN_SOURCES` | IP/CIDR/lista | `` (vacío) | vacío = SSH público limitado |
| `BYPASS_SOURCE_IPS` | IP/CIDR/lista | `` (vacío) | solo whitelist + privilegio explícito |
| `BYPASS_SOURCE_DOMAINS` | DNS/lista | `` (vacío) | privilegio + DNS_ALLOWED_CIDRS; se conserva IP resuelta |
| `DNS_ALLOWED_CIDRS` | CIDR/lista | `` (vacío) | respuestas DNS deben quedar dentro |
| `GEO_IPV6_POLICY` | enum | `` (vacío) | GeoIP dual activo exige deny; no GeoIPv6 |
| `DOCKER_INPUT_COMPAT` | booleano | `false` | solo false; true retirado |
| `DOCKER_CHAIN_AUTORECOVER` | booleano | `false` | solo false; true retirado |

## Módulos

Las celdas de ambos motores son defaults **declarados**; «ausente» significa que
ese backend no lo declara en esa metadata, no que acepte omitir un campo requerido.
El núcleo incorpora opciones comunes del peer para paridad y aplica validación.
Seleccionar un ID retirado no lo habilita por tener metadata. `TYPECHAIN=0` aparece
en metadata legacy pero se excluye del bundle: el adaptador lo inyecta por destino.
La traducción input 0/1/2 ocurre una vez; no se usa en partial/remove.

| Variable | Tipo | nftables declarado | iptables declarado | Módulos/alcance |
|---|---|---|---|---|
| `A2S_INFO_BURST` | entero | `80` | `80` | `l4d2_a2s_filters` |
| `A2S_INFO_RATE` | entero | `16` | `16` | `l4d2_a2s_filters` |
| `A2S_PLAYERS_BURST` | entero | `60` | `60` | `l4d2_a2s_filters` |
| `A2S_PLAYERS_RATE` | entero | `12` | `12` | `l4d2_a2s_filters` |
| `A2S_RULES_BURST` | entero | `40` | `40` | `l4d2_a2s_filters` |
| `A2S_RULES_RATE` | entero | `8` | `8` | `l4d2_a2s_filters` |
| `BYPASS_TCP_PORTS` | puerto/lista | vacío | vacío | `allowlist_ports` |
| `BYPASS_UDP_PORTS` | puerto/lista | vacío | vacío | `allowlist_ports` |
| `DOCKER_DNS_EGRESS_SUBNETS` | IP/CIDR/lista | `172.16.0.0/12` | `172.16.0.0/12` | `docker_dns_egress`; módulo retirado/rechazado |
| `DOCKER_MONITOR_EGRESS_SUBNETS` | IP/CIDR/lista | `172.16.0.0/12` | `172.16.0.0/12` | `docker_monitor_egress`; módulo retirado/rechazado |
| `DOCKER_MONITOR_EGRESS_TARGETS` | IP/CIDR/lista | vacío | vacío | `docker_monitor_egress`; módulo retirado/rechazado |
| `DOCKER_MONITOR_EGRESS_TCP_PORTS` | puerto/lista | `9100` | `9100` | `docker_monitor_egress`; módulo retirado/rechazado |
| `ENABLE_MALFORMED_FILTER` | booleano | `false` | `false` | `l4d2_packet_validation` |
| `ENABLE_PACKET_NORMALIZATION_LOGS` | booleano | `false` | `false` | `l4d2_packet_validation` |
| `ENABLE_STEAM_GROUP_FILTER` | booleano | `true` | `true` | `l4d2_a2s_filters`, `l4d2_udp_base` |
| `ENABLE_UDP_BASELINE_LOGS` | booleano | `false` | `false` | `l4d2_udp_base` |
| `ENABLE_UDP_NEW_FFFFFFFF_BYPASS` | booleano | `true` | `true` | `l4d2_udp_base` |
| `ENABLE_UDP_NEW_LARGE_FILTER` | booleano | `false` | `false` | `l4d2_udp_base` |
| `FIREWALL_LOG_HOST_ALIAS` | prefijo log | vacío | ausente | `l4d2_a2s_filters`, `l4d2_packet_validation`, `l4d2_tcp_protect`, `l4d2_udp_base` |
| `GEO_POLICY_ALLOWED_COUNTRIES` | países alfa-2 | `CL,AR,PE,CO,MX,BO,US` | ausente | `geo_country_filter` |
| `GEO_POLICY_DATA_DIR` | ruta | `./geoip/generated/countries` | ausente | `geo_country_filter` |
| `GEO_POLICY_DENIED_COUNTRIES` | países alfa-2 | vacío | ausente | `geo_country_filter` |
| `GEO_POLICY_MANUAL_ALLOW_FILE` | ruta | `./geoip/manual/allow_ipv4.txt` | ausente | `geo_country_filter` |
| `GEO_POLICY_MANUAL_DENY_FILE` | ruta | `./geoip/manual/deny_ipv4.txt` | ausente | `geo_country_filter` |
| `GEO_POLICY_MODE` | off / allowlist / denylist | `off` | ausente | `geo_country_filter` |
| `HTTP_HTTPS_BURST` | entero | `360` | `360` | `http_https_protect` |
| `HTTP_HTTPS_PORTS` | puerto/lista | `80,443` | `80,443` | `http_https_protect` |
| `HTTP_HTTPS_RATE` | tasa/unidad | `180/minute` | `180/min` | `http_https_protect` |
| `L4D2_CMD_LIMIT` | entero | `100` | `100` | `l4d2_udp_base` |
| `L4D2_GAMESERVER_TCP_PORTS` | puerto/lista | vacío | vacío | `l4d2_tcp_protect` |
| `L4D2_GAMESERVER_UDP_PORTS` | puerto/lista | `27015` | `27015` | `geo_country_filter`, `l4d2_a2s_filters`, `l4d2_packet_validation`, `l4d2_udp_base` |
| `L4D2_LOGIN_BURST` | entero | `16` | `16` | `l4d2_a2s_filters` |
| `L4D2_LOGIN_RATE` | entero | `4` | `4` | `l4d2_a2s_filters` |
| `L4D2_SOURCETV_UDP_PORTS` | puerto/lista | `27020` | `27020` | `geo_country_filter`, `l4d2_a2s_filters`, `l4d2_packet_validation`, `l4d2_udp_base` |
| `LOG_PREFIX_A2S_INFO` | prefijo log | `A2S_INFO_FLOOD:` | `A2S_INFO_FLOOD:` | `l4d2_a2s_filters` |
| `LOG_PREFIX_A2S_PLAYERS` | prefijo log | `A2S_PLAYERS_FLOOD:` | `A2S_PLAYERS_FLOOD:` | `l4d2_a2s_filters` |
| `LOG_PREFIX_A2S_RULES` | prefijo log | `A2S_RULES_FLOOD:` | `A2S_RULES_FLOOD:` | `l4d2_a2s_filters` |
| `LOG_PREFIX_HTTP_HTTPS_ABUSE` | prefijo log | `HTTP_HTTPS_ABUSE:` | `HTTP_HTTPS_ABUSE:` | `http_https_protect` |
| `LOG_PREFIX_ICMP_FLOOD` | prefijo log | `ICMP_FLOOD:` | `ICMP_FLOOD:` | `l4d2_udp_base` |
| `LOG_PREFIX_INVALID_SIZE` | prefijo log | `INVALID_SIZE:` | `INVALID_SIZE:` | `l4d2_packet_validation` |
| `LOG_PREFIX_L4D2_CONNECT` | prefijo log | `L4D2_CONNECT_FLOOD:` | `L4D2_CONNECT_FLOOD:` | `l4d2_a2s_filters` |
| `LOG_PREFIX_L4D2_RESERVE` | prefijo log | `L4D2_RESERVE_FLOOD:` | `L4D2_RESERVE_FLOOD:` | `l4d2_a2s_filters` |
| `LOG_PREFIX_MALFORMED` | prefijo log | `MALFORMED:` | `MALFORMED:` | `l4d2_packet_validation` |
| `LOG_PREFIX_SSH_ABUSE` | prefijo log | `SSH_ABUSE:` | `SSH_ABUSE:` | `tcp_ssh` |
| `LOG_PREFIX_STEAM_GROUP` | prefijo log | `STEAM_GROUP_FLOOD:` | `STEAM_GROUP_FLOOD:` | `l4d2_a2s_filters` |
| `LOG_PREFIX_TCP_RCON_BLOCK` | prefijo log | `TCP_RCON_BLOCK:` | `TCP_RCON_BLOCK:` | `l4d2_tcp_protect`, `l4d2_tcpfilter_chain` |
| `LOG_PREFIX_UDP_EST_LIMIT` | prefijo log | `UDP_EST_LIMIT:` | `UDP_EST_LIMIT:` | `l4d2_udp_base` |
| `LOG_PREFIX_UDP_NEW_LIMIT` | prefijo log | `UDP_NEW_LIMIT:` | `UDP_NEW_LIMIT:` | `l4d2_udp_base` |
| `NFT_A2S_METER_TIMEOUT` | duración | `5s` | ausente | `l4d2_a2s_filters` |
| `NFT_HTTP_HTTPS_METER_TIMEOUT` | duración | `5m` | ausente | `http_https_protect` |
| `NFT_LOGIN_METER_TIMEOUT` | duración | `1s` | ausente | `l4d2_a2s_filters` |
| `NFT_UDP_EST_METER_TIMEOUT` | duración | `5s` | ausente | `l4d2_udp_base` |
| `NFT_UDP_NEW_METER_TIMEOUT` | duración | `5s` | ausente | `l4d2_udp_base` |
| `OVPNS2S_ENABLE_NAT` | booleano | `false` | `false` | `openvpn_sitetosite` |
| `OVPNS2S_INTERFACE` | interfaz | ausente | ausente | `openvpn_sitetosite` |
| `OVPNS2S_LOCAL_INTERFACE` | interfaz | vacío | vacío | `openvpn_sitetosite` |
| `OVPNS2S_LOCAL_SUBNETS` | IP/CIDR/lista | ausente | ausente | `openvpn_sitetosite` |
| `OVPNS2S_LOG_ENABLED` | booleano | ausente | `false` | `openvpn_sitetosite`; true rechazado |
| `OVPNS2S_LOG_PREFIX` | prefijo log | ausente | `VPN_S2S_TRAFFIC:` | `openvpn_sitetosite` |
| `OVPNS2S_REMOTE_SUBNETS` | IP/CIDR/lista | ausente | ausente | `openvpn_sitetosite` |
| `OVPNS2S_ROUTER_ALIAS` | pares IPv4 | vacío | vacío | `openvpn_sitetosite` |
| `OVPNS2S_ROUTER_ALIAS_IP` | IPv4 | vacío | vacío | `openvpn_sitetosite` |
| `OVPNS2S_ROUTER_ALIAS_SNAT` | booleano | `false` | `false` | `openvpn_sitetosite` |
| `OVPNS2S_ROUTER_REAL_IP` | IPv4 | vacío | vacío | `openvpn_sitetosite` |
| `OVPNSRV_DOCKER_INTERFACE` | interfaz | ausente | vacío | `openvpn_server`; valor no vacío rechazado |
| `OVPNSRV_ENABLE_NAT` | booleano | ausente | `false` | `openvpn_server` |
| `OVPNSRV_INTERFACE` | interfaz | `tun0` | `tun0` | `openvpn_server` |
| `OVPNSRV_LAN_INTERFACE` | interfaz | ausente | vacío | `openvpn_server` |
| `OVPNSRV_LAN_SUBNET` | IP/CIDR/lista | `192.168.1.0/24` | `192.168.1.0/24` | `openvpn_server` |
| `OVPNSRV_LOG_ENABLED` | booleano | ausente | `false` | `openvpn_server`; true rechazado |
| `OVPNSRV_LOG_PREFIX` | prefijo log | ausente | `VPN_SERVER_TRAFFIC:` | `openvpn_server` |
| `OVPNSRV_PORT` | puerto/lista | `1194` | `1194` | `openvpn_server` |
| `OVPNSRV_PROTO` | tcp / udp | `udp` | `udp` | `openvpn_server` |
| `OVPNSRV_ROUTER_ALIAS_IP` | IPv4 | ausente | vacío | `openvpn_server` |
| `OVPNSRV_ROUTER_REAL_IP` | IPv4 | ausente | vacío | `openvpn_server` |
| `OVPNSRV_SUBNET` | IP/CIDR/lista | `10.8.0.0/24` | `10.8.0.0/24` | `openvpn_server` |
| `SOURCETV_UDP_NEW_GLOBAL_BURST` | entero | ausente | ausente | `l4d2_udp_base` |
| `SOURCETV_UDP_NEW_GLOBAL_RATE` | entero | ausente | ausente | `l4d2_udp_base` |
| `SOURCETV_UDP_NEW_SRC_BURST` | entero | ausente | ausente | `l4d2_udp_base` |
| `SOURCETV_UDP_NEW_SRC_RATE` | entero | ausente | ausente | `l4d2_udp_base` |
| `SSH_BURST` | entero | `20` | `20` | `tcp_ssh` |
| `SSH_DOCKER` | puerto/lista | vacío | vacío | `tcp_ssh`; valor no vacío rechazado |
| `SSH_PORT` | puerto/lista | `22` | `22` | `tcp_ssh` |
| `SSH_RATE` | tasa/unidad | `60/minute` | `60/min` | `tcp_ssh` |
| `STEAM_GROUP_BURST` | entero | `30` | `30` | `l4d2_a2s_filters` |
| `STEAM_GROUP_RATE` | entero | `6` | `6` | `l4d2_a2s_filters` |
| `STEAM_GROUP_SIGNATURES` | bytes hex/lista | `69` | `69` | `l4d2_a2s_filters`, `l4d2_udp_base` |
| `TCP_DOCKER` | puerto/lista | ausente | vacío | `l4d2_tcpfilter_chain`; valor no vacío rechazado |
| `TYPECHAIN` | compatibilidad | `0` | `0` | `allowlist_ports`, `docker_dns_egress`, `docker_monitor_egress`, `geo_country_filter`, `http_https_protect`, `l4d2_a2s_filters`, `l4d2_packet_validation`, `l4d2_tcp_protect`, `l4d2_udp_base`, `loopback`, `openvpn_server`, `openvpn_sitetosite`, `tcp_ssh`, `whitelist` |
| `UDP_NEW_GLOBAL_BURST` | entero | `960` | `960` | `l4d2_udp_base` |
| `UDP_NEW_GLOBAL_RATE` | entero | `240` | `240` | `l4d2_udp_base` |
| `UDP_NEW_LARGE_DROP_MIN_LEN` | entero | `1024` | `1024` | `l4d2_udp_base` |
| `UDP_NEW_SRC_BURST` | entero | `24` | `24` | `l4d2_udp_base` |
| `UDP_NEW_SRC_RATE` | entero | `8` | `8` | `l4d2_udp_base` |

## Defaults efectivos derivados

- `SOURCETV_UDP_NEW_SRC_RATE/BURST` y `SOURCETV_UDP_NEW_GLOBAL_RATE/BURST` heredan
  UDP NEW si ausentes; no tienen un literal propio en metadata.
- `NFT_LOGIN_METER_TIMEOUT` declara `1s`, pero rate4/burst16 exige `4s`; si no se
  especifica, se amplía. SSH/web/A2S/UDP NEW también se ajustan a recarga completa.
  Un timeout explícito insuficiente falla; no se corrige silenciosamente.
- `OVPNSRV_ENABLE_NAT=false` y `OVPNSRV_LAN_INTERFACE=''` proceden de metadata
  iptables incorporada por el núcleo para paridad aunque no se declaren en nft.
- `BYPASS_SOURCE_DOMAINS` se resuelve durante configuración y se vacía en el bundle;
  `BYPASS_SOURCE_IPS` conserva el conjunto efectivo. `ACCESS_POLICY` conserva ACL
  parseada fuera del diccionario de variables, con ruta de entrada vaciada.
- `IPTABLES_FRONTEND=auto` se resuelve al inspeccionar/aplicar y el journal conserva
  el frontend concreto. No vuelven a elegirse alternativas al revertir.

Consulta `generate`/`plan` con archivo explícito, desde raíz y sin root, para ver
valores efectivos del perfil. No atribuyas un default de otra selección a la tuya.
Las [capacidades](../firewall/backends.md) y [migración](../migration/README.md)
registran rechazos y limitaciones de opciones heredadas.
