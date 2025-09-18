import telebot
import random

# توكن البوت
TOKEN = "8398354970:AAEiraXWDpOld2JGAwqt08gfmZmbbcSPj6s"
bot = telebot.TeleBot(TOKEN)

# دالة توليد الأرقام
def generate_numbers(count, start_with="+96773"):
    numbers = []
    for _ in range(count):
        number = start_with + "".join([str(random.randint(0, 9)) for _ in range(7)])
        numbers.append(number)
    return numbers

# دالة حفظ الأرقام في ملف VCF
def save_to_vcf(numbers, filename="contacts.vcf"):
    with open(filename, "w", encoding="utf-8") as f:
        for i, num in enumerate(numbers, start=1):
            f.write("BEGIN:VCARD\n")
            f.write("VERSION:3.0\n")
            f.write(f"N:;Contact{i};;;\n")
            f.write(f"FN:Contact{i}\n")
            f.write(f"TEL;TYPE=CELL:{num}\n")
            f.write("END:VCARD\n")

# التعامل مع الرسائل
@bot.message_handler(commands=['start'])
def welcome(message):
    bot.send_message(message.chat.id, "🔢 أرسل عدد الأرقام التي تريد توليدها:")

@bot.message_handler(func=lambda msg: msg.text.isdigit())
def handle_number_request(message):
    count = int(message.text)
    bot.send_message(message.chat.id, f"✅ جاري توليد {count} رقم...")
    numbers = generate_numbers(count)
    save_to_vcf(numbers)
    with open("contacts.vcf", "rb") as file:
        bot.send_document(message.chat.id, file, caption=f"📁 تم توليد {count} رقم وحفظها في الملف contacts.vcf")

# تشغيل البوت
bot.infinity_polling()
