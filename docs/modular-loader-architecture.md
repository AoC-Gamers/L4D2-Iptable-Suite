# Arquitectura modular

El núcleo está en `core/`: `config.py` resuelve datos/composición, `compiler.py` genera
política, `engine.py` implementa operaciones Netfilter, `store.py` serializa escrituras
y journal/rollback, `fw.py` expone la CLI. Los entrypoints y `ipp.sh` delegan al mismo
escritor. `preload.sh` y `run_target_modules` antiguos fallan explícitamente para
impedir aplicación imperativa por una ruta alternativa.

Los módulos shell existentes mantienen IDs/aliases y metadata literal. El núcleo
lee esos heredocs sin ejecutar código. Selecciona el conjunto efectivo, aplica sólo
defaults ausentes, comprueba dependencias/conflictos y valida datos. Después importa
solamente módulos seleccionados en un proceso con entorno controlado. Todos sus
validadores terminan antes de llamar a generadores. En ese proceso `nft`/`iptables`
son funciones de registro; no se llama al motor activo. Reinicios/operaciones Docker
están prohibidos. No es una sandbox para módulos maliciosos: código root debe ser
revisado y protegido, incluidos directorios y helpers. El bootstrap verifica los
archivos Python antes de importar código del proyecto.

La representación común es deliberadamente pequeña: configuración, módulos, grants
host/forward/containers y un bundle de objetos/reglas por motor. No intenta modelar
todo Netfilter. VPN y grants se compilan desde permisos explícitos; servicios de juego,
SSH/web y GeoIP reutilizan sus módulos. Setup/finalize, ICMP/ICMPv6, propiedad y
transacciones son responsabilidades obligatorias del núcleo.

Recorrido UDP de juego: validación de longitud → clasificación A2S/Steam/login →
límite específico y veredicto; tráfico restante → límites base NEW/ESTABLISHED →
veredicto. El ACCEPT genérico establecido queda después de estos controles. SourceTV
permanece separado de login GameServer. nft usa longitud UDP, independiente del tamaño
de cabecera IP; iptables conserva matching IPv4 y rechaza prometer juego IPv6.
Meters por dirección IPv4/IPv6 tienen capacidad y timeout; los logs tienen un límite
escalar y las reglas de descarte no dependen de ese presupuesto. Los límites TCP/web
controlan nuevas conexiones; no son límites por petición.

Una operación parcial recompone el bundle completo partiendo de política confirmada;
comprueba objetos y dependencias existentes. Guardar/cargar/desactivar usan el registro,
no listas manuales de nombres de cadenas. [Operación y garantías](security/operations.md),
[capacidades](security/capabilities.md) y [migración](security/migration.md) contienen
el contrato operativo actual.
