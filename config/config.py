import random
import os
import dotenv

dotenv.load_dotenv()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

TIMEZONES = ["Europe/Moscow", "Europe/Samara", "Asia/Yekaterinburg"]
WIDTHS = [1920, 1366, 1440, 1536]
HEIGHTS = [1080, 768, 900, 864]

FIRST_NAMES = ["ИВАН", "ПЕТР", "СЕРГЕЙ", "АНДРЕЙ", "ДМИТРИЙ", "АЛЕКСАНДР", "МИХАИЛ", "АЛЕКСЕЙ", "ЕВГЕНИЙ", "АНТОН"]
LAST_NAMES = ["ИВАНОВ", "ПЕТРОВ", "СИДОРОВ", "СМИРНОВ", "КУЗНЕЦОВ", "ПОПОВ", "ВАСИЛЬЕВ", "СОКОЛОВ", "МИХАЙЛОВ", "НОВИКОВ"]
MIDDLE_NAMES = ["ИВАНОВИЧ", "ПЕТРОВИЧ", "СЕРГЕЕВИЧ", "АНДРЕЕВИЧ", "ДМИТРИЕВИЧ", "АЛЕКСАНДРОВИЧ", "МИХАЙЛОВИЧ", "АЛЕКСЕЕВИЧ", "ЕВГЕНЬЕВИЧ", "АНТОНОВИЧ"]

CARD_COUNTRIES = {
    "TJK": {"countryCode": "TJK", "currencyFrom": "RUB", "currencyTo": "TJS", "name": "Таджикистан"},
    "UZB": {"countryCode": "UZB", "currencyFrom": "RUB", "currencyTo": "UZS", "name": "Узбекистан"},
    "KGZ": {"countryCode": "KGZ", "currencyFrom": "RUB", "currencyTo": "KGS", "name": "Кыргызстан"}
}

TARGET_URL = "https://multitransfer.ru"

CAPTCHA_API_KEY = os.getenv('CAPTCHA_API_KEY')
PROXY = os.getenv('PROXY')
CAPTCHA_SERVICE = "2captcha"
PRIORITY = 10

PASSPORT_DATES = [
    {"date_birth": "1985-03-15T00:00:00", "date_issue": "2010-06-20T00:00:00"},
    {"date_birth": "1990-07-22T00:00:00", "date_issue": "2015-09-10T00:00:00"},
    {"date_birth": "1988-11-30T00:00:00", "date_issue": "2012-04-15T00:00:00"},
    {"date_birth": "1992-05-18T00:00:00", "date_issue": "2016-08-25T00:00:00"},
    {"date_birth": "1987-09-08T00:00:00", "date_issue": "2011-12-03T00:00:00"},
    {"date_birth": "1991-01-25T00:00:00", "date_issue": "2014-05-30T00:00:00"},
    {"date_birth": "1989-06-12T00:00:00", "date_issue": "2013-10-18T00:00:00"},
    {"date_birth": "1993-10-05T00:00:00", "date_issue": "2017-02-14T00:00:00"},
    {"date_birth": "1986-04-28T00:00:00", "date_issue": "2010-11-22T00:00:00"},
    {"date_birth": "1994-08-16T00:00:00", "date_issue": "2018-01-09T00:00:00"},
    {"date_birth": "1984-12-20T00:00:00", "date_issue": "2009-07-15T00:00:00"},
    {"date_birth": "1995-02-11T00:00:00", "date_issue": "2019-06-28T00:00:00"},
    {"date_birth": "1983-07-03T00:00:00", "date_issue": "2008-03-19T00:00:00"},
    {"date_birth": "1996-11-24T00:00:00", "date_issue": "2020-04-12T00:00:00"},
    {"date_birth": "1982-05-14T00:00:00", "date_issue": "2007-09-08T00:00:00"},
    {"date_birth": "1997-09-07T00:00:00", "date_issue": "2021-02-23T00:00:00"},
    {"date_birth": "1981-01-19T00:00:00", "date_issue": "2006-12-05T00:00:00"},
    {"date_birth": "1998-04-30T00:00:00", "date_issue": "2022-08-17T00:00:00"},
    {"date_birth": "1980-08-26T00:00:00", "date_issue": "2005-05-11T00:00:00"},
    {"date_birth": "1999-12-09T00:00:00", "date_issue": "2023-03-26T00:00:00"},
]

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
TOKEN_POOL_SIZE = int(os.getenv('TOKEN_POOL_SIZE', '10'))
TOKEN_LIFETIME = int(os.getenv('TOKEN_LIFETIME', '300'))

def random_series() -> str:
    return f"{random.randint(10, 99)}{random.randint(10, 99)}"


def random_number() -> str:
    return str(random.randint(100000, 999999))


def genPhone() -> str:
    return f"79{random.randint(100000000, 999999999)}"

