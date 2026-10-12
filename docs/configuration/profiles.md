# Perfiles y selección efectiva

Los perfiles seleccionan módulos; no cargan automáticamente los archivos de ejemplo
ni instalan servicios. Los archivos versionados contienen decisiones que solo se
usan con `--env-file`. Configuración de archivo y precedencia:
[guía principal](README.md); tipos/defaults: [referencia](reference.md).

| Perfil | Módulos | Ejemplo y decisiones |
|---|---|---|
| `host-minimal` | `tcp_ssh` | [host-minimal.conf](../../config/profiles/host-minimal.conf); adaptar puerto y fuentes administrativas ficticias |
| `web` | `tcp_ssh`, `http_https_protect` | [web.conf](../../config/profiles/web.conf); TCP/80,443, sin UDP/443 |
| `games` | SSH + `l4d2_packet_validation`, `l4d2_a2s_filters`, `l4d2_udp_base` | [games.conf](../../config/profiles/games.conf); UDP GameServer/TV separados; juego dual solo nftables |
| `vpn-gateway` | `tcp_ssh`, `openvpn_server` | [vpn-gateway.conf](../../config/profiles/vpn-gateway.conf); adaptar tun/LAN/ACL; NAT no autoriza rutas |

| Entrada | Conjunto efectivo |
|---|---|
| Lista ausente o `MODULES_ONLY=''` en archivo | Usa `PROFILE`, cuyo default es `host-minimal` |
| `--only tcp_ssh,http_https_protect` | Sustituye lista del archivo y selección por perfiles |
| `--only ''` | Solo núcleo, aun si hay perfiles |
| `--profile web --profile games` sin `only` efectiva | Unión de módulos |
| `--skip` | Sustituye `MODULES_EXCLUDE` y excluye del conjunto; no puede excluir núcleo |

Setup, finalize, loopback e ICMP/ICMPv6 son núcleo obligatorio. IDs desconocidos,
alias ambiguos, dependencias/conflictos y solapamientos fallan antes de aplicar.
Los tres módulos UDP son indivisibles; `openvpn_server` y `openvpn_sitetosite`
son excluyentes. TCP de juego es opt-in, fuera de `games`.

Desde la raíz del checkout, sin root, estos comandos generan planes/validación,
sin consultar el kernel. Los valores proceden de ejemplos ficticios:

```sh
./nftables.rules.sh plan --env-file config/profiles/games.conf --profile web --profile games
./iptables.rules.sh validate --env-file config/profiles/games.conf --set FAMILY_POLICY=ipv4-block-ipv6
```

El primer plan debe mostrar SSH, web y el grupo UDP. El segundo exige decisión
explícita IPv6 para iptables; no desactiva IPv6 en el sistema. No apliques hasta
comprobar [capacidades](../firewall/backends.md) y [recuperación](../firewall/transactions.md).
Cambios parciales no usan estos perfiles de entrada: recomponen estado confirmado,
según [persistencia](../firewall/persistence.md).
