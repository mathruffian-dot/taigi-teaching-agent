# 台語語音辨識與評估模組 (generator.py)
import os
import sys
import json
import requests
from typing import Dict, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import safe_print
print = safe_print

class TaigiSTT:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.stt_config = self.config.get("stt", {})
        self.provider = self.stt_config.get("provider", "dummy")
        self.api_key = self.stt_config.get("api_key", "")
        self.api_url = self.stt_config.get("api_url", "https://api.openai.com/v1/audio/transcriptions")
        self.model = self.stt_config.get("model", "whisper-1")

    def _load_config(self, filepath: str) -> Dict[str, Any]:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except Exception:
                    pass
        return {}

    def speech_to_text(self, audio_path: str, target_text: str = "") -> str:
        """
        將音訊檔案轉換為文字。支援 dummy、openai 與 whisper 模式。
        """
        if not os.path.exists(audio_path):
            print(f"  [-] 找不到音訊檔案: {audio_path}")
            return ""

        if self.provider == "openai" and self.api_key:
            return self._stt_openai(audio_path)
        elif self.provider == "whisper":
            return self._stt_local_whisper(audio_path, target_text)
        else:
            return self._stt_dummy(audio_path, target_text)

    def _stt_openai(self, audio_path: str) -> str:
        """
        呼叫 OpenAI 或相容規格的 Whisper ASR API。
        """
        try:
            print(f"[*] 正在發送 ASR 請求 (OpenAI 規格) 處理音訊: {audio_path}...")
            headers = {
                "Authorization": f"Bearer {self.api_key}"
            }
            # 以二進位讀取並打包音訊檔案
            with open(audio_path, "rb") as f:
                files = {
                    "file": (os.path.basename(audio_path), f, "audio/wav")
                }
                data = {
                    "model": self.model,
                    "language": "zh"  # Whisper 辨識台語輸出漢字通常設為 zh
                }
                
                res = requests.post(self.api_url, headers=headers, files=files, data=data, timeout=30)
                
            if res.status_code == 200:
                res_json = res.json()
                text = res_json.get("text", "").strip()
                print(f"  [+] ASR 辨識成功: 「{text}」")
                return text
            else:
                print(f"  [-] ASR 呼叫失敗: HTTP {res.status_code} - {res.text}")
                return ""
        except Exception as e:
            print(f"  [-] ASR 呼叫發生異常: {str(e)}")
            return ""

    def _stt_local_whisper(self, audio_path: str, target_text: str = "") -> str:
        """
        本地使用 faster-whisper 引擎進行辨識 (若已安裝相依套件)。
        會自動透過 ffmpeg 轉換音訊為 16kHz mono WAV，以保證解碼相容性。
        """
        converted_path = None
        try:
            print(f"[*] 嘗試在本地使用 faster-whisper 辨識音訊: {audio_path}...")
            
            # 使用 ffmpeg 轉換為 16kHz mono WAV (Whisper 最佳格式)
            import subprocess
            import tempfile
            
            # 建立臨時 wav 檔案
            temp_dir = tempfile.gettempdir()
            converted_path = os.path.join(temp_dir, f"whisper_input_{os.urandom(8).hex()}.wav")
            
            # 轉換
            cmd = ["ffmpeg", "-y", "-i", audio_path, "-ar", "16000", "-ac", "1", converted_path]
            res_conv = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            
            # 若轉換成功，使用轉換後的檔案，否則使用原檔案
            input_to_whisper = converted_path if (res_conv.returncode == 0 and os.path.exists(converted_path)) else audio_path
            
            from faster_whisper import WhisperModel
            model_size = self.stt_config.get("local_model_size", "tiny") # 預設改用 tiny 提升本地 CPU 運算速度
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            
            segments, info = model.transcribe(input_to_whisper, beam_size=5, language="zh")
            text = "".join([segment.text for segment in segments]).strip()
            print(f"  [+] 本地 ASR 辨識成功: 「{text}」")
            return text
        except ImportError:
            print("  [!] 警告: 未安裝 faster-whisper。自動降級為 dummy 模式。")
            return self._stt_dummy(audio_path, target_text)
        except Exception as e:
            print(f"  [-] 本地 ASR 辨識異常: {str(e)}")
            return ""
        finally:
            # 清理臨時 wav 檔案
            if converted_path and os.path.exists(converted_path):
                try:
                    os.remove(converted_path)
                except:
                    pass

    def _stt_dummy(self, audio_path: str, target_text: str = "") -> str:
        """
        Dummy 模式：直接返回預期文字以供離線或開發階段測試。
        """
        print(f"[*] 執行 Dummy ASR 語音辨識佔位處理...")
        if target_text:
            return target_text
        return "菜市仔"
