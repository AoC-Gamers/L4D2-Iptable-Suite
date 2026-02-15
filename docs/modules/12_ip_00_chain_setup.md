Módulo 12 — ip_00_chain_setup.sh

Descripción:
Este módulo inicializa la estructura base para `iptables` (backend `ip`): crea tablas, cadenas y políticas por defecto necesarias para los módulos posteriores, y aplica ajustes de compatibilidad con el sistema (interfaces, NAT, tablas existentes).

Contextos recomendados:
- Usar en sistemas que empleen `iptables` en lugar de `nftables` para garantizar una base consistente antes de añadir reglas específicas.
- Ejecutar con precaución en entornos en producción; comprobar idempotencia para que su re-ejecución no rompa conectividad.
- Mantener este módulo centrado en la infraestructura (cadenas y políticas) y delegar reglas puntuales a módulos específicos.
