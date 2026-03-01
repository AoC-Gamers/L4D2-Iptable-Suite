# Módulo unificado — l4d2_a2s_filters (ip/nf)

## Objetivo
Mitigar flood de consultas A2S/Steam Group y patrones de login (`connect/reserve`).

## Backends
- iptables: `modules/ip/ip_70_l4d2_a2s_filters.sh` (`ID=ip_l4d2_a2s_filters`)
- nftables: `modules/nf/nf_70_l4d2_a2s_filters.sh` (`ID=nf_l4d2_a2s_filters`)

## Variables principales
- `L4D2_GAMESERVER_PORTS`
- `LOG_PREFIX_A2S_INFO`, `LOG_PREFIX_A2S_PLAYERS`, `LOG_PREFIX_A2S_RULES`
- `LOG_PREFIX_STEAM_GROUP`, `LOG_PREFIX_L4D2_CONNECT`, `LOG_PREFIX_L4D2_RESERVE`

## Variables de tuning (flexibilidad)
- `A2S_INFO_RATE` (default `16`)
- `A2S_INFO_BURST` (default `80`)
- `A2S_PLAYERS_RATE` (default `12`)
- `A2S_PLAYERS_BURST` (default `60`)
- `A2S_RULES_RATE` (default `8`)
- `A2S_RULES_BURST` (default `40`)
- `STEAM_GROUP_RATE` (default `6`)
- `STEAM_GROUP_BURST` (default `30`)
- `L4D2_LOGIN_RATE` (default `4`)
- `L4D2_LOGIN_BURST` (default `16`)
- `ENABLE_STEAM_GROUP_FILTER` (`true|false`, default `true`)
- `STEAM_GROUP_SIGNATURES` (default `"00"`, formato `hex,hex`, por ejemplo `"00,69"`)

## Firmas que usa el módulo
El módulo inspecciona el prefijo Source `0xFFFFFFFF` y luego clasifica por byte de comando:

- `54` -> A2S_INFO (`A2S_LIMITS`)
- `55` -> A2S_PLAYERS (`A2S_PLAYERS_LIMITS`)
- `56` -> A2S_RULES (`A2S_RULES_LIMITS`)
- `71` -> Login short-query L4D2 (subfiltro `connect/reserve`)
- `00` -> Steam Group / queries legacy (si `ENABLE_STEAM_GROUP_FILTER=true`)
- `69` -> Firma opcional Steam/legacy adicional (si se agrega en `STEAM_GROUP_SIGNATURES`)

### Detalle de firmas Steam Group
- La detección Steam Group ya no está hardcodeada a `00`.
- Ahora se controla con `STEAM_GROUP_SIGNATURES`.
- El módulo acepta lista CSV de bytes hex de 2 dígitos, por ejemplo:
  - `STEAM_GROUP_SIGNATURES="00"`
  - `STEAM_GROUP_SIGNATURES="00,69"`
- Si `ENABLE_STEAM_GROUP_FILTER=false`, no se crean reglas de match para firmas Steam Group.

## Lógica de mitigación
- A2S (`54/55/56`): cada tipo entra a su propia cadena con rate/burst dedicado.
- Steam Group (`00` y firmas configuradas): entra a `STEAM_GROUP_LIMITS`.
- Login (`71`):
  - acepta a tasa controlada paquetes que contienen `connect`
  - acepta a tasa controlada paquetes que contienen `reserve`
  - `drop` para el resto de `71` en ventana corta (1..70 bytes)
- El módulo mantiene logging con prefijos específicos para facilitar diagnóstico.

## Validaciones de configuración
Antes de aplicar reglas, el módulo valida:
- `TYPECHAIN` en `0|1|2`
- formato de `L4D2_GAMESERVER_PORTS`
- todos los `*_RATE` y `*_BURST` como enteros positivos
- `ENABLE_STEAM_GROUP_FILTER` en `true|false`
- `STEAM_GROUP_SIGNATURES` con regex hex CSV (`00` o `00,69`, etc.) cuando está habilitado

## Diferencias por backend
- Ambos aplican mitigaciones A2S/Steam y patrones de login equivalentes por área.
- `iptables` usa `-m string --hex-string '|FFFFFFFF..|'`.
- `nftables` usa payload match (`@th,64,40 0xFFFFFFFF..`) con meter/rate.

## Nota operativa
- Excluir `l4d2_a2s_filters` de `MODULES_ONLY` en nodos sin servicios de juego.
- Recomendación: usar puertos reales de juego en `L4D2_GAMESERVER_PORTS` y dejar `UDP_ALLOW_PORTS=""` para evitar bypass de mitigaciones.

## Ejemplos de configuración
Perfil equilibrado (recomendado):

```env
A2S_INFO_RATE=16
A2S_INFO_BURST=80
A2S_PLAYERS_RATE=12
A2S_PLAYERS_BURST=60
A2S_RULES_RATE=8
A2S_RULES_BURST=40
STEAM_GROUP_RATE=6
STEAM_GROUP_BURST=30
L4D2_LOGIN_RATE=4
L4D2_LOGIN_BURST=16
ENABLE_STEAM_GROUP_FILTER=true
STEAM_GROUP_SIGNATURES="00,69"
```

Perfil más estricto:

```env
A2S_INFO_RATE=10
A2S_INFO_BURST=40
A2S_PLAYERS_RATE=8
A2S_PLAYERS_BURST=30
A2S_RULES_RATE=5
A2S_RULES_BURST=20
STEAM_GROUP_RATE=3
STEAM_GROUP_BURST=12
L4D2_LOGIN_RATE=2
L4D2_LOGIN_BURST=6
ENABLE_STEAM_GROUP_FILTER=true
STEAM_GROUP_SIGNATURES="00"
```

Perfil permisivo (tráfico alto legítimo):

```env
A2S_INFO_RATE=30
A2S_INFO_BURST=160
A2S_PLAYERS_RATE=24
A2S_PLAYERS_BURST=120
A2S_RULES_RATE=14
A2S_RULES_BURST=70
STEAM_GROUP_RATE=12
STEAM_GROUP_BURST=60
L4D2_LOGIN_RATE=8
L4D2_LOGIN_BURST=32
ENABLE_STEAM_GROUP_FILTER=true
STEAM_GROUP_SIGNATURES="00,69"
```
