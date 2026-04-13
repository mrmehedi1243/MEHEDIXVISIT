from flask import Flask, jsonify, request
import aiohttp
import asyncio
import json
import os
from byte import encrypt_api, Encrypt_ID
from visit_count_pb2 import Info

app = Flask(__name__)

# ================= TOKEN LOAD =================
def load_tokens(server_name):
    try:
        if server_name == "BD":
            path = "token_bd.json"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            path = "token_br.json"
        else:
            path = "token_bd.json"

        with open(path, "r") as f:
            data = json.load(f)

        return [i["token"] for i in data if i.get("token") not in ["", "N/A", None]]

    except Exception as e:
        app.logger.error(f"❌ Token load error: {e}")
        return []

# ================= URL =================
def get_url(server):
    if server == "IND":
        return "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    elif server in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
    else:
        return "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"

# ================= PARSE =================
def parse_protobuf_response(response_data):
    try:
        info = Info()
        info.ParseFromString(response_data)

        return {
            "uid": getattr(info.AccountInfo, "UID", 0),
            "nickname": getattr(info.AccountInfo, "PlayerNickname", ""),
            "likes": getattr(info.AccountInfo, "Likes", 0),
            "region": getattr(info.AccountInfo, "PlayerRegion", ""),
            "level": getattr(info.AccountInfo, "Levels", 0),
        }

    except Exception as e:
        print("❌ Protobuf failed, trying fallback...", e)

        # fallback (safe default)
        return {
            "uid": 0,
            "nickname": "Unknown",
            "likes": 0,
            "region": "",
            "level": 0,
        }

# ================= VISIT =================
async def send_requests(tokens, uid, server):
    url = get_url(server)
    connector = aiohttp.TCPConnector(limit=0)

    success = 0
    first_resp = None
    player_info = None

    encrypted = encrypt_api("08" + Encrypt_ID(str(uid)) + "1801")
    data = bytes.fromhex(encrypted)

    async with aiohttp.ClientSession(connector=connector) as session:

        async def hit(token):
            headers = {
                "ReleaseVersion": "OB53",  # ✅ FIXED
                "X-GA": "v1 1",
                "Authorization": f"Bearer {token}",
                "Host": url.replace("https://", "").split("/")[0]
            }

            try:
                async with session.post(url, headers=headers, data=data, ssl=False) as resp:
                    if resp.status == 200:
                        r = await resp.read()
                        return True, r
                    return False, None
            except:
                return False, None

        tasks = [hit(token) for token in tokens]
        results = await asyncio.gather(*tasks)

        for ok, resp in results:
            if ok:
                success += 1
                if first_resp is None and resp and len(resp) > 5:
                    first_resp = resp
                    player_info = parse_protobuf_response(resp)

    return success, len(tokens), player_info

# ================= ROUTE =================
@app.route("/visit", methods=["GET"])
def visit_api():
    uid = request.args.get("uid")
    region = request.args.get("region", "IND").upper()

    if not uid or not uid.isdigit():
        return jsonify({"error": "UID must be number"}), 400

    uid = int(uid)
    tokens = load_tokens(region)

    if not tokens:
        return jsonify({"error": "No tokens found"}), 500

    success, total, player = asyncio.run(send_requests(tokens, uid, region))

    failed = total - success

    # fallback if decode failed
    player_name = player["nickname"] if player else "Unknown"
    player_uid = player["uid"] if player and player["uid"] != 0 else uid
    player_likes = player["likes"] if player else 0

    return jsonify({
        "VISIT_STATUS": "✅ VISIT SENT SUCCESSFUL!",
        "PlayerNickname": player_name,
        "UID": player_uid,
        "Region": region,
        "Likes": player_likes,
        "Successful": success,
        "Failed": failed,
        "Total": total,
        "Credits": "@Sextymods"
    }), 200


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 6000))
    app.run(host="0.0.0.0", port=port, debug=True)