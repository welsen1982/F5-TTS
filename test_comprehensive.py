
import os
import time
import requests
import json
import base64

# Configuration
API_URL = "http://127.0.0.1:8008"
API_KEY = os.environ.get("F5_TTS_API_KEY", "b3766c7969fb8ac818c579978899bb6a6fbedae99724283c8787d2fb204a4466")
HEADERS = {"X-API-Key": API_KEY}

def run_test(name, endpoint, payload=None, files=None, method="POST", expect_status=200):
    print(f"\n[{name}] Testing {endpoint} ...")
    url = f"{API_URL}{endpoint}"
    start_time = time.time()
    
    try:
        if method == "GET":
            response = requests.get(url, headers=HEADERS)
        else:
            if files:
                # When using files, requests handles content-type
                response = requests.post(url, headers=HEADERS, data=payload, files=files)
            else:
                response = requests.post(url, headers=HEADERS, json=payload)
        
        latency = time.time() - start_time
        
        if response.status_code == expect_status:
            print(f"✅ Passed (Status: {response.status_code}, Latency: {latency:.2f}s)")
            try:
                data = response.json()
                # Print summary if available
                if "duration_sec" in data:
                    print(f"   Audio Duration: {data['duration_sec']:.2f}s")
                if "results" in data:
                    print(f"   Batch Results: {len(data['results'])} items")
                return data
            except:
                return response.text
        else:
            print(f"❌ Failed (Status: {response.status_code})")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def main():
    print(f"Target Server: {API_URL}")
    print(f"Using API Key: {API_KEY[:6]}******")

    # 1. System Health
    run_test("Health Check", "/health", method="GET")
    
    # 2. Version Info
    run_test("Version Info", "/version", method="GET")
    
    # 3. Text Normalization Test (Mixed Content)
    # Testing: Date, Number, English, Punctuation
    text_cases = [
        "F5-TTS在2024年表现出色。",
        "今天的气温是-5°C。",
        "请拨打13800138000联系。",
        "价格是$20.5，含50%折扣。"
    ]
    
    print(f"\n[Normalization Test] Running {len(text_cases)} cases...")
    
    # Use Batch API for efficiency
    batch_payload = [
        {"gen_text": text} for text in text_cases
    ]
    
    result = run_test("Batch TTS (Normalization)", "/tts/batch", payload=batch_payload)
    
    if result and "results" in result:
        for i, item in enumerate(result["results"]):
            audio_data = base64.b64decode(item["audio_base64"])
            audio_len = len(audio_data)
            output_file = f"test_norm_case_{i+1}.wav"
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"   Case {i+1}: '{text_cases[i]}' -> Saved to {output_file} ({audio_len/1024:.1f}KB)")

    # 4. Long Text Performance
    long_text = (
        "随着人工智能技术的飞速发展，语音合成已经深入到我们生活的方方面面。"
        "F5-TTS 作为一个前沿的流匹配模型，不仅能够生成自然流畅的语音，"
        "还能精确捕捉参考音频的情感和韵律，实现零样本的声音克隆。"
    )
    result = run_test("Long Text Perf", "/tts", payload={"gen_text": long_text})
    if result and "audio_base64" in result:
        audio_data = base64.b64decode(result["audio_base64"])
        output_file = "test_long_text.wav"
        with open(output_file, "wb") as f:
            f.write(audio_data)
        print(f"   Saved Long Text Audio to {output_file}")

    # 5. Security Test (Invalid Key)
    print("\n[Security Test] Sending request with invalid key...")
    bad_headers = {"X-API-Key": "wrong-key"}
    try:
        resp = requests.post(f"{API_URL}/warmup", headers=bad_headers)
        if resp.status_code == 403:
             print(f"✅ Passed (Status: 403 Forbidden)")
        else:
             print(f"❌ Failed (Expected 403, got {resp.status_code})")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
