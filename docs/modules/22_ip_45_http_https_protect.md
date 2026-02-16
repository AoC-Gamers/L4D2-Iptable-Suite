Módulo 22 — ip_45_http_https_protect.sh

Descripción:
Este módulo aplica controles anti-abuso para servicios HTTP/HTTPS en el backend `iptables`, con foco en limitar picos de conexiones TCP nuevas (NEW) hacia puertos web expuestos públicamente (por ejemplo, Traefik).

Variables relevantes:
- `ENABLE_HTTP_PROTECT`:
	- `false` (default): módulo deshabilitado.
	- `true`: activa limitación y bloqueo de bursts en HTTP/HTTPS.
- `HTTP_HTTPS_PORTS`: puertos web en cadena `INPUT` (ej: `80,443`).
- `HTTP_HTTPS_DOCKER`: puertos web en `DOCKER-USER` cuando existe flujo Docker (ej: `80,443`).
- `HTTP_HTTPS_RATE`: tasa máxima de conexiones `NEW` por origen/puerto (formato iptables, ej: `240/min`).
- `HTTP_HTTPS_BURST`: ráfaga permitida antes de bloqueo temporal.
- `LOG_PREFIX_HTTP_HTTPS_ABUSE`: prefijo para logs de excedentes.

Comportamiento:
- Permite conexiones `NEW` dentro del umbral (`hashlimit` por `srcip,dstport`).
- Registra excedentes con `LOG_PREFIX_HTTP_HTTPS_ABUSE`.
- Descarta excedentes (`DROP`) solo para estado `NEW` en puertos web definidos.
- Si existe `DOCKER-USER`, aplica también protección en cadena Docker para reverse proxies en contenedores.

Contextos recomendados:
- Servidores con paneles o sitios públicos detrás de Traefik/Nginx/Caddy.
- Entornos expuestos a picos de escaneo/fuerza bruta HTTP sin necesidad de WAF completo.
- Escenarios donde se desea mitigar abuso temprano a nivel L3/L4 antes de llegar a la app.

Notas operativas:
- Iniciar con valores conservadores (`240/min`, burst `480`) y ajustar según tráfico real.
- Monitorear logs (`HTTP_HTTPS_ABUSE`) para calibrar sin afectar usuarios legítimos.
- No reemplaza controles de capa 7 (WAF/rate-limit por ruta), los complementa.
