"""Worker payout preferences. No transfers or external profile lookups."""
import json
import re
from pathlib import Path

_DIRECTORY = json.loads((Path(__file__).resolve().parents[1] / "assets/data/sbp_banks.json").read_text(encoding="utf-8"))
BANK_NAMES = {item["id"]: item["name"] for item in _DIRECTORY["banks"]}
PAYOUT_FIELDS = {"payout_method", "payout_bank_id", "payout_phone"}

def normalize_phone(value: str) -> str:
    if not value:
        return ""
    if (not re.fullmatch(r"[+0-9 ()-]+", value) or value.count("+") > 1
            or ("+" in value and not value.strip().startswith("+"))):
        raise ValueError("Укажите телефон банка в формате +7 900 000-00-00")
    digits = re.sub(r"[^0-9]", "", value)
    if len(digits) == 11 and digits[0] in "78":
        digits = digits[1:]
    if len(digits) != 10:
        raise ValueError("Укажите телефон банка в формате +7 900 000-00-00")
    return "+7" + digits

def clean_bank_id(value: str) -> str:
    if value and value not in BANK_NAMES:
        raise ValueError("Выберите банк из списка")
    return value

def prepare_patch(stored: dict, cleaned: dict) -> dict:
    if not PAYOUT_FIELDS.intersection(cleaned):
        return cleaned
    combined = {**stored, **cleaned}
    if combined.get("payout_method") != "sbp":
        return cleaned
    bank_id = str(combined.get("payout_bank_id") or "")
    phone = normalize_phone(str(combined.get("payout_phone") or ""))
    if bank_id not in BANK_NAMES or not phone:
        raise ValueError("Для выплат по СБП выберите банк и укажите привязанный к нему телефон")
    return {**cleaned, "payout_bank_name": BANK_NAMES[bank_id], "payout_phone": phone}
