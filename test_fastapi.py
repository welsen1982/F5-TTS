import base64
import json
import requests
import os
from pathlib import Path

# 服务地址
API_URL = "http://192.168.10.206:8008/tts"

# 样例数据
REF_AUDIO_PATH = "/home/zju/projects/F5-TTS/data/ref_audio/aliyuntts-4sec.wav"
REF_TEXT = "沈先生，你好，我是客服助手小黄，很高兴为您服务"
GEN_TEXT = "你好，今天天气不错，一起打球吧"
OUTPUT_FILE = "test_output.wav"

def test_tts():
    # 检查参考音频是否存在
    if not os.path.exists(REF_AUDIO_PATH):
        print(f"Error: 参考音频文件不存在: {REF_AUDIO_PATH}")
        # 如果不存在，创建一个假的音频文件用于测试（实际场景请确保文件存在）
        # 这里仅作演示，不实际创建假文件，直接返回
        return

    print(f"正在发送请求到 {API_URL} ...")
    print(f"参考音频: {REF_AUDIO_PATH}")
    print(f"参考文本: {REF_TEXT}")
    print(f"生成文本: {GEN_TEXT}")

    try:
        # 准备请求参数
        # 注意：使用 multipart/form-data 上传文件，参数作为 json 字符串放在 request 字段中
        params = {
            "gen_text": GEN_TEXT,
            "ref_text": REF_TEXT,
            "params": {
                "nfe_step": 32,
                "cfg_strength": 2.0,
                "speed": 1.0
            }
        }
        
        files = {
            "ref_audio": (Path(REF_AUDIO_PATH).name, open(REF_AUDIO_PATH, "rb"), "audio/wav")
        }
        
        # 将参数序列化为 json 字符串
        data = {
            "request": json.dumps(params)
        }

        # 发送请求
        response = requests.post(API_URL, files=files, data=data)
        
        # 检查响应
        if response.status_code == 200:
            result = response.json()
            
            # 解码音频
            audio_data = base64.b64decode(result["audio_base64"])
            
            # 保存文件
            with open(OUTPUT_FILE, "wb") as f:
                f.write(audio_data)
            
            print(f"\n生成成功！")
            print(f"耗时: {result['duration_sec']:.2f} 秒")
            print(f"采样率: {result['sample_rate']} Hz")
            print(f"已保存到: {os.path.abspath(OUTPUT_FILE)}")
            
            # 打印其他信息
            print("\n返回信息:")
            print(json.dumps(result["info"], indent=2, ensure_ascii=False))
            
        else:
            print(f"\n请求失败 (Status {response.status_code}):")
            print(response.text)
            
    except Exception as e:
        print(f"\n发生错误: {str(e)}")
    finally:
        # 关闭文件句柄
        if 'files' in locals():
            files["ref_audio"][1].close()

if __name__ == "__main__":
    test_tts()
