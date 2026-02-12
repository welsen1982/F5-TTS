import time
import requests
import json
import base64
import os

# 服务地址
API_URL = "http://192.168.10.206:8008/tts"
API_KEY = os.environ.get("F5_TTS_API_KEY", "b3766c7969fb8ac818c579978899bb6a6fbedae99724283c8787d2fb204a4466")

# 约 1 分钟阅读量的中文文本（约 200-250 字）
# 正常语速约为 200-250 字/分钟
LONG_TEXT = (
    "随着人工智能技术的飞速发展，语音合成已经深入到我们生活的方方面面。"
    "从智能手机的语音助手，到车载导航的温馨提示，再到有声读物的精彩演绎，"
    "高质量的语音合成技术正在改变着人机交互的方式。"
    "F5-TTS 作为一个前沿的流匹配模型，不仅能够生成自然流畅的语音，"
    "还能精确捕捉参考音频的情感和韵律，实现零样本的声音克隆。"
    "今天我们进行的这项测试，旨在评估该系统在生成长段落文本时的性能表现，"
    "特别是其生成速度与实时率。实时率是衡量语音合成系统效率的关键指标，"
    "它定义为生成音频耗时与音频实际时长的比值。"
    "如果实时率小于 1，说明生成速度快于播放速度，这对于实时交互应用至关重要。"
    "让我们拭目以待，看看 F5-TTS 在处理这段约一分钟的文本时，究竟表现如何。"
)

def test_performance():
    print(f"文本长度: {len(LONG_TEXT)} 字")
    print(f"正在发送请求到 {API_URL} ...")
    
    # 最简参数调用，利用服务端的默认参考音频与文本
    payload = {
        "gen_text": LONG_TEXT
    }
    
    start_time = time.time()
    
    try:
        # 使用 JSON 格式发送（Content-Type: application/json）
        # 注意：这里直接传 json 参数，requests 会自动设置 header
        headers = {"X-API-Key": API_KEY}
        print(f"使用 API Key: {API_KEY[:8]}...")
        response = requests.post(API_URL, json=payload, headers=headers)
        
        request_latency = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            
            # 解析结果
            duration_sec = result["duration_sec"]
            sample_rate = result["sample_rate"]
            audio_data = base64.b64decode(result["audio_base64"])
            audio_size_mb = len(audio_data) / (1024 * 1024)
            
            # 计算 RTF (Real Time Factor) = 生成耗时 / 音频时长
            rtf = request_latency / duration_sec
            
            print("\n---------------- 测试结果 ----------------")
            print(f"API 响应状态: 成功 (200 OK)")
            print(f"生成音频时长: {duration_sec:.2f} 秒")
            print(f"总请求耗时  : {request_latency:.2f} 秒")
            print(f"实时率 (RTF): {rtf:.4f} (越小越快)")
            print(f"生成速度    : {1/rtf:.2f} x 实时")
            print(f"音频大小    : {audio_size_mb:.2f} MB")
            print(f"采样率      : {sample_rate} Hz")
            
            # 保存文件
            output_file = "perf_test_1min.wav"
            with open(output_file, "wb") as f:
                f.write(audio_data)
            print(f"音频已保存  : {output_file}")
            
        else:
            print(f"\n请求失败 (Status {response.status_code}):")
            print(response.text)
            
    except Exception as e:
        print(f"\n发生异常: {str(e)}")

if __name__ == "__main__":
    test_performance()
