# main.py
import os
import json
import logging
import asyncio
from datetime import datetime
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# إعدادات البوت
BOT_TOKEN = os.getenv("7966976239:AAFEtPbUEIqMVaLN20HH49zIMVSh4jKZJA4")
API_ID = os.getenv("23656977")
API_HASH = os.getenv("49d3f43531a92b3f5bc403766313ca1e")
SESSION_DIR = "sessions"
LOG_DIR = "logs"
ACCOUNTS_FILE = "accounts.json"
TASK_FILE = "current_task.json"

# تأكد من وجود المجلدات اللازمة
os.makedirs(SESSION_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# تهيئة السجل
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# تهيئة جدولة المهام
scheduler = AsyncIOScheduler()

class AccountManager:
    """إدارة حسابات تيليجرام"""
    
    @staticmethod
    def load_accounts():
        """تحميل الحسابات من الملف"""
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    @staticmethod
    def save_accounts(accounts):
        """حفظ الحسابات إلى الملف"""
        with open(ACCOUNTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    async def add_account(phone, api_id, api_hash):
        """إضافة حساب جديد"""
        accounts = AccountManager.load_accounts()
        
        # إنشاء جلسة جديدة
        session_path = os.path.join(SESSION_DIR, f"{phone}.session")
        client = TelegramClient(session_path, api_id, api_hash)
        
        await client.connect()
        if not await client.is_user_authorized():
            try:
                await client.send_code_request(phone)
                return "code"
            except Exception as e:
                logger.error(f"خطأ في إرسال الرمز: {e}")
                return f"خطأ: {str(e)}"
        
        # الحصول على معلومات الحساب
        me = await client.get_me()
        account_id = str(me.id)
        
        # الحصول على المجموعات
        groups = []
        async for dialog in client.iter_dialogs():
            if dialog.is_group:
                group = {
                    "id": dialog.id,
                    "name": dialog.name,
                    "permissions": {
                        "send_messages": dialog.entity.admin_rights.send_messages if dialog.entity.admin_rights else False
                    }
                }
                groups.append(group)
        
        # حفظ الحساب
        accounts[account_id] = {
            "phone": phone,
            "session": f"{phone}.session",
            "groups": groups,
            "api_id": api_id,
            "api_hash": api_hash
        }
        
        AccountManager.save_accounts(accounts)
        await client.disconnect()
        return account_id
    
    @staticmethod
    async def verify_account(phone, code, password=None):
        """التحقق من الحساب باستخدام الرمز"""
        accounts = AccountManager.load_accounts()
        session_path = os.path.join(SESSION_DIR, f"{phone}.session")
        client = TelegramClient(session_path, API_ID, API_HASH)
        
        await client.connect()
        try:
            await client.sign_in(phone, code)
            if password:
                await client.sign_in(password=password)
            
            # الحصول على معلومات الحساب
            me = await client.get_me()
            account_id = str(me.id)
            
            # الحصول على المجموعات
            groups = []
            async for dialog in client.iter_dialogs():
                if dialog.is_group:
                    group = {
                        "id": dialog.id,
                        "name": dialog.name,
                        "permissions": {
                            "send_messages": dialog.entity.admin_rights.send_messages if dialog.entity.admin_rights else False
                        }
                    }
                    groups.append(group)
            
            # حفظ الحساب
            accounts[account_id] = {
                "phone": phone,
                "session": f"{phone}.session",
                "groups": groups,
                "api_id": API_ID,
                "api_hash": API_HASH
            }
            
            AccountManager.save_accounts(accounts)
            await client.disconnect()
            return account_id
        except SessionPasswordNeededError:
            return "password"
        except Exception as e:
            logger.error(f"خطأ في التحقق: {e}")
            return f"خطأ: {str(e)}"
    
    @staticmethod
    def delete_account(account_id):
        """حذف حساب"""
        accounts = AccountManager.load_accounts()
        if account_id in accounts:
            session_file = os.path.join(SESSION_DIR, accounts[account_id]['session'])
            if os.path.exists(session_file):
                os.remove(session_file)
            del accounts[account_id]
            AccountManager.save_accounts(accounts)
            return True
        return False

class TaskManager:
    """إدارة مهام النشر"""
    
    @staticmethod
    def load_task():
        """تحميل المهمة الحالية"""
        if os.path.exists(TASK_FILE):
            with open(TASK_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None
    
    @staticmethod
    def save_task(task_data):
        """حفظ المهمة الحالية"""
        with open(TASK_FILE, 'w', encoding='utf-8') as f:
            json.dump(task_data, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def create_task(account_id, groups, content, interval):
        """إنشاء مهمة جديدة"""
        task_data = {
            "account_id": account_id,
            "groups": groups,
            "content": content,
            "interval": interval,
            "status": "active",
            "paused_groups": [],
            "logs": [],
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "total_posts": 0
        }
        TaskManager.save_task(task_data)
        return task_data
    
    @staticmethod
    def update_task(update_data):
        """تحديث المهمة الحالية"""
        task_data = TaskManager.load_task()
        if task_data:
            task_data.update(update_data)
            TaskManager.save_task(task_data)
        return task_data
    
    @staticmethod
    def log_post(group_id, status, content):
        """تسجيل عملية النشر"""
        task_data = TaskManager.load_task()
        if task_data:
            log_entry = {
                "time": datetime.now().isoformat(),
                "group": group_id,
                "content": content,
                "status": status
            }
            task_data["logs"].append(log_entry)
            task_data["total_posts"] += 1
            task_data["last_run"] = datetime.now().isoformat()
            TaskManager.save_task(task_data)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """رسالة الترحيب"""
    user = update.effective_user
    await update.message.reply_text(
        f"مرحبًا {user.first_name}!\n\n"
        "أنا بوت النشر التلقائي لمجموعات تيليجرام.\n"
        "استخدم الأوامر التالية للتحكم:\n"
        "/add_account - إضافة حساب جديد\n"
        "/delete_account - حذف حساب\n"
        "/create_task - إنشاء مهمة نشر جديدة\n"
        "/control - التحكم بالمهمة الحالية\n"
        "/status - عرض حالة المهمة"
    )

async def add_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إضافة حساب جديد"""
    await update.message.reply_text(
        "الرجاء إرسال رقم هاتف الحساب (مع رمز الدولة)\n"
        "مثال: +1234567890"
    )
    context.user_data['state'] = 'awaiting_phone'

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الرسائل الواردة"""
    user_state = context.user_data.get('state', '')
    message = update.message.text
    
    if user_state == 'awaiting_phone':
        phone = message.strip()
        result = await AccountManager.add_account(phone, API_ID, API_HASH)
        
        if result == "code":
            context.user_data['phone'] = phone
            await update.message.reply_text("تم إرسال رمز التحقق إلى الحساب. الرجاء إرسال الرمز:")
            context.user_data['state'] = 'awaiting_code'
        else:
            await update.message.reply_text(result)
    
    elif user_state == 'awaiting_code':
        phone = context.user_data['phone']
        code = message.strip()
        result = await AccountManager.verify_account(phone, code)
        
        if result == "password":
            await update.message.reply_text("الرجاء إرسال كلمة المرور الثنائية:")
            context.user_data['state'] = 'awaiting_password'
        elif isinstance(result, str) and result.startswith("خطأ"):
            await update.message.reply_text(result)
        else:
            await update.message.reply_text(f"تمت إضافة الحساب بنجاح! ID: {result}")
            context.user_data.clear()
    
    elif user_state == 'awaiting_password':
        phone = context.user_data['phone']
        password = message.strip()
        result = await AccountManager.verify_account(phone, None, password)
        
        if isinstance(result, str) and result.startswith("خطأ"):
            await update.message.reply_text(result)
        else:
            await update.message.reply_text(f"تمت إضافة الحساب بنجاح! ID: {result}")
            context.user_data.clear()

async def create_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنشاء مهمة نشر جديدة"""
    # التحقق من وجود مهمة نشطة
    current_task = TaskManager.load_task()
    if current_task and current_task.get('status') == 'active':
        await update.message.reply_text("يوجد مهمة نشطة بالفعل. الرجاء إيقافها أولاً.")
        return
    
    accounts = AccountManager.load_accounts()
    if not accounts:
        await update.message.reply_text("لا توجد حسابات متاحة. الرجاء إضافة حساب أولاً.")
        return
    
    # عرض قائمة الحسابات
    keyboard = []
    for account_id, account_info in accounts.items():
        keyboard.append([InlineKeyboardButton(
            f"{account_info['phone']} ({len(account_info['groups'])} مجموعات)",
            callback_data=f"select_account:{account_id}"
        )])
    
    await update.message.reply_text(
        "اختر حسابًا للنشر:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def select_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار حساب للمهمة"""
    query = update.callback_query
    await query.answer()
    
    account_id = query.data.split(':')[1]
    context.user_data['account_id'] = account_id
    
    accounts = AccountManager.load_accounts()
    account_info = accounts.get(account_id)
    
    if not account_info:
        await query.edit_message_text("الحساب غير موجود!")
        return
    
    # عرض قائمة المجموعات
    keyboard = []
    for group in account_info['groups']:
        if group['permissions']['send_messages']:
            keyboard.append([InlineKeyboardButton(
                group['name'],
                callback_data=f"select_group:{group['id']}"
            )])
    
    keyboard.append([InlineKeyboardButton("تم الاختيار", callback_data="finish_groups")])
    
    await query.edit_message_text(
        "اختر المجموعات للنشر (يمكن اختيار أكثر من مجموعة):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    context.user_data['selected_groups'] = []

async def select_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """اختيار مجموعة للنشر"""
    query = update.callback_query
    await query.answer()
    
    group_id = query.data.split(':')[1]
    selected_groups = context.user_data.get('selected_groups', [])
    
    if group_id in selected_groups:
        selected_groups.remove(group_id)
    else:
        selected_groups.append(group_id)
    
    context.user_data['selected_groups'] = selected_groups
    
    # تحديث الواجهة لإظهار التحديد
    accounts = AccountManager.load_accounts()
    account_info = accounts.get(context.user_data['account_id'])
    
    keyboard = []
    for group in account_info['groups']:
        if group['permissions']['send_messages']:
            is_selected = str(group['id']) in selected_groups
            prefix = "✓ " if is_selected else ""
            keyboard.append([InlineKeyboardButton(
                f"{prefix}{group['name']}",
                callback_data=f"select_group:{group['id']}"
            )])
    
    keyboard.append([InlineKeyboardButton("تم الاختيار", callback_data="finish_groups")])
    
    await query.edit_message_text(
        f"المجموعات المحددة: {len(selected_groups)}\n"
        "اختر المجموعات للنشر (يمكن اختيار أكثر من مجموعة):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def finish_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """إنهاء اختيار المجموعات"""
    query = update.callback_query
    await query.answer()
    
    selected_groups = context.user_data.get('selected_groups', [])
    if not selected_groups:
        await query.edit_message_text("لم تختر أي مجموعات!")
        return
    
    context.user_data['state'] = 'awaiting_content'
    await query.edit_message_text(
        "تم اختيار المجموعات بنجاح!\n"
        "الرجاء إرسال المحتوى النصي للنشر:"
    )

async def set_interval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """تعيين الفاصل الزمني"""
    content = update.message.text
    context.user_data['content'] = content
    
    await update.message.reply_text(
        "الرجاء إرسال الفاصل الزمني بين النشرات بالدقائق (الحد الأدنى 2 دقائق):"
    )
    context.user_data['state'] = 'awaiting_interval'

async def start_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """بدء المهمة"""
    interval = update.message.text.strip()
    try:
        interval_min = max(int(interval), 2)  # الحد الأدنى 2 دقائق
    except ValueError:
        await update.message.reply_text("قيمة غير صالحة! الرجاء إدخال رقم صحيح.")
        return
    
    # جمع بيانات المهمة
    account_id = context.user_data['account_id']
    selected_groups = context.user_data['selected_groups']
    content = context.user_data['content']
    
    # إنشاء المهمة
    task_data = TaskManager.create_task(
        account_id=account_id,
        groups=selected_groups,
        content=content,
        interval=interval_min * 60  # التحويل إلى ثواني
    )
    
    # بدء المهمة
    scheduler.add_job(
        publish_job,
        'interval',
        seconds=task_data['interval'],
        id='posting_job'
    )
    
    if not scheduler.running:
        scheduler.start()
    
    await update.message.reply_text(
        f"تم بدء المهمة بنجاح!\n"
        f"سوف يتم النشر كل {interval_min} دقائق\n"
        f"في {len(selected_groups)} مجموعات"
    )
    
    # مسح بيانات المستخدم المؤقتة
    context.user_data.clear()

async def publish_job():
    """وظيفة النشر المتكرر"""
    task_data = TaskManager.load_task()
    if not task_data or task_data.get('status') != 'active':
        return
    
    accounts = AccountManager.load_accounts()
    account_info = accounts.get(task_data['account_id'])
    
    if not account_info:
        logger.error("الحساب غير موجود!")
        return
    
    # الاتصال بالحساب
    session_path = os.path.join(SESSION_DIR, account_info['session'])
    client = TelegramClient(
        session_path,
        account_info['api_id'],
        account_info['api_hash']
    )
    
    await client.start()
    
    # النشر في المجموعات
    for group_id in task_data['groups']:
        if group_id in task_data.get('paused_groups', []):
            continue
            
        try:
            # البحث عن معلومات المجموعة
            group_info = next(
                (g for g in account_info['groups'] if str(g['id']) == group_id),
                None
            )
            
            if not group_info:
                logger.error(f"المجموعة {group_id} غير موجودة في الحساب")
                continue
                
            # إرسال الرسالة
            await client.send_message(int(group_id), task_data['content'])
            logger.info(f"تم النشر في {group_info['name']}")
            TaskManager.log_post(group_id, "success", task_data['content'])
            
        except Exception as e:
            logger.error(f"خطأ في النشر في المجموعة {group_id}: {str(e)}")
            TaskManager.log_post(group_id, f"error: {str(e)}", task_data['content'])
    
    await client.disconnect()

async def control_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """لوحة التحكم بالمهمة"""
    task_data = TaskManager.load_task()
    if not task_data:
        await update.message.reply_text("لا توجد مهمة نشطة حالياً.")
        return
    
    # عرض حالة المهمة
    status_text = {
        'active': 'نشطة',
        'paused': 'متوقفة',
        'completed': 'مكتملة'
    }.get(task_data['status'], 'غير معروفة')
    
    message = (
        f"حالة المهمة: {status_text}\n"
        f"عدد النشرات: {task_data['total_posts']}\n"
        f"آخر نشر: {task_data['last_run'] or 'لم يتم'}\n\n"
        "التحكم بالمهمة:"
    )
    
    # إنشاء أزرار التحكم
    keyboard = []
    
    if task_data['status'] == 'active':
        keyboard.append([InlineKeyboardButton("إيقاف مؤقت", callback_data="pause_task")])
    elif task_data['status'] == 'paused':
        keyboard.append([InlineKeyboardButton("استئناف", callback_data="resume_task")])
    
    keyboard.append([InlineKeyboardButton("تعديل المحتوى", callback_data="edit_content")])
    keyboard.append([InlineKeyboardButton("تعديل الفاصل الزمني", callback_data="edit_interval")])
    keyboard.append([InlineKeyboardButton("إدارة المجموعات المتوقفة", callback_data="manage_paused")])
    keyboard.append([InlineKeyboardButton("إيقاف المهمة", callback_data="stop_task")])
    
    await update.message.reply_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """معالجة الضغطات على الأزرار"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == 'pause_task':
        TaskManager.update_task({'status': 'paused'})
        await query.edit_message_text("تم إيقاف المهمة مؤقتاً.")
    
    elif data == 'resume_task':
        TaskManager.update_task({'status': 'active'})
        await query.edit_message_text("تم استئناف المهمة.")
    
    elif data == 'edit_content':
        await query.edit_message_text("الرجاء إرسال المحتوى الجديد:")
        context.user_data['state'] = 'editing_content'
    
    elif data == 'edit_interval':
        await query.edit_message_text("الرجاء إرسال الفاصل الزمني الجديد بالدقائق (الحد الأدنى 2 دقيقة):")
        context.user_data['state'] = 'editing_interval'
    
    elif data == 'manage_paused':
        await show_paused_groups(query)
    
    elif data == 'stop_task':
        TaskManager.update_task({'status': 'completed'})
        await query.edit_message_text("تم إيقاف المهمة نهائياً.")
    
    elif data.startswith('toggle_group:'):
        group_id = data.split(':')[1]
        task_data = TaskManager.load_task()
        paused_groups = task_data.get('paused_groups', [])
        
        if group_id in paused_groups:
            paused_groups.remove(group_id)
        else:
            paused_groups.append(group_id)
        
        TaskManager.update_task({'paused_groups': paused_groups})
        await show_paused_groups(query)

async def show_paused_groups(query):
    """عرض المجموعات المتوقفة"""
    task_data = TaskManager.load_task()
    accounts = AccountManager.load_accounts()
    account_info = accounts.get(task_data['account_id'])
    
    message = "المجموعات المتوقفة:\n\n"
    keyboard = []
    
    for group_id in task_data['groups']:
        group_info = next(
            (g for g in account_info['groups'] if str(g['id']) == group_id),
            None
        )
        
        if group_info:
            is_paused = group_id in task_data.get('paused_groups', [])
            status = "✓ متوقفة" if is_paused else "نشطة"
            keyboard.append([InlineKeyboardButton(
                f"{group_info['name']} - {status}",
                callback_data=f"toggle_group:{group_id}"
            )])
    
    keyboard.append([InlineKeyboardButton("العودة", callback_data="back_to_control")])
    
    await query.edit_message_text(
        message,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """عرض حالة المهمة"""
    task_data = TaskManager.load_task()
    if not task_data:
        await update.message.reply_text("لا توجد مهمة نشطة حالياً.")
        return
    
    accounts = AccountManager.load_accounts()
    account_info = accounts.get(task_data['account_id'])
    
    status_text = {
        'active': 'نشطة',
        'paused': 'متوقفة',
        'completed': 'مكتملة'
    }.get(task_data['status'], 'غير معروفة')
    
    # حساب عدد الرسائل لكل مجموعة
    group_stats = {}
    for log in task_data['logs']:
        group_id = log['group']
        group_stats[group_id] = group_stats.get(group_id, 0) + 1
    
    # إنشاء تقرير الحالة
    message = (
        f"حالة المهمة: {status_text}\n"
        f"الحساب المستخدم: {account_info['phone'] if account_info else 'غير معروف'}\n"
        f"عدد النشرات الإجمالي: {task_data['total_posts']}\n"
        f"آخر نشر: {task_data['last_run'] or 'لم يتم'}\n\n"
        "إحصائيات المجموعات:\n"
    )
    
    for group_id in task_data['groups']:
        group_info = next(
            (g for g in account_info['groups'] if str(g['id']) == group_id),
            None
        )
        if group_info:
            count = group_stats.get(group_id, 0)
            paused = " (متوقفة)" if group_id in task_data.get('paused_groups', []) else ""
            message += f"- {group_info['name']}: {count} نشرات{paused}\n"
    
    await update.message.reply_text(message)

def main():
    """الدالة الرئيسية لتشغيل البوت"""
    # إنشاء تطبيق البوت
    application = Application.builder().token(BOT_TOKEN).build()
    
    # تسجيل معالجات الأوامر
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("add_account", add_account))
    application.add_handler(CommandHandler("create_task", create_task))
    application.add_handler(CommandHandler("control", control_panel))
    application.add_handler(CommandHandler("status", status))
    
    # معالجات الرسائل
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # معالجات الضغطات على الأزرار
    application.add_handler(CallbackQueryHandler(select_account, pattern="^select_account:"))
    application.add_handler(CallbackQueryHandler(select_group, pattern="^select_group:"))
    application.add_handler(CallbackQueryHandler(finish_groups, pattern="^finish_groups$"))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # بدء البوت
    application.run_polling()

if __name__ == "__main__":
    main()
