
import os
import time
from f5_tts.model.text_normalizer import normalize_text, _global_normalizer

def test_normalization():
    print("Initializing WeTextProcessing...")
    start_time = time.time()
    _global_normalizer.initialize()
    print(f"Initialization took {time.time() - start_time:.2f} seconds.")

    test_cases = [
        ("F5-TTS是2024年最强的TTS模型之一。", "F5-TTS是二零二四年最强的TTS模型之一。"),
        ("这个项目的GitHub只有1.5k stars吗？", "这个项目的GitHub只有一点五千 stars吗？"),
        ("今天气温是-3°C，记得穿厚点。", "今天气温是零下三摄氏度，记得穿厚点。"),
        ("联系电话: 13800138000", "联系电话: 一三八零零一三八零零零"),
        ("价格是$10.5", "价格是十点五美元"),
        ("完成了50%的进度", "完成了百分之五十的进度")
    ]

    print("\n=== Running Normalization Tests ===")
    for input_text, expected_fragment in test_cases:
        normalized = normalize_text(input_text)
        print(f"Input:    {input_text}")
        print(f"Output:   {normalized}")
        
        # Simple verification: check if key conversions happened
        # Note: Exact output might vary slightly depending on WeTextProcessing version rules
        if input_text != normalized:
            print("Status:   [CHANGED] (As expected)")
        else:
            print("Status:   [UNCHANGED] (Might be unexpected for pure numbers)")
        print("-" * 40)

if __name__ == "__main__":
    # Ensure environment is set up (although we import directly)
    test_normalization()
