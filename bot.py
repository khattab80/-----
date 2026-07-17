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

if not CHANNEL_ID.startswith("@"):
    CHANNEL_ID = f"@{CHANNEL_ID}"

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
        # 👈 تم تحديث اسم النموذج هنا إلى النموذج الجديد المعتمد والمدعوم حالياً
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant", 
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
        )
        return completion.choices.message.content
    except Exception as e:
        logging.error(f"خطأ جروق في توليد المحتوى: {e}")
        return None

async def auto_post_job(context: ContextTypes.DEFAULT_TYPE):
    topic, raw_data = get_random_anthropology_data()
    print(f"[فحص] جاري معالجة موضوع: {topic}")
    prompt = f"قم بصياغة منشور احترافي ومثير بناءً على هذه المعلومات: {raw_data}"
    formatted_post = generate_groq_content(prompt, SYSTEM_PROMPT_POST)
    
    if not formatted_post:
        print("[خطأ] لم يتم توليد نص من جروق، تأكد من مفتاح GROQ_API_KEY أو اسم النموذج")
        return

    image_url = get_verified_image(topic)
    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_url,
            caption=formatted_post,
            parse_mode="Markdown"
        )
        print("[نجاح] تم النشر في القناة بالتنسيق المتقدم!")
    except Exception as e:
        print(f"[تحذير] فشل الإرسال بالتنسيق، جاري التجربة بنص عادي. السبب: {e}")
        try:
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_url,
                caption=formatted_post
            )
            print("[نجاح] تم النشر بنص عادي!")
        except Exception as critical_error:
            print(f"[خطأ فادح] البوت لا يستطيع النشر أبداً! السبب الرئيسي: {critical_error}")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً بك! أنا بوت 'أثر' لعلم الإنسان، أعمل الآن بنجاح 🏛️.")

async def test_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("جاري تجربة جلب البيانات والنشر في القناة الآن... انتظر لحظة 🔄.")
    await auto_post_job(context)

async def handle_new_post_in_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(f"[مجموعة] استقبلت رسالة جديدة في المجموعة من شات: {update.message.chat.id}")
    
    is_forwarded = update.message.forward_from_chat is not None
    if is_forwarded:
        print(f"[مجموعة] الرسالة محولة من قناة: {update.message.forward_from_chat.username}")
        
    if is_forwarded and update.message.forward_from_chat.username == CHANNEL_ID.replace("@", ""):
        post_text = update.message.text or update.message.caption
        if not post_text:
            return
        prompt = f"اقرأ هذا المنشور بعناية وعلق عليه بمعلومات إضافية حصرية: {post_text}"
        ai_comment = generate_groq_content(prompt, SYSTEM_PROMPT_COMMENT)
        if ai_comment:
            try:
                await update.message.reply_text(ai_comment, parse_mode="Markdown")
                print("[نجاح] تم الرد في التعليقات!")
            except Exception as e:
                try:
                    await update.message.reply_text(ai_comment)
                    print("[نجاح] تم الرد في التعليقات بنص عادي!")
                except Exception as ce:
                    print(f"[خطأ] فشل الرد في التعليقات: {ce}")

def main():
    if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
        print("[خطأ فادح] لم يتم العثور على المتغيرات في ريلواي!")
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
    
