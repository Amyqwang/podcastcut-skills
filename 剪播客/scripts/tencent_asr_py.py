#!/usr/bin/env python3
"""
腾讯云 ASR 录音文件识别（纯 Python 标准库，正确 TC3 签名）
用法: python3 tencent_asr_py.py <音频URL> <说话人数量>
输出: tencent_asr_result.json → aliyun_funasr_transcription.json (兼容格式)
"""
import sys, os, json, time, hmac, hashlib, http.client, subprocess

def sign(key, msg):
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()

def tc3_auth(secret_id, secret_key, service, host, action, body, timestamp, date):
    # 1. 拼接规范请求串
    ct = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{ct}\nhost:{host}\n"
    signed_headers = "content-type;host"
    hashed_payload = hashlib.sha256(body.encode("utf-8")).hexdigest()
    canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"

    # 2. 拼接待签名串
    credential_scope = f"{date}/{service}/tc3_request"
    hashed_canonical = hashlib.sha256(canonical_request.encode("utf-8")).hexdigest()
    string_to_sign = f"TC3-HMAC-SHA256\n{timestamp}\n{credential_scope}\n{hashed_canonical}"

    # 3. HMAC 签名链
    secret_date = sign(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = sign(secret_date, service)
    secret_signing = sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    return (f"TC3-HMAC-SHA256 Credential={secret_id}/{credential_scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}")

def api_call(secret_id, secret_key, action, body_dict):
    host = "asr.tencentcloudapi.com"
    service = "asr"
    version = "2019-06-14"
    timestamp = str(int(time.time()))
    date = time.strftime("%Y-%m-%d", time.gmtime())
    body = json.dumps(body_dict)

    auth = tc3_auth(secret_id, secret_key, service, host, action, body, timestamp, date)

    conn = http.client.HTTPSConnection(host)
    headers = {
        "Authorization": auth,
        "Content-Type": "application/json; charset=utf-8",
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Version": version,
        "X-TC-Timestamp": timestamp,
        "X-TC-Region": "ap-shanghai",
    }
    conn.request("POST", "/", body, headers)
    resp = conn.getresponse()
    data = json.loads(resp.read().decode("utf-8"))
    conn.close()
    return data

def main():
    if len(sys.argv) < 2:
        print("用法: python3 tencent_asr_py.py <音频URL> [说话人数量]")
        sys.exit(1)

    audio_url = sys.argv[1]
    speaker_count = int(sys.argv[2]) if len(sys.argv) > 2 else 2

    # 从环境变量读取密钥
    secret_id = os.environ.get("TENCENT_SECRET_ID", "")
    secret_key = os.environ.get("TENCENT_SECRET_KEY", "")
    if not secret_id or not secret_key:
        print("❌ 请设置环境变量 TENCENT_SECRET_ID 和 TENCENT_SECRET_KEY")
        sys.exit(1)

    print(f"🎤 提交腾讯云 ASR 转录任务")
    print(f"   音频URL: {audio_url}")
    print(f"   说话人数: {speaker_count}")
    print()

    # 提交任务
    resp = api_call(secret_id, secret_key, "CreateRecTask", {
        "EngineModelType": "16k_zh",
        "ChannelNum": 1,
        "ResTextFormat": 3,
        "SourceType": 0,
        "Url": audio_url,
        "SpeakerDiarization": 1,
        "SpeakerNumber": speaker_count,
    })

    if "Response" in resp and "Error" in resp["Response"]:
        print(f"❌ 提交失败: {resp['Response']['Error']['Message']}")
        sys.exit(1)

    task_id = resp["Response"]["Data"]["TaskId"]
    print(f"✅ 任务已提交 (TaskId: {task_id})")
    print("⏳ 等待转录完成...")

    # 轮询
    for attempt in range(300):
        time.sleep(5)
        qr = api_call(secret_id, secret_key, "DescribeTaskStatus", {"TaskId": task_id})

        if "Response" in qr and "Error" in qr["Response"]:
            print(f"\n❌ 查询失败: {qr['Response']['Error']['Message']}")
            sys.exit(1)

        status = qr["Response"]["Data"]["Status"]
        if status == 2:
            print(f"\n✅ 转录完成！")
            with open("tencent_asr_result.json", "w", encoding="utf-8") as f:
                json.dump(qr, f, ensure_ascii=False, indent=2)
            print("   已保存: tencent_asr_result.json")

            # 转换为阿里云兼容格式
            script_dir = os.path.dirname(os.path.abspath(__file__))
            adapter = os.path.join(script_dir, "tencent_to_aliyun_adapter.js")
            if os.path.exists(adapter):
                subprocess.run(['node', adapter, 'tencent_asr_result.json'], check=True)
                print("   已保存: aliyun_funasr_transcription.json (兼容格式)")
            return
        elif status == 3:
            print(f"\n❌ 转录失败")
            print(json.dumps(qr, ensure_ascii=False, indent=2))
            sys.exit(1)
        else:
            if (attempt + 1) % 12 == 0:
                print(f"   处理中... ({(attempt+1)*5}秒)")
            else:
                print(".", end="", flush=True)

    print("\n❌ 超时")
    sys.exit(1)

if __name__ == "__main__":
    main()
