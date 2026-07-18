import os
import logging
import asyncio
import requests
import wikipediaapi
from telegram import Update
from telegram.ext import Application, MessageHandler, ContextTypes, CommandHandler, filters
from groq import Groq

# --- قراءة المتغيرات تلقائياً من إعدادات Railway ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@Athar_Anthro")

if not CHANNEL_ID.startswith("@"):
    CHANNEL_ID = f"@{CHANNEL_ID}"

UNSPLASH_ACCESS_KEY = "kIjwGpgKjcSmYhgFRVA-guYHiTeXtVhm-Ihfar1_HnQ"

# إعداد عميل Groq و ويكيبيديا
groq_client = Groq(api_key=GROQ_API_KEY)
wiki = wikipediaapi.Wikipedia(user_agent="AtharAnthroBot/1.0 (aass90.uk@gmail.com)", language="ar")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# --- التوجيهات الصارمة لنظام الذكاء الاصطناعي ---
SYSTEM_PROMPT_POST = (
    "تصرّف كعالم أنثروبولوجيا (علم الإنسان) خبير ومتحدث باللغة العربية الفصحى. "
    "اكتب منشوراً مشوقاً ومختصراً جداً (بحد أقصى 500 حرف). قسّم المقال إلى نقاط واضحة باستخدام الإيموجي. "
    "تنبيه صارم: لا تستخدم رموز الماركداون مثل النجوم أو الخطوط نهائياً. استخدم نصوصاً عادية فقط لتجنب أخطاء الإرسال."
)

SYSTEM_PROMPT_COMMENT = (
    "تصرّف كعالم أنثروبولوجيا (علم الإنسان) خبير ومتحدث باللغة العربية الفصحى الفصيحة والمشوقة. "
    "في التعليقات: اقرأ منشور القناة المحول جيداً، واكتب تعليقاً علمياً إضافياً يثري النقاش ويضيف معلومة تاريخية أو ثقافية حصرية وجديدة تماماً دون تكرار كلمات المنشور."
)

SYSTEM_PROMPT_GROUP_CHAT = (
    "تصرّف كعالم أنثروبولوجيا خبير ومستشار ودود في مجموعة نقاشات القناة العلمية. "
    "عندما يوجه لك الأعضاء (الأخوة والأخوات) سؤالاً أو رداً في المجموعة: أجبهم بكل أدب واحترام وبسط لهم المفاهيم العلمية بأسلوب ممتع ومختصر لتشجيعهم على حب علم الإنسان ومتابعة القناة."
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
            return topic, page.summary[:600]
    except Exception as e:
        logging.error(f"خطأ ويكيبيديا: {e}")
    return "الأنثروبولوجيا", "البحث في أصل المجتمعات البشرية وثقافاتها وتطورها عبر العصور المعرفية المختلفة."

def get_english_search_keyword(topic):
    try:
        prompt = f"Give me exactly one or two precise English search keywords for Unsplash images related to the topic: '{topic}'. Output ONLY the keywords, no introduction, no punctuation."
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}]
        )
        keyword = completion.choices.message.content.strip().replace('"', '').replace("'", "")
        return keyword
    except Exception:
        return "anthropology"

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
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices.message.content
    except Exception as e:
        logging.error(f"خطأ في استدعاء Groq: {e}")
        return None

async def auto_post_job(context: ContextTypes.DEFAULT_TYPE):
    topic, raw_data = get_random_anthropology_data()
    prompt = f"اكتب منشوراً علمياً شيقاً وموجزاً جداً عن: {raw_data}"
    
    post_content = generate_groq_content(prompt, SYSTEM_PROMPT_POST)
    if not post_content:
        post_content = f"موضوع اليوم يركز على الأنثروبولوجيا واستكشاف أصل المجتمعات وتطورها الثقافي والاجتماعي عبر العصور التاريخية المختلفة."

    english_keyword = get_english_search_keyword(topic)
    image_url = get_verified_image(english_keyword)
    caption_formatted = f"<b>✨ {topic} ✨</b>\n\n{post_content}"

    if len(caption_formatted) > 1000:
        caption_formatted = caption_formatted[:950] + "..."

    try:
        await context.bot.send_photo(
            chat_id=CHANNEL_ID,
            photo=image_url,
            caption=caption_formatted,
            parse_mode="HTML"
        )
        print("تم النشر التلقائي في القناة بنجاح [صيغة HTML]")
    except Exception as e:
        print(f"فشل الإرسال المنسق. السبب: {e}")
        try:
            clean_text = f"{topic}\n\n{post_content}"
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_url,
                caption=clean_text[:1000]
            )
            print("تم النشر الاحتياطي بنجاح (نص خام)")
        except Exception as ce:
            print(f"البوت لا يستطيع النشر نهائياً: {ce}")

# --- أوامر التحكم الأساسية ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("مرحباً بك في المحراب العلمي لـ أثر! أنا هنا كعالم إنثروبولوجيا مجيب، يمكنك سؤالي عن أي شيء يخص علوم الإنسان والمجتمعات في هذا الشات الخاص وسأجيبك فوراً!")

async def test_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("جاري تجربة النشر الفوري والمطور في القناة الآن... انتظر لحظة ⏳")
    await auto_post_job(context)

# --- ميزة الخاص والرد التلقائي العلمي في الشات الخاص ---
async def handle_private_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    
    user_query = update.message.text
    print(f"رسالة جديدة من المستخدم [خاص]: {user_query}")
    
    # إشعار المستخدم بأن البوت يقوم بالمعالجة
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    
    ai_response = generate_groq_content(user_query, SYSTEM_PROMPT_PRIVATE_CHAT)
    if ai_response:
        await update.message.reply_text(ai_response)
    else:
        await update.message.reply_text("أعتذر منك يا محب العلم، واجهت صعوبة في معالجة السؤال حالياً.")

# --- إدارة التفاعل والردود الشاملة داخل مجموعة التعليقات التابعة للقناة ---
async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    # أولاً: الرد على المنشورات المحولة تلقائياً من القناة
    is_forwarded = message.forward_from_chat is not None
    if is_forwarded and message.forward_from_chat.username == CHANNEL_ID.replace("@", ""):
        post_text = message.text or message.caption
        if not post_text:
            return
        print("المنشور وصل للمجموعة، جاري توليد تعليق علمي تلقائي...")
        prompt = f"اقرأ هذا المنشور بعناية وعلق عليه كخبير بمزيد من المعلومات المثرية والشيقة:\n{post_text}"
        ai_comment = generate_groq_content(prompt, SYSTEM_PROMPT_COMMENT)
        if ai_comment:
            await message.reply_text(ai_comment)
            return

    # ثانياً: الرد الذكي على أسئلة الأعضاء (منشن أو ريبلاي)
    bot_user = await context.bot.get_me()
    bot_username = f"@{bot_user.username}"
    
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_user.id
    is_mentioned = bot_username in message.text

    if is_reply_to_bot or is_mentioned:
        user_question = message.text.replace(bot_username, "").strip()
        print(f"سؤال جديد من أحد الأعضاء في المجموعة: {user_question}")
        
        prompt = f"أحد الأعضاء يسألك في مجموعة النقاش: {user_question}\nأجب عليه إجابة علمية مبسطة ومباشرة."
        ai_response = generate_groq_content(prompt, SYSTEM_PROMPT_GROUP_CHAT)
        if ai_response:
            await message.reply_text(ai_response)

def main():
    if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
        print("المتغيرات مفقودة في إعدادات ريلواي [خطأ فادح]")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # الجدولة الزمنية لنشر منشور جديد كل 30 دقيقة (1800 ثانية)
    job_queue = application.job_queue
    job_queue.run_repeating(auto_post_job, interval=1800, first=10)

    # تسجيل الأوامر الأساسية
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("testpost", test_post_command))

    # تسجيل مستمع الشات الخاص (تمت تصفية النصوص العادية بشكل مرن ومباشر)
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & (~filters.COMMAND), handle_private_chat))
    
    # تسجيل مستمع المجموعات (النصوص العادية)
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS & (~filters.COMMAND), handle_group_messages))

    application.run_polling()

if __name__ == "__main__":
    main()
                
