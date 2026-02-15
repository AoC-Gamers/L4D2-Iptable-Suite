Módulo 08 — nf_50_udp_base.sh

Descripción:
Este módulo define la base de reglas UDP para `nftables`: normaliza puertos de servicios, crea excepciones para servicios UDP (juegos, DNS, servicios multimedia) y aplica controles básicos de conexión y límites por origen.

Contextos recomendados:
- Usar en servidores que ofrezcan servicios UDP expuestos públicamente (servidores de juego, DNS autoritativos, streaming).
- Verificar compatibilidad con NAT y políticas de reenvío cuando el host actúe como gateway.
- Mantener límites y validaciones en las especificaciones de puertos para evitar exposiciones accidentales; probar en entorno de staging antes de producción.
