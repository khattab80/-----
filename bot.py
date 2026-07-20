import os
import logging
import asyncio
import requests
import wikipediaapi
from telegram import Update, InputMediaPhoto
from telegram.ext import Application, MessageHandler, ContextTypes, CommandHandler, filters
from groq import Groq

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID", "@Athar_Anthro")
if not CHANNEL_ID.startswith("@"):
    CHANNEL_ID = f"@{CHANNEL_ID}"
UNSPLASH_ACCESS_KEY = os.getenv("UNSPLASH_ACCESS_KEY", "kIjwGpgKjcSmYhgFRVA-guYHiTeXtVhm-Ihfar1_HnQ")

groq_client = Groq(api_key=GROQ_API_KEY)
wiki = wikipediaapi.Wikipedia(user_agent="AtharAnthroBot/1.0 (aass90.uk@gmail.com)", language="ar")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

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
        keyword = completion.choices[0].message.content.strip().replace('"', '').replace("'", "")
        return keyword
    except Exception:
        return "anthropology"


def get_unsplash_images(keyword, count=2):
    """Fetch `count` real Unsplash image URLs matching the keyword."""
    url = f"https://api.unsplash.com/search/photos?query={keyword}&per_page={count}&orientation=landscape&client_id={UNSPLASH_ACCESS_KEY}"
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        results = data.get("results", [])
        images = [r["urls"]["regular"] for r in results if "urls" in r]
        if len(images) >= count:
            return images[:count]
    except Exception as e:
        logging.error(f"خطأ Unsplash: {e}")
    # Fallback: two different Pexels-style static images
    fallback = [
        "https://images.pexels.com/photos/3184416/pexels-photo-3184416.jpeg",
        "https://images.pexels.com/photos/3184418/pexels-photo-3184418.jpeg",
    ]
    return fallback[:count]


def generate_groq_content(prompt, system_instruction):
    try:
        completion = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices[0].message.content
    except Exception as e:
        logging.error(f"خطأ في استدعاء Groq: {e}")
        return None


async def auto_post_job(context: ContextTypes.DEFAULT_TYPE):
    topic, raw_data = get_random_anthropology_data()
    prompt = f"اكتب منشوراً علمياً شيقاً وموجزاً جداً عن: {raw_data}"

    post_content = generate_groq_content(prompt, SYSTEM_PROMPT_POST)
    if not post_content:
        post_content = "موضوع اليوم يركز على الأنثروبولوجيا واستكشاف أصل المجتمعات وتطورها الثقافي والاجتماعي عبر العصور التاريخية المختلفة."

    english_keyword = get_english_search_keyword(topic)
    image_urls = get_unsplash_images(english_keyword, count=2)

    caption_text = f"✨ {topic} ✨\n\n{post_content}"
    if len(caption_text) > 1024:
        caption_text = caption_text[:1020] + "..."

    try:
        media_group = [
            InputMediaPhoto(media=image_urls[0], caption=caption_text, parse_mode="HTML"),
            InputMediaPhoto(media=image_urls[1]),
        ]
        await context.bot.send_media_group(chat_id=CHANNEL_ID, media=media_group)
        logging.info("تم النشر التلقائي بصورتين في القناة بنجاح")
    except Exception as e:
        logging.error(f"فشل إرسال مجموعة الصور: {e}")
        # Fallback: single photo
        try:
            await context.bot.send_photo(
                chat_id=CHANNEL_ID,
                photo=image_urls[0],
                caption=caption_text[:1024],
                parse_mode="HTML"
            )
            logging.info("تم النشر بصورة واحدة احتياطياً")
        except Exception as ce:
            logging.error(f"البوت لا يستطيع النشر نهائياً: {ce}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحباً بك في المحراب العلمي لـ أثر! أنا هنا كعالم إنثروبولوجيا مجيب، يمكنك سؤالي عن أي شيء يخص علوم الإنسان والمجتمعات في هذا الشات الخاص وسأجيبك فوراً!"
    )


async def test_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("جاري تجربة النشر الفوري في القناة الآن... انتظر لحظة ⏳")
    await auto_post_job(context)


async def handle_private_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    user_query = update.message.text
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    ai_response = generate_groq_content(user_query, SYSTEM_PROMPT_PRIVATE_CHAT)
    if ai_response:
        await update.message.reply_text(ai_response)
    else:
        await update.message.reply_text("أعتذر منك يا محب العلم، واجهت صعوبة في معالجة السؤال حالياً.")


async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    is_forwarded = message.forward_from_chat is not None
    if is_forwarded and message.forward_from_chat.username == CHANNEL_ID.replace("@", ""):
        post_text = message.text or message.caption
        if not post_text:
            return
        prompt = f"اقرأ هذا المنشور بعناية وعلق عليه كخبير بمزيد من المعلومات المثرية والشيقة:\n{post_text}"
        ai_comment = generate_groq_content(prompt, SYSTEM_PROMPT_COMMENT)
        if ai_comment:
            await message.reply_text(ai_comment)
        return

    bot_user = await context.bot.get_me()
    bot_username = f"@{bot_user.username}"
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot_user.id
    is_mentioned = bot_username in message.text

    if is_reply_to_bot or is_mentioned:
        user_question = message.text.replace(bot_username, "").strip()
        prompt = f"أحد الأعضاء يسألك في مجموعة النقاش: {user_question}\nأجب عليه إجابة علمية مبسطة ومباشرة."
        ai_response = generate_groq_content(prompt, SYSTEM_PROMPT_GROUP_CHAT)
        if ai_response:
            await message.reply_text(ai_response)


def main():
    if not TELEGRAM_BOT_TOKEN or not GROQ_API_KEY:
        print("المتغيرات مفقودة في إعدادات ريلواي [خطأ فادح]")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # النشر كل 3 ساعات (10800 ثانية)
    job_queue = application.job_queue
    job_queue.run_repeating(auto_post_job, interval=10800, first=10)

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("testpost", test_post_command))
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.PRIVATE & (~filters.COMMAND), handle_private_chat))
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS & (~filters.COMMAND), handle_group_messages))

    application.run_polling()


if __name__ == "__main__":
    main()
