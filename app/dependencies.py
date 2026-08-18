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


def read_config(path, default=None, warn=True):
    if default is None:
        default = {}
    if path.exists() is False:
        if warn:
            print(f"WARNING: {path} not found")
        return default
    else:
        with path.open('r') as ymlfile:
            return yaml.safe_load(ymlfile) or {}


BAS_DIR = Path(__file__).parent
config = {
    **read_config(BAS_DIR / 'config.yml'),
    **read_config(BAS_DIR / 'config.local.yml', warn=False),
}


def get_config_value(key, default=None):
    value = os.getenv(key)
    if value is not None and value != "":
        return value
    return config.get(key, default)


def get_config_list(key, default=None):
    value = os.getenv(key)
    if value is not None and value != "":
        return [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]
    return config.get(key, default or [])


# Database
DB_USER = get_config_value("DB_USER")
DB_PASS = get_config_value("DB_PASS")
DB_HOST = get_config_value("DB_HOST")
DB_PORT = get_config_value("DB_PORT")
DB_NAME = get_config_value("DB_NAME")


DATABASE_DATA = f"{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
DATABASE_URL = f'postgresql+asyncpg://{DATABASE_DATA}'
DATABASE_URL_SYNC = f'postgresql://{DATABASE_DATA}'


WEBHOOK_DOMAIN = get_config_value("WEBHOOK_DOMAIN")
WEBHOOK_PATH = get_config_value("WEBHOOK_PATH")
WEBAPP_HOST = get_config_value("WEBAPP_HOST")
WEBAPP_PORT = get_config_value("WEBAPP_PORT")


YANDEX_TOKEN = get_config_value('YANDEX_TOKEN')
CLIENT_SECRET = get_config_value('CLIENT_SECRET')
CLIENT_ID = get_config_value('CLIENT_ID')
YANDEX_DIR = '/Подрядчики Телеграмм Бот паспорта'
GEOCODER_API = get_config_value('GEOCODER_API')

GOSUSLUGI_LOGIN = get_config_value('GOSUSLUGI_LOGIN')
GOSUSLUGI_PASSWORD = get_config_value('GOSUSLUGI_PASSWORD')
GOSUSLUGI_HTTP_PROXY = get_config_value('GOSUSLUGI_HTTP_PROXY')


YOUDO_ISS = get_config_value('YOUDO_ISS')
YOUDO_KID = get_config_value('YOUDO_KID')
YOUDO_CID = get_config_value('YOUDO_CID')
YOUDO_PROJECT_ID = get_config_value('YOUDO_PROJECT_ID')
YOUDO_PRIVATE_KEY_PATH = get_config_value('YOUDO_PRIVATE_KEY_PATH')


CAPMONSTER_API_KEY = get_config_value('CAPMONSTER_API_KEY')


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

API_TOKEN = get_config_value('API_TOKEN')
ADMINS = get_config_list('ADMINS', [])
MODERATOR_ID = get_config_value('MODERATOR_ID')
SUPPORT_ID = get_config_value('SUPPORT_ID')
REQUESTS_ID = get_config_value('REQUESTS_ID')
TICKETS_ID = get_config_value('TICKETS_ID')
ERRORS_ID = get_config_value('ERRORS_ID')
RAISING_ID = get_config_value('RAISING_ID')
CHAT_IDS = {
    "Москва": get_config_value('MOSCOW_ID_1'),
    "Москва_2": get_config_value('MOSCOW_ID_2'),
    "Санкт-Петербург": get_config_value('SPB_ID_1'),
    "Санкт-Петербург_2": get_config_value('SPB_ID_2'),
    "Нижний Новгород": get_config_value('NN_ID'),
    "Краснодар": get_config_value('KRAS_ID'),
    "Ростов-на-Дону": get_config_value('ROSTOV_ID'),
    "Казань": get_config_value('KAZAN_ID'),
    "Самара": get_config_value('SAMARA_ID'),
    "Екатеринбург": get_config_value('EKB_ID'),
    "Уфа": get_config_value('UFA_ID')
}
bot = Bot(token=API_TOKEN, parse_mode='HTML')
dp = Dispatcher(bot, storage=MemoryStorage())
app = FastAPI()



CONFIG_ADMIN = 'config_admin.yaml'
CRM_URL = get_config_value('CRM_URL', 'https://test.workstaffcrm.ru/api/telegram/')
HEADERS = {
    "X-Telegram-Bot-Token": get_config_value('CRM_API_KEY'),
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

