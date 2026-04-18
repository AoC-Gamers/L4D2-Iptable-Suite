# Arquitectura Modular Dinámica (Legacy + Modern)

## Objetivo

Definir una arquitectura modular para coexistencia indefinida de dos entrypoints:

- iptables.rules.sh (legacy)
- nftables.rules.sh (modern)

Ambos deben cargar módulos dinámicamente desde modules sin conocer de antemano cuántos módulos existen.

---

## Principios de diseño

1. Monorepo con dos targets coexistiendo indefinidamente.
2. Descubrimiento automático de módulos por prefijo de archivo.
3. Metadata embebida en cada módulo (no archivo metadata central).
4. Ejecución determinista por orden semántico: `*_chain_setup` primero, `*_finalize` al final y resto por orden alfabético.
5. Validación centralizada de variables requeridas (CLI > .env > default).
6. Hooks globales de preload y postload para lógica transversal.

---

## Estructura sugerida

```text
.
├─ iptables.rules.sh
├─ nftables.rules.sh
├─ .env
├─ modules/
│  ├─ common_loader.sh
│  ├─ common_nft.sh
│  ├─ preload.sh
│  ├─ postload.sh
│  ├─ ip_chain_setup.sh
│  ├─ ip_finalize.sh
│  ├─ nf_chain_setup.sh
│  ├─ nf_finalize.sh
│  ├─ ip/
│  │  ├─ ip_05_loopback.sh
│  │  ├─ ip_10_whitelist.sh
│  │  ├─ ip_20_allowlist_ports.sh
│  │  ├─ ip_22_docker_dns_egress.sh
│  │  ├─ ip_30_openvpn_server.sh
│  │  ├─ ip_31_openvpn_sitetosite.sh
│  │  ├─ ip_35_tcpfilter_chain.sh
│  │  ├─ ip_40_tcp_ssh.sh
│  │  ├─ ip_42_l4d2_tcp_protect.sh
│  │  ├─ ip_45_http_https_protect.sh
│  │  ├─ ip_50_l4d2_udp_base.sh
│  │  ├─ ip_60_l4d2_packet_validation.sh
│  │  └─ ip_70_l4d2_a2s_filters.sh
│  └─ nf/
│     ├─ nf_35_l4d2_tcpfilter_chain.sh
│     ├─ nf_10_whitelist.sh
│     ├─ nf_20_allowlist_ports.sh
│     ├─ nf_22_docker_dns_egress.sh
│     ├─ nf_30_openvpn_server.sh
│     ├─ nf_31_openvpn_sitetosite.sh
│     ├─ nf_40_tcp_ssh.sh
│     ├─ nf_42_l4d2_tcp_protect.sh
│     ├─ nf_45_http_https_protect.sh
│     ├─ nf_50_l4d2_udp_base.sh
│     ├─ nf_60_l4d2_packet_validation.sh
│     └─ nf_70_l4d2_a2s_filters.sh
└─ docs/
   └─ modular-loader-architecture.md
```

Notas:
- Prefijos recomendados: `ip_` y `nf_`.
- Los módulos de infraestructura transversal por backend (`ip_chain_setup`, `ip_finalize`, `nf_chain_setup`, `nf_finalize`) viven en `modules/` raíz.
- Módulos `common_*` solo para utilidades compartidas (sin reglas específicas de backend).
- Los entrypoints cargan desde el directorio del backend y también desde `modules/` raíz.

---

## Contrato estándar de módulo

Cada módulo debe implementar funciones con namespace del módulo para evitar colisiones.

Ejemplo para modules/ip/ip_30_openvpn_server.sh:

- ip_30_openvpn_server_metadata
- ip_30_openvpn_server_validate
- ip_30_openvpn_server_apply

Ejemplo para modules/nf/nf_30_openvpn_server.sh:

- nf_30_openvpn_server_metadata
- nf_30_openvpn_server_validate
- nf_30_openvpn_server_apply

### Formato de metadata (salida KEY=VALUE)

La función *_metadata imprime líneas KEY=VALUE, por ejemplo:

```bash
ip_openvpn_metadata() {
  cat << 'EOF'
ID=ip_openvpn
DESCRIPTION=Reglas OpenVPN para backend iptables
REQUIRED_VARS=VPN_PORT VPN_PROTO
OPTIONAL_VARS=VPN_SUBNET VPN_INTERFACE VPN_ENABLE_NAT
DEFAULTS=VPN_ENABLE_NAT=false VPN_INTERFACE=tun0
EOF
}
```

Reglas:
- REQUIRED_VARS: variables que deben quedar resueltas tras merge CLI/.env/default.
- OPTIONAL_VARS: variables opcionales que el módulo puede consumir.
- DEFAULTS: pares clave=valor aplicados solo si no existe valor en CLI o .env.

---

## Resolución de variables

Orden de precedencia recomendado:

1. Argumentos CLI
2. Variables de .env
3. Defaults del módulo

Si una variable de REQUIRED_VARS no queda resuelta, el loader detiene ejecución con error claro.

---

## Hooks globales

### preload.sh

Responsabilidades:
- Parsear argumentos globales y por módulo.
- Cargar .env si existe.
- Configurar logging base.
- Checks globales (root, binarios requeridos, compatibilidad mínima).

### postload.sh

Responsabilidades:
- Mostrar resumen de módulos ejecutados.
- Mostrar variables faltantes (si hubo skip por configuración).
- Auditoría final y salida estandarizada.

---

## Descubrimiento dinámico

### Selección por target

- En `iptables.rules.sh`: buscar `ip_*.sh` en `modules/ip` y `modules/`.
- En `nftables.rules.sh`: buscar `nf_*.sh` en `modules/nf` y `modules/`.

### Comportamiento recomendado

1. Listar archivos del patrón correspondiente en backend + raíz.
2. Asignar prioridad semántica (`*_chain_setup` primero, `*_finalize` último).
3. Ordenar por prioridad y nombre para determinismo.
4. `source` de cada módulo.
5. Derivar nombre base del módulo desde archivo.
6. Invocar funciones `metadata/validate/apply` de ese módulo.

---

## Pseudocódigo del loader

```bash
main() {
  run_preload "$@"

  target="ip" # o "nf" según entrypoint
  modules=( $(discover_modules "$target") )

  for module_file in "${modules[@]}"; do
    source "$module_file"

    module_name="$(basename "$module_file" .sh)"
    fn_meta="${module_name}_metadata"
    fn_validate="${module_name}_validate"
    fn_apply="${module_name}_apply"

    metadata="$("$fn_meta")"
    parse_metadata "$metadata"

    resolve_defaults_from_metadata
    merge_cli_env_defaults
    assert_required_vars

    "$fn_validate"
    "$fn_apply"
  done

  run_postload
}
```

---

## Convención de argumentos

Sugerencia para CLI uniforme:

- --env-file .env
- --set KEY=VALUE (repetible)
- --only module_id (repetible)
- --skip module_id (repetible)
- --dry-run
- --verbose
- --modular (compatibilidad heredada, actualmente no requerido)
- --legacy (compatibilidad heredada, sin efecto en entrypoints modulares puros)

Reglas:
- --set siempre sobrescribe .env.
- --only y --skip filtran después de descubrir módulos.
- `MODULES_ONLY` (CSV en `.env`) también permite módulos y se combina con `--only`.
- --dry-run ejecuta metadata + validate, pero no apply.
- Ambos entrypoints (`iptables.rules.sh` y `nftables.rules.sh`) ejecutan modo modular por defecto.

---

## Manejo de errores

Recomendaciones:

1. Fallar rápido en preload si faltan dependencias globales.
2. Fallar por módulo si faltan REQUIRED_VARS.
3. Error explícito con contexto: módulo, variable, origen esperado.
4. Exit codes consistentes:
   - 0 éxito
   - 1 error general
   - 2 validación de variables
   - 3 dependencia del sistema faltante

---

## Ejemplo de flujo (iptables)

1. iptables.rules.sh invoca preload.
2. Descubre `ip_*.sh` en `modules/ip` + `modules/`.
3. Carga ip_30_openvpn_server.sh.
4. Lee metadata y resuelve VPN_PORT por CLI/.env/default.
5. Ejecuta ip_30_openvpn_server_validate.
6. Ejecuta ip_30_openvpn_server_apply.
7. Repite con el resto de módulos.
8. Ejecuta postload con resumen final.

---

## Ejemplo de flujo (nftables)

1. nftables.rules.sh invoca preload.
2. Descubre `nf_*.sh` en `modules/nf` + `modules/`.
3. `nf_chain_setup` crea tabla/cadenas base inet.
4. nf_10..nf_70 aplican reglas por área (whitelist, OpenVPN, TCP, UDP, validaciones, A2S).
5. `nf_finalize` muestra resumen operativo.
6. postload reporta módulos ejecutados y omitidos.

---

## Ejecución rápida

IPTables modular:

```bash
sudo ./iptables.rules.sh
```

Backend moderno nftables:

```bash
sudo ./nftables.rules.sh
```

Con overrides por CLI (aplica en ambos backends):

```bash
sudo ./nftables.rules.sh --set TYPECHAIN=2 --set VPN_PORT=1194
```

---

## Matriz de paridad (ip ↔ nf)

| Área | IPTables | NFTables | Estado |
|---|---|---|---|
| Inicialización de cadenas/tablas | `ip_chain_setup` | `nf_chain_setup` | ✅ Implementado |
| Loopback | `ip_05_loopback` | Integrado en `nf_chain_setup` | ✅ Equivalente funcional |
| Whitelist IP | `ip_10_whitelist` | `nf_10_whitelist` | ✅ Implementado |
| Allowlist de puertos | `ip_20_allowlist_ports` | `nf_20_allowlist_ports` | ✅ Implementado |
| DNS egress Docker | `ip_22_docker_dns_egress` | `nf_22_docker_dns_egress` | ✅ Implementado |
| OpenVPN server | `ip_30_openvpn_server` | `nf_30_openvpn_server` | ✅ Implementado |
| OpenVPN site-to-site | `ip_31_openvpn_sitetosite` | `nf_31_openvpn_sitetosite` | ✅ Implementado |
| Cadena TCP anti-spam | `ip_l4d2_tcpfilter_chain` | `nf_l4d2_tcpfilter_chain` (compat/no-op) | ✅ Implementado |
| SSH base | `ip_40_tcp_ssh` | `nf_40_tcp_ssh` | ✅ Implementado |
| Protección TCP L4D2 | `ip_l4d2_tcp_protect` | `nf_l4d2_tcp_protect` | ✅ Implementado |
| UDP base y límites | `ip_l4d2_udp_base` | `nf_l4d2_udp_base` | ✅ Implementado |
| Validación de tamaños UDP | `ip_l4d2_packet_validation` | `nf_l4d2_packet_validation` | ✅ Implementado |
| Filtros A2S / Steam / login | `ip_l4d2_a2s_filters` | `nf_l4d2_a2s_filters` | ✅ Implementado |
| Cierre y resumen | `ip_finalize` | `nf_finalize` | ✅ Implementado |

Notas de paridad:
- Hay equivalencia funcional por área, no equivalencia 1:1 de sintaxis entre motores.
- En nft se usan expresiones nativas (`nft`) en lugar de módulos `iptables` como `hashlimit`/`string`.

---

## Checklist de validación rápida (host Linux)

Precondiciones:
- Ejecutar como root/sudo.
- Tener instalados `iptables` y `nft` según el backend a probar.
- Partir de `.env` conocido (idealmente copia limpia de `example.env`).

### 1) Validación en seco (sin aplicar)

```bash
sudo ./iptables.rules.sh --dry-run --verbose
sudo ./nftables.rules.sh --dry-run --verbose
```

Esperado:
- Carga de módulos sin errores de `REQUIRED_VARS`.
- Resumen en `postload` con módulos ejecutados/omitidos.

### 1.1) Smoke test automatizado

```bash
./tests/smoke-modules.sh
```

Incluye:
- Validación del contrato por módulo (`*_metadata`, `*_validate`, `*_apply`).
- `dry-run` de ambos backends cuando el entorno tiene root + binarios disponibles.

### 2) Aplicación real por backend

```bash
sudo ./iptables.rules.sh
sudo ./nftables.rules.sh

```

Esperado:
- Mensajes de éxito en `ip_finalize` / `nf_finalize`.
- Sin errores durante carga/validate/apply.

### 3) Verificación de reglas cargadas

```bash
sudo iptables -S
sudo nft list ruleset
```

Esperado:
- Presencia de reglas por áreas equivalentes (whitelist, allowlist, openvpn, tcp, udp, a2s, finalize).

### 4) Escenarios mínimos de paridad

Ejecutar para ambos backends (mismo `.env`):
- `TYPECHAIN=0`, `TYPECHAIN=1`, `TYPECHAIN=2`.
- Inclusión/exclusión del módulo `*_openvpn`.
- Inclusión/exclusión de `*_l4d2_tcp_protect` y prueba con `L4D2_GAMESERVER_TCP_PORTS` con/sin puertos.
- Con y sin `WHITELISTED_IPS`.

Esperado:
- Comportamiento equivalente por escenario, ajustado al motor subyacente.

### 5) Mantenibilidad (regresión rápida)

Antes de merge:
- `--dry-run` en ambos entrypoints.
- Revisión de que nuevos módulos respeten contrato `metadata/validate/apply`.
- Verificar orden semántico (`*_chain_setup` primero, `*_finalize` al final) y alfabético en el resto.

Resultado de aceptación sugerido:
- Sin errores de validación.
- Reglas aplicadas en ambos backends.
- Cobertura completa de la matriz de paridad.

---

## Ventajas de este enfoque

- Escalable: agregar módulo nuevo no requiere tocar el main.
- Mantenible: metadata y lógica viven juntas en el módulo.
- Coexistencia limpia: dos entrypoints, misma filosofía.
- Menor acoplamiento: utilidades comunes separadas de reglas específicas.
- Determinista: prioridad semántica + orden alfabético evita ejecuciones ambiguas.

---

## Plan de implementación sugerido

Fase A (base):
1. Crear common_loader.sh, preload.sh y postload.sh.
2. Adaptar iptables.rules.sh para usar loader dinámico.
3. Extraer 2 módulos iniciales ip_ (por ejemplo openvpn y whitelist).

Fase B (paridad legacy):
1. Migrar el resto de lógica iptables a módulos ip_.
2. Confirmar paridad funcional contra comportamiento actual.

Fase C (modern):
1. Crear nftables.rules.sh con el mismo loader.
2. Implementar módulos nf_ equivalentes a los ip_ críticos.

Fase D (operación):
1. Añadir dry-run y filtros only/skip.
2. Documentar ejemplos operativos en README.
3. Validar mantenimiento simple en ambos targets.

---

## Plantilla mínima de módulo

```bash
#!/bin/bash

ip_sample_metadata() {
  cat << 'EOF'
ID=ip_sample
DESCRIPTION=Modulo de ejemplo
REQUIRED_VARS=MAX_RATE
OPTIONAL_VARS=BURST
DEFAULTS=BURST=20
EOF
}

ip_sample_validate() {
  : "${MAX_RATE:?MAX_RATE is required}"
}

ip_sample_apply() {
  echo "Aplicando ip_sample con MAX_RATE=${MAX_RATE} BURST=${BURST}"
}
```

Esta plantilla aplica igual para nf_sample cambiando prefijo de funciones.
