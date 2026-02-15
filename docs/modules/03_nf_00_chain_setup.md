Módulo 03 — nf_00_chain_setup.sh

Descripción:
Este módulo inicializa la estructura base de `nftables`: crea tablas, cadenas y políticas por defecto necesarias para los módulos posteriores. Define las cadenas de entrada/salida/reenvío y establece políticas seguras por defecto.

Contextos recomendados:
- Usar cuando el backend seleccionado es `nft` y se necesita asegurar una base consistente antes de aplicar reglas específicas.
- Ejecutar en despliegues controlados (servidores, VMs). Evitar ejecuciones en caliente sin pruebas en sistemas en producción porque puede afectar conectividad.
- Mantener idempotencia: el módulo debe poder re-ejecutarse sin romper la tabla existente.
