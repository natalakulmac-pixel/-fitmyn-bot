import asyncio
import base64
import gzip
import html as html_lib
import hashlib
import hmac
import json
import logging
import os
import re
import time
import random
from urllib.parse import parse_qsl
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import asyncpg
from aiohttp import web, ClientSession, ClientTimeout
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    Update,
    MenuButtonWebApp,
    WebAppInfo,
    LabeledPrice,
    PreCheckoutQuery,
)
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openrouter/free").strip()
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1").strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "fitmyn-webhook").strip()
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "10000"))
CRON_SECRET = os.getenv("CRON_SECRET", "").strip()
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Europe/Moscow").strip() or "Europe/Moscow"
DEFAULT_MORNING_TIME = os.getenv("DEFAULT_MORNING_TIME", "08:00").strip() or "08:00"
DEFAULT_EVENING_TIME = os.getenv("DEFAULT_EVENING_TIME", "20:30").strip() or "20:30"
TRIAL_DAYS = 14
SUBSCRIPTION_STARS = int(os.getenv("SUBSCRIPTION_STARS", "350"))
SUBSCRIPTION_PERIOD = 30 * 24 * 60 * 60
APP_BUILD_VERSION = "v26-core-sync-subscription-images-1"
APP_URL = f"{RENDER_EXTERNAL_URL}/app?v={APP_BUILD_VERSION}" if RENDER_EXTERNAL_URL else ""
MINI_APP_HTML_GZIP_B64 = """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"""
MINI_APP_HTML = gzip.decompress(base64.b64decode(MINI_APP_HTML_GZIP_B64)).decode("utf-8")
MINI_APP_MEAL_IMAGE_SOURCES = {'oatmeal': ('Завтрак', 'Овсянка с ягодами и орехами', 'https://images.unsplash.com/photo-1517673132405-a56a62b18caf?auto=format&fit=crop&w=900&q=85'), 'omeletSpinach': ('Завтрак', 'Омлет со шпинатом и томатами', 'https://snapcalorie-webflow-website.s3.us-east-2.amazonaws.com/media/food_pics_v2/medium/omelette_with_spinach_and_tomatoes.jpg'), 'yogurtGranola': ('Завтрак', 'Греческий йогурт с гранолой и ягодами', 'https://suckhoedoisong.qltns.mediacdn.vn/324455921873985536/2023/5/11/sua-chua-2-16837932984001329860943.jpg'), 'avocadoEgg': ('Завтрак', 'Тост с авокадо и яйцом', 'https://claraplate.com/wp-content/uploads/2025/05/Avocado-Toast-with-Egg-1.webp'), 'smoothieBowl': ('Завтрак', 'Смузи-боул с киви и ягодами', 'https://bucket.cooklaif.com/321-coconut-berry-bliss-smoothie-321.jpg'), 'chiaPudding': ('Завтрак', 'Чиа-пудинг с ягодами', 'https://www.gosupps.com/media/catalog/product/cache/25/image/1500x/040ec09b1e35df139433887a97daa66f/8/1/81MPLb09b8L._SL1500_.jpg'), 'cottageBerryBreakfast': ('Завтрак', 'Творог со свежими ягодами', 'https://res.cloudinary.com/solin-fitness/image/upload/c_scale%2Cw_800%2Cq_auto%2Cf_auto/single-meal-images/getinhrkdn5cfwlg7gka'), 'chickenQuinoa': ('Обед', 'Курица с киноа и овощами', 'https://res.cloudinary.com/solin-fitness/image/upload/c_scale%2Cw_800%2Cq_auto%2Cf_auto/single-meal-images/hrbxuivrdwx4olnrnrrh'), 'turkeyBuckwheat': ('Обед', 'Индейка с гречкой и свежими овощами', 'https://www.arise-app.com/images/dishes/ru/indejka-v-sobstvennom-soku-de5yx9.webp'), 'salmonRice': ('Обед', 'Лосось с рисом и брокколи', 'https://tb-static.uber.com/prod/image-proc/processed_images/bc22ea33e1d4604d3d5054267281f725/d03e52b3c8af19d8fa8222e23efd9cfa.jpeg'), 'tunaPasta': ('Обед', 'Паста с тунцом и томатами', 'https://i.pinimg.com/736x/e2/b0/27/e2b0271e758a703fb77f401ab4fe2c3a.jpg'), 'lentilSoup': ('Обед', 'Чечевичный суп с овощами', 'https://itsonly.recipes/images/recipeimages/lentil-and-vegetable-soup.webp'), 'beefBuckwheat': ('Обед', 'Говядина с гречкой и овощами', 'https://cdn.food.ru/unsigned/fit/640/480/ce/0/czM6Ly9tZWRpYS9waWN0dXJlcy8yMDI2MDMxNy8zcXdqUlQuanBlZw.jpg'), 'chickenSoup': ('Обед', 'Куриный крем-суп с овощами', 'https://www.arise-app.com/images/dishes/ru/kurinyj-kremsup-s-ovosami-pwvyqx.webp'), 'yogurtChia': ('Перекус', 'Йогурт с ягодами и чиа', 'https://diabetesfoodhub.org/sites/foodhub/files/styles/recipe_hero_banner_720w/public/2026-04/mixed-berry-chia-yogurt-bowl.png?h=af9bc2fc&itok=1CTuHlTU'), 'applePeanut': ('Перекус', 'Яблоко с арахисовой пастой', 'https://easylunches.com/cdn/shop/files/white-Photoroom_-_2025-11-10T145821.588.jpg?v=1762808449&width=1512'), 'cottageBanana': ('Перекус', 'Творог с бананом и чиа', 'https://res.cloudinary.com/solin-fitness/image/upload/c_scale%2Cw_800%2Cq_auto%2Cf_auto/single-meal-images/yjbnpx9ltecafomqyit7'), 'kefirBerries': ('Перекус', 'Кефир со свежими ягодами', 'https://cdn.shopify.com/s/files/1/0555/8661/9426/files/kefir-abnehmen-hero.png?v=1769499265'), 'yogurtNuts': ('Перекус', 'Йогурт с бананом, ягодами и орехами', 'https://www.arise-app.com/images/dishes/en/yogurt-bowl-with-fruit-and-nuts-1rgog6.webp'), 'hummusVeg': ('Перекус', 'Хумус с морковью и огурцом', 'https://img.siterank.app/topic/veggie-sticks-hummus-snack-dish.png'), 'bananaPeanut': ('Перекус', 'Банан с арахисовой пастой', 'https://hips.hearstapps.com/hmg-prod/images/light-healthy-snack-made-from-banana-slices-and-royalty-free-image-913465318-1559057454.jpg?crop=0.607xw%3A0.908xh%3B0.0153xw%2C0.0918xh'), 'salmonBroccoli': ('Ужин', 'Лосось с брокколи и лимоном', 'https://www.reciz.com/img.php?f=lemon-garlic-salmon-broccoli-a-healthy-delight_featured_598.jpg&w=600'), 'codVeg': ('Ужин', 'Запечённая треска с овощами', 'https://mancaregatita.ro/cdn/shop/files/cod_la_tava_cu_legume.png?v=1755085091&width=2048'), 'chickenRoastVeg': ('Ужин', 'Куриная грудка с запечёнными овощами', 'https://www.arise-app.com/images/dishes/de/hahnchenbrust-mit-ofengemuse-17ofd2.webp'), 'turkeyStew': ('Ужин', 'Тушёная индейка с овощами', 'https://snapcalorie-webflow-website.s3.us-east-2.amazonaws.com/media/recipe_pics_v2/medium/hearty_turkey_stew.jpg'), 'shrimpZoodles': ('Ужин', 'Креветки с лапшой из кабачка', 'https://jpimg.com.br/uploads/2023/07/4-receitas-economicas-e-deliciosas-com-frutos-do-mar.jpg'), 'ratatouilleQuinoa': ('Ужин', 'Рататуй с киноа', 'https://itsonly.recipes/images/recipeimages/thumbnails/650/herbed-ratatouille-with-quinoa.webp'), 'turkeyGrillVeg': ('Ужин', 'Индейка-гриль с овощами', 'https://res.cloudinary.com/solin-fitness/image/upload/c_scale%2Cw_800%2Cq_auto%2Cf_auto/single-meal-images/fdohovk0dwhy5oglqdsi')}

ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().isdigit()
}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fitmyn")

router = Router()
dp = Dispatcher(storage=MemoryStorage())
dp.include_router(router)

bot = Bot(TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None
client = AsyncOpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL) if OPENAI_API_KEY else None
pool: asyncpg.Pool | None = None

_seen_update_ids: dict[int, float] = {}
_update_tasks: set[asyncio.Task] = set()
UPDATE_DEDUPE_TTL = 600

APP_MEAL_TYPE_ORDER = ["Завтрак", "Обед", "Перекус", "Ужин"]
APP_MEAL_CATALOG = {
    "oatsApple": {"type": "Завтрак", "name": "Овсянка с яблоком и корицей", "kcal": 330, "cook": 10, "protein": 23, "fat": 10, "carbs": 37, "budget": True, "goals": ["loss","maintain"]},
    "oatsBanana": {"type": "Завтрак", "name": "Овсянка с бананом", "kcal": 370, "cook": 10, "protein": 26, "fat": 12, "carbs": 40, "budget": True, "goals": ["loss","maintain"]},
    "milletPumpkin": {"type": "Завтрак", "name": "Пшённая каша с тыквой", "kcal": 340, "cook": 20, "protein": 24, "fat": 11, "carbs": 36, "budget": True, "goals": ["loss","maintain"]},
    "ricePorridge": {"type": "Завтрак", "name": "Рисовая каша с яблоком", "kcal": 350, "cook": 20, "protein": 25, "fat": 11, "carbs": 38, "budget": True, "goals": ["loss","maintain"]},
    "buckwheatEgg": {"type": "Завтрак", "name": "Гречка с яйцом и овощами", "kcal": 390, "cook": 15, "protein": 27, "fat": 12, "carbs": 44, "budget": True, "goals": ["loss","maintain"]},
    "omeletVeg": {"type": "Завтрак", "name": "Омлет с овощами", "kcal": 350, "cook": 12, "protein": 25, "fat": 11, "carbs": 38, "budget": True, "goals": ["loss","maintain"]},
    "eggsToast": {"type": "Завтрак", "name": "Яйца с цельнозерновым тостом", "kcal": 380, "cook": 10, "protein": 27, "fat": 12, "carbs": 41, "budget": True, "goals": ["loss","maintain"]},
    "cottageApple": {"type": "Завтрак", "name": "Творог с яблоком и корицей", "kcal": 320, "cook": 5, "protein": 22, "fat": 10, "carbs": 36, "budget": True, "goals": ["loss","maintain"]},
    "cottageBanana2": {"type": "Завтрак", "name": "Творог с бананом", "kcal": 380, "cook": 5, "protein": 27, "fat": 12, "carbs": 41, "budget": True, "goals": ["loss","maintain"]},
    "kefirOats": {"type": "Завтрак", "name": "Ленивая овсянка на кефире", "kcal": 360, "cook": 5, "protein": 25, "fat": 11, "carbs": 40, "budget": True, "goals": ["loss","maintain"]},
    "cheeseOmelet": {"type": "Завтрак", "name": "Омлет с сыром и томатами", "kcal": 420, "cook": 12, "protein": 29, "fat": 13, "carbs": 47, "budget": True, "goals": ["loss","maintain","gain"]},
    "oatPancakes": {"type": "Завтрак", "name": "Овсяноблин с творогом", "kcal": 410, "cook": 15, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "syrniki": {"type": "Завтрак", "name": "Сырники в духовке", "kcal": 430, "cook": 25, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "lavashEgg": {"type": "Завтрак", "name": "Лаваш с яйцом и сыром", "kcal": 440, "cook": 12, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "sandwichChicken": {"type": "Завтрак", "name": "Сэндвич с курицей и яйцом", "kcal": 470, "cook": 10, "protein": 33, "fat": 15, "carbs": 51, "budget": True, "goals": ["maintain","gain"]},
    "buckwheatMilk": {"type": "Завтрак", "name": "Гречневая каша с молоком", "kcal": 360, "cook": 15, "protein": 25, "fat": 11, "carbs": 40, "budget": True, "goals": ["loss","maintain"]},
    "semolinaBerry": {"type": "Завтрак", "name": "Манная каша с ягодами", "kcal": 350, "cook": 10, "protein": 25, "fat": 11, "carbs": 38, "budget": True, "goals": ["loss","maintain"]},
    "cottageCarrot": {"type": "Завтрак", "name": "Творожная запеканка с морковью", "kcal": 400, "cook": 35, "protein": 28, "fat": 12, "carbs": 45, "budget": True, "goals": ["loss","maintain","gain"]},
    "eggPotato": {"type": "Завтрак", "name": "Яйца с картофелем и овощами", "kcal": 450, "cook": 20, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "oatsCottage": {"type": "Завтрак", "name": "Овсянка с творогом и бананом", "kcal": 460, "cook": 10, "protein": 32, "fat": 14, "carbs": 52, "budget": True, "goals": ["maintain","gain"]},
    "pitaOmelet": {"type": "Завтрак", "name": "Пита с омлетом и овощами", "kcal": 450, "cook": 15, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "toastCottage": {"type": "Завтрак", "name": "Тосты с творогом и бананом", "kcal": 400, "cook": 7, "protein": 28, "fat": 12, "carbs": 45, "budget": True, "goals": ["loss","maintain","gain"]},
    "applePancakes": {"type": "Завтрак", "name": "Яблочные овсяные оладьи", "kcal": 390, "cook": 18, "protein": 27, "fat": 12, "carbs": 44, "budget": True, "goals": ["loss","maintain"]},
    "eggRice": {"type": "Завтрак", "name": "Рис с яйцом и овощами", "kcal": 430, "cook": 15, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "cottageRaisins": {"type": "Завтрак", "name": "Творог с изюмом и овсянкой", "kcal": 420, "cook": 5, "protein": 29, "fat": 13, "carbs": 47, "budget": True, "goals": ["loss","maintain","gain"]},
    "omeletChicken": {"type": "Завтрак", "name": "Омлет с курицей", "kcal": 470, "cook": 15, "protein": 33, "fat": 15, "carbs": 51, "budget": True, "goals": ["maintain","gain"]},
    "bananaPorridge": {"type": "Завтрак", "name": "Пшённая каша с бананом", "kcal": 390, "cook": 20, "protein": 27, "fat": 12, "carbs": 44, "budget": True, "goals": ["loss","maintain"]},
    "bakedOats": {"type": "Завтрак", "name": "Запечённая овсянка с яблоком", "kcal": 410, "cook": 30, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "eggBeans": {"type": "Завтрак", "name": "Яйца с фасолью и томатами", "kcal": 440, "cook": 15, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "curdLavash": {"type": "Завтрак", "name": "Лаваш с творогом и яблоком", "kcal": 430, "cook": 15, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "chickenBuckwheat": {"type": "Обед", "name": "Курица с гречкой и овощами", "kcal": 500, "cook": 25, "protein": 35, "fat": 16, "carbs": 54, "budget": True, "goals": ["maintain","gain"]},
    "chickenRice": {"type": "Обед", "name": "Курица с рисом и овощами", "kcal": 520, "cook": 25, "protein": 36, "fat": 16, "carbs": 58, "budget": True, "goals": ["maintain","gain"]},
    "chickenPasta": {"type": "Обед", "name": "Паста с курицей и томатами", "kcal": 540, "cook": 25, "protein": 38, "fat": 17, "carbs": 59, "budget": True, "goals": ["maintain","gain"]},
    "chickenPotato": {"type": "Обед", "name": "Курица с картофелем и салатом", "kcal": 510, "cook": 30, "protein": 36, "fat": 16, "carbs": 56, "budget": True, "goals": ["maintain","gain"]},
    "turkeyRice": {"type": "Обед", "name": "Индейка с рисом и морковью", "kcal": 520, "cook": 25, "protein": 36, "fat": 16, "carbs": 58, "budget": True, "goals": ["maintain","gain"]},
    "turkeyPasta": {"type": "Обед", "name": "Макароны с индейкой в томатном соусе", "kcal": 540, "cook": 25, "protein": 38, "fat": 17, "carbs": 59, "budget": True, "goals": ["maintain","gain"]},
    "beefBarley": {"type": "Обед", "name": "Говядина с перловкой", "kcal": 530, "cook": 35, "protein": 37, "fat": 16, "carbs": 60, "budget": True, "goals": ["maintain","gain"]},
    "beefRice": {"type": "Обед", "name": "Говядина с рисом и овощами", "kcal": 550, "cook": 30, "protein": 39, "fat": 17, "carbs": 60, "budget": True, "goals": ["maintain","gain"]},
    "liverBuckwheat": {"type": "Обед", "name": "Куриная печень с гречкой", "kcal": 490, "cook": 25, "protein": 34, "fat": 15, "carbs": 55, "budget": True, "goals": ["maintain","gain"]},
    "liverPotato": {"type": "Обед", "name": "Печень с картофельным пюре", "kcal": 510, "cook": 30, "protein": 36, "fat": 16, "carbs": 56, "budget": True, "goals": ["maintain","gain"]},
    "pollockRice": {"type": "Обед", "name": "Минтай с рисом и овощами", "kcal": 480, "cook": 25, "protein": 34, "fat": 15, "carbs": 52, "budget": True, "goals": ["maintain","gain"]},
    "pollockPotato": {"type": "Обед", "name": "Минтай с картофелем и салатом", "kcal": 470, "cook": 30, "protein": 33, "fat": 15, "carbs": 51, "budget": True, "goals": ["maintain","gain"]},
    "mackerelPotato": {"type": "Обед", "name": "Скумбрия с картофелем и капустой", "kcal": 540, "cook": 30, "protein": 38, "fat": 17, "carbs": 59, "budget": True, "goals": ["maintain","gain"]},
    "tunaRice": {"type": "Обед", "name": "Рис с тунцом и кукурузой", "kcal": 500, "cook": 15, "protein": 35, "fat": 16, "carbs": 54, "budget": True, "goals": ["maintain","gain"]},
    "lentilChicken": {"type": "Обед", "name": "Чечевица с курицей и овощами", "kcal": 510, "cook": 30, "protein": 36, "fat": 16, "carbs": 56, "budget": True, "goals": ["maintain","gain"]},
    "lentilStew": {"type": "Обед", "name": "Чечевичное рагу с овощами", "kcal": 450, "cook": 30, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "beansRice": {"type": "Обед", "name": "Фасоль с рисом и овощами", "kcal": 470, "cook": 25, "protein": 33, "fat": 15, "carbs": 51, "budget": True, "goals": ["maintain","gain"]},
    "peasChicken": {"type": "Обед", "name": "Гороховое пюре с курицей", "kcal": 510, "cook": 35, "protein": 36, "fat": 16, "carbs": 56, "budget": True, "goals": ["maintain","gain"]},
    "chickenBorscht": {"type": "Обед", "name": "Борщ с курицей и сметаной", "kcal": 440, "cook": 45, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "peaSoup": {"type": "Обед", "name": "Гороховый суп с курицей", "kcal": 460, "cook": 45, "protein": 32, "fat": 14, "carbs": 52, "budget": True, "goals": ["maintain","gain"]},
    "chickenNoodleSoup": {"type": "Обед", "name": "Куриный суп с лапшой", "kcal": 430, "cook": 35, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "meatballsBuckwheat": {"type": "Обед", "name": "Куриные тефтели с гречкой", "kcal": 510, "cook": 35, "protein": 36, "fat": 16, "carbs": 56, "budget": True, "goals": ["maintain","gain"]},
    "meatballsPasta": {"type": "Обед", "name": "Тефтели из индейки с макаронами", "kcal": 530, "cook": 35, "protein": 37, "fat": 16, "carbs": 60, "budget": True, "goals": ["maintain","gain"]},
    "cabbageChicken": {"type": "Обед", "name": "Тушёная капуста с курицей", "kcal": 460, "cook": 35, "protein": 32, "fat": 14, "carbs": 52, "budget": True, "goals": ["maintain","gain"]},
    "lazyCabbageRolls": {"type": "Обед", "name": "Ленивые голубцы с рисом", "kcal": 500, "cook": 40, "protein": 35, "fat": 16, "carbs": 54, "budget": True, "goals": ["maintain","gain"]},
    "pilafChicken": {"type": "Обед", "name": "Домашний плов с курицей", "kcal": 550, "cook": 40, "protein": 39, "fat": 17, "carbs": 60, "budget": True, "goals": ["maintain","gain"]},
    "pastaBeans": {"type": "Обед", "name": "Паста с фасолью и томатами", "kcal": 480, "cook": 20, "protein": 34, "fat": 15, "carbs": 52, "budget": True, "goals": ["maintain","gain"]},
    "buckwheatMushroomChicken": {"type": "Обед", "name": "Гречка с курицей и грибами", "kcal": 520, "cook": 30, "protein": 36, "fat": 16, "carbs": 58, "budget": True, "goals": ["maintain","gain"]},
    "potatoTurkeyStew": {"type": "Обед", "name": "Картофельное рагу с индейкой", "kcal": 500, "cook": 35, "protein": 35, "fat": 16, "carbs": 54, "budget": True, "goals": ["maintain","gain"]},
    "barleyChicken": {"type": "Обед", "name": "Перловка с курицей и овощами", "kcal": 490, "cook": 40, "protein": 34, "fat": 15, "carbs": 55, "budget": True, "goals": ["maintain","gain"]},
    "appleKefir": {"type": "Перекус", "name": "Яблоко и кефир", "kcal": 190, "cook": 2, "protein": 9, "fat": 6, "carbs": 25, "budget": True, "goals": ["loss","maintain"]},
    "bananaKefir": {"type": "Перекус", "name": "Банан и кефир", "kcal": 220, "cook": 2, "protein": 10, "fat": 7, "carbs": 29, "budget": True, "goals": ["loss","maintain"]},
    "cottageAppleSnack": {"type": "Перекус", "name": "Творог с яблоком", "kcal": 230, "cook": 4, "protein": 10, "fat": 7, "carbs": 32, "budget": True, "goals": ["loss","maintain"]},
    "cottageBananaSnack": {"type": "Перекус", "name": "Творог с бананом", "kcal": 270, "cook": 4, "protein": 12, "fat": 8, "carbs": 38, "budget": True, "goals": ["loss","maintain"]},
    "yogurtApple": {"type": "Перекус", "name": "Йогурт с яблоком и овсянкой", "kcal": 240, "cook": 4, "protein": 11, "fat": 7, "carbs": 33, "budget": True, "goals": ["loss","maintain"]},
    "yogurtBanana": {"type": "Перекус", "name": "Йогурт с бананом", "kcal": 230, "cook": 3, "protein": 10, "fat": 7, "carbs": 32, "budget": True, "goals": ["loss","maintain"]},
    "eggToastSnack": {"type": "Перекус", "name": "Яйцо и цельнозерновой тост", "kcal": 220, "cook": 8, "protein": 10, "fat": 7, "carbs": 29, "budget": True, "goals": ["loss","maintain"]},
    "cheeseApple": {"type": "Перекус", "name": "Сыр и яблоко", "kcal": 230, "cook": 2, "protein": 10, "fat": 7, "carbs": 32, "budget": True, "goals": ["loss","maintain"]},
    "kefirOatSnack": {"type": "Перекус", "name": "Кефир с овсяными хлопьями", "kcal": 220, "cook": 3, "protein": 10, "fat": 7, "carbs": 29, "budget": True, "goals": ["loss","maintain"]},
    "carrotHummus": {"type": "Перекус", "name": "Морковь с домашним хумусом", "kcal": 210, "cook": 5, "protein": 9, "fat": 7, "carbs": 28, "budget": True, "goals": ["loss","maintain"]},
    "bananaPeanutBudget": {"type": "Перекус", "name": "Банан с арахисовой пастой", "kcal": 250, "cook": 3, "protein": 11, "fat": 8, "carbs": 34, "budget": True, "goals": ["loss","maintain"]},
    "applePeanutBudget": {"type": "Перекус", "name": "Яблоко с арахисовой пастой", "kcal": 230, "cook": 3, "protein": 10, "fat": 7, "carbs": 32, "budget": True, "goals": ["loss","maintain"]},
    "curdRaisins": {"type": "Перекус", "name": "Творог с изюмом", "kcal": 250, "cook": 4, "protein": 11, "fat": 8, "carbs": 34, "budget": True, "goals": ["loss","maintain"]},
    "yogurtSeeds": {"type": "Перекус", "name": "Йогурт с семечками", "kcal": 240, "cook": 3, "protein": 11, "fat": 7, "carbs": 33, "budget": True, "goals": ["loss","maintain"]},
    "milkBanana": {"type": "Перекус", "name": "Молочно-банановый коктейль", "kcal": 250, "cook": 4, "protein": 11, "fat": 8, "carbs": 34, "budget": True, "goals": ["loss","maintain"]},
    "ryazhenkaApple": {"type": "Перекус", "name": "Ряженка и яблоко", "kcal": 220, "cook": 2, "protein": 10, "fat": 7, "carbs": 29, "budget": True, "goals": ["loss","maintain"]},
    "eggCucumber": {"type": "Перекус", "name": "Яйца и огурец", "kcal": 200, "cook": 8, "protein": 9, "fat": 6, "carbs": 28, "budget": True, "goals": ["loss","maintain"]},
    "toastCheese": {"type": "Перекус", "name": "Тост с сыром и томатом", "kcal": 250, "cook": 6, "protein": 11, "fat": 8, "carbs": 34, "budget": True, "goals": ["loss","maintain"]},
    "cottageCarrotSnack": {"type": "Перекус", "name": "Творог с морковью и зеленью", "kcal": 210, "cook": 5, "protein": 9, "fat": 7, "carbs": 28, "budget": True, "goals": ["loss","maintain"]},
    "beansToast": {"type": "Перекус", "name": "Паштет из фасоли с хлебцем", "kcal": 230, "cook": 7, "protein": 10, "fat": 7, "carbs": 32, "budget": True, "goals": ["loss","maintain"]},
    "bakedAppleCurd": {"type": "Перекус", "name": "Запечённое яблоко с творогом", "kcal": 250, "cook": 20, "protein": 11, "fat": 8, "carbs": 34, "budget": True, "goals": ["loss","maintain"]},
    "bananaOatsSnack": {"type": "Перекус", "name": "Банан с овсянкой и йогуртом", "kcal": 270, "cook": 5, "protein": 12, "fat": 8, "carbs": 38, "budget": True, "goals": ["loss","maintain"]},
    "kefirCottage": {"type": "Перекус", "name": "Кефир и творог", "kcal": 240, "cook": 3, "protein": 11, "fat": 7, "carbs": 33, "budget": True, "goals": ["loss","maintain"]},
    "appleSunflower": {"type": "Перекус", "name": "Яблоко с семечками", "kcal": 210, "cook": 2, "protein": 9, "fat": 7, "carbs": 28, "budget": True, "goals": ["loss","maintain"]},
    "pearYogurt": {"type": "Перекус", "name": "Груша с йогуртом", "kcal": 220, "cook": 3, "protein": 10, "fat": 7, "carbs": 29, "budget": True, "goals": ["loss","maintain"]},
    "curdCocoa": {"type": "Перекус", "name": "Творог с какао и бананом", "kcal": 270, "cook": 4, "protein": 12, "fat": 8, "carbs": 38, "budget": True, "goals": ["loss","maintain"]},
    "eggLavashSnack": {"type": "Перекус", "name": "Мини-лаваш с яйцом", "kcal": 260, "cook": 10, "protein": 12, "fat": 8, "carbs": 35, "budget": True, "goals": ["loss","maintain"]},
    "oatCookieKefir": {"type": "Перекус", "name": "Домашнее овсяное печенье и кефир", "kcal": 250, "cook": 20, "protein": 11, "fat": 8, "carbs": 34, "budget": True, "goals": ["loss","maintain"]},
    "cheeseCucumberToast": {"type": "Перекус", "name": "Тост с сыром и огурцом", "kcal": 240, "cook": 5, "protein": 11, "fat": 7, "carbs": 33, "budget": True, "goals": ["loss","maintain"]},
    "bananaCottageMini": {"type": "Перекус", "name": "Банан с творогом", "kcal": 260, "cook": 3, "protein": 12, "fat": 8, "carbs": 35, "budget": True, "goals": ["loss","maintain"]},
    "chickenCabbage": {"type": "Ужин", "name": "Курица с тушёной капустой", "kcal": 400, "cook": 30, "protein": 28, "fat": 12, "carbs": 45, "budget": True, "goals": ["loss","maintain","gain"]},
    "chickenVeg": {"type": "Ужин", "name": "Курица с овощами на сковороде", "kcal": 410, "cook": 25, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "chickenBuckwheatDinner": {"type": "Ужин", "name": "Курица с гречкой и салатом", "kcal": 440, "cook": 25, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "turkeyCabbage": {"type": "Ужин", "name": "Индейка с капустой и морковью", "kcal": 410, "cook": 30, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "turkeyVeg": {"type": "Ужин", "name": "Индейка с овощным рагу", "kcal": 420, "cook": 30, "protein": 29, "fat": 13, "carbs": 47, "budget": True, "goals": ["loss","maintain","gain"]},
    "pollockVeg": {"type": "Ужин", "name": "Минтай с овощами", "kcal": 380, "cook": 25, "protein": 27, "fat": 12, "carbs": 41, "budget": True, "goals": ["loss","maintain"]},
    "pollockPotatoDinner": {"type": "Ужин", "name": "Минтай с картофелем и огурцом", "kcal": 430, "cook": 30, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "mackerelSalad": {"type": "Ужин", "name": "Скумбрия с капустным салатом", "kcal": 450, "cook": 25, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "liverVeg": {"type": "Ужин", "name": "Куриная печень с овощами", "kcal": 410, "cook": 25, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "liverBuckwheatDinner": {"type": "Ужин", "name": "Печень с гречкой и огурцом", "kcal": 440, "cook": 25, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "omeletDinner": {"type": "Ужин", "name": "Омлет с овощами и сыром", "kcal": 390, "cook": 15, "protein": 27, "fat": 12, "carbs": 44, "budget": True, "goals": ["loss","maintain"]},
    "cottageDinner": {"type": "Ужин", "name": "Творог с зеленью и овощами", "kcal": 340, "cook": 5, "protein": 24, "fat": 11, "carbs": 36, "budget": True, "goals": ["loss","maintain"]},
    "beansChicken": {"type": "Ужин", "name": "Фасоль с курицей и томатами", "kcal": 430, "cook": 25, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "lentilTurkey": {"type": "Ужин", "name": "Чечевица с индейкой", "kcal": 440, "cook": 30, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "lentilVegDinner": {"type": "Ужин", "name": "Чечевица с овощами", "kcal": 390, "cook": 25, "protein": 27, "fat": 12, "carbs": 44, "budget": True, "goals": ["loss","maintain"]},
    "cabbageMeatballs": {"type": "Ужин", "name": "Капуста с куриными тефтелями", "kcal": 420, "cook": 35, "protein": 29, "fat": 13, "carbs": 47, "budget": True, "goals": ["loss","maintain","gain"]},
    "zucchiniChicken": {"type": "Ужин", "name": "Кабачки с курицей и томатами", "kcal": 390, "cook": 25, "protein": 27, "fat": 12, "carbs": 44, "budget": True, "goals": ["loss","maintain"]},
    "eggBeansDinner": {"type": "Ужин", "name": "Яйца с фасолью и овощами", "kcal": 400, "cook": 15, "protein": 28, "fat": 12, "carbs": 45, "budget": True, "goals": ["loss","maintain","gain"]},
    "buckwheatMushroomDinner": {"type": "Ужин", "name": "Гречка с грибами и яйцом", "kcal": 410, "cook": 25, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "riceChickenDinner": {"type": "Ужин", "name": "Рис с курицей и овощами", "kcal": 450, "cook": 25, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "potatoChickenDinner": {"type": "Ужин", "name": "Картофель с курицей и салатом", "kcal": 450, "cook": 30, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "pastaTurkeyDinner": {"type": "Ужин", "name": "Паста с индейкой и овощами", "kcal": 460, "cook": 25, "protein": 32, "fat": 14, "carbs": 52, "budget": True, "goals": ["maintain","gain"]},
    "fishCabbage": {"type": "Ужин", "name": "Белая рыба с тушёной капустой", "kcal": 380, "cook": 25, "protein": 27, "fat": 12, "carbs": 41, "budget": True, "goals": ["loss","maintain"]},
    "chickenPumpkin": {"type": "Ужин", "name": "Курица с тыквой и гречкой", "kcal": 430, "cook": 30, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "turkeyPotatoDinner": {"type": "Ужин", "name": "Индейка с картофелем и овощами", "kcal": 450, "cook": 30, "protein": 32, "fat": 14, "carbs": 49, "budget": True, "goals": ["maintain","gain"]},
    "curdCasseroleDinner": {"type": "Ужин", "name": "Творожная запеканка без сахара", "kcal": 380, "cook": 35, "protein": 27, "fat": 12, "carbs": 41, "budget": True, "goals": ["loss","maintain"]},
    "omeletChickenDinner": {"type": "Ужин", "name": "Омлет с курицей и томатами", "kcal": 430, "cook": 15, "protein": 30, "fat": 13, "carbs": 48, "budget": True, "goals": ["loss","maintain","gain"]},
    "beansVegDinner": {"type": "Ужин", "name": "Фасоль с овощами и яйцом", "kcal": 410, "cook": 25, "protein": 29, "fat": 13, "carbs": 44, "budget": True, "goals": ["loss","maintain","gain"]},
    "chickenBarleyDinner": {"type": "Ужин", "name": "Курица с перловкой и овощами", "kcal": 440, "cook": 35, "protein": 31, "fat": 14, "carbs": 48, "budget": True, "goals": ["maintain","gain"]},
    "pollockBuckwheat": {"type": "Ужин", "name": "Минтай с гречкой и салатом", "kcal": 420, "cook": 25, "protein": 29, "fat": 13, "carbs": 47, "budget": True, "goals": ["loss","maintain","gain"]},

    # Простые белковые варианты: обычные продукты, без деликатесов.
    "proteinCurdEgg": {"type": "Завтрак", "name": "Творог с яйцом и цельнозерновым тостом", "kcal": 390, "cook": 8, "protein": 34, "fat": 13, "carbs": 34, "budget": True, "high_protein": True, "goals": ["loss","maintain","gain"]},
    "proteinOmeletCurd": {"type": "Завтрак", "name": "Омлет с творогом и томатами", "kcal": 370, "cook": 12, "protein": 33, "fat": 14, "carbs": 27, "budget": True, "high_protein": True, "goals": ["loss","maintain","gain"]},
    "proteinChickenEgg": {"type": "Завтрак", "name": "Яйца с курицей и овощами", "kcal": 400, "cook": 12, "protein": 38, "fat": 15, "carbs": 25, "budget": True, "high_protein": True, "goals": ["loss","maintain","gain"]},
    "proteinChickenBuckwheat": {"type": "Обед", "name": "Куриная грудка с гречкой и салатом", "kcal": 480, "cook": 25, "protein": 48, "fat": 13, "carbs": 43, "budget": True, "high_protein": True, "goals": ["loss","maintain","gain"]},
    "proteinTurkeyRice": {"type": "Обед", "name": "Индейка с рисом и овощами", "kcal": 490, "cook": 25, "protein": 46, "fat": 13, "carbs": 47, "budget": True, "high_protein": True, "goals": ["loss","maintain","gain"]},
    "proteinPollockPotato": {"type": "Обед", "name": "Минтай с картофелем и овощным салатом", "kcal": 440, "cook": 25, "protein": 42, "fat": 11, "carbs": 43, "budget": True, "high_protein": True, "goals": ["loss","maintain"]},
    "proteinCurdYogurt": {"type": "Перекус", "name": "Творог с натуральным йогуртом", "kcal": 220, "cook": 3, "protein": 26, "fat": 7, "carbs": 13, "budget": True, "high_protein": True, "goals": ["loss","maintain","gain"]},
    "proteinEggCurdSnack": {"type": "Перекус", "name": "Яйцо и творог с зеленью", "kcal": 210, "cook": 7, "protein": 23, "fat": 10, "carbs": 7, "budget": True, "high_protein": True, "goals": ["loss","maintain","gain"]},
    "proteinYogurtCurdApple": {"type": "Перекус", "name": "Йогурт с творогом и яблоком", "kcal": 240, "cook": 4, "protein": 24, "fat": 6, "carbs": 23, "budget": True, "high_protein": True, "goals": ["loss","maintain"]},
    "proteinChickenVeg": {"type": "Ужин", "name": "Куриная грудка с овощами", "kcal": 360, "cook": 22, "protein": 45, "fat": 12, "carbs": 18, "budget": True, "high_protein": True, "goals": ["loss","maintain","gain"]},
    "proteinTurkeyCabbage": {"type": "Ужин", "name": "Индейка с тушёной капустой", "kcal": 370, "cook": 25, "protein": 43, "fat": 12, "carbs": 22, "budget": True, "high_protein": True, "goals": ["loss","maintain","gain"]},
    "proteinCurdDinner": {"type": "Ужин", "name": "Творог с яйцом, огурцом и зеленью", "kcal": 330, "cook": 8, "protein": 36, "fat": 14, "carbs": 12, "budget": True, "high_protein": True, "goals": ["loss","maintain"]},
}

APP_CURATED_WEEK_IDS = {
    "Завтрак": ["proteinCurdEgg","proteinOmeletCurd","proteinChickenEgg","omeletVeg","oatsCottage","eggBeans","cottageApple"],
    "Обед": ["proteinChickenBuckwheat","proteinTurkeyRice","proteinPollockPotato","chickenRice","pastaBeans","lentilStew","chickenNoodleSoup"],
    "Перекус": ["proteinCurdYogurt","proteinEggCurdSnack","proteinYogurtCurdApple","cottageAppleSnack","yogurtBanana","eggToastSnack","beansToast"],
    "Ужин": ["proteinChickenVeg","proteinTurkeyCabbage","proteinCurdDinner","fishCabbage","omeletDinner","beansChicken","lentilVegDinner"],
}
APP_CURATED_MEAL_IDS = {mid for ids in APP_CURATED_WEEK_IDS.values() for mid in ids}

# Only audited dish photos are assigned. Unknown/unverified meals intentionally use None:
# the UI renders a neutral placeholder instead of showing another dish.
APP_MEAL_IMAGES = {
    "proteinChickenBuckwheat": "https://www.arise-app.com/images/dishes/ru/grecka-s-kuricej-i-ovosami-s-ogurcami-t6is4x.webp",
    "proteinCurdEgg": "https://nowcookthis.com/wp-content/uploads/2025/05/breakfast-cottage-cheese-toast-with-egg-1a.jpg",
    "proteinOmeletCurd": "https://cdn.shopify.com/s/files/1/0066/4295/8420/files/callekocht_omelette_selbstgemacht_600x600.jpg?v=1770793473",
    "proteinChickenEgg": "https://cdn.abo.media/upload/article/bstk5dgrxaxkfzphp49x.jpg",
    "omeletVeg": "https://www.arise-app.com/images/dishes/pt/omelete-de-legumes-13xb0x.webp",
    "oatsCottage": "https://cupofyum.com/uploads/images/000/250/161/250161-cottage-cheese-oatmeal-47837205e543a946afafebfc45d4ab03.jpg",
    "cottageApple": "https://pinterest-media-cdn.b-cdn.net/article-images/high-protein-snack-ideas-v2/snack_7_cottage_cheese_apple.png",
    "proteinTurkeyRice": "https://fitfoodway.hu/media/produse/pulykamell-zoeldfuszerekkel-zoeldsegekkel.jpg",
    "proteinPollockPotato": "https://www.arise-app.com/images/dishes/en/fish-with-potatoes-and-cherry-tomatoes-1xgbvn.webp",
    "chickenRice": "https://snapcalorie-webflow-website.s3.us-east-2.amazonaws.com/media/food_pics_v2/medium/rice_with_vegetables_and_chicken.jpg",
    "pastaBeans": "https://s3.us-east-2.amazonaws.com/pfimg1/013/e5/76/e576843f75f4f9787c00b457f4f32ee7_1280m.jpg",
    "lentilStew": "https://itsonly.recipes/images/recipeimages/hearty-lentil-stew.webp",
    "chickenNoodleSoup": "https://kochwunder.com/assets/images/1744123953542-yhby33g9.png",
    "proteinEggCurdSnack": "https://img.wprost.pl/_thumb/e6/6e/5a1da32bef5933b889a9fb65c820.jpeg",
    "cottageAppleSnack": None,
    "eggToastSnack": "https://images.deliveryhero.io/image/talabat/MenuItems/DAC359AEED66C855CAC41A45CC237C4D",
    "beansToast": "https://static.hnonline.sk/images/archive/2019/07/01/08a49b16-d3e4-4629-9726-0d57d9b0d62e.JPG",
    "proteinChickenVeg": "https://www.foodjajce.com/server/static/products/243.jpg",
    "proteinTurkeyCabbage": "https://irepo.primecp.com/2015/10/238976/EDR-Unstuffed-Cabbage-Skillet_ExtraLarge1000_ID-1218864.jpg?v=1218864",
    "proteinCurdDinner": "https://res.cloudinary.com/solin-fitness/image/upload/c_scale%2Cw_800%2Cq_auto%2Cf_auto/single-meal-images/vzkkh5v4vu06ovgr3nbk",
    "fishCabbage": "https://dt565gqrz3z7y.cloudfront.net/ce/image/nD22KuksvfOMIBqKrPR_tA.jpg",
    "omeletDinner": "https://cdn.goodsouppot.com/images/f694239a-8b43-44d9-94d5-1075886ab2ed_f80cfa79.webp",
    "beansChicken": "https://v.cdn.ww.com/media/system/wine/5e33ef0407ef3c0011189483/29105f3c-2d71-4270-86ef-cc1d386eea4d/pr4haicgplsgmtng9jji.jpg?enable=upscale&fit=crop&height=800&quality=80&width=800",
    "lentilVegDinner": None,
}

# Correct the curated quick-plan timings. Recipes assume pre-cooked grains where noted.
APP_MEAL_CATALOG["lentilStew"]["cook"] = 25
APP_MEAL_CATALOG["chickenNoodleSoup"]["cook"] = 25
for _mid in APP_CURATED_MEAL_IDS:
    APP_MEAL_CATALOG[_mid]["goals"] = ["loss","maintain","gain"]

def _meal_details(name: str):
    n = name.lower()
    ingredients = []
    rules = [
        (("куриц",), "куриная грудка 150 г"), (("индей",), "филе индейки 150 г"),
        (("минтай","белая рыба","рыб"), "филе белой рыбы 160 г"), (("яйц","омлет"), "яйца 2 шт."),
        (("творог","творож"), "творог 150 г"), (("йогурт",), "натуральный/греческий йогурт 120 г"),
        (("греч",), "гречка готовая 120 г"), (("рис",), "рис готовый 120 г"),
        (("овсян",), "овсяные хлопья 50 г"), (("макарон","паста"), "цельнозерновая паста 70 г"),
        (("картоф",), "картофель 180 г"), (("фасол",), "фасоль готовая 140 г"),
        (("чечев",), "чечевица готовая 160 г"), (("капуст",), "капуста 180 г"),
        (("томат",), "томаты 120 г"), (("огур",), "огурец 120 г"), (("яблок",), "яблоко 1 шт."),
        (("банан",), "банан 1 шт."), (("тост","хлеб"), "цельнозерновой хлеб 1–2 ломтика"),
        (("лапш",), "лапша 60 г"), (("овощ","салат"), "овощи 200 г"),
    ]
    for keys, value in rules:
        if any(k in n for k in keys) and value not in ingredients:
            ingredients.append(value)
    if not ingredients:
        ingredients = ["основные продукты по названию блюда"]
    if not any("овощ" in x or "томат" in x or "огур" in x or "капуст" in x for x in ingredients) and any(x in n for x in ("куриц","индей","рыб","омлет")):
        ingredients.append("свежие или замороженные овощи 150–200 г")
    if any(x in n for x in ("куриц","индей","рыб","минтай","омлет","яйц","фасол","чечев","паста","макарон")):
        ingredients += ["соль и специи по вкусу", "растительное масло 1 ч. л."]
    elif not any(x in n for x in ("яблок","банан","йогурт","творог","овсян")):
        ingredients += ["соль и специи по вкусу"]
    if "суп" in n:
        recipe = ["Подготовь и нарежь продукты.", "Доведи 450–500 мл воды или лёгкого бульона до кипения.", "Добавь ингредиенты и вари до готовности, в конце приправь."]
    elif any(x in n for x in ("творог","йогурт")) and not any(x in n for x in ("омлет","куриц","индей")):
        recipe = ["Подготовь все ингредиенты.", "Соедини их в миске.", "Добавь специи или зелень/фрукты по названию блюда и подавай сразу."]
    elif "омлет" in n or "яйц" in n:
        recipe = ["Нарежь добавки и разогрей сковороду.", "Взбей яйца, добавь остальные ингредиенты.", "Готовь под крышкой на среднем огне до готовности."]
    else:
        recipe = ["Подготовь и нарежь ингредиенты.", "Белковый продукт обжарь или прогрей до готовности.", "Добавь овощи и готовый гарнир, приправь и прогрей вместе 3–5 минут."]
    return ingredients, recipe

def app_meal_payload(meal_id: str):
    item = APP_MEAL_CATALOG[meal_id]
    ingredients, recipe = _meal_details(item["name"])
    return {
        "id": meal_id, "type": item["type"], "name": item["name"],
        "image": f"/api/app/meal-image/{meal_id}?v={APP_BUILD_VERSION}",
        "kcal": int(item["kcal"]), "protein": int(item["protein"]), "fat": int(item["fat"]), "carbs": int(item["carbs"]),
        "cookTime": int(item["cook"]), "ingredients": ingredients, "recipe": recipe,
    }

async def api_app_meal_image(request: web.Request):
    meal_id = request.match_info.get("meal_id", "")
    item = APP_MEAL_CATALOG.get(meal_id)
    if not item:
        return web.Response(status=404)
    url = APP_MEAL_IMAGES.get(meal_id)
    if url:
        try:
            timeout = ClientTimeout(total=7)
            async with ClientSession(timeout=timeout) as session:
                async with session.get(url, headers={"User-Agent": "Mozilla/5.0"}) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        ctype = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
                        if data and ctype.startswith("image/"):
                            return web.Response(body=data, content_type=ctype, headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            logger.warning("Meal image proxy fallback for %s", meal_id)
    name = re.sub(r"[<>&\"']", "", item["name"])[:52]
    kind = item["type"]
    accent = {"breakfast":"#d9b56d","lunch":"#7e9a62","snack":"#d8a5a5","dinner":"#67806c"}.get(kind,"#7e9a62")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640">
<rect width="960" height="640" fill="#f5f1e7"/><ellipse cx="480" cy="355" rx="310" ry="185" fill="#fffdf8" stroke="{accent}" stroke-width="18"/>
<ellipse cx="480" cy="355" rx="235" ry="125" fill="{accent}" opacity=".22"/><circle cx="390" cy="330" r="62" fill="{accent}" opacity=".72"/>
<circle cx="520" cy="380" r="74" fill="#d9c38d"/><circle cx="600" cy="305" r="48" fill="#8fa66f"/>
<text x="480" y="105" text-anchor="middle" font-family="Arial,sans-serif" font-size="38" font-weight="700" fill="#173b25">{name}</text>
<text x="480" y="585" text-anchor="middle" font-family="Arial,sans-serif" font-size="24" fill="#687168">Fitmy2.0 · фото блюда будет обновлено</text></svg>"""
    return web.Response(text=svg, content_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})


def serialize_weekly_meal_plan(row):
    raw = decode_app_plan(row["plan_json"])
    start = row["start_date"]
    keys = ["breakfast","lunch","snack","dinner"]
    return [
        {"date": (start + timedelta(days=i)).isoformat(), "meals": {keys[j]: str(raw[i][j]) for j in range(4)}}
        for i in range(7)
    ]

def catalog_for_week(row):
    ids = {mid for day in decode_app_plan(row["plan_json"]) for mid in day}
    return {mid: app_meal_payload(mid) for mid in ids if mid in APP_MEAL_CATALOG}



_main_rows = []
if APP_URL:
    _main_rows.append([KeyboardButton(text="📱 Открыть Fitmy2.0", web_app=WebAppInfo(url=APP_URL))])
_main_rows.extend([
    [KeyboardButton(text="🥗 Питание"), KeyboardButton(text="🏋️ Тренировка")],
    [KeyboardButton(text="📊 Отчёт"), KeyboardButton(text="📅 Неделя")],
    [KeyboardButton(text="🗓 Рацион на неделю"), KeyboardButton(text="🛒 Список покупок")],
    [KeyboardButton(text="💬 Спросить агента"), KeyboardButton(text="👤 Мой профиль")],
    [KeyboardButton(text="⏰ Расписание")],
])
MAIN_KB = ReplyKeyboardMarkup(keyboard=_main_rows, resize_keyboard=True)

CONSENT_KB = InlineKeyboardMarkup(
    inline_keyboard=[[
        InlineKeyboardButton(text="Согласен", callback_data="consent_yes"),
        InlineKeyboardButton(text="Не согласен", callback_data="consent_no"),
    ]]
)

SYSTEM_PROMPT = """
Ты — персональный ИИ-ассистент по питанию, тренировкам, восстановлению и устойчивым привычкам.

Работай как помощник по питанию, персональный тренер, трекер прогресса и коуч по привычкам.

Правила безопасности:
- Не ставь диагнозы и не заменяй врача.
- Не назначай лекарства, БАДы, гормоны или лечение.
- Не рекомендуй экстремальные диеты, длительное голодание, обезвоживание, очищения или опасное снижение веса.
- Не стыди человека за еду, вес, внешность или пропущенные тренировки.
- При боли в груди, выраженной одышке, обмороке, сильной необычной боли и других потенциально опасных симптомах
  рекомендуй прекратить тренировку и обратиться за медицинской помощью.
- При беременности, расстройствах пищевого поведения, серьёзных травмах, хронических заболеваниях или значимых лекарствах
  действуй осторожно и при необходимости рекомендуй консультацию профильного специалиста.
- Не создавай ложную точность для калорий и КБЖУ.
- Для тренировок учитывай уровень, ограничения, оборудование, восстановление и постепенную прогрессию.
- Для питания учитывай предпочтения, доступность продуктов, поездки, домашнюю еду и рестораны.
- Не раскрывай данные других пользователей.
- Для командной механики не соревнуй людей по весу, калориям или внешности.

Стиль ответа для Telegram:
- Пиши простым живым русским языком.
- Не используй Markdown-разметку: никаких **, ##, ``` и таблиц.
- Не используй HTML-теги, включая <br>.
- Не используй таблицы и вертикальные черты |.
- Делай короткие абзацы и списки с символом •.
- Для нумерации используй обычные 1., 2., 3.
- Заголовок — одна короткая строка с подходящим эмодзи.
- Не делай длинное полотно текста.
- Не повторяй данные профиля без необходимости.
- Для тренировки используй блоки: Цель, Разминка, Основная часть, Отдых, Заминка, Совет.
- Для питания на день используй блоки: Главная задача, Завтрак, Обед, Ужин, Перекус, Фокус дня.
- Для рациона на неделю составляй реалистичный план на 7 дней без таблиц: завтрак, обед, ужин и 1 перекус на каждый день.
- Рацион должен быть удобным в жизни: повторно используй продукты, учитывай остатки, не добавляй десятки редких ингредиентов.
- Список покупок должен точно соответствовать рациону и быть сгруппирован по категориям с примерным количеством на 1 человека.
- Ответ на обычный запрос обычно должен помещаться примерно в 900–1400 символов.
- Выводи только готовый текст для пользователя, без пояснений про форматирование.
"""

class Onboarding(StatesGroup):
    name = State()
    age = State()
    sex = State()
    height = State()
    weight = State()
    goal = State()
    activity = State()
    frequency = State()
    equipment = State()
    restrictions = State()
    food = State()
    sleep = State()

class Checkin(StatesGroup):
    waiting_report = State()

def now_utc():
    return datetime.now(timezone.utc)

async def db_execute(sql: str, *params):
    if not pool:
        raise RuntimeError("Database is not configured")
    async with pool.acquire() as conn:
        await conn.execute(sql, *params)

async def db_fetchrow(sql: str, *params):
    if not pool:
        raise RuntimeError("Database is not configured")
    async with pool.acquire() as conn:
        return await conn.fetchrow(sql, *params)

async def db_fetch(sql: str, *params):
    if not pool:
        raise RuntimeError("Database is not configured")
    async with pool.acquire() as conn:
        return await conn.fetch(sql, *params)

async def init_db():
    global pool
    if not DATABASE_URL:
        logger.warning("DATABASE_URL is missing; service starts in configuration mode")
        return

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=5)
    async with pool.acquire() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            telegram_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            consent BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL,
            last_seen TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS profiles (
            telegram_id BIGINT PRIMARY KEY,
            name TEXT,
            age TEXT,
            sex TEXT,
            height TEXT,
            weight TEXT,
            goal TEXT,
            activity TEXT,
            frequency TEXT,
            equipment TEXT,
            restrictions TEXT,
            food TEXT,
            sleep TEXT,
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS messages (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS checkins (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            report TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notification_settings (
            telegram_id BIGINT PRIMARY KEY,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            timezone TEXT NOT NULL DEFAULT 'Europe/Moscow',
            morning_time TEXT NOT NULL DEFAULT '08:00',
            evening_time TEXT NOT NULL DEFAULT '20:30',
            workout_days TEXT NOT NULL DEFAULT '0,2,4',
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS notification_log (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            kind TEXT NOT NULL,
            local_date DATE NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            UNIQUE(telegram_id, kind, local_date)
        );

        CREATE TABLE IF NOT EXISTS weekly_meal_plans (
            telegram_id BIGINT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            meal_plan TEXT NOT NULL,
            shopping_list TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (telegram_id, start_date)
        );

        CREATE TABLE IF NOT EXISTS app_week_plans (
            telegram_id BIGINT NOT NULL,
            start_date DATE NOT NULL,
            end_date DATE NOT NULL,
            plan_json JSONB NOT NULL,
            source TEXT NOT NULL DEFAULT 'fallback',
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (telegram_id, start_date)
        );

        CREATE TABLE IF NOT EXISTS app_goal_settings (
            telegram_id BIGINT PRIMARY KEY,
            target_weight NUMERIC(6,2),
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS app_weight_log (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            weight NUMERIC(6,2) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_app_weight_log_user_time
            ON app_weight_log(telegram_id, created_at DESC);

        CREATE TABLE IF NOT EXISTS app_water_log (
            telegram_id BIGINT NOT NULL,
            local_date DATE NOT NULL,
            water_ml INTEGER NOT NULL DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (telegram_id, local_date)
        );

        CREATE TABLE IF NOT EXISTS app_workout_log (
            telegram_id BIGINT NOT NULL,
            local_date DATE NOT NULL,
            workout_key TEXT NOT NULL,
            workout_name TEXT NOT NULL,
            completed_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (telegram_id, local_date, workout_key)
        );

        CREATE TABLE IF NOT EXISTS app_profile_photos (
            telegram_id BIGINT PRIMARY KEY,
            photo_data TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS app_subscriptions (
            telegram_id BIGINT PRIMARY KEY,
            trial_started_at TIMESTAMPTZ NOT NULL,
            trial_ends_at TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL DEFAULT 'trial',
            subscription_until TIMESTAMPTZ,
            telegram_payment_charge_id TEXT,
            auto_renew BOOLEAN NOT NULL DEFAULT FALSE,
            stars_amount INTEGER NOT NULL DEFAULT 350,
            updated_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS app_payments (
            id BIGSERIAL PRIMARY KEY,
            telegram_id BIGINT NOT NULL,
            telegram_payment_charge_id TEXT NOT NULL UNIQUE,
            total_amount INTEGER NOT NULL,
            currency TEXT NOT NULL,
            subscription_expiration_date TIMESTAMPTZ,
            is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
            is_first_recurring BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_app_payments_user_time
            ON app_payments(telegram_id, created_at DESC);
        """)

async def touch_user(message: Message):
    await db_execute(
        """
        INSERT INTO users(telegram_id, username, first_name, created_at, last_seen)
        VALUES ($1, $2, $3, $4, $4)
        ON CONFLICT(telegram_id) DO UPDATE SET
            username=EXCLUDED.username,
            first_name=EXCLUDED.first_name,
            last_seen=EXCLUDED.last_seen
        """,
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        now_utc(),
    )

async def has_consent(user_id: int) -> bool:
    row = await db_fetchrow("SELECT consent FROM users WHERE telegram_id=$1", user_id)
    return bool(row and row["consent"])


async def ensure_subscription(user_id: int):
    row = await db_fetchrow("SELECT * FROM app_subscriptions WHERE telegram_id=$1", user_id)
    if row:
        return row
    now = now_utc()
    trial_end = now + timedelta(days=TRIAL_DAYS)
    await db_execute(
        """INSERT INTO app_subscriptions(
            telegram_id, trial_started_at, trial_ends_at, status,
            subscription_until, telegram_payment_charge_id, auto_renew,
            stars_amount, updated_at
        ) VALUES($1,$2,$3,'trial',NULL,NULL,FALSE,$4,$2)
        ON CONFLICT(telegram_id) DO NOTHING""",
        user_id, now, trial_end, SUBSCRIPTION_STARS,
    )
    return await db_fetchrow("SELECT * FROM app_subscriptions WHERE telegram_id=$1", user_id)


async def subscription_info(user_id: int) -> dict:
    row = await ensure_subscription(user_id)
    now = now_utc()
    paid_until = row["subscription_until"]
    paid_active = bool(paid_until and paid_until > now)
    trial_active = bool(row["trial_ends_at"] and row["trial_ends_at"] > now)
    if paid_active:
        status = "active"
        access = True
        seconds_left = max(0, int((paid_until - now).total_seconds()))
        days_left = (seconds_left + 86399) // 86400
    elif trial_active:
        status = "trial"
        access = True
        seconds_left = max(0, int((row["trial_ends_at"] - now).total_seconds()))
        days_left = (seconds_left + 86399) // 86400
    else:
        status = "expired"
        access = False
        days_left = 0
        if row["status"] != "expired":
            await db_execute(
                "UPDATE app_subscriptions SET status='expired', auto_renew=FALSE, updated_at=$2 WHERE telegram_id=$1",
                user_id, now,
            )
    return {
        "status": status,
        "has_access": access,
        "trial_started_at": row["trial_started_at"].isoformat() if row["trial_started_at"] else None,
        "trial_ends_at": row["trial_ends_at"].isoformat() if row["trial_ends_at"] else None,
        "subscription_until": paid_until.isoformat() if paid_until else None,
        "days_left": int(days_left),
        "auto_renew": bool(row["auto_renew"]) if paid_active else False,
        "stars": SUBSCRIPTION_STARS,
        "period_days": 30,
    }


async def subscription_has_access(user_id: int) -> bool:
    return bool((await subscription_info(user_id))["has_access"])


async def create_subscription_invoice_link(user_id: int) -> str:
    if not bot:
        raise RuntimeError("Telegram bot is not configured")
    payload = f"fitmy2-sub:{user_id}:{int(time.time())}"
    return await bot.create_invoice_link(
        title="Fitmy2.0 — подписка",
        description="Полный доступ к питанию, тренировкам, прогрессу и ИИ-агенту на 30 дней. Автопродление каждые 30 дней.",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="Fitmy2.0 — 30 дней", amount=SUBSCRIPTION_STARS)],
        subscription_period=SUBSCRIPTION_PERIOD,
    )


def subscription_terms_text() -> str:
    return (
        f"Условия подписки Fitmy2.0\n\n"
        f"• Новому пользователю предоставляется {TRIAL_DAYS} дней бесплатного полного доступа.\n"
        f"• После пробного периода подписка стоит {SUBSCRIPTION_STARS} Telegram Stars за 30 дней.\n"
        "• После первой оплаты подписка автоматически продлевается каждые 30 дней, пока автопродление не отменено.\n"
        "• При отмене уже оплаченный доступ сохраняется до конца оплаченного периода.\n"
        "• Fitmy2.0 — информационный помощник по питанию и тренировкам и не заменяет медицинскую помощь.\n"
        "• По вопросам платежей используй /paysupport."
    )


async def get_profile(user_id: int):
    return await db_fetchrow("SELECT * FROM profiles WHERE telegram_id=$1", user_id)

def profile_to_text(p) -> str:
    if not p:
        return "Профиль ещё не заполнен."
    return f"""
Имя: {p['name']}
Возраст: {p['age']}
Пол: {p['sex']}
Рост: {p['height']}
Вес: {p['weight']}
Цель: {p['goal']}
Активность: {p['activity']}
Тренировок в неделю: {p['frequency']}
Где тренируется / оборудование: {p['equipment']}
Ограничения и травмы: {p['restrictions']}
Питание и предпочтения: {p['food']}
Сон: {p['sleep']}
""".strip()



async def user_local_date(user_id: int):
    settings = await ensure_notification_settings(user_id)
    tz_name = settings["timezone"] if settings else DEFAULT_TIMEZONE
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo(DEFAULT_TIMEZONE)
    return now_utc().astimezone(tz).date()



def app_week_start(local_date):
    return local_date - timedelta(days=local_date.weekday())


def valid_app_week_plan(plan) -> bool:
    if not isinstance(plan, list) or len(plan) != 7:
        return False
    for day in plan:
        if not isinstance(day, list) or len(day) != 4:
            return False
        for idx, meal_id in enumerate(day):
            meal = APP_MEAL_CATALOG.get(str(meal_id))
            if not meal or meal["type"] != APP_MEAL_TYPE_ORDER[idx]:
                return False
        # В один день нельзя показывать одно и то же блюдо или фактически одинаковое блюдо.
        ids = [str(x) for x in day]
        names = [APP_MEAL_CATALOG[x]["name"].strip().lower() for x in ids]
        if len(set(ids)) != 4 or len(set(names)) != 4:
            return False
    # Внутри недели каждый завтрак/обед/перекус/ужин уникален.
    for idx in range(4):
        ids = [str(day[idx]) for day in plan]
        names = [APP_MEAL_CATALOG[x]["name"].strip().lower() for x in ids]
        if len(set(ids)) != 7 or len(set(names)) != 7:
            return False
    return True


def decode_app_plan(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return None
    return value


def app_goal_mode(profile) -> str:
    goal = str(profile["goal"] if profile else "").lower()
    if any(x in goal for x in ("набор", "мыш", "мас")):
        return "gain"
    if any(x in goal for x in ("сниж", "похуд", "сброс", "дефиц")):
        return "loss"
    return "maintain"


def fallback_app_week_plan(user_id: int, start_date, salt: str = "", goal_mode: str = "maintain") -> list[list[str]]:
    pools = {
        meal_type: [
            meal_id for meal_id, item in APP_MEAL_CATALOG.items()
            if meal_id in APP_CURATED_MEAL_IDS and item["type"] == meal_type and item["cook"] <= 25 and goal_mode in item.get("goals", ["loss","maintain","gain"])
        ]
        for meal_type in APP_MEAL_TYPE_ORDER
    }
    seed_text = f"{user_id}:{start_date.isoformat()}:{salt}"
    seed = int(hashlib.sha256(seed_text.encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    ordered = {}
    for meal_type, choices in pools.items():
        choices = list(choices)
        # Приоритет блюдам с большей долей белка, но сохраняем вариативность недели.
        choices.sort(key=lambda mid: APP_MEAL_CATALOG[mid]["protein"] / max(APP_MEAL_CATALOG[mid]["kcal"], 1), reverse=True)
        top = choices[:max(10, min(len(choices), 16))]
        rng.shuffle(top)
        high = [mid for mid in top if APP_MEAL_CATALOG[mid].get("high_protein")]
        rest = [mid for mid in top if mid not in high]
        ordered[meal_type] = (high[:3] + rest)[:7]
    plan = [
        [ordered[meal_type][day_index] for meal_type in APP_MEAL_TYPE_ORDER]
        for day_index in range(7)
    ]
    # Если названия случайно пересеклись между категориями в одном дне, переставляем
    # блюда внутри соответствующей категории, пока каждый день не станет уникальным.
    for meal_idx in range(1, 4):
        for day_idx in range(7):
            used = {APP_MEAL_CATALOG[plan[day_idx][j]]["name"].strip().lower() for j in range(meal_idx)}
            if APP_MEAL_CATALOG[plan[day_idx][meal_idx]]["name"].strip().lower() in used:
                for swap_idx in range(day_idx + 1, 7):
                    candidate = plan[swap_idx][meal_idx]
                    if APP_MEAL_CATALOG[candidate]["name"].strip().lower() not in used:
                        plan[day_idx][meal_idx], plan[swap_idx][meal_idx] = plan[swap_idx][meal_idx], plan[day_idx][meal_idx]
                        break
    return plan


def parse_ai_app_plan(answer: str):
    if not answer:
        return None
    candidates = [answer.strip()]
    start = answer.find("{")
    end = answer.rfind("}")
    if start >= 0 and end > start:
        candidates.append(answer[start:end + 1])
    start = answer.find("[")
    end = answer.rfind("]")
    if start >= 0 and end > start:
        candidates.append(answer[start:end + 1])
    for raw in candidates:
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, dict):
            data = data.get("days") or data.get("plan")
        if valid_app_week_plan(data):
            return data
    return None


async def generate_ai_app_week_plan(user_id: int, start_date, previous_plan=None):
    if not client:
        return None
    profile = await get_profile(user_id)
    goal_mode = app_goal_mode(profile)
    choices = "\n".join(
        f"{meal_id} | {item['type']} | {item['name']} | {item['kcal']} ккал | Б {item['protein']} Ж {item['fat']} У {item['carbs']} | {item['cook']} мин | бюджетное"
        for meal_id, item in APP_MEAL_CATALOG.items()
        if meal_id in APP_CURATED_MEAL_IDS and item["cook"] <= 25 and goal_mode in item.get("goals", ["loss","maintain","gain"]) and item.get("budget", True)
    )
    previous = json.dumps(previous_plan, ensure_ascii=False) if previous_plan else "нет"
    answer = await ask_ai(
        user_id,
        f"Подбери рацион Fitmy2.0 на неделю с {start_date.strftime('%d.%m.%Y')}.",
        f"""
Выбери рацион на 7 дней ТОЛЬКО из библиотеки ниже.
Учитывай профиль пользователя, его цель, пищевые предпочтения и ограничения.
Целевой режим: {goal_mode}. Все блюда должны быть доступными и бюджетными: обычные крупы, яйца, творог, курица, индейка, печень, минтай/скумбрия, бобовые, сезонные овощи и фрукты. Не используй дорогие продукты вроде лосося, креветок, киноа, авокадо и чиа.
Белок — один из главных приоритетов: каждый основной приём пищи должен содержать полноценный источник белка (курица, индейка, яйца, творог, недорогая рыба или бобовые), а перекусы чаще делай творожными/яичными/йогуртовыми. При близких вариантах выбирай блюдо с большим количеством белка.
Основные приёмы пищи собирай сбалансированно: белок + овощи + крупа/другой сложный углевод там, где это уместно по БЖУ и цели пользователя. Используй обычные овощи: огурцы, томаты, капусту, морковь, перец, брокколи, кабачок, зелень; крупы: гречка, овсянка, рис, перловка, пшено.
Рецепты должны быть максимально быстрыми и вкусными: преимущественно 5–25 минут, минимум сложных действий и посуды. Предпочитай омлеты, боулы, салаты, сковороду/духовку, заранее сваренные крупы.
Для loss выбирай более лёгкие и сытные варианты; для gain — более калорийные варианты с достаточным белком и углеводами; для maintain — средний диапазон.
Если профиль явно исключает продукт, не выбирай блюдо с этим продуктом.
КРИТИЧНО: в пределах ОДНОГО ДНЯ все 4 блюда должны быть разными — нельзя повторять одинаковое блюдо или одно и то же название на завтрак, обед, перекус и ужин.
Также все 7 завтраков должны быть разными, все 7 обедов разными, все 7 перекусов разными и все 7 ужинов разными. Не ставь одно и то же блюдо несколько раз за неделю.
По возможности не копируй прошлую неделю целиком.

БИБЛИОТЕКА:
{choices}

ПРОШЛАЯ НЕДЕЛЯ:
{previous}

Ответь ТОЛЬКО валидным JSON без пояснений:
{{"days":[
["id_завтрака","id_обеда","id_перекуса","id_ужина"],
["...","...","...","..."],
["...","...","...","..."],
["...","...","...","..."],
["...","...","...","..."],
["...","...","...","..."],
["...","...","...","..."]
]}}

В каждом дне порядок строго: Завтрак, Обед, Перекус, Ужин.
Используй только ID из библиотеки.
""",
        save_history=False,
    )
    return parse_ai_app_plan(answer)


async def get_app_week_plan(user_id: int, local_date=None):
    local_date = local_date or await user_local_date(user_id)
    start_date = app_week_start(local_date)
    return await db_fetchrow(
        """
        SELECT * FROM app_week_plans
        WHERE telegram_id=$1 AND start_date=$2
        LIMIT 1
        """,
        user_id, start_date
    )


async def _upgrade_app_week_plan_with_ai(user_id: int, start_date, fallback_plan, previous_plan=None):
    try:
        ai_plan = await generate_ai_app_week_plan(user_id, start_date, previous_plan)
        final_plan = ai_plan if valid_app_week_plan(ai_plan) else fallback_plan
        source = "v22-unified-ai" if ai_plan else "v22-unified-fallback"
        await db_execute(
            """
            UPDATE app_week_plans
            SET plan_json=$3::jsonb, source=$4, updated_at=$5
            WHERE telegram_id=$1 AND start_date=$2
            """,
            user_id, start_date, json.dumps(final_plan), source, now_utc()
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Weekly app plan AI generation failed for %s", user_id)
        await db_execute(
            """
            UPDATE app_week_plans
            SET source='fallback', updated_at=$3
            WHERE telegram_id=$1 AND start_date=$2
            """,
            user_id, start_date, now_utc()
        )


async def ensure_app_week_plan(user_id: int, local_date=None, wait_for_ai: bool = False):
    local_date = local_date or await user_local_date(user_id)
    start_date = app_week_start(local_date)
    end_date = start_date + timedelta(days=6)

    existing = await db_fetchrow(
        "SELECT * FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
        user_id, start_date
    )
    if existing:
        existing_plan = decode_app_plan(existing["plan_json"])
        if valid_app_week_plan(existing_plan) and str(existing["source"] or "").startswith("v22-unified"):
            return existing
        if valid_app_week_plan(existing_plan):
            profile = await get_profile(user_id)
            fresh_plan = fallback_app_week_plan(user_id, start_date, salt="v22-unified", goal_mode=app_goal_mode(profile))
            await db_execute(
                """UPDATE app_week_plans SET plan_json=$3::jsonb, source='v22-unified', updated_at=$4
                   WHERE telegram_id=$1 AND start_date=$2""",
                user_id, start_date, json.dumps(fresh_plan), now_utc(),
            )
            return await db_fetchrow("SELECT * FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2", user_id, start_date)
        # Миграция старого плана v7: сразу заменяем его на новую библиотеку из 28 уникальных блюд.
        profile = await get_profile(user_id)
        fallback_plan = fallback_app_week_plan(user_id, start_date, salt="v22-unified", goal_mode=app_goal_mode(profile))
        await db_execute(
            """UPDATE app_week_plans
            SET plan_json=$3::jsonb, source='v22-unified', updated_at=$4
            WHERE telegram_id=$1 AND start_date=$2""",
            user_id, start_date, json.dumps(fallback_plan), now_utc(),
        )
        task = asyncio.create_task(_upgrade_app_week_plan_with_ai(user_id, start_date, fallback_plan, existing_plan))
        _update_tasks.add(task)
        task.add_done_callback(_update_tasks.discard)
        return await db_fetchrow(
            "SELECT * FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
            user_id, start_date
        )

    previous_row = await db_fetchrow(
        """
        SELECT plan_json FROM app_week_plans
        WHERE telegram_id=$1 AND start_date < $2
        ORDER BY start_date DESC
        LIMIT 1
        """,
        user_id, start_date
    )
    previous_plan = decode_app_plan(previous_row["plan_json"]) if previous_row else None
    profile = await get_profile(user_id)
    fallback_plan = fallback_app_week_plan(user_id, start_date, salt="v22-unified", goal_mode=app_goal_mode(profile))

    inserted = await db_fetchrow(
        """
        INSERT INTO app_week_plans
            (telegram_id, start_date, end_date, plan_json, source, created_at, updated_at)
        VALUES ($1,$2,$3,$4::jsonb,'pending',$5,$5)
        ON CONFLICT(telegram_id, start_date) DO NOTHING
        RETURNING *
        """,
        user_id, start_date, end_date, json.dumps(fallback_plan), now_utc()
    )
    if not inserted:
        return await db_fetchrow(
            "SELECT * FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
            user_id, start_date
        )

    if wait_for_ai:
        await _upgrade_app_week_plan_with_ai(user_id, start_date, fallback_plan, previous_plan)
        return await db_fetchrow(
            "SELECT * FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
            user_id, start_date
        )

    task = asyncio.create_task(
        _upgrade_app_week_plan_with_ai(user_id, start_date, fallback_plan, previous_plan)
    )
    _update_tasks.add(task)
    task.add_done_callback(_update_tasks.discard)
    return inserted


async def regenerate_app_week_plan(user_id: int, local_date=None):
    local_date = local_date or await user_local_date(user_id)
    start_date = app_week_start(local_date)
    end_date = start_date + timedelta(days=6)
    current = await db_fetchrow(
        "SELECT plan_json FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
        user_id, start_date
    )
    previous_plan = decode_app_plan(current["plan_json"]) if current else None
    ai_plan = await generate_ai_app_week_plan(user_id, start_date, previous_plan)
    plan = ai_plan if valid_app_week_plan(ai_plan) else fallback_app_week_plan(
        user_id, start_date, salt=str(time.time_ns())
    )
    source = "v22-unified-manual-ai" if ai_plan else "v22-unified-manual-fallback"
    await db_execute(
        """
        INSERT INTO app_week_plans
            (telegram_id, start_date, end_date, plan_json, source, created_at, updated_at)
        VALUES ($1,$2,$3,$4::jsonb,$5,$6,$6)
        ON CONFLICT(telegram_id, start_date) DO UPDATE SET
            end_date=EXCLUDED.end_date,
            plan_json=EXCLUDED.plan_json,
            source=EXCLUDED.source,
            updated_at=EXCLUDED.updated_at
        """,
        user_id, start_date, end_date, json.dumps(plan), source, now_utc()
    )
    return await get_app_week_plan(user_id, local_date)



async def choose_ai_replacement(user_id: int, old_id: str, candidate_ids: list[str], reason: str):
    if not client or not candidate_ids:
        return None
    old = APP_MEAL_CATALOG[old_id]
    choices = "\n".join(
        f"{mid} | {APP_MEAL_CATALOG[mid]['name']} | {APP_MEAL_CATALOG[mid]['kcal']} ккал | {APP_MEAL_CATALOG[mid]['cook']} мин"
        for mid in candidate_ids
    )
    answer = await ask_ai(
        user_id,
        f"Замени блюдо {old['name']}. Причина: {reason}.",
        f"""
Выбери ОДНО подходящее блюдо на замену из списка ниже.
Учитывай профиль пользователя, цель, пищевые предпочтения и ограничения.
Причина замены: {reason}
Текущее блюдо: {old['name']}.

Варианты:
{choices}

Старайся сохранить близкую калорийность и тип приёма пищи.
Выбирай только обычные повседневные продукты из супермаркета. Не предлагай лосось, форель, креветки, морепродукты, киноа, авокадо, чиа и другие дорогие или экзотические продукты.
Ответь только одним ID из списка, без пояснений.
""",
        save_history=False,
    )
    candidate = answer.strip().split()[0].strip("`'\".,;:")
    return candidate if candidate in candidate_ids else None


async def replace_app_meal(user_id: int, day_index: int, meal_index: int, reason: str, local_date=None):
    row = await ensure_app_week_plan(user_id, local_date)
    plan = decode_app_plan(row["plan_json"])
    if not valid_app_week_plan(plan):
        profile = await get_profile(user_id)
        plan = fallback_app_week_plan(user_id, row["start_date"], salt="v22-unified", goal_mode=app_goal_mode(profile))

    old_id = plan[day_index][meal_index]
    old = APP_MEAL_CATALOG[old_id]
    used_same_type = {str(day[meal_index]) for day in plan if isinstance(day, list) and len(day) > meal_index}
    candidates = [
        meal_id for meal_id, item in APP_MEAL_CATALOG.items()
        if meal_id in APP_CURATED_MEAL_IDS and item["type"] == old["type"] and item.get("budget", True) and item["cook"] <= 25 and meal_id != old_id and meal_id not in used_same_type
    ]
    if not candidates:
        candidates = [
            meal_id for meal_id, item in APP_MEAL_CATALOG.items()
            if meal_id in APP_CURATED_MEAL_IDS and item["type"] == old["type"] and item.get("budget", True) and item["cook"] <= 25 and meal_id != old_id
        ]
    if not candidates:
        return row

    if reason == "fast":
        new_id = min(candidates, key=lambda mid: APP_MEAL_CATALOG[mid]["cook"])
    else:
        new_id = await choose_ai_replacement(user_id, old_id, candidates, reason)
        if not new_id:
            seed_text = f"{user_id}:{row['start_date']}:{day_index}:{meal_index}:{reason}:{old_id}"
            idx = int(hashlib.sha256(seed_text.encode()).hexdigest()[:12], 16) % len(candidates)
            new_id = candidates[idx]

    plan[day_index][meal_index] = new_id
    await db_execute(
        """
        UPDATE app_week_plans
        SET plan_json=$3::jsonb, source='v22-unified-edited', updated_at=$4
        WHERE telegram_id=$1 AND start_date=$2
        """,
        user_id, row["start_date"], json.dumps(plan), now_utc()
    )
    return await db_fetchrow(
        "SELECT * FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
        user_id, row["start_date"]
    )


def app_plan_day_text(row, local_date) -> str | None:
    if not row:
        return None
    plan = decode_app_plan(row["plan_json"])
    if not valid_app_week_plan(plan):
        return None
    day_index = (local_date - row["start_date"]).days
    if day_index < 0 or day_index > 6:
        return None
    lines = []
    for meal_id in plan[day_index]:
        item = APP_MEAL_CATALOG[meal_id]
        lines.append(f"{item['type']}: {item['name']} — около {item['kcal']} ккал")
    return "\n".join(lines)

async def save_weekly_meal_plan(user_id: int, start_date, meal_plan: str, shopping_list: str):
    end_date = start_date + timedelta(days=6)
    await db_execute(
        """
        INSERT INTO weekly_meal_plans(telegram_id, start_date, end_date, meal_plan, shopping_list, created_at)
        VALUES ($1,$2,$3,$4,$5,$6)
        ON CONFLICT(telegram_id, start_date) DO UPDATE SET
            end_date=EXCLUDED.end_date,
            meal_plan=EXCLUDED.meal_plan,
            shopping_list=EXCLUDED.shopping_list,
            created_at=EXCLUDED.created_at
        """,
        user_id, start_date, end_date, meal_plan, shopping_list, now_utc()
    )


async def get_active_weekly_meal_plan(user_id: int, local_date=None):
    local_date = local_date or await user_local_date(user_id)
    return await db_fetchrow(
        """
        SELECT * FROM weekly_meal_plans
        WHERE telegram_id=$1 AND start_date <= $2 AND end_date >= $2
        ORDER BY start_date DESC
        LIMIT 1
        """,
        user_id, local_date
    )


def extract_day_from_weekly_plan(meal_plan: str, day_number: int) -> str | None:
    if not meal_plan or not (1 <= day_number <= 7):
        return None
    start_marker = f"===DAY_{day_number}==="
    next_marker = f"===DAY_{day_number + 1}===" if day_number < 7 else None
    if start_marker in meal_plan:
        chunk = meal_plan.split(start_marker, 1)[1]
        if next_marker and next_marker in chunk:
            chunk = chunk.split(next_marker, 1)[0]
        return clean_telegram_text(chunk.strip())
    # запасной вариант, если модель не соблюла служебные маркеры
    pattern = rf"(?is)(День\s*{day_number}\b.*?)(?=\n\s*День\s*{day_number + 1}\b|$)" if day_number < 7 else rf"(?is)(День\s*{day_number}\b.*)$"
    m = re.search(pattern, meal_plan)
    return clean_telegram_text(m.group(1).strip()) if m else None


def split_telegram_chunks(text: str, limit: int = 3600) -> list[str]:
    text = text.strip()
    if len(text) <= limit:
        return [text]
    chunks = []
    current = ""
    for block in text.split("\n\n"):
        candidate = block if not current else current + "\n\n" + block
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        while len(block) > limit:
            cut = block.rfind("\n", 0, limit)
            if cut < limit // 2:
                cut = limit
            chunks.append(block[:cut].strip())
            block = block[cut:].strip()
        current = block
    if current:
        chunks.append(current)
    return [c for c in chunks if c]


async def send_long_message(message: Message, text: str):
    for chunk in split_telegram_chunks(text):
        await message.answer(chunk)
        await asyncio.sleep(0.15)


def parse_weekly_bundle(answer: str) -> tuple[str, str]:
    marker = "===FITMYN_SHOPPING==="
    if marker in answer:
        meal_plan, shopping = answer.split(marker, 1)
        return meal_plan.strip(), shopping.strip()
    # запасной поиск по заголовку списка покупок
    m = re.search(r"(?im)^🛒\s*Список покупок.*$", answer)
    if m:
        return answer[:m.start()].strip(), answer[m.start():].strip()
    return answer.strip(), "🛒 Список покупок\n\nНе удалось отделить список покупок. Нажми «🗓 Рацион на неделю» ещё раз."


async def generate_weekly_meal_bundle(user_id: int, start_date) -> tuple[str, str]:
    end_date = start_date + timedelta(days=6)
    answer = await ask_ai(
        user_id,
        f"Составь мой рацион на 7 дней с {start_date.strftime('%d.%m')} по {end_date.strftime('%d.%m')} и список покупок к нему.",
        f"""
Составь персональный рацион на 7 дней с учетом профиля, цели, предпочтений и ограничений пользователя.
Период: {start_date.strftime('%d.%m.%Y')}–{end_date.strftime('%d.%m.%Y')}.

Важно:
• План должен быть реалистичным для обычной жизни и не требовать готовить 4 разных сложных блюда каждый день.
• Повторно используй часть продуктов и заготовок, чтобы уменьшить расходы и отходы.
• На каждый день: завтрак, обед, ужин, 1 перекус.
• Для каждого приема пищи укажи конкретное блюдо и ориентир порции обычными мерами или примерным весом, без ложной точности.
• Если продукт не подходит по анкете, не используй его.
• Не добавляй сладости и мучное, если пользователь указал, что их исключает.
• Для сложного блюда дай очень короткое пояснение состава, но не полноценный рецепт.
• Сохраняй разнообразие, но используй разумное число ингредиентов.

Строго используй служебные маркеры — каждый на отдельной строке:
===DAY_1===
📅 День 1 — {start_date.strftime('%d.%m')}
Завтрак
• ...
Обед
• ...
Ужин
• ...
Перекус
• ...

===DAY_2===
...
И так до ===DAY_7===.

После 7-го дня поставь отдельной строкой:
===FITMYN_SHOPPING===

Затем:
🛒 Список покупок на 7 дней

🥩 Белок
• продукт — примерное количество

🥚 Яйца и молочные продукты
• ...

🌾 Крупы и гарниры
• ...

🥦 Овощи и зелень
• ...

🍎 Фрукты и ягоды
• ...

🥜 Орехи, масла и прочее
• ...

Проверь перед ответом:
1. Каждый продукт из списка покупок реально используется в рационе.
2. В списке есть примерное суммарное количество на 1 человека на 7 дней.
3. Нет таблиц, Markdown, HTML и <br>.
4. Не добавляй вступление и заключение.
""",
        save_history=False,
    )
    return parse_weekly_bundle(answer)


def workout_days_from_frequency(value: str | None) -> str:
    """Подбирает равномерные тренировочные дни из ответа анкеты."""
    match = re.search(r"\d+", value or "")
    n = int(match.group()) if match else 3
    if n <= 1:
        days = [2]  # Ср
    elif n == 2:
        days = [1, 4]  # Вт, Пт
    elif n == 3:
        days = [0, 2, 4]  # Пн, Ср, Пт
    elif n == 4:
        days = [0, 1, 3, 5]  # Пн, Вт, Чт, Сб
    elif n == 5:
        days = [0, 1, 2, 4, 5]  # Пн, Вт, Ср, Пт, Сб
    elif n == 6:
        days = [0, 1, 2, 3, 4, 5]
    else:
        days = [0, 1, 2, 3, 4, 5, 6]
    return ",".join(str(x) for x in days)


def workout_days_label(value: str) -> str:
    labels = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    result = []
    for item in (value or "").split(","):
        item = item.strip()
        if item.isdigit() and 0 <= int(item) <= 6:
            result.append(labels[int(item)])
    return ", ".join(result) or "не выбраны"


def timezone_label(value: str) -> str:
    names = {
        "Europe/Moscow": "Москва",
        "Europe/London": "Лондон",
        "Asia/Dubai": "Дубай",
        "Asia/Novosibirsk": "Новосибирск",
        "Asia/Almaty": "Алматы",
        "Asia/Tbilisi": "Тбилиси",
    }
    return names.get(value, value)


async def ensure_notification_settings(user_id: int):
    row = await db_fetchrow(
        "SELECT * FROM notification_settings WHERE telegram_id=$1", user_id
    )
    if row:
        return row
    profile = await get_profile(user_id)
    days = workout_days_from_frequency(profile["frequency"] if profile else None)
    await db_execute(
        """
        INSERT INTO notification_settings(
            telegram_id, enabled, timezone, morning_time, evening_time,
            workout_days, updated_at
        ) VALUES ($1, TRUE, $2, $3, $4, $5, $6)
        ON CONFLICT(telegram_id) DO NOTHING
        """,
        user_id, DEFAULT_TIMEZONE, DEFAULT_MORNING_TIME, DEFAULT_EVENING_TIME,
        days, now_utc()
    )
    return await db_fetchrow(
        "SELECT * FROM notification_settings WHERE telegram_id=$1", user_id
    )


def schedule_keyboard(settings) -> InlineKeyboardMarkup:
    toggle_text = "🔕 Выключить авто" if settings["enabled"] else "🔔 Включить авто"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data="notify_toggle")],
        [
            InlineKeyboardButton(text="Утро 07:00", callback_data="notify_m_0700"),
            InlineKeyboardButton(text="08:00", callback_data="notify_m_0800"),
            InlineKeyboardButton(text="09:00", callback_data="notify_m_0900"),
            InlineKeyboardButton(text="10:00", callback_data="notify_m_1000"),
        ],
        [
            InlineKeyboardButton(text="Вечер 19:00", callback_data="notify_e_1900"),
            InlineKeyboardButton(text="20:00", callback_data="notify_e_2000"),
            InlineKeyboardButton(text="21:00", callback_data="notify_e_2100"),
            InlineKeyboardButton(text="22:00", callback_data="notify_e_2200"),
        ],
        [
            InlineKeyboardButton(text="Москва", callback_data="notify_tz_moscow"),
            InlineKeyboardButton(text="Лондон", callback_data="notify_tz_london"),
        ],
        [
            InlineKeyboardButton(text="Дубай", callback_data="notify_tz_dubai"),
            InlineKeyboardButton(text="Новосибирск", callback_data="notify_tz_nsk"),
        ],
        [InlineKeyboardButton(text="♻️ Дни тренировок по анкете", callback_data="notify_days_auto")],
    ])


def schedule_text(settings) -> str:
    status = "включены" if settings["enabled"] else "выключены"
    return (
        "⏰ Автоматическое сопровождение\n\n"
        f"Статус: {status}\n"
        f"Часовой пояс: {timezone_label(settings['timezone'])}\n"
        f"Утренний план: {settings['morning_time']}\n"
        f"Вечерний отчёт: {settings['evening_time']}\n"
        f"Тренировочные дни: {workout_days_label(settings['workout_days'])}\n\n"
        "Утром я сам пришлю питание и тренировку или восстановление. "
        "Вечером напомню про короткий отчёт."
    )


def parse_hhmm(value: str) -> tuple[int, int]:
    try:
        h, m = value.split(":", 1)
        return int(h), int(m)
    except Exception:
        return 8, 0


def is_due(local_now: datetime, hhmm: str, window_minutes: int = 90) -> bool:
    hour, minute = parse_hhmm(hhmm)
    scheduled = local_now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return scheduled <= local_now < scheduled + timedelta(minutes=window_minutes)


async def claim_notification(user_id: int, kind: str, local_date):
    return await db_fetchrow(
        """
        INSERT INTO notification_log(telegram_id, kind, local_date, created_at)
        VALUES ($1,$2,$3,$4)
        ON CONFLICT(telegram_id, kind, local_date) DO NOTHING
        RETURNING id
        """,
        user_id, kind, local_date, now_utc()
    )


async def release_notification(log_id: int):
    await db_execute("DELETE FROM notification_log WHERE id=$1", log_id)


async def build_daily_auto_plan(user_id: int, local_date, workout_day: bool) -> tuple[str, str]:
    task = "Сегодня тренировочный день." if workout_day else "Сегодня день восстановления без силовой тренировки."

    # Текущий недельный рацион Mini App создаётся автоматически раз в неделю.
    # В понедельник (или при первом открытии приложения) формируется новый план,
    # сохраняется в БД и затем используется без повторных AI-запросов.
    app_plan = await ensure_app_week_plan(user_id, local_date, wait_for_ai=True)
    planned_food = app_plan_day_text(app_plan, local_date)

    # Совместимость со старым текстовым недельным рационом.
    if not planned_food:
        active_plan = await get_active_weekly_meal_plan(user_id, local_date)
        if active_plan:
            day_number = (local_date - active_plan["start_date"]).days + 1
            planned_food = extract_day_from_weekly_plan(active_plan["meal_plan"], day_number)

    if planned_food:
        activity = await ask_ai(
            user_id,
            f"Составь активность на сегодня. {task}",
            f"""
{task}
Сформируй только второе сообщение:
{'🏋️ Тренировка на сегодня: Цель, Разминка, Основная часть, Отдых, Заминка, Совет.' if workout_day else '🌿 Восстановление сегодня: активность, мобильность, шаги, сон и один совет.'}
Без Markdown, HTML, таблиц и <br>. Компактно.
""",
            save_history=False,
        )
        food = "🥗 Питание на сегодня\n\n" + planned_food
        return food, activity

    answer = await ask_ai(
        user_id,
        f"Составь автоматический план на сегодня. {task}",
        f"""
Сформируй два коротких сообщения для Telegram на сегодня с учетом профиля пользователя.
{task}

Сначала питание, потом тренировку или восстановление.
Между сообщениями поставь отдельной строкой ТОЧНО такой маркер:
===FITMYN_SPLIT===

Первая часть:
🥗 Питание на сегодня
Главная задача
Завтрак
Обед
Ужин
Перекус
Фокус дня

Вторая часть:
{'🏋️ Тренировка на сегодня: Цель, Разминка, Основная часть, Отдых, Заминка, Совет.' if workout_day else '🌿 Восстановление сегодня: активность, мобильность, шаги, сон и один совет.'}

Каждая часть должна быть компактной. Без Markdown, HTML, таблиц и <br>.
""",
        save_history=False,
    )
    parts = [p.strip() for p in answer.split("===FITMYN_SPLIT===", 1)]
    if len(parts) == 2:
        return parts[0], parts[1]
    return answer, (
        "🏋️ Тренировка сегодня\n\nОткрой кнопку «🏋️ Тренировка», и я соберу план под тебя."
        if workout_day else
        "🌿 Сегодня восстановление\n\nЛёгкая активность, прогулка и качественный сон — достаточно."
    )


async def send_morning_plan(user_id: int, local_date, workout_day: bool):
    if not bot:
        return False
    claim = await claim_notification(user_id, "morning", local_date)
    if not claim:
        return False
    log_id = claim["id"]
    try:
        food, activity = await build_daily_auto_plan(user_id, local_date, workout_day)
        await bot.send_message(user_id, food, reply_markup=MAIN_KB)
        await asyncio.sleep(0.3)
        await bot.send_message(user_id, activity, reply_markup=MAIN_KB)
        return True
    except Exception:
        logger.exception("Failed to send morning plan to %s", user_id)
        await release_notification(log_id)
        return False


async def send_evening_checkin(user_id: int, local_date):
    if not bot:
        return False
    claim = await claim_notification(user_id, "evening", local_date)
    if not claim:
        return False
    log_id = claim["id"]
    try:
        await bot.send_message(
            user_id,
            "📊 Как прошёл день?\n\n"
            "Нажми «📊 Отчёт» и коротко отметь питание, тренировку или активность, сон, энергию и самочувствие.",
            reply_markup=MAIN_KB,
        )
        return True
    except Exception:
        logger.exception("Failed to send evening checkin to %s", user_id)
        await release_notification(log_id)
        return False


async def run_due_notifications() -> dict:
    if not pool or not bot:
        return {"checked": 0, "morning_sent": 0, "evening_sent": 0}

    users = await db_fetch(
        """
        SELECT u.telegram_id
        FROM users u
        JOIN profiles p ON p.telegram_id=u.telegram_id
        WHERE u.consent=TRUE
        ORDER BY u.telegram_id
        """
    )
    stats = {"checked": len(users), "morning_sent": 0, "evening_sent": 0}
    utc_now = now_utc()

    for row in users:
        uid = row["telegram_id"]
        settings = await ensure_notification_settings(uid)
        if not settings:
            continue
        try:
            tz = ZoneInfo(settings["timezone"])
        except ZoneInfoNotFoundError:
            tz = ZoneInfo(DEFAULT_TIMEZONE)
        local_now = utc_now.astimezone(tz)
        local_date = local_now.date()
        sub = await subscription_info(uid)

        if sub["status"] == "trial" and sub["days_left"] in (3, 1) and local_now.hour == 10:
            log_id = await reserve_notification(uid, f"trial_{sub['days_left']}", local_date)
            if log_id:
                try:
                    await bot.send_message(uid, f"До конца бесплатного периода Fitmy2.0 осталось {sub['days_left']} дн. После этого подписка — {SUBSCRIPTION_STARS} ⭐ на 30 дней. Оформить: /subscribe")
                except Exception:
                    await release_notification(log_id)
        if not sub["has_access"]:
            if local_now.hour == 10:
                log_id = await reserve_notification(uid, "trial_expired", local_date)
                if log_id:
                    try:
                        await bot.send_message(uid, f"Бесплатный период Fitmy2.0 закончился. Полный доступ — {SUBSCRIPTION_STARS} ⭐ на 30 дней. Оформить: /subscribe")
                    except Exception:
                        await release_notification(log_id)
            continue

        # Каждую неделю новый рацион создаётся автоматически.
        # Cron будит сервис каждые 15 минут; в понедельник после 05:00
        # план создаётся один раз и сохраняется в БД, даже если пользователь
        # ещё не открывал Mini App.
        if local_now.weekday() == 0 and local_now.hour >= 5:
            await ensure_app_week_plan(uid, local_date, wait_for_ai=False)

        if not settings["enabled"]:
            continue

        if is_due(local_now, settings["morning_time"]):
            workout_days = {
                int(x) for x in settings["workout_days"].split(",")
                if x.strip().isdigit()
            }
            if await send_morning_plan(uid, local_date, local_now.weekday() in workout_days):
                stats["morning_sent"] += 1

        if is_due(local_now, settings["evening_time"]):
            if await send_evening_checkin(uid, local_date):
                stats["evening_sent"] += 1

    return stats


async def notification_loop():
    """Фоновая подстраховка, пока Render-сервис не спит."""
    while True:
        try:
            await run_due_notifications()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Notification loop error")
        await asyncio.sleep(60)

async def recent_history(user_id: int, limit: int = 12):
    rows = await db_fetch(
        """
        SELECT role, content
        FROM messages
        WHERE telegram_id=$1
        ORDER BY id DESC
        LIMIT $2
        """,
        user_id,
        limit,
    )
    return list(reversed(rows))

async def save_message(user_id: int, role: str, content: str):
    await db_execute(
        "INSERT INTO messages(telegram_id, role, content, created_at) VALUES ($1,$2,$3,$4)",
        user_id, role, content, now_utc()
    )

def clean_telegram_text(text: str) -> str:
    """Убирает типичные артефакты Markdown/HTML из ответов моделей."""
    text = text.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    text = text.replace("**", "").replace("__", "").replace("```", "")
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"^[ \t]*\|[ \t]*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]*\|[ \t]*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"[ \t]*\|[ \t]*", " • ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

async def ask_ai(user_id: int, user_text: str, extra_instruction: str = "", save_history: bool = True) -> str:
    if not client:
        return "ИИ пока не подключён. Администратору нужно добавить OPENAI_API_KEY."

    profile = await get_profile(user_id)
    history = await recent_history(user_id)

    history_text = "\n".join(
        f"{row['role'].upper()}: {row['content']}" for row in history
    )

    instructions = SYSTEM_PROMPT
    if extra_instruction:
        instructions += "\n\nТекущая задача:\n" + extra_instruction

    prompt = f"""
ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ:
{profile_to_text(profile)}

ПОСЛЕДНИЙ КОНТЕКСТ:
{history_text or "Нет истории."}

НОВОЕ СООБЩЕНИЕ:
{user_text}
""".strip()

    response = await client.responses.create(
        model=OPENAI_MODEL,
        instructions=instructions,
        input=prompt,
    )
    answer = clean_telegram_text((response.output_text or "").strip()) or "Не получилось сформировать ответ."
    if save_history:
        await save_message(user_id, "user", user_text)
        await save_message(user_id, "assistant", answer)
    return answer

async def ensure_ready(message: Message) -> bool:
    if not pool:
        await message.answer("База данных пока не подключена. Администратор завершает настройку.")
        return False
    await touch_user(message)
    if not await has_consent(message.from_user.id):
        await message.answer("Сначала нужно согласиться с правилами через /start.")
        return False
    if not await get_profile(message.from_user.id):
        await message.answer("Сначала заполним короткую анкету. Напиши /start.")
        return False
    sub = await subscription_info(message.from_user.id)
    if not sub["has_access"]:
        await message.answer(
            f"Пробный период закончился. Полный доступ к Fitmy2.0 — {SUBSCRIPTION_STARS} ⭐ на 30 дней.\n\n"
            "Для оформления подписки отправь /subscribe."
        )
        return False
    return True

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    if not pool:
        await message.answer("FitMyN почти готов. Администратор завершает подключение базы.")
        return

    await touch_user(message)
    await state.clear()

    if await has_consent(message.from_user.id) and await get_profile(message.from_user.id):
        await message.answer(
            "Я FitMyN — твой ИИ-помощник по питанию, тренировкам и привычкам. Что делаем?",
            reply_markup=MAIN_KB,
        )
        return

    await message.answer(
        "Привет! Я FitMyN — ИИ-помощник по питанию, тренировкам и привычкам.\n\n"
        "Я не заменяю врача и не ставлю диагнозы. Для персонализации я сохраняю только данные, "
        "которые ты сам сообщишь: цель, питание, активность, тренировки и ограничения.\n\n"
        "Продолжить?",
        reply_markup=CONSENT_KB,
    )

@router.callback_query(F.data == "consent_no")
async def consent_no(call: CallbackQuery):
    await call.answer()
    await call.message.answer(
        "Без согласия персональный профиль сохраняться не будет. Если передумаешь — /start."
    )

@router.callback_query(F.data == "consent_yes")
async def consent_yes(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await db_execute("UPDATE users SET consent=TRUE WHERE telegram_id=$1", call.from_user.id)
    await state.set_state(Onboarding.name)
    await call.message.answer("Как тебя зовут?")

@router.message(Onboarding.name)
async def ob_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(Onboarding.age)
    await message.answer("Сколько тебе лет?")

@router.message(Onboarding.age)
async def ob_age(message: Message, state: FSMContext):
    await state.update_data(age=message.text.strip())
    await state.set_state(Onboarding.sex)
    await message.answer("Пол? Можно написать: женский / мужской / не хочу указывать.")

@router.message(Onboarding.sex)
async def ob_sex(message: Message, state: FSMContext):
    await state.update_data(sex=message.text.strip())
    await state.set_state(Onboarding.height)
    await message.answer("Рост в сантиметрах? Можно написать «пропустить».")

@router.message(Onboarding.height)
async def ob_height(message: Message, state: FSMContext):
    await state.update_data(height=message.text.strip())
    await state.set_state(Onboarding.weight)
    await message.answer("Текущий вес? Если не хочешь указывать — «пропустить».")

@router.message(Onboarding.weight)
async def ob_weight(message: Message, state: FSMContext):
    await state.update_data(weight=message.text.strip())
    await state.set_state(Onboarding.goal)
    await message.answer(
        "Какая главная цель? Например: снизить вес, набрать мышцы, стать сильнее, "
        "улучшить форму или повысить уровень энергии."
    )

@router.message(Onboarding.goal)
async def ob_goal(message: Message, state: FSMContext):
    await state.update_data(goal=message.text.strip())
    await state.set_state(Onboarding.activity)
    await message.answer(
        "Опиши обычную активность: сидячая работа, сколько примерно шагов, есть ли спорт сейчас."
    )

@router.message(Onboarding.activity)
async def ob_activity(message: Message, state: FSMContext):
    await state.update_data(activity=message.text.strip())
    await state.set_state(Onboarding.frequency)
    await message.answer("Сколько тренировок в неделю реально готов(а) делать?")

@router.message(Onboarding.frequency)
async def ob_frequency(message: Message, state: FSMContext):
    await state.update_data(frequency=message.text.strip())
    await state.set_state(Onboarding.equipment)
    await message.answer("Где будешь тренироваться и какое оборудование доступно?")

@router.message(Onboarding.equipment)
async def ob_equipment(message: Message, state: FSMContext):
    await state.update_data(equipment=message.text.strip())
    await state.set_state(Onboarding.restrictions)
    await message.answer(
        "Есть ли травмы, боли, ограничения, заболевания или другие особенности, "
        "которые важно учитывать? Если нет — напиши «нет»."
    )

@router.message(Onboarding.restrictions)
async def ob_restrictions(message: Message, state: FSMContext):
    await state.update_data(restrictions=message.text.strip())
    await state.set_state(Onboarding.food)
    await message.answer(
        "Расскажи про питание: что любишь/не ешь, аллергии, готовишь ли дома, "
        "хочешь ли считать калории."
    )

@router.message(Onboarding.food)
async def ob_food(message: Message, state: FSMContext):
    await state.update_data(food=message.text.strip())
    await state.set_state(Onboarding.sleep)
    await message.answer("Сколько обычно спишь и как оцениваешь качество сна?")

@router.message(Onboarding.sleep)
async def ob_sleep(message: Message, state: FSMContext):
    await state.update_data(sleep=message.text.strip())
    data = await state.get_data()
    uid = message.from_user.id

    await db_execute(
        """
        INSERT INTO profiles(
            telegram_id, name, age, sex, height, weight, goal, activity,
            frequency, equipment, restrictions, food, sleep, updated_at
        )
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
        ON CONFLICT(telegram_id) DO UPDATE SET
            name=EXCLUDED.name,
            age=EXCLUDED.age,
            sex=EXCLUDED.sex,
            height=EXCLUDED.height,
            weight=EXCLUDED.weight,
            goal=EXCLUDED.goal,
            activity=EXCLUDED.activity,
            frequency=EXCLUDED.frequency,
            equipment=EXCLUDED.equipment,
            restrictions=EXCLUDED.restrictions,
            food=EXCLUDED.food,
            sleep=EXCLUDED.sleep,
            updated_at=EXCLUDED.updated_at
        """,
        uid, data["name"], data["age"], data["sex"], data["height"], data["weight"],
        data["goal"], data["activity"], data["frequency"], data["equipment"],
        data["restrictions"], data["food"], data["sleep"], now_utc()
    )
    await ensure_subscription(uid)
    local_date = await user_local_date(uid)
    await db_execute(
        "DELETE FROM app_week_plans WHERE telegram_id=$1 AND start_date=$2",
        uid, app_week_start(local_date)
    )
    await state.clear()

    await message.answer("Профиль готов. Собираю стартовый план…", reply_markup=MAIN_KB)
    answer = await ask_ai(
        uid,
        "Составь мой стартовый план.",
        """
Сделай стартовый план на 7 дней.
Оформи короткими блоками с эмодзи и маркированными списками.
Без таблиц, Markdown, HTML и <br>.

Нужные блоки:
🎯 Цель недели
🥗 Питание — 4–6 простых правил
🍽 Пример одного дня
🏋️ Тренировки на неделю
⚡ Минимум на занятый день
📊 Что отслеживать ежедневно

Не давай медицинских обещаний.
""",
    )
    await message.answer(answer)

@router.message(F.text == "🥗 Питание")
async def food_menu(message: Message):
    if not await ensure_ready(message):
        return
    answer = await ask_ai(
        message.from_user.id,
        "Составь мне план питания на сегодня.",
        """
Составь практичный план питания на сегодня с учётом профиля пользователя.

Формат:
🥗 Питание на сегодня

Главная задача
1–2 коротких предложения.

Завтрак
• вариант блюда
• при необходимости замена

Обед
• вариант блюда
• при необходимости замена

Ужин
• вариант блюда

Перекус
• 1–2 варианта

Фокус дня
Одна простая задача.

Без таблиц, Markdown, HTML и <br>. Пиши компактно.
"""
    )
    await message.answer(answer)

@router.message(F.text == "🏋️ Тренировка")
async def workout_menu(message: Message):
    if not await ensure_ready(message):
        return
    answer = await ask_ai(
        message.from_user.id,
        "Какую тренировку мне сделать сегодня?",
        """
Подбери тренировку под профиль пользователя и доступное оборудование.

Формат:
🏋️ Тренировка на сегодня

Цель
Одна короткая строка.

Разминка
• 2–4 пункта

Основная часть
1. Упражнение — подходы × повторения
2. Упражнение — подходы × повторения
3. И так далее, без лишнего текста

Отдых
• сколько между подходами

Заминка
• 2–3 коротких пункта

Совет
Одна рекомендация по технике или нагрузке.

Без таблиц, Markdown, HTML, <br> и вертикальных черт.
Если есть боль или выраженное недомогание, не предлагай нагрузку через боль.
"""
    )
    await message.answer(answer)

@router.message(Command("mealplan"))
@router.message(F.text == "🗓 Рацион на неделю")
async def weekly_meal_plan(message: Message):
    if not await ensure_ready(message):
        return
    await message.answer("🗓 Собираю рацион на 7 дней и список покупок. Обычно это занимает несколько секунд…")
    try:
        start_date = await user_local_date(message.from_user.id)
        meal_plan, shopping = await generate_weekly_meal_bundle(message.from_user.id, start_date)
        await save_weekly_meal_plan(message.from_user.id, start_date, meal_plan, shopping)

        # Служебные маркеры нужны для связи с ежедневным планом, пользователю их не показываем.
        visible_plan = re.sub(r"(?m)^===DAY_[1-7]===\s*$", "", meal_plan).strip()
        visible_shopping = shopping.replace("===FITMYN_SHOPPING===", "").strip()

        await send_long_message(message, visible_plan)
        await message.answer("🛒 К этому рациону готов список покупок:")
        await send_long_message(message, visible_shopping)
        await message.answer(
            "Готово. До конца этих 7 дней утреннее питание будет опираться на этот рацион, чтобы меню и покупки не расходились.",
            reply_markup=MAIN_KB,
        )
    except Exception:
        logger.exception("Weekly meal plan error")
        await message.answer("Не получилось собрать рацион. Попробуй ещё раз через минуту.", reply_markup=MAIN_KB)


@router.message(Command("shopping"))
@router.message(F.text == "🛒 Список покупок")
async def shopping_list(message: Message):
    if not await ensure_ready(message):
        return
    plan = await get_active_weekly_meal_plan(message.from_user.id)
    if not plan:
        await message.answer(
            "Сначала нажми «🗓 Рацион на неделю». Я составлю меню на 7 дней и сохраню список покупок именно к нему.",
            reply_markup=MAIN_KB,
        )
        return
    await send_long_message(message, plan["shopping_list"])


@router.message(F.text == "📊 Отчёт")
async def report_start(message: Message, state: FSMContext):
    if not await ensure_ready(message): return
    await state.set_state(Checkin.waiting_report)
    await message.answer(
        "Пришли одним сообщением:\n\n"
        "Питание: …\nТренировка: …\nШаги/активность: …\nСон: … часов\n"
        "Энергия: …/10\nГолод: …/10\nСамочувствие: …\nЧто было сложным: …"
    )

@router.message(Checkin.waiting_report)
async def report_finish(message: Message, state: FSMContext):
    report = message.text.strip()
    await db_execute(
        "INSERT INTO checkins(telegram_id, report, created_at) VALUES ($1,$2,$3)",
        message.from_user.id, report, now_utc()
    )
    await state.clear()
    answer = await ask_ai(
        message.from_user.id,
        report,
        """
Это ежедневный отчёт. Ответь:
Итог дня
Что получилось
Что скорректировать — максимум 2 пункта
Одна задача на завтра
Будь кратким.
"""
    )
    await message.answer(answer, reply_markup=MAIN_KB)

@router.message(F.text == "📅 Неделя")
async def week_summary(message: Message):
    if not await ensure_ready(message): return
    since = now_utc() - timedelta(days=7)
    rows = await db_fetch(
        """
        SELECT report, created_at
        FROM checkins
        WHERE telegram_id=$1 AND created_at >= $2
        ORDER BY created_at ASC
        """,
        message.from_user.id, since
    )
    if not rows:
        await message.answer("За последние 7 дней пока нет отчётов. Начни с «📊 Отчёт».")
        return

    reports = "\n\n".join(
        f"{r['created_at'].date()}:\n{r['report']}" for r in rows
    )
    answer = await ask_ai(
        message.from_user.id,
        f"Мои отчёты за неделю:\n\n{reports}",
        """
Сделай недельный разбор:
1. Что получилось.
2. Какие тенденции видны.
3. Что мешает.
4. Что изменить на следующей неделе.
5. План тренировок.
6. Фокус питания.
7. Одна главная задача недели.
Не делай выводов по одному измерению веса.
"""
    )
    await message.answer(answer)

@router.message(F.text == "👤 Мой профиль")
async def my_profile(message: Message):
    if not await ensure_ready(message): return
    await message.answer(profile_to_text(await get_profile(message.from_user.id)))

@router.message(F.text == "💬 Спросить агента")
async def ask_prompt(message: Message):
    if not await ensure_ready(message): return
    await message.answer("Напиши вопрос обычным сообщением. Я учту профиль и последние диалоги.")


@router.message(Command("schedule"))
@router.message(F.text == "⏰ Расписание")
async def notification_schedule(message: Message):
    if not await ensure_ready(message):
        return
    settings = await ensure_notification_settings(message.from_user.id)
    await message.answer(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data == "notify_toggle")
async def notify_toggle(call: CallbackQuery):
    await call.answer()
    settings = await ensure_notification_settings(call.from_user.id)
    await db_execute(
        "UPDATE notification_settings SET enabled=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, not settings["enabled"], now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data.startswith("notify_m_"))
async def notify_morning_time(call: CallbackQuery):
    await call.answer("Время сохранено")
    raw = call.data.rsplit("_", 1)[-1]
    value = f"{raw[:2]}:{raw[2:]}"
    await db_execute(
        "UPDATE notification_settings SET morning_time=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, value, now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data.startswith("notify_e_"))
async def notify_evening_time(call: CallbackQuery):
    await call.answer("Время сохранено")
    raw = call.data.rsplit("_", 1)[-1]
    value = f"{raw[:2]}:{raw[2:]}"
    await db_execute(
        "UPDATE notification_settings SET evening_time=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, value, now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data.startswith("notify_tz_"))
async def notify_timezone(call: CallbackQuery):
    mapping = {
        "notify_tz_moscow": "Europe/Moscow",
        "notify_tz_london": "Europe/London",
        "notify_tz_dubai": "Asia/Dubai",
        "notify_tz_nsk": "Asia/Novosibirsk",
    }
    value = mapping.get(call.data)
    if not value:
        await call.answer("Не удалось выбрать часовой пояс")
        return
    await call.answer("Часовой пояс сохранён")
    await ensure_notification_settings(call.from_user.id)
    await db_execute(
        "UPDATE notification_settings SET timezone=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, value, now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.callback_query(F.data == "notify_days_auto")
async def notify_days_auto(call: CallbackQuery):
    await call.answer("Дни обновлены")
    await ensure_notification_settings(call.from_user.id)
    profile = await get_profile(call.from_user.id)
    days = workout_days_from_frequency(profile["frequency"] if profile else None)
    await db_execute(
        "UPDATE notification_settings SET workout_days=$2, updated_at=$3 WHERE telegram_id=$1",
        call.from_user.id, days, now_utc()
    )
    settings = await ensure_notification_settings(call.from_user.id)
    await call.message.edit_text(schedule_text(settings), reply_markup=schedule_keyboard(settings))


@router.message(Command("team"))
async def team_stats(message: Message):
    if not pool:
        await message.answer("База данных пока не подключена.")
        return
    await touch_user(message)
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Эта команда доступна только администратору.")
        return

    since = now_utc() - timedelta(days=7)
    total = await db_fetchrow("SELECT COUNT(*) AS c FROM users WHERE consent=TRUE")
    active = await db_fetchrow(
        "SELECT COUNT(DISTINCT telegram_id) AS c FROM checkins WHERE created_at >= $1", since
    )
    checkins = await db_fetchrow(
        "SELECT COUNT(*) AS c FROM checkins WHERE created_at >= $1", since
    )
    await message.answer(
        "Команда за 7 дней\n\n"
        f"Участников с согласием: {total['c']}\n"
        f"Сдали хотя бы 1 отчёт: {active['c']}\n"
        f"Всего дневных отчётов: {checkins['c']}\n\n"
        "Личные медицинские сведения, вес и ограничения здесь не показываются."
    )

@router.message(Command("reset_profile"))
async def reset_profile(message: Message, state: FSMContext):
    if not pool: return
    await touch_user(message)
    if not await has_consent(message.from_user.id):
        await message.answer("Сначала /start.")
        return
    await db_execute("DELETE FROM app_week_plans WHERE telegram_id=$1", message.from_user.id)
    await db_execute("DELETE FROM profiles WHERE telegram_id=$1", message.from_user.id)
    await state.clear()
    await message.answer("Профиль сброшен. Напиши /start, чтобы заполнить его заново.")

@router.message(Command("delete_me"))
async def delete_me(message: Message, state: FSMContext):
    if not pool: return
    uid = message.from_user.id
    await db_execute("DELETE FROM notification_log WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM notification_settings WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM weekly_meal_plans WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM app_week_plans WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM app_payments WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM app_subscriptions WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM checkins WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM messages WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM profiles WHERE telegram_id=$1", uid)
    await db_execute("DELETE FROM users WHERE telegram_id=$1", uid)
    await state.clear()
    await message.answer("Твои данные FitMyN удалены. Чтобы начать заново — /start.")

@router.message(Command("terms"))
async def subscription_terms(message: Message):
    await message.answer(subscription_terms_text())


@router.message(Command("subscribe"))
async def subscribe_command(message: Message):
    if not pool or not bot:
        await message.answer("Оплата временно недоступна. Попробуй чуть позже.")
        return
    await touch_user(message)
    if not await get_profile(message.from_user.id):
        await message.answer("Сначала заполни анкету через /start — после неё начнутся 14 бесплатных дней.")
        return
    sub = await subscription_info(message.from_user.id)
    if sub["status"] == "active":
        until = sub["subscription_until"][:10] if sub["subscription_until"] else ""
        await message.answer(f"Подписка уже активна до {until}.")
        return
    link = await create_subscription_invoice_link(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"Принимаю условия · оплатить {SUBSCRIPTION_STARS} ⭐", url=link)],
    ])
    await message.answer(subscription_terms_text(), reply_markup=kb)


@router.message(Command("cancel_subscription"))
async def cancel_subscription_command(message: Message):
    if not pool or not bot:
        return
    row = await ensure_subscription(message.from_user.id)
    charge_id = row["telegram_payment_charge_id"]
    if not charge_id or not row["subscription_until"] or row["subscription_until"] <= now_utc():
        await message.answer("Активной платной подписки с автопродлением сейчас нет.")
        return
    try:
        await bot.edit_user_star_subscription(user_id=message.from_user.id, telegram_payment_charge_id=charge_id, is_canceled=True)
        await db_execute("UPDATE app_subscriptions SET auto_renew=FALSE, updated_at=$2 WHERE telegram_id=$1", message.from_user.id, now_utc())
        await message.answer("Автопродление отключено. Доступ сохранится до конца уже оплаченного периода.")
    except Exception:
        logger.exception("Failed to cancel Telegram Stars subscription")
        await message.answer("Не получилось отключить автопродление. Напиши /paysupport с описанием проблемы.")


@router.message(Command("paysupport"))
async def payment_support(message: Message):
    details = (message.text or "").partition(" ")[2].strip()
    if not details:
        await message.answer("По вопросам оплаты отправь одним сообщением:\n/paysupport описание проблемы\n\nНе присылай данные карты, коды из SMS и пароли.")
        return
    delivered = False
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"💳 Fitmy2.0 — вопрос по оплате\nПользователь: {message.from_user.id} @{message.from_user.username or 'без_username'}\n\n{details}")
            delivered = True
        except Exception:
            logger.exception("Failed to deliver payment support request to admin %s", admin_id)
    await message.answer("Сообщение по оплате передано администратору." if delivered else "Не удалось передать сообщение. Попробуй ещё раз чуть позже.")


@router.pre_checkout_query()
async def subscription_pre_checkout(query: PreCheckoutQuery):
    ok = False
    error = "Не удалось проверить подписку. Создай новый счёт через /subscribe."
    try:
        parts = query.invoice_payload.split(":")
        payload_uid = int(parts[1]) if len(parts) >= 3 and parts[0] == "fitmy2-sub" else 0
        ok = payload_uid == query.from_user.id and query.currency == "XTR" and query.total_amount == SUBSCRIPTION_STARS
    except Exception:
        logger.exception("Subscription pre-checkout validation failed")
    await query.answer(ok=ok, error_message=None if ok else error)


@router.message(F.successful_payment)
async def subscription_successful_payment(message: Message):
    payment = message.successful_payment
    if not payment or payment.currency != "XTR" or not payment.invoice_payload.startswith("fitmy2-sub:"):
        return
    try:
        payload_uid = int(payment.invoice_payload.split(":")[1])
    except Exception:
        return
    if payload_uid != message.from_user.id or payment.total_amount != SUBSCRIPTION_STARS:
        logger.warning("Rejected mismatched subscription payment payload for user %s", message.from_user.id)
        return
    exp_ts = getattr(payment, "subscription_expiration_date", None)
    paid_until = datetime.fromtimestamp(exp_ts, tz=timezone.utc) if exp_ts else now_utc() + timedelta(days=30)
    charge_id = payment.telegram_payment_charge_id
    now = now_utc()
    await db_execute(
        """INSERT INTO app_payments(telegram_id,telegram_payment_charge_id,total_amount,currency,subscription_expiration_date,is_recurring,is_first_recurring,created_at)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8) ON CONFLICT(telegram_payment_charge_id) DO NOTHING""",
        message.from_user.id, charge_id, payment.total_amount, payment.currency, paid_until,
        bool(getattr(payment, "is_recurring", False)), bool(getattr(payment, "is_first_recurring", False)), now,
    )
    await ensure_subscription(message.from_user.id)
    await db_execute(
        """UPDATE app_subscriptions SET status='active',subscription_until=$2,
        telegram_payment_charge_id=COALESCE(telegram_payment_charge_id,$3),auto_renew=TRUE,stars_amount=$4,updated_at=$5
        WHERE telegram_id=$1""",
        message.from_user.id, paid_until, charge_id, SUBSCRIPTION_STARS, now,
    )
    await message.answer(f"Оплата получена. Fitmy2.0 открыт до {paid_until.strftime('%d.%m.%Y')}. Автопродление включено. Отключить: /cancel_subscription.")


@router.message()
async def free_chat(message: Message):
    if not message.text: return
    if not await ensure_ready(message): return
    try:
        answer = await ask_ai(message.from_user.id, message.text)
        await message.answer(answer)
    except Exception:
        logger.exception("AI error")
        await message.answer("Не получилось получить ответ. Попробуй ещё раз.")

async def setup_telegram():
    if not bot:
        logger.warning("TELEGRAM_BOT_TOKEN is missing")
        return
    await bot.set_my_commands([
        BotCommand(command="start", description="Начать работу с FitMyN"),
        BotCommand(command="team", description="Статистика команды"),
        BotCommand(command="schedule", description="Настроить авто-сообщения"),
        BotCommand(command="mealplan", description="Рацион на 7 дней"),
        BotCommand(command="shopping", description="Список покупок"),
        BotCommand(command="subscribe", description="Оформить подписку"),
        BotCommand(command="cancel_subscription", description="Отключить автопродление"),
        BotCommand(command="terms", description="Условия подписки"),
        BotCommand(command="paysupport", description="Поддержка по оплате"),
        BotCommand(command="reset_profile", description="Перезаполнить профиль"),
        BotCommand(command="delete_me", description="Удалить мои данные"),
    ])
    await bot.set_my_description(
        "FitMyN — персональный ИИ-помощник по питанию, тренировкам и привычкам."
    )
    await bot.set_my_short_description(
        "ИИ-тренер и помощник по питанию: план, тренировки и контроль прогресса."
    )

    if APP_URL:
        try:
            await bot.set_chat_menu_button(
                menu_button=MenuButtonWebApp(
                    text="Открыть Fitmy2.0",
                    web_app=WebAppInfo(url=APP_URL),
                )
            )
            logger.info("Telegram Mini App menu button configured: %s", APP_URL)
        except Exception:
            logger.exception("Failed to configure Mini App menu button")

    if RENDER_EXTERNAL_URL:
        webhook_url = f"{RENDER_EXTERNAL_URL}/telegram/{WEBHOOK_SECRET}"
        await bot.set_webhook(
            webhook_url,
            secret_token=WEBHOOK_SECRET,
            drop_pending_updates=False,
        )
        logger.info("Webhook configured: %s", webhook_url)
    else:
        logger.warning("RENDER_EXTERNAL_URL missing; webhook not configured")

async def health(request: web.Request):
    configured = bool(bot and client and pool)
    status = 200 if configured else 503
    return web.json_response(
        {
            "service": "FitMyN",
            "configured": configured,
            "telegram": bool(bot),
            "openai": bool(client),
            "database": bool(pool),
        },
        status=status,
    )

async def _process_telegram_payload(payload: dict):
    try:
        if not bot:
            return
        update = Update.model_validate(payload, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception:
        logger.exception("Telegram update processing failed")


async def telegram_webhook(request: web.Request):
    """Acknowledge Telegram immediately and process updates in background.

    This prevents Telegram from retrying slow AI requests and also ignores duplicate update_id values.
    """
    if not bot:
        return web.Response(status=503, text="Telegram not configured")

    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != WEBHOOK_SECRET:
        return web.Response(status=403, text="Forbidden")

    payload = await request.json()
    update_id = payload.get("update_id")
    now = time.monotonic()

    # prune old ids
    for uid, ts in list(_seen_update_ids.items()):
        if now - ts > UPDATE_DEDUPE_TTL:
            _seen_update_ids.pop(uid, None)

    if isinstance(update_id, int):
        if update_id in _seen_update_ids:
            logger.info("Duplicate Telegram update ignored: %s", update_id)
            return web.Response(text="ok")
        _seen_update_ids[update_id] = now

    task = asyncio.create_task(_process_telegram_payload(payload))
    _update_tasks.add(task)
    task.add_done_callback(_update_tasks.discard)
    return web.Response(text="ok")


def validate_telegram_init_data(init_data: str, max_age_seconds: int = 86400):
    """Validate Telegram Mini App initData and return the Telegram user dict."""
    if not init_data or not TELEGRAM_BOT_TOKEN:
        return None
    try:
        values = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = values.pop("hash", "")
        if not received_hash:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(values.items()))
        secret_key = hmac.new(b"WebAppData", TELEGRAM_BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calculated_hash, received_hash):
            return None
        auth_date = int(values.get("auth_date", "0") or 0)
        if auth_date and time.time() - auth_date > max_age_seconds:
            return None
        user_raw = values.get("user", "")
        user = json.loads(user_raw) if user_raw else None
        return user if isinstance(user, dict) else None
    except Exception:
        logger.exception("Telegram Mini App initData validation failed")
        return None


def app_request_user(request: web.Request):
    return validate_telegram_init_data(request.headers.get("X-Telegram-Init-Data", ""))


async def api_app_mini_meal_image(request: web.Request):
    meal_id = request.match_info.get("meal_id", "")
    item = MINI_APP_MEAL_IMAGE_SOURCES.get(meal_id)
    if not item:
        return web.Response(status=404)
    kind, name, url = item
    if url:
        try:
            timeout = ClientTimeout(total=8)
            async with ClientSession(timeout=timeout) as session:
                async with session.get(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8"}) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        content_type = resp.headers.get("Content-Type", "image/jpeg").split(";", 1)[0]
                        if data and content_type.startswith("image/"):
                            return web.Response(body=data, content_type=content_type, headers={"Cache-Control": "public, max-age=86400"})
        except Exception:
            logger.warning("Mini App meal photo proxy fallback for %s", meal_id)
    safe_name = html_lib.escape(name, quote=True)[:80]
    tint = hashlib.sha256(meal_id.encode("utf-8")).hexdigest()[:6]
    accent = {"Завтрак": "#c8a564", "Обед": "#718c58", "Перекус": "#c88f89", "Ужин": "#58755e"}.get(kind, "#718c58")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="960" height="640" viewBox="0 0 960 640">
<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#{tint}" stop-opacity=".16"/><stop offset="1" stop-color="#f7f2ea"/></linearGradient></defs>
<rect width="960" height="640" fill="url(#bg)"/><ellipse cx="480" cy="360" rx="310" ry="188" fill="#fffdf8" stroke="{accent}" stroke-width="16"/>
<ellipse cx="480" cy="360" rx="245" ry="135" fill="{accent}" opacity=".18"/><circle cx="385" cy="335" r="56" fill="{accent}" opacity=".76"/><circle cx="520" cy="385" r="68" fill="#d7bb80"/><circle cx="602" cy="314" r="44" fill="#91a875"/>
<text x="480" y="105" text-anchor="middle" font-family="Arial,sans-serif" font-size="38" font-weight="700" fill="#173b25">{safe_name}</text>
<text x="480" y="585" text-anchor="middle" font-family="Arial,sans-serif" font-size="24" fill="#687168">Fitmy2.0 · {kind}</text></svg>'''
    return web.Response(text=svg, content_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})


async def mini_app_index(request: web.Request):
    telegram_sdk = '<script src="https://telegram.org/js/telegram-web-app.js"></script>'
    html = MINI_APP_HTML
    if "telegram-web-app.js" not in html:
        html = html.replace("</head>", telegram_sdk + "</head>")
    return web.Response(
        text=html,
        content_type="text/html",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"},
    )


def _parse_weight_value(value):
    if value is None:
        return None
    m = re.search(r"(\d{2,3}(?:[.,]\d{1,2})?)", str(value))
    if not m:
        return None
    try:
        v = float(m.group(1).replace(",", "."))
        return v if 30 <= v <= 300 else None
    except Exception:
        return None


async def get_app_goal_progress(user_id: int, profile=None):
    profile = profile or await get_profile(user_id)
    latest = await db_fetchrow(
        "SELECT weight FROM app_weight_log WHERE telegram_id=$1 ORDER BY created_at DESC LIMIT 1",
        user_id,
    )
    current = float(latest["weight"]) if latest else _parse_weight_value(profile["weight"] if profile else None)
    goal = await db_fetchrow("SELECT target_weight FROM app_goal_settings WHERE telegram_id=$1", user_id)
    target = float(goal["target_weight"]) if goal and goal["target_weight"] is not None else None
    first = await db_fetchrow(
        "SELECT weight FROM app_weight_log WHERE telegram_id=$1 ORDER BY created_at ASC LIMIT 1",
        user_id,
    )
    start = float(first["weight"]) if first else current
    remaining = max(0.0, current - target) if current is not None and target is not None else None
    progress = None
    if current is not None and target is not None and start is not None:
        total = max(0.1, start - target)
        progress = 100.0 if current <= target else max(0.0, min(100.0, (start - current) / total * 100.0))
    return {
        "current_weight": current,
        "target_weight": target,
        "start_weight": start,
        "remaining_weight": remaining,
        "progress_percent": progress,
    }


async def get_app_water(user_id: int):
    local_date = await user_local_date(user_id)
    row = await db_fetchrow(
        "SELECT water_ml FROM app_water_log WHERE telegram_id=$1 AND local_date=$2",
        user_id, local_date,
    )
    return {"date": local_date.isoformat(), "today_ml": int(row["water_ml"]) if row else 0, "goal_ml": 2000}


async def api_app_bootstrap(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)

    profile = await get_profile(user_id)
    first_weight_row = await db_fetchrow("SELECT 1 FROM app_weight_log WHERE telegram_id=$1 LIMIT 1", user_id)
    if not first_weight_row and profile:
        initial_weight = _parse_weight_value(profile["weight"])
        if initial_weight is not None:
            await db_execute(
                "INSERT INTO app_weight_log(telegram_id,weight,created_at) VALUES($1,$2,$3)",
                user_id, initial_weight, profile["updated_at"] or now_utc(),
            )
    settings = await db_fetchrow("SELECT * FROM notification_settings WHERE telegram_id=$1", user_id)
    active_plan = await get_active_weekly_meal_plan(user_id)
    goal_progress = await get_app_goal_progress(user_id, profile)
    water = await get_app_water(user_id)
    workout_progress = await get_app_workout_progress(user_id)
    photo_row = await db_fetchrow("SELECT photo_data FROM app_profile_photos WHERE telegram_id=$1", user_id)
    weight_rows = await db_fetch(
        "SELECT weight, created_at FROM app_weight_log WHERE telegram_id=$1 ORDER BY created_at ASC LIMIT 180",
        user_id,
    )
    subscription = await subscription_info(user_id) if profile else None
    app_week_plan = None
    if profile and await has_consent(user_id) and subscription and subscription["has_access"]:
        app_week_plan = await ensure_app_week_plan(user_id, wait_for_ai=False)

    profile_json = None
    if profile:
        profile_json = {k: profile[k] for k in [
            "name", "age", "sex", "height", "weight", "goal", "activity",
            "frequency", "equipment", "restrictions", "food", "sleep"
        ]}
    settings_json = None
    if settings:
        settings_json = {k: settings[k] for k in [
            "enabled", "timezone", "morning_time", "evening_time", "workout_days"
        ]}

    return web.json_response({
        "telegram_user": {
            "id": user_id,
            "first_name": tg_user.get("first_name"),
            "username": tg_user.get("username"),
            "photo_url": tg_user.get("photo_url"),
        },
        "profile": profile_json,
        "profile_updated_at": profile["updated_at"].isoformat() if profile and profile["updated_at"] else None,
        "goal_progress": goal_progress,
        "water": water,
        "workout_progress": workout_progress,
        "profile_photo": photo_row["photo_data"] if photo_row else None,
        "weight_history": [{"weight": float(r["weight"]), "created_at": r["created_at"].isoformat()} for r in weight_rows],
        "notifications": settings_json,
        "subscription": subscription,
        "weekly_plan": ({
            "start_date": active_plan["start_date"].isoformat(),
            "end_date": active_plan["end_date"].isoformat(),
            "meal_plan": active_plan["meal_plan"],
            "shopping_list": active_plan["shopping_list"],
        } if active_plan else None),
        "weeklyMealPlan": serialize_weekly_meal_plan(app_week_plan) if app_week_plan else None,
        "mealCatalog": catalog_for_week(app_week_plan) if app_week_plan else {},
        "app_week_plan": ({
            "start_date": app_week_plan["start_date"].isoformat(),
            "end_date": app_week_plan["end_date"].isoformat(),
            "plan": decode_app_plan(app_week_plan["plan_json"]),
            "source": app_week_plan["source"],
        } if app_week_plan else None),
    }, headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache", "Expires": "0"})




async def get_app_workout_progress(user_id: int):
    local_date = await user_local_date(user_id)
    week_start = local_date - timedelta(days=local_date.weekday())
    rows = await db_fetch(
        """SELECT local_date, workout_key, workout_name, completed_at
           FROM app_workout_log
           WHERE telegram_id=$1 AND local_date BETWEEN $2 AND $3
           ORDER BY local_date""",
        user_id, week_start, week_start + timedelta(days=6),
    )
    return {
        "week_start": week_start.isoformat(),
        "completed_count": len({r["local_date"] for r in rows}),
        "completed_dates": sorted({r["local_date"].isoformat() for r in rows}),
        "today_completed": any(r["local_date"] == local_date for r in rows),
    }


async def api_app_complete_workout(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    try:
        body = await request.json()
    except Exception:
        body = {}
    workout_key = str(body.get("workout_key") or "daily").strip()[:80]
    workout_name = str(body.get("workout_name") or "Тренировка").strip()[:120]
    local_date = await user_local_date(user_id)
    await db_execute(
        """INSERT INTO app_workout_log(telegram_id,local_date,workout_key,workout_name,completed_at)
           VALUES($1,$2,$3,$4,$5)
           ON CONFLICT(telegram_id,local_date,workout_key)
           DO UPDATE SET workout_name=EXCLUDED.workout_name, completed_at=EXCLUDED.completed_at""",
        user_id, local_date, workout_key, workout_name, now_utc(),
    )
    return web.json_response(await get_app_workout_progress(user_id))


async def api_app_profile_photo(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    try:
        body = await request.json()
        photo_data = str(body.get("photo_data") or "")
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)
    if not photo_data.startswith("data:image/") or len(photo_data) > 1400000:
        return web.json_response({"error": "bad_photo"}, status=400)
    await db_execute(
        """INSERT INTO app_profile_photos(telegram_id,photo_data,updated_at) VALUES($1,$2,$3)
           ON CONFLICT(telegram_id) DO UPDATE SET photo_data=EXCLUDED.photo_data,updated_at=EXCLUDED.updated_at""",
        user_id, photo_data, now_utc(),
    )
    return web.json_response({"ok": True})


async def api_app_weight_history(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    rows = await db_fetch(
        "SELECT weight, created_at FROM app_weight_log WHERE telegram_id=$1 ORDER BY created_at ASC LIMIT 180",
        user_id,
    )
    return web.json_response({"items": [{"weight": float(r["weight"]), "created_at": r["created_at"].isoformat()} for r in rows]})


async def api_app_set_goal(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    try:
        body = await request.json()
        target = float(str(body.get("target_weight", "")).replace(",", "."))
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)
    if not 30 <= target <= 300:
        return web.json_response({"error": "bad_weight"}, status=400)
    first_weight = await db_fetchrow("SELECT 1 FROM app_weight_log WHERE telegram_id=$1 LIMIT 1", user_id)
    if not first_weight:
        profile = await get_profile(user_id)
        initial_weight = _parse_weight_value(profile["weight"] if profile else None)
        if initial_weight is not None:
            await db_execute("INSERT INTO app_weight_log(telegram_id,weight,created_at) VALUES($1,$2,$3)", user_id, initial_weight, now_utc())
    await db_execute(
        """INSERT INTO app_goal_settings(telegram_id,target_weight,updated_at) VALUES($1,$2,$3)
        ON CONFLICT(telegram_id) DO UPDATE SET target_weight=EXCLUDED.target_weight, updated_at=EXCLUDED.updated_at""",
        user_id, target, now_utc(),
    )
    return web.json_response({"target_weight": target})


async def api_app_set_weight(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    try:
        body = await request.json()
        weight = float(str(body.get("weight", "")).replace(",", "."))
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)
    if not 30 <= weight <= 300:
        return web.json_response({"error": "bad_weight"}, status=400)
    first_weight = await db_fetchrow("SELECT 1 FROM app_weight_log WHERE telegram_id=$1 LIMIT 1", user_id)
    if not first_weight:
        profile = await get_profile(user_id)
        initial_weight = _parse_weight_value(profile["weight"] if profile else None)
        if initial_weight is not None and abs(initial_weight - weight) > 0.001:
            await db_execute("INSERT INTO app_weight_log(telegram_id,weight,created_at) VALUES($1,$2,$3)", user_id, initial_weight, now_utc() - timedelta(seconds=1))
    await db_execute("INSERT INTO app_weight_log(telegram_id,weight,created_at) VALUES($1,$2,$3)", user_id, weight, now_utc())
    await db_execute("UPDATE profiles SET weight=$2, updated_at=$3 WHERE telegram_id=$1", user_id, str(weight), now_utc())
    return web.json_response({"current_weight": weight})


async def api_app_add_water(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    try:
        body = await request.json()
        delta = int(body.get("delta_ml", 0))
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)
    if delta == 0 or abs(delta) > 2000:
        return web.json_response({"error": "bad_amount"}, status=400)
    local_date = await user_local_date(user_id)
    row = await db_fetchrow(
        """INSERT INTO app_water_log(telegram_id,local_date,water_ml,updated_at)
        VALUES($1,$2,GREATEST(0,$3),$4)
        ON CONFLICT(telegram_id,local_date) DO UPDATE SET
            water_ml=GREATEST(0,LEAST(10000,app_water_log.water_ml+$3)), updated_at=EXCLUDED.updated_at
        RETURNING water_ml""",
        user_id, local_date, delta, now_utc(),
    )
    return web.json_response({"date": local_date.isoformat(), "water_ml": int(row["water_ml"]), "water_goal_ml": 2000})


async def api_app_week_regenerate(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    if not await has_consent(user_id):
        return web.json_response({"error": "consent_required"}, status=403)
    try:
        row = await regenerate_app_week_plan(user_id)
        return web.json_response({
            "weeklyMealPlan": serialize_weekly_meal_plan(row),
            "mealCatalog": catalog_for_week(row),
            "source": row["source"],
        })
    except Exception:
        logger.exception("Mini App week regeneration failed")
        return web.json_response({"error": "week_generation_failed"}, status=500)


async def api_app_replace_meal(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    if not await has_consent(user_id):
        return web.json_response({"error": "consent_required"}, status=403)
    try:
        body = await request.json()
        day = int(body.get("day"))
        index = int(body.get("index"))
        reason = str(body.get("reason", "different"))[:200]
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)
    if day not in range(7) or index not in range(4):
        return web.json_response({"error": "bad_position"}, status=400)
    try:
        row = await replace_app_meal(user_id, day, index, reason)
        return web.json_response({
            "start_date": row["start_date"].isoformat(),
            "end_date": row["end_date"].isoformat(),
            "plan": decode_app_plan(row["plan_json"]),
            "source": row["source"],
            "weeklyMealPlan": serialize_weekly_meal_plan(row),
            "mealCatalog": catalog_for_week(row),
        })
    except Exception:
        logger.exception("Mini App meal replacement failed")
        return web.json_response({"error": "replace_failed"}, status=500)

async def api_app_subscription_checkout(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool or not bot:
        return web.json_response({"error": "not_ready"}, status=503)
    try:
        body = await request.json()
    except Exception:
        body = {}
    if body.get("terms_accepted") is not True:
        return web.json_response({"error": "terms_required"}, status=400)
    if not await get_profile(user_id):
        return web.json_response({"error": "profile_required"}, status=400)
    sub = await subscription_info(user_id)
    if sub["status"] == "active":
        return web.json_response({"error": "already_active", "subscription": sub}, status=409)
    try:
        link = await create_subscription_invoice_link(user_id)
        return web.json_response({"invoice_link": link, "stars": SUBSCRIPTION_STARS, "period_days": 30})
    except Exception:
        logger.exception("Failed to create subscription invoice link")
        return web.json_response({"error": "invoice_failed"}, status=500)


async def api_app_ask(request: web.Request):
    tg_user = app_request_user(request)
    if not tg_user:
        return web.json_response({"error": "unauthorized"}, status=401)
    user_id = int(tg_user.get("id", 0) or 0)
    if not user_id or not pool:
        return web.json_response({"error": "not_ready"}, status=503)
    if not await subscription_has_access(user_id):
        return web.json_response({"error": "subscription_required", "subscription": await subscription_info(user_id)}, status=402)
    if not await has_consent(user_id):
        return web.json_response({"error": "consent_required"}, status=403)
    body = await request.json()
    message = str(body.get("message", "")).strip()
    if not message:
        return web.json_response({"error": "message_required"}, status=400)
    if len(message) > 1500:
        return web.json_response({"error": "message_too_long"}, status=400)
    try:
        answer = await ask_ai(user_id, message)
        return web.json_response({"answer": answer})
    except Exception:
        logger.exception("Mini App AI request failed")
        return web.json_response({"error": "ai_failed"}, status=500)


async def cron_due(request: web.Request):
    if not CRON_SECRET:
        return web.Response(status=503, text="CRON_SECRET is not configured")
    supplied = request.headers.get("X-Cron-Secret", "")
    if supplied != CRON_SECRET:
        return web.Response(status=403, text="Forbidden")
    stats = await run_due_notifications()
    return web.json_response(stats)


async def on_startup(app: web.Application):
    await init_db()
    await setup_telegram()
    app["notification_task"] = asyncio.create_task(notification_loop())

async def on_cleanup(app: web.Application):
    for update_task in list(_update_tasks):
        update_task.cancel()
    if _update_tasks:
        await asyncio.gather(*list(_update_tasks), return_exceptions=True)

    task = app.get("notification_task")
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    if bot:
        await bot.session.close()
    if pool:
        await pool.close()

def create_app():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_get("/app", mini_app_index)
    app.router.add_get("/app/", mini_app_index)
    app.router.add_get("/api/app/meal-image/{meal_id}", api_app_meal_image)
    app.router.add_get("/api/app/mini-meal-image/{meal_id}", api_app_mini_meal_image)
    app.router.add_get("/api/app/bootstrap", api_app_bootstrap)
    app.router.add_post("/api/app/goal", api_app_set_goal)
    app.router.add_post("/api/app/weight", api_app_set_weight)
    app.router.add_post("/api/app/water", api_app_add_water)
    app.router.add_post("/api/app/workout/complete", api_app_complete_workout)
    app.router.add_post("/api/app/profile/photo", api_app_profile_photo)
    app.router.add_get("/api/app/weight/history", api_app_weight_history)
    app.router.add_post("/api/app/week/regenerate", api_app_week_regenerate)
    app.router.add_post("/api/app/meal/replace", api_app_replace_meal)
    app.router.add_post("/api/app/subscription/checkout", api_app_subscription_checkout)
    app.router.add_post("/api/app/ask", api_app_ask)
    app.router.add_post("/telegram/{secret}", telegram_webhook)
    app.router.add_post("/cron/due", cron_due)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app

if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=PORT)
