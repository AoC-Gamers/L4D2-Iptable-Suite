Módulo 05 — nf_20_allowlist_ports.sh

Descripción:
Este módulo gestiona una "allowlist" de puertos para el backend `nftables`. Normaliza las especificaciones de puertos y crea `sets` o reglas reutilizables que permiten tráfico hacia servicios explícitos (por ejemplo servidores de juego, DNS, SSH) antes de aplicar reglas más restrictivas.

Contextos recomendados:
- Usar cuando se necesita exponer de forma explícita puertos de servicios conocidos en servidores o máquinas virtuales dedicadas.
- Adecuado para entornos donde el número de puertos es limitado y estable; para colecciones muy grandes considerar soluciones dinámicas o sistemas de listas externas.
- Mantener idempotencia y revisar las entradas periódicamente; evitar introducir puertos desde fuentes no verificadas para no exponer servicios críticos.
