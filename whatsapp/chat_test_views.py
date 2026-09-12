"""Chat web TEMPORAL para probar el agente de DeepSeek en local.

NO forma parte del producto: sirve para charlar con el mismo orquestador que usa
WhatsApp (mismas tools, misma DB) desde el navegador, sin pasar por Meta.

Se monta fuera de /api/ para que el StandardizedResponseMiddleware no envuelva
las respuestas. Borrar este archivo (y su ruta) cuando ya no se necesite.
"""
import json
import logging
from decimal import Decimal

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


@csrf_exempt
def chat_test_api(request):
    """POST {wa_id, texto?, lat?, lon?, reset?} -> {respuesta, meta...}."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Usá POST'}, status=405)

    try:
        body = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    wa_id = (body.get('wa_id') or '').strip()
    if not wa_id:
        return JsonResponse({'error': 'Falta wa_id'}, status=400)

    from whatsapp import services
    from whatsapp.agent import orchestrator

    conv = services.obtener_o_crear_conversacion(wa_id)

    # Reset: limpia el historial/estado para arrancar una charla nueva con el mismo número.
    if body.get('reset'):
        conv.historial = []
        conv.estado = conv.ESTADO_IDLE
        conv.flujo = conv.FLUJO_CLIENTE
        conv.slots = {}
        conv.ubicacion_lat = None
        conv.ubicacion_lon = None
        conv.ciudad = ''
        conv.pais = ''
        conv.save()
        return JsonResponse({'ok': True, 'reset': True, 'conv_id': conv.id})

    lat, lon = body.get('lat'), body.get('lon')
    if lat is not None and lon is not None:
        conv.ubicacion_lat = Decimal(str(lat))
        conv.ubicacion_lon = Decimal(str(lon))
        if conv.estado == conv.ESTADO_ESPERANDO_UBICACION:
            conv.estado = conv.ESTADO_IDLE
        conv.save(update_fields=['ubicacion_lat', 'ubicacion_lon', 'estado', 'ultima_actividad'])

    texto = (body.get('texto') or '').strip()
    if not texto:
        return JsonResponse({'error': 'Falta texto'}, status=400)

    trace = []
    try:
        respuesta = orchestrator.responder_mensaje(conv, texto, trace=trace)
    except Exception as exc:  # noqa: BLE001 - queremos ver el error en el chat
        logger.exception('chat_test falló')
        return JsonResponse({'error': f'{type(exc).__name__}: {exc}'}, status=500)

    conv.refresh_from_db()
    return JsonResponse({
        'respuesta': respuesta,
        'conv_id': conv.id,
        'flujo': conv.flujo,
        'estado': conv.estado,
        'usuario_id': conv.usuario_id,
        'tiene_ubicacion': conv.tiene_ubicacion,
        'ciudad': conv.ciudad,
        'tools': trace,
    })


def chat_test_page(request):
    """Sirve la página HTML del chat de prueba."""
    return HttpResponse(_PAGE_HTML, content_type='text/html; charset=utf-8')


_PAGE_HTML = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fixeo · Chat de prueba (DeepSeek)</title>
<style>
  :root { --bg:#0b141a; --panel:#111b21; --in:#202c33; --out:#005c4b; --txt:#e9edef; --muted:#8696a0; --accent:#00a884; }
  * { box-sizing:border-box; }
  body { margin:0; height:100vh; display:flex; flex-direction:column; font-family:-apple-system,Segoe UI,Roboto,sans-serif; background:var(--bg); color:var(--txt); }
  header { background:var(--panel); padding:10px 16px; display:flex; align-items:center; gap:12px; border-bottom:1px solid #222d34; }
  header .dot { width:38px; height:38px; border-radius:50%; background:var(--accent); display:grid; place-items:center; font-weight:700; color:#04231c; }
  header h1 { font-size:15px; margin:0; }
  header small { color:var(--muted); font-size:12px; }
  header .spacer { flex:1; }
  header button { background:var(--in); color:var(--txt); border:1px solid #2a3942; border-radius:8px; padding:7px 12px; cursor:pointer; font-size:13px; }
  header button:hover { background:#2a3942; }
  #meta { font-size:11px; color:var(--muted); padding:4px 16px; background:var(--panel); border-bottom:1px solid #222d34; white-space:nowrap; overflow-x:auto; }
  #body { flex:1; display:flex; min-height:0; }
  #chatcol { flex:1; display:flex; flex-direction:column; min-width:0; }
  #tools { width:340px; background:#0c1418; border-left:1px solid #222d34; overflow-y:auto; padding:10px; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; font-size:12px; }
  #tools h2 { font-size:12px; color:var(--accent); margin:2px 4px 10px; font-family:-apple-system,sans-serif; text-transform:uppercase; letter-spacing:.5px; }
  .tool { background:#111b21; border:1px solid #223; border-radius:8px; margin-bottom:8px; overflow:hidden; }
  .tool .th { padding:6px 8px; background:#16232b; color:#7fd7c4; font-weight:600; cursor:pointer; display:flex; justify-content:space-between; gap:6px; }
  .tool .th .turn { color:var(--muted); font-weight:400; }
  .tool pre { margin:0; padding:6px 8px; white-space:pre-wrap; word-break:break-word; color:#c9d3d9; border-top:1px solid #223; }
  .tool pre.args { color:#e6c07b; }
  .tool .lbl { color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.5px; padding:4px 8px 0; }
  #tools .empty { color:var(--muted); padding:8px; }
  @media (max-width:720px){ #tools{ display:none; } }
  #log { flex:1; overflow-y:auto; padding:18px 14px; display:flex; flex-direction:column; gap:8px; }
  .msg { max-width:76%; padding:8px 11px; border-radius:9px; line-height:1.35; font-size:14.5px; white-space:pre-wrap; word-break:break-word; }
  .user { align-self:flex-end; background:var(--out); border-bottom-right-radius:2px; }
  .bot { align-self:flex-start; background:var(--in); border-bottom-left-radius:2px; }
  .err { align-self:center; background:#3a1d1d; color:#ffb4b4; font-size:13px; border:1px solid #5a2a2a; }
  .sys { align-self:center; color:var(--muted); font-size:12px; }
  .typing { align-self:flex-start; color:var(--muted); font-size:13px; padding:4px 11px; }
  footer { background:var(--panel); padding:10px 12px; display:flex; gap:8px; border-top:1px solid #222d34; }
  #txt { flex:1; resize:none; background:var(--in); color:var(--txt); border:1px solid #2a3942; border-radius:10px; padding:10px 12px; font-size:14.5px; max-height:120px; }
  #send { background:var(--accent); color:#04231c; border:none; border-radius:10px; padding:0 18px; font-weight:700; cursor:pointer; }
  #send:disabled { opacity:.5; cursor:default; }
</style>
</head>
<body>
<header>
  <div class="dot">F</div>
  <div>
    <h1>Asistente Fixeo</h1>
    <small id="waid"></small>
  </div>
  <div class="spacer"></div>
  <button id="reset">🗑 Nueva charla</button>
</header>
<div id="meta">flujo: — · estado: — · usuario: — · ubicación: —</div>
<div id="body">
  <div id="chatcol">
    <div id="log"></div>
    <footer>
      <textarea id="txt" rows="1" placeholder="Escribí un mensaje… (Enter para enviar)"></textarea>
      <button id="send">Enviar</button>
    </footer>
  </div>
  <div id="tools">
    <h2>🛠 Tool-calls</h2>
    <div id="toolslist"><div class="empty">Todavía no se llamó ninguna herramienta.</div></div>
  </div>
</div>

<script>
const KEY = 'fixeo_chat_waid';
let waid = localStorage.getItem(KEY);
if (!waid) { waid = '5999' + Math.floor(1000000 + Math.random()*8999999); localStorage.setItem(KEY, waid); }
document.getElementById('waid').textContent = 'wa_id de prueba: ' + waid;

const log = document.getElementById('log');
const txt = document.getElementById('txt');
const send = document.getElementById('send');
const metaEl = document.getElementById('meta');
const toolsList = document.getElementById('toolslist');
let turno = 0;

function renderTools(tools) {
  turno++;
  if (!tools || !tools.length) return;
  if (toolsList.querySelector('.empty')) toolsList.innerHTML = '';
  tools.forEach(t => {
    const div = document.createElement('div');
    div.className = 'tool';
    const args = JSON.stringify(t.args, null, 2);
    const res = typeof t.resultado === 'string' ? t.resultado : JSON.stringify(t.resultado, null, 2);
    div.innerHTML = `<div class="th">${t.nombre}()<span class="turn">turno ${turno}</span></div>
      <div class="lbl">args</div><pre class="args">${escapeHtml(args)}</pre>
      <div class="lbl">resultado</div><pre>${escapeHtml(res)}</pre>`;
    div.querySelector('.th').onclick = () => div.querySelectorAll('pre,.lbl').forEach(e => e.style.display = e.style.display === 'none' ? '' : 'none');
    toolsList.appendChild(div);
  });
  toolsList.scrollTop = toolsList.scrollHeight;
}
function escapeHtml(s){ return String(s).replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])); }

function add(text, cls) {
  const d = document.createElement('div');
  d.className = 'msg ' + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
  return d;
}
function updMeta(m) {
  if (!m || m.flujo === undefined) return;
  metaEl.textContent = `flujo: ${m.flujo} · estado: ${m.estado} · usuario: ${m.usuario_id || '—'} · ubicación: ${m.tiene_ubicacion ? (m.ciudad || 'sí') : 'no'}`;
}

async function post(payload) {
  const r = await fetch('/chat-test/mensaje/', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(Object.assign({wa_id: waid}, payload)),
  });
  return r.json();
}

async function enviar() {
  const t = txt.value.trim();
  if (!t) return;
  add(t, 'user');
  txt.value = ''; txt.style.height = 'auto';
  send.disabled = true;
  const typing = add('escribiendo…', 'typing');
  try {
    const data = await post({texto: t});
    typing.remove();
    if (data.error) { add('⚠ ' + data.error, 'err'); }
    else { add(data.respuesta || '(sin respuesta)', 'bot'); updMeta(data); renderTools(data.tools); }
  } catch (e) {
    typing.remove();
    add('⚠ Error de red: ' + e.message, 'err');
  }
  send.disabled = false;
  txt.focus();
}

send.onclick = enviar;
txt.addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); }
});
txt.addEventListener('input', () => { txt.style.height = 'auto'; txt.style.height = Math.min(txt.scrollHeight, 120) + 'px'; });

document.getElementById('reset').onclick = async () => {
  await post({reset: true});
  log.innerHTML = '';
  turno = 0;
  toolsList.innerHTML = '<div class="empty">Todavía no se llamó ninguna herramienta.</div>';
  add('Charla reiniciada. El historial y la ubicación se borraron.', 'sys');
  metaEl.textContent = 'flujo: — · estado: — · usuario: — · ubicación: —';
};

add('Escribí para empezar. Probá: "busco un plomero cerca" o "quiero ofrecer mis servicios". Cuando te pida la ubicación, escribí tu ciudad/zona en texto.', 'sys');
txt.focus();
</script>
</body>
</html>
"""
