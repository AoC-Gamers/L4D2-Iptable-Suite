Módulo 20 — ip_60_packet_validation.sh

Descripción:
Este módulo aplica validaciones de paquetes para el backend `iptables`: filtra paquetes malformados, detecta patrones de fragmentación problemática y aplica reglas de mitigación temprana para tráfico sospechoso, reduciendo carga en capas superiores.

Contextos recomendados:
- Útil en bordes de red y hosts expuestos donde el filtrado temprano mejora seguridad y rendimiento.
- Probar cuidadosamente en topologías con túneles, NAT o dispositivos que fragmenten paquetes, ya que validaciones estrictas pueden bloquear tráfico legítimo.
- Empezar en modo registro para ajustar reglas y minimizar falsos positivos antes de habilitar bloqueos permanentes.
