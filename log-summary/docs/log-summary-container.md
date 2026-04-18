# Contenedor de Resumen de Logs (Resúmenes Rápidos de Ataques)

Este contenedor opcional lee logs del firewall y genera resúmenes rápidos en JSON y TXT.

## Ubicación

- `log-summary/`

## Archivos

- `docker-compose.yml`
- `Dockerfile`
- `app/fw_log_summary.py`
- `.env.example`

## Configuración

```bash
cd log-summary
cp .env.example .env
```

Edita los valores de `.env` según tu entorno.

## Ejecución (modo continuo)

```bash
docker compose up -d --build
```

Archivos generados:

- `docker/log-summary/output/summary.latest.json`
- `docker/log-summary/output/summary.latest.txt`
 
Nota: en la estructura actual del repositorio estos archivos quedan en:

- `log-summary/output/summary.latest.json`
- `log-summary/output/summary.latest.txt`
- `log-summary/output/summary.status.json`

## Ejecutar una sola vez (snapshot único)

```bash
docker compose run --rm -e SUMMARY_RUN_MODE=once log-summary
```

## Variables principales de entorno

- `SUMMARY_LOG_PATH`: ruta del log en el host (montado en solo lectura).
- `SUMMARY_LOG_MOUNT_DIR`: directorio del host que se monta en solo lectura (recomendado: `/var/log`).
- `SUMMARY_OUTPUT_DIR`: carpeta de salida dentro del contenedor (montada a `./output`).
- `SUMMARY_TOP_N`: cantidad máxima de elementos en rankings.
- `SUMMARY_WINDOW_MINUTES`: 0 = archivo completo, >0 = ventana de tiempo deslizante.
- `SUMMARY_POLL_SECONDS`: intervalo de actualización en modo `loop`.
- `SUMMARY_RUN_MODE`: `loop` o `once`.
- `SUMMARY_STATUS_PATH`: archivo de estado usado por healthcheck.
- `SUMMARY_HEALTHCHECK_MAX_EMPTY_CYCLES`: máximo de ciclos vacíos consecutivos antes de marcar `unhealthy`.

## Notas

- El parser está basado en líneas estructuradas `FW_EVT`.
- Acepta tanto campos largos (`backend`, `module`, `chain`, `action`, `severity`) como aliases compactos de nftables (`be`, `mod`, `ch`, `act`, `sev`).
- El contenedor usa nombres genéricos y no depende de nombres específicos de juegos.
- El `healthcheck` de Docker falla cuando `consecutive_empty_cycles` supera el umbral configurado.
- Actualmente este componente **no** expone endpoint HTTP/API.
- La consulta se realiza mediante archivos de salida (`summary.latest.json`, `summary.latest.txt`, `summary.status.json`) y logs del contenedor.
