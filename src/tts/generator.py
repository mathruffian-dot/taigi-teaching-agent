# 台語語音合成與下載模組 (generator.py)
import os
import sys
import json
import struct
import base64
import urllib.parse
import requests
from typing import Dict, Any

# 關閉 urllib3 在 verify=False 時產生的 InsecureRequestWarning 警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import safe_print
print = safe_print

class TaigiTTS:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.tts_config = self.config.get("tts", {})
        self.provider = self.tts_config.get("provider", "dummy")
        self.api_key = self.tts_config.get("api_key", "")

    def _load_config(self, filepath: str) -> Dict[str, Any]:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except Exception:
                    pass
        return {}

    def fetch_vocab_audio(self, hanji: str, output_path: str) -> bool:
        """
        向萌典 API 查詢詞條，取得語音 ID 並下載對應教育部《臺灣台語常用詞辭典》官方 OGG 音訊檔。
        """
        try:
            print(f"[*] 嘗試為詞彙 「{hanji}」 下載萌典官方發音...")
            encoded_hanji = urllib.parse.quote(hanji)
            api_url = f"https://www.moedict.tw/t/{encoded_hanji}.json"
            
            # 查詢萌典 JSON
            res = requests.get(api_url, verify=False, timeout=5)
            if res.status_code != 200:
                print(f"  [-] 萌典 API 查詢失敗: HTTP {res.status_code}")
                return False
                
            data = res.json()
            # 尋找音標語音 ID
            audio_id = None
            if "h" in data and len(data["h"]) > 0:
                audio_id = data["h"][0].get("_")
                
            if not audio_id:
                print(f"  [-] 無法在萌典中找到詞彙 「{hanji}」 的語音 ID。")
                return False
                
            # 依語言類別處理語音 ID 的 padding (台語 /t/ 需要補 0 到 5 碼)
            # 例如: "8965" -> "08965"
            normalized_audio_id = str(audio_id).strip()
            if normalized_audio_id.isdigit() and len(normalized_audio_id) < 5:
                normalized_audio_id = normalized_audio_id.zfill(5)

            # 台語音檔 CDN: https://1763c5ee9859e0316ed6-db85b55a6a3fbe33f09b9245992383bd.ssl.cf1.rackcdn.com
            cdn_base = "https://1763c5ee9859e0316ed6-db85b55a6a3fbe33f09b9245992383bd.ssl.cf1.rackcdn.com"
            ogg_url = f"{cdn_base}/{normalized_audio_id}.ogg"
            ogg_res = requests.get(ogg_url, verify=False, timeout=10)
            if ogg_res.status_code != 200:
                print(f"  [-] 音訊檔下載失敗: HTTP {ogg_res.status_code}")
                return False
                
            # 確保目錄存在並寫入
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(ogg_res.content)
            print(f"  [+] 成功儲存詞彙 「{hanji}」 語音檔至: {output_path}")
            return True
            
        except Exception as e:
            print(f"  [-] 下載 「{hanji}」 音訊時發生異常: {str(e)}")
            return False

    def synthesize_sentence(self, text: str, output_path: str) -> bool:
        """
        將自訂句子進行台語語音合成並存檔。支援 yating 與 dummy 模式。
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        if self.provider == "yating" and self.api_key:
            return self._synthesize_yating(text, output_path)
        else:
            if self.provider == "yating":
                print("  [!] 警告: 已設定 provider 為 yating 但未提供 api_key。自動降級為 dummy 模式。")
            return self._synthesize_dummy(text, output_path)

    def _synthesize_yating(self, text: str, output_path: str) -> bool:
        """
        呼叫雅婷智慧 (Yating) TTS API 合成語音。
        """
        try:
            print(f"[*] 正在呼叫雅婷 TTS 合成語音：「{text}」...")
            
            # 使用雅婷 TTS v2 短語音合成 API (支援 tai_female_1 模型)
            url = "https://tts.api.yating.tw/v2/speeches/short"
            headers = {
                "key": self.api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "text": text,
                "speed": 1.0,
                "pitch": 1.0,
                "energy": 1.0,
                "voice": "tai_female_1"
            }
            
            res = requests.post(url, json=payload, headers=headers, timeout=15)
            if res.status_code == 200:
                res_data = res.json()
                # 取得 base64 音訊資料並解碼
                audio_b64 = res_data.get("audioContent")
                if audio_b64:
                    audio_data = base64.b64decode(audio_b64)
                    with open(output_path, "wb") as f:
                        f.write(audio_data)
                    print(f"  [+] 成功合成語音並儲存至: {output_path}")
                    return True
                else:
                    print("  [-] 雅婷 API 回傳成功，但未包含 audioContent 欄位。")
                    return False
            else:
                print(f"  [-] 雅婷 API 呼叫失敗: HTTP {res.status_code} - {res.text}")
                return False
                
        except Exception as e:
            print(f"  [-] 雅婷 TTS 合成異常: {str(e)}")
            return False

    def _synthesize_dummy(self, text: str, output_path: str) -> bool:
        """
        Dummy 模式：使用 Python struct 標準庫生成 0.5 秒的靜音 WAV 檔作為佔位符。
        """
        try:
            print(f"[*] 執行 Dummy 語音生成佔位符：「{text}」...")
            # 規格: 單聲道、16-bit、8000Hz PCM、0.5秒靜音
            sample_rate = 8000
            num_samples = int(sample_rate * 0.5)
            data = b'\x00\x00' * num_samples
            
            num_channels = 1
            bits_per_sample = 16
            byte_rate = sample_rate * num_channels * bits_per_sample // 8
            block_align = num_channels * bits_per_sample // 8
            
            # 建立標準 WAV 檔頭
            header = struct.pack(
                '<4sI4s4sIHHIIHH4sI',
                b'RIFF',
                36 + len(data),
                b'WAVE',
                b'fmt ',
                16,              # Subchunk1Size
                1,               # AudioFormat (PCM)
                num_channels,
                sample_rate,
                byte_rate,
                block_align,
                bits_per_sample,
                b'data',
                len(data)
            )
            
            with open(output_path, "wb") as f:
                f.write(header + data)
            print(f"  [+] 已建立 Dummy 佔位音訊檔: {output_path}")
            return True
        except Exception as e:
            print(f"  [-] 建立 Dummy 佔位音訊檔失敗: {str(e)}")
            return False
