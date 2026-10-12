# Capacidades y convivencia

La capacidad implementada y la evidencia observada son cosas distintas. La
continuación se probó en VM QEMU/KVM con kernel propio `6.8.0-142-generic`,
nftables `1.0.9`, iptables `1.8.10` (frontends nft y legacy), OpenVPN `2.6.19`
y Docker Engine `29.8.2`. El daemon de prueba y su red son privados; el Docker y
firewall del anfitrión permanecieron intactos. Docker nftables es experimental
según su documentación oficial. Versiones y límites en [results.md](results.md).

| Capacidad | nftables nativo | iptables-nft | iptables-legacy |
|---|---|---|---|
| Host mínimo / SSH / web doble pila | Implementado; tráfico real | Implementado; tráfico real | Implementado; tráfico real en VM |
| Juego UDP, A2S, Steam Group, login, TV | IPv4/IPv6; tráfico sintético real | IPv4; tráfico sintético real | IPv4; tráfico sintético real en VM |
| Juego dual pila | Sí | Rechazado: matcher u32 IPv4 | Rechazado: matcher u32 IPv4 |
| Alternativa juego IPv4 | `FAMILY_POLICY=ipv4-block-ipv6` | Obligatoria | Obligatoria |
| SSH por origen / web por origen+puerto | Meter por familia, timeout, capacidad | Hashlimit por familia, timeout, capacidad | Hashlimit por familia; capacidad efectiva probada en VM |
| Logs acotados + descarte independiente | Límite escalar por regla | `limit` por regla | Mismo emisor |
| Reenvío nativo / VPN sin Docker | Grants v4/v6 probados con tráfico | Grants v4/v6 probados con tráfico | Grants v4/v6 probados con tráfico en VM |
| OpenVPN server NAT / DNAT | NAT con tráfico de integración; TLS/alias en VM | NAT con tráfico de integración; TLS/alias en VM | NAT con tráfico de integración; alias candidata kernel; TLS legacy no ensayado |
| OpenVPN S2S NAT / alias / SNAT | Ruta S2S/alias/TLS con tráfico; SNAT candidata kernel | Ruta S2S/alias/TLS con tráfico; SNAT candidata kernel | DNAT/SNAT candidata kernel; tráfico S2S/TLS legacy no ensayado |
| NAT concede permiso de filtrado | Nunca | Nunca | Nunca |
| Puertos públicos frente a internos | Tuple original + DNAT + destino/interfaces + puerto interno | Igual, conntrack explícito | Igual; tráfico DNAT real en VM |
| SSH_DOCKER / TCP_DOCKER / UDP_DOCKER | Rechazo con migración a grants | Mismo rechazo | Mismo rechazo |
| GeoIP | Sólo IPv4; dual exige `GEO_IPV6_POLICY=deny` | Módulo no disponible, ID rechazado | Módulo no disponible, ID rechazado |
| Whitelist por DNS | Privilegio explícito + CIDRs esperados + fallo cerrado | Igual | Igual |
| Docker DNS/monitor egress heredado | Rechazado; migrar a grants direccionales | Igual | Igual |
| VPN log heredado / interfaz Docker del túnel | Rechazado explícitamente | Igual | Igual |
| Infraestructura setup/finalize/loopback | Núcleo obligatorio | Núcleo obligatorio | Núcleo obligatorio |

La política `ipv4-block-ipv6` conserva IPv6 habilitado y reglas ajenas; instala una
negación explícita de tráfico IPv6 de servicios/reenvío con excepciones ICMPv6/ND
necesarias para el host. No garantiza conectividad saliente IPv6: los retornos no
ICMPv6 también se bloquean. Requiere una decisión consciente del operador.

Los grants de routing soportan ambas familias. NAT VPN requiere que los prefijos
de origen/destino de una adaptación tengan la misma familia; una lista NAT mixta
se rechaza al generar, no se expande silenciosamente. Alias de router sólo IPv4.
SSH/web usan origen+puerto como clave; UDP establecido usa origen+puerto origen+
puerto destino; A2S usa origen+destino puerto y login añade IP destino. Límites
globales adicionales de UDP NEW son explícitos y separados del presupuesto por
origen. No hay límite SSH global adicional oculto.

`HOST_SERVICES`, `CONTAINER_POLICY` y `ROUTED_POLICY` son independientes. Por defecto
el reenvío se descarta. Un host web junto a Docker debe declarar grants de contenedores
y egreso que necesita, o elegir explícitamente `ROUTED_POLICY=unmanaged` y delegar
las otras rutas en otro administrador. `unmanaged` no inserta ACCEPT global; retorna
a las demás reglas. No confundir ese modo con protección del reenvío por la suite.

## Docker

| Suite / Docker | Integración y estado |
|---|---|
| iptables / Docker iptables en el mismo frontend | Hook propio en DOCKER-USER. Se exige cadena y salto de FORWARD existentes. Daemon Docker 29.8.2 real: DNAT/retorno TCP IPv4/IPv6, UDP independiente, egreso explícito y conservación; frontends nft y legacy. |
| nftables / Docker iptables | Tabla propia, forward prioridad -5; DROP previo a Docker. Daemon Docker 29.8.2 real (frontend nft y legacy): DNAT/retorno TCP IPv4/IPv6 y UDP independiente; permisos deben corresponder a publicaciones que Docker permita. Grants nativos de reenvío se rechazan por posible FORWARD DROP de Docker. |
| nftables / Docker nftables | Tabla propia antes de las cadenas de Docker. Daemon Docker 29.8.2 real: DNAT/retorno TCP IPv4/IPv6, UDP independiente, egreso explícito y conservación. No se modifica docker-bridges. |
| iptables / Docker nftables | Rechazado explícitamente. Migrar motor o elegir nftables. |
| Tablas Docker nft + DOCKER-USER residual | Diagnóstico ambiguo y rechazo con grants de contenedores; migración explícita. |
| Docker en otro frontend legacy/nft distinto al elegido | No se presume integración. Si no aparecen los objetos requeridos en el frontend seleccionado, falla antes de aplicar. Usar doctor y revisar alternativas/daemon manualmente. |

`IPTABLES_FRONTEND=auto|nft|legacy` selecciona binarios, sin cambiar alternativas del
sistema. El registro conserva versiones: un cambio de frontend/versión activo no se
acepta silenciosamente. `doctor` informa los binarios efectivos y objetos detectados.
La aplicación resuelve `auto` y conserva el frontend concreto en el journal, la
política y la persistencia; rollback no vuelve a resolver alternativas del sistema.
IPv4/IPv6 con frontends distintos se rechazan para la suite iptables.
Para diagnosticar otro frontend: `ipp.sh doctor --set IPTABLES_FRONTEND=legacy`.
`DOCKER_BACKEND=auto|iptables|nftables|none` restringe el diagnóstico; los nombres de
objetos en el kernel son evidencia operativa, no una certificación de configuración
del daemon. Nombres no estándar o restos de migraciones requieren revisión humana.

Un ACCEPT en una cadena base nftables termina esa cadena, pero otras cadenas base
pueden descartar después. La suite no usa marks para sobrepasar políticas de Docker
ni autoriza acceso directo a redes internas por coincidir un puerto. Cada grant de
contenedor comprueba origen, dirección, interfaces, destino interno, protocolo,
estado DNAT, IP pública original y puertos públicos/internos. TCP/443 no autoriza
UDP/443; QUIC requiere grant independiente (`service=allowlist_ports` y módulo
seleccionado). Para juego se requiere `role=gameserver|sourcetv` y el grupo de tres
módulos de juego; cada publicación usa sus puertos internos para controles.
No hay reinicios ni reparación automática de redes Docker.

## Fuentes oficiales consultadas

- [Netfilter: sustitución atómica](https://wiki.nftables.org/wiki-nftables/index.php/Atomic_rule_replacement).
- [Manual nftables: check, hooks, límites y sets](https://netfilter.org/projects/nftables/manpage.html).
- [Manual iptables-restore](https://man7.org/linux/man-pages/man8/iptables-restore.8.html)
  y manpage instalada de iptables 1.8.10: `--noflush` conserva tablas compartidas,
  pero las cadenas de usuario declaradas se reconstruyen; `--test` no hace commit.
- [Docker con iptables: DOCKER-USER y DNAT](https://docs.docker.com/engine/network/firewall-iptables/).
- [Docker con nftables: ausencia de DOCKER-USER y prioridades](https://docs.docker.com/engine/network/firewall-nftables/).

Las pruebas con daemon real y tráfico publicado IPv4/IPv6 se detallan en
[vm-docker.md](vm-docker.md). Se verifican también hooks/reglas ajenas completos;
la mera existencia de una tabla no se usa como prueba de conservación.

Estas referencias explican la semántica; las versiones efectivamente comprobadas
se registran en results.md. No sustituyen pruebas sobre el kernel/Docker de destino.
