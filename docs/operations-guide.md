# Guía operativa rápida

Esta guía resume el flujo recomendado para operar `L4D2-Iptable-Suite` en servidores reales, especialmente cuando conviven Docker, game servers L4D2, SourceTV, OpenVPN, GeoIP y logging.

La idea es reducir falsos diagnósticos y evitar cambios destructivos en producción. Porque romper el firewall por “probar rápido” sigue siendo una tradición humana bastante popular, pero no por eso recomendable.

---

## 1. Elección de backend

La suite mantiene dos entrypoints:

- `iptables.rules.sh`: backend legacy basado en `iptables`.
- `nftables.rules.sh`: backend moderno basado en `nftables`.

Ambos usan el mismo `.env` y el mismo modelo modular.

### Usa `iptables` cuando

- El host usa Docker intensivamente.
- Quieres enganchar reglas de contenedores en `DOCKER-USER`.
- Necesitas máxima predictibilidad con el flujo tradicional de Docker.
- El host ya opera estable con `iptables`/`iptables-nft` y no hay una razón fuerte para migrar.

### Usa `nftables` cuando

- El host ya opera nativamente con `nft`.
- Validaste que no existe `flush ruleset` global en el flujo activo.
- Validaste que las cadenas de Docker y las tablas de la suite no se pisan.
- Necesitas mantener reglas modernas en `inet firewall_main`.

### No desplegar todavía cuando

- Docker está activo y falta `DOCKER-USER` en un escenario `iptables`.
- El backend `nftables` intenta limpiar el ruleset global.
- Fallan los smoke tests críticos.
- No sabes si el tráfico real entra por host, Docker o ambos. Adivinar rutas de firewall es una forma elegante de perder conectividad.

---

## 2. Variables base que debes revisar antes de aplicar

Antes de ejecutar reglas reales, revisa al menos estas variables del `.env`:

```bash
TYPECHAIN=0
MODULES_ONLY=""
L4D2_GAMESERVER_UDP_PORTS="27015"
L4D2_SOURCETV_UDP_PORTS="27020"
L4D2_GAMESERVER_TCP_PORTS=""
WHITELISTED_IPS=""
WHITELISTED_DOMAINS=""
GEO_POLICY_MODE=off
ENABLE_MALFORMED_FILTER=false
ENABLE_PACKET_NORMALIZATION_LOGS=false
```

### `TYPECHAIN`

- `0`: protege tráfico nativo por `INPUT`.
- `1`: protege tráfico de contenedores por `DOCKER-USER`.
- `2`: protege ambos caminos.

### `MODULES_ONLY`

Permite aplicar un subconjunto de módulos. Es útil para pruebas, pero peligroso si lo dejas limitado sin querer.

Ejemplo para pruebas L4D2:

```bash
MODULES_ONLY="chain_setup,loopback,whitelist,geo_country_filter,allowlist_ports,l4d2_udp_base,l4d2_packet_validation,l4d2_a2s_filters,finalize"
```

---

## 3. Flujo seguro de aplicación

### 3.1 Validación sin aplicar

```bash
sudo ./iptables.rules.sh --dry-run --verbose
sudo ./nftables.rules.sh --dry-run --verbose
```

También puedes ejecutar:

```bash
./tests/smoke-modules.sh
```

Resultado esperado:

- No hay errores de contrato `metadata/validate/apply`.
- No faltan variables requeridas.
- El resumen final muestra módulos ejecutados u omitidos de forma clara.

### 3.2 Aplicación real

Elige un solo backend para producción, salvo que estés haciendo pruebas controladas.

```bash
sudo ./iptables.rules.sh
```

O:

```bash
sudo ./nftables.rules.sh
```

### 3.3 Persistencia

Para `iptables`:

```bash
sudo ./ipp.sh
```

Usa la opción de guardar reglas activas.

Para `nftables`, `ipp.sh` puede guardar las tablas administradas por la suite en `/etc/nftables.conf`, pero revisa siempre el ruleset exportado antes de depender de él en producción.

```bash
sudo nft list ruleset
sudo cat /etc/nftables.conf
```

---

## 4. Docker y `DOCKER-USER`

En Docker, el punto seguro para reglas de usuario es `DOCKER-USER`.

Validación rápida:

```bash
sudo iptables -S DOCKER-USER 2>/dev/null || true
sudo iptables -S FORWARD
sudo iptables -t nat -S
```

Si `TYPECHAIN=1` o `TYPECHAIN=2`, pero `DOCKER-USER` no existe, detén el despliegue y revisa Docker antes de culpar al módulo L4D2. El firewall no puede proteger una cadena que no existe, por muy optimista que esté el `.env`.

Con `TYPECHAIN=0` y Docker instalado, revisa:

```bash
DOCKER_INPUT_COMPAT=true
DOCKER_CHAIN_AUTORECOVER=true
```

Esto ayuda a preservar o recuperar cadenas Docker cuando solo quieres proteger tráfico nativo por `INPUT`.

---

## 5. SourceTV no debe mezclarse con GameServer

Mantén separados:

```bash
L4D2_GAMESERVER_UDP_PORTS="27001:27008"
L4D2_SOURCETV_UDP_PORTS="27101:27108"
```

Motivo:

- A2S puede aplicar a ambos rangos.
- `connect/reserve` solo debe tratarse como login de GameServer.
- SourceTV puede usar handshakes cortos que deben pasar por el limitador base, no por el subfiltro de login.

Si un cliente no puede conectar a SourceTV, valida primero:

```bash
ss -lunp | grep -E ':27101|:27108'
sudo tcpdump -nni any udp port 27101 -vv -XX
sudo nft list chain inet firewall_main input_l4d2_udp 2>/dev/null || true
sudo nft list chain inet firewall_main udp_new_limit 2>/dev/null || true
```

---

## 6. GeoIP puede bloquear sin generar eventos `FW_EVT`

El módulo GeoIP puede bloquear antes de que existan logs de abuso. Por eso, ausencia de eventos no significa ausencia de bloqueo.

Diagnóstico recomendado:

```bash
make geoip-check-ip IP=IP_DEL_CLIENTE
```

Con resolución de dominios confiables:

```bash
make geoip-check-ip IP=IP_DEL_CLIENTE RESOLVE_DOMAINS=1
```

Si estás investigando conectividad, revisa GeoIP antes de ajustar límites UDP. Así evitas subir límites por un bloqueo que ni siquiera venía del rate limiter, una pequeña tragedia administrativa.

---

## 7. Logs: qué muestran y qué no muestran

Los reportes solo ven paquetes que el firewall decidió loguear.

No aparecerán necesariamente en los reportes:

- Paquetes aceptados por whitelist.
- Tráfico aceptado bajo umbral de rate limit.
- Drops de GeoIP si el módulo no loguea ese caso.
- Tráfico bloqueado por reglas externas a la suite.

Revisión rápida:

```bash
tail -n 100 /var/log/firewall-suite.log
python3 log-summary/app/iptable.loggin.py --env-file .env
```

Para diagnóstico temporal puedes activar:

```bash
ENABLE_PACKET_NORMALIZATION_LOGS=true
```

No lo dejes activo sin razón en producción. Los logs también pueden convertirse en otro incendio, porque aparentemente incluso registrar problemas puede crear problemas.

---

## 8. `ENABLE_MALFORMED_FILTER` es agresivo

Valor recomendado por defecto:

```bash
ENABLE_MALFORMED_FILTER=false
```

Actívalo solo si tienes evidencia real, idealmente captura `pcap` o patrón confirmado.

```bash
sudo tcpdump -nni any udp port 27015 -vv -XX -w l4d2-debug.pcap
```

Si lo activas y aparecen falsos positivos:

1. Vuelve a `false`.
2. Reaplica reglas.
3. Captura tráfico real.
4. Ajusta solo con evidencia.

---

## 9. Protección TCP L4D2 no abre puertos

Esta variable:

```bash
L4D2_GAMESERVER_TCP_PORTS="27015"
```

define puertos TCP a proteger o rate-limitar. No funciona como allowlist general.

Si quieres permitir servicios adicionales, usa las variables de allowlist correspondientes:

```bash
TCP_ALLOW_PORTS="8080,9090"
UDP_ALLOW_PORTS=""
```

Para Docker también revisa:

```bash
TCP_DOCKER="80,443"
SSH_DOCKER="2222"
```

---

## 10. Checklist ante problema de conectividad

Ejecuta en este orden:

```bash
# 1. Confirmar que el proceso escucha
ss -lunp | grep -E ':27015|:27101'

# 2. Confirmar ruta del tráfico
sudo tcpdump -nni any udp port 27015 -vv -XX

# 3. Revisar GeoIP
make geoip-check-ip IP=IP_DEL_CLIENTE

# 4. Revisar logs
sudo tail -n 100 /var/log/firewall-suite.log

# 5. Revisar reglas activas iptables
sudo iptables -S
sudo iptables -S DOCKER-USER 2>/dev/null || true

# 6. Revisar reglas activas nftables
sudo nft list ruleset

# 7. Reaplicar después de cambios de .env
sudo ./iptables.rules.sh
# o
sudo ./nftables.rules.sh
```

---

## 11. Checklist antes de mergear cambios al firewall

```bash
make firewall-validate
make geoip-check
./tests/smoke-modules.sh
python3 -m py_compile \
  log-summary/app/fw_log_summary.py \
  log-summary/app/iptable.loggin.py \
  scripts/geoip/build_geo_country_sets.py \
  scripts/geoip/check_geo_policy_ip.py
find . -path './.git' -prune -o -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n
```

Resultado esperado:

- Validación bash sin errores.
- Smoke test sin fallos de contrato modular.
- Python compila sin errores.
- GeoIP valida updater, módulo y checker.

---

## 12. Resumen operativo corto

- Docker productivo: prioriza `iptables` + `DOCKER-USER`, salvo evidencia clara para `nftables`.
- `nftables`: nunca debe hacer `flush ruleset` global.
- SourceTV y GameServer deben ir separados.
- GeoIP puede bloquear sin aparecer en `FW_EVT`.
- Los logs no representan todo el tráfico.
- `ENABLE_MALFORMED_FILTER=false` por defecto.
- `L4D2_GAMESERVER_TCP_PORTS` protege TCP, no abre puertos.
- Siempre usa `--dry-run` y smoke tests antes de aplicar en producción.
