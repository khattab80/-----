import os
import logging
import asyncio
import requests
import wikipediaapi
import httpx
from telegram import Update
from telegram.ext import Application, MessageHandler, Filters, ContextTypes, CommandHandler
from groq import Groq

# --- قراءة المتغيرات تلقائياً من إعدادات Railway ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@Athar_Anthro")

if not CHANNEL_ID.startswith("@"):
    CHANNEL_ID = f"@{CHANNEL_ID}"

UNSPLASH_ACCESS_KEY = "kIjwGpgKjcSmYhgFRVA-guYHiTeXtVhm-Ihfar1_HnQ"

# إعداد العميل لـ Groq و ويكيبيديا
groq_client = Groq(api_key=GROQ_API_KEY)
wiki = wikipediaapi.Wikipedia(user_agent="AtharAnthroBot/1.0 (aass90.uk@gmail.com)", language="ar")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- التوجيهات الصارمة لنظام الذكاء الاصطناعي (تم تحديثها لمنع النصوص الطويلة وأخطاء التنسيق) ---
SYSTEM_PROMPT_POST = (
    "تصرّف كعالم أنثروبولوجيا (علم الإنسان) خبير ومتحدث باللغة العربية الفصحى. "
    "اكتب منشوراً مشوقاً ومختصراً جداً (بحد أقصى 600 حرف). قسّم المقال إلى نقاط واضحة باستخدام الإيموجي. "
    "تنبيه صارم: لا تستخدم رموز الماركداون مثل النجوم أو الخطوط نهائياً. استخدم نصوصاً عادية فقط لتجنب أخطاء الإرسال."
)

SYSTEM_PROMPT_COMMENT = (
    "تصرّف كعالم أنثروبولوجيا (علم الإنسان) خبير ومتحدث باللغة العربية الفصحى. "
    "في التعليقات التالية: اقرأ المنشور جيداً وعلق باختصار بعبارة ترحيبية مشوقة دون استخدام أي رموز تنسيق."
)

SYSTEM_PROMPT_PRIVATE_CHAT = (
    "تصرّف كعالم أنثروبولوجيا (علم الإنسان) خبير وأستاذ جامعي متحدث باللغة العربية الفصحى. "
    "أجب على أسئلة المستخدمين في الخاص بكل رحابة صدر وبشكل مبسط ومباشر دون استخدام رموز التنسيق المعقدة."
)

ANCHRO_TOPICS = [
    "الأنثروبولوجيا اللغوية", "النياندرتال", "التطور البشري", "علم الإنسان الثقافي",
    "القرابة في علم الإنسان", "بناء المجتمعات", "الطقوس الجنائزية القديمة",
    "الحضارات القديمة", "الأنثروبولوجيا الفيزيائية", "الهجرة البشرية الأولى"
]

topic_index = 0

def get_random_anthropology_data():
    global topic_index
    topic = ANCHRO_TOPICS[topic_index % len(ANCHRO_TOPICS)]
    topic_index += 1
    try:
        page = wiki.page(topic)
        if page.exists:
            return topic, page.summary[:800] # تقليل حجم الملخص المجلوب
    except Exception as e:
        logging.error(f"خطأ ويكيبيديا: {e}")
    return "الأنثروبولوجيا", "البحث في أصل المجتمعات البشرية وثقافاتها وتطورها عبر العصور."

def get_verified_image(keyword):
    url = f"https://unsplash.com{keyword}&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        response = requests.get(url, timeout=10).json()
        return response['urls']['regular']
    except Exception:
        return "https://unsplash.com" # رابط صورة احتياطية مستقرة

def generate_groq_content(prompt, system_instruction):
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices.message.content
    except Exception as e:
        logging.error(f"خطأ في Groq: {e}")
        return None

async def auto_post_job(context: ContextTypes.DEFAULT_TYPE):
    topic, raw_data = get_random_anthropology_data()
    prompt = f"اكتب منشوراً علمياً شيقاً وموجزاً جداً عن: {raw_data}"
    
    post_content = generate_groq_content(prompt, SYSTEM_PROMPT_POST)
    if not post_content:
        print("فشل توليد المحتوى من الذكاء الاصطناعي.")
        return

    image_url = get_verified_image(topic)
    
    # الاعتماد على تنسيق HTML الآمن وبناء النص برمجياً لتجنب أخطاء القفل
    caption_formatted = f"<b>✨ {topic} ✨</b>\n\n{post_content}"

    # التأكد التام من عدم تجاوز الحد المسموح لتلجرام في وصف الصورة
    if len(caption_formatted) > 1000:
        caption_formatted = caption_formatted[:950] + "..."

    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_url,
            caption=caption_formatted,
            parse_mode="HTML"
        )
        print("تم النشر في القناة بنجاح باستخدام صيغة HTML آمنة")
    except Exception as e:
        print(f"فشل الإرسال المنسق، جاري المحاولة بنص خام خالي من التنسيقات. السبب: {e}")
        try:
            # تجريد النص تماماً من أي وسوم لإجبار تلجرام على تمريره
            clean_text = f"{topic}\n\n{post_content}"
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_url,
                caption=clean_text[:1000]
            )
            print("تم النشر الاحتياطي بنجاح (نص خام)")
        except Exception as ce:
            print(f"البوت لا يستطيع النشر نهائياً [خطأ فادح في الشبكة أو الصلاحيات]: {ce}")

# --- أوامر التحكم الأساسية ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً يا محب! يمكنك سؤالي عن أي شيء يخص علوم الإنسان والمجتمعات في هذا الشات الخاص وسأجيبك فوراً.")

async def test_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("جاري تجربة النشر الفوري والمطور في القناة الآن... انتظر لحظة ⏳")
    await auto_post_job(context)

# --- ميزة الخاص والرد التلقائي العلمي في الشات الخاص ---
async def handle_private_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text
    if not user_query:
        return
    
    print(f"رسالة جديدة من المستخدم [خاص]: {user_query}")
    ai_response = generate_groq_content(user_query, SYSTEM_PROMPT_PRIVATE_CHAT)
    
    if ai_response:
        await update.message.reply_text(ai_response)

# --- الرد التلقائي الذكي في مجموعة التعليقات ---
async def handle_new_post_in_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    is_forwarded = update.message.forward_from_chat is not None
    if is_forwarded and update.message.forward_from_chat.username == CHANNEL_ID.replace("@", ""):
        post_text = update.message.text or update.message.caption
        if not post_text:
            return
        
        prompt = f"اقرأ هذا المنشور وعلق عليه باختصار شديد وبمعلومة إضافية حصرية:\n{post_text}"
        ai_comment = generate_groq_content(prompt, SYSTEM_PROMPT_COMMENT)
        
        if ai_comment:
            try:
                await update.message.reply_text(ai_comment)
                print("تم إضافة التعليق الذكي بنجاح")
            except Exception:
                pass

def main():
    if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
        print("المتغيرات مفقودة في إعدادات ريلواي [خطأ فادح]")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    job_queue = application.job_queue
    # الجدولة كل 30 دقيقة (1800 ثانية)
    job_queue.run_repeating(auto_post_job, interval=1800, first=10)

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("testpost", test_post_command))

    application.add_handler(MessageHandler(Filters.chat_type.PRIVATE & (~Filters.command), handle_private_chat))
    application.add_handler(MessageHandler(Filters.chat_type.SUPERGROUP & (~Filters.command), handle_new_post_in_comments))

    application.run_polling()

if __name__ == "__main__":
    main()
        
