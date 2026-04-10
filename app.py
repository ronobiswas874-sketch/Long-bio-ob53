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



# ================= SEND BIO =================
@app.route('/send_bio', methods=['GET'])
def send_bio():
    try:
        token = request.args.get('token')
        bio = request.args.get('bio')

        if not token or not bio:
            return jsonify({
                "status": "error",
                "color": "red",
                "message": "Missing token or bio"
            }), 400

        uid, region = decode_jwt(token)
        name = get_player_info(uid)

        region = (region or "OTHER").upper()
        DATA_API = REGION_APIS.get(region, REGION_APIS["OTHER"])

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

        response = session.post(
            DATA_API,
            data=encrypted,
            headers=headers,
            verify=False,
            timeout=15
        )

        now = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

        if response.status_code != 200:
            return jsonify({
                "status": "error",
                "color": "red",
                "message": "JWT TOKEN INVALID PLEASE CHECK YOUR JWT TOKEN",
                "code": response.status_code
            })

        return jsonify({
            "status": "success",
            "color": "green",
            "time": now,
            "nickname": name,
            "region": region,
            "uid": uid,
            "new_bio": bio
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "color": "red",
            "message": str(e)
        })

@app.route('/')
def home():
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Send Bio Panel</title>
</head>
<body>

<h2 id="msg">Loading...</h2>

<script>
fetch("/send_bio?token=xxx&bio=test")
.then(res => res.json())
.then(data => {

    const msg = document.getElementById("msg");

    msg.innerText = data.message || data.status;

    // 🔥 REAL COLOR APPLY
    if (data.color === "red") {
        msg.style.color = "red";
    }

    if (data.color === "green") {
        msg.style.color = "green";
    }
});
</script>

</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
