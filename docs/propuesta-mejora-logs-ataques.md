# Propuesta: Mejora de Registros de Ataques (nftables + L4D2)

## 1. Contexto
Estado actual del proyecto:
- Backend activo en producción: `nftables`.
- Reglas modulares en `modules/nf/*`.
- Detección de ataques por prefijos (`LOG_PREFIX_*`) y parsing en `iptable.loggin.py`.
- Generación de reportes JSON por IP/puerto/día/semana/mes/tipo.

Fortaleza actual:
- Muy buena segmentación por tipo de ataque (`A2S_*`, `L4D2_*`, `UDP_*`, `ICMP`, etc.).

Límite actual:
- El parser se basa principalmente en prefijos y campos kernel estándar (`SRC=`, `DPT=`, `LEN=`), con poco contexto operacional del evento (backend, módulo, chain, acción, severidad, host, entorno).

## 2. Objetivo de la mejora
Mejorar trazabilidad, correlación y observabilidad de ataques sin romper compatibilidad con:
- módulos actuales de firewall,
- pipeline rsyslog existente,
- y reportes JSON ya usados operativamente.

## 3. Principios de diseño
1. Compatibilidad hacia atrás: mantener `LOG_PREFIX_*` actuales.
2. Enriquecimiento incremental: agregar contexto por etapas.
3. Bajo riesgo operativo: no alterar la lógica de bloqueo/drop, solo visibilidad.
4. Preparado para métricas: diseño orientado a Prometheus/Grafana.

## 4. Diseño propuesto (resumen)
## Fase A: Estandarizar el formato de prefijos (sin romper)
Definir un formato de prefijo extendido para nuevas reglas de log:

`FW_EVT attack=<tipo> backend=nft module=<modulo> chain=<chain> action=drop severity=<nivel>:`

Ejemplo:

`FW_EVT attack=A2S_INFO_FLOOD backend=nft module=nf_70_l4d2_a2s_filters chain=input action=drop severity=medium:`

Notas:
- Mantener también los prefijos legados (`A2S_INFO_FLOOD:`, etc.) durante transición.
- Longitud del prefijo controlada para no truncar contexto en `dmesg/journal`.

## Fase B: Canalizar y normalizar logs
1. Mantener rsyslog para archivo legado (`/var/log/firewall-suite.log`).
2. Agregar salida estructurada JSON (opcional y recomendada):
   - `/var/log/firewall-suite.json.log`
3. Incluir metadatos del host:
   - `host`, `facility`, `programname`, `timestamp`.

Resultado:
- Soporte dual: texto clásico + JSON estructurado.

## Fase C: Evolucionar `iptable.loggin.py`
Agregar parseo híbrido:
1. Primero intenta parseo de formato extendido `FW_EVT`.
2. Si no existe, cae a parseo legado por `LOG_PREFIX_*`.
3. Nuevos campos en salida JSON:
   - `Backend`, `Module`, `Chain`, `Action`, `Severity`, `Env`, `Host`.

Beneficio:
- No se rompe análisis histórico, pero se habilita analítica más rica para eventos nuevos.

## Fase D: Métricas y alertas (Prometheus)
Exponer métricas de ataques desde el resumen (job programado cada 1m/5m):
- `firewall_attack_events_total{attack,host,port_type,severity}`
- `firewall_top_attacker_events_total{host,ip}`
- `firewall_attack_unique_ips{host,attack}`
- `firewall_dropped_packets_total{host,chain,module}`

Implementación sugerida:
- Exporter tipo textfile para `node_exporter` (`/var/lib/node_exporter/textfile_collector/*.prom`)
  o exporter HTTP liviano en Python.

## 5. Cambios concretos por componente
### 5.1 Módulos nft (`modules/nf/*.sh`)
Objetivo:
- Enriquecer `log prefix` en reglas seleccionadas de alto valor (A2S, login flood, UDP over-limit, TCP RCON).

Estrategia:
1. Usar formato estructurado único `FW_EVT ...`.
2. Mantener `FIREWALL_HOST_ALIAS` como metadata opcional.

Impacto:
- Cero impacto funcional en reglas `drop/accept`; solo cambia texto de `log`.

### 5.2 Configuración `.env` / `example.env`
Agregar variables nuevas:
- `FIREWALL_HOST_ALIAS=` (opcional)

Mantener:
- Todos los `LOG_PREFIX_*` actuales.

### 5.3 Script `iptable.loggin.py`
Cambios recomendados:
1. Parser para campos key-value de `FW_EVT`.
2. Enriquecimiento de salida con campos de contexto (`Backend`, `Module`, `Chain`, `Action`, `Severity`, `Env`, `Host`).
3. Reporte nuevo `summary_by_signature.json` (ataque + módulo + chain + acción).

### 5.4 Rsyslog
Mantener reglas actuales `contains`.
Agregar pipeline opcional para JSON template:
- idealmente en archivo separado, por ejemplo:
  - `/etc/rsyslog.d/firewall-suite-json.conf`

## 6. Política de retención y rotación
Recomendado para `valpo2`:
1. Rotación diaria (`logrotate`).
2. Retención 30 días texto + 14 días JSON (si alto volumen).
3. Compresión para históricos.
4. Límite de tamaño por archivo para proteger disco.

## 7. Reglas de calidad de logs
1. Cada evento de drop crítico debe tener:
   - tipo de ataque,
   - chain,
   - acción,
   - severidad.
2. Evitar cardinalidad explosiva en labels Prometheus:
   - no usar IP como label en métricas globales de alta frecuencia.
3. Incluir IP detallada solo en reportes JSON/offline.

## 8. Alertas recomendadas
1. Pico de eventos por ataque (baseline + desviación).
2. Top IP atacante supera umbral sostenido.
3. Eventos `L4D2_CONNECT_FLOOD` o `L4D2_RESERVE_FLOOD` anómalos.
4. Aumento abrupto de `UDP_EST_LIMIT` (posible saturación real de juego).

## 9. Plan de migración seguro
1. Implementar parser `FW_EVT` en branch.
2. Desplegar en un servidor de prueba o ventana controlada.
3. Comparar 48-72h:
   - conteos por tipo,
   - falsos positivos,
   - volumen de logs.
4. Si estable, activar en `valpo2`.

## 10. Entregables propuestos
1. Cambios en `example.env` y documentación.
2. Parser híbrido en `iptable.loggin.py`.
3. Modo `extended` en módulos `nf_*` prioritarios.
4. Documento de operación (consultas, rotación, alertas).
5. Dashboard Grafana de ataques por tipo/puerto/host.

## 11. Roadmap sugerido
Semana 1:
- Parser híbrido + documentación + pruebas con logs de ejemplo.

Semana 2:
- Modo `extended` en módulos `nf_50`, `nf_60`, `nf_70`, `nf_42`.

Semana 3:
- Exportación de métricas a Prometheus + dashboard inicial.

Semana 4:
- Ajuste fino de umbrales y alertas (sin ruido operativo).

---

## Decisiones pendientes
1. ¿Mantener solo archivo texto o habilitar también JSON estructurado?
2. ¿Nivel de detalle en prefijo extendido (mínimo vs completo)?
3. ¿Exporter Prometheus via textfile o HTTP custom?
4. ¿Retención exacta de logs en `valpo2` según espacio de disco?
