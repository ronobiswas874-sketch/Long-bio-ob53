from flask import Flask, request, jsonify
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import requests
import traceback
from datetime import datetime
import my_pb2
from key_iv import AES_KEY, AES_IV
import base64
import json
import time

app = Flask(__name__)
session = requests.Session()

# ===== REGION BASED API =====
REGION_APIS = {
    "IND": "https://client.ind.freefiremobile.com/UpdateSocialBasicInfo",
    "BR": "https://client.br.freefiremobile.com/UpdateSocialBasicInfo",
    "US": "https://client.us.freefiremobile.com/UpdateSocialBasicInfo",
    "SAC": "https://client.sac.freefiremobile.com/UpdateSocialBasicInfo",
    "NA": "https://client.na.freefiremobile.com/UpdateSocialBasicInfo",
    "OTHER": "https://clientbp.ggblueshark.com/UpdateSocialBasicInfo"
}

# ===== OB52 HEADERS =====
HEADERS_TEMPLATE = {
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 10; SM-G973F Build/QP1A)",
    "Connection": "Keep-Alive",
    "Accept-Encoding": "gzip",
    "Content-Type": "application/octet-stream",
    "Expect": "100-continue",
    "X-Unity-Version": "2019.4.40f1",
    "X-GA": "v1 1",
    "ReleaseVersion": "OB53",
}

# ===== AES ENCRYPT =====
def encrypt_message(key, iv, plaintext):
    cipher = AES.new(key, AES.MODE_CBC, iv)
    padded = pad(plaintext, AES.block_size)
    return cipher.encrypt(padded)

# ===== JWT DECODE =====
def decode_jwt(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        data = json.loads(decoded)

        name = data.get("nickname", "Unknown")
        uid = data.get("account_id", "Unknown")
        region = data.get("noti_region", "Unknown")
        version = data.get("release_version", "Unknown")
        exp = data.get("exp", 0)

        if exp:
            expire_time = datetime.fromtimestamp(exp).strftime("%d %b %Y %I:%M %p")
            remaining = int(exp - time.time())
            hours = remaining // 3600
            minutes = (remaining % 3600) // 60
            remaining_text = f"{hours}h {minutes}m left"
        else:
            expire_time = "Unknown"
            remaining_text = "Unknown"

        return name, uid, region, version, expire_time, remaining_text

    except Exception as e:
        print("JWT decode error:", e)
        return "Unknown", "Unknown", "Unknown", "Unknown", "Unknown", "Unknown"

# ================= SEND BIO =================
@app.route('/send_bio', methods=['GET'])
def send_bio():
    try:
        token = request.args.get('token')
        bio = request.args.get('bio')

        if not token or not bio:
            return jsonify({
                "status": "error",
                "message": "Missing token or bio"
            }), 400

        # ===== Decode JWT info =====
        name, uid, region, version, expire_time, remaining = decode_jwt(token)

        # ===== SELECT API BASED ON REGION =====
        region = region.upper()  # Ensure region is uppercase
        DATA_API = REGION_APIS.get(region, REGION_APIS["OTHER"])

        # ===== Protobuf =====
        message = my_pb2.Signature()
        message.field2 = 9
        message.field8 = bio
        message.field9 = 1

        encrypted = encrypt_message(
            AES_KEY,
            AES_IV,
            message.SerializeToString()
        )

        headers = HEADERS_TEMPLATE.copy()
        headers["Authorization"] = f"Bearer {token}"

        # ===== Update Bio =====
        response = session.post(
            DATA_API,
            data=encrypted,
            headers=headers,
            verify=False,
            timeout=15
        )

        # ===== REAL STATUS CHECK =====
        if response.status_code != 200:
            return jsonify({
                "status": "error",
                "message": "Game API request failed",
                "code": response.status_code
            })

        now = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

        return jsonify({
            "status": "success",
            "time": now,
            "nickname": name,
            "region": region,
            "uid": uid,
            "release_version": version,
            "token_expire": expire_time,
            "remaining_time": remaining,
            "new_bio": bio,
            "api_used": DATA_API,
            "response_status_code": response.status_code,
            "response_text": response.text
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)