import os
import json
import logging
import asyncio
import time
import paho.mqtt.client as mqtt
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# === CONFIGURACIÓN MEJORADA ===
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_API_KEY")
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "admin")
MQTT_PASS = os.getenv("MQTT_PASS", "admin1234")

mqtt_client = None
device_cache = {"sensors": {}, "actuators": {}}
user_sessions = {}

# === EMOJIS Y CONSTANTES VISUALES ===
EMOJIS = {
    "sensors": "📟",
    "actuators": "⚙️",
    "alerts": "⚠️",
    "back": "⬅️",
    "refresh": "🔄",
    "home": "🏠",
    "loading": "⏳",
    "success": "✅",
    "error": "❌",
    "info": "ℹ️",
    "warning": "⚠️"
}

# === FUNCIONES AUXILIARES MEJORADAS ===
def escape_markdown(text):
    """Escape caracteres especiales de Markdown para evitar errores de parseo"""
    if not text:
        return ""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(['\\' + char if char in escape_chars else char for char in str(text)])

def build_main_keyboard():
    """Teclado principal con mejor distribución visual"""
    keyboard = [
        [f"{EMOJIS['sensors']} Sensores", f"{EMOJIS['actuators']} Actuadores"],
        [f"{EMOJIS['alerts']} Alertas", f"{EMOJIS['refresh']} Actualizar"],
        [f"{EMOJIS['info']} Ayuda", f"{EMOJIS['home']} Menú principal"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def build_device_menu(req_type, user_id=None):
    """Menú de dispositivos con estado visual"""
    devices = list(device_cache[req_type].keys())
    
    if not devices:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{EMOJIS['refresh']} Actualizar", callback_data=f"refresh|{req_type}")],
            [InlineKeyboardButton(f"{EMOJIS['back']} Volver", callback_data="main_menu")]
        ])
    
    keyboard = []
    for dev in devices:
        components = device_cache[req_type].get(dev, [])
        status_emoji = "🟢" if components else "⚫"
        button_text = f"{status_emoji} {dev} ({len(components)})"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"device|{req_type}|{dev}")])
    
    keyboard.append([InlineKeyboardButton(f"{EMOJIS['refresh']} Actualizar", callback_data=f"refresh|{req_type}")])
    keyboard.append([InlineKeyboardButton(f"{EMOJIS['back']} Volver", callback_data="main_menu")])
    
    return InlineKeyboardMarkup(keyboard)

def build_component_menu(req_type, device, user_id=None):
    """Submenú de componentes con información de estado"""
    items = device_cache[req_type].get(device, [])
    
    if not items:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(f"{EMOJIS['refresh']} Actualizar", callback_data=f"refresh_component|{req_type}|{device}")],
            [InlineKeyboardButton(f"{EMOJIS['back']} Atrás", callback_data=f"back|{req_type}")]
        ])
    
    keyboard = []
    for item in items:
        state_emoji = "📊" if req_type == "sensors" else "🔘"
        button_text = f"{state_emoji} {item['name']}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"component|{req_type}|{device}|{item['id']}")])
    
    keyboard.append([
        InlineKeyboardButton(f"{EMOJIS['refresh']} Actualizar", callback_data=f"refresh_component|{req_type}|{device}"),
        InlineKeyboardButton(f"{EMOJIS['back']} Atrás", callback_data=f"back|{req_type}")
    ])
    
    return InlineKeyboardMarkup(keyboard)

# === GESTIÓN DE SESIONES DE USUARIO ===
def get_user_session(user_id):
    """Obtiene o crea sesión de usuario"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "last_action": time.time(),
            "message_history": [],
            "pending_requests": set()
        }
    return user_sessions[user_id]

def update_user_session(user_id, action=None):
    """Actualiza la sesión del usuario"""
    session = get_user_session(user_id)
    session["last_action"] = time.time()
    if action:
        session["message_history"].append((action, time.time()))

# === COMANDOS MEJORADOS ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando de inicio mejorado con bienvenida personalizada"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    logger.info(f"[TELEGRAM] Usuario {user.first_name} ({user.id}) conectado")

    app = context.application
    if "active_chats" not in app.bot_data:
        app.bot_data["active_chats"] = set()
    app.bot_data["active_chats"].add(chat_id)
    
    update_user_session(user.id, "start")

    welcome_text = f"""
🤖 *¡Bienvenido {escape_markdown(user.first_name)}\!*

*Sistema de Monitoreo Inteligente*

📊 *Sensores:* Consulta estados en tiempo real
⚙️ *Actuadores:* Controla dispositivos remotos
⚠️ *Alertas:* Notificaciones automáticas

Selecciona una opción del menú:
"""

    reply_markup = build_main_keyboard()
    
    if context.user_data.get("welcome_message_id"):
        try:
            await context.bot.delete_message(chat_id, context.user_data["welcome_message_id"])
        except:
            pass
    
    message = await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode="MarkdownV2"
    )
    
    context.user_data["welcome_message_id"] = message.message_id

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando de ayuda expandido"""
    help_text = """
*📖 Guía de Uso Rápido*

*🔍 Consultar Sensores:*
• Selecciona "📟 Sensores"
• Elige un dispositivo
• Selecciona el sensor específico

*⚙️ Gestionar Actuadores:*
• Selecciona "⚙️ Actuadores" 
• Elige un dispositivo
• Controla componentes individuales

*⚠️ Sistema de Alertas:*
• Alertas automáticas en tiempo real
• Historial de eventos importantes

*🔄 Actualizar Datos:*
• Usa "🔄 Actualizar" para refrescar listas
• Los datos se cachean para mejor rendimiento

*💡 Consejos:*
• Usa el menú principal para navegación rápida
• Las alertas llegan automáticamente
• Estado visual con emojis de colores
"""

    await update.message.reply_text(help_text, parse_mode="Markdown")

# === MANEJO MEJORADO DEL MENÚ ===
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejo mejorado de opciones del menú con feedback visual"""
    user = update.effective_user
    text = update.message.text.lower().strip()
    
    logger.info(f"[TELEGRAM] Usuario {user.id} seleccionó: {text}")
    update_user_session(user.id, f"menu_{text}")

    if "sensor" in text or "📟" in text:
        await handle_sensors_request(update, context)
    elif "actuador" in text or "⚙️" in text:
        await handle_actuators_request(update, context)
    elif "alerta" in text or "⚠️" in text:
        await handle_alerts_request(update, context)
    elif "actualizar" in text or "🔄" in text:
        await handle_refresh_request(update, context)
    elif "ayuda" in text or "ℹ️" in text:
        await help_command(update, context)
    elif "menú" in text or "🏠" in text:
        await start(update, context)
    else:
        await update.message.reply_text(
            f"{EMOJIS['error']} Opción no reconocida. Usa los botones del menú.",
            reply_markup=build_main_keyboard()
        )

async def handle_sensors_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejo mejorado de petición de sensores"""
    user = update.effective_user
    user_session = get_user_session(user.id)
    
    if not device_cache["sensors"]:
        loading_msg = await update.message.reply_text(
            f"{EMOJIS['loading']} Consultando sensores disponibles..."
        )
        user_session["pending_requests"].add("sensors")
        
        mqtt_client.publish("system/get/telegram", json.dumps({"request": "sensors"}))
        
        await asyncio.sleep(3)
        if device_cache["sensors"]:
            await loading_msg.delete()
            menu = build_device_menu("sensors", user.id)
            await update.message.reply_text(
                f"{EMOJIS['sensors']} Sensores Detectados:",
                reply_markup=menu,
                parse_mode="Markdown",
            )
        else:
            await loading_msg.edit_text(
                f"{EMOJIS['warning']} No se encontraron sensores. Reintentando..."
            )
    else:
        menu = build_device_menu("sensors", user.id)
        await update.message.reply_text(
            f"{EMOJIS['sensors']} Sensores Disponibles:",
            reply_markup=menu,
            parse_mode="Markdown",
        )

async def handle_actuators_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejo mejorado de petición de actuadores"""
    user = update.effective_user
    user_session = get_user_session(user.id)
    
    if not device_cache["actuators"]:
        loading_msg = await update.message.reply_text(
            f"{EMOJIS['loading']} Consultando actuadores disponibles..."
        )
        user_session["pending_requests"].add("actuators")
        
        mqtt_client.publish("system/get/telegram", json.dumps({"request": "actuators"}))
        
        await asyncio.sleep(3)
        if device_cache["actuators"]:
            await loading_msg.delete()
            menu = build_device_menu("actuators", user.id)
            await update.message.reply_text(
                f"{EMOJIS['actuators']} Actuadores Detectados:",
                reply_markup=menu,
                parse_mode="Markdown",
            )
        else:
            await loading_msg.edit_text(
                f"{EMOJIS['warning']} No se encontraron actuadores. Reintentando..."
            )
    else:
        menu = build_device_menu("actuators", user.id)
        await update.message.reply_text(
            f"{EMOJIS['actuators']} Actuadores Disponibles:",
            reply_markup=menu,
            parse_mode="Markdown",
        )

async def handle_alerts_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejo mejorado de petición de alertas"""
    user = update.effective_user
    loading_msg = await update.message.reply_text(
        f"{EMOJIS['loading']} Consultando estado del sistema y alertas..."
    )
    
    mqtt_client.publish("system/get/telegram", json.dumps({"request": "alerts"}))
    
    await asyncio.sleep(2)
    await loading_msg.edit_text(
        f"{EMOJIS['alerts']} *Sistema de Alertas*\n\n"
        "Las alertas se mostrarán automáticamente cuando ocurran eventos importantes. "
        "Puedes continuar usando el sistema normalmente."
    )

async def handle_refresh_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Actualización completa del sistema"""
    user = update.effective_user
    loading_msg = await update.message.reply_text(
        f"{EMOJIS['refresh']} Actualizando inventario del sistema..."
    )
    
    device_cache["sensors"].clear()
    device_cache["actuators"].clear()
    
    mqtt_client.publish("system/get/telegram", json.dumps({"request": "sensors"}))
    mqtt_client.publish("system/get/telegram", json.dumps({"request": "actuators"}))
    
    await asyncio.sleep(3)
    await loading_msg.edit_text(
        f"{EMOJIS['success']} *Sistema Actualizado*\n\n"
        f"• Sensores: {len(device_cache['sensors'])} dispositivos\n"
        f"• Actuadores: {len(device_cache['actuators'])} dispositivos\n"
        "Los menús han sido refrescados con la información más reciente."
    )

# === CALLBACKS MEJORADOS Y CORREGIDOS ===
async def handle_submenu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manejo mejorado de callbacks con control de errores y sin conflictos Markdown."""
    query = update.callback_query
    user = query.from_user

    await query.answer()
    choice = query.data
    logger.info(f"[TELEGRAM] Callback de {user.id}: {choice}")

    update_user_session(user.id, f"callback_{choice}")

    try:
        # --- Actualizar dispositivos ---
        if choice.startswith("refresh|"):
            _, req_type = choice.split("|", 1)
            device_cache[req_type].clear()
            mqtt_client.publish("system/get/telegram", json.dumps({"request": req_type}))
            await query.edit_message_text(f"{EMOJIS['loading']} Actualizando {req_type}...")
            return

        # --- Actualizar componentes específicos ---
        elif choice.startswith("refresh_component|"):
            _, req_type, device = choice.split("|", 2)
            if device in device_cache[req_type]:
                device_cache[req_type][device] = []
            mqtt_client.publish("system/get/telegram", json.dumps({"request": req_type, "device": device}))
            await query.edit_message_text(f"{EMOJIS['loading']} Actualizando componentes de {device}...")
            return

        # --- Submenú de dispositivos ---
        elif choice.startswith("device|"):
            _, req_type, device = choice.split("|", 2)
            menu = build_component_menu(req_type, device, user.id)
            emoji = EMOJIS.get(req_type, "📋")

            # Mostrar texto sin Markdown problemático
            await query.edit_message_text(
                f"{emoji} {device} ({req_type})",
                reply_markup=menu
            )

        # --- Volver atrás ---
        elif choice.startswith("back|"):
            _, req_type = choice.split("|", 1)
            menu = build_device_menu(req_type, user.id)
            emoji = EMOJIS.get(req_type, "📋")
            await query.edit_message_text(
                f"{emoji} {req_type.capitalize()} detectados:",
                reply_markup=menu
            )

        # --- Componente individual ---
        elif choice.startswith("component|"):
            _, req_type, device, cid = choice.split("|", 3)
            payload = {"request": req_type, "device": device, "id": int(cid)}
            mqtt_client.publish("system/get/telegram", json.dumps(payload))

            # Buscar nombre del componente (opcional)
            component_name = f"ID {cid}"
            items = device_cache[req_type].get(device, [])
            for item in items:
                if item["id"] == int(cid):
                    component_name = item["name"]
                    break

            # Mensaje simple sin Markdown para evitar parseos erróneos
            await query.edit_message_text(
                f"{EMOJIS['loading']} Consultando {component_name} en {device}..."
            )

        # --- Menú principal ---
        elif choice == "main_menu":
            await query.edit_message_text(f"{EMOJIS['home']} Menú Principal")

    except Exception as e:
        logger.error(f"Error en callback: {e}")
        await query.edit_message_text(
            f"{EMOJIS['error']} Error procesando la solicitud. Intenta nuevamente."
        )

# === RECEPCIÓN MQTT MEJORADA ===
def on_message(client, userdata, msg):
    """Procesa las respuestas MQTT con mejor manejo de errores y feedback"""
    try:
        payload = msg.payload.decode()
        topic = msg.topic
        data = json.loads(payload)
        logger.info(f"[MQTT] Mensaje recibido: {topic}")

        parts = topic.split("/")
        
        if len(parts) < 4:
            return

        req_type = parts[3]
        app = userdata.get("app")
        loop = userdata.get("loop")

        if req_type in ["sensors", "actuators"]:
            dev = data.get("device_name")
            is_global = len(parts) == 5 and parts[4].isdigit()

            if is_global and dev:
                existing = device_cache[req_type].get(dev, [])
                if not any(e["id"] == data["id"] for e in existing):
                    device_cache[req_type].setdefault(dev, []).append(data)
                    logger.info(f"[CACHE] {req_type}: añadido {data.get('name')} en {dev}")
                
                asyncio.run_coroutine_threadsafe(
                    notify_cache_update(app, req_type, dev),
                    loop,
                )
                return

            if not is_global:
                asyncio.run_coroutine_threadsafe(
                    show_data_in_chat(app, req_type, data),
                    loop,
                )

        elif req_type == "alerts":
            asyncio.run_coroutine_threadsafe(
                show_data_in_chat(app, req_type, data),
                loop,
            )

    except Exception as e:
        logger.error(f"[MQTT] Error procesando mensaje: {e}")

async def notify_cache_update(app, req_type, device_name):
    """Notifica a los usuarios cuando se actualiza la cache"""
    if "active_chats" not in app.bot_data:
        return

    emoji = EMOJIS.get(req_type, "📋")
    # MENSAJE CORREGIDO: Usar escape_markdown
    message = f"{EMOJIS['success']} *{escape_markdown(req_type.capitalize())} actualizados*\nDispositivo `{escape_markdown(device_name)}` disponible"

    for user_id, session in list(user_sessions.items()):
        if req_type in session.get("pending_requests", set()):
            try:
                await app.bot.send_message(
                    chat_id=user_id,
                    text=message,
                    parse_mode="MarkdownV2"
                )
                session["pending_requests"].discard(req_type)
            except Exception as e:
                logger.warning(f"Error notificando a usuario {user_id}: {e}")

# === ENVÍO MEJORADO DE DATOS AL CHAT ===
async def show_data_in_chat(app, req_type, data):
    """Muestra en Telegram los resultados con formato mejorado y sin errores de parseo"""
    if "active_chats" not in app.bot_data:
        return

    # === Formateo de mensaje mejorado y CORREGIDO ===
    if req_type == "sensors":
        state = str(data.get('state', '')).lower()
        status_emoji = "🟢" if any(x in state for x in ['on', 'true', '1', 'activ']) else "🔴"
        
        # MENSAJE CORREGIDO: Usar escape_markdown en todos los campos
        msg = (
            f"{EMOJIS['sensors']} *Información de Sensor*\n\n"
            f"*Dispositivo:* `{escape_markdown(data['device_name'])}`\n"
            f"*Sensor:* `{escape_markdown(data['name'])}`\n"
            f"*Ubicación:* {escape_markdown(data['location'])}\n"
            f"*Estado:* {status_emoji} `{escape_markdown(data['state'])}`\n"
            f"*ID:* `{escape_markdown(data['id'])}`"
        )

    elif req_type == "actuators":
        state = str(data.get('state', '')).lower()
        status_emoji = "🟢" if any(x in state for x in ['on', 'true', '1', 'activ']) else "🔴"
        
        # MENSAJE CORREGIDO: Usar escape_markdown en todos los campos
        msg = (
            f"{EMOJIS['actuators']} *Información de Actuador*\n\n"
            f"*Dispositivo:* `{escape_markdown(data['device_name'])}`\n"
            f"*Actuador:* `{escape_markdown(data['name'])}`\n"
            f"*Ubicación:* {escape_markdown(data['location'])}\n"
            f"*Estado:* {status_emoji} `{escape_markdown(data['state'])}`\n"
            f"*ID:* `{escape_markdown(data['id'])}`"
        )

    elif req_type == "alerts":
        priority = data.get('priority', 'medium').lower()
        priority_emoji = "🔴" if priority == 'high' else "🟡" if priority == 'medium' else "🔵"
        
        # MENSAJE CORREGIDO: Usar escape_markdown en todos los campos
        msg = (
            f"{priority_emoji} *ALERTA DEL SISTEMA*\n\n"
            f"*Dispositivo:* `{escape_markdown(data.get('device_name', 'Desconocido'))}`\n"
            f"*Componente:* `{escape_markdown(data.get('component_name', data.get('name', 'N/A')))}`\n"
            f"*Ubicación:* `{escape_markdown(data.get('location', 'N/A'))}`\n"
            f"*Estado:* `{escape_markdown(data.get('state', 'N/A'))}`\n"
            f"*Timestamp:* `{escape_markdown(data.get('timestamp', ''))}`\n"
            f"*Prioridad:* {priority_emoji} {escape_markdown(priority.upper())}"
        )

    else:
        msg = f"📨 *Datos MQTT*\n```json\n{json.dumps(data, indent=2, ensure_ascii=False)}\n```"

    # === Enviar a todos los chats activos ===
    for chat_id in list(app.bot_data["active_chats"]):
        try:
            await app.bot.send_message(
                chat_id=chat_id, 
                text=msg, 
                parse_mode="MarkdownV2",  # CAMBIADO a MarkdownV2
                reply_markup=build_main_keyboard()
            )
            logger.info(f"[TELEGRAM] Mensaje enviado a chat {chat_id} ({req_type})")
        except Exception as e:
            logger.warning(f"[TELEGRAM] Error enviando mensaje a {chat_id}: {e}")

# === LOOP MQTT CON RECONEXIÓN MEJORADA ===
def mqtt_loop(app, loop):
    """Bucle MQTT mejorado con mejor manejo de errores"""
    global mqtt_client
    reconnect_attempts = 0
    max_reconnect_delay = 60
    
    while True:
        try:
            mqtt_client = mqtt.Client(userdata={"app": app, "loop": loop})
            mqtt_client.username_pw_set(MQTT_USER, MQTT_PASS)
            
            def on_connect(client, userdata, flags, rc):
                nonlocal reconnect_attempts
                if rc == 0:
                    logger.info(f"[MQTT] ✅ Conectado exitosamente")
                    reconnect_attempts = 0
                    client.subscribe("system/response/telegram/#")
                    client.subscribe("system/alert")
                    logger.info("[MQTT] ✅ Suscripciones activas: system/response/telegram/# y system/alert")
                else:
                    logger.error(f"[MQTT] ❌ Error de conexión: código {rc}")
            
            mqtt_client.on_connect = on_connect
            mqtt_client.on_message = on_message

            logger.info(f"[MQTT] Conectando a {MQTT_HOST}:{MQTT_PORT}...")
            mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
            mqtt_client.loop_forever()
            
        except Exception as e:
            reconnect_attempts += 1
            delay = min(5 * reconnect_attempts, max_reconnect_delay)
            
            logger.error(f"[MQTT] ❌ Error de conexión: {e}. Reintento {reconnect_attempts} en {delay}s...")
            time.sleep(delay)

# === MAIN MEJORADO ===
if __name__ == "__main__":
    logger.info("🚀 Iniciando bot Telegram mejorado...")
    
    try:
        application = Application.builder().token(TOKEN).build()

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))
        application.add_handler(CallbackQueryHandler(handle_submenu))

        loop = asyncio.get_event_loop()
        import threading
        mqtt_thread = threading.Thread(target=mqtt_loop, args=(application, loop), daemon=True)
        mqtt_thread.start()

        logger.info("✅ Bot iniciado correctamente. Esperando mensajes...")
        application.run_polling()
        
    except Exception as e:
        logger.exception(f"❌ Error crítico al iniciar el bot: {e}")
