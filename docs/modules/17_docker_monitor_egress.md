# Módulo unificado — docker_monitor_egress (ip/nf)

## Objetivo
Permitir egreso de monitoreo desde subredes Docker hacia destinos LAN específicos (por ejemplo, `Prometheus -> node-exporter:9100` en otro servidor).

## Backends
- iptables: `modules/ip/ip_23_docker_monitor_egress.sh` (`ID=ip_docker_monitor_egress`)
- nftables: `modules/nf/nf_23_docker_monitor_egress.sh` (`ID=nf_docker_monitor_egress`)

## Alias de activación
- `docker_monitor_egress`

## Variables
- `TYPECHAIN`
- `DOCKER_MONITOR_EGRESS_SUBNETS` (CIDRs origen, separados por coma)
- `DOCKER_MONITOR_EGRESS_TARGETS` (IPv4 destino, separadas por coma)
- `DOCKER_MONITOR_EGRESS_TCP_PORTS` (puertos/rangos TCP permitidos)

## Defaults
- `DOCKER_MONITOR_EGRESS_SUBNETS="172.16.0.0/12"`
- `DOCKER_MONITOR_EGRESS_TARGETS=""`
- `DOCKER_MONITOR_EGRESS_TCP_PORTS="9100"`

## Alcance de reglas
- `nftables`: agrega reglas en cadena `forward`.
- `iptables`: agrega reglas en cadena `DOCKER-USER` (cuando `TYPECHAIN` incluye flujo Docker).

## Ejemplo (caso valpo1 -> valpo2)
```env
DOCKER_MONITOR_EGRESS_SUBNETS="172.21.0.0/16"
DOCKER_MONITOR_EGRESS_TARGETS="192.168.1.202"
DOCKER_MONITOR_EGRESS_TCP_PORTS="9100"
```

## Nota operativa
Si `DOCKER_MONITOR_EGRESS_TARGETS` está vacío, el módulo no aplica reglas (comportamiento seguro por defecto).
