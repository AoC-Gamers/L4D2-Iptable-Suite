# Validación con Docker real en VM QEMU

Los resultados citados son evidencia anterior, no una ejecución nueva de esta rama
documental. [Aprobación por commit](../security/approval.md) identifica la revisión
aceptada y [archivo](../archive/audits/README.md) conserva los ensayos anteriores.

## Estado

Harness ejecutado en VM QEMU desechable. El script aborta salvo que corra
como root dentro de una VM `qemu`/`kvm` cuyo
`/run/l4d2-suite-vm.json` sea archivo regular de root, modo `0600`, y contenga
exactamente `{"virtualization":"qemu","disposable":true}`.

El wrapper crea namespaces privados de red y montajes, monta un `/run` tmpfs y
recrea allí el marcador. Así el suite y Docker sólo operan en esa red aislada,
y el state-dir temporal no colisiona con el estado persistente del guest.

El harness inicia un `dockerd` dedicado con socket, `data-root`, `exec-root`,
PID y configuración propios bajo un directorio temporal en `/run`. El cliente
Docker siempre recibe ese socket explícitamente. El proceso no lee ni escribe
`/etc/docker/daemon.json`, no usa systemd y no cambia `update-alternatives`.
Para el backend Docker iptables, los ejecutables `iptables`, `ip6tables`,
`*-restore` y `*-save` se seleccionan con enlaces privados en el `PATH` del
daemon. El backend y el frontend solicitados se reflejan en el resultado JSON.

## Resultado

Matriz ejecutada en kernel guest `6.8.0-142-generic`, Docker Engine `29.8.2`,
iptables `1.8.10` y nftables `1.0.9`:

| Suite | Docker | Frontend Docker iptables | IPv4/IPv6 | Estado |
| --- | --- | --- | --- | --- |
| iptables | iptables | nft | TCP publicado/retorno, UDP aislado | PASS |
| iptables | iptables | legacy | TCP publicado/retorno, UDP aislado | PASS |
| nftables | iptables | nft | TCP publicado/retorno, UDP aislado | PASS |
| nftables | iptables | legacy | TCP publicado/retorno, UDP aislado | PASS |
| nftables | nftables | nativo | TCP publicado/retorno, UDP aislado | PASS |

La combinación iptables suite / Docker nftables queda fuera de la matriz:
devuelve `SKIP` con código 77 porque no está soportada.

Cada PASS comprobó DNAT IPv4 e IPv6 a un puerto interno distinto del público, retorno TCP,
aislamiento TCP/UDP con una única concesión TCP por familia, preservación de
reglas extranjeras y aplicación idempotente. Las pruebas de tráfico se
repitieron después de `disable` para confirmar que Docker conserva las
publicaciones. Los dos casos con forwarding limitado también permitieron el
puerto IPv4 concedido y bloquearon un listener activo en el puerto adyacente.
En suite nftables / Docker iptables, el egress quedó delegado a Docker, tal
como indica el preflight del producto.

Las salidas completas están en `tmp/vm/docker-*.log` en el workspace de
validación.

## Invocación

Estos comandos son fases privilegiadas **solo dentro del guest QEMU desechable**,
desde `/opt/l4d2-firewall`, no instrucciones para el host. La reproducción preferida
es [el runner completo](vm.md) sin root anfitrión; crea daemons/puertos/estado de
prueba y limpia los objetos propios al salir. Si falta attestation, se debe fallar.

Provisionar el guest con Docker Engine y CLI, Python 3, `iproute2`, el suite en
`/opt/l4d2-firewall`, y los frontends que se quieran probar. No configurar un
daemon Docker para arrancar en el guest: el harness levanta su propia instancia.
El namespace de red desechable se destruye al salir, así que reglas y bridges
de esa corrida no permanecen en el namespace de red del guest.

```sh
sudo tests/vm/docker.sh --suite-backend iptables --docker-backend iptables --iptables-frontend nft
sudo tests/vm/docker.sh --suite-backend iptables --docker-backend iptables --iptables-frontend legacy
sudo tests/vm/docker.sh --suite-backend nftables --docker-backend iptables --iptables-frontend nft
sudo tests/vm/docker.sh --suite-backend nftables --docker-backend iptables --iptables-frontend legacy
sudo tests/vm/docker.sh --suite-backend nftables --docker-backend nftables
```

La combinación suite iptables / Docker nftables no está soportada por la
política actual y se reporta como `SKIP`. El egress limitado se prueba en
suite iptables / Docker iptables y suite nftables / Docker nftables. Para suite
nftables / Docker iptables, el preflight del producto no admite grants de
forwarding; se usa `ROUTED_POLICY=unmanaged` y el egress queda delegado a Docker,
sin afirmar que el suite lo limita.

## Flujos y límites

El harness construye una imagen dentro del guest a partir de su intérprete y
biblioteca estándar Python y la importa localmente, sin consultar un registry.
Un cliente en namespace de red separado alcanza la IP guest `198.18.0.1`; Docker
publica TCP y UDP `:18080` al puerto interno `18443` del contenedor. Sólo se
concede TCP, por lo que la prueba comprueba remapeo, retorno TCP y aislamiento
de protocolo UDP. También prueba un grant de egress a un listener TCP y bloquea
un listener activo en el puerto adyacente. Verifica una regla extranjera,
aplicación idempotente y que `disable` conserva la publicación de Docker.

El daemon habilita forwarding IPv4 e IPv6 sólo dentro de namespaces desechables
del guest. El cliente IPv6 usa un veth aislado; Docker recibe un pool IPv6 fijo y
el harness confirma la dirección IPv6 del contenedor dentro del prefijo ULA
de prueba antes de comprobar la publicación IPv6. El wrapper destruye las interfaces y namespaces al
salir. Native nftables de Docker requiere
Engine 29 o posterior, sigue siendo experimental y no funciona en Swarm; el
harness informa `SKIP` si falta el frontend o la versión. Docker documenta que
el backend nftables no habilita por sí mismo el forwarding IP y no es compatible
con Swarm. Esta matriz cubre tráfico TCP/UDP dual-stack en el guest; no sustituye
la validación con clientes de juego ni cubre otros protocolos de aplicación.

Referencias: [Docker con nftables](https://docs.docker.com/engine/network/firewall-nftables/),
[firewalls y backend del daemon](https://docs.docker.com/engine/network/packet-filtering-firewalls/),
[configuración del daemon](https://docs.docker.com/engine/daemon/) y
[resolución de `iptables` en Moby mediante `exec.LookPath`](https://github.com/moby/libnetwork/blob/master/iptables/iptables.go).
