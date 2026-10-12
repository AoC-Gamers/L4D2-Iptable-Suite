# L4D2 Iptable Suite

Firewall modular para servicios del host, publicaciones de contenedores y gateways
OpenVPN. Conserva dos motores: **iptables**, con frontends legacy o nft, y
**nftables nativo**. El núcleo compone la política y administra sus propios objetos;
los módulos aportan los controles de cada servicio.

**Instalaciones anteriores:** leer [la migración](docs/security/migration.md).
La selección vacía ya no activa todos los módulos, el forwarding se descarta por
defecto y las redes VPN no reciben acceso completo. Reglas heredadas requieren
identificación y retirada selectiva por el operador antes de adoptar el nuevo flujo.

## Cómo funciona

```text
Configuración declarativa → perfiles/módulos → validación → candidata
→ comprobación del motor → journal + timer → aplicación → conexión nueva → confirmación
                                                     └→ expiración/fallo → reversión
```

`iptables.rules.sh` y `nftables.rules.sh` eligen motor; `ipp.sh` gestiona el mismo
estado y escritor, con nftables por defecto. Sin operación explícita los entrypoints
de motor aplican reglas; `ipp.sh` sin argumentos sólo muestra ayuda.

| Operación | Resultado |
|---|---|
| `validate` | Valida configuración, selección y generación; no consulta el kernel |
| `generate` | Emite un bundle JSON con reglas concretas y objetos administrados |
| `plan` / `--dry-run` | Muestra módulos, familias, permisos y reglas; `--against` añade diferencias |
| `check` | Comprueba la candidata con el motor sin aplicarla; requiere root |
| `apply` | Comprueba y aplica con reversión temporizada; requiere confirmar |
| `confirm` / `rollback` | Confirma un cambio pendiente o restaura sus objetos previos |
| `save` / `load` / `disable` | Guarda, reaplica o retira exclusivamente la política propia |

Los comandos privilegiados recuperan primero cualquier cambio pendiente vencido;
por eso `check`, `status` y `doctor` pueden ejecutar su rollback antes de continuar.
La candidata de `check` no se aplica. Para revisión estrictamente pasiva usar las
operaciones lógicas sin root y consultas directas de lectura del motor.

Los comandos privilegiados comparten bloqueo. nftables sustituye las tablas propias
en una transacción; iptables confirma por tabla/familia y puede tener un intervalo
de versiones mixtas hasta la recuperación. Las cadenas compartidas mantienen sus
reglas y políticas, y Docker no se reinicia. El rollback sólo restaura objetos de
la suite; no recupera conexiones ni estado conntrack.

## Configurar y revisar sin privilegios

Se necesita Python 3.10+ y Bash para validar/generar. El archivo usa `KEY=VALUE`
declarativo; no se ejecuta como shell. Precedencia: CLI > archivo > defaults.
`--env-file` evita cargar el `.env` local implícito. Una configuración desconocida
o incompatible falla antes de aplicar. Ver [configuración y permisos](docs/configuration.md).

```sh
./nftables.rules.sh validate --env-file config/profiles/web.conf
./nftables.rules.sh generate --env-file config/profiles/web.conf > candidate.json
./nftables.rules.sh plan --env-file config/profiles/web.conf --set SSH_RATE=30/minute --against candidate.json
./iptables.rules.sh validate --env-file config/profiles/web.conf
```

| Perfil | Servicios seleccionados | Decisiones necesarias |
|---|---|---|
| [host-minimal](config/profiles/host-minimal.conf) | SSH + núcleo | Adaptar puerto y orígenes administrativos del ejemplo |
| [web](config/profiles/web.conf) | SSH + HTTP/HTTPS TCP | UDP/443 necesita autorización independiente |
| [games](config/profiles/games.conf) | SSH + validaciones/A2S/UDP L4D2 | Juego doble pila en nftables; iptables exige bloqueo IPv6 explícito |
| [vpn-gateway](config/profiles/vpn-gateway.conf) | SSH + OpenVPN servidor | Adaptar interfaces, redes y permisos de reenvío |

Los perfiles se combinan con `--profile web --profile games`; eso selecciona sus
módulos, no carga automáticamente los archivos de ejemplo ni crea servicios.
Una lista `MODULES_ONLY` vacía usa el perfil configurado (default `host-minimal`).
La selección CLI `--only ''` pide únicamente el núcleo.

`HOST_SERVICES`, `CONTAINER_POLICY` y `ROUTED_POLICY` son independientes. Los
[grants de host/reenvío](config/access.example.json) y
[grants de contenedores](config/containers.example.json) delimitan origen, destino,
interfaces, protocolo y puertos. Para Docker también distinguen IP/puerto público
original y destino/puerto interno. NAT modifica direcciones; los permisos de filtro
se declaran por separado.

## Aplicar y persistir

Desplegar primero código revisado en una ruta root sin escritura de grupo/otros,
por ejemplo `/opt/l4d2-firewall`, y configuración en `/etc/l4d2-firewall`. El checkout
de un usuario no cumple el límite de confianza de root. No se instalan paquetes ni
se cambian permisos automáticamente. La [guía operativa](docs/operations-guide.md)
describe preparación, comprobación y recuperación.

Ejemplo para el **host de destino**, después del ensayo en una VM desechable:

```sh
sudo /opt/l4d2-firewall/nftables.rules.sh apply --env-file /etc/l4d2-firewall/web.conf --timeout 120
# Abrir y comprobar una conexión administrativa NUEVA desde otra máquina.
sudo /opt/l4d2-firewall/nftables.rules.sh confirm --token TOKEN --admin-verified
sudo /opt/l4d2-firewall/ipp.sh save
```

El timer systemd se arma antes del primer cambio y sobrevive al proceso/sesión
aplicadora. Sin confirmación, revierte. La automatización puede confirmar mediante
un verificador externo root con `--verify-with`. `--local` es una decisión explícita
para consola/arranque, sin watchdog remoto.

`save` conserva la política confirmada en `/var/lib/l4d2-firewall/persisted.json`.
La [unidad de arranque](systemd/l4d2-firewall.service) se instala/habilita
explícitamente y necesita adaptación de orden si depende de Docker. No se reemplazan
`/etc/nftables.conf` ni los archivos de persistencia de iptables de otros gestores.

## Capacidades y evidencia

La [matriz de motores y Docker](docs/security/capabilities.md) distingue lo soportado,
lo rechazado y lo comprobado. Entre las restricciones actuales:

- Juego iptables: IPv4; `ipv4-block-ipv6` bloquea servicios/reenvío IPv6 y puede
  cortar retornos IPv6 salientes. No desactiva IPv6 en el sistema.
- GeoIP: nftables e IPv4; con política dual exige `GEO_IPV6_POLICY=deny`.
- Suite iptables con Docker nftables: combinación rechazada.
- Clientes L4D2/SourceTV reales, PMTU de VPN, algunas variantes VPN y carga sostenida:
  pruebas pendientes. Los [resultados](docs/security/results.md) detallan el riesgo.

La ejecución local aceptada del 11 de octubre de 2026 incluye 54 unitarias, 20 comprobaciones kernel,
46 casos de integración/regresión y una VM completa con cinco combinaciones Docker,
OpenVPN TLS, SSH nuevo, timer de producción y dos reinicios. Los paquetes de juego
son sintéticos. CI separa lógica, generación, kernel, tráfico y VM; un fallo de
dependencias o privilegios no se contabiliza como aprobación. Comandos reproducibles:
[validación](docs/ai-compat-check.md) y [runner VM](docs/security/vm-runner.md).

El módulo web limita tráfico/conexiones de red; los límites de peticiones pertenecen
al proxy o aplicación. Las reglas locales no recuperan un enlace saturado.

## Documentación

- [Índice de documentación](docs/README.md).
- [Configuración y perfiles](docs/configuration.md), [catálogo de módulos](docs/modules/README.md).
- [Arquitectura](docs/modular-loader-architecture.md) y [garantías transaccionales](docs/security/operations.md).
- [Persistencia y operaciones selectivas](docs/ipp.md).
- [Watcher de IP pública](docs/public-ip-watch.md) y [actualizador GeoIP](geoip-updater/README.md).
- [Auditoría, evidencia y pendientes](docs/operational-audit.md).
- [Analizadores de logs](log-summary/docs/log-summary-container.md): configuración separada del firewall.

## Créditos

Basado en [SirPlease/IPTables](https://github.com/SirPlease/IPTables), con módulos y
herramientas de AoC-Gamers y contribuciones de Sheo y la comunidad L4D2.
