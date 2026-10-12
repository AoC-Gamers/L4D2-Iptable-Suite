# Primer despliegue

La primera decisión es qué servicios y rutas debe permitir el host. Haz inventario
de interfaces, direcciones, frontend iptables, Docker, familias activas y vía de
recuperación. La suite no deduce permisos a partir de puertos publicados ni de NAT.

1. Lee [los límites](../security/limitations.md) y, si ya hay reglas de una versión
   anterior, [la migración](../migration/README.md).
2. Elige [perfiles](../configuration/profiles.md) y [ACL](../configuration/access-policy.md).
3. Genera y revisa sin root siguiendo [la instalación](installation.md).
4. Comprueba motor y tráfico en [VM desechable](../testing/vm.md).
5. Despliega código/configuración confiables, conserva consola fuera de banda,
   aplica con timer, prueba SSH nuevo desde otro equipo y confirma.
6. Guarda la política y decide expresamente si integrar [el arranque](../boot/README.md).

Un perfil `web` no carga módulos VPN/juego. Un gateway sin Docker puede proteger
servicios nativos y reenvío con decisiones independientes. Ni una salida exitosa de
`validate` ni una conexión SSH establecida aceptan un despliegue.
