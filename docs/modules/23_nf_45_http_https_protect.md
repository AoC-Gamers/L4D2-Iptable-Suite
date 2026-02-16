Módulo 23 — nf_45_http_https_protect.sh

Descripción:
Este módulo aplica controles anti-abuso para servicios HTTP/HTTPS en el backend `nftables`, limitando conexiones TCP nuevas hacia puertos web expuestos.

Variables relevantes:
- `ENABLE_HTTP_PROTECT`:
	- `false` (default): módulo deshabilitado.
	- `true`: activa limitación y bloqueo de bursts en HTTP/HTTPS.
- `HTTP_HTTPS_PORTS`: puertos web a proteger (ej: `80,443`).
- `HTTP_HTTPS_RATE`: tasa máxima de conexiones `NEW` (formato nftables: `180/minute`, `60/second`, etc.).
- `HTTP_HTTPS_BURST`: ráfaga permitida antes de bloqueo temporal.
- `LOG_PREFIX_HTTP_HTTPS_ABUSE`: prefijo para logs de excedentes.

Comportamiento:
- Permite conexiones `NEW` dentro de la tasa configurada.
- Registra excedentes con `LOG_PREFIX_HTTP_HTTPS_ABUSE`.
- Descarta excedentes (`DROP`) para estado `NEW` en puertos web definidos.
- Se aplica sobre cadenas objetivo según `TYPECHAIN` (`input`, `forward` o ambas).

Contextos recomendados:
- Hosts con servicios web públicos o reverse proxy expuesto.
- Escenarios de escaneo masivo o intentos de saturación por bursts de TCP.
- Despliegues que priorizan mitigación simple y rápida a nivel firewall.

Notas operativas:
- Verificar formato de `HTTP_HTTPS_RATE` compatible con nftables (`second|minute|hour|day`).
- Ajustar tasa/burst con observabilidad de logs para minimizar falsos positivos.
- Complementar con controles L7 en proxy/aplicación cuando sea necesario.
