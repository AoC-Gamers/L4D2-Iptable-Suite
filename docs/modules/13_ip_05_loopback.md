Módulo 13 — ip_05_loopback.sh

Descripción:
Este módulo configura reglas para la interfaz `loopback` en el backend `iptables`. Asegura que el tráfico local (127.0.0.1 y equivalentes) esté permitido y que las cadenas relevantes traten este tráfico con prioridad, evitando que validaciones o restricciones globales lo bloqueen.

Contextos recomendados:
- Siempre habilitar en hosts que ejecuten servicios locales que dependan de comunicación interna entre procesos.
- Mantener el módulo mínimo y explícito: permitir todo en loopback y evitar listas o filtros complejos aquí.
- Probar en entornos con contenedores o redes virtuales para verificar que las direcciones de loopback internas no se vean afectadas por reglas de host.
