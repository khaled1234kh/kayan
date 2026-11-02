import hashlib
import hmac
import json
from integration.roe_signing import signing_key


def bridge_signature(payload):
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hmac.new(signing_key().encode(), ("kayan-bridge-v1:"+body).encode(), hashlib.sha256).hexdigest()
