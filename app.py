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
    return cipher.encrypt(pad(plaintext, AES.block_size))

# ===== JWT DECODE (ONLY UID USE) =====
def decode_jwt(token):
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        decoded = base64.urlsafe_b64decode(payload)
        data = json.loads(decoded)

        uid = data.get("account_id", "Unknown")
        region = data.get("noti_region", "OTHER")

        return uid, region

    except Exception as e:
        print("JWT decode error:", e)
        return "Unknown", "OTHER"


# ===== REAL PLAYER INFO API =====
def get_player_info(uid):
    try:
        url = f"https://sextyinfo-cyan.vercel.app/player-info?uid={uid}"
        r = session.get(url, timeout=10)
        data = r.json()

        # ✅ correct path (your real response)
        nickname = (
            data.get("basicInfo", {}).get("nickname")
        )

        # safety fallback (optional)
        if not nickname:
            nickname = "Unknown Player"

        return nickname

    except Exception as e:
        print("Player info error:", e)
        return "Unknown Player"



import urllib.parse
from datetime import datetime, timedelta # নিশ্চিত করুন timedelta ইম্পোর্ট করা আছে

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

        # Decode the bio to handle any encoded spaces
        bio = urllib.parse.unquote_plus(bio)

        # ===== GET UID + REGION =====
        uid, region = decode_jwt(token)

        # ===== GET REAL NICKNAME =====
        name = get_player_info(uid)

        # ===== SELECT API =====
        region = region.upper()
        DATA_API = REGION_APIS.get(region, REGION_APIS["OTHER"])

        # ===== PROTOBUF =====
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

        # ===== SEND REQUEST =====
        response = session.post(
            DATA_API,
            data=encrypted,
            headers=headers,
            verify=False,
            timeout=15
        )

        if response.status_code != 200:
            return jsonify({
                "status": "error",
                "message": "JWT TOKEN INVALID PLEASE CHECK YOUR JWT TOKEN",
                "code": response.status_code
            })

        # ===== KOLKATA TIME (IST) FIX - ADDED ONLY =====
        # UTC এর সাথে ৫ ঘণ্টা ৩০ মিনিট যোগ করে কলকাতা সময় সেট করা হয়েছে
        now_ist = datetime.utcnow() + timedelta(hours=5, minutes=30)
        now = now_ist.strftime("%H:%M:%S %d/%m/%Y")

        return jsonify({
            "status": "success",
            "time": now,
            "nickname": name,
            "region": region,
            "uid": uid,
            "release_version": "OB53",
            "new_bio": bio,
            "api_owner": "XEROX_MOD",
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
