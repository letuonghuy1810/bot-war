import asyncio
import json
import os
import re
import time
import threading
import requests
import smtplib
import ssl
import gc
import aiohttp
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from textwrap import shorten
from colorama import Fore, init

# Thư viện cho Telegram Bot API
import telebot
from telebot.types import Message

# Khởi tạo colorama
init(autoreset=True)

# ===== CONFIG CỐ ĐỊNH =====
BOT_TOKEN = "8620475733:AAGHh0hZFSY7y1vdnfwk-kUKS6n8XQwo5Ps"

ADMIN_IDS = [
    "7059122227"
]
# ==========================


# Khởi tạo bot với python-telegram-bot
bot = telebot.TeleBot(BOT_TOKEN)

DATA_FILE = "users.json"
user_tabs = {}
TAB_LOCK = threading.Lock()
user_nhaymess_tabs = {}
NHAY_LOCK = threading.Lock()
user_treotele_tabs = {}
TREOTELE_LOCK = threading.Lock()
user_treogmail_tabs = {}
TREOGMAIL_LOCK = threading.Lock()
user_discord_tabs = {}
DIS_LOCK = threading.Lock()

# Lưu trữ trạng thái chờ response
waiting_for_response = {}

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)

def load_users():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_users(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def is_admin(user_id):
    return str(user_id) in ADMIN_IDS

def is_authorized(user_id):
    users = load_users()
    uid = str(user_id)
    if uid in users:
        exp = users[uid]
        if exp is None:
            return True
        elif datetime.fromisoformat(exp) > datetime.now():
            return True
        else:
            _remove_user_and_kill_tabs(uid)
    return False

def _add_user(uid: str, days: int = None):
    users = load_users()
    if days:
        expire_time = (datetime.now() + timedelta(days=days)).isoformat()
        users[uid] = expire_time
    else:
        users[uid] = None
    save_users(users)

def _remove_user_and_kill_tabs(uid: str):
    users = load_users()
    if uid in users:
        del users[uid]
        save_users(users)

    with TAB_LOCK:
        if uid in user_tabs:
            for tab in user_tabs[uid]:
                tab["stop_event"].set()
            del user_tabs[uid]

    with NHAY_LOCK:
        if uid in user_nhaymess_tabs:
            for tab in user_nhaymess_tabs[uid]:
                tab["stop_event"].set()
            del user_nhaymess_tabs[uid]

    with TREOTELE_LOCK:
        if uid in user_treotele_tabs:
            for tab in user_treotele_tabs[uid]:
                tab["stop_event"].set()
            del user_treotele_tabs[uid]

    with TREOGMAIL_LOCK:
        if uid in user_treogmail_tabs:
            for tab in user_treogmail_tabs[uid]:
                tab["stop_event"].set()
            del user_treogmail_tabs[uid]

    with DIS_LOCK:
        if uid in user_discord_tabs:
            for tab in user_discord_tabs[uid]:
                for stop_event in tab["stop_events"]:
                    stop_event.set()
            del user_discord_tabs[uid]

def _get_user_list():
    users = load_users()
    result = []
    for uid, exp in users.items():
        if exp:
            remaining = datetime.fromisoformat(exp) - datetime.now()
            if remaining.total_seconds() <= 0:
                continue
            days = remaining.days
            hours, rem = divmod(remaining.seconds, 3600)
            minutes, _ = divmod(rem, 60)
            time_str = f"{days} ngày, {hours} giờ, {minutes} phút"
            result.append((uid, time_str))
        else:
            result.append((uid, "vĩnh viễn"))
    return result

class Kem:
    def __init__(self, cookie):
        self.cookie = cookie
        self.user_id = self.id_user()
        self.fb_dtsg = None
        self.init_params()

    def id_user(self):
        try:
            c_user = re.search(r"c_user=(\d+)", self.cookie).group(1)
            return c_user
        except:
            raise Exception("Cookie không hợp lệ")

    def init_params(self):
        headers = {
            'Cookie': self.cookie,
            'User-Agent': 'Mozilla/5.0',
            'Accept': '*/*',
        }
        try:
            response = requests.get('https://www.facebook.com', headers=headers)
            fb_dtsg_match = re.search(r'"token":"(.*?)"', response.text)
            if not fb_dtsg_match:
                response = requests.get('https://mbasic.facebook.com', headers=headers)
                fb_dtsg_match = re.search(r'name="fb_dtsg" value="(.*?)"', response.text)
                if not fb_dtsg_match:
                    response = requests.get('https://m.facebook.com', headers=headers)
                    fb_dtsg_match = re.search(r'name="fb_dtsg" value="(.*?)"', response.text)
            if fb_dtsg_match:
                self.fb_dtsg = fb_dtsg_match.group(1)
            else:
                raise Exception("Không thể lấy được fb_dtsg")
        except Exception as e:
            raise Exception(f"Lỗi khi khởi tạo tham số: {str(e)}")

    def gui_tn(self, recipient_id, message):
        if not message or not recipient_id:
            raise ValueError("ID Box và Nội Dung không được để trống")
        timestamp = int(time.time() * 1000)
        data = {
            'thread_fbid': recipient_id,
            'action_type': 'ma-type:user-generated-message',
            'body': message,
            'client': 'mercury',
            'author': f'fbid:{self.user_id}',
            'timestamp': timestamp,
            'source': 'source:chat:web',
            'offline_threading_id': str(timestamp),
            'message_id': str(timestamp),
            'ephemeral_ttl_mode': '',
            '__user': self.user_id,
            '__a': '1',
            '__req': '1b',
            '__rev': '1015919737',
            'fb_dtsg': self.fb_dtsg
        }
        headers = {
            'Cookie': self.cookie,
            'User-Agent': 'python-http/0.27.0',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        try:
            response = requests.post('https://www.facebook.com/messaging/send/', data=data, headers=headers)
            if response.status_code != 200:
                return {'success': False, 'error_description': f'Status: {response.status_code}'}
            if 'for (;;);' in response.text:
                clean = response.text.replace('for (;;);', '')
                result = json.loads(clean)
                if 'error' in result:
                    return {'success': False, 'error_description': result.get('errorDescription', 'Unknown error')}
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error_description': str(e)}

def spam_tab_worker(messenger: Kem, box_id: str, message: str, delay: float, stop_event: threading.Event, start_time: datetime, user_id: str):
    success = 0
    fail = 0
    while not stop_event.is_set():
        result = messenger.gui_tn(box_id, message)
        ok = result.get("success", False)
        if ok:
            success += 1
            status = "OK"
        else:
            fail += 1
            status = "FAIL"
            stop_event.set()
        uptime = (datetime.now() - start_time).total_seconds()
        h, rem = divmod(int(uptime), 3600)
        m, s = divmod(rem, 60)
        print(f"[{messenger.user_id}] → {box_id} | {status} | Up: {h:02}:{m:02}:{s:02} | OK: {success} | FAIL: {fail}".ljust(120), end='\r')
        time.sleep(delay)
        gc.collect()
    print(f"\nTab của user {user_id} với cookie {messenger.user_id} đã dừng.")

def discord_spam_worker(session, token, channels, message, delay, start_time, user_id, stop_event):
    """Discord spam worker for async"""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def run():
        while not stop_event.is_set():
            elapsed = int((datetime.now() - start_time).total_seconds())
            ts = time.strftime("%H:%M:%S", time.gmtime(elapsed))
            for channel_id in channels:
                if stop_event.is_set():
                    break
                try:
                    headers = {
                        "Authorization": token,
                        "Content-Type": "application/json"
                    }
                    async with session.post(
                        f"https://discord.com/api/v10/channels/{channel_id}/messages",
                        json={"content": message},
                        headers=headers
                    ) as resp:
                        if resp.status == 200:
                            print(Fore.LIGHTGREEN_EX + f"[DIS][{user_id}] {channel_id} | Token:{token[:20]}... | Delay:{delay}s | Up:{ts}")
                        else:
                            error_text = await resp.text()
                            print(Fore.RED + f"[DIS][{user_id}] {channel_id}: {error_text}")
                except Exception as e:
                    print(Fore.RED + f"[DIS][{user_id}] {channel_id}: {e}")
            await asyncio.sleep(delay)

    loop.run_until_complete(run())

def parse_gmail_accounts(input_str: str):
    accounts = []
    for entry in re.split(r"[|]", input_str):
        if ":" in entry:
            email, pwd = entry.split(":", 1)
            accounts.append({
                "server": "smtp.gmail.com",
                "port": 465,
                "email": email.strip(),
                "password": pwd.strip(),
                "active": True
            })
    return accounts

def send_mail(smtp_info, to_email, content):
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_info["server"], smtp_info["port"], context=context) as server:
        server.login(smtp_info["email"], smtp_info["password"])
        msg = MIMEText(content)
        msg["From"] = smtp_info["email"]
        msg["To"] = to_email
        msg["Subject"] = " "
        server.sendmail(smtp_info["email"], to_email, msg.as_string())

def gmail_spam_loop(tab, user_id):
    smtp_list = tab["smtp_list"]
    to_email = tab["to_email"]
    content = tab["content"]
    delay = tab["delay"]
    stop_evt = tab["stop_event"]
    idx = 0
    while not stop_evt.is_set():
        active = [acc for acc in smtp_list if acc["active"]]
        if not active:
            for acc in smtp_list: acc["active"] = True
            active = smtp_list
        smtp = active[idx % len(active)]
        try:
            send_mail(smtp, to_email, content)
            print(f"[GMAIL][{user_id}] ✓ {smtp['email']} → {to_email}")
        except smtplib.SMTPAuthenticationError:
            smtp["active"] = False
            print(f"[GMAIL][{user_id}] ✗ Auth failed {smtp['email']}")
        except smtplib.SMTPDataError as e:
            txt = str(e)
            if "Quota" in txt or "limit" in txt:
                smtp["active"] = False
                print(f"[GMAIL][{user_id}] Quota limit {smtp['email']}")
            else:
                print(f"[GMAIL][{user_id}] DataErr {smtp['email']}: {e}")
        except Exception as e:
            print(f"[GMAIL][{user_id}] Err {smtp['email']}: {e}")
        idx += 1
        for _ in range(int(delay)):
            if stop_evt.is_set(): break
            time.sleep(1)
        if stop_evt.is_set(): break
        time.sleep(delay - int(delay))

def handle_waiting_response(message: Message):
    """Xử lý response cho các lệnh cần nhập số tab"""
    user_id = str(message.from_user.id)
    chat_id = message.chat.id

    if user_id in waiting_for_response:
        callback = waiting_for_response[user_id]
        callback(message)
        del waiting_for_response[user_id]

@bot.message_handler(commands=['start'])
def start_handler(message: Message):
    user_id = message.from_user.id
    if is_admin(user_id):
        bot.reply_to(message, "👋 **Chào Admin!**\nSử dụng /menu để xem tất cả chức năng.", parse_mode='Markdown')
    elif is_authorized(user_id):
        bot.reply_to(message, "👋 **Chào mừng!**\nSử dụng /menu để xem các chức năng.", parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ **Bạn không có quyền sử dụng bot này!**\nLiên hệ admin để được cấp quyền.", parse_mode='Markdown')

@bot.message_handler(commands=['menu'])
def menu_handler(message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id) and not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền sử dụng bot!")
        return

    menu_text = """📋 **MENU BOT** 📋
Bot by **Shade Lunar** - Zalo: 0977284114
Bot sell by **Lê Tường Huy** - Zalo: 0342433460

💬 **Messenger**
├── /treomess - Treo ngôn Messenger
└── /nhaymess - Nhây réo tên

🎮 **Discord**
├── /treodis - Treo ngôn Discord
└── /nhaydis - Nhây tag fake

📱 **Telegram**
└── /treotele - Treo ngôn kèm ảnh

📧 **Gmail**
└── /treogmail - Treo spam Gmail

⚙️ **Quản lý**
├── /add - Thêm user (admin)
├── /xoa - Xoá user (admin)
├── /list - Danh sách user (admin)
├── /tabtreomess - Quản lý tab Messenger
├── /tabnhaymess - Quản lý tab nhây Messenger
├── /tabtreodis - Quản lý tab Discord
├── /tabtreotele - Quản lý tab Telegram
└── /tabtreogmail - Quản lý tab Gmail

📝 **Cú pháp:** Thông tin cách nhau bằng dấu |
📌 **Ví dụ:** `/treomess idbox|cookie|noidung|delay`"""
    bot.reply_to(message, menu_text, parse_mode='Markdown')

@bot.message_handler(commands=['treomess'])
def treomess_handler(message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id) and not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    args = message.text.split(' ', 1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Sai cú pháp!\n`/treomess idbox|cookie|noidung|delay`", parse_mode='Markdown')
        return

    params = args[1].split('|')
    if len(params) != 4:
        bot.reply_to(message, "❌ Cần 4 tham số: `idbox|cookie|noidung|delay`", parse_mode='Markdown')
        return

    idbox, cookie, noidung, delay_str = params

    try:
        delay = float(delay_str.strip())
        if delay < 0.5:
            bot.reply_to(message, "❌ Delay phải ≥ 0.5 giây!")
            return
    except:
        bot.reply_to(message, "❌ Delay phải là số!")
        return

    try:
        messenger = Kem(cookie.strip())
    except Exception as e:
        bot.reply_to(message, f"❌ Cookie lỗi: {e}")
        return

    stop_event = threading.Event()
    start_time = datetime.now()

    thread = threading.Thread(
        target=spam_tab_worker,
        args=(messenger, idbox.strip(), noidung.strip(), delay, stop_event, start_time, str(user_id)),
        daemon=True
    )
    thread.start()

    with TAB_LOCK:
        if str(user_id) not in user_tabs:
            user_tabs[str(user_id)] = []
        user_tabs[str(user_id)].append({
            "box_id": idbox.strip(),
            "delay": delay,
            "start": start_time,
            "stop_event": stop_event,
            "thread": thread
        })

    short_content = shorten(noidung.strip(), width=100, placeholder="...")
    bot.reply_to(message, f"✅ **Đã khởi tab Messenger**\n📦 Box: `{idbox.strip()}`\n⏱ Delay: `{delay}s`\n📝 Nội dung: `{short_content}`\n🕐 Bắt đầu: `{start_time.strftime('%H:%M:%S')}`", parse_mode='Markdown')

@bot.message_handler(commands=['add'])
def add_handler(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    args = message.text.split(' ', 1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Sai cú pháp!\n`/add user_id|thoihan`\nVí dụ: `/add 123456789|7d`", parse_mode='Markdown')
        return

    params = args[1].split('|')
    if len(params) != 2:
        bot.reply_to(message, "❌ Cần 2 tham số: `user_id|thoihan`", parse_mode='Markdown')
        return

    target_id, thoihan = params

    days = None
    if thoihan and thoihan.endswith("d"):
        try:
            days = int(thoihan[:-1])
        except:
            bot.reply_to(message, "❌ Thời hạn sai! Ví dụ: `7d`", parse_mode='Markdown')
            return

    _add_user(target_id.strip(), days)
    bot.reply_to(message, f"✅ **Đã thêm user** `{target_id.strip()}`\n⏱ Thời hạn: {'vĩnh viễn' if not days else f'{days} ngày'}", parse_mode='Markdown')

@bot.message_handler(commands=['xoa'])
def xoa_handler(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    args = message.text.split(' ', 1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Sai cú pháp!\n`/xoa user_id`", parse_mode='Markdown')
        return

    target_id = args[1].strip()
    _remove_user_and_kill_tabs(target_id)
    bot.reply_to(message, f"✅ **Đã xóa user** `{target_id}`\n🗑️ Đã dừng tất cả tab.", parse_mode='Markdown')

@bot.message_handler(commands=['list'])
def list_handler(message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    user_list = _get_user_list()
    if not user_list:
        bot.reply_to(message, "📭 Danh sách trống.")
        return

    msg = "📋 **DANH SÁCH USER**\n\n"
    for uid, time_str in user_list:
        msg += f"👤 `{uid}`\n⏱ `{time_str}`\n" + "─" * 20 + "\n"

    if len(msg) > 4000:
        chunks = [msg[i:i+4000] for i in range(0, len(msg), 4000)]
        for chunk in chunks:
            bot.reply_to(message, chunk, parse_mode='Markdown')
    else:
        bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(commands=['tabtreomess'])
def tabtreomess_handler(message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id) and not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    with TAB_LOCK:
        tabs = user_tabs.get(str(user_id), [])

    if not tabs:
        bot.reply_to(message, "📭 Không có tab nào đang chạy.")
        return

    msg = "📋 **DANH SÁCH TAB MESSENGER**\n\n"
    for idx, tab in enumerate(tabs, 1):
        uptime = datetime.now() - tab["start"]
        hours, rem = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{hours:02}:{minutes:02}:{seconds:02}"

        msg += f"**{idx}. Tab #{idx}**\n📦 Box: `{tab['box_id']}`\n⏱ Delay: `{tab['delay']}s`\n🕐 Up: `{uptime_str}`\n" + "─" * 20 + "\n"

    msg += "\n📝 **Gửi số tab để dừng** (Ví dụ: 1)"
    bot.reply_to(message, msg, parse_mode='Markdown')

    def callback(response_msg):
        if response_msg.text.strip().isdigit():
            idx = int(response_msg.text.strip())
            if 1 <= idx <= len(tabs):
                with TAB_LOCK:
                    chosen = tabs[idx-1]
                    chosen["stop_event"].set()
                    tabs.pop(idx-1)
                    if not tabs:
                        del user_tabs[str(user_id)]
                bot.reply_to(response_msg, f"✅ Đã dừng tab số {idx}")
            else:
                bot.reply_to(response_msg, "❌ Số tab không hợp lệ!")
        else:
            bot.reply_to(response_msg, "❌ Vui lòng nhập số!")

    waiting_for_response[str(user_id)] = callback

@bot.message_handler(commands=['nhaymess'])
def nhaymess_handler(message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id) and not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    args = message.text.split(' ', 1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Sai cú pháp!\n`/nhaymess cookies|box_ids|ten_reo|delay`", parse_mode='Markdown')
        return

    params = args[1].split('|')
    if len(params) != 4:
        bot.reply_to(message, "❌ Cần 4 tham số: `cookies|box_ids|ten_reo|delay`", parse_mode='Markdown')
        return

    cookies_str, box_ids_str, ten_reo, delay_str = params

    cookie_list = [x.strip() for x in cookies_str.split(",") if x.strip()]
    id_list = [x.strip() for x in box_ids_str.split(",") if x.strip()]

    try:
        delay = float(delay_str.strip())
        if delay < 0.5:
            bot.reply_to(message, "❌ Delay phải ≥ 0.5 giây!")
            return
    except:
        bot.reply_to(message, "❌ Delay phải là số!")
        return

    messengers = []
    for c in cookie_list:
        try:
            messengers.append(Kem(c))
        except Exception as e:
            print(f"[!] Cookie lỗi: {e}")

    if not messengers:
        bot.reply_to(message, "❌ Tất cả cookie đều lỗi!")
        return

    class NhayReoWorker:
        def __init__(self, messengers, box_ids, messages, delay, stop_event, ten_reo):
            self.messengers = messengers
            self.box_ids = box_ids
            self.messages = messages
            self.delay = delay
            self.stop_event = stop_event
            self.ten_reo = ten_reo

        def run(self):
            idx = 0
            while not self.stop_event.is_set():
                for messenger in self.messengers:
                    for box_id in self.box_ids:
                        msg = self.messages[idx % len(self.messages)].format(name=self.ten_reo.strip())
                        result = messenger.gui_tn(box_id, msg)
                        if result.get("success"):
                            print(f"[NHAY][{messenger.user_id}] → {box_id}: OK")
                        else:
                            print(f"[NHAY][{messenger.user_id}] → {box_id}: FAIL")
                        time.sleep(0.2)
                idx += 1
                time.sleep(self.delay)

    stop_event = threading.Event()
    start_time = datetime.now()

    worker = NhayReoWorker(messengers, id_list, CAU_CHUI, delay, stop_event, ten_reo)
    thread = threading.Thread(target=worker.run, daemon=True)
    thread.start()

    with NHAY_LOCK:
        if str(user_id) not in user_nhaymess_tabs:
            user_nhaymess_tabs[str(user_id)] = []
        user_nhaymess_tabs[str(user_id)].append({
            "messengers": messengers,
            "box_ids": id_list,
            "delay": delay,
            "start_time": start_time,
            "stop_event": stop_event,
            "thread": thread,
            "ten_reo": ten_reo.strip()
        })

    bot.reply_to(message, f"✅ **Đã tạo tab nhây Messenger**\n👤 User: `{user_id}`\n📦 Box: {len(id_list)}\n📡 Tài khoản: {len(messengers)}\n⏱ Delay: `{delay}s`\n🕐 Bắt đầu: `{start_time.strftime('%H:%M:%S')}`", parse_mode='Markdown')

@bot.message_handler(commands=['tabnhaymess'])
def tabnhaymess_handler(message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id) and not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    with NHAY_LOCK:
        tabs = user_nhaymess_tabs.get(str(user_id), [])

    if not tabs:
        bot.reply_to(message, "📭 Không có tab nhây Messenger nào đang chạy.")
        return

    msg = "📋 **DANH SÁCH TAB NHÂY MESSENGER**\n\n"
    for idx, tab in enumerate(tabs, 1):
        elapsed = (datetime.now() - tab["start_time"]).total_seconds()
        h, rem = divmod(int(elapsed), 3600)
        m, s = divmod(rem, 60)
        uptime = f"{h:02}:{m:02}:{s:02}"

        box_list = ', '.join(tab['box_ids'][:3]) + ('...' if len(tab['box_ids']) > 3 else '')
        msg += f"**{idx}. Tab #{idx}**\n"
        msg += f"👤 Tên réo: `{tab['ten_reo']}`\n"
        msg += f"📦 Box: `{box_list}`\n"
        msg += f"📡 Tài khoản: {len(tab['messengers'])}\n"
        msg += f"⏱ Delay: `{tab['delay']}s`\n"
        msg += f"🕐 Up: `{uptime}`\n"
        msg += "─" * 20 + "\n"

    msg += "\n📝 **Gửi số tab để dừng** (Ví dụ: 1)"
    bot.reply_to(message, msg, parse_mode='Markdown')

    def callback(response_msg):
        if response_msg.text.strip().isdigit():
            idx = int(response_msg.text.strip())
            if 1 <= idx <= len(tabs):
                with NHAY_LOCK:
                    tabs[idx-1]["stop_event"].set()
                    del tabs[idx-1]
                    if not tabs:
                        del user_nhaymess_tabs[str(user_id)]
                bot.reply_to(response_msg, f"✅ Đã dừng tab nhây số {idx}")
            else:
                bot.reply_to(response_msg, "❌ Số tab không hợp lệ!")
        else:
            bot.reply_to(response_msg, "❌ Vui lòng nhập số!")

    waiting_for_response[str(user_id)] = callback

@bot.message_handler(commands=['treotele'])
def treotele_handler(message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id) and not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    args = message.text.split(' ', 1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Sai cú pháp!\n`/treotele tokens|chats|text|delay|img`\n(img có thể để trống)", parse_mode='Markdown')
        return

    params = args[1].split('|')
    if len(params) < 4:
        bot.reply_to(message, "❌ Cần ít nhất 4 tham số: `tokens|chats|text|delay|img`", parse_mode='Markdown')
        return

    tokens_str = params[0]
    chats_str = params[1]
    text = params[2]
    delay_str = params[3]
    img = params[4] if len(params) > 4 else None

    tokens_list = [t.strip() for t in tokens_str.split(",") if t.strip()]
    chats_list = [c.strip() for c in chats_str.split(",") if c.strip()]

    try:
        delay = int(delay_str.strip())
        if delay < 1:
            bot.reply_to(message, "❌ Delay phải ≥ 1 giây!")
            return
    except:
        bot.reply_to(message, "❌ Delay phải là số nguyên!")
        return

    valid_tokens = []
    for tk in tokens_list:
        try:
            resp = requests.get(f"https://api.telegram.org/bot{tk}/getMe", timeout=5)
            if resp.ok:
                valid_tokens.append(tk)
            else:
                bot.reply_to(message, f"⚠️ Token không hợp lệ: `{tk[:10]}...`", parse_mode='Markdown')
        except:
            bot.reply_to(message, f"⚠️ Token lỗi: `{tk[:10]}...`", parse_mode='Markdown')

    if not valid_tokens:
        bot.reply_to(message, "❌ Không có token hợp lệ!")
        return

    start_time = datetime.now()

    for tk in valid_tokens:
        stop_event = threading.Event()

        def tele_worker():
            while not stop_event.is_set():
                for chat_id in chats_list:
                    if stop_event.is_set():
                        break
                    try:
                        if img:
                            if img.startswith("http"):
                                url = f"https://api.telegram.org/bot{tk}/sendPhoto"
                                data = {"chat_id": chat_id, "caption": text, "photo": img}
                                resp = requests.post(url, data=data, timeout=10)
                            else:
                                url = f"https://api.telegram.org/bot{tk}/sendPhoto"
                                with open(img, "rb") as f:
                                    files = {"photo": f}
                                    data = {"chat_id": chat_id, "caption": text}
                                    resp = requests.post(url, data=data, files=files, timeout=10)
                        else:
                            url = f"https://api.telegram.org/bot{tk}/sendMessage"
                            data = {"chat_id": chat_id, "text": text}
                            resp = requests.post(url, data=data, timeout=10)

                        if resp.status_code == 200:
                            print(f"[TELE][{user_id}] {tk[:10]}... → {chat_id}")
                        elif resp.status_code == 429:
                            retry = resp.json().get("parameters", {}).get("retry_after", 10)
                            time.sleep(retry)
                    except Exception as e:
                        print(f"[TELE][{user_id}] Lỗi: {e}")
                    time.sleep(0.2)
                time.sleep(delay)

        thread = threading.Thread(target=tele_worker, daemon=True)
        thread.start()

        with TREOTELE_LOCK:
            if str(user_id) not in user_treotele_tabs:
                user_treotele_tabs[str(user_id)] = []
            user_treotele_tabs[str(user_id)].append({
                "stop_event": stop_event,
                "thread": thread,
                "start": start_time,
                "token": tk,
                "chats": chats_list,
                "text": text,
                "img": img,
                "delay": delay
            })

    bot.reply_to(message, f"✅ **Đã tạo tab Telegram**\n📡 Tokens: {len(valid_tokens)}\n💬 Chats: {len(chats_list)}\n⏱ Delay: `{delay}s`\n🕐 Bắt đầu: `{start_time.strftime('%H:%M:%S')}`", parse_mode='Markdown')

@bot.message_handler(commands=['tabtreotele'])
def tabtreotele_handler(message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id) and not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    with TREOTELE_LOCK:
        tabs = user_treotele_tabs.get(str(user_id), [])

    if not tabs:
        bot.reply_to(message, "📭 Không có tab Telegram nào đang chạy.")
        return

    msg = "📋 **DANH SÁCH TAB TELEGRAM**\n\n"
    for idx, tab in enumerate(tabs, 1):
        uptime = datetime.now() - tab["start"]
        hours, rem = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{hours:02}:{minutes:02}:{seconds:02}"

        msg += f"**{idx}. Tab #{idx}**\n🤖 Token: `{tab['token'][:10]}...`\n💬 Chats: {len(tab['chats'])}\n⏱ Delay: `{tab['delay']}s`\n🕐 Up: `{uptime_str}`\n" + "─" * 20 + "\n"

    msg += "\n📝 **Gửi số tab để dừng** (Ví dụ: 1)"
    bot.reply_to(message, msg, parse_mode='Markdown')

    def callback(response_msg):
        if response_msg.text.strip().isdigit():
            idx = int(response_msg.text.strip())
            if 1 <= idx <= len(tabs):
                with TREOTELE_LOCK:
                    tabs[idx-1]["stop_event"].set()
                    del tabs[idx-1]
                    if not tabs:
                        del user_treotele_tabs[str(user_id)]
                bot.reply_to(response_msg, f"✅ Đã dừng tab Telegram số {idx}")
            else:
                bot.reply_to(response_msg, "❌ Số tab không hợp lệ!")
        else:
            bot.reply_to(response_msg, "❌ Vui lòng nhập số!")

    waiting_for_response[str(user_id)] = callback

@bot.message_handler(commands=['treodis'])
def treodis_handler(message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id) and not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    args = message.text.split(' ', 1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Sai cú pháp!\n`/treodis tokens|channels|message|delay`", parse_mode='Markdown')
        return

    params = args[1].split('|')
    if len(params) != 4:
        bot.reply_to(message, "❌ Cần 4 tham số: `tokens|channels|message|delay`", parse_mode='Markdown')
        return

    tokens_str, channels_str, message_text, delay_str = params

    tokens_list = [t.strip() for t in tokens_str.split(",") if t.strip()]
    channels_list = [c.strip() for c in channels_str.split(",") if c.strip()]

    try:
        delay = float(delay_str.strip())
        if delay < 0.5:
            bot.reply_to(message, "❌ Delay phải ≥ 0.5 giây!")
            return
    except:
        bot.reply_to(message, "❌ Delay phải là số!")
        return

    session = aiohttp.ClientSession()
    start_time = datetime.now()
    stop_events = []

    for token in tokens_list:
        stop_event = threading.Event()
        stop_events.append(stop_event)

        thread = threading.Thread(
            target=discord_spam_worker,
            args=(session, token, channels_list, message_text, delay, start_time, str(user_id), stop_event),
            daemon=True
        )
        thread.start()

    with DIS_LOCK:
        if str(user_id) not in user_discord_tabs:
            user_discord_tabs[str(user_id)] = []
        user_discord_tabs[str(user_id)].append({
            "session": session,
            "stop_events": stop_events,
            "channels": channels_list,
            "tokens": tokens_list,
            "message": message_text,
            "delay": delay,
            "start": start_time
        })

    bot.reply_to(message, f"✅ **Đã tạo tab Discord**\n📡 Tokens: {len(tokens_list)}\n📦 Channels: {len(channels_list)}\n⏱ Delay: `{delay}s`\n🕐 Bắt đầu: `{start_time.strftime('%H:%M:%S')}`", parse_mode='Markdown')

@bot.message_handler(commands=['treogmail'])
def treogmail_handler(message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id) and not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    args = message.text.split(' ', 1)
    if len(args) < 2:
        bot.reply_to(message, "❌ Sai cú pháp!\n`/treogmail accounts|to_email|content|delay`\n(accounts: email:password|email:password)", parse_mode='Markdown')
        return

    params = args[1].split('|')
    if len(params) != 4:
        bot.reply_to(message, "❌ Cần 4 tham số: `accounts|to_email|content|delay`", parse_mode='Markdown')
        return

    accounts_str, to_email, content_text, delay_str = params

    try:
        delay = float(delay_str.strip())
        if delay < 1:
            bot.reply_to(message, "❌ Delay phải ≥ 1 giây!")
            return
    except:
        bot.reply_to(message, "❌ Delay phải là số!")
        return

    smtp_list = []
    for entry in re.split(r"[|]", accounts_str):
        if ":" in entry:
            email, pwd = entry.split(":", 1)
            smtp_list.append({
                "server": "smtp.gmail.com",
                "port": 465,
                "email": email.strip(),
                "password": pwd.strip(),
                "active": True
            })

    if not smtp_list:
        bot.reply_to(message, "❌ Không parse được tài khoản!")
        return

    stop_evt = threading.Event()
    start_time = datetime.now()

    tab = {
        "stop_event": stop_evt,
        "start": start_time,
        "smtp_list": smtp_list,
        "to_email": to_email.strip(),
        "content": content_text.strip(),
        "delay": delay
    }

    thread = threading.Thread(target=gmail_spam_loop, args=(tab, str(user_id)), daemon=True)
    tab["thread"] = thread

    with TREOGMAIL_LOCK:
        user_treogmail_tabs.setdefault(str(user_id), []).append(tab)

    thread.start()

    bot.reply_to(message, f"✅ **Đã tạo tab Gmail**\n📧 Tài khoản: {len(smtp_list)}\n📨 To: `{to_email.strip()}`\n⏱ Delay: `{delay}s`\n🕐 Bắt đầu: `{start_time.strftime('%H:%M:%S')}`", parse_mode='Markdown')

@bot.message_handler(commands=['tabtreogmail'])
def tabtreogmail_handler(message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id) and not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    with TREOGMAIL_LOCK:
        tabs = user_treogmail_tabs.get(str(user_id), [])

    if not tabs:
        bot.reply_to(message, "📭 Không có tab Gmail nào đang chạy.")
        return

    msg = "📋 **DANH SÁCH TAB GMAIL**\n\n"
    for idx, tab in enumerate(tabs, 1):
        uptime = datetime.now() - tab["start"]
        hours, rem = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{hours:02}:{minutes:02}:{seconds:02}"

        msg += f"**{idx}. Tab #{idx}**\n📧 Tài khoản: {len(tab['smtp_list'])}\n📨 To: `{tab['to_email']}`\n⏱ Delay: `{tab['delay']}s`\n🕐 Up: `{uptime_str}`\n" + "─" * 20 + "\n"

    msg += "\n📝 **Gửi số tab để dừng** (Ví dụ: 1)"
    bot.reply_to(message, msg, parse_mode='Markdown')

    def callback(response_msg):
        if response_msg.text.strip().isdigit():
            idx = int(response_msg.text.strip())
            if 1 <= idx <= len(tabs):
                with TREOGMAIL_LOCK:
                    tabs[idx-1]["stop_event"].set()
                    del tabs[idx-1]
                    if not tabs:
                        del user_treogmail_tabs[str(user_id)]
                bot.reply_to(response_msg, f"✅ Đã dừng tab Gmail số {idx}")
            else:
                bot.reply_to(response_msg, "❌ Số tab không hợp lệ!")
        else:
            bot.reply_to(response_msg, "❌ Vui lòng nhập số!")

    waiting_for_response[str(user_id)] = callback

@bot.message_handler(commands=['tabtreodis'])
def tabtreodis_handler(message: Message):
    user_id = message.from_user.id
    if not is_authorized(user_id) and not is_admin(user_id):
        bot.reply_to(message, "❌ Bạn không có quyền!")
        return

    with DIS_LOCK:
        tabs = user_discord_tabs.get(str(user_id), [])

    if not tabs:
        bot.reply_to(message, "📭 Không có tab Discord nào đang chạy.")
        return

    msg = "📋 **DANH SÁCH TAB DISCORD**\n\n"
    for idx, tab in enumerate(tabs, 1):
        uptime = datetime.now() - tab["start"]
        hours, rem = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(rem, 60)
        uptime_str = f"{hours:02}:{minutes:02}:{seconds:02}"

        msg += f"**{idx}. Tab #{idx}**\n📡 Tokens: {len(tab['tokens'])}\n📦 Channels: {len(tab['channels'])}\n⏱ Delay: `{tab['delay']}s`\n🕐 Up: `{uptime_str}`\n" + "─" * 20 + "\n"

    msg += "\n📝 **Gửi số tab để dừng** (Ví dụ: 1)"
    bot.reply_to(message, msg, parse_mode='Markdown')

    def callback(response_msg):
        if response_msg.text.strip().isdigit():
            idx = int(response_msg.text.strip())
            if 1 <= idx <= len(tabs):
                with DIS_LOCK:
                    for stop_event in tabs[idx-1]["stop_events"]:
                        stop_event.set()
                    asyncio.run_coroutine_threadsafe(tabs[idx-1]["session"].close(), asyncio.get_event_loop())
                    del tabs[idx-1]
                    if not tabs:
                        del user_discord_tabs[str(user_id)]
                bot.reply_to(response_msg, f"✅ Đã dừng tab Discord số {idx}")
            else:
                bot.reply_to(response_msg, "❌ Số tab không hợp lệ!")
        else:
            bot.reply_to(response_msg, "❌ Vui lòng nhập số!")

    waiting_for_response[str(user_id)] = callback

# Xử lý tất cả tin nhắn để bắt response cho waiting_for_response
@bot.message_handler(func=lambda message: True)
def all_messages_handler(message: Message):
    handle_waiting_response(message)

# ==================== DANH SÁCH CÂU CHỬI ====================
CAU_CHUI = [
    "ccho sua lofi de {name}",
    "sua di {name} em😏🤞",
    "lofi di {name} cu😝",
    "tk ngu lon {name} eyy🤣🤣",
    "nhanh ti em {name}🤪👌",
    "cam a {name} mo coi😏🤞",
    "hang hai len ti {name} de👉🤣",
    "cn tat nguyen {name}😏??",
    "cn 2 lai mat mam {name}🤪👎",
    "anh cho may sua a {name}😏🤞",
    "ah ba meta 2025 ma {name}😋👎",
    "bi anh da na tho cmnr dk {name}🤣",
    "thieu oxi a {name}🤣🤣",
    "anh cko may oxi hoa ne {name}😏👉🤣",
    "may cay cha qua a cn ngu {name}🤪",
    "may phe nhu con me may bi tao hiep ma {name}🤣",
    "dung ngam dang nuot cay tao nha coan {name}👉🤣",
    "con cho {name} cay tao ro👉🌶",
    "oc cho ngoi do nhay voi tao a {name}🤣",
    "me may bi tao cho len dinh r {name}=))",
    "ui cn ngu {name} oc cac=))",
    "cn gai me may khog bt day nay a {name} cn oc cac😝",
    "cn cho {name} may cam a:))?",
    "cam lang that r a cn ngu {name}🤣",
    "ui tk cac dam cha chem chu ak {name}😝🤞",
    "cn cho dot so tao run cam cap me roi ha em {name} =))",
    "ui cai con hoi {name}👉🤣",
    "cn me may chet duoi ao roi kia {name}😆",
    "djt con {name} cu cn lon tham:))",
    "ui con bem {name} nha la nhin phen v:))",
    "con cho cay gan nha sua di {name}😏",
    "con bem {name} co me khog😏🤞",
    "a quen may mo coi tu nho ma {name}🤣",
    "sua chill de {name} oc🤣",
    "hay cam nhan noi dau di em {name}:))))",
    "hinh anh con bem {name} gie rach bi anh cha dap:))))))",
    "ti anh chup dang tbg la may hot nha {name}🤣",
    "a may muon hot cx dau de cho cn ngu {name}👉🤣🤣",
    "oi may bi cha suc pham kia {name}-))",
    "tao co noti con boai {name} so tao:)) ti tao cap dang profile 1m theo doi:))",
    "{name} con o moi khong bame bi tao khinh thuong=)))",
    "may con gi khac hon khong con bem du ngu {name}🤣",
    "cam canh cdy ngu bi cha chui khong giam phan khang a {name}:))",
    "bi tao chui ma toi so a {name}🤞",
    "nhin ga {name} muon ia chay🤣",
    "con culi lua thay phan ban bi phan boi a {name}:))",
    "may bi tao chui cho om han dk {name}👉🤣🤣🤞",
    "bi tao chui cho so queo cac dung khong {name}:))))",
    "dung cam han tao nua {name}:))",
    "con dog {name} bi tao chui ghi thu a:))",
    "su dung ngon sat thuong xiu de bem anh di mo {name}=)))",
    "co sat thuong chi mang ko ay {name}😝",
    "con ngheo nha la {name} bi bo si va👉🤣🤣",
    "nao may co biet thu nhu anh vay {name}🤪👌",
    "thang nghich tu {name} sao may giet cha may the:))",
    "khong ngo thang phan nghich {name} lua cha doi me=))",
    "tk ngu {name} bi anh co lap ma-))",
    "phan khang di con cali {name} mat map:))",
    "may con gi khac ngoai sua khong ay {name}👉😏🤞",
    "{name} mo coi=))",
    "bi cha chui phat nao ghi han phat do {name} dk em:))",
    "may toi day de chi bi tao chui thoi ha {name}:))",
    "bo la ac quy fefe ne {name}🤣🤣",
    "nen bo lay cay ak ban nat so may luon😏🤞",
    "keo lu ban an hai may ra lmj dc anh khong vay {name}🤣🤞",
    "ui ui dung thang an hai mang ten {name}:))",
    "dung la con can ba mxh chi biet nhin anh chui cha mang me no ma {name}=))",
    "may co phan khang duoc khong vay:)) {name}",
    "may khong phan khang duoc a {name}=))",
    "may yeu kem den vay a con cali {name}😋👎",
    "con cali {name} mat mam cay ah roi🌶",
    "cu anh lam dk em {name}:))",
    "may co biet gi ngoai sua kiki dau ma {name}👉🤣🤣",
    "may la chi qua qua ban may la chi gau gau ha {name}=))",
    "mua skill di em {name}🤪🤞",
    "anh mua skill duoc ma em {name}😏🤞",
    "anh mua skill vo cai lon me may ay em {name}:))",
    "con culi {name} said : sap win duoc anh roi mung vai a🤣",
    "con cali {name} nghi vay nen mung lam dk:)) {name}",
    "win duoc anh dau de dau em {name}🤪🤞",
    "con cho dien {name} sua dien cuong nao🤣",
    "ui ui con kiki {name} cay anh da man a🌶",
    "tk mo coi {name} sua belike a🤣",
    "chill ti di em {name}🤣🤣",
    "sao sua ko chill gi het vay {name}🤣🤣",
    "bi anh chui cho tat ngon a {name}=))",
    "may sua mau khong anh dap may tat sua bh {name}:))",
    "sua toi khi kiet que nha cn thu {name}🤣🤣",
    "cam may ngung nha cn kiki {name}😝",
    "bo mat nghen ngon a ma nhai hoai v {name}:🤪👌",
    "tao cam 1887 ban ca gia pha nha may chet {name} ay:))",
    "may thay anh ba qua nen sui cmnr a {name}😜",
    "sao may cam vay {name}🤪🤞",
    "may cam = tao win do {name}🤣🤣",
    "may nham win duoc tao khong {name}🤣",
    "ga ma hay sua vay {name}👉🤣",
    "tao dem 123 may chua len tao giet con gia may do {name}🤣",
    "ra tinh hieu de tao treo co con ba may die di {name}:))",
    "may ra tinh hieu sos chay thoat than trc a {name}🤣",
    "dung thang con bat hieu {name}👉🤣🤣",
    "con me may moi de ra thang con bat hieu nhu vay🤣🤞",
    "thang con troi danh di bao gia pha a {name}🤪🤞",
    "bao nhu may gap anh cung tat dien {name}🤣🤞🤞",
    "{name} bi anh chui off mxh la vua roi=))",
    "may lam lai anh khong vayy {name}:))",
    "tao biet la khongg ma {name}👉🤣",
    "do may bai tao all san ro cmnr ma {name}🤣",
    "tao dep trai ma {name}👉🤣",
    "nen may le luoi liem chan tao di {name}🤪🤞",
    "o o ccho {name} loe toe bo may dap vo mom🤣",
    "tk cac {name} oc cho vai cuc👉🤣",
    "tk ngu {name} thay hw la lam than a🤪🤞",
    "du ngu cung onl mxh a {name}😏😏",
    "svat {name} cay cu anh den tim tai het roi a🤣",
    "moi ti xiu ma go duoi roi a {name}🤣",
    "anh speed ne tk ngu {name}👉😏",
    "cn cho ngu {name} moi 5p ma da met a🤣🤣",
    "tk bach tang {name}",
    "ccho dot la {name}",
    "ngu cn ra de a {name}",
    "tk ngon lu {name}",
    "sped di tk ga {name}",
    "ga v em {name}",
    "anh uoc ga giong may a {name}",
    "o o cn nghich tu {name}",
    "chay dau vay tk {name} ngu",
    "anh cho may chay a {name}",
    "chay nhanh vay em {name}",
    "ma sao em thoat khoi anh duoc ha {name} em",
    "co gang win anh di {name}",
    "sap win dc roi do {name}",
    "e e care t di ma {name}",
    "sao ko giam {name}",
    "roi roi cam lang a {name}",
    "on khong vay {name}",
    "bat on a {name}",
    "bi tao chui ma sao on dc {name}",
    "cn cali {name} sua bay",
    "ai cho m sua v {name}",
    "xin phep ah chua o {name}",
    "da may chetme may ma cn culi {name} du xe",
    "sao may bel vay em {name}",
    "120kg a {name}",
    "sao may khon v {name}",
    "khon nhu con kiki nha tao🤣 {name}",
    "sat thuog ti di em {name}",
    "em kem coi v {name}",
    "co gi khac khong {name}",
    "khong co j a {name}",
    "em phe vay la cung dk {name}",
    "dung a🤣 {name}",
    "roi roi {name}",
    "cn phe {name}",
    "leg keg di troi {name}",
    "lien tuc {name} di boa",
    "sao ko lien tuc {name}",
    "yeu sinh ly a🤣 {name}",
    "nang khong em {name}",
    "so anh nen dai ra mau luon a {name}",
    "cn culi {name} mat mam",
    "gap gap len tk ngu {name}",
    "anh speed vcl ma {name}",
    "may slow vaicalonn {name}",
    "an c j phe lam vay tk phe vat {name}",
    "cay cu anh lam ma {name}",
    "cay ma choi a {name}",
    "nhin mat ns nhu trai ot kia {name}",
    "choi la doi a {name}",
    "sao hay v cn dog ten {name}",
    "t cam ba chia dam dit bme may ma {name}",
    "o o thg cn bat hieu nay chs gay vs cau {name} a",
    "{name} teu v em",
    "tau hai a {name}",
    "cn an hai danh trong lang a {name}",
    "duoi a {name}",
    "nhin biet duoi r🤣 {name}",
    "anh cho may rot a {name}",
    "sao cam lang r {name}",
    "roi roi cn ngu cam {name}",
    "ccho {name} nay phen ia v",
    "anh go ba vcl ay {name}",
    "cay a {name}",
    "Ngầu Êyy {name}",
    "Cố lên con thú {name}",
    "Tao cho mày ngậm chx ? {name}",
    "Mày cút rồi hả {name} ",
    "cố tí nữa {name}",
    "speed nào {name}",
    "nhây tới năm sau dc ko {name}",
    "mạnh mẽ nào {name}",
    "Con culi mocoi ey {name}",
    "k đc à {name}",
    "con chó ngu cố đê {name}",
    "sao m câm kìa {name}",
    "gà j {name}",
    "mày sợ tao à =)) {name}",
    "m gà mà {name}",
    "mày ngu rõ mà {name}",
    "đúng mà {name}",
    "cãi à {name}",
    "mày còn gì khác k {name}",
    "học lỏm kìa {name}",
    "cố tí em {name}",
    "mếu à {name}",
    "sao mếu kìa {name}",
    "tao đã cho m mếu đâu {name}",
    "va lẹ đi con dốt {name}",
    "sao kìa {name}",
    "từ bỏ r à {name}",
    "mạnh mẽ tí đi con đĩ {name}",
    "cố lên con chó ngu {name}",
    "=)) cay tao à con đĩ {name}",
    "sợ tao à {name}",
    "sao sợ tao kìa {name}",
    "cay lắm phải kh {name}",
    "ớt rồi kìa em {name}",
    "mày còn chối à {name}",
    "làm tí đê {name}",
    "mới đó đã mệt r kìa {name}",
    "sao gà mà sồn v {name}",
    "sồn như lúc đầu cho tao {name}",
    "sao à {name}",
    "ai cho m nhai {name}",
    "cay lắm r {name}",
    "từ bỏ đi em {name}",
    "mày nghĩ mày làm t cay đc à {name}",
    "có đâu {name}",
    "tao đang hành m mà {name}",
    "bịa à {name}",
    "cay :))))) {name}",
    "cố lên chó dốt {name}",
    "hăng tiếp đi {name}",
    "tới sáng k em {name}",
    "k tới sáng à {name}",
    "chán v {name}",
    "m gà mà {name}",
    "log acc thay phiên à {name}",
    "coi tụi nó dồn ngu kìa {name}",
    "sợ tao à con chó đần {name}",
    "lại win à {name}",
    "lại win r {name}",
    "lũ cặc cay tao lắm🤣🤣 {name}",
    "cố lên đê {name}",
    "sao mới 5p đã câm r {name}",
    "yếu đến thế à {name}",
    "sao kìa {name}",
    "khóc kìa {name}",
    "cầu cứu lẹ ei {name}",
    "ai cứu đc m à :)) {name}",
    "tao bá mà {name}",
    "sao m gà thế {name}",
    "hăng lẹ cho tao {name}",
    "con chó eiii🤣 {name}",
    "ổn k em {name}",
    "kh ổn r à {name}",
    "mày óc à con chó bẻm=)) {name}",
    "mẹ mày ngu à {name}",
    "bú cặc cha m k em {name}",
    "thg giả gái :)) {name}",
    "coi nó ngu kìa ae {name}",
    "con chó này giả ngu à {name}",
    "m ổn k {name}",
    "mồ côi kìa {name}",
    "sao v sợ r à {name}",
    "cố gắng tí em {name}",
    "cay cú lắm r {name}",
    "đấy đấy bắt đầu {name}",
    "chảy nước đái bò r à em {name}",
    "sao kìa đừng run {name}",
    "mày run à:)) {name}",
    "thg dái lở {name}",
    "cay mẹ m lắm {name}",
    "lgbt xuất trận à con đĩ {name}",
    "thg cặc giết cha mắng mẹ {name}",
    "sủa mạnh eii {name}",
    "mày chết r à:)) {name}",
    "sao chết kìa {name}",
    "bị t hành nên muốn chết à {name}",
    "con lồn ngu=)) {name}",
    "sao kìa {name}",
    "mạnh lên kìa {name}",
    "yếu sinh lý à {name}",
    "sủa đê {name}",
    "cay à {name}",
    "hăng đê {name}",
    "gà kìa ae {name}",
    "akakaa {name}",
    "óc chó kìa {name}",
    "🤣🤣🤣 {name}",
    "ổn không🤣🤣 {name}",
    "bất ổn à {name}",
    "ơ kìaaa {name}",
    "hăng hái đê {name}",
    "chạy à 🤣🤣 {name}",
    "tởn à {name}",
    "kkkk {name}",
    "mày dốt à {name}",
    "cặc ngu {name}",
    "cháy đê {name}",
    "chat hăng lên {name}",
    "cố lên {name}",
    "mồ côi cay {name}",
    "cay à {name}",
    "cn chó ngu {name}",
    "óc cac kìa {name}",
    "đĩ đú:)) {name}",
    "đú kìa {name}",
    "cùn v {name}",
    "r x {name}",
    "hhhhh {name}",
    "kkakak {name}",
    "sao đú đó em {name}",
    "cac teo a con {name}",
    "ngu kìa {name}",
    "chat mạnh đê {name}",
    "hăng ee {name}",
    "ơ ơ ơ {name}",
    "sủa cháy đê {name}",
    "sủa mạnh eei {name}",
    "mày óc à con {name}",
    "tao cho m chạy à {name}",
    "con đĩ ngu sủa? {name}",
    "mày chạy à con đĩ lồn {name}",
    "co len con {name}",
    "son hang len em {name}",
    "sao m yeu v {name} ",
    "co ti nua {name}",
    "sao kia cham a {name}",
    "hang hai len ti chu {name}",
    "toi sang di {name}",
    "co gang ti con cho {name}",
    "yeu v con {name}",
    "con cho {name} co de",
    "sao m cam kia {name}",
    "ga v {name}",
    "may so a k dam chat hang ak {name}",
    "m ga ma {name}",
    "may ngu ro ma {name}",
    "con {name} an hai ma",
    "cai cun ak {name}",
    "may con gi khac ko vay {name}",
    "hoc dot nen nhay dot ak {name}",
    "co ti di em {name}",
    "meu a {name}",
    "sao meu kia {name}",
    "tao da cho m meu dau {name}",
    "va le di con {name} dot",
    "sao kia {name}",
    "tu bo r a {name}",
    "manh me ti di con {name}",
    "co len con cho {name} ngu",
    "😆 cay tao a con di {name}",
    "so tao a {name}",
    "sao cham roi kia {name}",
    "cay lam phai kh {name}",
    "{name} ot anh cmnr",
    "may con choi a {name}",
    "lam ti keo de {name}",
    "moi do da met r ha {name}",
    "sao ga ma son v {name}",
    "son nhu luc dau cho tao di con {name} dot",
    "sao duoi roi kia {name}",
    "ai cho m nhai vay {name}",
    "cay lam r a {name}",
    "tu bo di em {name}",
    "may nghi may lam t cay dc ha {name}",
    "m dang cay ma {name}",
    "tao dang hanh m ma {name}",
    "keo nhay kg ay {name}",
    "con mo coi {name}",
    "co len {name} oc cho",
    "hang tiep di {name}",
    "toi sang k em {name}",
    "met roi ha {name}",
    "speed ti dc ko {name}",
    "m ga ma {name}",
    "thay phien a {name}",
    "tui anh thay phien ban vo loz me con {name} ma kaka",
    "so tao a con cho {name}",
    "anh win me roi {name} dot",
    "ga ma hay the hien ha {name}",
    "con mo coi {name} keo cai ko em",
    "co len de {name}",
    "sao moi 1 ti ma da cam roi {name}",
    "yeu vay ak {name}",
    "sao kia {name}",
    "bat luc r ak {name}",
    "tim cach roi ha {name}",
    "ai cuu dc m a :)) {name}",
    "anh ba cmnr ma {name}",
    "sao m ga vay {name}",
    "hang le cho tao di {name}",
    "con mo coi {name}",
    "on k em {name}",
    "bat on roi a {name}",
    "may oc a con cho {name}",
    "me may ngu a {name}",
    "bu cac cha m k em {name}",
    "mo coi {name} cay anh ha",
    "me m dot tu roi a {name}",
    "phe vay {name}",
    "m on k {name}",
    "mo coi kia {name}",
    "sao v so r a {name}",
    "co gang ti em {name}",
    "cay cu lam r ha {name}",
    "dien dai di em {name}",
    "chay nuoc dai bo r a em {name}",
    "sao kia dung so anh ma {name}",
    "may run a:)) {name}",
    "thg {name} mo coi",
    "cay tao lam ha {name}",
    "lgbt len phim ngu ak em {name}",
    "thg cac giet cha mang me {name}",
    "sua manh eii {name}",
    "may chet r a:)) {name}",
    "sao chet kia {name}",
    "bi t hanh nen muon chet a {name}",
    "con {name} loz ngu kaka",
    "sao kia {name}",
    "manh len kia {name}",
    "yeu sinh ly a {name}",
    "sua de {name}",
    "cay a {name}",
    "hang de {name}",
    "con ga {name}",
    "phe vat {name}",
    "oc cho {name}",
    "me m bi t du hap hoi kia con {name}",
    "on ko em {name}",
    "bat on ak {name}",
    "o kiaaa sao vayy {name}",
    "hang hai de {name}",
    "chay ak {name}",
    "so ak {name}",
    "quiu luon roi ak {name}",
    "may dot ak {name}",
    "cac ngu {name}",
    "chay de {name}",
    "chat hang len {name}",
    "co len {name}",
    "{name} mo coi",
    "cn cho ngu {name}",
    "oc cac {name}",
    "di du {name}",
    "du kia {name}",
    "cun v {name}",
    "r luon con {name} bi ngu roi",
    "met r am {name}",
    "kkakak",
    "sao du {name}",
    "cac con {name}",
    "ngu kia {name}",
    "chat manh de {name}",
    "hang ee {name}",
    "clm thk oc cho {name}",
    "sua chay de {name}",
    "sua manh eei {name}",
    "may oc a con {name}",
    "tao cho m chay a {name}",
    "con mo coi {name}",
    "may chay a con di lon {name}",
    "sua de {name}",
    "con phen {name}",
    "bat on ho {name}",
    "s do  {name}",
    "sua lien tuc de {name}",
    "moi tay ak {name}",
    "choi t giet cha ma m ne {name}",
    "hang xiu de {name}",
    "th ngu {name}",
    "len daica bieu ne {name}",
    "sua chill de {name}",
    "m thich du ko da {name}",
    "son hang dc kg {name}",
    "cam chay nhen {name}",
    "m mau de {name}",
    "duoi ak {name}",
    "th ngu {name}",
    "con {name} len day anh sut chet me may",
    "m khoc ak {name}",
    "sua lien tuc de {name}",
    "thg {name} cho dien",
    "bi ngu ak {name}",
    "speed de {name}",
    "cham v cn culi {name}",
    "hoang loan ak {name}",
    "bat on ak {name}",
    "run ak {name}",
    "chay ak {name}",
    "duoi ak {name}",
    "met r ak {name}",
    "sua mau {name}",
    "manh dan len {name}",
    "nhanh t cho co hoi cuu ma m ne {name}",
    "cam mach me nha {name}",
    "ao war ak {name}",
    "tk {name} dot v ak",
    "cham chap ak {name}",
    "th cho bua m sao v {name}",
    "th dau buoi mat cho {name}",
    "cam hoang loan ma {name}",
    "lo lo sao may cam v {name}",
    "ai cho may cam vayy {name}",
    "anh cho chx ay=)) {name}",
    "cmm hai a {name}",
    "hai vay em {name}",
    "co gi khac khong {name}",
    "khong a {name}",
    "ga den vay a {name}",
    "thang an hai lien tuc di {name}",
    "bi anh dap dau ma {name}",
    "cay cu anh lam dk {name}",
    "âkkak sua di em {name}",
    "ccho ngu sua {name}",
    "xem ns occho kia {name}",
    "ngu hay sua a👉😏 {name}",
    "alo alo cdy ngu {name}👉🤪",
    "leg keg loc troc lay sa beg dap dau may {name}👉🤣",
    "sua hang hai ti di em ey {name}👉🤪",
    "may vua sua bi tao lay sa beg dap vo 2 hon trug dai ma {name}👉😋",
    "o o cn culi {name} bia ngu a👉🤣🤣",
    "cay anh ma lmj dc anh dau {name} dk🤞🤞",
    "culi {name} cn oc bem a con😋",
    "sao do coan zai {name} cn sua dc khong ay👉😏",
    "khong a {name}🤣🤣",
    "anh biet anh ba ma {name}",
    "ccho ngu hay sua a {name}🤪🤪",
    "mat may nhu trai ot roi kia {name}🤣🤣",
    "ngu ngu bi anh dap dau vo cot dien chetme may nha {name}🤣🤣",
    "anh thog minh vcll ma {name}🤪🤪",
    "may ngu nguc vcll ma em {name}🤣🤣",
    "dk {name} em😏🤞",
    "dung a {name}🤣🤣",
    "may lam tao cuoi dc roi ds {name}🤪🤞",
    "dien siet duoc roi do {name} ngu ey🤣🤣",
    "anh chuc may dien ko ai coi nha {name}👉🤣",
    "bi anh hanh ha den die dk {name}😏🤞",
    "anh dap chetme may ma {name} em🤣🤣",
    "sua lam vay {name} kiki🤣🤣",
    "cn me nay hap hoi a {name}👉😏🤞",
    "may bua nhan a {name}🤣🤣",
    "run ray khi gap a ma {name}🤪🤞",
    "anh len san la may khiep so dk {name}🤣🤣",
    "do ah ba qua nen may so dk {name}👉😏",
    "may van xin anh tha thu ma {name}😝🙏",
    "tao cam ak47 na vo dau mat chetme may {name}😝🙏",
    "may sua dien cuong di {name}🤣🤣",
    "cmm ngu the em {name}🤣🤞",
    "ai ngu = may nua dau {name} em 👉🤣🤞",
    "may nhu culi giang tran vay {name}🤣🤣",
    "may ma culi j may lgbt ma {name} em🤣",
    "anh ba dao san war ma {name} cu😝👎",
    "may an cut san treo ma {name} 👉🤣🤞",
    "bu cut tao song qua ngay ma {name}🤣🤣",
    "xao lon cn gay a {name}😝",
    "culi biet sua la day a {name}😏🤞",
    "ga ma gay quai vay {name}🤪👌",
    "may can ngon roi a {name}😏🤞",
    "con gi khac hon khong {name}🤪🤪",
    "khog a {name}🤣",
    "ngu den vay la cung ha {name}😏🤞",
    "sao may phe nhan vay😏🤞",
    "con nghich tu phan loan {name}🤣🤣",
    "con cho chiu so phan di {name}😏🤞",
    "chiu so phan bi anh dam cha giet ma {name} ha🤣🤣",
    "anh cs hoi dau may tu tra loi a {name}🤣",
    "tk bua nhan {name}😏🤞",
    "sao culi khong sua nx di {name}🤣🤣",
    "nin ngon roi a {name}🤣🤪",
    "gap phai cha la may phai ngam ot roi {name}🤣🤣",
    "ngon xam cac lay len doi bem ah a tk culi {name}🤪🤞",
    "cn cali mat mam sua j ay {name}😏🤞",
    "len nhay vs ah toi trang tron di {name}😝",
    "sao ay tai mat roi a {name}🤣🤣",
    "so lam roi a {name}😏🤞",
    "co may anh da dau may toi chet me {name}🤣",
    "dcm cay cu anh a {name}🤣🤣",
]

def main():
    print("Bot đang khởi động...")
    print(f"👑 Admin IDs: {ADMIN_IDS}")
    print("✅ Bot đã online!")
    print("Đang lắng nghe lệnh...")

    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30)
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        time.sleep(3)
        main()  # Tự động restart

if __name__ == "__main__":
    main()