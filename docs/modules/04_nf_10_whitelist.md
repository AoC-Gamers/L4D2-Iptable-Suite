Módulo 04 — nf_10_whitelist.sh

Descripción:
Este módulo implementa listas blancas de direcciones IP para el backend `nftables`. Su función principal es permitir de forma explícita el tráfico desde IPs o redes de confianza antes de aplicar reglas más restrictivas.

Contextos recomendados:
- Útil en entornos donde se dispone de grupos de confianza (administradores, servicios internos, peers) que requieren acceso sin restricciones.
- Mantener la lista pequeña y gestionada: para grandes conjuntos de IPs, considerar mecanismos externos (listas dinámicas, fuentes de confianza) y evaluar rendimiento.
- Evitar introducir entradas dinámicas sin control: las entradas deben provenir de una fuente verificada o un proceso de revisión.
