Módulo 18 — ip_40_tcp_ssh.sh

Descripción:
Este módulo configura reglas TCP específicas para SSH en `iptables`. Suele incluir excepciones para el puerto SSH, controles de tasa (rate limiting), y listas de confianza para reducir la exposición a ataques de fuerza bruta, manteniendo al mismo tiempo acceso administrativo seguro.

Contextos recomendados:
- Usar en servidores con acceso SSH público o administrativo; preferir restricciones por origen cuando sea posible.
- Combinar con mecanismos de autenticación robustos (llaves, 2FA) y sistemas de gestión de accesos para minimizar riesgos.
- Probar en entornos controlados antes de desplegar en producción para evitar cortes accidentales del servicio SSH.
