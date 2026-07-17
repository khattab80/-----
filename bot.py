import os
import logging
import asyncio
import requests
import wikipediaapi
import httpx  
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler
from groq import Groq

# --- قراءة المتغيرات تلقائياً من إعدادات Railway ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@Athar_Anthro")  

# مفتاح Unsplash الثابت الخاص بك
UNSPLASH_ACCESS_KEY = "kIjWpGPgkjcSmYhgFRVA-guVHTwXtVmm-Ihfarl_Hn0" 

# إعداد العميل
groq_client = Groq(api_key=GROQ_API_KEY, http_client=httpx.Client())
wiki = wikipediaapi.Wikipedia(user_agent="AtharAnthroBot/1.0 (aass90.uk@gmail.com)", language="ar")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

SYSTEM_PROMPT_POST = (
    "تصرف كعالم إنثروبولوجيا (علم الإنسان) خبير ومتحدث لبق باللغة العربية الفصحى. "
    "في المنشورات التلقائية: قسّم المقال إلى نقاط واضحة ومثيرة، واستخدم الرموز التعبيرية المناسبة، "
    "واختم دائماً بسؤال تفاعلي يشجع المتابعين على التعليق."
)

SYSTEM_PROMPT_COMMENT = (
    "تصرف كعالم إنثروبولوجيا خبير ومتحدث لبق بالفصحى. في التعليقات: ابدأ بعبارة ترحيبية مشوقة، "
    "ثم أضف معلومة تاريخية أو ثقافية حصرية تدعم المنشور الأساسي دون تكرار."
)

ANCHRO_TOPICS = [
    "علم الإنسان الثقافي", "التطور البشري", "نياندرتال", "الأنثروبولوجيا اللغوية", 
    "الطقوس الجنائزية القديمة", "نشأة المجتمعات", "القرابة في علم الإنسان", 
    "الهجرة البشرية الأولى", "أنثروبولوجيا الطعام", "الحضارات القديمة"
]
topic_index = 0

def get_random_anthropology_data():
    global topic_index
    topic = ANCHRO_TOPICS[topic_index % len(ANCHRO_TOPICS)]
    topic_index += 1
    try:
        page = wiki.page(topic)
        if page.exists():
            return topic, page.summary[:1500]
    except Exception as e:
        logging.error(f"خطأ ويكيبيديا: {e}")
    return "علم الإنسان", "البحث في أصل المجتمعات البشرية وثقافاتها وتطورها عبر العصور."

def get_verified_image(keyword):
    url = f"https://unsplash.com{keyword}&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        response = requests.get(url, timeout=10).json()
        return response['urls']['regular']
    except Exception:
        return "https://unsplash.com"

def generate_groq_content(prompt, system_instruction):
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
        logging.error(f"خطأ جروق: {e}")
        return None

async def auto_post_job(context: ContextTypes.DEFAULT_TYPE):
    """وظيفة النشر المعدلة لتفادي أخطاء التنسيق"""
    topic, raw_data = get_random_anthropology_data()
    prompt = f"قم بصياغة منشور احترافي ومثير بناءً على هذه المعلومات: {raw_data}"
    formatted_post = generate_groq_content(prompt, SYSTEM_PROMPT_POST)
    
    if formatted_post:
        image_url = get_verified_image(topic)
        try:
            # محاولة الإرسال بالتنسيق المتقدم أولاً
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_url,
                caption=formatted_post,
                parse_mode="Markdown"
            )
            logging.info("تم النشر بنجاح بالتنسيق.")
        except Exception as e:
            logging.warning(f"فشل الإرسال بالتنسيق، جاري الإرسال كنص عادي: {e}")
            try:
                # محاولة الإرسال كنص عادي إذا فشل التنسيق لضمان وصول الرسالة
                await context.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=image_url,
                    caption=formatted_post
                )
            except Exception as critical_error:
                logging.error(f"فشل الإرسال نهائياً! تأكد من اسم القناة: {critical_error}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً بك! أنا بوت 'أثر' لعلم الإنسان، أعمل الآن بنجاح 🏛️.")

async def test_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("جاري تجربة جلب البيانات والنشر في القناة الآن... انتظر لحظة 🔄.")
    await auto_post_job(context)

async def handle_new_post_in_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.forward_from_chat and update.message.forward_from_chat.username == CHANNEL_ID.replace("@", ""):
        post_text = update.message.text or update.message.caption
        if not post_text:
            return
        prompt = f"اقرأ هذا المنشور بعناية وعلق عليه بمعلومات إضافية حصرية: {post_text}"
        ai_comment = generate_groq_content(prompt, SYSTEM_PROMPT_COMMENT)
        if ai_comment:
            try:
                await update.message.reply_text(ai_comment, parse_mode="Markdown")
            except Exception:
                await update.message.reply_text(ai_comment)

def main():
    if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
        return
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    job_queue = application.job_queue
    job_queue.run_repeating(auto_post_job, interval=1800, first=10)

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("testpost", test_post_command))
    application.add_handler(MessageHandler(filters.ChatType.SUPERGROUP & (~filters.COMMAND), handle_new_post_in_comments))

    application.run_polling()

if __name__ == "__main__":
    main()
                
