Módulo 17 — ip_35_tcpfilter_chain.sh

Descripción:
Este módulo crea y gestiona una cadena dedicada al filtrado TCP en `iptables`. Centraliza reglas comunes de TCP (marcado, redirecciones a cadenas de filtrado, apply de listas de puertos) y facilita la aplicación de políticas coherentes para puertos TCP.

Contextos recomendados:
- Usar cuando se necesite un punto centralizado para reglas TCP complejas o compartidas entre servicios.
- Ideal en hosts que alojan múltiples servicios TCP para evitar duplicidad de reglas y simplificar auditoría.
- Probar cambios en un entorno de staging, ya que reglas TCP mal aplicadas pueden cortar servicios críticos.
