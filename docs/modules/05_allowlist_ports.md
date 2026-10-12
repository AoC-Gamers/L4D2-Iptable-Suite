# `allowlist_ports` — puertos adicionales al host

`BYPASS_TCP_PORTS` y `BYPASS_UDP_PORTS` permiten los puertos listados para los servicios del host cuando se selecciona `allowlist_ports`. No son grants de routing ni autorizaciones Docker. Las listas UDP globales no se admiten junto con el conjunto de controles de juego; la superposición TCP con SSH, web o protección TCP de juego se rechaza.

Para forwarding use grants `forward` con source/destination, interfaces, protocolo y puertos. Para publicaciones Docker use grants `containers` que declaren el tuple público e interno y servicio. TCP no abre UDP/QUIC. Vea [capacidades](../security/capabilities.md) y [migración](../security/migration.md).
