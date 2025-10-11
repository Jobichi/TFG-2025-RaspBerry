from flask import Flask, request, jsonify
from vosk import Model, KaldiRecognizer
import wave, json, io

app = Flask(__name__)
model = Model("/model")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "model_loaded": True}), 200
def transcribe():
    if 'audio' not in request.files:
        return jsonify({"error": "No se envió ningún archivo 'audio'"}), 400

    wf = wave.open(request.files['audio'], "rb")
    rec = KaldiRecognizer(model, wf.getframerate())

    result = ""
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            result += res.get("text", "") + " "

    wf.close()
    return jsonify({"text": result.strip()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=2700)
