# Auditoria operativa y problemas conocidos

Esta guia resume hallazgos practicos al revisar la suite en un nodo real con `nftables`, GeoIP, logging y multiples servidores L4D2/SourceTV.

## Estado de validacion

Comandos usados para validar cambios de bajo riesgo:

```bash
make firewall-validate
make geoip-check
tests/smoke-modules.sh
python3 -m py_compile log-summary/app/fw_log_summary.py log-summary/app/iptable.loggin.py scripts/geoip/build_geo_country_sets.py scripts/geoip/check_geo_policy_ip.py
find . -path './.git' -prune -o -type f -name '*.sh' -print0 | xargs -0 -n1 bash -n
```

Resultado esperado:

- `firewall-validate` debe pasar con `bash -n`.
- `geoip-check` debe validar updater, modulo GeoIP y checker de IP/CIDR.
- `smoke-modules.sh` puede saltar dry-runs reales si no corre como root.
- `py_compile` debe pasar para los scripts Python de logging y GeoIP.

## Hallazgos corregidos

### Codigo legacy retirado

Se retiro el modulo `ip_l4d2_source_dispatch` (`l4d2_source_dispatch` / `l4d2_query_dispatch`) y su documento asociado.

Motivo:

- Era un modulo exclusivo de `iptables` sin equivalente `nftables`.
- Insertaba reglas al inicio de `INPUT`/`DOCKER-USER` con `iptables -I`, fuera del flujo modular normal.
- Duplicaba clasificacion que hoy esta cubierta por `l4d2_udp_base` y `l4d2_a2s_filters`.
- Podia ocultar regresiones reales en SourceTV y A2S al actuar como parche paralelo.

Tambien se limpio la documentacion de `ENABLE_L4D2_TCP_PROTECT`. El flujo actual usa inclusion del modulo `l4d2_tcp_protect` y puertos explicitos en `L4D2_GAMESERVER_TCP_PORTS`.

### SourceTV y paquetes `FFFFFFFF71`

Sintoma:

- El cliente intenta conectar a SourceTV con `Sending UDP connect to public IP ...:27121`.
- `tcpdump` muestra paquetes entrantes `UDP length 23`.
- El payload contiene `FFFFFFFF71 connect...`.
- No hay respuesta saliente desde el `tv_port`.

Causa:

- `l4d2_udp_base` hacia bypass temprano de `FFFFFFFF71` para GameServer y SourceTV.
- El clasificador `connect/reserve` de `l4d2_a2s_filters` solo aplica a `L4D2_GAMESERVER_UDP_PORTS`.
- En SourceTV, el paquete corto quedaba fuera del limitador base y luego caia en `packet_validation` por `meta length 0-28`.

Estado actual:

- `FFFFFFFF71` solo se deriva al subfiltro `connect/reserve` cuando el destino esta en `L4D2_GAMESERVER_UDP_PORTS`.
- En `L4D2_SOURCETV_UDP_PORTS`, los handshakes cortos quedan bajo el limitador `NEW` normal y pueden ser aceptados.

Comprobacion util:

```bash
sudo nft list chain inet firewall_main udp_new_limit
```

Debe verse una regla equivalente a:

```text
udp dport { 27001-27013, 27021-27026 } @th,64,40 0xffffffff71 return
```

### Prefijos `FW_EVT` truncados en nftables

Sintoma:

- Eventos con campos truncados al final, por ejemplo `severity=hig:` o `severity=l:`.
- Reportes con severidad incompleta o campos `host` ausentes.

Causa:

- El `log prefix` de nftables es limitado.
- Los nombres largos de `module=` y `chain=` dejaban `severity=` y `host=` al final del prefijo.

Estado actual:

- El backend `nftables` usa claves compactas para nuevos eventos:

```text
FW_EVT attack=... sev=... act=... be=nft mod=... ch=... host=...:
```

- Los parsers aceptan el formato viejo y el nuevo.
- `iptable.loggin.py` normaliza `be/mod/ch/act/sev` a `Backend/Module/Chain/Action/Severity`.
- `fw_log_summary.py` normaliza las mismas claves para sus rankings.

## Problemas operativos que pueden confundirse con bugs

### GeoIP puede bloquear sin generar `FW_EVT`

El modulo `nf_geo_country_filter` corre antes de los limitadores UDP y no loguea drops por pais. Si una IP no ve servidores y no hay eventos nuevos en `/var/log/firewall-suite.log`, no descartes GeoIP solo por ausencia de logs.

Comando recomendado:

```bash
make geoip-check-ip IP=179.6.17.240/28
```

Si quieres incluir dominios confiables resueltos desde `WHITELISTED_DOMAINS`:

```bash
make geoip-check-ip IP=203.0.113.10 RESOLVE_DOMAINS=1
```

### Logs no equivalen a todo el trafico

Los reportes solo ven paquetes que el firewall loguea. Tráfico aceptado por whitelist, GeoIP allow, limitadores bajo umbral o bypass operativo no aparece en los JSON.

Para problemas de conectividad usa tambien:

```bash
sudo tcpdump -nni any udp port 27121 -vv -XX
sudo nft list chain inet firewall_main input_l4d2_udp
sudo nft list chain inet firewall_main udp_new_limit
```

### `ENABLE_MALFORMED_FILTER=true` es agresivo

El filtro de malformados bloquea tamanos especificos historicamente asociados a abuso, pero puede solaparse con comportamiento legitimo si el trafico real cambia.

Recomendacion:

- Mantener `ENABLE_MALFORMED_FILTER=false` salvo que exista captura `pcap` o evidencia clara.
- Usar `ENABLE_PACKET_NORMALIZATION_LOGS=true` temporalmente para diagnostico.
- Volver a `false` si el volumen de logs crece demasiado.

### SourceTV debe permanecer separado de GameServer

`L4D2_SOURCETV_UDP_PORTS` no debe mezclarse con `L4D2_GAMESERVER_UDP_PORTS`.

Motivo:

- A2S puede aplicar a ambos rangos.
- Login `connect/reserve` solo aplica a GameServer.
- SourceTV emite handshakes cortos que necesitan pasar por el limitador base, no por el subfiltro de login.

### `L4D2_GAMESERVER_TCP_PORTS` no abre puertos

`L4D2_GAMESERVER_TCP_PORTS` define puertos TCP a proteger/rate-limitar, no una allowlist.

Si esta vacio:

- El modulo `l4d2_tcp_protect` se salta.
- Los puertos TCP no quedan permitidos por esa variable.
- El resultado final depende de otras reglas y de la politica `drop` del backend activo.

## Checklist rapido ante falso positivo de conectividad

1. Confirmar que el proceso escucha:

```bash
ss -lunp | grep -E ':27121|:27021'
```

2. Verificar que la IP pasa GeoIP:

```bash
make geoip-check-ip IP=IP_DEL_CLIENTE
```

3. Capturar entrada/salida:

```bash
sudo tcpdump -nni any udp port PUERTO -vv -XX
```

4. Revisar logs:

```bash
tail -n 100 /var/log/firewall-suite.log
```

5. Revisar reglas activas:

```bash
sudo nft list chain inet firewall_main input_l4d2_udp
sudo nft list chain inet firewall_main udp_new_limit
```

6. Si cambiaste `.env` o codigo de modulos, reaplicar:

```bash
sudo ./nftables.rules.sh
```
