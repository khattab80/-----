import os
import logging
import asyncio
import requests
import wikipediaapi
import httpx  # تم إضافته لضمان توافق الشبكة ومنع الكراش
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from groq import Groq

# --- قراءة المتغيرات تلقائياً من إعدادات Railway ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@Athar_Anthro")  # معرف قناتك الافتراضي

# مفتاح Unsplash الثابت الخاص بك
UNSPLASH_ACCESS_KEY = "kIjWpGPgkjcSmYhgFRVA-guVHTwXtVmm-Ihfarl_Hn0" 

# إعداد عميل Groq باستخدام httpx لحل مشكلة الـ proxies والكراش نهائياً
groq_client = Groq(api_key=GROQ_API_KEY, http_client=httpx.Client())
wiki = wikipediaapi.Wikipedia(user_agent="AtharAnthroBot/1.0 (aass90.uk@gmail.com)", language="ar")

# إعدادات السجلات (Logging) لمراقبة الأداء في Railway
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- التوجيهات (System Prompts) المحددة من قبلك ---
SYSTEM_PROMPT_POST = (
    "تصرف كعالم إنثروبولوجيا (علم الإنسان) خبير ومتحدث لبق باللغة العربية الفصحى. "
    "في المنشورات التلقائية: قسّم المقال المترجم والمستخرج إلى نقاط واضحة ومثيرة، "
    "واستخدم الرموز التعبيرية (Emojis) المناسبة للتنسيق، واختم دائماً بسؤال تفاعلي يشجع المتابعين على التعليق."
)

SYSTEM_PROMPT_COMMENT = (
    "تصرف كعالم إنثروبولوجيا (علم الإنسان) خبير ومتحدث لبق باللغة العربية الفصحى. "
    "في التعليقات التلقائية: اقرأ المنشور جيداً، وابدأ التعليق بعبارة ترحيبية مشوقة، "
    "ثم أضف معلومة تاريخية أو ثقافية حصرية تدعم المنشور الأساسي وتثري النقاش دون تكرار نفس الكلام الموجود في المنشور."
)

# قائمة بمواضيع أنثروبولوجية غنية لضمان التجدد كل نصف ساعة
ANTHRO_TOPICS = [
    "علم الإنسان الثقافي", "التطور البشري", "نياندرتال", "الأنثروبولوجيا اللغوية", 
    "الطقوس الجنائزية القديمة", "نشأة المجتمعات", "القرابة في علم الإنسان", 
    "الهجرة البشرية الأولى", "أنثروبولوجيا الطعام", "الحضارات القديمة",
    "الأنثروبولوجيا الفيزيائية", "الأساطير القديمة", "التنوع الثقافي البشرى"
]
topic_index = 0

# --- وظائف جلب البيانات والصور ---
def get_random_anthropology_data():
    """جلب نص عشوائي موثوق من ويكيبيديا حول علم الإنسان"""
    global topic_index
    topic = ANTHRO_TOPICS[topic_index % len(ANTHRO_TOPICS)]
    topic_index += 1
    
    try:
        page = wiki.page(topic)
        if page.exists():
            return topic, page.summary[:1500]
    except Exception as e:
        logging.error(f"خطأ في جلب بيانات ويكيبيديا: {e}")
    return "علم الإنسان", "البحث في أصل المجتمعات البشرية وثقافاتها وتطورها عبر العصور العلمية المختلفة."

def get_verified_image(keyword):
    """جلب رابط صورة عالية الجودة وموثوقة من Unsplash باستخدام مفتاحك"""
    url = f"https://unsplash.com{keyword}&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        response = requests.get(url, timeout=10).json()
        return response['urls']['regular']
    except Exception as e:
        logging.error(f"خطأ في جلب صورة Unsplash: {e}")
        return "https://unsplash.com"

# --- وظائف الذكاء الاصطناعي (Groq) ---
def generate_groq_content(prompt, system_instruction):
    """توليد محتوى باستخدام ذكاء Groq الاصطناعي وبنية متوافقة"""
    try:
        completion = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return completion.choices.message.content
    except Exception as e:
        logging.error(f"خطأ في Groq API: {e}")
        return None

# --- المهام التلقائية (النشر كل 30 دقيقة) ---
async def auto_post_job(context: ContextTypes.DEFAULT_TYPE):
    """وظيفة النشر التلقائي كل نصف ساعة"""
    topic, raw_data = get_random_anthropology_data()
    
    prompt = f"قم بصياغة منشور احترافي ومثير بناءً على هذه المعلومات: {raw_data}"
    formatted_post = generate_groq_content(prompt, SYSTEM_PROMPT_POST)
    
    if formatted_post:
        image_url = get_verified_image(topic)
        try:
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_url,
                caption=formatted_post,
                parse_mode="Markdown"
            )
            logging.info(f"تم نشر منشور جديد بنجاح حول: {topic}")
        except Exception as e:
            logging.error(f"فشل إرسال المنشور إلى القناة: {e}")

# --- الرد التلقائي في مجموعة التعليقات ---
async def handle_new_post_in_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرد على المنشورات المعاد توجيهها في مجموعة النقاش لفتح نقاش في التعليقات"""
    if update.message.forward_from_chat and update.message.forward_from_chat.username == CHANNEL_ID.replace("@", ""):
        post_text = update.message.text or update.message.caption
        if not post_text:
            return

        prompt = f"اقرأ هذا المنشور بعناية وعلق عليه بمعلومات إضافية حصرية: {post_text}"
        ai_comment = generate_groq_content(prompt, SYSTEM_PROMPT_COMMENT)

        if ai_comment:
            try:
                await update.message.reply_text(ai_comment, parse_mode="Markdown")
                logging.info("تم إضافة تعليق ذكي ومثري بنجاح على منشور القناة.")
            except Exception as e:
                logging.error(f"فشل إرسال التعليق: {e}")

# --- تشغيل البوت ---
def main():
    if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
        print("خطأ: تأكد من ضبط متغيرات البيئة TELEGRAM_BOT_TOKEN و GROQ_API_KEY في Railway!")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # المجدول الزمني للنشر كل 1800 ثانية (30 دقيقة)
    job_queue = application.job_queue
    job_queue.run_repeating(auto_post_job, interval=1800, first=10)

    # الاستماع للرسائل داخل المجموعات الفائقة (Supergroups) للرد على التعليقات
    application.add_handler(MessageHandler(filters.ChatType.SUPERGROUP & (~filters.COMMAND), handle_new_post_in_comments))

    print("البوت يعمل الآن بنجاح ومستعد للرفع على Railway...")
    application.run_polling()

if __name__ == "__main__":
    main()
