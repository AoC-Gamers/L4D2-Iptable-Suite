# Backend iptables: comportamiento actual

`iptables.rules.sh` es un wrapper de compatibilidad que invoca `core/fw.py --backend iptables` directamente. Las reglas no se definen en este documento como una receta manual: `core/config.py` valida la configuración y `core/compiler.py` genera una candidata declarativa que el motor transaccional aplica a objetos de propiedad exclusiva.

## Uso

Desde cualquier directorio, las rutas absolutas apuntan a la instalación confiable
del destino. `validate`/`plan` no necesitan root ni consultan kernel; los comandos
con `sudo` requieren root. Es una referencia: `check` puede recuperar journal
vencido; `apply` modifica Netfilter y debe confirmar conexión nueva o revertir
siguiendo [transacciones](transactions.md), no ejecutar esta lista a ciegas.

```bash
/opt/l4d2-firewall/iptables.rules.sh validate \
  --env-file /etc/l4d2-firewall/web.conf
/opt/l4d2-firewall/iptables.rules.sh plan \
  --env-file /etc/l4d2-firewall/web.conf
sudo /opt/l4d2-firewall/iptables.rules.sh check \
  --env-file /etc/l4d2-firewall/web.conf
sudo /opt/l4d2-firewall/iptables.rules.sh apply \
  --env-file /etc/l4d2-firewall/web.conf
sudo /opt/l4d2-firewall/iptables.rules.sh status
```

Ejecute los comandos desde una instalación confiable propiedad de root y pase un archivo de configuración explícito. `validate` y `plan` son comprobaciones lógicas/generación, no validan reglas en el kernel ni cambian el firewall. `check` comprueba la candidata. `apply` aplica con la confirmación/rollback descritos en [operaciones](transactions.md). No use las recetas antiguas de este archivo ni `iptables-restore` directo para sustituir el ruleset.

## Composición y selección

El perfil por defecto `host-minimal` solo selecciona SSH; `web` añade HTTP/HTTPS, `games` añade el grupo UDP de juego y `vpn-gateway` añade OpenVPN server. Los perfiles están detallados en [módulos](../architecture/modules.md). Setup, finalize y loopback son obligatorios. Una asignación `MODULES_ONLY=` vacía en el archivo conserva el fallback del perfil, mientras `--only ''` selecciona explícitamente solo el núcleo. `--only` de CLI reemplaza la selección del archivo; el entorno exportado del proceso no sustituye el archivo.

La configuración es declarativa `KEY=VALUE`, sin evaluación de shell. Usa `HOST_SERVICES`, `CONTAINER_POLICY`, `ROUTED_POLICY`, `FAMILY_POLICY` y grants de `ACCESS_POLICY`; `TYPECHAIN=0/1/2` solo es alias de migración. Los valores no vacíos de `SSH_DOCKER`, `TCP_DOCKER` y `UDP_DOCKER`, las opciones `DOCKER_CHAIN_AUTORECOVER=true`/`DOCKER_INPUT_COMPAT=true` y los módulos `docker_dns_egress`/`docker_monitor_egress` se rechazan; los flags Docker en `false` son válidos. Migraciones y límites están en [migration](../migration/README.md).

## Alcance de backend

- `IPTABLES_FRONTEND=auto|nft|legacy` selecciona ejecutables sin cambiar las alternativas del sistema. Se rechaza una mezcla de frontend IPv4/IPv6.
- La candidata conserva tablas compartidas y reemplaza únicamente cadenas propias; instala/quita hooks exactos y falla ante layout heredado ambiguo, pérdida de ownership o integración Docker incompatible. No se vacían tablas ni se cambia una política base global.
- El forwarding predeterminado es `ROUTED_POLICY=drop`. Grants `forward` exigen modo drop y definen tuple/interfaces; `unmanaged` delega otras rutas, no promete filtrado completo de ellas.
- Grants de contenedores verifican publicación DNAT, IP pública, puertos públicos/internos, protocolo, origen/destino e interfaces. TCP no concede UDP. NAT de VPN nunca concede permiso de firewall.
- El payload de juego con iptables está limitado a IPv4; debe usarse `FAMILY_POLICY=ipv4-block-ipv6`. Para juego dual-stack se requiere nftables. Con la política IPv4, el núcleo bloquea input/forward IPv6 salvo excepciones de ICMPv6/ND que requiere el host.
- Whitelist necesita `PRIVILEGED_BYPASS=true`; DNS además requiere CIDRs permitidos y falla cerrada. Es un bypass de input al host, no un permiso general para rutas/containers.

La ejecución en VM y las combinaciones probadas están separadas de la capacidad teórica en [capabilities](backends.md) y [aprobación](../security/approval.md). En particular, paquetes de juego fueron sintéticos, no un cliente real de L4D2; la validación no certifica otros kernels, frontends o versiones de Docker.
