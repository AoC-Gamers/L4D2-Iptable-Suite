# `chain_setup` — núcleo obligatorio

El núcleo genera las cadenas/tablas privadas y hooks base del backend seleccionado. `chain_setup` no se carga ni se excluye como módulo funcional: es parte del contrato obligatorio junto a `finalize` y `loopback`.

- nftables: tabla `inet` privada y cadenas de input/forward; límites y propiedad se validan antes de aplicar.
- iptables: cadenas propias por tabla/familia e inserción selectiva en hooks; no vacía tablas compartidas.
- La base acepta loopback, estados relacionados y errores ICMP/ICMPv6 necesarios. `FAMILY_POLICY=ipv4-block-ipv6` agrega bloqueo explícito IPv6 de input/forward con excepciones ICMPv6/ND del host; no equivale a conectividad IPv6 completa.

`TYPECHAIN` solo se conserva como alias de migración: `0` traduce host activo/contenedores apagados, `1` host apagado/contenedores restrictivos, `2` ambos activos/restrictivos. Conflictos con `HOST_SERVICES` o `CONTAINER_POLICY` se rechazan. Para permisos use políticas y grants de [capacidades](../security/capabilities.md), no `TYPECHAIN`.
