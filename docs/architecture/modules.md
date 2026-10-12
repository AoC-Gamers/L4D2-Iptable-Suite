# Catálogo de módulos y compatibilidad

El núcleo lee metadata literal y solo ejecuta generadores seleccionados después de
validar la composición. No es un loader indiscriminado de scripts. El contrato de
extensión está en [arquitectura](README.md); perfiles, permisos y familias en
[configuración](../configuration/README.md). Los nombres numerados anteriores
siguen resolviendo mediante avisos; el número no define el orden efectivo.

<a id="preloadsh"></a>

## `preload.sh` — compatibilidad retirada

`modules/preload.sh` conserva una función de compatibilidad para instalaciones antiguas. La función `run_preload` informa que el preload fue retirado y termina con error; no parsea argumentos ni carga la configuración actual.

Use `ipp.sh` como CLI (`--env-file`, `--set`, `--only`, `--skip`, `--profile`) y consulte [operaciones](../firewall/transactions.md) y [migración](../migration/README.md). El CLI lee `.env` como asignaciones `KEY=VALUE`, nunca como shell. Las pruebas unitarias y `validate` no aplican reglas al kernel.

<a id="postloadsh"></a>

## `postload.sh` — helper heredado

`modules/postload.sh` es un helper de salida histórica, no el cierre del flujo actual. El núcleo genera y valida la candidata antes de entregarla al motor transaccional; los módulos no controlan servicios.

No use este script para inferir que una política quedó aplicada o confirmada. Consulte `ipp.sh status` y [operaciones](../firewall/transactions.md). La evidencia de integración y sus límites está en [aprobación](../security/approval.md).

<a id="chain-setup"></a>

## `chain_setup` — núcleo obligatorio

El núcleo genera las cadenas/tablas privadas y hooks base del backend seleccionado. `chain_setup` no se carga ni se excluye como módulo funcional: es parte del contrato obligatorio junto a `finalize` y `loopback`.

- nftables: tabla `inet` privada y cadenas de input/forward; límites y propiedad se validan antes de aplicar.
- iptables: cadenas propias por tabla/familia e inserción selectiva en hooks; no vacía tablas compartidas.
- La base acepta loopback, estados relacionados y errores ICMP/ICMPv6 necesarios. `FAMILY_POLICY=ipv4-block-ipv6` agrega bloqueo explícito IPv6 de input/forward con excepciones ICMPv6/ND del host; no equivale a conectividad IPv6 completa.

`TYPECHAIN` solo se conserva como alias de migración: `0` traduce host activo/contenedores apagados, `1` host apagado/contenedores restrictivos, `2` ambos activos/restrictivos. Conflictos con `HOST_SERVICES` o `CONTAINER_POLICY` se rechazan. Para permisos use políticas y grants de [capacidades](../firewall/backends.md), no `TYPECHAIN`.

<a id="whitelist"></a>

## `whitelist` — bypass privilegiado al host

El módulo reconoce `BYPASS_SOURCE_IPS` y dominios resueltos, pero la lista no concede acceso por sí sola: la configuración exige seleccionar `whitelist` y declarar `PRIVILEGED_BYPASS=true`.

Uso, configuración, verificación y límites: [guía canónica](../configuration/access-policy.md).

<a id="allowlist-ports"></a>

## `allowlist_ports` — puertos adicionales al host

Abre puertos TCP/UDP adicionales del host sin controles de servicio específicos.
No es un permiso de routing ni de contenedores. Configuración y restricciones:
[permisos delimitados](../configuration/access-policy.md).

<a id="openvpn"></a>

## OpenVPN — adaptación de firewall

`openvpn_server` y `openvpn_sitetosite` son modos excluyentes de configuración.

Uso, configuración, verificación y límites: [guía canónica](../vpn/README.md).

<a id="tcp-ssh"></a>

## `tcp_ssh` — servicio SSH del host

El módulo agrega el puerto `SSH_PORT` (por defecto 22) al input del host y limita conexiones TCP nuevas por origen.

Uso, configuración, verificación y límites: [guía canónica](../administration/README.md).

<a id="http-https-protect"></a>

## `http_https_protect` — HTTP/HTTPS

Controla conexiones TCP nuevas a `HTTP_HTTPS_PORTS` (por defecto `80,443`) con tasa y ráfaga por origen y puerto.

Uso, configuración, verificación y límites: [guía canónica](../web/README.md).

<a id="l4d2-udp-base"></a>

## `l4d2_udp_base` — estado UDP de juego

Este módulo controla UDP NEW/ESTABLISHED para `L4D2_GAMESERVER_UDP_PORTS` y `L4D2_SOURCETV_UDP_PORTS`.

Uso, configuración, verificación y límites: [guía canónica](../l4d2/README.md).

<a id="l4d2-packet-validation"></a>

## `l4d2_packet_validation` — validación UDP

Seleccionado junto con `l4d2_udp_base` y `l4d2_a2s_filters`, valida longitudes inválidas y, de forma opt-in, patrones malformados en puertos GameServer/SourceTV.

Uso, configuración, verificación y límites: [guía canónica](../l4d2/README.md).

<a id="l4d2-a2s-filters"></a>

## `l4d2_a2s_filters` — consultas UDP Source

El módulo aplica límites por clase a A2S INFO/PLAYERS/RULES y a clasificadores de login/Steam-group en los puertos de juego.

Uso, configuración, verificación y límites: [guía canónica](../l4d2/source-queries.md).

<a id="finalize"></a>

## `finalize` — núcleo obligatorio

`finalize` es parte de la composición obligatoria del núcleo, no un cierre shell posterior. El motor genera una candidata, comprueba límites/propiedad y aplica por las transacciones descritas en [operaciones](../firewall/transactions.md). No expone una opción para omitir el cierre del pipeline.

La salida de `validate` solo prueba validación lógica/generación; no hace kernel check ni instala reglas. Para saber el estado activo use `status` y consulte el historial de aceptación en [aprobación](../security/approval.md).

<a id="loopback"></a>

## `loopback` — núcleo obligatorio

Loopback se acepta en el input como regla de base en ambos backends. El ID legacy `loopback` puede resolverse por compatibilidad, pero no es un módulo funcional opcional ni se puede excluir: forma parte del núcleo junto con setup y finalize.

La política IPv6 `ipv4-block-ipv6` conserva las excepciones necesarias de ND/ICMPv6 además de loopback; no promete conectividad general IPv6. Detalle en [capacidades](../firewall/backends.md).

<a id="l4d2-tcpfilter-chain"></a>

## `l4d2_tcpfilter_chain` — alias de compatibilidad

Este identificador antiguo solo se acepta si se selecciona también `l4d2_tcp_protect`; el compilador actual no emite reglas propias para él en ninguno de los motores. El control actual se implementa en `l4d2_tcp_protect`. Migre las listas `TCP_DOCKER` rechazadas a grants `containers` y configure `L4D2_GAMESERVER_TCP_PORTS` explícitamente.

No confunda una cadena heredada llamada `TCPfilter` con un objeto que la suite haya creado o pueda adoptar. El módulo `l4d2_tcp_protect` aplica el control a los puertos TCP de juego configurados; el perfil `games` no lo activa por defecto.

<a id="l4d2-tcp-protect"></a>

## `l4d2_tcp_protect` — TCP de juego/RCON

Aplica limitación de conexiones TCP NEW por origen a `L4D2_GAMESERVER_TCP_PORTS`.

Uso, configuración, verificación y límites: [guía canónica](../l4d2/README.md).

<a id="docker-dns-egress"></a>

## `docker_dns_egress` — retirado, requiere migración

La configuración rechaza seleccionar `docker_dns_egress`: la antigua regla por subred y puerto 53 no identifica interfaz ni destino DNS y concedía un ámbito de forwarding demasiado amplio.

Uso, configuración, verificación y límites: [guía canónica](../docker/README.md).

<a id="docker-monitor-egress"></a>

## `docker_monitor_egress` — retirado, requiere migración

La antigua autorización por subred/targets/puerto se rechaza como módulo.

Uso, configuración, verificación y límites: [guía canónica](../docker/README.md).

<a id="geo-country-filter"></a>

## `geo_country_filter` — GeoIP IPv4 para UDP de juego

Disponible en nftables.

Uso, configuración, verificación y límites: [guía canónica](../automation/geoip.md).
