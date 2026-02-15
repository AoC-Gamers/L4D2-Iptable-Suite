Módulo 01 — preload.sh

Descripción:
El módulo `preload.sh` se ejecuta antes de cargar los módulos específicos de backend. Prepara el entorno necesario para el resto de módulos: carga módulos del kernel, inicializa variables globales, aplica compatibilidades (por ejemplo con Docker) y realiza saneamiento mínimo de la configuración.

Contextos recomendados:
- Usar cuando sea necesario inicializar dependencias del sistema antes de aplicar reglas (bare-metal, VMs).
- Mantener este módulo ligero y idempotente: evitar lógica de filtrado o reglas complejas aquí.
- Verificar que las acciones sean seguras en entornos con contenedores o sistemas gestionados para no sobrescribir configuraciones en caliente.
