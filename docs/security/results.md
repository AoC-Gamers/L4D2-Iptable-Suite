# Evidencia y límites de aceptación — 2026-10-11

Base revisada: `aeabda7cbba25ecd94629797f5637a9a6987c147`, `main` inicialmente
limpio. Implementación en `security/modular-safe-apply`. No se aplicaron reglas en
el anfitrión ni se reiniciaron sus redes, Docker, SSH o VPN. El `.env` local
ignorado se conservó. Código y documentos se modificaron en la rama dedicada.

## Entorno

Linux x86_64 `7.0.0-38-generic`; nftables `1.0.9`; iptables/ip6tables `1.8.10`
con frontend `nf_tables`; Python `3.12.3`; Bash `5.2.21`; util-linux `2.39.3`;
ShellCheck `0.9.0` (binario extraído de paquete, sin instalarlo en el host).
Las pruebas privilegiadas ejecutan una copia del repositorio en namespaces de
usuario, red y montaje desechables, con peers en otras redes aisladas. El wrapper
comprueba que la red no es la del proceso llamador antes de ejecutar Netfilter.

También se intentó el frontend legacy `1.8.10` en un contenedor desechable Debian
bookworm, `--network none`, sin socket Docker ni red del host. El kernel compartido
no tenía `ip6_tables` disponible dentro de ese entorno. La suite completa legacy
**falló**, no se cuenta como aprobada; no se cargaron módulos en el anfitrión para
sortearlo. Docker anfitrión `29.8.2` sólo se usó para inventario y ese contenedor.

## Resultados separados

| Capa | Comando reproducible | Resultado observado | Qué demuestra |
|---|---|---|---|
| Unitarias de núcleo | `python3 -I tests/test_core.py` | 21 PASS | Parser, IP/CIDR, selección/dependencias/conflictos, familias, tipos, privilegios DNS, duración de estado, metadata sin ejecutar código deshabilitado |
| Unitarias de datos | `python3 -I tests/test_geoip.py` | 3 PASS | CIDR inválido conserva archivo previo; país no escapa directorio; generación selectiva |
| Watcher con mocks | `bash tests/public-ip-watch.sh` | PASS | DDNS, recarga y estado; no demuestra reglas kernel ni una conexión administrativa real |
| Emisión HTTP con captura | `bash tests/http-https-protect.sh` | PASS | Sintaxis emitida/protocolo/claves; no prueba kernel por sí sola |
| Generación | `bash tests/generate.sh` | 8 PASS | Cuatro perfiles por ambos motores, sin root |
| Comprobación kernel | `bash tests/isolated-run.sh tests/check-engine.py` | 10 PASS | Candidatas mínimas/web/juegos/VPN server NAT/S2S alias+SNAT aceptadas por `nft -c` o restore `--test` |
| Integración real | `bash tests/isolated-run.sh` | 17 PASS | Reglas aplicadas y paquetes reales entre namespaces, más fallos/reversión/concurrencia; ambos motores nf/nft-nativo |
| Sintaxis | `bash -n` de todos los shell versionados; `python3 -m compileall -q core scripts tests`; `git diff --check` | PASS | Sintaxis y whitespace, no política efectiva |
| ShellCheck | `shellcheck -x` del shell de suite, automatizaciones y pruebas | PASS | Se excluye sólo el helper histórico de entorno de logs `log-summary/venv.loggin.sh`, ajeno a Netfilter; no se declara limpio todo el shell del repositorio |
| Workflow local | `actionlint 1.7.7` en contenedor sin red, checkout readonly | PASS | YAML/expresiones/jobs; sin ejecutar CI remoto |
| CI remoto | Jobs separados, matriz nft/legacy | Configurado, no ejecutado remotamente | Falta de root/dependencias falla; no hay skip con resultado verde |

Los logs de la ejecución local se conservaron en `tmp/security/` (ignorado) y en
la entrega de evidencia. Una prueba exitosa de generación o una captura con mocks
no se contabiliza como comprobación del motor o del tráfico.

## Implementado y probado con motor o tráfico real

Las 17 pruebas de `tests/integration.py` cubren:

1. Configuración, ID y candidata de kernel inválidos conservan reglas activas.
2. Web/administración IPv4 e IPv6; segunda aplicación sin duplicar hooks/objetos.
3. Presupuestos SSH independientes por origen; contadores de LOG acotados bajo
   una ráfaga y descartes que continúan agotado el presupuesto de logs.
4. UDP establecido pasa validaciones/límites; vacío/sobredimensionado descartado;
   A2S, login y SourceTV sintéticos; opciones IPv4 no eluden el tamaño UDP.
5. Expiración restaura; confirmación conserva; snapshot de meters ya poblados.
6. SIGKILL del aplicador tras una escritura real; watchdog separado restaura.
7. Fallo inyectado **después de un commit IPv4 real** restaura ambas familias.
8. Guardar/desactivar/cargar, retirar web y actualizar SSH parcialmente.
9. Dos escritores CLI concurrentes: uno aplica y el otro rechaza el cambio
   pendiente, compartiendo el mismo bloqueo.
10. Gateway nativo sin Docker, permisos direccionales IPv4/IPv6; otros puertos,
    orígenes y acceso al host permanecen denegados.
11. Topologías Docker iptables/nft **sintéticas en kernel**, DNAT público/interno,
    retorno y prohibición de UDP por un permiso TCP del mismo puerto.
12. Reglas ajenas añadidas mientras hay cambio pendiente sobreviven al rollback.
13. Remapeo de GameServer y SourceTV en contenedores, consulta/login/tamaño y
    separación TCP/UDP.
14. NAT de VPN no concede reenvío; grant explícito permite sólo el servicio y
    el servidor remoto observa la dirección traducida esperada.
15. Configuración escribible rechazada; parcial con tabla ausente falla sin crearla.
16. Verificador fallido restaura; verificador desde otro namespace abre una
    conexión TCP nueva y confirma. No se afirma autenticación SSH real.
17. Nombre nft personalizado, colisión con objeto ajeno y Docker ausente: error
    antes de modificar la política activa.

Todas las pruebas conservan además una tabla/regla ajena y un archivo centinela.
El centinela no equivale a reiniciar servicios de persistencia del sistema.
La recarga de la política guardada se probó en el mismo kernel, dentro del namespace; un reinicio
completo del sistema sigue pendiente.

## Implementado, probado sólo de forma unitaria o lógica

Resolución DNS privilegiada cerrada ante fallos/respuestas fuera de CIDR; parser
de automatización; sustitución selectiva de datos GeoIP; precedencia CLI/archivo,
rechazo de opciones retiradas y plazos monotónicos vinculados al boot ID. Los
errores DNS se inyectaron mediante mocks y no certifican un DNS real.

La unidad systemd de arranque y el timer independiente de producción están
implementados. La prueba de interrupción usa el watchdog de procesos restringido
al namespace; **no demuestra el timer systemd de producción**. La verificación
automática prueba su contrato con TCP desde otro namespace, no un servicio SSH
autenticado desde Internet.

## Pendiente y riesgo residual

| Pendiente | Causa / evidencia que falta | Riesgo residual y condición de despliegue |
|---|---|---|
| Docker daemon real, ambos backends, versiones de destino | Se probaron topologías y DNAT de kernel; no daemon anidado real | Orden/prioridades y cambios de Docker pueden diferir. Validar publicaciones, egreso y retorno en VM desechable con esa versión |
| Timer systemd y pérdida de sesión en VM | Namespace de pruebas sin systemd como PID 1 | No desplegar cambios remotos hasta probar timer independiente, timeout y fallo del verificador en VM |
| Persistencia tras reboot completo | Se probó save/disable/load; no reinicio de VM | Verificar unidad, orden respecto a Docker/servicios y recuperación de journal anterior al boot |
| Suite iptables-legacy completa y doble pila | Falta `ip6_tables` en entorno desechable local; intento fallido visible | No certificar legacy con esta evidencia. CI exige módulos en su VM y falla si faltan; ejecutar matriz antes de promover |
| Clientes L4D2/SourceTV/OpenVPN y SSH reales | Tráfico sintético/socket TCP y redes simuladas | Verificar handshake, descubrimiento, PMTU y autenticación con clientes/capturas representativos |
| Tráfico S2S alias/SNAT y GeoIP | Candidata S2S comprobada por kernel; GeoIP validación/generación, sin matriz de tráfico completa | Probar permisos después de DNAT y allow/deny/manual v4; no prometer GeoIP v6 |
| Exhaustión sostenida de todos los meters / logs durante horas | Hay capacidad/timeout/fallback y pruebas de ráfaga, no ensayo prolongado | Ajustar memoria/tasas con carga representativa; límites por regla no son un presupuesto universal del host |
| Atomicidad conjunta iptables | Limitación del motor entre tablas/familias | Puede haber versiones mixtas hasta rollback; conexiones, contadores, conntrack y tokens no se restauran |

Los nombres registrados son propiedad exclusiva de la suite. El bloqueo serializa
sus escritores, no administradores externos; se conservan cambios ajenos fuera
de esos objetos. No hay adopción/borrado automático de objetos heredados.
`--local` elige explícitamente operar sin watchdog remoto y requiere consola para
recuperar una interrupción. Los datos GeoIP se reemplazan por archivo, no como
una única edición transaccional multi-país.

La aceptación completa solicitada **no queda demostrada** por esta ejecución.
La entrega implementa y verifica los bloques indicados, y deja estas condiciones
visibles para la validación final en una VM adecuada. Terminar scripts sin errores
no constituye una certificación de seguridad ni una garantía contra saturación
del enlace.

## Auditoría iterativa posterior

La ronda posterior desde `148875e`, delegada a tres agentes GPT-6 Luna con esfuerzo
alto, corrigió **10 issues** y cerró con una revisión cruzada sin hallazgos nuevos
confirmados. El registro, archivos, regresiones y alcance están en
[`iterative-audit.md`](iterative-audit.md). El coordinador repitió 39 unitarias,
8 generaciones, 10 comprobaciones de motor y 23 casos aislados, además de watcher,
ShellCheck/sintaxis/actionlint. Estas cifras sustituyen los totales de la primera
ejecución para el estado final de la rama; las limitaciones de aceptación anteriores
permanecen vigentes. `/run` y su lock xtables también están aislados en el harness.
