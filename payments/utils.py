def translate_payment_channel(channel: str) -> str:
    payment_type_by_channel = {
                "card": "card",
                "bank": "bank_transfer",
                "apple_pay": "card",
                "ussd": "ussd",
                "qr": "other",
                "mobile_money": "mobile_money",
                "bank_transfer": "bank_transfer",
                "eft": "bank_transfer",
                "capitec_pay": "mobile_money",
                "payattitude": "mobile_money",
        }

    return payment_type_by_channel.get(channel)