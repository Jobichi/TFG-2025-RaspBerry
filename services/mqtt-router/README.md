# Especificación de la arquitectura MQTT

## 1. Visión general

La comunicación entre los dispositivos **ESP32**, el **router MQTT** (Raspberry Pi) y los **microservicios** del sistema se realiza mediante el protocolo **MQTT**.
El sistema está dividido en **dos dominios lógicos**:

| Dominio | Participantes | Propósito |
|----------|----------------|------------|
| **System** | Microservicios ↔ `mqtt-router` | Comunicaciones internas, consultas a la base de datos y solicitudes de información estructurada. |
| **Field** | `mqtt-router` ↔ ESP32 | Intercambio directo con los dispositivos físicos (sensores y actuadores). |

## 2. Dominio `system/#`

Todos los mensajes de este dominio usan la forma general:

```bash
system/<acción>/<servicio_origen>
```

Ejemplos:

```bash
system/select/intent-service
system/get/telegram-service
system/response/intent-service/actuators/esp32_cocina/0
```

### 2.1 Tipos de acción

| Acción | Descripción | Fuente de datos | Destino |
|--------|--------------|-----------------|----------|
| `select` | Consulta persistente sobre la base de datos MariaDB. | BBDD | `mqtt-router` |
| `get` | Lectura de datos en tiempo real desde un dispositivo físico (router → ESP32). | Dispositivo físico | `mqtt-router` |
| `response` | Respuesta del router o dispositivo hacia el microservicio que solicitó la operación. | Router / ESP32 | Microservicio destino |
| `alert` | Notificaciones críticas o eventos del sistema. | Router / ESP32 | Microservicios interesados |

---

## 3. Formatos `system/select/#`

### 3.1 Consulta de datos específicos

**Topic:**

```bash
system/select/<servicio>
```

**Payload:**

```json
{
  "request": "actuators",
  "device": "esp32_cocina",
  "id": 0
}
```

Respuesta (por cada registro):

```bash
system/response/<servicio>/actuators/<device>/<id>
```

Payload:

```json
{
  "id": 0,
  "device_name": "esp32_cocina",
  "name": "LuzPrincipal",
  "location": "salon",
  "state": "OFF"
}
```

### 3.2 Consulta global de dispositivos (`"device": "all"`)

Respuesta:
El router publicará todos los sensores y actuadores disponibles en la base de datos, cada uno en su tópico correspondiente:

```bash
system/response/<servicio>/sensors/<device>/<id>
system/response/<servicio>/actuators/<device>/<id>
system/response/<servicio>/alerts/<id>
```

## 4. Formatos `system/get/#`

**Topic:**

```bash
system/get/<servicio>
```

**Payload:**

```json
{
  "device": "esp32_cocina",
  "type": "sensor",
  "id": 1
}
```

El router valida la existencia del componente en la base de datos y redirige la solicitud al dispositivo correspondiente:

```bash
get/esp32_cocina/sensor/1
```

Payload reenviado:

```bash
{
  "requester": "intent-service"
}
```

Respuesta del ESP32:

```bash
response/esp32_cocina/sensor/1
```

Payload:

```json
{
  "value": 22.8,
  "unit": "°C",
  "requester": "intent-service"
}
```

Respuesta final del router:

```bash
system/response/intent-service/sensor/esp32_cocina/1
```

Payload:

```bash
{
  "value": 22.8,
  "unit": "°C"
}
```

## Dominio `Field` (nivel ESP32)

Los tópicos de este dominio son utilizados para la comunicación directa entre el rotuer y los ESP32.
El nombre del dispositivo forma parte del tópico.

| Tipo | Dirección | Descripción |
|------|------------|-------------|
| `announce/#` | ESP32 → Router | Publicación inicial o periódica con metadatos de los sensores/actuadores. |
| `update/#` | ESP32 → Router | Cambio de estado o lectura periódica. |
| `alert/#` | ESP32 → Router | Condiciones anómalas o alertas de hardware. |
| `get/#` | Router → ESP32 | Solicitud de lectura en tiempo real. |
| `response/#` | ESP32 → Router | Respuesta a una petición `get/#`. |
| `set/#` | Router → ESP32 | Orden directa para modificar el estado de un actuador. |

## 6. Formatos de tópicos `Field`

### 6.1 `announce/<device>/<type>/<id>`

Publicación inicial o de sincronización periódica.

Payload:

```json
{
  "name": "LuzPrincipal",
  "location": "salon",
  "state": "OFF"
}
```

### 6.2 `update/<device>/<type>/<id>`

Cambio de estado o valor medido.

Payload:

```json
{
  "value": 22.5,
  "unit": "°C"
}
```

### 6.3 `alert/<device>/<type>/<id>`

Alerta de hardware o sensor.

Payload:

```json
{
  "state": "ALERT",
  "message": "Temperatura fuera de rango"
}
```

### 6.4 `get/<device>/<type>/<id>`

Solicitud de lectura en tiempo real desde el router.

Payload:

```json
{
  "requester": "intent-service"
}
```

### 6.5 `response/<device>/<type>/<id>`

Respuesta del dispositivo a una solicitud `get/#`.

```json
{
  "value": 22.8,
  "unit": "°C",
  "requester": "intent-service"
}
```

### 6.6 `set/<device>/<type>/<id>`

Comando de cambio de estado (router → ESP32).

```json
{
  "state": "ON"
}
```

## 7. Estructura común de los payloads

| Campo | Tipo | Obligatorio | Descripción |
|--------|------|--------------|--------------|
| `device` | string | ✅ (solo en system-level) | Nombre del dispositivo ESP32. |
| `type` | string | ✅ | “sensor” o “actuator”. |
| `id` | int | ✅ | Identificador interno del componente. |
| `name` | string | Opcional | Nombre lógico (solo en announce). |
| `location` | string | Opcional | Ubicación física (solo en announce). |
| `state` / `value` | variable | ✅ según tipo | Valor actual o estado. |
| `unit` | string | Opcional | Unidad de medida (°C, %, etc.). |
| `requester` | string | Opcional | Nombre del microservicio solicitante. |
| `timestamp` | string | Opcional | Fecha y hora del envío. |

## 8. Reglas generales

- Todos los mensajes usan JSON UTF-8 válido.
- Se emplea nomenclatura en snake_case para consistencia.
- El `mqtt-roouter`:
    - Gestiona todos los accesos a la BBDD.
    - Valida la existencia de dispositivos y componentes.
    - Redirige las peticiones de tiempo real (`system/get`) al hardware físico.
- Los ESP32:
    - Solo publican bajo `announce`, `update`, `alert` y `response`.
    - Solo se suscriben a `get/#`, `set/#` y `pong/#`.

###

# Flujo interno del `mqtt-router`

El `mqtt-router` actúa como **punto central de enrutamiento y control** entre los microservicios internos y los dispositivos físicos (ESP32).
Todos los mensajes MQTT pasan por él, garantizando coherencia entre la **base de datos**, el **hardware** y los **servicios lógicos** del sistema.

---

## 1. Flujo general de comunicaciones

```text
┌────────────────────────────┐
│        Microservicios      │
│  (Intent, Asterisk,        │
│   Telegram, Dashboard...)  │
└──────────────┬─────────────┘
               │
               │ Mensajes internos (dominio system/#)
               │
               ▼
       ┌──────────────────────────┐
       │        MQTT Router       │
       │  (Handlers + DB Manager) │
       │                          │
       │  ┌────────────────────┐  │
       │  │ system/select/#    │◄─┤─── Consultas persistentes (SELECT)
       │  │ system/get/#       │◄─┤─── Peticiones en tiempo real
       │  │ system/set/#       │◄─┤─── Comandos a dispositivos
       │  │ response/#         │◄─┤─── Respuestas de lectura
       │  │ announce/#         │◄─┤─── Registro inicial ESP32
       │  │ update/#           │◄─┤─── Cambios de estado o valor
       │  │ alert/#            │◄─┤─── Notificaciones de alerta
       │  └────────────────────┘  │
       │                          │
       │  Base de datos MariaDB   │
       │  ─────────────────────── │
       │  devices / sensors /     │
       │  actuators / alerts      │
       └────────────┬─────────────┘
                    │
                    │ Mensajes físicos (dominio directo)
                    │
                    ▼
         ┌────────────────────────────┐
         │         ESP32 Nodes        │
         │  (Sensores / Actuadores)   │
         │                            │
         │  Publican:                 │
         │   - announce/<dev>/<t>/<id>│
         │   - update/<dev>/<t>/<id>  │
         │   - alert/<dev>/<t>/<id>   │
         │   - response/<dev>/<t>/<id>│
         │                            │
         │  Reciben:                  │
         │   - set/<dev>/<t>/<id>     │
         │   - get/<dev>/<t>/<id>     │
         └────────────────────────────┘
```

El router se comunica mediante los **topics `system/#`** con los microservicios,
y mediante los **topics directos (`announce/#`, `update/#`, `set/#`, `get/#`, `response/#`, `alert/#`)** con los ESP32.

---

## 2. Flujo de mensajes **de entrada desde ESP32**

| Topic recibido | Handler | Acción principal | Acceso DB | Publicaciones derivadas |
|----------------|----------|------------------|------------|--------------------------|
| `announce/<device>/<type>/<id>` | `announce_handler` | Registra o actualiza sensores y actuadores. | ✅ Inserta / actualiza | `system/notify/<device>/announce` |
| `update/<device>/<type>/<id>` | `update_handler` | Actualiza valor/estado de componentes. | ✅ Actualiza | `system/notify/<device>/update` |
| `alert/<device>/<type>/<id>` | `alert_handler` | Inserta alerta y notifica. | ✅ Inserta | `system/notify/alert` |
| `response/<device>/<type>/<id>` | `response_handler` | Actualiza DB y reenvía lectura a requester. | ✅ Actualiza | `system/response/<servicio>/...` |

---

## 3. Flujo de mensajes **de entrada desde microservicios**

| Topic recibido | Handler | Función | Acceso DB | Publicaciones derivadas |
|----------------|----------|----------|------------|--------------------------|
| `system/select/<servicio>` | `system_select_handler` | Consulta la BBDD (lectura persistente). | ✅ SELECT | `system/response/<servicio>/...` |
| `system/get/<servicio>` | `system_get_handler` | Solicita datos en tiempo real. | ✅ Valida | `get/<device>/<type>/<id>` |
| `system/set/<servicio>` | `system_set_handler` | Ordena cambio de estado físico. | ✅ Actualiza (actuadores) | `set/<device>/<type>/<id>` |

---

## 4. Flujo completo de lectura en tiempo real (`system/get`)

```text
┌────────────────────┐
│ intent-service     │
│ (u otro servicio)  │
└────────┬───────────┘
         │
         │ system/get/<servicio>
         ▼
┌─────────────────────┐
│ mqtt-router         │
│ (system_get_handler)│
│ - Valida en DB      │
│ - Reenvía petición  │
└────────┬────────────┘
         │
         │ get/<device>/<type>/<id>
         ▼
┌────────────────────┐
│ ESP32              │
│ - Lee sensor       │
│ - Publica respuesta│
└────────┬───────────┘
         │
         │ response/<device>/<type>/<id>
         ▼
┌────────────────────┐
│ mqtt-router        │
│ (response_handler) │
│ - Actualiza DB     │
│ - Reenvía lectura  │
└────────┬───────────┘
         │
         │ system/response/<servicio>/sensor/<device>/<id>
         ▼
┌─────────────────────┐
│ Servicio solicitante│
│ recibe el valor     │
└─────────────────────┘
```

---

## 🔄 5. Flujo completo de cambio de estado (`system/set`)

```text
┌────────────────────┐
│ asterisk-service   │
│ o intent-service   │
└────────┬───────────┘
         │
         │ system/set/<servicio>
         ▼
┌────────────────────┐
│ mqtt-router        │
│ (system_set_handler)│
│ - Valida en DB     │
│ - Reenvía orden    │
└────────┬───────────┘
         │
         │ set/<device>/<type>/<id>
         ▼
┌────────────────────┐
│ ESP32              │
│ - Ejecuta acción   │
│ - Publica confirm. │
└────────┬───────────┘
         │
         │ update/<device>/<type>/<id>
         ▼
┌────────────────────┐
│ mqtt-router        │
│ (update_handler)   │
│ - Actualiza DB     │
│ - Notifica cambio  │
└────────┬───────────┘
         │
         │ system/notify/<device>/update
         ▼
┌────────────────────┐
│ Otros servicios    │
│ (ej. Telegram)     │
│ reciben evento     │
└────────────────────┘
```

---

## ⚙️ 6. Flujo de registro inicial (`announce`)

```text
ESP32 ──► announce/<device>/<type>/<id>
│
▼
mqtt-router (announce_handler)
```

- Inserta/actualiza dispositivo en DB
- Marca last_seen
- Publica confirmación: system/notify/<device>/announce

---

## 7. Acceso a la base de datos

| Operación | Handlers que la realizan | Tipo |
|------------|--------------------------|-------|
| `INSERT / UPDATE devices` | announce, update, alert | Escritura |
| `INSERT / UPDATE sensors` | announce, update, response | Escritura |
| `INSERT / UPDATE actuators` | announce, update, response, set | Escritura |
| `INSERT alerts` | alert | Escritura |
| `SELECT *` | system_select, system_get (validación) | Lectura |

---

## 8. Flujo de notificaciones internas

El router emite notificaciones para que otros servicios puedan reaccionar:

| Topic | Descripción | Generado por |
|--------|--------------|--------------|
| `system/notify/<device>/announce` | Confirmación de registro o reconexión. | announce_handler |
| `system/notify/<device>/update` | Cambio o lectura de valor. | update_handler |
| `system/notify/alert` | Nueva alerta registrada. | alert_handler |
| `system/notify/set` | Acción ejecutada por un microservicio. | system_set_handler |

---

**Resumen:**
- Todos los flujos físicos (`announce`, `update`, `alert`, `response`) parten de los ESP32.
- Todos los flujos lógicos (`system/select`, `system/get`, `system/set`) parten de microservicios internos.
- El `mqtt-router` centraliza y sincroniza ambos mundos mediante la base de datos y las notificaciones.
