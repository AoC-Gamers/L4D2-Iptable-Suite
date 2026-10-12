# L4D2, A2S y SourceTV

El perfil [games.conf](../../config/profiles/games.conf) activa SSH y el grupo
`l4d2_packet_validation` + `l4d2_a2s_filters` + `l4d2_udp_base`. Los tres controles
UDP se requieren juntos. El recorrido efectivo es clasificación → validaciones
aplicables → límites de clase/estado → veredicto final. UDP establecido de juego
pasa por sus controles antes de la aceptación general de conexiones establecidas.
El bypass de clasificación no es una aceptación final: [consultas Source](source-queries.md).

## Puertos y controles

| Configuración | Default / alcance |
|---|---|
| `L4D2_GAMESERVER_UDP_PORTS` | `27015`; GameServer y clasificadores connect/reserve |
| `L4D2_SOURCETV_UDP_PORTS` | `27020`; separado, no puede solaparse con GameServer |
| `L4D2_CMD_LIMIT` | `100`; rango 10..10000, presupuesto UDP establecido |
| `UDP_NEW_SRC_RATE/BURST` | `8`/`24` por origen y puerto |
| `UDP_NEW_GLOBAL_RATE/BURST` | `240`/`960` global por puerto |
| `SOURCETV_UDP_NEW_*` | Heredan los correspondientes UDP NEW si están ausentes |
| `ENABLE_MALFORMED_FILTER` | `false`; requiere capturas representativas antes de activarlo |
| `ENABLE_PACKET_NORMALIZATION_LOGS`, `ENABLE_UDP_BASELINE_LOGS` | `false`; logging no determina presencia del bloqueo |
| `ENABLE_UDP_NEW_LARGE_FILTER` | `false`; opt-in, umbral histórico explicado abajo |

La validación de longitudes se aplica a GameServer y SourceTV. nftables compara
longitud del datagrama UDP y soporta doble pila. iptables requiere explícitamente
`FAMILY_POLICY=ipv4-block-ipv6`; bloquea servicios/reenvío IPv6, no desactiva IPv6,
y puede cortar retornos IPv6 salientes. Consulta [motores](../firewall/backends.md).
`UDP_NEW_LARGE_DROP_MIN_LEN=1024` conserva escala IPv4 histórica: compara longitud
UDP >=1004 al restar 20; no representa longitud IP real. No actives filtros
opcionales basándote solo en paquetes sintéticos.

## SourceTV

SourceTV tiene puertos y overrides NEW propios. Hereda límites solo para variables
ausentes, no las vaciadas. No recibe la excepción `71` de login GameServer; ese
tráfico queda bajo el limitador NEW genérico. Grants Docker requieren
`role=sourcetv` y puertos internos del servicio; GameServer usa `role=gameserver`.
Las pruebas existentes usan cargas sintéticas TV/A2S/login, **no clientes reales**
de jugador ni SourceTV ni descubrimiento Steam completo.

## TCP opcional

`l4d2_tcp_protect` queda fuera de `games`. Acepta TCP NEW bajo límite en
`L4D2_GAMESERVER_TCP_PORTS` explícitos; vacío no abre puertos. El ID heredado
`l4d2_tcpfilter_chain` solo es compatibilidad y requiere ese módulo. No hay una
variante del limitador TCP de juego para contenedores: un grant `allowlist_ports`
solo concede acceso TCP acotado. No etiquetes RCON como SSH para obtener otro filtro.

Desde raíz del checkout, sin root, revisar ejemplo ficticio y decisión de familia:

```sh
./nftables.rules.sh plan --env-file config/profiles/games.conf
./iptables.rules.sh validate --env-file config/profiles/games.conf --set FAMILY_POLICY=ipv4-block-ipv6
```

El resultado acredita composición, no conectividad. Antes de aplicar sigue
[el flujo con recuperación](../firewall/transactions.md); comprueba A2S, entrada
al servidor y TV con clientes propios y contadores en entorno representativo.
Si falla, no excluyas un control para lograr PASS: compara puertos, capturas y
[clasificadores](source-queries.md). GeoIP es opcional [IPv4](../automation/geoip.md).

Código: [compiler.py](../../core/compiler.py), [módulos nft](../../modules/nf/).
Pruebas: [integration.py](../../tests/integration.py), [policy-flows.py](../../tests/policy-flows.py).
[Límites](../security/limitations.md) separa cobertura sintética y despliegue pendiente.
