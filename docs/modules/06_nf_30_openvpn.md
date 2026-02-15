Módulo 06 — nf_30_openvpn.sh

Descripción:
Este módulo añade reglas específicas para tráfico de OpenVPN en el backend `nftables`. Configura las excepciones de puerto/protocolo necesarias y garantiza que el túnel VPN pueda establecer y mantener las conexiones entrantes y salientes según la topología definida.

Contextos recomendados:
- Usar en hosts que actúen como servidores o gateways OpenVPN donde el servicio de VPN debe quedar accesible.
- Verificar las interfaces y políticas de enrutado antes de activar las reglas para evitar pérdida de conectividad.
- Mantener reglas explícitas y auditadas; en entornos gestionados preferir integraciones con la configuración del servicio VPN para evitar duplicidad.
