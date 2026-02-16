Módulo 04 — nf_10_whitelist.sh

Descripción:
Este módulo implementa listas blancas para el backend `nftables`. Permite explícitamente tráfico desde IPs/redes de confianza y desde dominios resueltos a IPv4 antes de aplicar reglas más restrictivas, reduciendo el riesgo de bloquear accesos administrativos.

Variables relevantes:
- `WHITELISTED_IPS`: IPs/subredes de confianza (espacio separado).
- `WHITELISTED_DOMAINS`: dominios de confianza (espacio separado), resueltos a IPv4 al aplicar reglas.

Comportamiento:
- Fusiona IPs estáticas y dominios resueltos en una whitelist efectiva (sin duplicados).
- Si un dominio no resuelve y existe `WHITELISTED_IPS`, continúa con fallback por IP.
- Si no hay fallback por IP, emite advertencia para evitar bloqueo accidental.

Contextos recomendados:
- Útil en entornos donde se dispone de grupos de confianza (administradores, servicios internos) que requieren acceso permanente.
- Mantener la lista pequeña y gestionada; para conjuntos grandes, considerar mecanismos externos y evaluar rendimiento.
- Asegurar que las entradas provengan de fuentes verificadas y auditar cambios periódicamente.
