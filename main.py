# main.py — 兼容老版 uasyncio 的 ESP32-C3 网页→ST7735 文本显示（含K1/K2启停服务器）
import os
import network, uasyncio as asyncio, ure, time
from machine import SPI, Pin
from ST7735 import TFT, TFTColor
from font_pixel_operator_mono8 import FONT

# ---------- 屏幕 ----------
spi = SPI(1, baudrate=20000000, polarity=0, phase=0, sck=Pin(3), mosi=Pin(4))
tft = TFT(spi, 0, 5, 2)   # (cs, dc, rst) 分别为 0,5,2
tft.initr()
tft.fill(TFT.BLACK)

COLOR_MAP = {
    "white": TFT.WHITE, "black": TFT.BLACK, "red": TFT.RED, "maroon": TFT.MAROON,
    "green": TFT.GREEN, "forest": TFT.FOREST, "blue": TFT.BLUE, "navy": TFT.NAVY,
    "cyan": TFT.CYAN, "yellow": TFT.YELLOW, "purple": TFT.PURPLE, "gray": TFT.GRAY
}

FONT_W = FONT["Width"]
FONT_H = FONT["Height"]
SPACING = 1

def draw_text(text, color=TFT.WHITE, scale=2):
    tft.fill(TFT.BLACK)
    tft.text((0,0), text, color, FONT, scale)

# ---------- Wi-Fi（AP） ----------
def start_ap():
    ap = network.WLAN(network.AP_IF)
    ap.active(True)
    ap.config(essid='ESP32-TFT', password='12345678', authmode=3)  # WPA2
    while not ap.active():
        time.sleep_ms(100)
    return ap.ifconfig()[0]

# ---------- Wi-Fi（STA） ----------
def start_sta(ssid, pwd):
    sta = network.WLAN(network.STA_IF)
    sta.active(True); sta.connect(ssid, pwd)
    while not sta.isconnected():
        time.sleep_ms(200)
    return sta.ifconfig()[0]

SSID = "ChinaUnicom-B932"
PASSWORD = "87654326"
try:
    draw_text("Connecting to\nWiFi: %s" % SSID, TFT.CYAN, 1)
    IP = start_sta(SSID, PASSWORD)
    draw_text("Connected!\nIP: %s" % IP, TFT.GREEN, 1)
except Exception as e:
    print("WiFi error:", e)
    IP = start_ap()
    draw_text("AP Mode\nSSID: ESP32-TFT\nPassword: 12345678\nIP: %s" % IP, TFT.YELLOW, 1)

# ---------- 页面 ----------
PAGE = """\
<!doctype html>
<html>
<head><meta charset="utf-8"><title>ESP32-TFT</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:system-ui,Segoe UI,Arial,Helvetica,sans-serif;margin:22px;}
h1{font-size:18px;margin:0 0 12px;}
.row{margin:10px 0}
textarea{width:100%;height:120px;font-size:16px}
select,input[type=number]{font-size:16px;padding:4px}
button{padding:8px 14px;font-size:16px;margin-right:8px}
@font-face{
  font-family: 'PixelOP';
  src: url('/PixelOperatorMono8.woff2') format('woff2'),
       url('/PixelOperatorMono8.ttf') format('truetype');
  font-display: swap;
}
.preview{
  background:#000; color:#fff; margin-top:12px;
  font-family: 'PixelOP', ui-monospace, Menlo, Consolas, monospace;
  white-space: pre;
  box-sizing: content-box;
  overflow: hidden;               /* 固定区域：超出隐藏 */
}
.info{color:#888; font-size:12px; margin-top:6px}
</style>
</head>
<body>
<h1>ESP32-TFT 文本显示</h1>

<div class="row">
<label>颜色：</label>
<select id="color">
  <option value="white">白色</option>
  <option value="black">黑色</option>
  <option value="red">红</option>
  <option value="maroon">褐红</option>
  <option value="green">绿</option>
  <option value="forest">青绿</option>
  <option value="blue">蓝</option>
  <option value="navy">海军蓝</option>
  <option value="cyan">青</option>
  <option value="yellow">黄</option>
  <option value="purple">紫</option>
  <option value="gray">灰</option>
</select>
&nbsp;&nbsp;
<label>字号：</label>
<input id="scale" type="number" min="1" max="5" value="2" style="width:60px">
<small>(1-5)</small>
</div>

<div class="row">
<textarea id="text" placeholder="在此输入要显示到屏幕的文本..."></textarea>
</div>

<div class="row">
<button id="send">显示</button>
<button id="clear">清屏</button>
</div>

<div class="preview" id="pv"></div>
<div class="info" id="meta"></div>

<script>
/* 与设备保持一致的渲染逻辑（预览固定区域 + 字号随 scale 变化） */
const SCREEN_W = 128, SCREEN_H = 128;
"""+f"""
const FONT_W = {FONT_W}, FONT_H = {FONT_H};   // font5x8
const SPACING = {SPACING};              // +1 的列/行间距
"""+"""
const PREVIEW_ZOOM = 3;         // 网页预览放大倍数（不影响设备端）
const text = document.getElementById('text');
const color= document.getElementById('color');
const scale= document.getElementById('scale');
const pv   = document.getElementById('pv');
const meta = document.getElementById('meta');
const btnS = document.getElementById('send');
const btnC = document.getElementById('clear');

function colorToCss(name){
  const map = {
    white:'#ffffff', black:'#000000', red:'#ff0000', maroon:'#800000',
    green:'#00ff00', forest:'#008080', blue:'#0000ff', navy:'#000080',
    cyan:'#00ffff', yellow:'#ffff00', purple:'#ff00ff', gray:'#808080'
  };
  return map[name] || '#ffffff';
}

// 固定预览外壳尺寸：屏幕像素 × 放大倍数
function fixPreviewBox(){
  pv.style.width  = (SCREEN_W * PREVIEW_ZOOM) + 'px';
  pv.style.height = (SCREEN_H * PREVIEW_ZOOM) + 'px';
}
fixPreviewBox();

function renderPreview(){
  const s = Math.max(1, Math.min(5, parseInt(scale.value||'2')));
  const cellW = FONT_W * s + SPACING;
  const cellH = FONT_H * s + SPACING;
  const cols = Math.floor(SCREEN_W / cellW);
  const rows = Math.floor(SCREEN_H / cellH);

  // 折行&截断与设备一致
  const src = (text.value || "").replace(/\\r/g, "");
  const outLines = [];
  let line = "", x = 0, y = 0;

  for (let i = 0; i < src.length; i++){
    const ch = src[i];
    if (ch === '\\n'){
      outLines.push(line); line = ""; x = 0; y++;
      if (y >= rows) break;
      continue;
    }
    if (x >= cols){
      outLines.push(line); line = ""; x = 0; y++;
      if (y >= rows) break;
    }
    line += ch; x++;
  }
  if (y < rows && line.length) outLines.push(line);
  while (outLines.length > rows) outLines.pop();

  // 预览样式：字号/行距/字距随 scale & ZOOM 等比变化；外壳固定
  pv.style.color = colorToCss(color.value);
  pv.style.fontSize    = (FONT_H * s * PREVIEW_ZOOM) + "px";
  pv.style.lineHeight  = ((FONT_H * s + SPACING) * PREVIEW_ZOOM) + "px";
  pv.style.letterSpacing = (SPACING * PREVIEW_ZOOM) + "px";
  pv.textContent = outLines.join("\\n");

  meta.textContent = `屏幕: ${SCREEN_W}x${SCREEN_H}，单元: ${FONT_W}x${FONT_H}+间距1，列×行上限: ${cols}×${rows}，字号: ${s}x，预览放大: ${PREVIEW_ZOOM}x`;
}

async function post(path, body){
  try{
    const resp = await fetch(path, {
      method:'POST',
      headers:{'Content-Type':'application/x-www-form-urlencoded'},
      body: new URLSearchParams(body)
    });
    return await resp.text();
  }catch(e){ console.log(e); }
}

text.addEventListener('input', renderPreview);
color.addEventListener('change', renderPreview);
scale.addEventListener('change', renderPreview);

btnS.onclick = async ()=>{
  const s = Math.max(1, Math.min(5, parseInt(scale.value||'2')));
  await post('/update', {text:text.value||'', color:color.value, scale:s});
};
btnC.onclick = async ()=>{ await post('/clear', {}); };

renderPreview();
</script>
</body></html>
"""

last_text = "Hello, ESP32!"
last_color = "white"
last_scale = 2

def urldecode(s):
    s = s.replace('+', ' ')
    def repl(m): return chr(int(m.group(1), 16))
    return ure.sub('%([0-9A-Fa-f]{2})', repl, s)

# --- 更稳的读头：同时兼容 \r\n 与 \n，且限制最大头长 ---
async def read_headers(reader):
    buf = bytearray()
    # 我们找双换行：\r\n\r\n 或 \n\n
    while True:
        line = await reader.readline()
        if not line:
            break
        buf.extend(line)
        # 兼容不同结尾
        if b"\r\n\r\n" in buf or b"\n\n" in buf:
            break
        if len(buf) > 8192:  # 防御性限制
            break
    return bytes(buf)

def parse_form(body_str):
    # body_str 可能是 None/空，统一成字符串
    if not body_str:
        return {}
    res = {}
    for kv in body_str.split('&'):
        if '=' in kv:
            k, v = kv.split('=', 1)
            # urldecode 里已做 %xx 处理，这里也做 + 空格兼容
            res[k] = urldecode(v)
    return res

# ---------- HTTP 处理 ----------
async def handle_client(reader, writer):
    global last_text, last_color, last_scale
    try:
        head_bytes = await read_headers(reader)
        if not head_bytes:
            raise Exception("empty headers")

        head = head_bytes.decode('utf-8', 'ignore')
        # 首行
        first = head.split('\r\n', 1)[0] if '\r\n' in head else head.split('\n', 1)[0]
        parts = first.split(' ')
        method = parts[0] if len(parts) > 0 else 'GET'
        path   = parts[1] if len(parts) > 1 else '/'

        # Content-Length（忽略大小写）
        clen = 0
        for line in head.replace('\r\n', '\n').split('\n'):
            if line.lower().startswith('content-length:'):
                try:
                    clen = int(line.split(':', 1)[1].strip())
                except:
                    clen = 0
                break

        # ---- 稳健读取 body：确保是 bytes，不为 None ----
        body_bytes = b""
        if method == 'POST' and clen > 0:
            got = await reader.read(clen)
            body_bytes = got if isinstance(got, (bytes, bytearray)) else b""

        body_str = body_bytes.decode('utf-8', 'ignore') if body_bytes else ""

        status = "200 OK"
        ct = "text/html; charset=utf-8"
        resp = b""

        if method == 'GET' and path == '/':
            resp = PAGE.encode('utf-8')

        elif method == 'GET' and (path == '/PixelOperatorMono8.woff2' or path == '/PixelOperatorMono8.ttf'):
            try:
                st = os.stat(path[1:])  # 去掉前面的 /
                fsz = st[6] if isinstance(st, tuple) else st.st_size
                headers = ("HTTP/1.1 200 OK\r\nContent-Type: font/woff2\r\n"
                           "Content-Length: %d\r\nConnection: close\r\n\r\n") % fsz
                w = writer.write(headers.encode('utf-8'))
                if hasattr(w, "__await__"):
                    await w
                with open(path[1:], 'rb') as f:
                    while True:
                        chunk = f.read(2048)
                        if not chunk: break
                        wc = writer.write(chunk)
                        if hasattr(wc, "__await__"):
                            await wc
                return
            except Exception as e:
                print("serve font error:", e)
                status = "404 Not Found"
                resp = b"Not Found"
                ct = "text/plain; charset=utf-8"

        elif method == 'POST' and path == '/update':
            form = parse_form(body_str)
            txt = form.get('text', '')[:500]
            col = form.get('color', 'white').lower()
            sc  = form.get('scale', '2')
            try:
                sc = max(1, min(5, int(sc)))
            except:
                sc = 2
            color_val = COLOR_MAP.get(col, TFT.WHITE)
            last_text, last_color, last_scale = txt, col, sc
            draw_text(last_text, color_val, last_scale)
            resp = b"OK"
            ct = "text/plain; charset=utf-8"

        elif method == 'POST' and path == '/clear':
            tft.fill(TFT.BLACK)
            resp = b"OK"
            ct = "text/plain; charset=utf-8"

        else:
            status = "404 Not Found"
            resp = b"Not Found"
            ct = "text/plain; charset=utf-8"

        headers = (
            "HTTP/1.1 {st}\r\nContent-Type: {ct}\r\nContent-Length: {cl}\r\nConnection: close\r\n\r\n"
        ).format(st=status, ct=ct, cl=len(resp)).encode('utf-8')

        # 兼容不同 uasyncio：write/drain 可能不是协程
        w = writer.write(headers)
        if hasattr(w, "__await__"):
            await w
        if resp:
            w2 = writer.write(resp)
            if hasattr(w2, "__await__"):
                await w2
        try:
            d = writer.drain()
            if hasattr(d, "__await__"):
                await d
        except Exception:
            pass
    except Exception as e:
        print("Client error:", e)
    finally:
        try:
            a = writer.aclose()
            if hasattr(a, "__await__"):
                await a
        except AttributeError:
            try:
                writer.close()
            except Exception:
                pass

# ---------- 服务器启停：K1/K2 ----------
# 按键引脚
K1_PIN = 8   # 启动
K2_PIN = 10  # 停止
AUTO_START = True  # 上电是否自动启动HTTP服务器

srv = None                  # 当前服务器对象
_req_start = False
_req_stop  = False
_last_irq_ms = 0            # 消抖时间戳

# 空闲计时与一次性展示控制
_server_off_since = None
_idle_shown = False
IDLE_TIMEOUT_MS = 1 * 60 * 1000  # 1分钟

def _irq_debounced(cb):
    def _wrap(p):
        global _last_irq_ms
        now = time.ticks_ms()
        if time.ticks_diff(now, _last_irq_ms) > 180:  # ~180ms 消抖
            _last_irq_ms = now
            cb(p)
    return _wrap

def _on_k1(_):
    global _req_start
    _req_start = True

def _on_k2(_):
    global _req_stop
    _req_stop = True

# 按键为上拉输入，按下为低电平（如相反，改为 PULL_DOWN + IRQ_RISING）
btn_k1 = Pin(K1_PIN, Pin.IN, Pin.PULL_UP)
btn_k2 = Pin(K2_PIN, Pin.IN, Pin.PULL_UP)
btn_k1.irq(trigger=Pin.IRQ_FALLING, handler=_irq_debounced(_on_k1))
btn_k2.irq(trigger=Pin.IRQ_FALLING, handler=_irq_debounced(_on_k2))

async def start_http():
    global srv
    if srv is not None:
        return
    try:
        srv = await asyncio.start_server(handle_client, "0.0.0.0", 80)
        print("HTTP server started at http://%s" % IP)
        try:
            draw_text("Server ON\nIP: %s" % IP, TFT.GREEN, 1)
        except Exception:
            pass
    except Exception as e:
        print("start_http error:", e)
        srv = None

async def stop_http():
    global srv, _server_off_since, _idle_shown
    if srv is None:
        return
    try:
        srv.close()                 # 兼容老版：可能没有 wait_closed
        await asyncio.sleep_ms(50)  # 给调度器时间撤销监听
        print("HTTP server stopped")
        _server_off_since = time.ticks_ms()  # 记录关闭时间
        _idle_shown = False
        try:
            draw_text("Server OFF", TFT.YELLOW, 1)
        except Exception:
            pass
    except Exception as e:
        print("stop_http error:", e)
    finally:
        srv = None

# ---------- 主循环 ----------
async def main():
    if AUTO_START:
        await start_http()
    else:
        try:
            draw_text("Press K1 to\nstart server", TFT.CYAN, 1)
        except Exception:
            pass

    print("K1=start, K2=stop. Current IP:", IP)

    global _req_start, _req_stop, _server_off_since, _idle_shown
    while True:
        # 处理按键请求
        if _req_start:
            _req_start = False
            await start_http()
        if _req_stop:
            _req_stop = False
            await stop_http()

        # 空闲5分钟后展示图片（仅展示一次，直到下次启动/停止）
        if srv is None and _server_off_since is not None and not _idle_shown:
            if time.ticks_diff(time.ticks_ms(), _server_off_since) >= IDLE_TIMEOUT_MS:
                from show_img import show_image
                show_image()
                _idle_shown = True
                break  # 退出循环

        await asyncio.sleep_ms(50)

asyncio.run(main())
