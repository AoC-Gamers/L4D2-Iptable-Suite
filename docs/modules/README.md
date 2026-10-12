# Módulos y composición actual

Esta carpeta documenta IDs de compatibilidad y funciones visibles al componer la política. No describe un loader que ejecute todos los `*.sh`: el CLI `ipp.sh` lee metadata literal y `core/compiler.py` compone reglas solo para módulos seleccionados. Los módulos shell son una interfaz de generación interna restringida; no controlan servicios, Docker ni el firewall directamente.

## Contrato común

- CLI: `ipp.sh validate|generate|plan|check|apply|confirm|rollback|disable|save|load|status|doctor`. Consulte [operaciones](../security/operations.md).
- Perfiles: `host-minimal` (SSH), `web` (SSH + HTTP/HTTPS), `games` (SSH + UDP base, validación y A2S), `vpn-gateway` (SSH + OpenVPN server). Los módulos `chain_setup`, `finalize` y `loopback` son siempre core.
- `--only` de CLI reemplaza selección del archivo; `--only ''` intencionalmente elige core-only. En contraste, una asignación `MODULES_ONLY=` vacía en el archivo de configuración conserva el fallback del perfil. El entorno exportado del proceso no reemplaza el archivo de configuración. `--skip` excluye IDs funcionales, nunca el core.
- `.env` son asignaciones declarativas `KEY=VALUE`; no es shell. Opciones desconocidas, duplicadas, expansiones y valores incompatibles se rechazan.
- `TYPECHAIN=0/1/2` es un alias transitorio y contradictorio con las opciones nuevas falla. Use `HOST_SERVICES`, `CONTAINER_POLICY`, `ROUTED_POLICY` y grants `ACCESS_POLICY` explícitos. Los defaults descartan el routing y no abren permisos NAT.
- Los valores no vacíos de `SSH_DOCKER`, `TCP_DOCKER` y `UDP_DOCKER` se rechazan. `DOCKER_INPUT_COMPAT=true` y `DOCKER_CHAIN_AUTORECOVER=true` también se rechazan; sus valores `false` son válidos. Los módulos heredados de egress Docker se rechazan. Use grants delimitados; TCP y UDP son independientes.
- iptables con módulos de juego requiere `FAMILY_POLICY=ipv4-block-ipv6`. nftables puede jugar dual-stack. GeoIP sigue IPv4-only y en modo dual necesita declarar denegación IPv6.
- No excluya controles de juego por separado: UDP base, packet validation y A2S requieren selección conjunta. `l4d2_tcp_protect` es opt-in.

Las filas de módulo explican propósito actual y migraciones; fuentes de verdad de permisos y evidencia: [capacidades](../security/capabilities.md), [migración](../security/migration.md), [resultados](../security/results.md).

## Referencias por ID

- [preload](01_preload.md) y [postload](02_postload.md): compatibilidad retirada/helpers históricos.
- [chain setup](03_chain_setup.md), [whitelist](04_whitelist.md), [allowlist ports](05_allowlist_ports.md), [OpenVPN](06_openvpn.md).
- [SSH](07_tcp_ssh.md), [HTTP/HTTPS](08_http_https_protect.md), [UDP base](09_l4d2_udp_base.md), [validación](10_l4d2_packet_validation.md), [A2S](11_l4d2_a2s_filters.md).
- [finalize](12_finalize.md) y [loopback](13_ip_loopback.md): core obligatorio.
- [TCPfilter](14_ip_l4d2_tcpfilter_chain.md): compatibilidad; [protección TCP de juego](15_l4d2_tcp_protect.md).
- [egress DNS Docker](16_docker_dns_egress.md) y [egress monitoreo Docker](17_docker_monitor_egress.md): retirados, migrar a grants.
- [GeoIP](18_geo_country_filter.md): nftables e IPv4 solamente.
