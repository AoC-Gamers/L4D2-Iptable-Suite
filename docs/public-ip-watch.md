# Vigilancia de IP pública para Valpo2

## Objetivo

`l4d2-public-ip-watch` vigila la IPv4 pública del servidor Valpo2, ubicado
detrás de una conexión Movistar Hogar con dirección dinámica. El router sigue
siendo responsable de actualizar No-IP; este componente solamente detecta y
confirma el cambio desde el host.

Cuando la IP WAN cambia y los nameservers autoritativos de No-IP ya publican
la misma dirección, el watcher valida y reaplica el backend nftables. Esto
limpia estado de red local y deja disponible un hook opcional para renovar el
heartbeat de los gameservers ante el master server de Steam.

## Flujo DNS actual

```text
Router Movistar
  -> actualiza valparaiso.dns.aoc-gamers.com en No-IP
  -> Cloudflare publica CNAME DNS-only hacia el hostname de No-IP
  -> los usuarios consumen los nombres finales de aoc-gamers.com
```

Cloudflare no necesita una actualización de dirección mientras los registros
finales continúen siendo CNAME `Solo DNS`: al resolverlos se sigue la dirección
vigente publicada por No-IP.

## Decisión de recarga

Cada ejecución realiza estas comprobaciones:

1. Obtiene la IPv4 WAN desde el servicio oficial de detección de No-IP.
2. Valida que sea una IPv4 pública enrutable.
3. Consulta directamente `ns1.no-ip.com` hasta `ns4.no-ip.com`, evitando la
   caché de resolvers recursivos.
4. Exige que al menos `DDNS_MIN_MATCHES` servidores autoritativos publiquen la
   misma IP detectada.
5. Compara la dirección confirmada con el estado persistente.
6. Si cambió, ejecuta primero `nftables.rules.sh --dry-run` y luego la carga
   real.
7. Ejecuta `POST_CHANGE_HOOK`, si está configurado.
8. Guarda la IP nueva únicamente cuando todas las acciones terminan bien.

Los fallos transitorios de HTTP o DNS no alteran el firewall ni el estado. Un
lock evita dos ejecuciones simultáneas.

La primera ejecución normal solamente inicializa el estado y no recarga las
reglas.

## Frecuencia y No-IP

No-IP documenta un servicio de detección para equipos detrás de NAT y solicita
que los clientes no consulten con una frecuencia inferior a cinco minutos. El
timer utiliza diez minutos.

Durante la revisión no se encontró un webhook oficial de cambio de IP en la
documentación pública de No-IP. La API documentada permite actualizar DDNS y
consultar registros DNS, por lo que el sondeo periódico confirmado contra los
servidores autoritativos es el mecanismo utilizado.

Referencias:

- [Detección de IP de No-IP](https://www.noip.com/integrate/ip-detection)
- [Endpoint de actualización DDNS](https://developer.noip.com/reference/nic_update)
- [Consulta de registros DNS](https://developer.noip.com/reference/v1-dns-records-get-rrset)
- [Administración de IP dinámica en Cloudflare](https://developers.cloudflare.com/dns/manage-dns-records/how-to/managing-dynamic-ip-addresses/)

## Hallazgo relacionado en nftables

El backend nftables creaba meters dinámicos sin timeout de elementos. Cada
combinación de IP origen y puerto quedaba retenida hasta recrear la tabla. En
un host público con tráfico UDP de orígenes aleatorios, el set
`udp_new_src_under` podía alcanzar su capacidad de 65.535 elementos.

Reaplicar `nftables.rules.sh` recreaba la tabla y vaciaba esos meters, lo que
explica por qué la visibilidad de los gameservers podía recuperarse justo
después de ejecutar el script, aunque las reglas no dependieran de la IP WAN.

El backend aplica ahora estos timeouts:

```dotenv
NFT_UDP_NEW_METER_TIMEOUT=5s
NFT_UDP_EST_METER_TIMEOUT=5s
NFT_A2S_METER_TIMEOUT=5s
NFT_LOGIN_METER_TIMEOUT=1s
```

Las entradas se renuevan mientras continúa el tráfico y se liberan después de
quedar inactivas. No se recomienda desactivar la expiración.

Referencia: [Meters de nftables](https://wiki.nftables.org/wiki-nftables/index.php/Meters).

## Archivos

- `scripts/network/public-ip-watch.sh`: detector y ejecutor de acciones.
- `config/l4d2-public-ip-watch.env.example`: configuración de producción.
- `systemd/l4d2-public-ip-watch.service`: servicio oneshot endurecido.
- `systemd/l4d2-public-ip-watch.timer`: programación cada diez minutos.
- `tests/public-ip-watch.sh`: pruebas aisladas con WAN, DNS y firewall
  simulados.

En el host los archivos instalados son:

- `/usr/local/sbin/l4d2-public-ip-watch`
- `/etc/default/l4d2-public-ip-watch`
- `/etc/systemd/system/l4d2-public-ip-watch.service`
- `/etc/systemd/system/l4d2-public-ip-watch.timer`
- `/var/lib/l4d2-public-ip-watch/current-ip`

## Instalación

Desde la raíz del repositorio:

```bash
make public-ip-watch-test
sudo make public-ip-watch-install
```

El instalador conserva un `/etc/default/l4d2-public-ip-watch` existente. Antes
de usarlo en otro nodo se deben revisar especialmente `DDNS_HOSTNAME`,
`FIREWALL_SCRIPT` y `FIREWALL_ENV_FILE`.

## Operación

```bash
# Resumen del timer, estado guardado y resolución WAN/DDNS
make public-ip-watch-status

# Consultar sin cambiar estado ni recargar reglas
sudo /usr/local/sbin/l4d2-public-ip-watch --check

# Simular la decisión completa
sudo /usr/local/sbin/l4d2-public-ip-watch --dry-run

# Ver la próxima ejecución
systemctl list-timers l4d2-public-ip-watch.timer

# Seguir los registros
journalctl -u l4d2-public-ip-watch.service -f
```

`--force` fuerza una validación y recarga aunque la dirección no haya cambiado;
debe reservarse para pruebas controladas.

## Runbook: servidores ausentes del grupo Steam

### 1. Comprobar conectividad directa

Si el DNS permite entrar al servidor, el proceso, el port-forwarding y la ruta
básica funcionan. El problema puede estar en la publicación del master server
o en filtros aplicados a sus consultas UDP.

### 2. Comparar WAN, No-IP y estado local

```bash
sudo /usr/local/sbin/l4d2-public-ip-watch --check
```

- Si WAN y No-IP no coinciden, esperar al router/No-IP; el watcher no recarga.
- Si coinciden pero el estado guardado es anterior, la próxima ejecución debe
  validar y reaplicar nftables.
- Si los tres valores coinciden, continuar con los meters y Steam.

### 3. Revisar crecimiento de meters

```bash
sudo nft list table inet firewall_main
```

Los sets dinámicos deben mostrar `flags timeout,dynamic` o
`flags dynamic,timeout`, y sus elementos deben incluir `expires`. Una cantidad
que crece indefinidamente indica que las reglas persistentes o activas son de
una versión anterior.

### 4. Revisar publicación Steam

Valve documenta que los servidores Source pueden compartir el socket UDP del
juego con el tráfico de registro del master server, y ofrece una operación de
heartbeat forzado. Si nftables deja pasar el tráfico y el servidor sigue
ausente, se debe capturar el intercambio y luego configurar
`POST_CHANGE_HOOK` para enviar `heartbeat` a las instancias mediante su canal de
administración, sin reiniciarlas.

Referencia: [ISteamGameServer y `ForceHeartbeat`](https://partner.steamgames.com/doc/api/isteamgameserver#ForceHeartbeat).

El hook se invoca como:

```text
hook IP_ANTERIOR IP_ACTUAL
```

No se debe reiniciar masivamente los gameservers como primera respuesta: una
recarga controlada y un heartbeat atacan directamente los dos subsistemas
involucrados y son menos disruptivos.

## Desactivación y recuperación

```bash
sudo systemctl disable --now l4d2-public-ip-watch.timer
```

Esto detiene la vigilancia, pero no elimina el estado ni revierte las reglas
activas. Para reactivarla:

```bash
sudo systemctl enable --now l4d2-public-ip-watch.timer
```
