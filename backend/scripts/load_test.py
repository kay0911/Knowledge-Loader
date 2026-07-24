import asyncio
import time
import json
import statistics
import urllib.request
import urllib.error
import argparse
import sys
import os
from concurrent.futures import ThreadPoolExecutor

# Force UTF-8 encoding for Windows stdout
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Sample domain queries for RAG benchmark
SAMPLE_QUESTIONS = [
    "Mức lương kỹ sư dữ liệu là bao nhiêu?",
    "Thời gian bảo hành của xe điện VF9 là mấy năm?",
    "Chương V quy định hình thức kỷ luật sa thải thế nào?",
    "Yêu cầu kinh nghiệm tuyển dụng vị trí Python Developer?",
    "CBNV vi phạm trang phục quá 3 lần/tháng bị xử lý thế nào?"
]

def send_chat_request(target_url, question):
    start_time = time.time()
    payload = json.dumps({"question": question}).encode("utf-8")
    req = urllib.request.Request(
        target_url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read()
            elapsed_ms = (time.time() - start_time) * 1000
            return True, elapsed_ms, response.status
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return False, elapsed_ms, e.code
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        return False, elapsed_ms, 500

def run_load_test(target_url, concurrent_users, total_requests):
    print(f"============================================================")
    print(f"🚀 KÍCH HOẠT LOAD TEST HỆ THỐNG RAG BACKEND")
    print(f"   Target URL: {target_url}")
    print(f"   Số người dùng đồng thời (Concurrent Users): {concurrent_users}")
    print(f"   Tổng số câu hỏi (Total Requests): {total_requests}")
    print(f"============================================================\n")

    requests_per_user = total_requests // concurrent_users
    tasks = []
    
    start_total_time = time.time()
    
    results = []
    with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
        futures = []
        for i in range(total_requests):
            q = SAMPLE_QUESTIONS[i % len(SAMPLE_QUESTIONS)]
            futures.append(executor.submit(send_chat_request, target_url, q))
            
        for future in futures:
            results.append(future.result())
            
    total_duration_sec = time.time() - start_total_time

    # Compute statistics
    successes = [r for r in results if r[0]]
    failures = [r for r in results if not r[0]]
    latencies = [r[1] for r in results]
    
    success_rate = (len(successes) / len(results)) * 100 if results else 0
    rps = len(results) / total_duration_sec if total_duration_sec > 0 else 0
    
    latencies.sort()
    avg_latency = statistics.mean(latencies) if latencies else 0
    min_latency = min(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0
    p95_latency = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99_latency = latencies[int(len(latencies) * 0.99)] if latencies else 0

    print("📊 BÁO CÁO KẾT QUẢ ĐO ĐỘ CHỊU TẢI (RAG BENCHMARK REPORT):")
    print(f"------------------------------------------------------------")
    print(f"⏱️ Tổng thời gian thực thi : {total_duration_sec:.2f} giây")
    print(f"✅ Số câu hỏi thành công   : {len(successes)} / {len(results)} ({success_rate:.1f}%)")
    print(f"❌ Số câu hỏi thất bại    : {len(failures)}")
    print(f"🚀 Tốc độ xử lý (RPS)       : {rps:.2f} câu/giây (Requests Per Second)")
    print(f"------------------------------------------------------------")
    print(f"⚡ Thời gian phản hồi trung bình (Avg Latency) : {avg_latency:.1f} ms")
    print(f"⚡ Nhanh nhất (Min Latency)                   : {min_latency:.1f} ms")
    print(f"⚡ Chậm nhất (Max Latency)                   : {max_latency:.1f} ms")
    print(f"🎯 Phân vị 95% (P95 Latency)                 : {p95_latency:.1f} ms")
    print(f"🎯 Phân vị 99% (P99 Latency)                 : {p99_latency:.1f} ms")
    print(f"============================================================\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Test Script for RAG Backend")
    parser.add_argument("--url", type=str, default="http://localhost:8000/api/chat/", help="Target API endpoint")
    parser.add_argument("--users", type=int, default=20, help="Number of concurrent users")
    parser.add_argument("--requests", type=int, default=100, help="Total number of requests to send")
    
    args = parser.parse_args()
    run_load_test(args.url, args.users, args.requests)
