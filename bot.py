import os
import logging
import asyncio
import requests
import wikipediaapi
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from groq import Groq

# --- قراءة المتغيرات تلقائياً من إعدادات Railway ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@Athar_Anthro")  # القيمة الافتراضية لقناتك

# مفتاح Unsplash الثابت الخاص بك
UNSPLASH_ACCESS_KEY = "kIjWpGPgkjcSmYhgFRVA-guVHTwXtVmm-Ihfarl_Hn0" 

# إعداد عميل Groq وويكيبيديا
groq_client = Groq(api_key=GROQ_API_KEY)
wiki = wikipediaapi.Wikipedia(user_agent="AtharBot/1.0 (contact@example.com)", language="ar")

# إعدادات السجلات (Logging)
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

# قائمة بمواضيع أنثروبولوجية لضمان التجدد كل نصف ساعة
ANTHRO_TOPICS = [
    "علم الإنسان الثقافي", "التطور البشري", "نياندرتال", "الأنثروبولوجيا اللغوية", 
    "الطقوس الجنائزية القديمة", "نشأة المجتمعات", "القرابة في علم الإنسان", 
    "الهجرة البشرية الأولى", "أنثروبولوجيا الطعام", "الحضارات القديمة"
]
topic_index = 0

# --- وظائف جلب البيانات والصور ---
def get_random_anthropology_data():
    """جلب نص عشوائي موثوق من ويكيبيديا حول علم الإنسان"""
    global topic_index
    topic = ANTHRO_TOPICS[topic_index % len(ANTHRO_TOPICS)]
    topic_index += 1
    
    page = wiki.page(topic)
    if page.exists():
        return topic, page.summary[:1500]
    return "علم الإنسان", "البحث في أصل المجتمعات البشرية وثقافاتها وتطورها عبر العصور."

def get_verified_image(keyword):
    """جلب رابط صورة عالية الجودة وموثوقة من Unsplash باستخدام مفتاحك"""
    url = f"https://unsplash.com{keyword}&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        response = requests.get(url, timeout=10).json()
        return response['urls']['regular']
    except Exception:
        return "https://unsplash.com"

# --- وظائف الذكاء الاصطناعي (Groq) ---
def generate_groq_content(prompt, system_instruction):
    """توليد محتوى باستخدام ذكاء Groq الاصطناعي"""
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
        logging.error(f"خطأ في Groq: {e}")
        return None

# --- المهام التلقائية (النشر كل 30 دقيقة) ---
async def auto_post_job(context: ContextTypes.DEFAULT_TYPE):
    """وظيفة النشر التلقائي كل نصف ساعة"""
    topic, raw_data = get_random_anthropology_data()
    
    prompt = f"قم بصياغة منشور احترافي ومثير بناءً على هذه المعلومات: {raw_data}"
    formatted_post = generate_groq_content(prompt, SYSTEM_PROMPT_POST)
    
    if formatted_post:
        image_url = get_verified_image(topic)
        
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_url,
            caption=formatted_post,
            parse_mode="Markdown"
        )

# --- الرد التلقائي في مجموعة التعليقات ---
async def handle_new_post_in_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """الرد على المنشورات المعاد توجيهها في مجموعة النقاش"""
    if update.message.forward_from_chat and update.message.forward_from_chat.username == CHANNEL_ID.replace("@", ""):
        post_text = update.message.text or update.message.caption
        if not post_text:
            return

        prompt = f"اقرأ هذا المنشور بعناية وعلق عليه بمعلومات إضافية حصرية: {post_text}"
        ai_comment = generate_groq_content(prompt, SYSTEM_PROMPT_COMMENT)

        if ai_comment:
            await update.message.reply_text(ai_comment, parse_mode="Markdown")

# --- تشغيل البوت ---
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    job_queue = application.job_queue
    # النشر كل 30 دقيقة (1800 ثانية)، والمنشور الأول يظهر بعد 10 ثوانٍ من تشغيل السيرفر
    job_queue.run_repeating(auto_post_job, interval=1800, first=10)

    application.add_handler(MessageHandler(filters.ChatType.SUPERGROUP & (~filters.COMMAND), handle_new_post_in_comments))

    print("البوت يعمل الآن بنجاح على سيرفر Railway...")
    application.run_polling()

if __name__ == "__main__":
    main()
