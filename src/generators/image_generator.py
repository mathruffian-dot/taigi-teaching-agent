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

# 安全輸出至 Windows 控制台
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import safe_print
print = safe_print

class FreeImageGenerator:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config(config_path)
        self.ollama_url = self.config.get("ollama", {}).get("url", "http://localhost:11434")
        self.default_model = self.config.get("ollama", {}).get("model", "qwen2.5-coder:1.5b")
        self.image_config = self.config.get("image", {})
        self.max_wait_sec = int(self.image_config.get("max_wait_sec", 45))

    def _load_config(self, filepath: str) -> Dict[str, Any]:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8-sig") as f:
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

    def _fallback_image(self, term: str, output_path: str, width: int, height: int, reason: str = "") -> bool:
        """
        外部免費生圖服務排隊或失敗時，產生本機教學用插圖。
        這不是 AI 生圖，而是穩定的離線視覺 fallback，避免正式教材缺圖。
        """
        try:
            from PIL import Image, ImageDraw, ImageFont

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            img = Image.new("RGB", (width, height), "#f8f3e7")
            draw = ImageDraw.Draw(img)

            # 背景與框線
            draw.rectangle([(0, 0), (width, int(height * 0.42))], fill="#cfe8f3")
            draw.rectangle([(0, int(height * 0.42)), (width, height)], fill="#d8ead3")
            draw.rounded_rectangle(
                [(10, 10), (width - 10, height - 10)],
                radius=18,
                outline="#0b3c30",
                width=max(3, width // 120),
            )

            term_text = term or "教材插圖"
            if any(key in term_text for key in ("菜", "蔬", "有機", "田", "園", "種", "耕")):
                # 田畦
                ground_top = int(height * 0.52)
                for i in range(5):
                    y = ground_top + i * int(height * 0.08)
                    draw.line([(40, y), (width - 40, y + int(height * 0.04))], fill="#7a5c38", width=max(4, width // 90))
                # 葉菜
                cx, cy = width // 2, int(height * 0.45)
                stem = max(5, width // 80)
                draw.line([(cx, cy + 80), (cx, cy - 70)], fill="#2f6b3f", width=stem)
                leaf_w, leaf_h = int(width * 0.22), int(height * 0.16)
                for dx, dy, color in [
                    (-leaf_w // 2, -50, "#3c8f50"),
                    (leaf_w // 2, -25, "#4ca65d"),
                    (-leaf_w // 3, 20, "#5fb96b"),
                    (leaf_w // 3, 45, "#347a43"),
                ]:
                    draw.ellipse(
                        [(cx + dx - leaf_w // 2, cy + dy - leaf_h // 2), (cx + dx + leaf_w // 2, cy + dy + leaf_h // 2)],
                        fill=color,
                        outline="#1f4f2f",
                        width=2,
                    )
            else:
                # 通用教學圖卡
                center = (width // 2, height // 2)
                r = min(width, height) // 4
                draw.ellipse(
                    [(center[0] - r, center[1] - r), (center[0] + r, center[1] + r)],
                    fill="#f0c66a",
                    outline="#0b3c30",
                    width=max(3, width // 120),
                )
                draw.rectangle(
                    [(center[0] - r // 2, center[1] - r // 8), (center[0] + r // 2, center[1] + r // 8)],
                    fill="#0b3c30",
                )

            try:
                font_path = "C:/Windows/Fonts/msjh.ttc"
                title_font = ImageFont.truetype(font_path, max(22, width // 12))
                small_font = ImageFont.truetype(font_path, max(14, width // 28))
            except Exception:
                title_font = ImageFont.load_default()
                small_font = ImageFont.load_default()

            label = term_text[:10]
            box_top = int(height * 0.78)
            draw.rounded_rectangle(
                [(28, box_top), (width - 28, height - 28)],
                radius=14,
                fill="#ffffff",
                outline="#c8941f",
                width=2,
            )
            bbox = draw.textbbox((0, 0), label, font=title_font)
            text_w = bbox[2] - bbox[0]
            draw.text(((width - text_w) / 2, box_top + 12), label, font=title_font, fill="#0b3c30")
            note = "本機 fallback 插圖"
            if reason:
                note = note + "｜外部生圖未完成"
            note_bbox = draw.textbbox((0, 0), note, font=small_font)
            draw.text(((width - (note_bbox[2] - note_bbox[0])) / 2, height - 48), note, font=small_font, fill="#826252")

            save_kwargs = {}
            ext = os.path.splitext(output_path)[1].lower()
            if ext in (".jpg", ".jpeg"):
                save_kwargs["quality"] = 92
            img.save(output_path, **save_kwargs)
            print(f"  [+] 已產生本機 fallback 插圖: {output_path}")
            return True
        except Exception as e:
            print(f"  [-] 本機 fallback 插圖產生失敗: {e}")
            return False

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
                return self._fallback_image(term, output_path, width, height, "submit_failed")
                
            try:
                task_id = json.loads(response_text).get("id")
            except:
                task_id = None
                
            if not task_id:
                print("  [-] 任務提交失敗，未取得 task_id。")
                return self._fallback_image(term, output_path, width, height, "missing_task_id")
                
            print(f"  [+] 任務已提交，ID: {task_id}，正在排隊等候生圖...")
            
            # 4. Polling 等待結果 (最多等待 45 秒)
            max_wait = max(3, self.max_wait_sec)
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
                        return self._fallback_image(term, output_path, width, height, "worker_faulted")
                    else:
                        q_pos = status.get("queue_position", "unknown")
                        print(f"  [*] 排隊中... 隊伍位置: {q_pos}，已等待 {elapsed}s")
                else:
                    print(f"  [-] 檢查狀態時發生 HTTP 錯誤: {check_status}")
            else:
                print(f"  [-] 生圖超時 (超過 {max_wait}s)")
                return self._fallback_image(term, output_path, width, height, "timeout")
                
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
            return self._fallback_image(term, output_path, width, height, "missing_image_url")
        except Exception as e:
            print(f"  [-] 生圖時發生異常: {str(e)}")
            return self._fallback_image(term, output_path, width, height, "exception")

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
