# Migración desde aeabda7

No ejecutar el nuevo flujo directamente sobre un firewall antiguo remoto. Conservar
una consola fuera de banda y hacer primero un ensayo en VM con la política real.
No se atribuye propiedad a objetos preexistentes sólo por llamarse `firewall_main`,
`SSHfilter` o `UDP_GAME_NEW_LIMIT`; el primer despliegue los rechaza antes de modificar.

1. Inventariar ramas/versiones, `nft list ruleset`, ambos save de iptables y servicios
   publicados; identificar el frontend de Docker. Guardar las exportaciones de
   inventario fuera de la persistencia de la suite. No usarlas como rollback global
   automático sobre un host compartido.
2. Revisar el código de una instalación root no escribible por usuarios en `/opt`.
   Migrar configuración a KEY=VALUE declarativo y permisos root. Conservar el `.env`
   anterior como referencia privada; no ejecutarlo ni modificarlo automáticamente.
3. Elegir perfiles y familia. Lista vacía ahora significa perfil mínimo, no todos los
   módulos. Web no carga juego/VPN. CLI reemplaza la selección del archivo. Defaults
   no rellenan vacíos intencionales; un puerto SSH vacío en un módulo activo falla.
   Excepción explícita: `--only ''` significa sólo núcleo, aunque haya un perfil en
   CLI/archivo. No equivale a `MODULES_ONLY=''` sin selección CLI.
4. Traducir `TYPECHAIN=0/1/2` a host=true/false y contenedores=off/restrict. Cualquier
   combinación contradictoria falla. `TYPECHAIN` no determina permisos de enrutamiento.
   Declarar `ROUTED_POLICY` y grants; el default descarta forwarding y puede cortar
   rutas/egreso que antes pasaban de forma amplia. Revisarlo expresamente en el plan.
5. `SSH_DOCKER`, `TCP_DOCKER`, `UDP_DOCKER` pasan a grants `containers` con IP pública,
   IP interna, interfaces, protocolo y ambos puertos. Las publicaciones deben existir
   en Docker. `TYPECHAIN=1` con lista de puertos y sin grants ya no autoriza servicios.
6. Redes VPN dejan de recibir acceso completo al host. Abrir únicamente servicios
   necesarios en `host`, y comunicaciones entre redes en `forward`. El nombre de grupo
   documenta la identidad de uso (admins/monitores/usuarios/consultas). Los grants de
   host son permisos explícitos previos a controles públicos; pueden omitir el límite
   del servicio para ese origen/puerto, nunca otros servicios.
7. `BYPASS_SOURCE_IPS` requiere módulo whitelist y `PRIVILEGED_BYPASS=true`. El plan
   muestra el privilegio completo **al host**, no a todas las rutas. Preferir grants.
   DNS requiere además `DNS_ALLOWED_CIDRS`; cualquier error o respuesta fuera de esos
   prefijos aborta. No existe fallback silencioso a acceso amplio ni a datos DNS viejos.
8. `DOCKER_CHAIN_AUTORECOVER=true` y `DOCKER_INPUT_COMPAT=true` se rechazan. Verificar
   Docker manualmente. La suite no reinicia ni crea sus cadenas. Adaptar egress DNS y
   monitoreo heredados a grants con interfaces y destinos; no se aceptan subredes como
   autorización de todo forwarding por puerto.
9. Para iptables con juego elegir explícitamente `ipv4-block-ipv6`; para juego dual
   usar nftables. Con GeoIP dual, declarar `GEO_IPV6_POLICY=deny`; no existe base GeoIPv6
   equivalente en esta entrega. ICMP/ICMPv6 ya no dependen del módulo de juego.
10. NAT y alias VPN se conservan con validación, pero no abren INPUT/FORWARD. Interfaz
    VPN Docker heredada y logs VPN heredados se rechazan; túneles en host + grants y
    contadores son la migración disponible. No se añaden protocolos VPN.
11. Generar, revisar diferencias y comprobar candidata en VM. Sustituir la versión
    antigua sólo desde consola/mantenimiento, retirando exclusivamente reglas/objetos
    cuya propiedad se haya demostrado. No se entrega borrado automático del layout
    antiguo ambiguo: sus nombres y reglas podían mezclarse con las de terceros.
    No vaciar tablas compartidas ni cambiar políticas para simplificar la migración.
12. Aplicar mediante timer, probar una conexión administrativa nueva, confirmar y
    guardar. Instalar explícitamente la unidad de persistencia propia y adaptar su
    orden respecto de Docker/servicios. Ensayar un reinicio real de la VM antes de usar
    esa persistencia en producción. Conservar la persistencia ajena sin alteraciones.

El checkout local de desarrollo no se desplegó y su `.env` no se migró ni se cambió.
Sus claves históricas `WHITELISTED_*`, `TCP_ALLOW_PORTS`, `UDP_ALLOW_PORTS`,
`FIREWALL_HOST_ALIAS`, `LOGFILE`, `RSYSLOG_CONF` son rechazadas por el núcleo nuevo.
Separar configuración de logging del firewall y traducir permisos conscientemente;
no asumir que las versiones antiguas consumían esas claves.

El módulo opcional `l4d2_tcp_protect` **acepta NEW bajo límite** en sus puertos explícitos,
según el código real anterior y actual. La documentación anterior que decía que no
abría puertos no describía ese comportamiento. El perfil games no lo activa por defecto.
No colocar allowlists TCP que se solapen con SSH/web/TCP de juego protegido; se rechazan.
GameServer y SourceTV tampoco pueden compartir sus puertos configurados.
Los controles SSH/web/TCP de juego tampoco pueden solaparse entre sí. Los timeouts
explícitos deben cubrir la recarga de sus buckets; omitir el timeout permite derivar
un valor suficiente. Para UDP se comparan longitudes del datagrama, sin depender de
opciones IPv4. `UDP_NEW_LARGE_DROP_MIN_LEN` conserva la escala histórica de IPv4 con
cabecera de 20 bytes: se resta 20 y se compara con longitud UDP en ambas familias.
Por ejemplo, 1024 equivale a longitud UDP>=1004; no depende de la cabecera IPv6.

No cambiar backend mientras haya política registrada. Primero desactivar/confirmar
la suite anterior desde consola, comprobar reglas residuales y persistencia, después
seleccionar el otro backend. No se cambia ninguna alternativa ni configuración Docker.

El updater GeoIP en Compose requiere `HOST_UID`/`HOST_GID` del dueño del checkout.
`make geoip-update` y `make geoip-check` los calculan automáticamente. Para Compose
directo, exportarlos o pasarlos mediante `--env-file`; el `env_file` del servicio
no suministra interpolación Compose. La identidad incorrecta falla antes de descargar.
