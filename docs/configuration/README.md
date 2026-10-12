# Configuración, perfiles y permisos

El núcleo lee configuración declarativa y genera una candidata antes de modificar
reglas. Para comandos privilegiados, revisar la [operación](../firewall/transactions.md)
y desplegar código/configuración root fuera del checkout del usuario.

## Archivo y precedencia

Desde la raíz del checkout, sin root, estos comandos solo validan/generan un plan
con valores ficticios del ejemplo; no comprueban kernel ni aplican reglas:

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

## Elegir composición y permisos

Consulta [perfiles y selección efectiva](profiles.md), [permisos delimitados](access-policy.md)
y la [referencia de variables/defaults](reference.md). `HOST_SERVICES`,
`CONTAINER_POLICY` y `ROUTED_POLICY` se configuran independientemente; NAT no
concede filtrado. Los grants y su tuple DNAT se documentan únicamente en la guía de ACL.

## Familias y estado

`FAMILY_POLICY=dual` genera IPv4/IPv6. Juego iptables exige
`FAMILY_POLICY=ipv4-block-ipv6`: conserva IPv6 habilitado pero bloquea sus servicios
y reenvío, con excepciones ICMPv6/ND. Puede impedir retornos de conexiones
salientes IPv6. Para juego dual usar nftables.

GeoIP sólo filtra IPv4 y exige `GEO_IPV6_POLICY=deny` al combinarse con `dual`.
Alias de router VPN: IPv4. Adaptaciones NAT: prefijos de la misma familia;
no se admiten listas mixtas. Ver [capacidades](../firewall/backends.md).

SSH/web limitan por origen y puerto. `ADMIN_SOURCES` restringe fuentes SSH;
vacío significa SSH público sujeto a controles. `STATE_CAPACITY` limita cada
meter/hashlimit a 16..65535 entradas (default 8192). Los timeouts deben cubrir
la recarga completa del burst: uno explícito insuficiente falla; el default se
amplía si hace falta. Los logs se limitan por regla; el descarte continúa al
agotarse ese presupuesto.

En iptables el compilador fija tanto `--hashlimit-htable-size` como
`--hashlimit-htable-max` a `STATE_CAPACITY`: el máximo por sí solo no delimita
capacidades pequeñas si el kernel elige una tabla hash mayor. Esta capacidad
corresponde a cada regla, no a un presupuesto agregado de memoria del host.
La [regresión de política](../testing/README.md#regresiones-conservadas) comprueba
el corte efectivo; no sustituye un ensayo de carga sostenida del destino.

## Privilegios y compatibilidad

Bypass completo al host: módulo `whitelist` y `PRIVILEGED_BYPASS=true`.
Con DNS exige además `DNS_ALLOWED_CIDRS`; errores/respuestas fuera de esos
prefijos abortan. Preferir grants delimitados.

`SSH_DOCKER`, `TCP_DOCKER`, `UDP_DOCKER` no aceptan listas no vacías: migrar a
grants. Reinicios automáticos Docker, módulos de egress amplios y opciones VPN
sin implementación equivalente se rechazan. Consultar [migración](../migration/README.md).

## Composición sin modificar reglas

Desde raíz, sin root; ejemplos ficticios para revisar selección/familias y ACL:

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
