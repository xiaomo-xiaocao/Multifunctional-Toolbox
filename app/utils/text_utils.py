import json
import base64

def format_json(raw: str) -> str:
    try:
        parsed = json.loads(raw)
        return json.dumps(parsed, indent=2, ensure_ascii=False)
    except json.JSONDecodeError as e:
        return f"JSON 瑙ｆ瀽閿欒: {e}"

def base64_encode(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("utf-8")

def base64_decode(encoded: str) -> str:
    try:
        return base64.b64decode(encoded.encode("utf-8")).decode("utf-8")
    except Exception:
        return "瑙ｇ爜澶辫触锛岃妫€鏌ヨ緭鍏ユ槸鍚︿负鏈夋晥鐨?Base64"
