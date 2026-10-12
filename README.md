# L4D2 Iptable Suite

Suite modular de políticas de red para servicios del host, publicaciones Docker,
servidores L4D2/web y gateways OpenVPN. Ofrece **iptables** (frontends legacy o
nft) y **nftables nativo**, con configuración declarativa, generación previa,
objetos propios, confirmación remota y reversión temporizada.

El núcleo administra la composición, propiedad y aplicación; los módulos describen
controles de servicios. No instala esos servicios, no administra Docker y no
recupera capacidad de un enlace saturado. El módulo web limita tráfico de red;
las peticiones HTTP deben limitarse en el proxy o aplicación.

## Primera revisión sin privilegios

Desde la raíz del checkout, como usuario **sin root**, con Bash y Python 3.10+:

```sh
./nftables.rules.sh validate --env-file config/profiles/web.conf
./nftables.rules.sh generate --env-file config/profiles/web.conf > candidate.json
./nftables.rules.sh plan --env-file config/profiles/web.conf --set SSH_RATE=30/minute --against candidate.json
./iptables.rules.sh validate --env-file config/profiles/web.conf
```

Son validación lógica y generación: no comprueban kernel ni tráfico. `generate`
escribe el JSON en `candidate.json` mediante la redirección; `plan` muestra reglas
y diferencias respecto de ese archivo. Los valores del ejemplo son ficticios y
no descubren interfaces, rutas ni accesos administrativos del destino.
`--env-file` evita leer el `.env` privado implícito.

Los entrypoints de motor **aplican** si se invocan sin operación. Escribe siempre
la operación explícita. `ipp.sh` sin argumentos muestra ayuda. Los targets
`make firewall-nft` y `make firewall-ip` también aplican y cargan configuración
implícita: no son comandos de diagnóstico ni parte de este inicio rápido.

## Elegir el recorrido

| Necesidad | Guía canónica |
|---|---|
| Primer despliegue y requisitos | [Inicio](docs/getting-started/README.md) e [instalación](docs/getting-started/installation.md) |
| Configurar servicios y familias | [Configuración](docs/configuration/README.md), [perfiles](docs/configuration/profiles.md), [permisos](docs/configuration/access-policy.md) |
| SSH, web y juego | [Administración](docs/administration/README.md), [web](docs/web/README.md), [L4D2/SourceTV](docs/l4d2/README.md) |
| Contenedores o gateway | [Docker](docs/docker/README.md), [OpenVPN](docs/vpn/README.md) |
| Aplicar, confirmar y recuperar | [Transacciones](docs/firewall/transactions.md), [persistencia](docs/firewall/persistence.md), [arranque opt-in](docs/boot/README.md) |
| Instalar sobre versiones anteriores | [Migración funcional](docs/migration/README.md) |
| Desarrollar y probar | [Arquitectura](docs/architecture/README.md), [pruebas](docs/testing/README.md), [CONTRIBUTING](CONTRIBUTING.md) |
| Ver el alcance demostrado | [Motores](docs/firewall/backends.md), [aprobación](docs/security/approval.md), [limitaciones](docs/security/limitations.md) |

La aplicación privilegiada exige instalación confiable, consola de recuperación,
comprobación previa y prueba de una conexión administrativa **nueva** antes de
confirmar. Sigue [la instalación](docs/getting-started/installation.md); no
apliques desde el checkout editable del usuario. Guardar una política no activa
la protección de arranque: unidades y dependencias son opt-in.

## Estado del alcance revisado

> Aprobado con observaciones dentro del alcance implementado y probado.
> La aceptación operativa de cada despliegue requiere validar su configuración,
> versiones, servicios e integración de arranque.

La decisión corresponde al commit `93096dea2d7854a4d580a0b4922d5d1426c8149e`,
12 de octubre de 2026. El [registro de aprobación](docs/security/approval.md)
separa pruebas unitarias, motor, tráfico, VM y pendientes. No aprueba automáticamente
otros commits o despliegues. El [índice documental](docs/README.md) organiza todas
las funcionalidades; la [evidencia histórica](docs/archive/audits/README.md) conserva
fechas, intentos fallidos y límites de cada ensayo.

## Créditos

Basado en [SirPlease/IPTables](https://github.com/SirPlease/IPTables), con módulos y
herramientas de AoC-Gamers y contribuciones de Sheo y la comunidad L4D2.
