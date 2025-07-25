# Plan de Documentación - L4D2 IPTables Suite

## Estructura de Documentación

### 1. README.md (Documento Principal)
**Propósito**: Presentación general del proyecto y guía de inicio rápido.

#### Secciones:
- **Título y descripción**: L4D2 IPTables Suite - Suite de herramientas para administración de iptables en servidores L4D2
- **Características principales**:
  - Protección avanzada contra ataques DDoS específicos de L4D2
  - Soporte para servidores nativos y contenedores Docker
  - Sistema de logging y análisis de ataques
  - Gestión simplificada de reglas persistentes
- **Instalación rápida**:
  - Requisitos del sistema
  - Comandos básicos de instalación
  - Configuración inicial del archivo .env
- **Uso básico**:
  - Aplicar reglas de iptables
  - Activar logging
  - Generar reportes básicos
- **Estructura del proyecto**:
  - Resumen de cada script con enlaces a documentación detallada
- **Créditos**: Mención a SirPlease y el repositorio original
- **Licencia**

### 2. docs/iptables.rules.md
**Propósito**: Documentación técnica completa del script principal de iptables.

#### Secciones:
- **Instalación y configuración**:
  - Requisitos previos (permisos root, paquetes necesarios)
  - Descarga e instalación
  - Configuración del archivo .env
  - Ejemplos de configuración por tipo de servidor
- **Uso del script**:
  - Comandos básicos
  - Parámetros disponibles
  - Ejemplos de ejecución
- **Configuración avanzada**:
  - Explicación detallada de cada variable del .env
  - TYPECHAIN: Diferencias entre INPUT, DOCKER y BOTH
  - Configuración de puertos (GameServer vs SourceTV)
  - Whitelisting de IPs confiables
- **Protecciones implementadas**:
  - **Flood UDP**: Limitación de paquetes por IP y puerto
  - **Ataques Challenge**: Protección específica contra exploits de L4D2
  - **Validación de paquetes**: Filtrado por tamaño y contenido malformado
  - **Consultas A2S**: Control de A2S_INFO, A2S_PLAYERS, A2S_RULES
  - **Protección TCP/RCON**: Bloqueo de spam a puertos de administración
  - **Steam Group Queries**: Limitación de consultas de grupos Steam
  - **ICMP Flood**: Protección contra ping flood
- **Arquitectura técnica**:
  - Cadenas de iptables creadas
  - Algoritmos hashlimit utilizados
  - Análisis de patrones de ataque específicos
  - Diferenciación entre tráfico GameServer y SourceTV
- **Troubleshooting**:
  - Problemas comunes y soluciones
  - Verificación de reglas activas
  - Logs de depuración

### 3. docs/ipp.md
**Propósito**: Documentación del gestor de iptables persistentes.

#### Secciones:
- **Instalación**:
  - Requisitos (permisos sudo/root)
  - Descarga del script
  - Configuración de permisos
- **Uso del menú interactivo**:
  - Descripción de cada opción del menú
  - Flujo de trabajo recomendado
- **Funcionalidades**:
  - **Instalación/desinstalación** de iptables-persistent
  - **Visualización** de reglas actuales y guardadas
  - **Gestión de reglas**: Guardar, limpiar, recargar
  - **Estado del servicio**: Verificación de configuración
- **Casos de uso**:
  - Configuración inicial después de instalar iptables.rules.sh
  - Mantenimiento rutinario de reglas
  - Recovery en caso de problemas
- **Integración**:
  - Cómo usar junto con iptables.rules.sh
  - Automatización con cron/systemd

### 4. docs/iptable.loggin.md
**Propósito**: Documentación del sistema de logging y análisis de ataques.

#### Secciones:
- **Instalación y dependencias**:
  - Instalación de Python 3 y pip
  - Dependencias: pandas, python-dotenv
  - Configuración de permisos para logs del sistema
- **Configuración inicial**:
  - Setup de rsyslog
  - Configuración del archivo .env
  - Verificación de permisos de lectura de logs
- **Uso del menú interactivo**:
  - Opción 1: Instalación automática de rsyslog
  - Opción 2: Verificación de permisos
  - Opción 3: Configuración de grupo 'adm'
  - Opción 4: Análisis y generación de reportes
- **Tipos de análisis disponibles**:
  - **Por IP**: Actividad detallada por atacante con timeline
  - **Por Puerto**: Análisis de ataques por puerto de destino
  - **Por Día**: Breakdown diario con distribución temporal
  - **Por Semana**: Análisis semanal con porcentajes
  - **Por Mes**: Estadísticas mensuales comprehensivas
  - **Por Tipo de Ataque**: Categorización por patrón de ataque
- **Estructura de reportes JSON**:
  - Formato de cada tipo de reporte
  - Campos incluidos en cada análisis
  - Ejemplos prácticos de interpretación
- **Patrones de ataque detectados**:
  - INVALID_SIZE, MALFORMED
  - A2S_INFO_FLOOD, A2S_PLAYERS_FLOOD, A2S_RULES_FLOOD
  - STEAM_GROUP_FLOOD
  - L4D2_CONNECT_FLOOD, L4D2_RESERVE_FLOOD
  - UDP_NEW_LIMIT, UDP_EST_LIMIT
  - TCP_RCON_BLOCK, ICMP_FLOOD
- **Interpretación de resultados**:
  - Cómo leer los reportes generados
  - Identificación de patrones de ataque
  - Recomendaciones basadas en análisis

## Archivos de Ejemplo

### example.env
- Documentar cada variable de configuración
- Proporcionar ejemplos para diferentes escenarios:
  - Servidor único L4D2
  - Múltiples servidores
  - Configuración con Docker
  - Configuración híbrida

### summary_example/
- Incluir ejemplos de cada tipo de reporte
- Documentar la estructura JSON de cada reporte
- Proporcionar casos de uso para cada tipo de análisis

## Guías Adicionales

### Guía de Inicio Rápido (en README.md)
```bash
# 1. Configurar iptables
sudo ./iptables.rules.sh

# 2. Hacer reglas persistentes
sudo ./ipp.sh

# 3. Configurar logging
sudo python3 iptable.loggin.py

# 4. Generar reportes (después de algunos ataques)
sudo python3 iptable.loggin.py
```

### Guía de Troubleshooting
- Problemas comunes de permisos
- Conflictos con otras reglas de iptables
- Issues con Docker
- Problemas de logging

## Consideraciones Técnicas

### Información que debe incluirse:
1. **Compatibilidad**: Distribuciones Linux soportadas
2. **Requisitos**: Versiones mínimas de software
3. **Limitaciones**: Casos donde la suite no es efectiva
4. **Performance**: Impacto en el rendimiento del servidor
5. **Mantenimiento**: Tareas de mantenimiento recomendadas

### Formato de documentación:
- Markdown con sintaxis GitHub
- Código con highlighting apropiado
- Diagramas cuando sea necesario (mermaid)
- Screenshots de menús/salidas cuando sea útil
- Enlaces internos entre documentos
- Índices de contenido para docs largas

## Orden de Creación Recomendado

1. **README.md** - Vista general y entrada al proyecto
2. **docs/iptables.rules.md** - Core del sistema
3. **docs/ipp.md** - Gestión de persistencia
4. **docs/iptable.loggin.md** - Sistema de análisis
5. **Revisión y enlaces cruzados** entre documentos
6. **Testing** de todos los ejemplos y comandos

## Notas Adicionales

- Incluir enlaces al repositorio original de SirPlease
- Mencionar la comunidad L4D2 y casos de uso reales
- Proporcionar información de contacto/soporte
- Incluir changelog si hay versiones futuras
- Agregar badges de compatibilidad/estado del proyecto
