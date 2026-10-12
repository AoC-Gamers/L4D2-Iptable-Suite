# Configuración, perfiles y permisos

El núcleo lee configuración declarativa y genera una candidata antes de modificar
reglas. Para comandos privilegiados, revisar la [operación](security/operations.md)
y desplegar código/configuración root fuera del checkout del usuario.

## Archivo y precedencia

```sh
./nftables.rules.sh validate --env-file config/profiles/web.conf
./nftables.rules.sh plan --env-file config/profiles/web.conf --set SSH_PORT=2222
```

`--env-file` selecciona un archivo. Sin esa opción se carga `.env` junto al
entrypoint si existe; en su ausencia se usan defaults. El entorno exportado del
proceso no configura el firewall. Precedencia: CLI `--set` > archivo > defaults.
Las rutas relativas de `ACCESS_POLICY` y datos GeoIP parten de la raíz de instalación;
para archivos operativos en `/etc` usar rutas absolutas.

Formato: una asignación `KEY=VALUE` por línea, comentarios `#` y comillas opcionales.
Los valores con espacios necesitan comillas. No admite `export`, claves duplicadas,
expansiones, comandos, backticks ni continuaciones shell. Un valor vacío permanece
vacío; un campo obligatorio vacío falla. Las claves desconocidas se rechazan aunque
el módulo esté deshabilitado. No mezclar `LOGFILE`/`RSYSLOG_CONF` del analizador.

## Selección efectiva

| Entrada | Comportamiento |
|---|---|
| Sin lista de módulos | Usa `PROFILE`; default `host-minimal` |
| `MODULES_ONLY=''` en archivo | Sigue usando el perfil |
| `--only tcp_ssh,http_https_protect` | Sustituye la lista del archivo y la selección por perfil |
| `--only ''` | Sólo núcleo, sin SSH/web/juego/VPN |
| `--profile web --profile games` | Une módulos si no hay una lista `only` efectiva |
| `--skip` | Sustituye `MODULES_EXCLUDE` y excluye del conjunto seleccionado |

Los perfiles seleccionan módulos; no cargan los archivos `config/profiles/`
automáticamente. Esos archivos se usan mediante `--env-file` y contienen valores
específicos de ejemplo. Setup, loopback, ICMP/ICMPv6 y cierre pertenecen siempre
al núcleo. Se comprueban IDs/alias, dependencias, conflictos y solapamientos.

| Perfil | Módulos de servicio |
|---|---|
| `host-minimal` | `tcp_ssh` |
| `web` | `tcp_ssh`, `http_https_protect` |
| `games` | `tcp_ssh`, `l4d2_packet_validation`, `l4d2_a2s_filters`, `l4d2_udp_base` |
| `vpn-gateway` | `tcp_ssh`, `openvpn_server` |

Los tres módulos UDP de juego son una unidad de composición. `openvpn_server`
y `openvpn_sitetosite` son incompatibles. `l4d2_tcp_protect` es opcional: acepta
NEW TCP bajo límite en puertos explícitos; `games` no lo activa por defecto.
Seleccionar módulos no instala los servicios que protegen.

## Host, contenedores y rutas

| Opción | Valores y efecto |
|---|---|
| `HOST_SERVICES` | `true`/`false`: exposición de servicios del host |
| `CONTAINER_POLICY` | `off`/`restrict`: sin integración o publicaciones con grants |
| `ROUTED_POLICY` | `drop`/`unmanaged`: reenvío explícito o delegado a otras reglas |
| `DOCKER_BACKEND` | `auto`/`iptables`/`nftables`/`none`: diagnóstico esperado |
| `IPTABLES_FRONTEND` | `auto`/`nft`/`legacy`: binarios efectivos; no cambia alternativas |
| `ACCESS_POLICY` | Archivo JSON de permisos delimitados |

El default descarta reenvío. `unmanaged` retorna a otras reglas y delega su
protección. `TYPECHAIN=0/1/2` conserva traducción limitada a host/contenedores;
una contradicción falla. No determina la política enrutada ni concede permisos VPN.

`ACCESS_POLICY` admite las listas `host`, `forward` y `containers`. Cada grant
requiere exactamente los campos del ejemplo correspondiente:

| Campos | Uso |
|---|---|
| `group` | Etiqueta de propósito (admins/monitores); no autentica usuarios |
| `source`, `destination` | IP/CIDR completos de la misma familia |
| `input` | Interfaz de entrada exacta |
| `protocol`, `ports` | `tcp` o `udp`, puertos/rangos de destino |
| `output` | Obligatorio en `forward` y `containers` |
| `public_destination`, `public_ports`, `service` | Obligatorios en `containers`: dirección/puerto original y servicio seleccionado |
| `role` | Sólo contenedor `l4d2_udp_base`: `gameserver` o `sourcetv` |

En contenedores, `destination`/`ports` identifican el destino interno tras DNAT;
los rangos públicos e internos deben tener igual longitud. El servicio debe estar
seleccionado y su protocolo debe corresponder. TCP/443 no concede UDP/443.
Los grants `host` son permisos explícitos anteriores a controles públicos y pueden
omitir límites para ese origen/servicio: reservarlos para identidades confiables.
NAT no crea permisos de filtro.

Ver [host y rutas](../config/access.example.json),
[contenedores](../config/containers.example.json) y
[Docker](security/capabilities.md). Los ejemplos no descubren la topología real.

## Familias y estado

`FAMILY_POLICY=dual` genera IPv4/IPv6. Juego iptables exige
`FAMILY_POLICY=ipv4-block-ipv6`: conserva IPv6 habilitado pero bloquea sus servicios
y reenvío, con excepciones ICMPv6/ND. Puede impedir retornos de conexiones
salientes IPv6. Para juego dual usar nftables.

GeoIP sólo filtra IPv4 y exige `GEO_IPV6_POLICY=deny` al combinarse con `dual`.
Alias de router VPN: IPv4. Adaptaciones NAT: prefijos de la misma familia;
no se admiten listas mixtas. Ver [capacidades](security/capabilities.md).

SSH/web limitan por origen y puerto. `ADMIN_SOURCES` restringe fuentes SSH;
vacío significa SSH público sujeto a controles. `STATE_CAPACITY` limita cada
meter/hashlimit a 16..65535 entradas (default 8192). Los timeouts deben cubrir
la recarga completa del burst: uno explícito insuficiente falla; el default se
amplía si hace falta. Los logs se limitan por regla; el descarte continúa al
agotarse ese presupuesto.

## Privilegios y compatibilidad

Bypass completo al host: módulo `whitelist` y `PRIVILEGED_BYPASS=true`.
Con DNS exige además `DNS_ALLOWED_CIDRS`; errores/respuestas fuera de esos
prefijos abortan. Preferir grants delimitados.

`SSH_DOCKER`, `TCP_DOCKER`, `UDP_DOCKER` no aceptan listas no vacías: migrar a
grants. Reinicios automáticos Docker, módulos de egress amplios y opciones VPN
sin implementación equivalente se rechazan. Consultar [migración](security/migration.md).

## Composición sin modificar reglas

```sh
# Usa valores del ejemplo games y selecciona también web.
./nftables.rules.sh plan --env-file config/profiles/games.conf --profile web --profile games
# Decisión explícita de familia para juego iptables.
./iptables.rules.sh validate --env-file config/profiles/games.conf --set FAMILY_POLICY=ipv4-block-ipv6
# Publicaciones de ejemplo: adaptar IP/interfaces antes de aplicar.
./nftables.rules.sh validate --env-file config/profiles/web.conf --profile web --profile games --set CONTAINER_POLICY=restrict --set ACCESS_POLICY=config/containers.example.json
```

`validate`, `generate` y `plan` no prueban kernel ni conectividad. Después se
comprueba y ensaya la candidata en VM desechable antes de desplegar.
