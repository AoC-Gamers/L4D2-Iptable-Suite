# HAR-01: aislamiento del lock de xtables

El namespace de red aísla las reglas, pero el namespace de montaje inicialmente
conserva el mismo filesystem de `/run`. iptables usa `/run/xtables.lock`; probar
el frontend legacy con ese archivo compartido podía provocar contención con
administradores externos aunque las reglas fueran de otro namespace.

`tests/isolated-run.sh` monta ahora un tmpfs privado sobre `/run` dentro del nuevo
namespace de montaje. Antes de ejecutar motores comprueba tanto la red diferente
como el dispositivo/inodo diferente de `/run`. Fallar al crear ese aislamiento es
un error obligatorio. `mount` también es una dependencia explícita.

Se verificó con nftables 1.0.9 e iptables 1.8.10 nf_tables mediante 10 candidatas,
17 casos de integración, 2 de recuperación y 4 de política aislados. Esto no
certifica legacy: sus intentos locales fallaron por capacidades del entorno.
No se creó intencionalmente un lock del host para reproducir el defecto.

Referencia: manual instalado de iptables 1.8.10, sección `LOCK FILE`, y
[Netfilter upstream](https://git.netfilter.org/iptables/log/configure.ac?showmsg=1).
