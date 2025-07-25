# L4D2 IPTables Suite

<div align="center">

![L4D2 IPTables Suite](https://img.shields.io/badge/L4D2-IPTables%20Suite-green.svg)
![Version](https://img.shields.io/badge/version-2.4-blue.svg)
![License](https://img.shields.io/badge/license-MIT-yellow.svg)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)

**Suite de herramientas avanzadas para administración de iptables especializada en servidores Left 4 Dead 2**

*Protección completa contra ataques DDoS específicos de Source Engine con sistema de logging y análisis integrado*

</div>

---

## 📋 Características Principales

- 🛡️ **Protección Avanzada DDoS**: Mitigación específica contra ataques comunes a servidores L4D2
- 🐳 **Soporte Docker**: Compatibilidad completa con servidores nativos y contenedores
- 📊 **Sistema de Logging**: Análisis detallado de ataques con reportes JSON comprehensivos
- ⚙️ **Gestión Simplificada**: Herramientas intuitivas para administrar reglas persistentes
- 🎯 **Detección Inteligente**: Identificación de patrones específicos de ataques Source Engine
- 📈 **Análisis Temporal**: Reportes por IP, puerto, día, semana, mes y tipo de ataque

## 🚀 Instalación Rápida

### Requisitos Previos

- **Sistema**: Linux (Ubuntu 18.04+, Debian 9+, CentOS 7+)
- **Permisos**: Acceso root/sudo
- **Dependencias**: Python 3.6+, iptables, rsyslog

### Instalación

```bash
# 1. Clonar el repositorio
git clone https://github.com/AoC-Gamers/L4D2-Iptable-Suite.git
cd L4D2-Iptable-Suite

# 2. Configurar archivo de entorno
cp example.env .env
nano .env  # Ajustar configuración según tu servidor

# 3. Aplicar reglas de iptables
sudo ./iptables.rules.sh

# 4. Hacer reglas persistentes
sudo ./ipp.sh

# 5. Configurar sistema de logging
sudo python3 iptable.loggin.py
```

### Configuración Básica

Edita el archivo `.env` según tu configuración:

```bash
# Tipo de servidor (0=Nativo, 1=Docker, 2=Ambos)
TYPECHAIN=0

# Puertos de tu servidor L4D2
GAMESERVERPORTS="27015"
TVSERVERPORTS="27020"

# Protección TCP RCON
ENABLE_TCP_PROTECT=true

# IPs de confianza (acceso completo al sistema - ⚠️ TODOS los puertos)
WHITELISTED_IPS="192.168.1.100 10.0.0.5"
```

> ⚠️ **ADVERTENCIA**: Las IPs en `WHITELISTED_IPS` tendrán acceso **completo e irrestricto** a toda la máquina (SSH, Web, Bases de datos, APIs, etc.). Usar solo para administradores e IPs absolutamente confiables.

## 🛠️ Herramientas Incluidas

### 1. `iptables.rules.sh` - Motor de Protección Principal

Script principal que implementa reglas avanzadas de iptables específicamente diseñadas para mitigar ataques DDoS contra servidores L4D2. Incluye protección contra floods UDP, ataques challenge, validación de paquetes, consultas A2S maliciosas, spam TCP/RCON, consultas Steam y ping floods. 

Soporta configuración flexible para servidores nativos, contenedores Docker o configuraciones híbridas mediante variables de entorno.

**📖 [Documentación Completa](docs/iptables.rules.md)**

---

### 2. `ipp.sh` - Gestor de Persistencia

Herramienta interactiva con menú para gestionar la persistencia de reglas iptables. Permite instalar/desinstalar iptables-persistent, visualizar reglas activas y guardadas, realizar backup y restauración de configuraciones, y diagnosticar el estado del sistema.

Simplifica significativamente la administración de reglas persistentes eliminando la necesidad de recordar comandos complejos de iptables.

**📖 [Documentación Completa](docs/ipp.md)**

---

### 3. `iptable.loggin.py` - Sistema de Análisis

Herramienta avanzada de logging y análisis que configura automáticamente rsyslog para capturar logs de iptables y genera reportes JSON detallados. Proporciona análisis temporal por IP, puerto, día, semana, mes y tipo de ataque, permitiendo identificar patrones maliciosos y tendencias de seguridad.

Incluye detección de 12 tipos específicos de ataques contra servidores L4D2 con categorización por severidad y recomendaciones de mitigación.

**📖 [Documentación Completa](docs/iptable.loggin.md)**

## 🎮 Casos de Uso Específicos

### Servidor Individual L4D2
```bash
# .env configuration
TYPECHAIN=0
GAMESERVERPORTS="27015"
TVSERVERPORTS="27020"
ENABLE_TCP_PROTECT=true
```

### Múltiples Servidores
```bash
# .env configuration
TYPECHAIN=0
GAMESERVERPORTS="27015:27030"  # 16 servidores
TVSERVERPORTS="27115:27130"    # 16 SourceTV
ENABLE_TCP_PROTECT=true
```

### Servidores en Docker
```bash
# .env configuration
TYPECHAIN=1  # Solo Docker
GAMESERVERPORTS="27015:27018"
TCP_DOCKER="80,443"  # Puertos adicionales
SSH_DOCKER="2222"
```

### Configuración Híbrida
```bash
# .env configuration
TYPECHAIN=2  # Nativo + Docker
GAMESERVERPORTS="27015:27020"
TVSERVERPORTS="27115:27120"
TCP_DOCKER="80,443,8080"
ENABLE_TCP_PROTECT=true
```

## 📊 Tipos de Ataques Detectados

El sistema identifica y mitiga los siguientes patrones de ataque:

| Tipo de Ataque | Descripción | Severidad | Impacto |
|---|---|---|---|
| **A2S_INFO_FLOOD** | Flood de consultas de información del servidor | Media | Saturación CPU/Bandwidth |
| **A2S_PLAYERS_FLOOD** | Flood de consultas de lista de jugadores | Media | Mayor consumo de bandwidth |
| **A2S_RULES_FLOOD** | Flood de consultas de variables del servidor | Alta | Respuesta muy grande |
| **L4D2_CONNECT_FLOOD** | Flood de paquetes "connect" | Alta | Bloquea conexiones legítimas |
| **L4D2_RESERVE_FLOOD** | Flood de paquetes "reserve" | Alta | Inestabilidad de lobby |
| **UDP_NEW_LIMIT** | Límite de conexiones UDP nuevas | Baja | Protección preventiva |
| **UDP_EST_LIMIT** | Límite de conexiones UDP establecidas | Media | Afecta jugadores activos |
| **TCP_RCON_BLOCK** | Intentos de acceso RCON malicioso | Alta | Compromiso administrativo |
| **INVALID_SIZE** | Paquetes con tamaños maliciosos | Baja | Consumo CPU |
| **MALFORMED** | Paquetes UDP malformados | Baja | Potencial crash |
| **STEAM_GROUP_FLOOD** | Flood de consultas Steam | Media | Recursos Steam API |
| **ICMP_FLOOD** | Ping flood | Baja | Degradación de red |

## 📈 Flujo de Trabajo Recomendado

### 1. Instalación Inicial
```bash
# Configurar reglas básicas
sudo ./iptables.rules.sh

# Hacer persistentes
sudo ./ipp.sh  # Opción 1: Install, Opción 5: Save

# Configurar logging
sudo python3 iptable.loggin.py  # Opción 1: Install rsyslog
```

### 2. Monitoreo Regular
```bash
# Generar reportes semanales
sudo python3 iptable.loggin.py  # Opción 4: Analyze logs

# Verificar estado de reglas
sudo ./ipp.sh  # Opción 9: Status
```

### 3. Mantenimiento
```bash
# Actualizar configuración
nano .env
sudo ./iptables.rules.sh  # Reaplicar reglas
sudo ./ipp.sh  # Opción 5: Save rules

# Limpiar logs antiguos
sudo logrotate -f /etc/logrotate.d/l4d2-iptables
```

## 📚 Documentación Completa

- **[📖 iptables.rules.sh](docs/iptables.rules.md)** - Documentación técnica del motor de protección
- **[📖 ipp.sh](docs/ipp.md)** - Guía del gestor de persistencia
- **[📖 iptable.loggin.py](docs/iptable.loggin.md)** - Manual del sistema de análisis
- **[📋 example.env](example.env)** - Archivo de configuración de ejemplo
- **[📊 summary_example/](summary_example/)** - Ejemplos de reportes JSON

## 🤝 Créditos y Reconocimientos

Este proyecto está basado en el trabajo original de **SirPlease** y su repositorio [IPTables](https://github.com/SirPlease/IPTables). La suite L4D2 IPTables incluye modificaciones significativas, nuevas funcionalidades y herramientas complementarias desarrolladas por la comunidad **AoC-Gamers**.

### Contribuidores de la Suite
- **[SirPlease](http://steamcommunity.com/profiles/76561198004878749)** - Creador del script base de iptables para L4D2
- **[AoC-Gamers](https://steamcommunity.com/groups/aoc-gamer)** - Desarrollo de herramientas complementarias y mejoras
- **[Sheo](http://steamcommunity.com/profiles/76561198034909367)** - Por sus aportes para el bloqueo de ataques A2S.
- Comunidad L4D2 - Testing y feedback

---

<div align="center">

**¿Te ha sido útil esta suite? ⭐ ¡Dale una estrella al repositorio!**

*Desarrollado para la comunidad de Left 4 Dead 2*

</div>
