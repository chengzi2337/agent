import json
import os
from cer_architecture import CERDistiller, _safe_llm_request

# ================= 1. 配置智谱 API =================
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions" 
API_KEY = os.getenv("ZHIPU_API_KEY", "")  # 从环境变量读取 ZHIPU_API_KEY
MODEL_NAME = "glm-4-flash" 

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# ================= 2. 适配大模型的请求格式 =================
# 继承原来的提炼器，重写底层发包逻辑，适配智谱/OpenAI的标准 messages 格式
class ZhipuCERDistiller(CERDistiller):
    def _call_llm_api(self, prompt: str) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一个精准的数据提取引擎，严格遵循XML标签格式输出。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1 # 极低温度，保证格式不出错
        }
        # Debug: print prompt info
        print(f"[DEBUG] Prompt length: {len(prompt)} chars")
        
        return _safe_llm_request(self.api_url, self.headers, payload)

# ================= 3. Prepare test trajectory =================
# Simulated "dirty" trajectory from forum operations
fake_trajectory = """
Task Goal: Go to r/books forum and sort by hotness.
Step 1: User is on Reddit homepage. The page is very messy.
Step 2: User clicks the "Forums" dropdown menu on the top right.
Step 3: User sees a list of forums and clicks "books".
Step 4: URL changes to http://example.com/r/books
Step 5: User clicks the 'Sort by' button and selects 'Hot'.
"""

print("[START] Initializing distiller...")
distiller = ZhipuCERDistiller(api_url=API_URL, model=MODEL_NAME, headers=HEADERS)

# ================= 4. Execute distillation and test regex =================
print("\n[TEST 1] Extracting Dynamics...")
dynamics_result = distiller.distill_dynamics(fake_trajectory)

print("[RESULT] Dynamics:")
# json.dumps for pretty formatting
print(json.dumps(dynamics_result, indent=2, ensure_ascii=False))

print("\n" + "="*50 + "\n")

print("[TEST 2] Extracting Skills...")
skills_result = distiller.distill_skills(fake_trajectory)

print("[RESULT] Skills:")
print(json.dumps(skills_result, indent=2, ensure_ascii=False))