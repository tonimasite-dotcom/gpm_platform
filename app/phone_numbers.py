"""Phone formatting and exact identity. Never guess by suffix or truncate."""
import re


def normalize_russian_phone(value: str) -> str:
    if (not isinstance(value, str) or len(value) > 64
            or not re.fullmatch(r"[+0-9()\s.-]+", value)):
        raise ValueError("Укажите телефон в формате +7 (999) 999-99-77")
    compact = re.sub(r"[()\s.-]", "", value)
    if re.fullmatch(r"\+7[0-9]{10}", compact):
        return compact
    if re.fullmatch(r"[78][0-9]{10}", compact):
        return "+7" + compact[1:]
    if re.fullmatch(r"[0-9]{10}", compact):
        return "+7" + compact
    raise ValueError("Укажите телефон в формате +7 (999) 999-99-77")


def format_russian_phone(value: str) -> str:
    number = normalize_russian_phone(value)[2:]
    return f"+7 ({number[:3]}) {number[3:6]}-{number[6:8]}-{number[8:]}"
