# Índice de módulos

Breve índice de la documentación de cada módulo. Cada entrada enlaza al fichero con la descripción y recomendaciones de uso.

- [01_preload.md](01_preload.md) — Preparación e inicialización previa a la carga de módulos.
- [02_postload.md](02_postload.md) — Limpieza y verificación tras aplicar los módulos.
- [03_chain_setup.md](03_chain_setup.md) — Inicialización base de cadenas/tablas (ip/nf).
- [04_whitelist.md](04_whitelist.md) — Whitelist IP/dominio (ip/nf).
- [05_allowlist_ports.md](05_allowlist_ports.md) — Excepciones de puertos (ip/nf).
- [06_openvpn.md](06_openvpn.md) — Reglas OpenVPN (ip/nf).
- [07_tcp_ssh.md](07_tcp_ssh.md) — SSH base (ip/nf).
- [08_http_https_protect.md](08_http_https_protect.md) — Protección HTTP/HTTPS (ip/nf).
- [09_l4d2_udp_base.md](09_l4d2_udp_base.md) — Base UDP L4D2 (ip/nf).
- [10_l4d2_packet_validation.md](10_l4d2_packet_validation.md) — Validación de paquetes L4D2 (ip/nf).
- [11_l4d2_a2s_filters.md](11_l4d2_a2s_filters.md) — Filtros A2S L4D2 (ip/nf).
- [12_finalize.md](12_finalize.md) — Cierre final (ip/nf).
- [13_ip_loopback.md](13_ip_loopback.md) — Módulo específico `ip`.
- [14_ip_l4d2_tcpfilter_chain.md](14_ip_l4d2_tcpfilter_chain.md) — Módulo específico `ip` (`ip_l4d2_tcpfilter_chain`).
- [15_l4d2_tcp_protect.md](15_l4d2_tcp_protect.md) — Protección TCP L4D2 (ip/nf).
- [16_docker_dns_egress.md](16_docker_dns_egress.md) — Egreso DNS para subredes Docker (ip/nf).
- [17_docker_monitor_egress.md](17_docker_monitor_egress.md) — Egreso de monitoreo Docker hacia targets LAN (ip/nf).
- [18_geo_country_filter.md](18_geo_country_filter.md) — Allowlist/denylist geográfica IPv4 para UDP de juego (nft).
