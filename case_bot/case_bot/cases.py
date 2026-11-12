"""Кейсы и предметы. Цены - виртуальные монеты, не реальные деньги.

Шансы редкостей близки к настоящим в CS:
Mil-spec 79.92% / Restricted 15.98% / Classified 3.2% / Covert 0.64% / Rare 0.26%
"""

RARITIES = {
    "milspec":    {"title": "Армейское качество", "emoji": "🟦", "weight": 7992},
    "restricted": {"title": "Запрещённое",        "emoji": "🟪", "weight": 1598},
    "classified": {"title": "Засекреченное",      "emoji": "🩷", "weight": 320},
    "covert":     {"title": "Тайное",             "emoji": "🟥", "weight": 64},
    "rare":       {"title": "Редкий предмет",     "emoji": "🟨", "weight": 26},
}


def item(name, rarity, price):
    return {"name": name, "rarity": rarity, "price": price}


CASES = {
    "start": {
        "name": "Старт-кейс",
        "price": 200,
        "items": [
            item("MAC-10 | Heat", "milspec", 25),
            item("P250 | Supernova", "milspec", 30),
            item("Nova | Antique", "milspec", 20),
            item("SG 553 | Tornado", "milspec", 35),
            item("AK-47 | Elite Build", "restricted", 90),
            item("M4A4 | Zirka", "restricted", 80),
            item("USP-S | Guardian", "restricted", 110),
            item("AWP | Redline", "classified", 350),
            item("Glock-18 | Water Elemental", "classified", 300),
            item("AK-47 | Redline", "covert", 900),
            item("M4A1-S | Hyper Beast", "covert", 1000),
            item("★ Bayonet | Fade", "rare", 12000),
            item("★ Karambit | Doppler", "rare", 15000),
        ],
    },
    "premium": {
        "name": "Премиум-кейс",
        "price": 1000,
        "items": [
            item("P90 | Asiimov", "milspec", 120),
            item("FAMAS | Roll Cage", "milspec", 100),
            item("Five-SeveN | Monkey Business", "milspec", 140),
            item("MP7 | Nemesis", "milspec", 130),
            item("AK-47 | Asiimov", "restricted", 450),
            item("M4A4 | Neo-Noir", "restricted", 500),
            item("Desert Eagle | Printstream", "restricted", 600),
            item("AWP | Neo-Noir", "classified", 1800),
            item("USP-S | Kill Confirmed", "classified", 1600),
            item("AK-47 | Fire Serpent", "covert", 5500),
            item("M4A1-S | Printstream", "covert", 5000),
            item("★ Butterfly Knife | Marble Fade", "rare", 60000),
            item("★ Sport Gloves | Pandora's Box", "rare", 80000),
        ],
    },
}
