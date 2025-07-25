# iptable.loggin.py - Sistema de Logging y Análisis de Ataques

## Tabla de Contenidos

- [Descripción General](#descripción-general)
- [Instalación y Dependencias](#instalación-y-dependencias)
- [Configuración Inicial](#configuración-inicial)
- [Uso del Script](#uso-del-script)
- [Tipos de Análisis](#tipos-de-análisis)
- [Estructura de Reportes JSON](#estructura-de-reportes-json)
- [Patrones de Ataque Detectados](#patrones-de-ataque-detectados)
- [Interpretación de Resultados](#interpretación-de-resultados)
- [Troubleshooting](#troubleshooting)

## Descripción General

`iptable.loggin.py` es una herramienta avanzada de análisis de logs para iptables específicamente diseñada para servidores L4D2. Proporciona capacidades de logging automático, análisis temporal detallado y generación de reportes JSON comprehensivos sobre diferentes tipos de ataques DDoS.

### Características Principales

- **Configuración automática de rsyslog** para capturar logs de iptables
- **Análisis temporal avanzado** con múltiples perspectivas (IP, puerto, día, semana, mes, tipo de ataque)
- **Generación de reportes JSON** detallados para análisis posterior
- **Detección de patrones específicos** de ataques a servidores L4D2
- **Gestión de permisos** automatizada para acceso a logs del sistema
- **Integración completa** con `iptables.rules.sh`

## Instalación y Dependencias

### Requisitos del Sistema

- **Sistema Operativo**: Linux (Ubuntu 18.04+, Debian 9+, CentOS 7+)
- **Python**: 3.6 o superior
- **Permisos**: sudo/root para configuración de rsyslog y acceso a logs
- **Memoria**: Mínimo 512MB RAM libre para análisis de logs grandes

### Instalación de Dependencias

#### 1. Instalar Python 3 y pip

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip

# CentOS/RHEL
sudo yum install python3 python3-pip
# o para versiones más nuevas:
sudo dnf install python3 python3-pip
```

### Instalación de Dependencias

#### Método 1: Instalación Directa en el Servidor

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-pandas python3-dotenv

# CentOS/RHEL 8+
sudo dnf install python3 python3-pip python3-pandas python3-python-dotenv

# CentOS/RHEL 7
sudo yum install python3 python3-pip
sudo pip3 install pandas python-dotenv

# Verificar instalación
python3 -c "import pandas, dotenv; print('✅ Dependencias instaladas correctamente')"
```

#### Método 2: Instalación con pip

```bash
# Instalar paquetes requeridos con pip
sudo pip3 install pandas>=1.3.0 python-dotenv>=0.19.0

# Verificar instalación
python3 -c "import pandas, dotenv; print('✅ Dependencias instaladas correctamente')"
```

#### Método 3: Entorno Virtual

Para desarrollo, testing o si prefieres mantener las dependencias aisladas del sistema, puedes usar el gestor de entorno virtual incluido. Ver documentación detallada: [Gestor de Entorno Virtual](venv.loggin.md)

```bash
# Ejecutar el gestor de entorno virtual
./venv.loggin.sh

# Seguir las opciones del menú interactivo
# Opción 1: Instalar entorno virtual
# Opción 2: Activar y usar el script
```

#### 3. Descargar el Script

```bash
# Clonar el repositorio completo
git clone https://github.com/AoC-Gamers/L4D2-Iptable-Suite.git
cd L4D2-Iptable-Suite

# O descargar solo el script
wget https://raw.githubusercontent.com/AoC-Gamers/L4D2-Iptable-Suite/main/iptable.loggin.py
chmod +x iptable.loggin.py
```

## Gestor de Entorno Virtual

Para facilitar la gestión de dependencias y el desarrollo en diferentes entornos, el proyecto incluye un gestor de entorno virtual automático (`venv.loggin.sh`). Este script proporciona una interfaz interactiva para:

- **Instalación automática** de entorno virtual Python
- **Gestión de dependencias** aisladas del sistema
- **Compatibilidad multiplataforma** (Linux, Windows, macOS)
- **Verificación automática** de dependencias
- **Activación/desactivación** simplificada

### Uso Rápido

```bash
# Ejecutar el gestor
./venv.loggin.sh

# Seleccionar opciones del menú:
# 1. Instalar entorno virtual
# 2. Activar y usar el script
```

**Documentación completa**: [Gestor de Entorno Virtual - venv.loggin.md](venv.loggin.md)

**Cuándo usar el entorno virtual:**
- 🧪 **Desarrollo y testing**
- 🔒 **Ambientes con restricciones de instalación global**
- 🖥️ **Sistemas Windows con bash**
- 📦 **Múltiples versiones de Python en el sistema**

---

### 1. Archivo de Configuración (.env)

El script utiliza el mismo archivo `.env` que `iptables.rules.sh`. Asegúrate de tener configuradas las siguientes variables relacionadas con logging:

```bash
# Configuración de Logging
LOGFILE=/var/log/l4d2-iptables.log
RSYSLOG_CONF=/etc/rsyslog.d/l4d2-iptables.conf

# Prefijos de Log para Diferentes Tipos de Ataque
LOG_PREFIX_INVALID_SIZE=\"INVALID_SIZE: \"
LOG_PREFIX_MALFORMED=\"MALFORMED: \"
LOG_PREFIX_A2S_INFO=\"A2S_INFO_FLOOD: \"
LOG_PREFIX_A2S_PLAYERS=\"A2S_PLAYERS_FLOOD: \"
LOG_PREFIX_A2S_RULES=\"A2S_RULES_FLOOD: \"
LOG_PREFIX_STEAM_GROUP=\"STEAM_GROUP_FLOOD: \"
LOG_PREFIX_L4D2_CONNECT=\"L4D2_CONNECT_FLOOD: \"
LOG_PREFIX_L4D2_RESERVE=\"L4D2_RESERVE_FLOOD: \"
LOG_PREFIX_UDP_NEW_LIMIT=\"UDP_NEW_LIMIT: \"
LOG_PREFIX_UDP_EST_LIMIT=\"UDP_EST_LIMIT: \"
LOG_PREFIX_TCP_RCON_BLOCK=\"TCP_RCON_BLOCK: \"
LOG_PREFIX_ICMP_FLOOD=\"ICMP_FLOOD: \"

# Configuración de Puertos (para clasificación en reportes)
GAMESERVERPORTS=\"27015\"
TVSERVERPORTS=\"27020\"
```

### 2. Configuración de Permisos

Para que el script pueda acceder a los logs del sistema, el usuario debe tener permisos adecuados:

```bash
# Agregar usuario al grupo 'adm' (para acceso a logs)
sudo usermod -a -G adm $USER

# Reiniciar sesión o aplicar cambios de grupo
newgrp adm

# Verificar permisos
id | grep adm
```

## Uso del Script

### Métodos de Ejecución

#### Método 1: Con Entorno Virtual (Recomendado)

```bash
# Usar el gestor de entorno virtual para ejecución automática
./venv.loggin.sh

# Seleccionar opción 6: 🐍 Run iptable.loggin.py script
# El script maneja automáticamente:
# - Detección de OS (Windows/Linux)
# - Uso de sudo solo cuando es necesario (Linux)
# - Verificación de dependencias
# - Ruta completa del Python del entorno virtual
```

**Ventajas del método de entorno virtual:**
- ✅ **Multiplataforma**: Funciona en Windows, Linux y macOS
- ✅ **Manejo automático de sudo**: Solo en Linux cuando es necesario
- ✅ **Dependencias aisladas**: No afecta el sistema global
- ✅ **Verificación automática**: Confirma que todo esté listo antes de ejecutar
- ✅ **Sin configuración manual**: El script maneja todo automáticamente

#### Método 2: Ejecución Directa (Tradicional)

```bash
# Ejecutar con archivo .env en el directorio actual
sudo python3 iptable.loggin.py

# Ejecutar especificando ruta del archivo .env
sudo python3 iptable.loggin.py --env-file /ruta/al/archivo/.env

# Ejecutar desde cualquier directorio
sudo python3 /ruta/completa/iptable.loggin.py --env-file /ruta/al/.env
```

#### Método 3: Con Entorno Virtual Activado Manualmente

```bash
# Activar el entorno virtual
./venv.loggin.sh
# Opción 2: Activate virtual environment

# En el shell interactivo del entorno virtual:
sudo python iptable.loggin.py --env-file .env

# Salir del entorno
deactivate
```

### Menú Interactivo

Al ejecutar el script, se presenta un menú con las siguientes opciones:

```
=====================================
       L4D2 IPTABLES LOG MANAGER    
=====================================
1 - Install rsyslog and configure L4D2 logging
2 - Check user permissions for log reading
3 - Add 'adm' group permissions to current user
4 - Analyze logs and generate reports
5 - Exit
=====================================
```

#### Opción 1: Instalar rsyslog y Configurar Logging

Esta opción realiza automáticamente:

- **Instalación de rsyslog** (si no está presente)
- **Configuración automática** del archivo rsyslog para L4D2
- **Creación de reglas de filtrado** basadas en los prefijos definidos en `.env`
- **Reinicio del servicio rsyslog** para aplicar cambios

```bash
# Archivo generado: /etc/rsyslog.d/l4d2-iptables.conf
# Contenido típico:
:msg, contains, "INVALID_SIZE: " /var/log/l4d2-iptables.log
:msg, contains, "A2S_INFO_FLOOD: " /var/log/l4d2-iptables.log
# ... etc para todos los prefijos
& stop
```

#### Opción 2: Verificar Permisos de Usuario

Verifica si el usuario actual tiene permisos para leer los logs del sistema:

- Revisa membresía en grupo 'adm'
- Verifica acceso al archivo de log
- Proporciona diagnóstico de problemas de permisos

#### Opción 3: Agregar Permisos de Grupo 'adm'

Agrega automáticamente el usuario actual al grupo 'adm' para acceso a logs del sistema.

#### Opción 4: Analizar Logs y Generar Reportes

Presenta un submenú para seleccionar el tipo de análisis:

```
=== ANALYSIS TYPE ===
1. Summary by IP (detailed structure with multiple dates)
2. Summary by Port (port-focused with top attackers)
3. Summary by Day (daily breakdown with time distribution)
4. Summary by Week (weekly analysis with percentages)
5. Summary by Month (monthly comprehensive stats)
6. Summary by Attack Type (attack pattern analysis)
7. Generate ALL reports (all analysis types)
8. Cancel
```

## Tipos de Análisis

### 1. Análisis por IP (`summary_by_ip.json`)

Proporciona una vista detallada de la actividad de cada IP atacante:

**Información incluida:**
- **Actividad por fecha**: Timeline detallado para cada día
- **Estadísticas totales**: Conteo total de eventos por tipo de ataque
- **Puertos afectados**: Separación entre GameServer y SourceTV
- **Duración de ataques**: Tiempo entre primer y último evento

**Caso de uso**: Identificar atacantes persistentes y patrones de comportamiento específicos.

### 2. Análisis por Puerto (`summary_by_port.json`)

Agrupa los ataques por puerto de destino:

**Información incluida:**
- **Tipo de puerto**: GameServer, SourceTV u Other
- **Breakdown de eventos**: Tipos de ataques por puerto
- **Top atacantes**: IPs más activas contra cada puerto
- **Ventana temporal**: Duración de ataques por puerto

**Caso de uso**: Identificar qué puertos son más vulnerables y requieren protección adicional.

### 3. Análisis por Día (`summary_by_day.json`)

Proporciona una vista diaria de la actividad de ataques:

**Información incluida:**
- **Eventos totales por día**
- **Breakdown por puerto y tipo de ataque**
- **Distribución temporal por horas**
- **Top atacantes por día**

**Caso de uso**: Identificar patrones temporales y picos de actividad maliciosa.

### 4. Análisis por Semana (`summary_by_week.json`)

Vista semanal con análisis estadístico:

**Información incluida:**
- **Totales semanales con porcentajes**
- **Distribución de tipos de ataque**
- **Análisis de puertos por semana**
- **Tendencias temporales**

**Caso de uso**: Análisis de tendencias a mediano plazo y planificación de defensas.

### 5. Análisis por Mes (`summary_by_month.json`)

Análisis mensual comprehensivo:

**Información incluida:**
- **Estadísticas mensuales completas**
- **Porcentajes de distribución de ataques**
- **Análisis de puertos con porcentajes**
- **Comparativas mes a mes**

**Caso de uso**: Reportes ejecutivos y análisis de tendencias a largo plazo.

### 6. Análisis por Tipo de Ataque (`summary_by_attack_type.json`)

Categorización por patrón de ataque:

**Información incluida:**
- **Conteo total por tipo de ataque**
- **Porcentaje del total de eventos**
- **Distribución por tipos de puerto**
- **Días con actividad por tipo**

**Caso de uso**: Identificar los tipos de ataques más comunes y ajustar defensas específicas.

## Estructura de Reportes JSON

Todos los reportes generados siguen una estructura JSON bien definida que facilita su procesamiento automatizado y análisis posterior. Los archivos se generan en la carpeta `summary_example/` del repositorio.

### Ejemplos de Estructura

Para ver ejemplos detallados de cada tipo de reporte, consulta los archivos de ejemplo:

- **Análisis por IP**: Ver [summary_by_ip.json](../summary_example/summary_by_ip.json)
- **Análisis por Puerto**: Ver [summary_by_port.json](../summary_example/summary_by_port.json)  
- **Análisis por Día**: Ver [summary_by_day.json](../summary_example/summary_by_day.json)
- **Análisis por Semana**: Ver [summary_by_week.json](../summary_example/summary_by_week.json)
- **Análisis por Mes**: Ver [summary_by_month.json](../summary_example/summary_by_month.json)
- **Análisis por Tipo de Ataque**: Ver [summary_by_attack_type.json](../summary_example/summary_by_attack_type.json)

### Características Comunes de los Reportes

Todos los reportes JSON incluyen:
- **Timestamps**: Fechas y horas en formato ISO para fácil parsing
- **Contadores**: Números exactos de eventos por categoría
- **Porcentajes**: Distribución relativa para análisis estadístico
- **Metadatos**: Información contextual sobre puertos, IPs y duraciones
- **Estructura jerárquica**: Organización lógica para navegación eficiente

## Patrones de Ataque Detectados

### Ataques de Validación de Paquetes

#### INVALID_SIZE
- **Descripción**: Paquetes UDP con tamaños específicos usados en ataques
- **Detalles técnicos**: Ver [Ataques de Validación de Paquetes](iptables.rules.md#ataques-validacion-paquetes)

#### MALFORMED
- **Descripción**: Paquetes UDP malformados o con contenido inválido
- **Detalles técnicos**: Ver [Ataques de Validación de Paquetes](iptables.rules.md#ataques-validacion-paquetes)

### Ataques de Consulta A2S (Server Query)

#### A2S_INFO_FLOOD
- **Descripción**: Flood de consultas A2S_INFO (0x54)
- **Puertos afectados**: Solo GameServer (no SourceTV)
- **Detalles técnicos**: Ver [Ataques de Consulta A2S](iptables.rules.md#ataques-consulta-a2s)

#### A2S_PLAYERS_FLOOD
- **Descripción**: Flood de consultas A2S_PLAYERS (0x55)
- **Puertos afectados**: Solo GameServer
- **Detalles técnicos**: Ver [Ataques de Consulta A2S](iptables.rules.md#ataques-consulta-a2s)

#### A2S_RULES_FLOOD
- **Descripción**: Flood de consultas A2S_RULES (0x56)
- **Puertos afectados**: Solo GameServer
- **Detalles técnicos**: Ver [Ataques de Consulta A2S](iptables.rules.md#ataques-consulta-a2s)

### Ataques Específicos de L4D2

#### L4D2_CONNECT_FLOOD
- **Descripción**: Flood de paquetes con string "connect"
- **Propósito**: Saturar el proceso de conexión de jugadores
- **Impacto**: Puede prevenir conexiones legítimas
- **Mitigación**: Rate limiting específico por IP
- **Detalles técnicos**: Ver [Ataques Específicos de L4D2](iptables.rules.md#ataques-especificos-l4d2)

#### L4D2_RESERVE_FLOOD
- **Descripción**: Flood de paquetes con string "reserve"
- **Propósito**: Atacar el sistema de reserva de slots
- **Impacto**: Puede causar inestabilidad en lobby management
- **Mitigación**: Rate limiting estricto
- **Detalles técnicos**: Ver [Ataques Específicos de L4D2](iptables.rules.md#ataques-especificos-l4d2)

### Ataques de Limitación UDP

#### UDP_NEW_LIMIT y UDP_EST_LIMIT
- **Descripción**: Protección contra floods UDP en conexiones nuevas y establecidas
- **Detalles técnicos**: Ver [Ataques de Rate Limiting UDP](iptables.rules.md#ataques-rate-limiting-udp)
- **Configuración**: Basada en `CMD_LIMIT` y algoritmos hashlimit específicos

### Otros Ataques

#### STEAM_GROUP_FLOOD
- **Descripción**: Flood de consultas relacionadas con grupos Steam
- **Propósito**: Saturar consultas de información de grupos
- **Impacto**: Consumo de recursos del servidor Steam API
- **Mitigación**: Rate limiting específico
- **Detalles técnicos**: Ver [Ataques de Consulta A2S](iptables.rules.md#ataques-consulta-a2s)

#### TCP_RCON_BLOCK
- **Descripción**: Bloqueo de conexiones TCP maliciosas
- **Propósito**: Proteger puertos RCON de spam/brute force
- **Impacto**: Previene ataques administrativos
- **Mitigación**: Bloqueo completo o rate limiting según configuración
- **Detalles técnicos**: Ver [Ataques TCP/RCON](iptables.rules.md#ataques-tcp-rcon)

#### ICMP_FLOOD
- **Descripción**: Flood de pings ICMP
- **Propósito**: Saturar conectividad de red
- **Impacto**: Degradación general de performance de red
- **Mitigación**: Rate limiting de paquetes ICMP
- **Detalles técnicos**: Ver [Ataques ICMP/Ping Flood](iptables.rules.md#ataques-icmp-ping-flood)

## Interpretación de Resultados

### Análisis de Severidad

#### Ataques de Alta Severidad
- **A2S_RULES_FLOOD**: Respuesta muy grande, alto impacto en bandwidth
- **L4D2_CONNECT_FLOOD**: Puede prevenir conexiones legítimas
- **TCP_RCON_BLOCK**: Intentos de comprometer administración

#### Ataques de Severidad Media
- **A2S_INFO_FLOOD / A2S_PLAYERS_FLOOD**: Impacto moderado en recursos
- **UDP_EST_LIMIT**: Afecta jugadores conectados
- **STEAM_GROUP_FLOOD**: Impacto en funcionalidades sociales

#### Ataques de Baja Severidad
- **INVALID_SIZE / MALFORMED**: Filtrados automáticamente
- **UDP_NEW_LIMIT**: Protección preventiva
- **ICMP_FLOOD**: Impacto mínimo si está bien limitado

### Recomendaciones por Patrón

#### Si predominan ataques A2S:
```bash
# Ajustar límites más estrictos en .env
CMD_LIMIT=60  # Reducir de 100 a 60
```

#### Si hay muchos TCP_RCON_BLOCK:
```bash
# Habilitar protección TCP completa
ENABLE_TCP_PROTECT=true
TCP_PROTECTION=\"27015:27020\"
```

#### Si hay ataques persistentes de una IP:
```bash
# Agregar a whitelist si es legítima (acceso completo al sistema)
WHITELISTED_IPS=\"IP_CONFIABLE1 IP_CONFIABLE2\"
```

### Umbrales de Alerta

- **> 1000 eventos/día por IP**: Investigar comportamiento
- **> 50% de un tipo de ataque**: Ajustar defensas específicas
- **Duración > 1 hora**: Posible ataque coordinado
- **> 10 IPs diferentes en 1 hora**: Posible botnet

## Troubleshooting

### Problemas Comunes

#### \"Permission denied\" al acceder a logs

**Síntomas**:
```
❌ Error: Permission denied reading /var/log/l4d2-iptables.log
```

**Solución**:
```bash
# Verificar permisos del archivo
ls -la /var/log/l4d2-iptables.log

# Agregar usuario a grupo adm
sudo usermod -a -G adm $USER
newgrp adm

# Si persiste, ajustar permisos del archivo
sudo chmod 644 /var/log/l4d2-iptables.log
```

#### Archivo de log no se genera

**Síntomas**:
- El archivo `/var/log/l4d2-iptables.log` no existe
- Los reportes están vacíos

**Diagnóstico**:
```bash
# Verificar configuración de rsyslog
sudo systemctl status rsyslog
cat /etc/rsyslog.d/l4d2-iptables.conf

# Verificar logs de sistema
sudo journalctl -u rsyslog -f
```

**Solución**:
```bash
# Reconfigurar rsyslog usando el script
sudo python3 iptable.loggin.py
# Seleccionar opción 1

# Reiniciar rsyslog
sudo systemctl restart rsyslog

# Generar tráfico de prueba para verificar logging
# (ejecutar iptables.rules.sh primero)
```

#### Dependencias de Python faltantes

**Síntomas**:
```python
ModuleNotFoundError: No module named 'pandas'
```

**Solución**:
```bash
# Instalar dependencias
sudo pip3 install pandas python-dotenv

# Verificar instalación
python3 -c \"import pandas, dotenv; print('OK')\"
```

#### Reportes JSON vacíos o incompletos

**Síntomas**:
- Archivos JSON generados pero con arrays vacíos
- Conteos de eventos en 0

**Posibles causas**:
1. **Prefijos de log incorrectos** en .env
2. **iptables.rules.sh no ejecutado** previamente
3. **No hay tráfico de ataque** registrado aún

**Solución**:
```bash
# Verificar que existen logs
sudo tail -20 /var/log/l4d2-iptables.log

# Verificar prefijos en .env coinciden con iptables.rules.sh
grep LOG_PREFIX .env

# Generar tráfico de prueba (opcional, solo para testing)
# Nota: NO hacer en producción
```

#### Error de configuración de .env

**Síntomas**:
```
❌ .env file not found: /path/to/.env
```

**Solución**:
```bash
# Especificar ruta correcta del archivo .env
sudo python3 iptable.loggin.py --env-file /ruta/correcta/.env

# O copiar example.env como .env
cp example.env .env
```

### Verificación de Configuración

Para verificar que el sistema de logging esté funcionando correctamente, puedes usar los siguientes comandos:

```bash
# Verificar estado de rsyslog
sudo systemctl status rsyslog

# Verificar configuración L4D2
cat /etc/rsyslog.d/l4d2-iptables.conf

# Verificar permisos de usuario
id | grep adm

# Verificar contenido del log
sudo tail -10 /var/log/l4d2-iptables.log
```

### Optimización de Performance

Para logs muy grandes (>100MB), el script automáticamente optimiza el análisis procesando los datos por chunks. Si necesitas analizar solo eventos recientes, puedes pre-filtrar:

```bash
# Analizar solo eventos del día actual
sudo grep "$(date +%Y-%m-%d)" /var/log/l4d2-iptables.log > /tmp/today-attacks.log
```

Para configurar rotación automática de logs y evitar que crezcan demasiado:

```bash
# Configurar logrotate para L4D2
sudo tee /etc/logrotate.d/l4d2-iptables > /dev/null << EOF
/var/log/l4d2-iptables.log {
    daily
    rotate 7
    compress
    delaycompress
    create 644 root adm
    postrotate
        systemctl reload rsyslog
    endscript
}
EOF
```

---

## Enlaces Relacionados

- [README Principal](../README.md)
- [Gestor de Entorno Virtual - venv.loggin.sh](venv.loggin.md)
- [Documentación iptables.rules.sh](iptables.rules.md)
- [Documentación ipp.sh](ipp.md)
- [Archivo de Configuración example.env](../example.env)

---

*Documentación actualizada para L4D2 IPTables Suite v2.4*
