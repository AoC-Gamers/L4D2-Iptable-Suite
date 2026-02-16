Módulo 14 — ip_10_whitelist.sh

Descripción:
Este módulo implementa listas blancas de direcciones IP para el backend `iptables`. Permite explícitamente tráfico desde IPs o redes de confianza antes de aplicar reglas más restrictivas, reduciendo el riesgo de bloquear servicios administrativos o internos.

Variables relevantes:
- `WHITELISTED_IPS`: IPs/subredes de confianza (espacio separado).
- `WHITELISTED_DOMAINS`: dominios de confianza (espacio separado), resueltos a IPv4 al aplicar reglas.

Comportamiento:
- Fusiona IPs estáticas y dominios resueltos en una whitelist efectiva (sin duplicados).
- Si un dominio no resuelve y existe `WHITELISTED_IPS`, continúa con fallback por IP.
- Si no hay fallback por IP, emite advertencia para evitar bloqueo accidental.

Contextos recomendados:
- Útil en entornos con grupos de confianza (administradores, servicios internos) que requieren acceso permanente.
- Para grandes conjuntos de IP, considerar mecanismos externos o dinámicos; mantener la lista manejable.
- Asegurar que las entradas provengan de fuentes verificadas y auditar cambios periódicamente.
