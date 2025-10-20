// index.js
const Ari = require('ari-client');
const { spawn } = require('child_process');
const WebSocket = require('ws');
const mqtt = require('mqtt');

const ASTERISK_URL  = process.env.ASTERISK_URL || 'http://localhost:8088';
const ASTERISK_USER = process.env.ASTERISK_USER || 'sttuser';
const ASTERISK_PASS = process.env.ASTERISK_PASS || 'asterisk';
const MQTT_HOST     = process.env.MQTT_HOST  || 'localhost';
const MQTT_PORT     = process.env.MQTT_PORT  || 1883;
const MQTT_USER     = process.env.MQTT_USER  || 'user';
const MQTT_PASS     = process.env.MQTT_PASS  || 'pass';

const VOSK_URL      = 'ws://localhost:2700'; // el vosk-service en la misma red
const RTP_PORT      = 4000;                  // puerto local de ExternalMedia
const APP_NAME      = 'stt_app';

const mqttClient = mqtt.connect(`mqtt://${MQTT_HOST}:${MQTT_PORT}`, {
  username: MQTT_USER,
  password: MQTT_PASS
});

mqttClient.on('connect', () => console.log('[MQTT] conectado'));

function startFfmpegPipe() {
  const cmd = [
    '-fflags', '+genpts', '-reorder_queue_size', '0',
    '-protocol_whitelist', 'file,udp,rtp',
    '-i', `rtp://127.0.0.1:${RTP_PORT}`,
    '-ac', '1', '-ar', '16000',
    '-f', 's16le', '-acodec', 'pcm_s16le', '-'
  ];
  return spawn('ffmpeg', cmd, { stdio: ['ignore', 'pipe', 'inherit'] });
}

async function startVoskStream(ffmpegProc) {
  const ws = new WebSocket(VOSK_URL);
  ws.on('open', () => console.log('[VOSK] Conectado'));
  ws.on('error', err => console.error('[VOSK] Error:', err));

  // lee salida binaria de ffmpeg y la manda a vosk
  ffmpegProc.stdout.on('data', chunk => {
    if (ws.readyState === WebSocket.OPEN) ws.send(chunk);
  });

  ws.on('message', msg => {
    try {
      const data = JSON.parse(msg);
      if (data.partial)
        mqttClient.publish('vosk/partial', JSON.stringify(data));
      if (data.text)
        mqttClient.publish('vosk/text', JSON.stringify(data));
    } catch (_) {}
  });

  ffmpegProc.on('close', () => {
    console.log('[FFMPEG] cerrado');
    if (ws.readyState === WebSocket.OPEN) ws.close();
  });
}

Ari.connect(ASTERISK_URL, ASTERISK_USER, ASTERISK_PASS, async (err, ari) => {
  if (err) throw err;
  console.log('[ARI] Conectado a Asterisk');

  ari.on('StasisStart', async (event, channel) => {
    console.log(`[ARI] Llamada entrante: ${channel.id}`);

    // crea canal ExternalMedia
    const ext = await ari.channels.externalMedia({
      app: APP_NAME,
      external_host: `127.0.0.1:${RTP_PORT}`,
      format: 'slin16'
    });
    console.log('[ARI] Canal ExternalMedia creado');

    // snoop al canal de la llamada
    await ari.channels.snoopChannel(channel.id, {
      app: APP_NAME,
      spy: 'in',
      whisper: 'none'
    });
    console.log('[ARI] Snoop creado');

    // arranca ffmpeg + websocket vosk
    const ff = startFfmpegPipe();
    startVoskStream(ff);

    // cuando termina la llamada
    channel.on('StasisEnd', () => {
      console.log('[ARI] Llamada finalizada');
      try { ff.kill('SIGINT'); } catch {}
    });
  });

  ari.start(APP_NAME);
});
