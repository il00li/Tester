#!/usr/bin/env python3
"""
واجهة البوت للمستخدم
python-telegram-bot v20
"""
import os, re, random, vobject, string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ---------- إعدادات ----------
BOT_TOKEN = "8398354970:AAEiraXWDpOld2JGAwqt08gfmZmbbcSPj6s"
VCFFILE   = "phones.vcf"
user_data = {}          # memory-only (يمكن استخدام DB)

# ---------- أوامر ----------
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "أهلاً! أرسل رمز الدولة (مثلاً 966) ثم أول رقمين بعد الكود.\n"
        "مثال: 96655"
    )

async def handle_prefix(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    m = re.fullmatch(r"(\d{1,3})(\d{2})", text)
    if not m:
        await update.message.reply_text("الصيغة خاطئة. أرسل مثلاً: 96655")
        return
    code, prefix = m.groups()
    user_id = update.effective_user.id
    user_data[user_id] = {"code": code, "prefix": prefix, "amount": None}
    await update.message.reply_text("كم رقماً تريد؟ (أقصى 200 للتجربة)")

async def handle_amount(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data or user_data[user_id]["amount"] is not None:
        return
    try:
        amount = int(update.message.text)
        if not (1 <= amount <= 200):
            raise ValueError
    except ValueError:
        await update.message.reply_text("أدخل رقماً بين 1 و 200")
        return
    user_data[user_id]["amount"] = amount
    await generate_and_send(update, ctx)

async def generate_and_send(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    data = user_data[user_id]
    code, prefix, amount = data["code"], data["prefix"], data["amount"]
    numbers = []
    for _ in range(amount):
        tail = ''.join(random.choices(string.digits, k=6))
        numbers.append(f"+{code}{prefix}{tail}")

    # إنشاء VCF
    with open(VCFFILE, "w", encoding="utf-8") as f:
        for i, num in enumerate(numbers, 1):
            card = vobject.vCard()
            card.add('fn').value = f"Contact {i}"
            card.add('tel').value = num
            f.write(card.serialize())

    await update.message.reply_document(
        document=open(VCFFILE, "rb"),
        filename="random_phones.vcf",
        caption=f"تم توليد {amount} رقم."
    )
    # زر الانتقال لمرحلة التحقق
    keyboard = [[InlineKeyboardButton("التحقق من الأرقام", callback_data="check")]]
    await update.message.reply_text(
        "للتحقق من الأرقام الموجودة في تلجرام اضغط الزر أدناه.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "check":
        await query.edit_message_text(
            text="الآن أرسل رقم حسابك (مع كود الدولة) ثم كود التحقق في رسالة واحدة بالصيغة:\n"
                 "`+9665XXXXXXXX 12345`"
        )

async def handle_creds(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    m = re.match(r"(\+\d{10,15})\s+(\d{5,7})", text)
    if not m:
        await update.message.reply_text("الصيغة المتوقعة: `+9665XXXXXXXX 12345`")
        return
    phone, code = m.groups()
    # نحفظ البيانات ونطلق المحرك في خلفية
    user_id = update.effective_user.id
    user_data[user_id]["phone"] = phone
    user_data[user_id]["code"]  = code
    await update.message.reply_text("جارٍ التحقق... سأخبرك بالنتيجة خلال دقائق.")
    # يمكن استخدام subprocess أو runner async
    import subprocess, shlex
    cmd = f"python checker.py {shlex.quote(phone)} {shlex.quote(code)} {shlex.quote(VCFFILE)}"
    subprocess.Popen(cmd, shell=True)   # بسيط وسريع للتجربة

# ---------- main ----------
def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex(r"^\d{3,5}\d{2}$"), handle_prefix))
    app.add_handler(MessageHandler(filters.Regex(r"^\d+$"), handle_amount))
    app.add_handler(MessageHandler(filters.Regex(r"^\+\d+"), handle_creds))
    app.add_handler(CallbackQueryHandler(button))
    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
