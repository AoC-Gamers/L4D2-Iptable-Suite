Módulo 16 — ip_30_openvpn.sh

Descripción:
Este módulo añade reglas y excepciones necesarias para que OpenVPN funcione correctamente usando `iptables`. Configura puertos y protocolos, ajusta NAT/forwarding si el host actúa como gateway y garantiza que el túnel permita tráfico entrante y saliente según la topología.

Contextos recomendados:
- Usar en hosts que ejecuten OpenVPN como servidor o gateway; comprobar interfaces y políticas de enrutado antes de activar reglas.
- Integrar con la configuración del servicio VPN para evitar reglas duplicadas o inconsistentes.
- Probar primero en un entorno controlado para prevenir cortes de conectividad a servicios gestionados por la VPN.
