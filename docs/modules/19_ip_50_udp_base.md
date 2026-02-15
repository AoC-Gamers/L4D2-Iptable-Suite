Módulo 19 — ip_50_udp_base.sh

Descripción:
Este módulo define la base de reglas UDP para `iptables`: normaliza puertos de servicios UDP, crea excepciones para servicios como servidores de juego, DNS o streaming, y aplica controles básicos por origen y límites de tasa.

Contextos recomendados:
- Usar en servidores que ofrecen servicios UDP expuestos públicamente; comprobar compatibilidad con NAT y reenvío.
- Mantener listas de puertos claras y validar entradas para evitar exposiciones accidentales.
- Probar en staging antes de producción y ajustar límites para evitar falsos positivos que afecten tráfico legítimo.
