import os, json, torch, mysql.connector
import paho.mqtt.client as mqtt
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

# === CONFIGURACIÓN ===
MODEL_PATH = "/models/tiny-llama"     # Cambia si usas otro directorio o modelo
MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
DB_HOST = os.getenv("DB_HOST", "mariadb-service")
DB_USER = os.getenv("DB_USER", "tfg")
DB_PASS = os.getenv("DB_PASS", "tfg123")
DB_NAME = os.getenv("DB_NAME", "tfgdb")

print("[Tiny-LLaMA] Cargando modelo local...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForCausalLM.from_pretrained(MODEL_PATH, torch_dtype="auto")
llm = pipeline("text-generation", model=model, tokenizer=tokenizer, max_new_tokens=200)

def query_actuators():
    db = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME)
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, device, name, location FROM actuators")
    data = cursor.fetchall()
    db.close()
    return data

def generate_command(text, actuators):
    listado = "\n".join([f"{a['id']}: {a['name']} ({a['location']}, {a['device']})" for a in actuators])
    prompt = f"""
Eres un asistente encargado de traducir órdenes de voz a comandos IoT.
Estos son los actuadores disponibles:
{listado}

El usuario ha dicho: "{text}"

Devuelve únicamente un JSON con los campos:
{{"id": <id>, "device": "<device>", "action": "<ON/OFF/OPEN/CLOSE/STOP>"}}.
    """

    print(f"[PROMPT]\n{prompt}")
    out = llm(prompt)[0]["generated_text"]

    try:
        json_str = out[out.find("{") : out.rfind("}") + 1]
        data = json.loads(json_str)
        return data
    except Exception:
        print(f"[WARN] Respuesta LLM no válida:\n{out}")
        return None

def on_message(client, userdata, msg):
    text = msg.payload.decode()
    print(f"[VOSK] → {text}")
    actuators = query_actuators()
    result = generate_command(text, actuators)
    if result:
        topic = f"set/{result['device']}/{result['id']}"
        print(f"[LLM→MQTT] {topic} = {result['action']}")
        client.publish(topic, result["action"])
    else:
        print("[ERROR] No se pudo generar comando válido")

def main():
    client = mqtt.Client()
    client.connect(MQTT_HOST, MQTT_PORT, 60)
    client.subscribe("vosk/text")
    client.on_message = on_message
    print("[Tiny-LLaMA] Esperando mensajes en vosk/text...")
    client.loop_forever()

if __name__ == "__main__":
    main()
