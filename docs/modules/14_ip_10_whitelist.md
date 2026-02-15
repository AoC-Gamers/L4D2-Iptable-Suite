Módulo 14 — ip_10_whitelist.sh

Descripción:
Este módulo implementa listas blancas de direcciones IP para el backend `iptables`. Permite explícitamente tráfico desde IPs o redes de confianza antes de aplicar reglas más restrictivas, reduciendo el riesgo de bloquear servicios administrativos o internos.

Contextos recomendados:
- Útil en entornos con grupos de confianza (administradores, servicios internos) que requieren acceso permanente.
- Para grandes conjuntos de IP, considerar mecanismos externos o dinámicos; mantener la lista manejable.
- Asegurar que las entradas provengan de fuentes verificadas y auditar cambios periódicamente.
