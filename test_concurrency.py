import asyncio
import time
import httpx
import numpy as np

# 服务地址
API_URL = "http://192.168.10.206:8008/tts"

# 测试配置
CONCURRENCY_LEVEL = 5      # 并发请求数
TOTAL_REQUESTS = 10        # 总请求数
TEST_TEXT = "这是一个并发测试，用于评估 F5-TTS 服务在高负载下的响应能力和稳定性。"

async def send_request(client, req_id):
    payload = {"gen_text": f"{TEST_TEXT} [ID:{req_id}]"}
    start_time = time.time()
    try:
        resp = await client.post(API_URL, json=payload, timeout=120.0)
        latency = time.time() - start_time
        if resp.status_code == 200:
            result = resp.json()
            return {
                "success": True,
                "latency": latency,
                "duration_sec": result["duration_sec"],
                "rtf": latency / result["duration_sec"]
            }
        else:
            return {"success": False, "code": resp.status_code, "latency": latency}
    except Exception as e:
        return {"success": False, "error": str(e), "latency": time.time() - start_time}

async def run_test():
    print(f"开始并发测试: 并发数={CONCURRENCY_LEVEL}, 总请求数={TOTAL_REQUESTS}")
    print(f"目标地址: {API_URL}")
    print("-" * 50)

    async with httpx.AsyncClient() as client:
        tasks = []
        # 分批次执行，或者一次性生成所有任务（受 CONCURRENCY_LEVEL 限制通常需要 semaphore，但这里简单起见直接并发）
        # 为了更真实的模拟并发，我们使用 Semaphore 控制同时进行的任务数
        sem = asyncio.Semaphore(CONCURRENCY_LEVEL)
        
        async def bounded_request(req_id):
            async with sem:
                print(f"-> 发送请求 {req_id}...")
                res = await send_request(client, req_id)
                print(f"<- 请求 {req_id} 完成: {'成功' if res['success'] else '失败'} (耗时 {res.get('latency', 0):.2f}s)")
                return res

        start_total = time.time()
        results = await asyncio.gather(*(bounded_request(i) for i in range(TOTAL_REQUESTS)))
        total_time = time.time() - start_total

    # 统计结果
    success_results = [r for r in results if r["success"]]
    failed_count = len(results) - len(success_results)
    
    if not success_results:
        print("\n所有请求均失败！")
        return

    latencies = [r["latency"] for r in success_results]
    rtfs = [r["rtf"] for r in success_results]
    durations = [r["duration_sec"] for r in success_results]

    print("\n" + "=" * 20 + " 测试报告 " + "=" * 20)
    print(f"总耗时      : {total_time:.2f} 秒")
    print(f"成功/总数    : {len(success_results)}/{TOTAL_REQUESTS}")
    print(f"吞吐量 (TPS) : {len(success_results) / total_time:.2f} req/s")
    print("-" * 50)
    print(f"平均延迟    : {np.mean(latencies):.2f} 秒")
    print(f"P95 延迟    : {np.percentile(latencies, 95):.2f} 秒")
    print(f"最大延迟    : {np.max(latencies):.2f} 秒")
    print("-" * 50)
    print(f"平均音频时长: {np.mean(durations):.2f} 秒")
    print(f"平均 RTF    : {np.mean(rtfs):.4f}")
    print(f"P95 RTF     : {np.percentile(rtfs, 95):.4f}")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(run_test())
