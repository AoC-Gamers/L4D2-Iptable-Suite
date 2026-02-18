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
- ⚖️ **Doble Backend**: Soporte modular para `iptables` (legacy) y `nftables` (modern)
- 🐳 **Soporte Docker**: Compatibilidad completa con servidores nativos y contenedores
- 🔐 **Soporte OpenVPN**: Acceso remoto seguro (host o Docker) sin afectar reglas de juego
- 📊 **Sistema de Logging**: Análisis detallado de ataques con reportes JSON comprehensivos
- ⚙️ **Gestión Simplificada**: Herramientas intuitivas para administrar reglas persistentes
- 🎯 **Detección Inteligente**: Identificación de patrones específicos de ataques Source Engine
- 📈 **Análisis Temporal**: Reportes por IP, puerto, día, semana, mes y tipo de ataque

## 🚀 Instalación Rápida

### Requisitos Previos

- **Sistema**: Linux (Ubuntu 18.04+, Debian 9+, CentOS 7+)
- **Permisos**: Acceso root/sudo
- **Dependencias**: Python 3.6+, iptables, rsyslog

### Bibliotecas/paquetes requeridos (Debian/Ubuntu)

Instala primero los paquetes base del sistema:

```bash
sudo apt update
sudo apt install -y \
  iptables \
  nftables \
  rsyslog \
  python3 \
  python3-pip \
  python3-venv
```

Instala luego las librerías de Python del analizador:

```bash
python3 -m pip install -r requirements.txt
```

Opcional (recomendado, para aislar dependencias):

```bash
./venv.loggin.sh
```

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

# 3b. (Opcional) Aplicar reglas con backend nftables
sudo ./nftables.rules.sh

# 4. Hacer reglas persistentes
sudo ./ipp.sh

# 5. Configurar entorno Python (Opcional - Recomendado)
chmod +x venv.loggin.sh
./venv.loggin.sh
# Seleccionar opción 1: Instalar entorno virtual

# 6. Configurar sistema de logging
# Método A: Con entorno virtual (recomendado)
./venv.loggin.sh
# Seleccionar opción 6: Run iptable.loggin.py script

# Método B: Ejecución directa
sudo python3 iptable.loggin.py
```

### Configuración Básica

Edita el archivo `.env` según tu configuración:

```bash
# Tipo de servidor (0=Nativo, 1=Docker, 2=Ambos)
TYPECHAIN=0

# Puertos de tu servidor L4D2
L4D2_GAMESERVER_PORTS="27015"
L4D2_TV_PORTS="27020"

# Protección TCP RCON
ENABLE_L4D2_TCP_PROTECT=true

# SSH: no exponer públicamente cuando sea true
SSH_PORT="2222,22220:22229"
SSH_REQUIRE_WHITELIST=true

# IPs de confianza (acceso completo al sistema - ⚠️ TODOS los puertos)
WHITELISTED_IPS="198.51.100.10 203.0.113.5"
WHITELISTED_DOMAINS="admin-gateway.example.net"

# OpenVPN (host o Docker)
# Se configura solo si incluyes el módulo ip_openvpn/nf_openvpn
VPN_PORT=1194
VPN_PROTO="udp"
VPN_SUBNET="10.8.0.0/24"
VPN_INTERFACE="tun0"  # o "tun+" para múltiples
VPN_DOCKER_INTERFACE="docker0"  # opcional para OpenVPN en Docker
VPN_LAN_SUBNET="192.168.1.0/24"
VPN_LAN_INTERFACE="enp3s0"  # requerido si VPN_ENABLE_NAT=true
VPN_ENABLE_NAT=false

# (Opcional) Alias del router/LAN vía VPN (DNAT) para evitar conflictos de subred en el cliente
# Útil si el cliente VPN está en una red que también usa 192.168.1.0/24 y no puede acceder a 192.168.1.1.
# Ejemplo: http://10.99.1.1  ->  Router real: 192.168.1.1
# Si cualquiera de las variables está vacía, NO se crea el alias.
VPN_ROUTER_REAL_IP=""
VPN_ROUTER_ALIAS_IP=""

VPN_LOG_ENABLED=false
VPN_LOG_PREFIX="VPN_TRAFFIC: "

# Puertos extra permitidos (servicios adicionales)
# Formato: "puerto,puerto" o rangos "inicio:fin" (multiport)
# Vacío = no agrega excepciones extras.
UDP_ALLOW_PORTS=""
TCP_ALLOW_PORTS=""

Nota Docker: esta suite usa directamente la cadena `DOCKER-USER` en `filter` para las reglas del usuario, siguiendo el flujo recomendado por Docker.
```

Asistente rápido de configuración (`.env` guiado):

```bash
./configure-env.sh
```

> ⚠️ **ADVERTENCIA**: Las entradas de `WHITELISTED_IPS` y `WHITELISTED_DOMAINS` tendrán acceso **completo e irrestricto** a toda la máquina (SSH, Web, Bases de datos, APIs, etc.). Usar solo para administradores y orígenes absolutamente confiables.

## 🛠️ Herramientas Incluidas

### 1. `iptables.rules.sh` - Motor de Protección Principal

Script principal que implementa reglas avanzadas de iptables específicamente diseñadas para mitigar ataques DDoS contra servidores L4D2. Incluye protección contra floods UDP, ataques challenge, validación de paquetes, consultas A2S maliciosas, spam TCP/RCON, consultas Steam Group y ping floods. 

Soporta configuración flexible para servidores nativos, contenedores Docker o configuraciones híbridas mediante variables de entorno.

**📖 [Documentación Completa](docs/iptables.rules.md)**

---

### 1b. `nftables.rules.sh` - Backend Moderno

Entrypoint equivalente para aplicar protección usando `nftables` con la misma filosofía modular y configuración compartida por `.env`.

Ideal para entornos modernos que ya operan con reglas `nft` y desean mantener paridad funcional con el flujo legacy.

**📖 [Arquitectura Modular](docs/modular-loader-architecture.md)**

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

---

### 4. `venv.loggin.sh` - Gestor de Entorno Virtual

Sistema avanzado de gestión de entorno virtual Python con interfaz interactiva de 8 opciones. Facilita la instalación, configuración y uso de `iptable.loggin.py` mediante aislamiento de dependencias y compatibilidad multiplataforma.

**Características principales:**
- 🖥️ **Compatibilidad multiplataforma**: Windows, Linux, macOS
- 🔧 **Instalación automática**: Crea y configura el entorno virtual automáticamente
- 🐍 **Ejecución inteligente**: Maneja sudo automáticamente en Linux, sin sudo en Windows
- 📊 **Verificación completa**: Confirma dependencias y archivos antes de ejecutar
- 🎯 **Uso directo**: Opción 6 ejecuta el script sin activación manual del entorno

**Menú interactivo:**
```
Available options:
  1. 🔧 Install virtual environment
  2. ▶️  Activate virtual environment  
  3. ⏹️  Deactivate virtual environment
  4. 📊 Check environment status
  5. 🔄 Reinstall dependencies
  6. 🐍 Run iptable.loggin.py script
  7. ❓ Help
  8. 🚪 Exit
```

**📖 [Documentación Completa](docs/venv.loggin.md)**

---

### 5. Tooling de Modularidad

- **Smoke tests modulares**: `tests/smoke-modules.sh`
  - Verifica contrato mínimo por módulo y ejecuta `--dry-run` de ambos backends si hay privilegios/dependencias.

Comando rápido:

```bash
./tests/smoke-modules.sh
```

---

## 🎮 Casos de Uso Específicos

### Servidor Individual L4D2
```bash
# .env configuration
TYPECHAIN=0
L4D2_GAMESERVER_PORTS="27015"
L4D2_TV_PORTS="27020"
ENABLE_L4D2_TCP_PROTECT=true
```

### Múltiples Servidores
```bash
# .env configuration
TYPECHAIN=0
L4D2_GAMESERVER_PORTS="27015:27030"  # 16 servidores
L4D2_TV_PORTS="27115:27130"          # 16 SourceTV
ENABLE_L4D2_TCP_PROTECT=true
```

### Servidores en Docker
```bash
# .env configuration
TYPECHAIN=1  # Solo Docker
L4D2_GAMESERVER_PORTS="27015:27018"
TCP_DOCKER="80,443"  # Puertos adicionales
SSH_DOCKER="2222"
```

### Configuración Híbrida
```bash
# .env configuration
TYPECHAIN=2  # Nativo + Docker
L4D2_GAMESERVER_PORTS="27015:27020"
L4D2_TV_PORTS="27115:27120"
TCP_DOCKER="80,443,8080"
ENABLE_L4D2_TCP_PROTECT=true
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

### Backends de Firewall

```bash
# Legacy (iptables)
sudo ./iptables.rules.sh

# Modern (nftables)
sudo ./nftables.rules.sh
```

### Estructura modular actual

```text
modules/
├─ common_loader.sh
├─ preload.sh
├─ postload.sh
├─ common_nft.sh
├─ ip/   # módulos ip_*.sh
└─ nf/   # módulos nf_*.sh
```

### 1. Instalación Inicial
```bash
# Configurar reglas básicas
sudo ./iptables.rules.sh

# Hacer persistentes
sudo ./ipp.sh  # Opción 1: Install, Opción 5: Save

# Configurar logging con entorno virtual (recomendado)
./venv.loggin.sh  # Opción 1: Install, Opción 6: Run script

# O configurar logging directamente
sudo python3 iptable.loggin.py  # Opción 1: Install rsyslog
```

### 2. Monitoreo Regular
```bash
# Generar reportes semanales con entorno virtual
./venv.loggin.sh  # Opción 6: Run script, Opción 4: Analyze logs

# O generar reportes directamente
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
- **[📖 nftables.rules.sh](docs/modular-loader-architecture.md)** - Arquitectura y operación del backend moderno
- **[📖 Arquitectura Modular](docs/modular-loader-architecture.md)** - Contrato de módulos, paridad y validación
- **[📖 ipp.sh](docs/ipp.md)** - Guía del gestor de persistencia
- **[📖 iptable.loggin.py](docs/iptable.loggin.md)** - Manual del sistema de análisis
- **[📖 venv.loggin.sh](docs/venv.loggin.md)** - Guía del gestor de entorno virtual
- **[📋 example.env](example.env)** - Archivo de configuración de ejemplo  
- **[📊 summary_example/](summary_example/)** - Ejemplos de reportes JSON
- **[📚 Documentación de Módulos](docs/modules/README.md)** - Índice con descripciones breves de cada módulo

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
