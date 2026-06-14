# 免費生圖模組 (image_generator.py)
import os
import sys
import json
import time
import urllib.parse
import requests
from typing import Dict, Any

# 關閉 urllib3 ssl 警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 解決 Windows UTF-8 輸出問題
import builtins

def safe_print(*args, **kwargs):
    try:
        builtins.print(*args, **kwargs)
    except UnicodeEncodeError:
        try:
            encoding = sys.stdout.encoding or "utf-8"
            new_args = []
            for arg in args:
                if isinstance(arg, str):
                    new_args.append(arg.encode(encoding, errors="replace").decode(encoding))
                else:
                    new_args.append(arg)
            builtins.print(*new_args, **kwargs)
        except Exception:
            pass

print = safe_print

class FreeImageGenerator:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.ollama_url = self.config.get("ollama", {}).get("api_base", "http://localhost:11434")
        self.default_model = self.config.get("ollama", {}).get("model", "qwen2.5-coder:1.5b")

    def _load_config(self, filepath: str) -> Dict[str, Any]:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except Exception:
                    pass
        return {}

    def _http_post_with_fallback(self, url: str, headers: Dict[str, str], json_data: Dict[str, Any]) -> tuple[int, str]:
        """
        支援 python requests (首選) 與 curl command (備案) 的 HTTP POST。
        """
        try:
            res = requests.post(url, headers=headers, json=json_data, timeout=12, verify=False)
            return res.status_code, res.text
        except Exception as e:
            print(f"  [!] Python requests 請求失敗 ({e})，自動降級切換至本機 curl...")
            try:
                import subprocess
                cmd = ["curl", "-s", "-X", "POST"]
                for k, v in headers.items():
                    cmd.extend(["-H", f"{k}: {v}"])
                cmd.extend(["-H", "Content-Type: application/json"])
                cmd.extend(["-d", json.dumps(json_data)])
                cmd.append(url)
                
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                status_code = 202 if "id" in result.stdout else 200
                return status_code, result.stdout
            except Exception as curl_err:
                print(f"  [-] curl 備案執行失敗: {curl_err}")
                return 500, ""

    def _http_get_with_fallback(self, url: str, headers: Dict[str, str] = None, is_binary: bool = False) -> tuple[int, bytes, str]:
        """
        支援 python requests (首選) 與 curl command (備案) 的 HTTP GET。
        """
        try:
            res = requests.get(url, headers=headers, timeout=12, verify=False)
            return res.status_code, res.content, res.text
        except Exception as e:
            print(f"  [!] Python requests 請求失敗 ({e})，自動降級切換至本機 curl...")
            try:
                import subprocess
                cmd = ["curl", "-s"]
                if headers:
                    for k, v in headers.items():
                        cmd.extend(["-H", f"{k}: {v}"])
                cmd.append(url)
                
                result = subprocess.run(cmd, capture_output=True, check=True)
                text_content = ""
                if not is_binary:
                    try:
                        text_content = result.stdout.decode("utf-8", errors="replace")
                    except:
                        pass
                return 200, result.stdout, text_content
            except Exception as curl_err:
                print(f"  [-] curl 備案執行失敗: {curl_err}")
                return 500, b"", ""

    def translate_to_english_prompt(self, chinese_term: str) -> str:
        """
        利用本地 Ollama 將中文詞彙翻譯為適合生圖的簡單英文單字或片語。
        如果 Ollama 未啟動或失敗，則直接回傳中文詞彙。
        """
        try:
            # 檢查 Ollama 是否可用
            res = requests.get(f"{self.ollama_url}/api/tags", timeout=2)
            if res.status_code != 200:
                return chinese_term
            
            # 取得可用模型列表
            models_data = res.json()
            available_models = [m["name"] for m in models_data.get("models", [])]
            if not available_models:
                return chinese_term
            
            # 選擇模型，若設定的模型不在本地，使用第一個可用模型
            model_to_use = self.default_model
            if model_to_use not in available_models and f"{model_to_use}:latest" not in available_models:
                model_to_use = available_models[0]
            
            # 發送翻譯 Prompt
            system_prompt = (
                "You are a translator. Translate the Chinese term into a simple, concrete English noun or phrase "
                "suitable for generating a clean educational illustration. "
                "Output ONLY the English translation, no punctuation, no quotes, no extra explanation."
            )
            
            payload = {
                "model": model_to_use,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Chinese term: {chinese_term}"}
                ],
                "stream": False,
                "options": {
                    "temperature": 0.1
                }
            }
            
            chat_res = requests.post(f"{self.ollama_url}/api/chat", json=payload, timeout=5)
            if chat_res.status_code == 200:
                result = chat_res.json()
                english_translation = result.get("message", {}).get("content", "").strip()
                if english_translation:
                    # 去除多餘的換行或引號
                    english_translation = english_translation.replace('"', '').replace("'", "").strip()
                    print(f"  [+] Ollama 翻譯 「{chinese_term}」 -> 「{english_translation}」")
                    return english_translation
        except Exception as e:
            # 優雅降級，直接回傳原詞彙
            pass
        
        return chinese_term

    def generate_image(self, term: str, output_path: str, width: int = 512, height: int = 512) -> bool:
        """
        利用 AI Horde (免費、免 Key 匿名 API) 下載詞彙插圖。
        會先嘗試使用 Ollama 將 term 翻譯成英文，若失敗則直送 term。
        """
        try:
            print(f"[*] 嘗試為 「{term}」 生成插圖 (使用 AI Horde 免費匿名 API)...")
            
            # 1. 嘗試翻譯為英文
            english_term = self.translate_to_english_prompt(term)
            
            # 2. 組合適合教學插圖的 Prompt
            prompt = f"A clear photo of {english_term}, educational style, white background, no text"
            
            # 3. 呼叫 AI Horde 提交任務 (帶有 curl 降級備案)
            url_submit = "https://aihorde.net/api/v2/generate/async"
            headers = {
                "apikey": "0000000000",
                "Client-Agent": "taigi-teaching-agent:1.0:github"
            }
            payload = {
                "prompt": prompt,
                "params": {
                    "n": 1,
                    "width": width,
                    "height": height,
                    "steps": 15
                }
            }
            
            status_code, response_text = self._http_post_with_fallback(url_submit, headers, payload)
            if status_code != 202 or not response_text:
                print(f"  [-] AI Horde 任務提交失敗: HTTP {status_code}")
                return False
                
            try:
                task_id = json.loads(response_text).get("id")
            except:
                task_id = None
                
            if not task_id:
                print("  [-] 任務提交失敗，未取得 task_id。")
                return False
                
            print(f"  [+] 任務已提交，ID: {task_id}，正在排隊等候生圖...")
            
            # 4. Polling 等待結果 (最多等待 45 秒)
            max_wait = 45
            wait_interval = 3
            elapsed = 0
            
            while elapsed < max_wait:
                time.sleep(wait_interval)
                elapsed += wait_interval
                
                # 檢查進度
                url_check = f"https://aihorde.net/api/v2/generate/check/{task_id}"
                check_status, _, check_text = self._http_get_with_fallback(url_check, headers)
                if check_status == 200 and check_text:
                    try:
                        status = json.loads(check_text)
                    except:
                        status = {}
                    if status.get("done") is True:
                        print("  [+] 圖片生成完成！正在下載...")
                        break
                    elif status.get("faulted") is True:
                        print("  [-] 圖片生成失敗 (AI Horde worker 故障)")
                        return False
                    else:
                        q_pos = status.get("queue_position", "unknown")
                        print(f"  [*] 排隊中... 隊伍位置: {q_pos}，已等待 {elapsed}s")
                else:
                    print(f"  [-] 檢查狀態時發生 HTTP 錯誤: {check_status}")
            else:
                print(f"  [-] 生圖超時 (超過 {max_wait}s)")
                return False
                
            # 5. 取得圖片下載網址並下載
            url_status = f"https://aihorde.net/api/v2/generate/status/{task_id}"
            status_code, _, status_text = self._http_get_with_fallback(url_status, headers)
            if status_code == 200 and status_text:
                try:
                    result = json.loads(status_text)
                except:
                    result = {}
                generations = result.get("generations", [])
                if generations:
                    img_url = generations[0].get("img") or generations[0].get("url")
                    if img_url:
                        # 下載圖片 (以 binary 模式)
                        img_status, img_content, _ = self._http_get_with_fallback(img_url, is_binary=True)
                        if img_status == 200 and img_content:
                            os.makedirs(os.path.dirname(output_path), exist_ok=True)
                            with open(output_path, "wb") as f:
                                f.write(img_content)
                            print(f"  [+] 成功儲存生圖至: {output_path}")
                            return True
            
            print("  [-] 無法取得圖片下載網址。")
            return False
        except Exception as e:
            print(f"  [-] 生圖時發生異常: {str(e)}")
            return False

if __name__ == "__main__":
    # 簡單的獨立測試
    gen = FreeImageGenerator()
    test_term = "蘋果"
    out = "output/test_apple.jpg"
    success = gen.generate_image(test_term, out)
    if success:
        print(f"生圖測試成功，檔案已存至 {out}")
    else:
        print("生圖測試失敗")
