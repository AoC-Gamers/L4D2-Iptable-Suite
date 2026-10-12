# Permisos delimitados y confianza

`HOST_SERVICES`, `CONTAINER_POLICY` y `ROUTED_POLICY` son dimensiones independientes.
El default descarta reenvío; `unmanaged` retorna a otras reglas y delega su protección.
`TYPECHAIN` solo es una traducción heredada al ingresar configuración, nunca un
permiso VPN o de routing. Consulta [migración](../migration/README.md).

`ACCESS_POLICY` es una ruta JSON. El núcleo valida y conserva la ACL parseada en el
bundle schema 2; el estado normalizado no reabre esa ruta en partial/remove/load.
Rutas relativas parten de la instalación. Entradas privilegiadas requieren propiedad
y ancestros root, sin escritura de grupo/otros ni symlinks.

| Sección | Campos exactos | Alcance |
|---|---|---|
| `host` | `group`, `source`, `destination`, `input`, `protocol`, `ports` | Acceso acotado al host, anterior a controles públicos; puede omitir límites de ese servicio |
| `forward` | Los de host + `output` | Flujo direccional enrutado, exige `ROUTED_POLICY=drop` |
| `containers` | Los de forward + `public_destination`, `public_ports`, `service` | Exige `CONTAINER_POLICY=restrict` y módulo de servicio seleccionado; diferencia tuple público/interno DNAT |
| Juego en contenedor | Los de containers + `role` | `service=l4d2_udp_base`; `role=gameserver` o `sourcetv`; protocolo UDP |

Todos los valores son strings; máximo 256 grants por sección. Grupo es etiqueta,
no autenticación. Source/destination son IP o CIDR canónicos de igual familia;
IP pública es una dirección única de esa familia. Interfaces exactas (sin comodín),
protocolo `tcp`/`udp` y puertos 1..65535 o rangos `inicio:fin`. Rangos públicos e
internos deben alinearse con igual longitud. Ver [validación de tipos](reference.md).

Fuentes canónicas: [host/rutas](../../config/access.example.json) y
[contenedores](../../config/containers.example.json). Son ficticias. Por ejemplo,
la red VPN del primer archivo solo obtiene SSH para el origen/destino administrativo
y TCP/9100 para el monitor indicado, no toda la LAN. NAT por sí solo no agrega grants.

Desde la raíz, sin root, esta validación compone los ejemplos sin aplicar reglas:

```sh
./nftables.rules.sh validate --env-file config/profiles/web.conf --profile web --profile games --set CONTAINER_POLICY=restrict --set ACCESS_POLICY=config/containers.example.json
```

Debe validar composición y puertos remapeados. No comprueba que Docker publique
esos puertos: eso requiere preflight/tráfico en [la integración Docker](../docker/README.md).
TCP/443 no concede UDP/443; usa permisos independientes.

## Bypass explícito

`whitelist` + `PRIVILEGED_BYPASS=true` + `BYPASS_SOURCE_IPS` concede bypass completo
**de input al host**, visible en el plan. No habilita reenvío ni acceso general a
contenedores. Prefiere grants por identidad/servicio. `allowlist_ports` abre los
puertos host listados en `BYPASS_TCP_PORTS`/`BYPASS_UDP_PORTS`; no es un permiso de routing.
No se admite allowlist UDP global junto al grupo de juego; solapamientos TCP con
servicios protegidos se rechazan.

DNS requiere además `DNS_ALLOWED_CIDRS`. Fallo DNS, cero/más de 32 respuestas por
dominio o respuesta fuera de los CIDR esperados abortan. La política conserva IP
resueltas, no reconsulta al cargar estado. Eso no acredita identidad ni legitimidad
del dominio: revisa las IP y el privilegio en el plan. Cambiar una ACL activa requiere
el flujo temporizado de [aplicación/rollback](../firewall/transactions.md).

Código: [config.py](../../core/config.py), [schema.py](../../core/schema.py).
Pruebas: [test_h2.py](../../tests/test_h2.py), [h2-flows.py](../../tests/h2-flows.py).
