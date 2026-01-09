import random
from datetime import datetime, timedelta

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

FIRST_NAMES = [
    "ИВАН", "ПЕТР", "СЕРГЕЙ", "АНДРЕЙ", "ДМИТРИЙ",
    "АЛЕКСАНДР", "МИХАИЛ", "АЛЕКСЕЙ", "ЕВГЕНИЙ", "АНТОН"
]

LAST_NAMES = [
    "ИВАНОВ", "ПЕТРОВ", "СИДОРОВ", "СМИРНОВ", "КУЗНЕЦОВ",
    "ПОПОВ", "ВАСИЛЬЕВ", "СОКОЛОВ", "МИХАЙЛОВ", "НОВИКОВ"
]

MIDDLE_NAMES = [
    "ИВАНОВИЧ", "ПЕТРОВИЧ", "СЕРГЕЕВИЧ", "АНДРЕЕВИЧ", "ДМИТРИЕВИЧ",
    "АЛЕКСАНДРОВИЧ", "МИХАЙЛОВИЧ", "АЛЕКСЕЕВИЧ", "ЕВГЕНЬЕВИЧ", "АНТОНОВИЧ"
]

CARD_COUNTRIES = {
    "TJK": {
        "countryCode": "TJK",
        "currencyFrom": "RUB",
        "currencyTo": "TJS",
        "name": "Таджикистан"
    },
    "UZB": {
        "countryCode": "UZB", 
        "currencyFrom": "RUB",
        "currencyTo": "UZS",
        "name": "Узбекистан"
    },
    "KGZ": {
        "countryCode": "KGZ",
        "currencyFrom": "RUB", 
        "currencyTo": "KGS",
        "name": "Кыргызстан"
    }
}

def random_series() -> str:
    return f"{random.randint(10, 99)}{random.randint(10, 99)}"

def random_number() -> str:
    return str(random.randint(100000, 999999))

def genPhone() -> str:
    return f"79{random.randint(100000000, 999999999)}"

def generate_passport_dates() -> dict:
    years_ago = random.randint(18, 60)
    birth_date = datetime.now() - timedelta(days=years_ago * 365)
    birth_date = birth_date.replace(
        month=random.randint(1, 12),
        day=random.randint(1, 28)
    )
    
    min_issue = birth_date + timedelta(days=18 * 365)
    max_issue = datetime.now()
    
    days_range = (max_issue - min_issue).days
    if days_range > 0:
        issue_date = min_issue + timedelta(days=random.randint(0, days_range))
    else:
        issue_date = min_issue
    
    return {
        "birth_date": birth_date.strftime("%Y-%m-%dT00:00:00"),
        "issue_date": issue_date.strftime("%Y-%m-%dT00:00:00")
    }