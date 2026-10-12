# Automatización

Hay dos flujos distintos: [watcher de IP pública](public-ip-watch.md), que puede
reaplicar al detectar cambio IPv4 coherente con DDNS, y [actualizador GeoIP](geoip.md),
que descarga/genera archivos antes de una aplicación separada. Ambos entran al
mismo escritor cuando cambian Netfilter y necesitan verificador administrativo
externo para confirmar sin operador.

Sus locks locales serializan trabajo/archivos, no reemplazan el lock del firewall.
El verificador debe probar una conexión nueva desde fuera, terminar sin invocar
al escritor y no imprimir tokens. Fallo/timeout de verificación revierte objetos
propios según [el contrato](../firewall/transactions.md). Un hook externo posterior
no forma parte de esa transacción.

No actives timers/cron copiando ejemplos sin adaptar rutas confiables, permisos,
fuentes de datos y recuperación. Las guías explican qué comandos solo consultan
y cuáles descargan, instalan servicios o aplican reglas.
