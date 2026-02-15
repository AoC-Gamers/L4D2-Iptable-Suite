Módulo 09 — nf_60_packet_validation.sh

Descripción:
Este módulo aplica validaciones de paquetes para el backend `nftables`: detecta y descarta paquetes malformados, verifica coherencia mínima (por ejemplo fragmentación problemática, checksums inválidos cuando es posible) y añade reglas de prevención temprana para tráfico sospechoso.

Contextos recomendados:
- Útil en bordes de red y hosts expuestos donde el filtrado temprano reduce carga en capas superiores.
- Probar cuidadosamente en entornos con túneles, NAT y dispositivos que fragmenten paquetes; algunas validaciones pueden bloquear tráfico legítimo en topologías complejas.
- Mantener reglas conservadoras por defecto y habilitar modos de registro para ajustar falsos positivos antes de aplicar bloqueos permanentes.
