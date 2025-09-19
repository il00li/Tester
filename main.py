from telethon import TelegramClient, events, Button, functions, types, errors
from telethon.sessions import MemorySession
import asyncio
import logging
import os
import re
import random
from datetime import datetime

# إعدادات التسجيل
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# إعدادات البوت
API_ID = 23656977
API_HASH = '49d3f43531a92b3f5bc403766313ca1e'
BOT_TOKEN = '7966976239:AAGKSpD7iRl1sCnZ4krQvzJ9wuvfw8TNZ5Q'

# قائمة الرموز التعبيرية العشوائية
RANDOM_EMOJIS = ['🌳', '🍃', '🌱', '🍀', '🌿', '🦠', '🪲', '🦜', '🦚', '🦎', 
                 '🐉', '🐛', '🍾', '🐢', '🐸', '🌽', '💐', '☘️', '🌴', '🌵',
                 '🐊', '🌳', '🌲', '🪴', '🌸', '🌺', '🌻', '🌼', '🌷', '⚘️']

# حالات المستخدمين
user_sessions = {}
user_states = {}
transfer_tasks = {}
phone_code_requests = {}
progress_messages = {}

# وظيفة للحصول على رمز تعبيري عشوائي
def get_random_emoji():
    return random.choice(RANDOM_EMOJIS)

# تهيئة البوت باستخدام MemorySession بدلاً من SQLite
bot = TelegramClient(MemorySession(), API_ID, API_HASH)

@bot.on(events.NewMessage(pattern='/start'))
async def start(event):
    """بدء المحادثة مع البوت"""
    user_id = event.sender_id
    
    # إعادة تعيين حالة المستخدم
    user_states[user_id] = 'MAIN_MENU'
    
    # إعداد لوحة المفاتيح الرئيسية
    keyboard = [
        [Button.inline(f"{get_random_emoji()} بدء عملية النقل", "start_transfer")],
        [Button.inline(f"{get_random_emoji()} إعداد العملية", "process_settings")],
        [Button.inline(f"{get_random_emoji()} حالة النقل الحالي", "transfer_status"),
         Button.inline(f"{get_random_emoji()} الإحصائيات", "show_stats")],
        [Button.inline(f"{get_random_emoji()} المساعدة", "show_help"),
         Button.inline(f"{get_random_emoji()} مسح البيانات", "clear_data")]
    ]
    
    await event.reply(
        f"{get_random_emoji()} **مرحباً بك في بوت نقل أعضاء Telegram**\n\n"
        "يمكنك استخدام هذا البوت لنقل الأعضاء بين المجموعات والقنوات.\n\n"
        "⚠️ **ملاحظات مهمة:**\n"
        "• يجب أن تكون مسؤولاً في المجموعتين\n"
        "• قد تتعرض لحظر مؤقت إذا أضفت الكثير من الأعضاء بسرعة\n"
        "• يوصى بإضافة أقل من 50-100 عضو في اليوم\n\n"
        "لبدء الاستخدام، اضغط على 'بدء عملية النقل' أو قم بإعداد العملية أولاً",
        buttons=keyboard
    )

@bot.on(events.CallbackQuery)
async def handle_callback(event):
    """معالجة الأزرار والعمليات"""
    user_id = event.sender_id
    data = event.data.decode('utf-8')
    
    if data == 'start_transfer':
        await start_transfer(event)
    
    elif data == 'process_settings':
        await show_process_settings(event)
    
    elif data == 'transfer_status':
        await show_transfer_status(event)
    
    elif data == 'pause_transfer':
        await pause_transfer(event)
    
    elif data == 'resume_transfer':
        await resume_transfer(event)
    
    elif data == 'stop_transfer':
        await stop_transfer(event)
    
    elif data == 'show_stats':
        await show_statistics(event)
    
    elif data == 'show_help':
        await show_help(event)
    
    elif data == 'clear_data':
        await clear_user_data(event)
    
    elif data == 'back_to_main':
        await start(event)
    
    elif data == 'back_to_settings':
        await show_process_settings(event)
    
    elif data == 'phone_login':
        await start_phone_login(event)
    
    elif data == 'set_delay':
        await set_delay(event)
    
    elif data == 'set_source':
        await set_source(event)
    
    elif data == 'set_target':
        await set_target(event)
    
    elif data == 'set_member_limit':
        await set_member_limit(event)
    
    elif data == 'view_settings':
        await view_current_settings(event)
    
    elif data.startswith('delay_'):
        delay = int(data.split('_')[1])
        if user_id in user_sessions:
            user_sessions[user_id]['delay'] = max(100, delay)
            await event.edit(f"✅ {get_random_emoji()} تم تعيين التأخير بين الدعوات إلى {user_sessions[user_id]['delay']} ثانية")
            await show_process_settings(event)
    
    elif data.startswith('limit_'):
        limit = int(data.split('_')[1])
        if user_id in user_sessions:
            user_sessions[user_id]['member_limit'] = limit
            await event.edit(f"✅ {get_random_emoji()} تم تعيين الحد الأقصى للأعضاء إلى {limit}")
            await show_process_settings(event)
    
    elif data == 'confirm_start':
        await confirm_start(event)
    
    elif data == 'cancel_transfer':
        if user_id in user_states:
            user_states[user_id] = 'MAIN_MENU'
        await event.edit(f"❌ {get_random_emoji()} تم إلغاء العملية")
        await start(event)
    
    elif data == 'start_now':
        await start_transfer_now(event)

async def start_transfer(event):
    """بدء عملية النقل"""
    user_id = event.sender_id
    
    # التحقق من إعداد جميع المتطلبات
    required_settings = ['phone', 'source', 'target']
    if user_id not in user_sessions or not all(key in user_sessions[user_id] for key in required_settings):
        await event.answer("❌ يجب إعداد جميع المتطلبات أولاً من خلال 'إعداد العملية'", alert=True)
        return
    
    user_data = user_sessions[user_id]
    
    # تأكيد البدء
    keyboard = [
        [Button.inline(f"{get_random_emoji()} نعم، ابدأ", "confirm_start"),
         Button.inline(f"{get_random_emoji()} لا، إلغاء", "cancel_transfer")]
    ]
    
    delay = user_data.get('delay', 100)
    limit = user_data.get('member_limit', 'لا حدود')
    
    await event.edit(
        f"⚠️ {get_random_emoji()} **تحذير أخير**\n\n"
        "أنت على وشك بدء عملية نقل الأعضاء:\n\n"
        f"• من: {user_data['source']}\n"
        f"• إلى: {user_data['target']}\n"
        f"• التأخير: {delay} ثانية\n"
        f"• الحد الأقصى: {limit} عضو\n\n"
        "تيليجرام قد يحظر حسابك مؤقتاً إذا:\n"
        "• أضفت أكثر من 50-100 عضو في اليوم\n"
        "• أضفت أعضاء بسرعة كبيرة\n\n"
        "هل أنت متأكد من أنك تريد المتابعة؟",
        buttons=keyboard
    )

async def show_process_settings(event):
    """عرض إعدادات العملية"""
    user_id = event.sender_id
    user_data = user_sessions.get(user_id, {})
    
    # إنشاء لوحة المفاتيح للإعدادات
    keyboard = [
        [Button.inline(f"{get_random_emoji()} تسجيل الدخول", "phone_login")],
        [Button.inline(f"{get_random_emoji()} تعيين المصدر", "set_source")],
        [Button.inline(f"{get_random_emoji()} تعيين الهدف", "set_target")],
        [Button.inline(f"{get_random_emoji()} تعيين الفاصل الزمني", "set_delay")],
        [Button.inline(f"{get_random_emoji()} تعيين عدد الأعضاء", "set_member_limit")],
        [Button.inline(f"{get_random_emoji()} عرض الإعدادات الحالية", "view_settings")],
        [Button.inline(f"{get_random_emoji()} العودة للرئيسية", "back_to_main")]
    ]
    
    status_text = f"⚙️ {get_random_emoji()} **إعدادات العملية**\n\n"
    status_text += "هنا يمكنك تعديل جميع إعدادات عملية النقل:\n\n"
    
    # عرض حالة الإعدادات الحالية
    status_text += f"• 📱 تسجيل الدخول: {'✅ مكتمل' if 'phone' in user_data else '❌ غير مكتمل'}\n"
    status_text += f"• 📥 المصدر: {'✅ مكتمل' if 'source' in user_data else '❌ غير مكتمل'}\n"
    status_text += f"• 📤 الهدف: {'✅ مكتمل' if 'target' in user_data else '❌ غير مكتمل'}\n"
    status_text += f"• ⏱ الفاصل الزمني: {user_data.get('delay', '❌ غير محدد')} ثانية\n"
    status_text += f"• 👥 عدد الأعضاء: {user_data.get('member_limit', '❌ غير محدد')}\n\n"
    
    status_text += "اختر الإعداد الذي تريد تعديله:"
    
    await event.edit(status_text, buttons=keyboard)

async def start_phone_login(event):
    """بدء عملية تسجيل الدخول برقم الهاتف"""
    user_id = event.sender_id
    user_states[user_id] = 'AWAITING_PHONE'
    
    keyboard = [[Button.inline("❌ إلغاء", "cancel_transfer")]]
    
    await event.edit(
        "📱 **تسجيل الدخول برقم الهاتف**\n\n"
        "أرسل رقم هاتفك مع مفتاح الدولة.\n\n"
        "📋 أمثلة:\n"
        "• +1234567890 (للهاتف الأمريكي)\n"
        "• +442071234567 (للهاتف البريطاني)\n"
        "• +966512345678 (للهاتف السعودي)\n\n"
        "⚠️ تأكد من إضافة رمز الدولة قبل رقم هاتفك",
        buttons=keyboard
    )

@bot.on(events.NewMessage)
async def handle_messages(event):
    """معالجة الرسائل النصية من المستخدم"""
    user_id = event.sender_id
    text = event.text.strip()
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    
    if state == 'AWAITING_PHONE':
        await handle_phone_input(event, text)
    
    elif state == 'AWAITING_CODE':
        await handle_code_input(event, text)
    
    elif state == 'AWAITING_PASSWORD':
        await handle_password_input(event, text)
    
    elif state == 'AWAITING_SOURCE':
        await handle_source_input(event, text)
    
    elif state == 'AWAITING_TARGET':
        await handle_target_input(event, text)

async def handle_phone_input(event, text):
    """معالجة إدخال رقم الهاتف"""
    user_id = event.sender_id
    
    # التحقق من صحة رقم الهاتف
    if not re.match(r'^\+\d{8,15}$', text):
        await event.reply("❌ رقم الهاتف غير صحيح. يرجى إدخال رقم هاتف صحيح مع رمز الدولة.\n\nمثال: +1234567890")
        return
    
    try:
        # إنشاء عميل جديد باستخدام MemorySession
        client = TelegramClient(MemorySession(), API_ID, API_HASH)
        
        # حفظ العميل في الذاكرة
        phone_code_requests[user_id] = {
            'client': client,
            'phone': text
        }
        
        # طلب إرسال الرمز
        await client.connect()
        sent_code = await client.send_code_request(text)
        
        user_states[user_id] = 'AWAITING_CODE'
        user_sessions[user_id] = {
            'phone': text,
            'phone_code_hash': sent_code.phone_code_hash
        }
        
        keyboard = [[Button.inline("❌ إلغاء", "cancel_transfer")]]
        
        await event.reply(
            "✅ **تم إرسال رمز التحقق**\n\n"
            "أرسل رمز التحقق الذي استلمته على Telegram.\n\n"
            "📝 إذا لم تستلم الرمز:\n"
            "• تأكد من أن رقم الهاتف صحيح\n"
            "• حاول إعادة إرسال الرمح باستخدام /start\n"
            "• قد تستغرق الرسالة عدة دقائق للوصول",
            buttons=keyboard
        )
        
    except Exception as e:
        await event.reply(f"❌ خطأ في إرسال رمز التحقق: {str(e)}\n\nيرجى المحاولة مرة أخرى.")
        if user_id in phone_code_requests:
            try:
                await phone_code_requests[user_id]['client'].disconnect()
            except:
                pass
            del phone_code_requests[user_id]

async def handle_code_input(event, text):
    """معالجة إدخال رمز التحقق"""
    user_id = event.sender_id
    
    if user_id not in user_sessions or 'phone_code_hash' not in user_sessions[user_id]:
        await event.reply("❌ لم يتم إعداد عملية تسجيل الدخول. يرجى البدء من /start")
        return
    
    if user_id not in phone_code_requests:
        await event.reply("❌ انتهت صلاحية جلسة التسجيل. يرجى البدء من /start")
        return
    
    try:
        # تسجيل الدخول باستخدام الرمز
        client = phone_code_requests[user_id]['client']
        phone = user_sessions[user_id]['phone']
        phone_code_hash = user_sessions[user_id]['phone_code_hash']
        
        # محاولة تسجيل الدخول
        await client.sign_in(
            phone=phone,
            code=text,
            phone_code_hash=phone_code_hash
        )
        
        # التحقق من نجاح تسجيل الدخول
        me = await client.get_me()
        
        # حفظ بيانات الجلسة
        user_sessions[user_id]['client'] = client
        user_sessions[user_id]['user_id'] = me.id
        user_sessions[user_id]['username'] = me.username
        user_sessions[user_id]['first_name'] = me.first_name
        
        # تنظيف طلبات الرمز
        if user_id in phone_code_requests:
            del phone_code_requests[user_id]
        
        user_states[user_id] = 'LOGGED_IN'
        
        await event.reply(
            f"✅ **تم تسجيل الدخول بنجاح!**\n\n"
            f"مرحباً {me.first_name or ''}!\n\n"
            f"• 👤 اسم المستخدم: @{me.username or 'غير متاح'}\n"
            f"• 📞 رقم الهاتف: {phone}\n"
            f"• 🆔 ID: {me.id}\n\n"
            "الآن يمكنك بدء عملية نقل الأعضاء."
        )
        
        # الانتقال إلى خطوة إدخال المصدر
        user_states[user_id] = 'AWAITING_SOURCE'
        keyboard = [[Button.inline("❌ إلغاء", "cancel_transfer")]]
        
        await event.reply(
            "📥 **الخطوة 1 من 2: إدخال المصدر**\n\n"
            "أرسل رابط المجموعة المصدر (التي تريد نقل الأعضاء منها):\n\n"
            "⚠️ يجب أن تكون مسؤولاً في هذه المجموعة",
            buttons=keyboard
        )
        
    except errors.SessionPasswordNeededError:
        # إذا كان الحساب محمياً بكلمة مرور
        user_states[user_id] = 'AWAITING_PASSWORD'
        await event.reply("🔐 هذا الحساب محمي بكلمة مرور. أرسل كلمة المرور للمتابعة:")
    
    except errors.PhoneCodeInvalidError:
        await event.reply("❌ رمز التحقق غير صحيح. أرسل الرمز الصحيح:")
    
    except errors.PhoneCodeExpiredError:
        await event.reply("❌ انتهت صلاحية رمز التحقق. يرجى البدء من /start")
        if user_id in phone_code_requests:
            del phone_code_requests[user_id]
        if user_id in user_sessions:
            del user_sessions[user_id]
        user_states[user_id] = 'MAIN_MENU'
    
    except Exception as e:
        await event.reply(f"❌ خطأ في تسجيل الدخول: {str(e)}\n\nيرجى المحاولة مرة أخرى باستخدام /start")
        if user_id in phone_code_requests:
            del phone_code_requests[user_id]
        if user_id in user_sessions:
            del user_sessions[user_id]
        user_states[user_id] = 'MAIN_MENU'

async def handle_password_input(event, text):
    """معالجة إدخال كلمة المرور"""
    user_id = event.sender_id
    
    if user_id not in phone_code_requests:
        await event.reply("❌ انتهت صلاحية جلسة التسجيل. يرجى البدء من /start")
        return
    
    try:
        client = phone_code_requests[user_id]['client']
        
        # تسجيل الدخول باستخدام كلمة المرور
        await client.sign_in(password=text)
        
        # التحقق من نجاح تسجيل الدخول
        me = await client.get_me()
        phone = user_sessions[user_id]['phone']
        
        # حفظ بيانات الجلسة
        user_sessions[user_id]['client'] = client
        user_sessions[user_id]['user_id'] = me.id
        user_sessions[user_id]['username'] = me.username
        user_sessions[user_id]['first_name'] = me.first_name
        
        # تنظيف طلبات الرمز
        if user_id in phone_code_requests:
            del phone_code_requests[user_id]
        
        user_states[user_id] = 'LOGGED_IN'
        
        await event.reply(
            f"✅ **تم تسجيل الدخول بنجاح!**\n\n"
            f"مرحباً {me.first_name or ''}!\n\n"
            f"• 👤 اسم المستخدم: @{me.username or 'غير متاح'}\n"
            f"• 📞 رقم الهاتف: {phone}\n"
            f"• 🆔 ID: {me.id}\n\n"
            "الآن يمكنك بدء عملية نقل الأعضاء."
        )
        
        # الانتقال إلى خطوة إdخال المصدر
        user_states[user_id] = 'AWAITING_SOURCE'
        keyboard = [[Button.inline("❌ إلغاء", "cancel_transfer")]]
        
        await event.reply(
            "📥 **الخطوة 1 من 2: إدخال المصدر**\n\n"
            "أرسل رابط المجموعة المصدر (التي تريد نقل الأعضاء منها):\n\n"
            "⚠️ يجب أن تكون مسؤولاً في هذه المجموعة",
            buttons=keyboard
        )
        
    except errors.PasswordHashInvalidError:
        await event.reply("❌ كلمة المرور غير صحيحة. أرسل كلمة المرور الصحيحة:")
    
    except Exception as e:
        await event.reply(f"❌ خطأ في تسجيل الدخول: {str(e)}\n\nيرجى المحاولة مرة أخرى باستخدام /start")
        if user_id in phone_code_requests:
            del phone_code_requests[user_id]
        if user_id in user_sessions:
            del user_sessions[user_id]
        user_states[user_id] = 'MAIN_MENU'

async def handle_source_input(event, text):
    """معالجة إدخال المصدر"""
    user_id = event.sender_id
    
    # التحقق من أن المستخدم سجل الدخول
    if user_id not in user_sessions or 'client' not in user_sessions[user_id]:
        await event.reply("❌ لم يتم تسجيل الدخول. يرجى البدء من /start")
        user_states[user_id] = 'MAIN_MENU'
        return
    
    user_sessions[user_id]['source'] = text
    user_states[user_id] = 'AWAITING_TARGET'
    
    keyboard = [[Button.inline("❌ إلغاء", "cancel_transfer")]]
    
    await event.reply(
        "✅ **تم حفظ المصدر بنجاح!**\n\n"
        "📥 **الخطوة 2 من 2: إدخال الهدف**\n\n"
        "أرسل رابط المجموعة الهدف (التي تريد نقل الأعضاء إليها):\n\n"
        "⚠️ يجب أن تكون مسؤولاً في هذه المجموعة",
        buttons=keyboard
    )

async def handle_target_input(event, text):
    """معالجة إدخال الهدف وبدء النقل"""
    user_id = event.sender_id
    
    # التحقق من أن المستخدم سجل الدخول
    if user_id not in user_sessions or 'client' not in user_sessions[user_id]:
        await event.reply("❌ لم يتم تسجيل الدخول. يرجى البدء من /start")
        user_states[user_id] = 'MAIN_MENU'
        return
    
    user_sessions[user_id]['target'] = text
    user_states[user_id] = 'READY'
    
    # عرض خيارات التأخير
    keyboard = [
        [Button.inline(f"{get_random_emoji()} 100 ثانية", "delay_100"), 
         Button.inline(f"{get_random_emoji()} 120 ثانية", "delay_120")],
        [Button.inline(f"{get_random_emoji()} 150 ثانية", "delay_150"), 
         Button.inline(f"{get_random_emoji()} 180 ثانية", "delay_180")],
        [Button.inline(f"{get_random_emoji()} بدء النقل الآن", "start_now"),
         Button.inline(f"{get_random_emoji()} إلغاء", "cancel_transfer")]
    ]
    
    await event.reply(
        "✅ **تم إعداد البيانات بنجاح!**\n\n"
        "📋 **البيانات المدخلة:**\n"
        f"• المصدر: {user_sessions[user_id]['source']}\n"
        f"• الهدف: {user_sessions[user_id]['target']}\n\n"
        "⏱ **اختر الوقت بين كل دعوة:**\n"
        "• وقت أقل = نقل أسرع ولكن خطر حظر أعلى\n"
        "• وقت أكثر = نقل أبطأ ولكن أكثر أماناً\n\n"
        "الوقت المقترح: 120-150 ثانية\n\n"
        "⚠️ الحد الأدنى هو 100 ثانية لتجنب الحظر",
        buttons=keyboard
    )

async def start_transfer_now(event):
    """بدء عملية النقل"""
    user_id = event.sender_id
    
    if user_id not in user_sessions or user_states.get(user_id) != 'READY':
        await event.edit("❌ لم يتم إعداد البيانات بعد. يرجى البدء من /start")
        return
    
    user_data = user_sessions[user_id]
    
    # تأكيد البدء
    keyboard = [
        [Button.inline(f"{get_random_emoji()} نعم، ابدأ", "confirm_start"),
         Button.inline(f"{get_random_emoji()} لا، إلغاء", "cancel_transfer")]
    ]
    
    delay = user_data.get('delay', 100)
    limit = user_data.get('member_limit', 'لا حدود')
    
    await event.edit(
        f"⚠️ {get_random_emoji()} **تحذير أخير**\n\n"
        "أنت على وشك بدء عملية نقل الأعضاء:\n\n"
        f"• من: {user_data['source']}\n"
        f"• إلى: {user_data['target']}\n"
        f"• التأخير: {delay} ثانية\n"
        f"• الحد الأقصى: {limit} عضو\n\n"
        "تيليجرام قد يحظر حسابك مؤقتاً إذا:\n"
        "• أضفت أكثر من 50-100 عضو في اليوم\n"
        "• أضفت أعضاء بسرعة كبيرة\n\n"
        "هل أنت متأكد من أنك تريد المتابعة؟",
        buttons=keyboard
    )

async def confirm_start(event):
    """تأكيد بدء النقل"""
    user_id = event.sender_id
    user_data = user_sessions[user_id]
    
    # تغيير الحالة إلى نقل
    user_states[user_id] = 'TRANSFERRING'
    
    # إنشاء مهمة النقل
    transfer_task = asyncio.create_task(execute_transfer(user_id, event))
    transfer_tasks[user_id] = {
        'task': transfer_task,
        'start_time': datetime.now(),
        'status': 'running',
        'added': 0,
        'errors': 0,
        'skipped': 0,
        'privacy_restricted': 0,
        'already_member': 0,
        'last_update': datetime.now()
    }
    
    # لوحة المفاتيح للتحكم في النقل
    keyboard = [
        [Button.inline(f"{get_random_emoji()} إيقاف مؤقت", "pause_transfer"),
         Button.inline(f"{get_random_emoji()} إيقاف", "stop_transfer")],
        [Button.inline(f"{get_random_emoji()} الحالة", "transfer_status")]
    ]
    
    await event.edit(
        f"🟢 {get_random_emoji()} **بدأت عملية النقل**\n\n"
        "جاري بدء نقل الأعضاء. هذه العملية قد تستغرق وقتاً طويلاً.\n\n"
        "يمكنك متابعة التقدم أو التحكم في العملية باستخدام الأزرار أدناه.",
        buttons=keyboard
    )

async def update_progress_message(user_id, event, current, total, added, skipped, already_member, privacy_restricted, errors, delay):
    """تحديث رسالة التقدم بدلاً من إرسال رسائل جديدة"""
    progress = (current + 1) / total * 100
    
    if user_id not in progress_messages:
        # إنشاء رسالة التقدم الأولى
        progress_msg = await event.reply(
            f"📊 {get_random_emoji()} **تقدم النقل**\n\n"
            f"• 📈 التقدم: {current+1}/{total} ({progress:.1f}%)\n"
            f"• ✅ تمت إضافة: {added} عضو\n"
            f"• ⚠️ تم تخطي: {skipped} عضو\n"
            f"• 🔄 موجود مسبقاً: {already_member} عضو\n"
            f"• 🚫 محظور: {privacy_restricted} عضو\n"
            f"• ❌ أخطاء: {errors} عضو\n"
            f"• ⏱ التأخير: {delay} ثانية"
        )
        progress_messages[user_id] = progress_msg
    else:
        # تحديث الرسالة الموجودة
        try:
            await progress_messages[user_id].edit(
                f"📊 {get_random_emoji()} **تقدم النقل**\n\n"
                f"• 📈 التقدم: {current+1}/{total} ({progress:.1f}%)\n"
                f"• ✅ تمت إضافة: {added} عضو\n"
                f"• ⚠️ تم تخطي: {skipped} عضو\n"
                f"• 🔄 موجود مسبقاً: {already_member} عضو\n"
                f"• 🚫 محظور: {privacy_restricted} عضو\n"
                f"• ❌ أخطاء: {errors} عضو\n"
                f"• ⏱ التأخير: {delay} ثانية"
            )
        except:
            # إذا فشل التحديث، إنشاء رسالة جديدة
            progress_msg = await event.reply(
                f"📊 {get_random_emoji()} **تقدم النقل**\n\n"
                f"• 📈 التقدم: {current+1}/{total} ({progress:.1f}%)\n"
                f"• ✅ تمت إضافة: {added} عضو\n"
                f"• ⚠️ تم تخطي: {skipped} عضو\n"
                f"• 🔄 موجود مسبقاً: {already_member} عضو\n"
                f"• 🚫 محظور: {privacy_restricted} عضو\n"
                f"• ❌ أخطاء: {errors} عضو\n"
                f"• ⏱ التأخير: {delay} ثانية"
            )
            progress_messages[user_id] = progress_msg

async def execute_transfer(user_id, event):
    """تنفيذ عملية نقل الأعضاء"""
    user_data = user_sessions.get(user_id)
    task_data = transfer_tasks.get(user_id)
    
    if not user_data or not task_data:
        return
    
    try:
        client = user_data['client']
        
        # إرسال رسالة بدء الحصول على الأعضاء
        await event.reply(f"🔍 {get_random_emoji()} **جاري الحصول على قائمة الأعضاء...**")
        
        # الحصول على كيانات المجموعات
        source_entity = await client.get_entity(user_data['source'])
        target_entity = await client.get_entity(user_data['target'])
        
        # جلب الأعضاء
        members = await client.get_participants(source_entity)
        
        if not members:
            await event.reply(f"❌ {get_random_emoji()} لم يتم العثور على أعضاء في المجموعة المصدر")
            return
        
        total_members = len(members)
        member_limit = user_data.get('member_limit', total_members)
        actual_limit = min(total_members, member_limit)
        delay = max(100, user_data.get('delay', 100))  # الحد الأدنى 100 ثانية
        
        await event.reply(
            f"✅ {get_random_emoji()} **تم العثور على {total_members} عضو**\n\n"
            f"• 📊 سيتم نقل: {actual_limit} عضو\n"
            f"• ⏱ التأخير: {delay} ثانية\n"
            f"• 🚀 بدء النقل..."
        )
        
        # نقل الأعضاء
        for i, member in enumerate(members[:actual_limit]):
            if user_states.get(user_id) != 'TRANSFERRING':
                break
            
            try:
                # تخطي البوتات والحسابات المحذوفة
                if member.bot or member.deleted:
                    task_data['skipped'] += 1
                    continue
                
                # تحديث رسالة التقدم كل 5 أعضاء
                if i % 5 == 0:
                    await update_progress_message(
                        user_id, event, i, actual_limit, 
                        task_data['added'], task_data['skipped'],
                        task_data['already_member'], task_data['privacy_restricted'],
                        task_data['errors'], delay
                    )
                
                # دعوة العضو
                await client(functions.channels.InviteToChannelRequest(
                    channel=target_entity,
                    users=[member]
                ))
                
                task_data['added'] += 1
                task_data['last_update'] = datetime.now()
                
                # تأخير بين الدعوات (100 ثانية على الأقل)
                await asyncio.sleep(delay)
                
            except errors.FloodWaitError as e:
                task_data['errors'] += 1
                await event.reply(f"⏳ {get_random_emoji()} تم حظرك مؤقتاً لمدة {e.seconds} ثانية. جاري الانتظار...")
                await asyncio.sleep(e.seconds)
                # إعادة المحاولة بعد الانتظار
                try:
                    await client(functions.channels.InviteToChannelRequest(
                        channel=target_entity,
                        users=[member]
                    ))
                    task_data['added'] += 1
                except:
                    task_data['errors'] += 1
                    
            except errors.UserPrivacyRestrictedError:
                task_data['privacy_restricted'] += 1
                await event.reply(f"🚫 {get_random_emoji()} العضو {member.id} يمنع إضافته إلى المجموعات")
                
            except errors.UserAlreadyParticipantError:
                task_data['already_member'] += 1
                
            except Exception as e:
                task_data['errors'] += 1
                await event.reply(f"❌ {get_random_emoji()} خطأ مع العضو {member.id}: {str(e)}")
                # زيادة التأخير عند حدوث أخطاء
                new_delay = delay + 30
                user_sessions[user_id]['delay'] = new_delay
                await event.reply(f"⚠️ {get_random_emoji()} تم زيادة التأخير إلى {new_delay} ثانية بسبب الأخطاء")
                delay = new_delay
        
        # تحديث رسالة التقدم النهائية
        await update_progress_message(
            user_id, event, actual_limit, actual_limit, 
            task_data['added'], task_data['skipped'],
            task_data['already_member'], task_data['privacy_restricted'],
            task_data['errors'], delay
        )
        
        # إرسال تقرير النهائي
        end_time = datetime.now()
        duration = end_time - task_data['start_time']
        
        await event.reply(
            f"✅ {get_random_emoji()} **تم الانتهاء من عملية النقل!**\n\n"
            f"• 📊 الإجمالي: {actual_limit} عضو\n"
            f"• ✅ تمت إضافة: {task_data['added']} عضو\n"
            f"• ⚠️ تم تخطي: {task_data['skipped']} عضو\n"
            f"• 🔄 موجود مسبقاً: {task_data['already_member']} عضو\n"
            f"• 🚫 محظور: {task_data['privacy_restricted']} عضو\n"
            f"• ❌ أخطاء: {task_data['errors']} عضو\n"
            f"• ⏱ المدة: {duration}\n\n"
            f"🔐 {get_random_emoji()} **تم حذف بيانات الجلسة لحماية حسابك**\n"
            f"لبدء عملية جديدة، استخدم /start"
        )
        
    except Exception as e:
        await event.reply(f"❌ {get_random_emoji()} حدث خطأ أثناء النقل: {str(e)}\n\nجرب مرة أخرى باستخدام /start")
    finally:
        # تنظيف البيانات في جميع الأحوال
        if user_id in user_sessions:
            if 'client' in user_sessions[user_id]:
                try:
                    await user_sessions[user_id]['client'].disconnect()
                except:
                    pass
            del user_sessions[user_id]
        
        if user_id in user_states:
            del user_states[user_id]
        
        if user_id in transfer_tasks:
            del transfer_tasks[user_id]
        
        if user_id in progress_messages:
            del progress_messages[user_id]

async def show_transfer_status(event):
    """عرض حالة النقل الحالي"""
    user_id = event.sender_id
    
    if user_id not in transfer_tasks:
        await event.answer("لا توجد عملية نقل نشطة حالياً", alert=True)
        return
    
    task_data = transfer_tasks[user_id]
    duration = datetime.now() - task_data['start_time']
    since_last_update = datetime.now() - task_data['last_update']
    
    status_message = (
        f"📊 {get_random_emoji()} **حالة النقل الحالية**\n\n"
        f"• 🟢 الحالة: {task_data['status']}\n"
        f"• ✅ تمت إضافة: {task_data['added']} عضو\n"
        f"• ⚠️ تم تخطي: {task_data['skipped']} عضو\n"
        f"• 🔄 موجود مسبقاً: {task_data['already_member']} عضو\n"
        f"• 🚫 محظور: {task_data['privacy_restricted']} عضو\n"
        f"• ❌ أخطاء: {task_data['errors']} عضو\n"
        f"• ⏱ المدة: {duration}\n"
        f"• 🕒 آخر تحديث: منذ {since_last_update.seconds} ثانية\n\n"
    )
    
    if user_id in user_sessions and 'delay' in user_sessions[user_id]:
        status_message += f"• ⏱ التأخير: {user_sessions[user_id]['delay']} ثانية\n"
    
    keyboard = [
        [Button.inline(f"{get_random_emoji()} تحديث", "transfer_status")],
        [Button.inline(f"{get_random_emoji()} العودة", "back_to_main")]
    ]
    
    await event.edit(status_message, buttons=keyboard)

async def pause_transfer(event):
    """إيقاف النقل مؤقتاً"""
    user_id = event.sender_id
    
    if user_id not in transfer_tasks:
        await event.answer("لا توجد عملية نقل نشطة حالياً", alert=True)
        return
    
    if user_states.get(user_id) == 'PAUSED':
        await event.answer("النقل متوقف بالفعل", alert=True)
        return
    
    user_states[user_id] = 'PAUSED'
    transfer_tasks[user_id]['status'] = 'paused'
    
    keyboard = [
        [Button.inline(f"{get_random_emoji()} استئناف", "resume_transfer")],
        [Button.inline(f"{get_random_emoji()} إيقاف", "stop_transfer")]
    ]
    
    await event.edit(f"⏸ {get_random_emoji()} **تم إيقاف النقل مؤقتاً**\n\nاستخدم الأزرار أدناه للتحكم:", buttons=keyboard)

async def resume_transfer(event):
    """استئناف النقل بعد الإيقاف المؤقت"""
    user_id = event.sender_id
    
    if user_id not in transfer_tasks:
        await event.answer("لا توجد عملية نقل نشطة حالياً", alert=True)
        return
    
    if user_states.get(user_id) != 'PAUSED':
        await event.answer("النقل ليس متوقفاً", alert=True)
        return
    
    user_states[user_id] = 'TRANSFERRING'
    transfer_tasks[user_id]['status'] = 'running'
    
    keyboard = [
        [Button.inline(f"{get_random_emoji()} إيقاف مؤقت", "pause_transfer"),
         Button.inline(f"{get_random_emoji()} إيقاف", "stop_transfer")],
        [Button.inline(f"{get_random_emoji()} الحالة", "transfer_status")]
    ]
    
    await event.edit(f"🟢 {get_random_emoji()} **تم استئناف النقل**\n\nجاري متابعة عملية نقل الأعضاء...", buttons=keyboard)

async def stop_transfer(event):
    """إيقاف النقل completely"""
    user_id = event.sender_id
    
    if user_id not in transfer_tasks:
        await event.answer("لا توجد عملية نقل نشطة حالياً", alert=True)
        return
    
    # تغيير الحالة لإيقاف النقل
    user_states[user_id] = 'STOPPED'
    transfer_tasks[user_id]['status'] = 'stopped'
    
    # إلغاء المهمة إذا كانت لا تزال تعمل
    if not transfer_tasks[user_id]['task'].done():
        transfer_tasks[user_id]['task'].cancel()
    
    # جمع الإحصائيات
    task_data = transfer_tasks[user_id]
    duration = datetime.now() - task_data['start_time']
    
    await event.edit(
        f"⏹ {get_random_emoji()} **تم إيقاف النقل**\n\n"
        f"• ✅ تمت إضافة: {task_data['added']} عضو\n"
        f"• ❌ أخطاء: {task_data['errors']} عضو\n"
        f"• ⏱ المدة: {duration}\n\n"
        "لبدء عملية جديدة، استخدم /start"
    )
    
    # تنظيف البيانات
    if user_id in user_sessions:
        if 'client' in user_sessions[user_id]:
            try:
                await user_sessions[user_id]['client'].disconnect()
            except:
                pass
        del user_sessions[user_id]
    
    if user_id in user_states:
        del user_states[user_id]
    
    if user_id in transfer_tasks:
        del transfer_tasks[user_id]
    
    if user_id in progress_messages:
        del progress_messages[user_id]

async def show_statistics(event):
    """عرض الإحصائيات العامة"""
    total_transfers = len(transfer_tasks)
    active_transfers = sum(1 for task in transfer_tasks.values() if task['status'] == 'running')
    
    keyboard = [[Button.inline(f"{get_random_emoji()} العودة", "back_to_main")]]
    
    await event.edit(
        f"📈 {get_random_emoji()} **إحصائيات البوت**\n\n"
        f"• 🔄 إجمالي عمليات النقل: {total_transfers}\n"
        f"• 🟢 العمليات النشطة: {active_transfers}\n"
        f"• 👥 المستخدمون النشطون: {len(user_sessions)}\n\n"
        "ℹ️ هذه الإحصائيات منذ آخر تشغيل للبوت",
        buttons=keyboard
    )

async def show_help(event):
    """عرض تعليمات المساعدة"""
    keyboard = [[Button.inline(f"{get_random_emoji()} العودة", "back_to_main")]]
    
    await event.edit(
        f"❓ {get_random_emoji()} **مساعدة واستفسارات**\n\n"
        "🔷 **كيفية الاستخدام:**\n"
        "1. اضغط على 'تسجيل الدخول برقم الهاتف'\n"
        "2. أرسل رقم هاتفك مع رمز الدولة\n"
        "3. أرسل رمز التحقق الذي استلمته\n"
        "4. أدخل رابط المجموعة المصدر والهدف\n"
        "5. اختر وقت التأخير بين الدعوات\n"
        "6. ابدأ عملية النقل\n\n"
        "⚠️ **نصائح مهمة:**\n"
        "• استخدم تأخير 100-150 ثانية لتجنب الحظر\n"
        "• لا تنقل أكثر من 50-100 عضو في اليوم\n"
        "• تأكد من أنك مسؤول في المجموعتين\n\n"
        "📊 **التحكم في العملية:**\n"
        "• يمكنك إيقاف النقل مؤقتاً أو إيقافه\n"
        "• يمكنك متابعة التقدم في أي وقت\n\n"
        "للأسئلة التقنية: @NPPJN",
        buttons=keyboard
    )

async def clear_user_data(event):
    """مسح بيانات المستخدم"""
    user_id = event.sender_id
    
    if user_id in user_sessions:
        if 'client' in user_sessions[user_id]:
            try:
                await user_sessions[user_id]['client'].disconnect()
            except:
                pass
        del user_sessions[user_id]
    
    if user_id in user_states:
        del user_states[user_id]
    
    if user_id in transfer_tasks:
        if not transfer_tasks[user_id]['task'].done():
            transfer_tasks[user_id]['task'].cancel()
        del transfer_tasks[user_id]
    
    if user_id in phone_code_requests:
        if 'client' in phone_code_requests[user_id]:
            try:
                await phone_code_requests[user_id]['client'].disconnect()
            except:
                pass
        del phone_code_requests[user_id]
    
    if user_id in progress_messages:
        del progress_messages[user_id]
    
    await event.edit(f"✅ {get_random_emoji()} **تم مسح جميع بياناتك بنجاح**\n\nلبدء جلسة جديدة، استخدم /start")
    await start(event)

async def set_delay(event):
    """تعيين الفاصل الزمني"""
    user_id = event.sender_id
    
    keyboard = [
        [Button.inline(f"{get_random_emoji()} 100 ثانية", "delay_100"), 
         Button.inline(f"{get_random_emoji()} 120 ثانية", "delay_120")],
        [Button.inline(f"{get_random_emoji()} 150 ثانية", "delay_150"), 
         Button.inline(f"{get_random_emoji()} 180 ثانية", "delay_180")],
        [Button.inline(f"{get_random_emoji()} العودة للإعدادات", "back_to_settings")]
    ]
    
    await event.edit(
        f"⏱ {get_random_emoji()} **تعيين الفاصل الزمني**\n\n"
        "اختر الوقت بين كل دعوة:\n\n"
        "• وقت أقل = نقل أسرع ولكن خطر حظر أعلى\n"
        "• وقت أكثر = نقل أبطأ ولكن أكثر أماناً\n\n"
        "الوقت المقترح: 120-150 ثانية\n\n"
        "⚠️ الحد الأدنى هو 100 ثانية لتجنب الحظر",
        buttons=keyboard
    )

async def set_source(event):
    """تعيين المصدر"""
    user_id = event.sender_id
    
    if user_id not in user_sessions or 'client' not in user_sessions[user_id]:
        await event.answer("يجب تسجيل الدخول أولاً", alert=True)
        return
    
    user_states[user_id] = 'AWAITING_SOURCE'
    
    keyboard = [[Button.inline("❌ إلغاء", "cancel_transfer")]]
    
    await event.edit(
        "📥 **إدخال المصدر**\n\n"
        "أرسل رابط المجموعة المصدر (التي تريد نقل الأعضاء منها):\n\n"
        "⚠️ يجب أن تكون مسؤولاً في هذه المجموعة",
        buttons=keyboard
    )

async def set_target(event):
    """تعيين الهدف"""
    user_id = event.sender_id
    
    if user_id not in user_sessions or 'source' not in user_sessions[user_id]:
        await event.answer("يجب تعيين المصدر أولاً", alert=True)
        return
    
    user_states[user_id] = 'AWAITING_TARGET'
    
    keyboard = [[Button.inline("❌ إلغاء", "cancel_transfer")]]
    
    await event.edit(
        "📤 **إدخال الهدف**\n\n"
        "أرسل رابط المجموعة الهدف (التي تريد نقل الأعضاء إليها):\n\n"
        "⚠️ يجب أن تكون مسؤولاً في هذه المجموعة",
        buttons=keyboard
    )

async def set_member_limit(event):
    """تعيين عدد الأعضاء"""
    user_id = event.sender_id
    
    keyboard = [
        [Button.inline(f"{get_random_emoji()} 30 عضو", "limit_30"),
         Button.inline(f"{get_random_emoji()} 50 عضو", "limit_50")],
        [Button.inline(f"{get_random_emoji()} 80 عضو", "limit_80"),
         Button.inline(f"{get_random_emoji()} 100 عضو", "limit_100")],
        [Button.inline(f"{get_random_emoji()} لا حدود", "limit_0"),
         Button.inline(f"{get_random_emoji()} العودة", "back_to_settings")]
    ]
    
    await event.edit(
        f"👥 {get_random_emoji()} **تعيين عدد الأعضاء**\n\n"
        "اختر الحد الأقصى لعدد الأعضاء الذين تريد نقلهم:\n\n"
        "⚠️ تيليجرام قد يحظر حسابك مؤقتاً إذا:\n"
        "• أضفت أكثر من 50-100 عضو في اليوم\n"
        "• أضفت أعضاء بسرعة كبيرة\n\n"
        "العدد المقترح: 30-50 عضو في اليوم مع تأخير 100 ثانية",
        buttons=keyboard
    )

async def view_current_settings(event):
    """عرض الإعدادات الحالية"""
    user_id = event.sender_id
    user_data = user_sessions.get(user_id, {})
    
    settings_text = f"⚙️ {get_random_emoji()} **الإعدادات الحالية**\n\n"
    
    if 'phone' in user_data:
        settings_text += f"• 📱 رقم الهاتف: {user_data['phone']}\n"
    else:
        settings_text += "• 📱 رقم الهاتف: ❌ غير مضبوط\n"
    
    if 'source' in user_data:
        settings_text += f"• 📥 المصدر: {user_data['source']}\n"
    else:
        settings_text += "• 📥 المصدر: ❌ غير مضبوط\n"
    
    if 'target' in user_data:
        settings_text += f"• 📤 الهدف: {user_data['target']}\n"
    else:
        settings_text += "• 📤 الهدف: ❌ غير مضبوط\n"
    
    settings_text += f"• ⏱ الفاصل الزمني: {user_data.get('delay', '❌ غير مضبوط')} ثانية\n"
    settings_text += f"• 👥 عدد الأعضاء: {user_data.get('member_limit', '❌ غير مضبوط')}\n\n"
    
    keyboard = [[Button.inline(f"{get_random_emoji()} العودة للإعدادات", "back_to_settings")]]
    
    await event.edit(settings_text, buttons=keyboard)

if __name__ == '__main__':
    print("✅ بدء تشغيل البوت...")
    try:
        bot.start(bot_token=BOT_TOKEN)
        print("✅ تم بدء تشغيل البوت بنجاح!")
        bot.run_until_disconnected()
    except Exception as e:
        print(f"❌ خطأ في تشغيل البوت: {e}")
        # محاولة الإغلاق النظيف
        try:
            bot.disconnect()
        except:
            pass
