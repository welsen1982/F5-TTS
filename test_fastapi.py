import base64
import json
import requests
import os
import time

# 服务地址
API_URL = "http://127.0.0.1:8008/tts"

# 测试文本：包含中文、英文和数字，长度适中
GEN_TEXT = (
    "F5-TTS 模型测试。这里是一段包含多语言的文本。"
    "The F5-TTS system allows for high-quality speech generation. "
    "当前测试编号为 2025-02-12，系统运行在 NVIDIA V100 GPU 上。"
    "Let's see how it performs with mixed content."
)

OUTPUT_FILE = "test_output_no_ref.wav"

def test_tts():
    print(f"正在发送请求到 {API_URL} ...")
    print(f"生成文本: {GEN_TEXT}")
    print("注：将使用服务器默认配置的参考音频和参考文本")

    try:
        # 准备请求参数 (直接发送 JSON)
        payload = {
            "gen_text": GEN_TEXT,
            # 不指定 ref_text 和 ref_audio，让服务器使用默认值
            "params": {
                "nfe_step": 32,
                "cfg_strength": 2.0,
                "speed": 1.0
            }
        }
        
        start_time = time.time()
        
        # 发送 POST 请求 (application/json)
        response = requests.post(API_URL, json=payload)
        
        # 检查响应
        if response.status_code == 200:
            result = response.json()
            
            # 解码音频
            audio_data = base64.b64decode(result["audio_base64"])
            
            # 保存文件
            with open(OUTPUT_FILE, "wb") as f:
                f.write(audio_data)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            print(f"\n生成成功！")
            print(f"总耗时: {total_time:.2f} 秒")
            print(f"推理耗时 (服务端): {result.get('duration_sec', 0):.2f} 秒")
            print(f"采样率: {result.get('sample_rate')} Hz")
            print(f"已保存到: {os.path.abspath(OUTPUT_FILE)}")
            
            # 打印其他信息
            if "info" in result:
                print("\n返回信息:")
                print(json.dumps(result["info"], indent=2, ensure_ascii=False))
            
        else:
            print(f"\n请求失败 (Status {response.status_code}):")
            print(response.text)
            
    except Exception as e:
        print(f"\n发生错误: {str(e)}")

if __name__ == "__main__":
    test_tts()
