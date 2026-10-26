import secrets
import string

import phonenumbers
from phonenumbers import PhoneNumberFormat


def generate_reference_code(prefix: str = "ASV-", length: int = 6) -> str:
    alphabet = string.ascii_uppercase + string.digits
    code = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{prefix}{code}"


def normalize_nigerian_phone_number(value: object) -> str:
    phone = str(value).strip()
    if not phone:
        raise ValueError("A phone number is required.")

    try:
        parsed = phonenumbers.parse(phone, "NG")
    except phonenumbers.NumberParseException as exc:
        raise ValueError("Enter a valid Nigerian phone number.") from exc

    if not phonenumbers.is_valid_number_for_region(parsed, "NG"):
        raise ValueError("Enter a valid Nigerian phone number.")

    return phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
