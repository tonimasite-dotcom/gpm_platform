from pathlib import Path
import yaml
from aiogram import Bot, Dispatcher
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from fastapi import FastAPI
import os

class Config:
    def __init__(self):
        self.bypass_geocoder: bool = False


global_config = Config()


def read_config(path, default={}):
    if path.exists() is False:
        print(f"WARNING: {path} not found")
        return default
    else:
        with path.open('r') as ymlfile:
            return yaml.safe_load(ymlfile)


BAS_DIR = Path(__file__).parent
config = read_config(BAS_DIR / 'config.yml')


# Database
DB_USER = config.get("DB_USER")
DB_PASS = config.get("DB_PASS")
DB_HOST = config.get("DB_HOST")
DB_PORT = config.get("DB_PORT")
DB_NAME = config.get("DB_NAME")


DATABASE_DATA = f"{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DATABASE_URL = f'postgresql+asyncpg://{DATABASE_DATA}'
DATABASE_URL_SYNC = f'postgresql://{DATABASE_DATA}'


WEBHOOK_DOMAIN = config.get("WEBHOOK_DOMAIN")
WEBHOOK_PATH = config.get("WEBHOOK_PATH")
WEBAPP_HOST = config.get("WEBAPP_HOST")
WEBAPP_PORT = config.get("WEBAPP_PORT")


YANDEX_TOKEN = config.get('YANDEX_TOKEN')
CLIENT_SECRET = config.get('CLIENT_SECRET')
CLIENT_ID = config.get('CLIENT_ID')
YANDEX_DIR = '/Подрядчики Телеграмм Бот паспорта'
GEOCODER_API = config.get('GEOCODER_API')

GOSUSLUGI_LOGIN = config.get('GOSUSLUGI_LOGIN')
GOSUSLUGI_PASSWORD = config.get('GOSUSLUGI_PASSWORD')
GOSUSLUGI_HTTP_PROXY = config.get('GOSUSLUGI_HTTP_PROXY')


YOUDO_ISS = config.get('YOUDO_ISS')
YOUDO_KID = config.get('YOUDO_KID')
YOUDO_CID = config.get('YOUDO_CID')
YOUDO_PROJECT_ID = config.get('YOUDO_PROJECT_ID')
YOUDO_PRIVATE_KEY_PATH = config.get('YOUDO_PRIVATE_KEY_PATH')


CAPMONSTER_API_KEY = config.get('CAPMONSTER_API_KEY')


DB_CONFIG = {
    'connections': {
        'default': {
            'engine': 'tortoise.backends.asyncpg',
            'credentials': {
                'host': f'{DB_HOST}',
                'port': f'{DB_PORT}',
                'user': f'{DB_USER}',
                'password': f'{DB_PASS}',
                'database': f'{DB_NAME}',
            },
        },
    },
    'apps': {
        'models': {
            'models': ['app.db.models', 'aerich.models'],
            'default_connection': 'default',
        },
    },
}

# with open("aerich.ini", "r") as aerich_file:
#     aerich_config = aerich_file.read()
#
# aerich_config = aerich_config.replace("%(db_url)s", DATABASE_URL)
#
# with open("aerich.ini", "w") as aerich_file:
#     aerich_file.write(aerich_config)

API_TOKEN = config.get('API_TOKEN')
ADMINS = config.get('ADMINS', [])
MODERATOR_ID = config.get('MODERATOR_ID')
SUPPORT_ID = config.get('SUPPORT_ID')
REQUESTS_ID = config.get('REQUESTS_ID')
TICKETS_ID = config.get('TICKETS_ID')
ERRORS_ID = config.get('ERRORS_ID')
RAISING_ID = config.get('RAISING_ID')
# MOSCOW_ID_1 = config.get('MOSCOW_ID_1')
# MOSCOW_ID_2 = config.get('MOSCOW_ID_2')
# SPB_ID_1 = config.get('SPB_ID_1')
# SPB_ID_2 = config.get('SPB_ID_2')
# NN_ID = config.get('NN_ID')
# KRAS_ID = config.get('KRAS_ID')
# ROSTOV_ID = config.get('ROSTOV_ID')
# KAZAN_ID = config.get('KAZAN_ID')
# SAMARA_ID = config.get('SAMARA_ID')
# EKB_ID = config.get('EKB_ID')
CHAT_IDS = {
    "Москва": config.get('MOSCOW_ID_1'),
    "Москва_2": config.get('MOSCOW_ID_2'),
    "Санкт-Петербург": config.get('SPB_ID_1'),
    "Санкт-Петербург_2": config.get('SPB_ID_2'),
    "Нижний Новгород": config.get('NN_ID'),
    "Краснодар": config.get('KRAS_ID'),
    "Ростов-на-Дону": config.get('ROSTOV_ID'),
    "Казань": config.get('KAZAN_ID'),
    "Самара": config.get('SAMARA_ID'),
    "Екатеринбург": config.get('EKB_ID'),
    "Уфа": config.get('UFA_ID')
}
bot = Bot(token=API_TOKEN, parse_mode='HTML')
dp = Dispatcher(bot, storage=MemoryStorage())
app = FastAPI()



CONFIG_ADMIN = 'config_admin.yaml'
CRM_URL = 'https://test.workstaffcrm.ru/api/telegram/'
HEADERS = {
    "X-Telegram-Bot-Token": config.get('CRM_API_KEY'),
    "Content-Type": "application/json"
}

def load_config(filename=CONFIG_ADMIN):
    if os.path.exists(filename):
        with open(filename, 'r', encoding='utf-8') as file:
            return yaml.safe_load(file) or {}  
    return {}  
    
def save_config(config_admin, filename=CONFIG_ADMIN):
    with open(filename, 'w', encoding='utf-8') as file:
        yaml.safe_dump(config_admin, file, default_flow_style=False, allow_unicode=True)


def update_config(key, value, filename=CONFIG_ADMIN):
    config_admin = load_config(filename)  
    config_admin[key] = value  
    save_config(config_admin, filename)  


def get_config(key, filename=CONFIG_ADMIN):
    config_admin = load_config(filename)  
    return config_admin.get(key)
  