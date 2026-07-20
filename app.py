from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
import json, os, time, requests
from threading import Thread
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'rino_store_secret_2026_xyz123'
ADMIN_PASSWORD = "$#ZAQWSCX$DERTGV@BHYTVNMJ@UIO$MLOPIGSGHEH8BEB8EV8S#GSUWBJSIS8H38BSI8EHUEBDNSKOS9S3UVDBDJH37"
IMGBB_API_KEY = os.environ.get('IMGBB_KEY', "3fd6caa2e26d2b535c568e6616891b46")

# === بيانات شاشة البداية ===
SPLASH_FILE = 'splash.json'

def load_splash():
    if os.path.exists(SPLASH_FILE):
        try:
            with open(SPLASH_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if data.get('media') else {"media": "", "type": "image"}
        except:
            return {"media": "", "type": "image"}
    return {"media": "", "type": "image"}

def save_splash(data):
    with open(SPLASH_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# === حماية DDOS ===
request_logs = defaultdict(list)
blocked_ips = {}
MAX_REQUESTS = 200
TIME_WINDOW = 60

def is_blocked(ip):
    if ip in blocked_ips:
        if datetime.now() < blocked_ips[ip]:
            return True
        else:
            del blocked_ips[ip]
    return False

@app.before_request
def ddos_protection():
    ip = request.remote_addr
    if is_blocked(ip):
        return "🚫 IP محظور بسبب طلبات كتيرة. حاول بعد 5 دقايق", 429
    now = datetime.now()
    request_logs[ip] = [t for t in request_logs[ip] if (now - t).total_seconds() < TIME_WINDOW]
    request_logs[ip].append(now)
    if len(request_logs[ip]) > MAX_REQUESTS:
        blocked_ips[ip] = now + timedelta(minutes=5)
        print(f"🚫 حظر IP: {ip} بسبب DDOS")
        return "🚫 تم حظرك 5 دقايق بسبب طلبات كتيرة", 429

online_users = {}

def get_visitors_count():
    ip = request.remote_addr
    if session.get('visited'):
        if os.path.exists('visitors_ips.json'):
            with open('visitors_ips.json', 'r') as f:
                return len(json.load(f))
        return 0
    session['visited'] = True
    session.permanent = True
    visitors = {}
    if os.path.exists('visitors_ips.json'):
        with open('visitors_ips.json', 'r', encoding='utf-8') as f:
            visitors = json.load(f)
    visitors[ip] = datetime.now().isoformat()
    with open('visitors_ips.json', 'w', encoding='utf-8') as f:
        json.dump(visitors, f, ensure_ascii=False)
    return len(visitors)

@app.before_request
def count_visitor():
    ip = request.remote_addr
    now = datetime.now()
    online_users[ip] = now
    for old_ip in list(online_users.keys()):
        if now - online_users[old_ip] > timedelta(minutes=3):
            del online_users[old_ip]

def load_categories():
    if os.path.exists('categories.json'):
        with open('categories.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return ["تشيرتات", "علاقات", "طباعة اكواب", "لوحات", "استيكرات", "رسم على جرابات الهواتف"]

def save_categories(cats):
    with open('categories.json', 'w', encoding='utf-8') as f:
        json.dump(cats, f, ensure_ascii=False, indent=2)

categories = load_categories()
ALLOWED_IMAGE = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
ALLOWED_VIDEO = {'mp4', 'webm', 'ogg', 'mov'}

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE

def allowed_video(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_VIDEO

def upload_to_imgbb(file):
    url = "https://api.imgbb.com/1/upload"
    payload = {"key": IMGBB_API_KEY, "expiration": 0}
    try:
        file.seek(0)
        files = {"image": (file.filename, file.read())}
        response = requests.post(url, data=payload, files=files, timeout=30)
        data = response.json()
        if data.get('success'):
            return data['data']['url'].replace('http://', 'https://')
    except Exception as e:
        print("imgbb error:", e)
    return ''

def upload_to_catbox(file):
    url = "https://catbox.moe/user/api.php"
    try:
        file.seek(0)
        files = {'fileToUpload': (file.filename, file.read())}
        data = {'reqtype': 'fileupload'}
        response = requests.post(url, data=data, files=files, timeout=60)
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass
    return ''

def load_products():
    if os.path.exists('products.json'):
        try:
            with open('products.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                for cat in data:
                    for p in data[cat]:
                        p.setdefault('whatsapp', '249XXXXXXXXX')
                        p.setdefault('sold', False)
                        p.setdefault('location', 'جميع الولايات')
                return data
        except:
            return {cat: [] for cat in categories}
    return {cat: [] for cat in categories}

def save_products(data):
    with open('products.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_ads():
    if os.path.exists('ads.json'):
        try:
            with open('ads.json', 'r', encoding='utf-8') as f:
                ads = json.load(f)
                valid_ads = []
                for a in ads:
                    if a.get('media') and (a.get('link') or a.get('whatsapp')):
                        a.setdefault('desc', '')
                        a.setdefault('whatsapp', '')
                        a.setdefault('type', 'image')
                        valid_ads.append(a)
                return valid_ads
        except:
            return []
    return []

def save_ads(data):
    with open('ads.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def check_new_items():
    if not os.path.exists('last_check.txt'):
        with open('last_check.txt', 'w') as f:
            f.write(str(int(time.time())))
        return {'products': [], 'ads': []}
    with open('last_check.txt', 'r') as f:
        last = int(f.read() or 0)
    now = int(time.time())
    products = load_products()
    ads = load_ads()
    new_products = []
    new_ads = []
    for cat in products:
        for p in products[cat]:
            try:
                if int(p['id']) > last:
                    new_products.append(p)
            except:
                pass
    for ad in ads:
        try:
            if int(ad['id']) > last:
                new_ads.append(ad)
        except:
            pass
    with open('last_check.txt', 'w') as f:
        f.write(str(now))
    return {'products': new_products, 'ads': new_ads}

def find_product_by_id(pid):
    products = load_products()
    for cat in products:
        for p in products[cat]:
            if p['id'] == pid:
                return p, cat, products
    return None, None, products

# ===== قالب الصفحة الرئيسية =====
HTML = '''<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>♕ 𝗭𝗘𝗥𝗢 𝗦𝗧𝗢𝗥𝗘 ♕</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap');
*{margin:0;padding:0;box-sizing:border-box;}
:root{--bg:#f8f9fa;--text:#222;--card:#fff;--border:#e0e0e0;--header:#fff;}
[data-theme="dark"]{--bg:#0a0a0f;--text:#e0e0e0;--card:rgba(20,20,30,0.7);--border:rgba(255,255,255,0.1);--header:rgba(15,15,20,0.8);}
body{background:var(--bg);color:var(--text);font-family:'Tajawal',sans-serif;}
.top-bar{background:var(--header);border-bottom:2px solid var(--border);padding:10px 20px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:1000;backdrop-filter:blur(10px);}
.stats-box{display:flex;gap:10px;}
.stat-card{background:var(--card);border:2px solid var(--border);padding:6px 12px;border-radius:10px;font-size:12px;text-align:center;min-width:95px;}
.stat-num{color:#00ff88;font-weight:900;font-size:22px;}
.theme-btn{background:var(--card);border:2px solid var(--border);color:var(--text);padding:8px 15px;border-radius:10px;cursor:pointer;font-weight:700;}
.notification{position:fixed;top:80px;right:20px;background:linear-gradient(135deg,#00ff88,#00ccff);color:#000;padding:15px 25px;border-radius:15px;font-weight:700;z-index:9999;display:none;animation:slideIn 0.5s;box-shadow:0 5px 20px rgba(0,255,136,0.4);max-width:350px;line-height:1.8;}
@keyframes slideIn{from{transform:translateX(300px);opacity:0}to{transform:translateX(0);opacity:1}}
.site-title{text-align:center;padding:25px 20px 15px;}
.site-name{font-size:32px;font-weight:900;white-space:nowrap;background:linear-gradient(90deg,#ff0066,#ffcc00,#00ccff,#33ff99,#ff0066);background-size:400% 400%;-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:rgb 3s ease infinite;line-height:1.2;letter-spacing:3px;}
@media(max-width:480px){.site-name{font-size:26px;}}
@keyframes rgb{0%{background-position:0% 50%;}50%{background-position:100% 50%;}100%{background-position:0% 50%;}}
.nav-cats{background:var(--header);padding:12px 10px;text-align:center;border-bottom:2px solid var(--border);}
.nav-row{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin-bottom:8px;}
.cat-link{background:var(--card);border:2px solid var(--border);color:var(--text);padding:8px 16px;border-radius:10px;text-decoration:none;font-weight:700;font-size:14px;white-space:nowrap;transition:0.3s;}
.cat-link:hover{border-color:#00ff88;}
.cat-link.active{background:var(--text);color:var(--bg);}
.ads-slider{max-width:1200px;margin:20px auto;padding:0 20px;position:relative;overflow:hidden;border-radius:20px;border:3px solid #00ff88;min-height:500px;background:#000;}
.ads-wrapper{display:flex;transition:transform 0.6s ease-in-out;width:100%;}
.ads-slide{min-width:100%;flex-shrink:0;width:100%;}
.ads-box{background:var(--card);overflow:hidden;width:100%;}
.ads-media{width:100%;height:500px;display:block;object-fit:contain;background:#000;cursor:pointer;}
.ads-btn-container{padding:15px;text-align:center;background:rgba(0,0,0,0.7);}
.ads-btn{display:inline-block;background:#25D366;color:#fff;padding:14px 40px;border-radius:12px;text-decoration:none;font-weight:700;font-size:18px;width:90%;}
.ads-desc{font-size:16px;margin:10px 15px;text-align:center;line-height:1.6;color:var(--text);}
.slider-dots{text-align:center;padding:10px;background:rgba(0,0,0,0.7);position:absolute;bottom:0;left:0;right:0;z-index:10;}
.dot{display:inline-block;width:12px;height:12px;border-radius:50%;background:#666;margin:0 5px;cursor:pointer;transition:0.3s;}
.dot.active{background:#00ff88;width:30px;border-radius:6px;}
.search-box{max-width:600px;margin:25px auto;padding:0 20px;}
.search-input{width:100%;padding:15px 20px;border-radius:12px;border:2px solid var(--border);background:var(--card);color:var(--text);font-size:16px;}
.container{max-width:1400px;margin:auto;padding:30px 20px;}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:30px;}
.card{background:var(--card);border:2px solid var(--border);border-radius:16px;overflow:hidden;position:relative;}
.card.sold{opacity:0.6;}
.card img{width:100%;height:auto;max-height:550px;object-fit:contain;background:#111;border-bottom:2px solid var(--border);cursor:zoom-in;}
.card-body{padding:22px;}
.price{font-size:26px;font-weight:700;color:#00ff88;}
.location{font-size:14px;color:#00ccff;margin:10px 0;font-weight:700;}
.order-btn{display:block;background:#8B5CF6;color:#fff;text-align:center;padding:15px;border-radius:10px;text-decoration:none;font-weight:700;font-size:17px;}
.order-btn.disabled{background:#666;pointer-events:none;}
.sold-stamp{position:absolute;top:40%;left:50%;transform:translate(-50%,-50%) rotate(-15deg);font-size:48px;font-weight:900;color:#ff4500;text-shadow:0 0 10px #ff0000,0 0 20px #ff6600,0 0 30px #ffaa00,0 0 40px #ffff00,0 0 60px #ff0000;z-index:10;border:5px solid #ff4500;padding:20px 50px;border-radius:15px;background:rgba(0,0,0,0.7);animation:fire 0.8s infinite alternate;}
@keyframes fire{0%{text-shadow:0 0 10px #ff0000,0 0 20px #ff6600,0 0 30px #ffaa00;filter:blur(0px)}100%{text-shadow:0 0 20px #ff0000,0 0 40px #ff6600,0 0 60px #ffaa00,0 0 80px #ffff00;filter:blur(1px)}}
.gallery-modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.95);z-index:99999;align-items:center;justify-content:center;}
.gallery-modal.active{display:flex;}
.gallery-img{max-width:95%;max-height:95%;border-radius:10px;}
.gallery-close{position:absolute;top:30px;right:40px;font-size:50px;color:#fff;cursor:pointer;}
</style>
</head>
<body>
<audio id="notificationSound" preload="auto">
    <source src="https://files.catbox.moe/u5zsfh.wav" type="audio/wav">
</audio>

{% if not session.get('splash_shown') %}
{% set splash = load_splash() %}
{% if splash and splash.media %}
<div id="splash" style="position:fixed;top:0;left:0;width:100%;height:100%;background:#000;z-index:99999;display:flex;align-items:center;justify-content:center;transition:opacity 1s;overflow:hidden;">
    <canvas id="splashCanvas" style="position:absolute;top:0;left:0;width:100%;height:100%;z-index:1;"></canvas>
    <div style="position:relative;z-index:2;width:90%;max-width:1200px;height:500px;border-radius:20px;border:3px solid #00ff88;background:#000;display:flex;align-items:center;justify-content:center;box-shadow:0 0 40px rgba(0,255,136,0.3);">
        {% if splash.type == 'video' %}
        <video id="splashMedia" autoplay muted loop playsinline style="max-width:100%;max-height:100%;border-radius:17px;">
            <source src="{{ splash.media }}" type="video/mp4">
        </video>
        {% else %}
        <img id="splashMedia" src="{{ splash.media }}" style="max-width:100%;max-height:100%;object-fit:contain;border-radius:17px;">
        {% endif %}
    </div>
    <div style="position:absolute;bottom:50px;z-index:2;color:#00ff88;font-size:24px;font-weight:900;letter-spacing:3px;text-shadow:0 0 30px rgba(0,255,136,0.5);">♕ 𝗭𝗘𝗥𝗢 𝗦𝗧𝗢𝗥𝗘 ♕</div>
</div>
<script>
var splashShown = false;
setTimeout(function() {
    if(!splashShown) {
        splashShown = true;
        var splash = document.getElementById('splash');
        splash.style.opacity = '0';
        setTimeout(function() {
            splash.remove();
        }, 1000);
        fetch('/splash_shown');
    }
}, 20000);

window.addEventListener('load', function() {
    const canvas = document.getElementById('splashCanvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    const dots = [];
    for(let i = 0; i < 80; i++){
        dots.push({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            r: Math.random() * 3 + 1,
            dx: (Math.random() - 0.5) * 0.5,
            dy: (Math.random() - 0.5) * 0.5,
            color: `hsl(${Math.random()*360}, 100%, 50%)`
        });
    }
    function animateDots(){
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        dots.forEach(dot => {
            dot.x += dot.dx;
            dot.y += dot.dy;
            if(dot.x < 0 || dot.x > canvas.width) dot.dx *= -1;
            if(dot.y < 0 || dot.y > canvas.height) dot.dy *= -1;
            ctx.beginPath();
            ctx.arc(dot.x, dot.y, dot.r, 0, Math.PI * 2);
            ctx.fillStyle = dot.color;
            ctx.shadowBlur = 15;
            ctx.shadowColor = dot.color;
            ctx.fill();
            const match = dot.color.match(/\\d+/);
            if(match) {
                const hue = (parseInt(match[0]) + 1) % 360;
                dot.color = `hsl(${hue}, 100%, 50%)`;
            }
        });
        requestAnimationFrame(animateDots);
    }
    animateDots();
});
window.addEventListener('resize', () => {
    const canvas = document.getElementById('splashCanvas');
    if(canvas){
        canvas.width = window.innerWidth;
        canvas.height = window.innerHeight;
    }
});
</script>
{% endif %}
{% endif %}

<div class="top-bar">
<a href="https://t.me/MRDPY" target="_blank" style="background:var(--text);color:var(--bg);padding:6px 18px;border-radius:25px;text-decoration:none;font-weight:700">👨‍💻 المبرمج</a>
<div class="stats-box">
<div class="stat-card"><span>👥 الزوار</span><div class="stat-num">{{ visitors }}</div></div>
<div class="stat-card"><span>🟢 المتصلين</span><div class="stat-num">{{ online }}</div></div>
</div>
<button class="theme-btn" onclick="toggleTheme()">🌓</button>
</div>

<div class="notification" id="notif"></div>
{% if message %}
<div class="alert" style="position:fixed;top:20px;right:20px;padding:15px 25px;border-radius:10px;font-weight:700;z-index:10000;background:#00ff88;color:#000;">{{ message }}</div>
<script>setTimeout(()=>document.querySelector('.alert').remove(),3000)</script>
{% endif %}
<div class="site-title"><div class="site-name">♕ 𝗭𝗘𝗥𝗢 𝗦𝗧𝗢𝗥𝗘 ♕</div></div>
<div class="nav-cats">
    <div class="nav-row">
        <a href="/" class="cat-link {% if not active_cat %}active{% endif %}">الكل</a>
        <a href="/available" class="cat-link {% if active_cat == 'available' %}active{% endif %}">المتاحات</a>
    </div>
    <div class="nav-row">
    {% for cat in categories %}
        <a href="/cat/{{ cat }}" class="cat-link {% if active_cat == cat %}active{% endif %}">{{ cat }}</a>
    {% endfor %}
    </div>
</div>
{% if ads and ads|length > 0 %}
<div class="ads-slider" id="adsSlider">
<div class="ads-wrapper" id="adsWrapper">
{% for ad in ads %}
<div class="ads-slide">
<div class="ads-box">
{% if ad.type == 'video' %}
<video class="ads-media" controls preload="metadata" playsinline>
<source src="{{ ad.media }}" type="video/mp4">
</video>
{% else %}
<img class="ads-media" src="{{ ad.media }}" alt="إعلان" onclick="openGallery(this.src)">
{% endif %}
{% if ad.desc %}
<div class="ads-desc">{{ ad.desc }}</div>
{% endif %}
<div class="ads-btn-container">
<a href="{{ ad.link if ad.link and ad.link!= '#' else 'https://wa.me/' + ad.whatsapp + '?text=استفسار عن الإعلان' }}" target="_blank" class="ads-btn">اضغط للمزيد</a>
</div>
</div>
</div>
{% endfor %}
</div>
{% if ads|length > 1 %}
<div class="slider-dots" id="sliderDots"></div>
{% endif %}
</div>
{% endif %}
<div class="search-box"><input type="text" id="searchInput" class="search-input" placeholder="🔍 ابحث..."></div>
<div class="container">
{% if products_list and products_list|length > 0 %}
<div class="grid" id="productsGrid">
{% for p in products_list %}
<div class="card {% if p.sold %}sold{% endif %}" data-name="{{ p.name }} {{ p.desc }} {{ p.location }}">
{% if p.sold %}<div class="sold-stamp">SOLD OUT</div>{% endif %}
<img src="{{ p.img if p.img else 'https://i.ibb.co/nR8mQmK/no-image.png' }}" onclick="openGallery(this.src)">
<div class="card-body">
<h3>{{ p.name }}</h3>
<div style="opacity:0.7;margin:8px 0">{{ p.desc }}</div>
<div class="price">{{ p.price }} جنيه</div>
<div class="location">📍 {{ p.location }}</div>
<a class="order-btn {% if p.sold %}disabled{% endif %}" href="https://wa.me/{{ p.whatsapp }}?text=أريد {{ p.name }} - {{ p.price }} جنيه - {{ p.location }}" target="_blank">
{% if p.sold %}نفذت{% else %}الطلب عبر واتساب{% endif %}</a>
</div>
</div>
{% endfor %}
</div>
{% else %}<div style="text-align:center;padding:80px;opacity:0.5">📦 لا توجد منتجات</div>{% endif %}
</div>
<div class="gallery-modal" id="galleryModal" onclick="closeGallery()">
<span class="gallery-close">×</span>
<img class="gallery-img" id="galleryImg">
</div>

<script>
function toggleTheme(){const html=document.documentElement;const newTheme=html.getAttribute('data-theme')==='dark'?'light':'dark';html.setAttribute('data-theme',newTheme);localStorage.setItem('theme',newTheme);}
document.documentElement.setAttribute('data-theme',localStorage.getItem('theme')||'dark');

document.getElementById('searchInput').addEventListener('input',function(){
    const query=this.value.toLowerCase();
    document.querySelectorAll('.card').forEach(card=>{
        card.style.display=card.getAttribute('data-name').toLowerCase().includes(query)?'block':'none'
    })
});
function openGallery(src){document.getElementById('galleryImg').src=src;document.getElementById('galleryModal').classList.add('active');}
function closeGallery(){document.getElementById('galleryModal').classList.remove('active');}

let currentSlide = 0;
let slideInterval;
function initSlider() {
    const wrapper = document.getElementById('adsWrapper');
    const dotsContainer = document.getElementById('sliderDots');
    if (!wrapper) return;
    const slides = wrapper.querySelectorAll('.ads-slide');
    if (slides.length <= 1) return;
    if(dotsContainer) {
        slides.forEach((_, i) => {
            const dot = document.createElement('span');
            dot.className = 'dot' + (i === 0? ' active' : '');
            dot.onclick = () => goToSlide(i);
            dotsContainer.appendChild(dot);
        });
    }
    function updateSlider() {
        wrapper.style.transform = 'translateX(' + (currentSlide * 100) + '%)';
        document.querySelectorAll('.dot').forEach((dot, i) => {
            dot.classList.toggle('active', i === currentSlide);
        });
    }
    function goToSlide(n) {
        currentSlide = n;
        updateSlider();
        resetInterval();
    }
    function nextSlide() {
        currentSlide = (currentSlide + 1) % slides.length;
        updateSlider();
    }
    function resetInterval() {
        clearInterval(slideInterval);
        slideInterval = setInterval(nextSlide, 5000);
    }
    slideInterval = setInterval(nextSlide, 5000);
    const slider = document.getElementById('adsSlider');
    slider.addEventListener('mouseenter', () => clearInterval(slideInterval));
    slider.addEventListener('mouseleave', resetInterval);
    updateSlider();
}
window.addEventListener('load', initSlider);

// === الاشعارات مع الصوت ===
var notifSound = document.getElementById('notificationSound');

function playNotificationSound() {
    if(notifSound) {
        notifSound.currentTime = 0;
        notifSound.play().catch(function(e) {});
    }
}

setInterval(function(){
    fetch('/check_new').then(r=>r.json()).then(data=>{
        const notif = document.getElementById('notif');
        let messages = [];

        if(data.products && data.products.length > 0){
            data.products.forEach(p=>{
                messages.push(`🛍️ منتج جديد نزل!<br>📦 الاسم: ${p.name}<br>💰 السعر: ${p.price} جنيه<br>🏷️ القسم: ${p.cat}`);
            });
        }
        if(data.ads && data.ads.length > 0){
            data.ads.forEach(a=>{
                messages.push(`📢 اعلان جديد!<br>📝 الوصف: ${a.desc || 'اعلان جديد في المتجر'}`);
            });
        }

        if(messages.length > 0){
            playNotificationSound();
            let i = 0;
            function showNext(){
                if(i < messages.length){
                    notif.innerHTML = messages[i];
                    notif.style.display = 'block';
                    setTimeout(()=>{
                        notif.style.display='none';
                        i++;
                        setTimeout(showNext, 500);
                    }, 6000);
                }
            }
            showNext();
        }
    });
}, 30000);
</script>
</body>
</html>'''

# ===== قالب تسجيل الدخول =====
LOGIN_HTML = '''<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<title>♕ 𝗭𝗘𝗥𝗢 𝗦𝗧𝗢𝗥𝗘 ♕ - دخول</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:'Tajawal',sans-serif;}
body{background:#0a0a0f;color:#e0e0e0;display:flex;align-items:center;justify-content:center;min-height:100vh;}
.box{background:rgba(20,20,30,0.9);padding:40px;border-radius:20px;border:2px solid #00ff88;max-width:400px;width:90%;box-shadow:0 0 40px rgba(0,255,136,0.2);}
h2{text-align:center;color:#00ff88;margin-bottom:30px;font-size:28px;}
input{width:100%;padding:14px;margin:10px 0;border-radius:10px;border:2px solid #333;background:#111;color:#fff;font-size:16px;}
button{width:100%;padding:15px;background:#00ff88;color:#000;border:0;border-radius:10px;font-weight:700;font-size:17px;cursor:pointer;}
</style>
</head>
<body>
<div class="box">
<h2>♕ 𝗭𝗘𝗥𝗢 𝗦𝗧𝗢𝗥𝗘 ♕</h2>
<form method="post" action="/admin/login">
<input type="password" name="password" placeholder="كلمة السر" required>
<button type="submit">دخول</button>
</form>
</div>
</body>
</html>'''

@app.route('/splash_shown')
def splash_shown():
    session['splash_shown'] = True
    return 'ok'

@app.route('/admin/login', methods=['POST'])
def admin_login():
    if request.form.get('password') == ADMIN_PASSWORD:
        session['admin_logged'] = True
        return redirect('/admin')
    return LOGIN_HTML

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    global categories
    if not session.get('admin_logged'):
        return LOGIN_HTML
    products = load_products()
    ads = load_ads()
    splash = load_splash()
    message = request.args.get('msg')
    
    if request.method == 'POST':
        action = request.form.get('action')
        pid = request.form.get('pid')
        ad_id = request.form.get('ad_id')
        cat_name = request.form.get('cat_name')
        
        if action == 'add_cat' and cat_name:
            if cat_name not in categories:
                categories.append(cat_name)
                save_categories(categories)
                products[cat_name] = []
                save_products(products)
            return redirect('/admin?msg=تم إضافة القسم')
            
        if action == 'delete_cat' and cat_name:
            if cat_name in categories:
                categories.remove(cat_name)
                save_categories(categories)
                if cat_name in products:
                    del products[cat_name]
                    save_products(products)
            return redirect('/admin?msg=تم حذف القسم')
            
        if action == 'delete' and pid:
            p, cat, prods = find_product_by_id(pid)
            if p:
                prods[cat] = [x for x in prods[cat] if x['id'] != pid]
                save_products(prods)
            return redirect('/admin?msg=تم حذف المنتج')
            
        if action == 'toggle_sold' and pid:
            p, cat, prods = find_product_by_id(pid)
            if p:
                p['sold'] = not p.get('sold', False)
                save_products(prods)
            return redirect('/admin')
            
        if action == 'update_splash':
            media_url = ''
            media_type = 'image'
            if 'splash_media' in request.files:
                file = request.files['splash_media']
                if file and file.filename:
                    if allowed_image(file.filename):
                        media_url = upload_to_imgbb(file)
                        media_type = 'image'
                    elif allowed_video(file.filename):
                        media_url = upload_to_catbox(file)
                        media_type = 'video'
            if media_url:
                save_splash({"media": media_url, "type": media_type})
                return redirect('/admin?msg=تم تحديث شاشة البداية')
                
        if action == 'delete_splash':
            save_splash({"media": "", "type": "image"})
            return redirect('/admin?msg=تم مسح شاشة البداية')
            
        if action == 'add':
            img_url = ''
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename and allowed_image(file.filename):
                    img_url = upload_to_imgbb(file)
                    if not img_url:
                        img_url = "https://i.ibb.co/nR8mQmK/no-image.png"
            new_id = str(int(time.time()))
            new_product = {
                "id": new_id, "name": request.form['name'], "desc": request.form['desc'],
                "price": int(request.form['price']), "whatsapp": request.form['whatsapp'],
                "location": request.form['location'], "img": img_url, "cat": request.form['cat'], "sold": False
            }
            products[request.form['cat']].append(new_product)
            save_products(products)
            return redirect('/admin?msg=تم إضافة المنتج')
            
        if action == 'add_ad':
            media_url = ''
            media_type = 'image'
            if 'ad_media' in request.files:
                file = request.files['ad_media']
                if file and file.filename:
                    if allowed_image(file.filename):
                        media_url = upload_to_imgbb(file)
                        media_type = 'image'
                    elif allowed_video(file.filename):
                        media_url = upload_to_catbox(file)
                        media_type = 'video'
            if media_url:
                new_ad = {
                    "id": str(int(time.time())),
                    "media": media_url,
                    "type": media_type,
                    "link": request.form.get('ad_link', '#'),
                    "desc": request.form.get('ad_desc', ''),
                    "whatsapp": request.form.get('ad_whatsapp', '')
                }
                ads.append(new_ad)
                save_ads(ads)
                return redirect('/admin?msg=تم إضافة الإعلان')
                
        if action == 'delete_ad' and ad_id:
            ads = [a for a in ads if a['id'] != ad_id]
            save_ads(ads)
            return redirect('/admin?msg=تم حذف الإعلان')
    
    # === بناء الصفحة ===
    all_products = []
    for cat in categories:
        all_products.extend(products.get(cat, []))
    
    cards_html = ''
    for p in all_products:
        sold_text = 'إرجاع' if p.get('sold') else 'SOLD OUT'
        img_src = p.get("img", "https://i.ibb.co/nR8mQmK/no-image.png")
        cards_html += f'<div class="admin-card"><img src="{img_src}" style="height:180px;width:100%;object-fit:contain"><h4>{p["name"]}</h4><p style="font-size:14px;opacity:0.7">{p["cat"]} - {p["price"]} جنيه</p><div class="control-btns"><form method="post"><input type="hidden" name="action" value="toggle_sold"><input type="hidden" name="pid" value="{p["id"]}"><button type="submit" class="btn-big btn-sold">{sold_text}</button></form><form method="post" onsubmit="return confirm(\'متأكد؟\')"><input type="hidden" name="action" value="delete"><input type="hidden" name="pid" value="{p["id"]}"><button type="submit" class="btn-big btn-delete">حذف</button></form></div></div>'
    
    ads_html = ''
    for ad in ads:
        media_preview = f'<video src="{ad.get("media","")}" style="height:150px;width:100%;object-fit:cover;border-radius:8px" controls></video>' if ad.get('type') == 'video' else f'<img src="{ad.get("media","https://i.ibb.co/nR8mQmK/no-image.png")}" style="height:150px;width:100%;object-fit:cover;border-radius:8px">'
        ads_html += f'<div class="admin-card">{media_preview}<p style="font-size:13px;margin:10px 0">{ad.get("desc","بدون وصف")}</p><p style="font-size:12px;opacity:0.6">{ad.get("link","#")}</p><form method="post" onsubmit="return confirm(\'تحذف الإعلان؟\')"><input type="hidden" name="action" value="delete_ad"><input type="hidden" name="ad_id" value="{ad["id"]}"><button type="submit" class="btn-big btn-delete">حذف</button></form></div>'
    
    cat_manage = '<div class="cat-manage"><h3 style="color:#00ff88;margin-bottom:15px">إدارة الأقسام</h3><form method="post" style="display:flex;gap:10px"><input type="hidden" name="action" value="add_cat"><input name="cat_name" placeholder="اسم القسم الجديد" required style="flex:1;padding:12px;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text)"><button type="submit" class="btn-big btn-add" style="min-height:auto;padding:12px 25px">إضافة قسم</button></form><div class="cat-list">'
    for cat in categories:
        cat_manage += f'<div class="cat-item"><span>{cat}</span><form method="post" onsubmit="return confirm(\'تحذف القسم وكل منتجاته؟\')"><input type="hidden" name="action" value="delete_cat"><input type="hidden" name="cat_name" value="{cat}"><button type="submit" style="background:#ff4444;color:#fff;border:0;padding:5px 10px;border-radius:5px;cursor:pointer">×</button></form></div>'
    cat_manage += '</div></div>'
    
    splash_html = ''
    if splash and splash.get('media'):
        if splash.get('type') == 'video':
            splash_html = f'<video src="{splash["media"]}" style="width:100%;height:300px;object-fit:contain;border-radius:10px;background:#000" controls></video>'
        else:
            splash_html = f'<img src="{splash["media"]}" style="width:100%;height:300px;object-fit:contain;border-radius:10px;background:#000">'
    
    return render_template_string('''
<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<title>♕ 𝗭𝗘𝗥𝗢 𝗦𝗧𝗢𝗥𝗘 ♕ - لوحة التحكم</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700;900&display=swap');
*{margin:0;padding:0;box-sizing:border-box;font-family:'Tajawal',sans-serif;}
:root{--bg:#0a0a0f;--text:#e0e0e0;--card:rgba(20,20,30,0.7);--border:rgba(255,255,255,0.1);--header:rgba(15,15,20,0.8);}
body{background:var(--bg);color:var(--text);}
.admin-container{max-width:1400px;margin:30px auto;padding:20px;}
.admin-title{text-align:center;font-size:32px;color:#00ff88;margin-bottom:30px;text-shadow:0 0 20px rgba(0,255,136,0.3);}
.section-title{color:#00ff88;font-size:24px;margin:30px 0 20px;}
.admin-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:20px;}
.admin-card{background:var(--card);border:2px solid var(--border);border-radius:12px;padding:20px;}
.control-btns{display:flex;gap:12px;margin-top:15px}
.btn-big{flex:1;padding:16px 0;font-size:18px;font-weight:700;border-radius:12px;border:none;cursor:pointer;min-height:55px;}
.btn-sold{background:#ffaa00;color:#000}
.btn-delete{background:#ff4444;color:#fff}
.btn-add{background:#00ff88;color:#000}
.btn-edit{background:#4a9eff;color:#fff}
input,select,textarea{width:100%;padding:12px;margin:8px 0;border-radius:8px;border:1px solid var(--border);background:var(--bg);color:var(--text);}
textarea{height:80px;font-family:inherit;}
.cat-manage{background:var(--card);border:2px solid var(--border);padding:20px;border-radius:12px;margin:20px 0}
.cat-list{display:flex;flex-wrap:wrap;gap:10px;margin-top:15px}
.cat-item{background:var(--bg);padding:8px 15px;border-radius:8px;border:1px solid var(--border);display:flex;align-items:center;gap:10px}
.alert{position:fixed;top:20px;right:20px;padding:15px 25px;border-radius:10px;font-weight:700;z-index:10000;background:#00ff88;color:#000;box-shadow:0 5px 20px rgba(0,255,136,0.3);}
</style>
</head>
<body>
<div class="admin-container">
<h1 class="admin-title">♕ 𝗭𝗘𝗥𝗢 𝗦𝗧𝗢𝗥𝗘 ♕ - لوحة التحكم</h1>
<div style="text-align:center;margin-bottom:20px">
<a href="#add" class="btn-big btn-add" style="display:inline-block;text-decoration:none;padding:14px 30px">➕ إضافة منتج</a>
<a href="#ads" class="btn-big btn-add" style="display:inline-block;text-decoration:none;padding:14px 30px;margin:0 10px">📢 إدارة الإعلانات</a>
<a href="/admin/logout" class="btn-big btn-delete" style="display:inline-block;text-decoration:none;padding:14px 30px">🚪 خروج</a>
</div>
{{ cat_manage|safe }}
<h2 class="section-title" id="ads">📢 إدارة الإعلانات - يدعم فيديو 1080p</h2>
<div class="admin-grid">{{ ads_html|safe }}</div>

<form method="post" enctype="multipart/form-data" style="max-width:500px;margin:30px auto;background:var(--card);padding:30px;border-radius:15px;border:1px solid var(--border);">
<input type="hidden" name="action" value="add_ad">
<h3 style="text-align:center;margin-bottom:20px;color:#00ff88;">إضافة إعلان جديد</h3>
<input name="ad_link" placeholder="الرابط: https://facebook.com/... او https://t.me/... او رقم واتساب">
<input name="ad_whatsapp" placeholder="رقم واتساب 249... - يستخدم لو ما في رابط">
<textarea name="ad_desc" placeholder="وصف الإعلان - اختياري"></textarea>
<input name="ad_media" type="file" accept="image/*,video/*" required>
<button type="submit" class="btn-big btn-add" style="width:100%">➕ إضافة الإعلان</button>
</form>

<h2 class="section-title">🖼️ شاشة البداية - صورة او فيديو واحد فقط</h2>
<div class="admin-card" style="max-width:600px;margin:20px auto;border-color:#00ff88;">
    {% if splash and splash.media %}
        <p style="text-align:center;color:#00ff88;margin-bottom:10px">المعروض حاليا:</p>
        {{ splash_html|safe }}
        <form method="post" style="margin-top:10px" onsubmit="return confirm('متأكد عايز تمسح؟')">
        <input type="hidden" name="action" value="delete_splash">
        <button type="submit" class="btn-big btn-delete">🗑️ مسح شاشة البداية</button>
        </form>
    {% else %}
        <p style="text-align:center;opacity:0.6">لا توجد شاشة بداية حاليا</p>
    {% endif %}
    <form method="post" enctype="multipart/form-data" style="margin-top:15px">
    <input type="hidden" name="action" value="update_splash">
    <label style="display:block;margin-bottom:5px;color:#00ff88;">ارفع صورة او فيديو جديد:</label>
    <input name="splash_media" type="file" accept="image/*,video/*" required>
    <button type="submit" class="btn-big btn-add" style="width:100%">🔄 رفع/تحديث شاشة البداية</button>
    </form>
</div>

<h2 class="section-title">📦 المنتجات</h2>
<div class="admin-grid">{{ cards_html|safe }}</div>

<form method="post" enctype="multipart/form-data" id="add" style="max-width:500px;margin:50px auto;background:var(--card);padding:30px;border-radius:15px;border:1px solid var(--border);">
<input type="hidden" name="action" value="add">
<h2 style="text-align:center;margin-bottom:20px;color:#00ff88;">➕ إضافة منتج</h2>
<input name="name" placeholder="اسم المنتج" required>
<textarea name="desc" placeholder="الوصف" required></textarea>
<input name="price" type="number" placeholder="السعر" required>
<input name="whatsapp" placeholder="رقم واتساب 249..." required>
<input name="location" placeholder="مكان التوصيل" required>
<input name="image" type="file" accept="image/*" required>
<select name="cat">''' + ''.join(['<option>'+c+'</option>' for c in categories]) + '''</select>
<button type="submit" class="btn-big btn-add" style="width:100%">➕ إضافة</button>
</form>
</div>
{% if message %}<div class="alert">{{ message }}</div><script>setTimeout(()=>document.querySelector('.alert').remove(),3000)</script>{% endif %}
</body>
</html>
''', 
        categories=categories,
        cards_html=cards_html,
        ads_html=ads_html,
        cat_manage=cat_manage,
        splash=splash,
        splash_html=splash_html,
        message=message
    )

@app.route('/admin/logout')
def logout():
    session.pop('admin_logged', None)
    return redirect('/admin')

@app.route('/check_new')
def check_new():
    data = check_new_items()
    return jsonify({
        'products': [{'name': p['name'], 'cat': p['cat'], 'price': p['price']} for p in data['products']],
        'ads': [{'desc': a.get('desc','اعلان جديد')} for a in data['ads']]
    })

@app.route('/')
def home():
    if 'splash_shown' in session:
        session.pop('splash_shown')
    products = load_products()
    ads = load_ads()
    splash = load_splash()
    all_products = []
    for cat in categories:
        all_products.extend(products.get(cat, []))
    return render_template_string(HTML, 
        categories=categories, 
        products_list=all_products, 
        ads=ads, 
        splash=splash, 
        active_cat=None, 
        visitors=get_visitors_count(), 
        online=len(online_users), 
        message=request.args.get('msg'),
        load_splash=load_splash,
        session=session
    )

@app.route('/available')
def available_products():
    products = load_products()
    ads = load_ads()
    splash = load_splash()
    available = []
    for cat in categories:
        available.extend([p for p in products.get(cat, []) if not p.get('sold')])
    return render_template_string(HTML, 
        categories=categories, 
        products_list=available, 
        ads=ads, 
        splash=splash, 
        active_cat='available', 
        visitors=get_visitors_count(), 
        online=len(online_users), 
        message=request.args.get('msg'),
        load_splash=load_splash,
        session=session
    )

@app.route('/cat/<cat_name>')
def category_page(cat_name):
    products = load_products()
    ads = load_ads()
    splash = load_splash()
    return render_template_string(HTML, 
        categories=categories, 
        products_list=products.get(cat_name, []), 
        ads=ads, 
        splash=splash, 
        active_cat=cat_name, 
        visitors=get_visitors_count(), 
        online=len(online_users), 
        message=request.args.get('msg'),
        load_splash=load_splash,
        session=session
    )

# === Keep Alive ===
keep_alive_app = Flask('keep_alive')
@keep_alive_app.route('/')
def home_keep():
    return "♕ 𝗭𝗘𝗥𝗢 𝗦𝗧𝗢𝗥𝗘 ♕ is alive"

def run_keep():
    keep_alive_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_keep)
    t.start()

if __name__ == '__main__':
    keep_alive()
    app.run(host='0.0.0.0', port=7000, debug=False)
