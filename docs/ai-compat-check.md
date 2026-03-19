# Instrucciones para IA en servidor: verificación de compatibilidad (Docker + iptables/nftables)

Objetivo: validar si el host puede ejecutar este proyecto de forma segura para GameServers dockerizados, y recomendar backend (`iptables` o `nftables`) con evidencia.

## 1) Reglas de ejecución para la IA

- Ejecutar todos los comandos con privilegios root (o `sudo`).
- No modificar reglas al inicio; primero auditar en modo lectura.
- Si encuentra riesgo crítico, detenerse y reportar.
- Reportar en formato estructurado (sección 8).

## 2) Contexto esperado del proyecto

- Backend `iptables` usa cadena `DOCKER-USER` para tráfico Docker.
- Backend `nftables` NO debe hacer `flush ruleset` global; solo sus tablas propias (`inet firewall_main`, `ip vpn_s2s_nat` cuando aplique).
- Archivo de configuración base: `.env`.

## 3) Chequeo del entorno (solo lectura)

Ejecutar y guardar salida:

```bash
set -e
uname -a
cat /etc/os-release || true
command -v docker && docker --version
command -v nft && nft --version
command -v iptables && iptables --version
iptables -V || true
update-alternatives --display iptables 2>/dev/null || true
```

Criterios:
- PASS si existen `docker`, `iptables` y/o `nft` según backend a evaluar.
- WARN si `iptables` está en modo legacy en hosts modernos con Docker+nft mezclado.

## 4) Chequeo Docker + cadenas firewall

### 4.1 iptables (lectura)

```bash
iptables -S
iptables -S FORWARD
iptables -S DOCKER-USER 2>/dev/null || true
iptables -t nat -S
```

Criterios para `iptables`:
- PASS si existe `DOCKER-USER` y `FORWARD` referencia flujo Docker.
- FAIL si `DOCKER-USER` no existe y Docker está activo.

### 4.2 nftables (lectura)

```bash
nft list ruleset
nft list table inet firewall_main 2>/dev/null || true
nft list table ip vpn_s2s_nat 2>/dev/null || true
```

Criterios para `nftables`:
- PASS si `ruleset` existe y no hay conflictos obvios entre tablas Docker y `inet firewall_main`.
- WARN si hay reglas Docker pero no hooks esperados en `forward` para tráfico contenedor.

## 5) Validación estática del repo (seguridad de implementación)

Desde raíz del proyecto:

```bash
grep -RIn "flush ruleset" modules/nf nftables.rules.sh || true
grep -RIn "DOCKER-USER" modules/ip || true
grep -RIn "\bDOCKER\b" modules/ip || true
```

Criterios:
- FAIL si aparece `nft flush ruleset` en flujo activo de backend `nf`.
- PASS si módulos `ip` apuntan a `DOCKER-USER` para ruta contenedores.
- WARN si hay referencias residuales a `DOCKER` en módulos `ip` que no sean texto histórico controlado.

## 6) Prueba funcional mínima (dry-run)

> Ejecutar en ventana de mantenimiento (puede tocar reglas según backend/script).

```bash
./tests/smoke-modules.sh
```

Si no es root o faltan binarios, reportar como `SKIPPED` con razón.

Criterios:
- PASS si smoke test completa y backend objetivo no falla.
- FAIL si falla contrato de módulos o dry-run de backend objetivo.

## 7) Matriz de decisión

- Recomendar `iptables` cuando:
  - Host usa Docker intensivamente.
  - `DOCKER-USER` está presente y estable.
  - Se requiere máxima predictibilidad con flujo Docker.

- Recomendar `nftables` cuando:
  - El host opera nativamente en nft.
  - No existe `flush ruleset` global en la implementación.
  - Pruebas muestran hooks correctos para tráfico de contenedores.

- Bloquear despliegue (`NO-GO`) cuando:
  - Falta `DOCKER-USER` en escenario Docker+iptables.
  - Se detecta limpieza global de ruleset en backend `nf`.
  - Fallan smoke tests críticos.

## 8) Formato de salida obligatorio (JSON)

```json
{
  "host": {
    "os": "...",
    "docker": "ok|missing",
    "iptables": "ok|missing",
    "nft": "ok|missing"
  },
  "checks": [
    {"id": "env-tools", "status": "PASS|WARN|FAIL", "evidence": "..."},
    {"id": "iptables-docker-user", "status": "PASS|WARN|FAIL", "evidence": "..."},
    {"id": "nft-no-global-flush", "status": "PASS|WARN|FAIL", "evidence": "..."},
    {"id": "smoke-test", "status": "PASS|WARN|FAIL|SKIPPED", "evidence": "..."}
  ],
  "recommended_backend": "iptables|nftables|none",
  "go_live": "GO|NO-GO",
  "actions": [
    "...",
    "..."
  ]
}
```

## 9) Prompt listo para pegar en la IA del servidor

Usa este prompt literal:

```text
Eres un auditor técnico de compatibilidad de firewall para L4D2-Iptable-Suite en un host Linux con Docker.

Objetivo:
1) Verificar compatibilidad real para GameServers dockerizados.
2) Determinar si conviene iptables o nftables.
3) Entregar veredicto GO/NO-GO con evidencia.

Instrucciones estrictas:
- Ejecuta solo comandos de lectura al inicio.
- Si detectas riesgo crítico, detente y marca NO-GO.
- Evalúa específicamente:
  - existencia y salud de DOCKER-USER en iptables,
  - ausencia de flush ruleset global en backend nft,
  - consistencia de hooks para tráfico Docker.
- Si puedes, ejecuta tests/smoke-modules.sh y clasifica resultado.
- Devuelve SOLO JSON con este esquema:
  host, checks[], recommended_backend, go_live, actions[].

Criterios:
- Docker en producción prioriza iptables+DOCKER-USER salvo evidencia sólida de nft estable.
- Si falta DOCKER-USER en escenario Docker+iptables => FAIL.
- Si hay flush ruleset global en nft activo => FAIL.
```
