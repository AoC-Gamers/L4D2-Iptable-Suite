Módulo 15 — ip_20_allowlist_ports.sh

Descripción:
Este módulo gestiona una "allowlist" de puertos para el backend `iptables`. Normaliza las especificaciones de puertos y crea reglas reutilizables que permiten tráfico hacia servicios explícitos (por ejemplo servidores de juego, DNS, SSH) antes de aplicar reglas más restrictivas.

Contextos recomendados:
- Usar en servidores dedicados o máquinas virtuales donde ciertos puertos deben permanecer accesibles de forma controlada.
- Para grandes conjuntos de puertos, considerar soluciones dinámicas o externas; mantener la lista manejable y auditada.
- Asegurar pruebas en staging antes de desplegar en producción y mantener idempotencia para poder re-ejecutar el módulo sin romper conectividad.
