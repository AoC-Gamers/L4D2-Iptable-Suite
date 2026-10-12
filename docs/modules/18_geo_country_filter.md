# `geo_country_filter` — GeoIP IPv4 para UDP de juego

Disponible en nftables. Solo afecta tráfico IPv4 de entrada al host en los puertos GameServer/SourceTV configurados. Puede seleccionarse de forma independiente; para combinar GeoIP con los controles de juego, seleccione también el grupo completo UDP base, validación y A2S. `GEO_POLICY_MODE` admite `off`, `allowlist` y `denylist`; dentro de la política geo rige deny manual, luego allow manual, luego decisión por país. No es un sustituto de controles de tasa.

La tabla de datos usa archivos `CC.ipv4.txt` y listas manuales IPv4. En `FAMILY_POLICY=dual`, un modo geo activo exige `GEO_IPV6_POLICY=deny`, que descarta UDP IPv6 en esos puertos: no existe GeoIPv6 en esta implementación. Con iptables el ID no está disponible. Los archivos son inputs de configuración confiables al operar como root; revise propietario/permisos y procedencia.

`geoip-check` clasifica entradas sin aplicar reglas; el updater `geoip-update` requiere datos de origen y no valida licencia/calidad de datos externos. La evidencia de updater offline usa un ZIP sintético, no una base actual MaxMind. [Resultados](../security/results.md).
