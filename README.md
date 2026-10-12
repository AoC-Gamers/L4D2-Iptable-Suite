# L4D2 Iptable Suite

Firewall modular con dos motores: **iptables** (frontends legacy/nft) y **nftables
nativo**. Núcleo general para configuración, composición, propiedad, bloqueo,
aplicación, confirmación, rollback y persistencia; módulos específicos para servicios.

Esta revisión cambia el flujo de aplicación y configuraciones peligrosas. **Leer
[la migración](docs/security/migration.md) antes de desplegar sobre una instalación
anterior.** El checkout de desarrollo no debe ejecutarse como root: desplegar código
y configuración revisados, propiedad de root y sin escritura de grupo/otros.

```sh
# Sin root, sin tocar reglas activas:
./nftables.rules.sh validate --env-file config/profiles/web.conf
./nftables.rules.sh plan --env-file config/profiles/web.conf
./iptables.rules.sh generate --env-file config/profiles/web.conf > candidate.json
```

Una lista vacía selecciona el perfil mínimo, no todos los módulos. Perfiles disponibles:
[host mínimo](config/profiles/host-minimal.conf), [web](config/profiles/web.conf),
[juegos](config/profiles/games.conf), [gateway VPN](config/profiles/vpn-gateway.conf).
Se pueden combinar. [Grants por servicio](config/access.example.json) y
[publicaciones de contenedores](config/containers.example.json) separan acceso al host,
redes remotas y puertos públicos/internos. Ejemplos sin datos privados ni secretos.

La aplicación comprueba todos los módulos y candidatas antes de escribir. nftables
reemplaza objetos propios en una transacción; iptables reemplaza cadenas propias por
tabla/familia con garantías limitadas entre commits. Ambos usan un lock común,
registro de propiedad y reversión temporizada independiente de la sesión. Confirmar
requiere comprobar una **conexión administrativa nueva**. No se vacían tablas globales,
no se reinicia Docker y no se reemplaza persistencia de terceros.

- [Operación, confirmación y rollback](docs/security/operations.md).
- [Arquitectura](docs/modular-loader-architecture.md).
- [Capacidades, familias y convivencia Docker](docs/security/capabilities.md).
- [Matriz de hallazgos](docs/security/findings.md).
- [Resultados y limitaciones](docs/security/results.md).
- [Gestión selectiva y persistencia](docs/ipp.md).

## Pruebas

```sh
python3 -I tests/test_core.py       # lógica y composición
python3 -I tests/test_geoip.py      # datos GeoIP sintéticos, sin descargas
bash tests/generate.sh             # generación sin privilegios
bash tests/public-ip-watch.sh      # watcher con mocks (no prueba Netfilter)
bash tests/isolated-run.sh tests/check-engine.py  # kernel, namespace desechable
bash tests/isolated-run.sh          # tráfico real, rollback y concurrencia aislados
```

Falta de dependencias/privilegios falla, no cuenta como aprobado. CI separa sintaxis,
unitarias, generación, comprobación del motor y tráfico. La matriz de versiones y
las pruebas aún pendientes están en results.md. Las topologías Docker sintéticas
no certifican una versión real del daemon ni un reinicio completo de VM.

El módulo web limita conexiones de red; no reemplaza límites de peticiones del proxy
o aplicación. Las reglas locales no mitigan saturación del enlace. Los filtros de
juego se prueban con tráfico sintético y requieren validación adicional con clientes
reales y capturas representativas antes del despliegue.

Los analizadores de logs continúan en [log-summary](log-summary/docs/log-summary-container.md).
La documentación operativa anterior queda como referencia histórica cuando su aviso
indique que fue reemplazada. La autoridad actual es `docs/security/`.

## Créditos

Basado en [SirPlease/IPTables](https://github.com/SirPlease/IPTables), con módulos y
herramientas de AoC-Gamers y contribuciones de Sheo y la comunidad L4D2.
