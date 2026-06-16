# 台語語音合成與下載模組 (generator.py)
import os
import re
import sys
import json
import struct
import shutil
import base64
import tempfile
import subprocess
import urllib.parse
import requests
from typing import Dict, Any, Optional, List, Tuple

# 關閉 urllib3 在 verify=False 時產生的 InsecureRequestWarning 警告
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import safe_print
print = safe_print

# 萌典台語音檔 CDN
MOEDICT_CDN_BASE = "https://1763c5ee9859e0316ed6-db85b55a6a3fbe33f09b9245992383bd.ssl.cf1.rackcdn.com"


class TaigiTTS:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.tts_config = self.config.get("tts", {})
        self.provider = self.tts_config.get("provider", "dummy")
        self.api_key = self.tts_config.get("api_key", "")
        # 接音合成用：單詞官方音檔快取（記憶體 + 磁碟），避免重複查詢萌典
        self._audio_cache_dir = os.path.join(tempfile.gettempdir(), "taigi_moedict_words")
        self._word_audio_cache: Dict[str, Optional[str]] = {}
        # 接音合成詞間靜音秒數（可調，越小越緊湊）；是否修剪單詞音檔頭尾靜音
        self.concat_gap_sec = float(self.tts_config.get("concat_gap_sec", 0.06))
        self.concat_trim_silence = bool(self.tts_config.get("concat_trim_silence", True))
        # 本地 MMS TTS（facebook/mms-tts-nan）模型快取，僅在首次使用時載入
        self.mms_model_id = self.tts_config.get("mms_model", "facebook/mms-tts-nan")
        self._mms_model = None
        self._mms_tokenizer = None

    def _load_config(self, filepath: str) -> Dict[str, Any]:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    return json.load(f)
                except Exception:
                    pass
        return {}

    # ==================== 萌典官方音檔下載 ====================
    def _try_moedict_ogg(self, hanji: str, output_path: str, quiet: bool = False) -> bool:
        """
        向萌典 API 查詢詞條，取得語音 ID 並下載對應教育部《臺灣台語常用詞辭典》官方 OGG 音訊檔。
        quiet=True 時不輸出查詢過程（供接音合成大量試查單詞時降噪）。
        """
        try:
            if not quiet:
                print(f"[*] 嘗試為詞彙 「{hanji}」 下載萌典官方發音...")
            encoded_hanji = urllib.parse.quote(hanji)
            api_url = f"https://www.moedict.tw/t/{encoded_hanji}.json"

            res = requests.get(api_url, verify=False, timeout=5)
            if res.status_code != 200:
                if not quiet:
                    print(f"  [-] 萌典 API 查詢失敗: HTTP {res.status_code}")
                return False

            data = res.json()
            # 尋找音標語音 ID
            audio_id = None
            if "h" in data and len(data["h"]) > 0:
                audio_id = data["h"][0].get("_")

            if not audio_id:
                if not quiet:
                    print(f"  [-] 無法在萌典中找到詞彙 「{hanji}」 的語音 ID。")
                return False

            # 依語言類別處理語音 ID 的 padding (台語 /t/ 需要補 0 到 5 碼)，例如 "8965" -> "08965"
            normalized_audio_id = str(audio_id).strip()
            if normalized_audio_id.isdigit() and len(normalized_audio_id) < 5:
                normalized_audio_id = normalized_audio_id.zfill(5)

            ogg_url = f"{MOEDICT_CDN_BASE}/{normalized_audio_id}.ogg"
            ogg_res = requests.get(ogg_url, verify=False, timeout=10)
            if ogg_res.status_code != 200:
                if not quiet:
                    print(f"  [-] 音訊檔下載失敗: HTTP {ogg_res.status_code}")
                return False

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(ogg_res.content)
            if not quiet:
                print(f"  [+] 成功儲存詞彙 「{hanji}」 語音檔至: {output_path}")
            return True

        except Exception as e:
            if not quiet:
                print(f"  [-] 下載 「{hanji}」 音訊時發生異常: {str(e)}")
            return False

    def fetch_vocab_audio(self, hanji: str, output_path: str) -> bool:
        """下載單一詞條的教育部官方台語音檔（對外介面，沿用舊行為）。"""
        return self._try_moedict_ogg(hanji, output_path, quiet=False)

    # ==================== 句子語音合成 ====================
    def synthesize_sentence(self, text: str, output_path: str, tailo_numeric: str = "") -> bool:
        """
        將自訂句子進行台語語音合成並存檔。
        支援 provider：
          - yating：雲端 API（需 api_key）
          - concat/moedict：接音合成，串接教育部官方單詞音檔（需 ffmpeg）
          - mms：本地 facebook/mms-tts-nan 神經網路合成（需 torch+transformers，輸入需羅馬字）
          - dummy：靜音佔位
        tailo_numeric：對應的臺羅數字調拼音，mms provider 需要（會轉成白話字餵入模型）。
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if self.provider == "yating" and self.api_key:
            return self._synthesize_yating(text, output_path)
        if self.provider == "mms":
            return self._synthesize_mms(text, output_path, tailo_numeric)
        if self.provider in ("concat", "moedict", "moedict_concat"):
            return self._synthesize_concatenative(text, output_path)
        if self.provider == "yating":
            print("  [!] 警告: 已設定 provider 為 yating 但未提供 api_key。自動降級為 dummy 模式。")
        return self._synthesize_dummy(text, output_path)

    def _synthesize_mms(self, text: str, output_path: str, tailo_numeric: str = "") -> bool:
        """
        本地 facebook/mms-tts-nan（VITS）語音合成。模型以白話字語料訓練，故先將臺羅數字調
        轉為白話字調符式再餵入。未安裝 torch/transformers，或缺臺羅拼音時，降級為接音合成。

        ⚠️ 授權：facebook/mms-tts-nan 為 CC-BY-NC 4.0（限非商業用途）。
        ⚠️ 安裝量大（torch ~2GB），建議裝在非雲端同步路徑的 venv。
        """
        if not tailo_numeric:
            print("  [!] mms provider 需要臺羅拼音 (tailo_numeric) 才能合成，改用接音合成。")
            return self._synthesize_concatenative(text, output_path)

        try:
            import torch  # noqa: F401
            from transformers import VitsModel, AutoTokenizer
        except ImportError:
            print("  [!] 未安裝 torch/transformers，無法使用本地 mms TTS，改用接音合成。")
            print("      安裝方式（建議在非 Drive 路徑的 venv）：pip install torch transformers")
            return self._synthesize_concatenative(text, output_path)

        try:
            from tailo.poj import tailo_to_poj
        except ImportError:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from tailo.poj import tailo_to_poj

        try:
            poj = tailo_to_poj(tailo_numeric)
            print(f"[*] 本地 MMS 合成（{self.mms_model_id}）：臺羅「{tailo_numeric}」→ 白話字「{poj}」")

            # 模型僅在首次使用時載入並快取重用
            if self._mms_model is None:
                import torch
                print(f"  [*] 首次載入 MMS 模型 {self.mms_model_id}（CPU）...")
                self._mms_model = VitsModel.from_pretrained(self.mms_model_id)
                self._mms_tokenizer = AutoTokenizer.from_pretrained(self.mms_model_id)
                self._mms_model.eval()

            import torch
            inputs = self._mms_tokenizer(poj, return_tensors="pt")
            with torch.no_grad():
                waveform = self._mms_model(**inputs).waveform  # shape [1, n]
            samples = waveform[0].cpu().numpy()

            # 轉為 16-bit PCM 並以標準庫 wave 寫出（免 scipy 依賴）
            import wave
            import numpy as np
            pcm = np.clip(samples, -1.0, 1.0)
            pcm = (pcm * 32767.0).astype("<i2")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with wave.open(output_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(int(self._mms_model.config.sampling_rate))
                wf.writeframes(pcm.tobytes())
            print(f"  [+] 本地 MMS 合成完成：{output_path}")
            return True
        except Exception as e:
            print(f"  [-] 本地 MMS 合成失敗（{e}），改用接音合成。")
            return self._synthesize_concatenative(text, output_path)

    def _get_word_audio(self, word: str) -> Optional[str]:
        """
        取得單一台語詞的官方音檔路徑（帶記憶體 + 磁碟快取）。查無音檔回傳 None。
        """
        if not word or not word.strip():
            return None
        if word in self._word_audio_cache:
            return self._word_audio_cache[word]

        os.makedirs(self._audio_cache_dir, exist_ok=True)
        cache_path = os.path.join(self._audio_cache_dir, f"w_{word}.ogg")
        if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
            self._word_audio_cache[word] = cache_path
            return cache_path

        ok = self._try_moedict_ogg(word, cache_path, quiet=True)
        self._word_audio_cache[word] = cache_path if ok else None
        return self._word_audio_cache[word]

    def _segment_for_audio(self, clause: str, max_len: int = 4) -> List[Tuple[str, str]]:
        """
        以「最長詞優先」策略，對照萌典是否收錄該詞來斷詞。
        回傳 [(詞, 音檔路徑), ...]；查無音檔的字會被略過（造成空隙）。
        """
        result: List[Tuple[str, str]] = []
        i, n = 0, len(clause)
        while i < n:
            matched = None
            for length in range(min(max_len, n - i), 0, -1):
                sub = clause[i:i + length]
                path = self._get_word_audio(sub)
                if path:
                    matched = (sub, path)
                    break
            if matched:
                result.append(matched)
                i += len(matched[0])
            else:
                i += 1  # 查無此字音檔，略過
        return result

    def _synthesize_concatenative(self, text: str, output_path: str) -> bool:
        """
        接音合成：將句子斷詞後，串接教育部官方單詞音檔。需要 ffmpeg。
        若 ffmpeg 不存在或無任何可用單詞音檔，降級為 dummy 靜音檔。
        """
        if not shutil.which("ffmpeg"):
            print("  [!] 警告: 找不到 ffmpeg，接音合成降級為 dummy 模式。")
            return self._synthesize_dummy(text, output_path)

        print(f"[*] 執行接音合成（串接教育部官方單詞發音）：「{text}」...")
        # 1. 以標點斷句，再逐句斷詞
        clauses = [c for c in re.split(r"[，。！？、；：,.!?\s]+", text) if c]
        word_paths: List[str] = []
        seg_preview: List[str] = []
        for clause in clauses:
            for word, path in self._segment_for_audio(clause):
                word_paths.append(path)
                seg_preview.append(word)

        if not word_paths:
            print("  [-] 句中無任何收錄於萌典的詞，接音合成降級為 dummy 模式。")
            return self._synthesize_dummy(text, output_path)

        print(f"  [*] 斷詞結果（可發音部分）：{' / '.join(seg_preview)}")

        tmp_dir = tempfile.mkdtemp(prefix="taigi_concat_")
        try:
            # 2. 將每個單詞音檔正規化為 22050Hz 單聲道 wav；可選修剪頭尾靜音以縮短停頓
            norm_paths: List[str] = []
            # silenceremove：修掉開頭與結尾低於 -45dB 的靜音（保留語音本體）
            af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0:"
                  "stop_periods=1:stop_threshold=-45dB:stop_silence=0.02:detection=peak")
            for idx, p in enumerate(word_paths):
                w = os.path.join(tmp_dir, f"w{idx:03d}.wav")
                cmd = ["ffmpeg", "-y", "-i", p, "-ar", "22050", "-ac", "1"]
                if self.concat_trim_silence:
                    cmd += ["-af", af]
                cmd.append(w)
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                # 修剪後若意外變空，退回不修剪版本，避免整詞消失
                if (not os.path.exists(w) or os.path.getsize(w) < 1024) and self.concat_trim_silence:
                    subprocess.run(["ffmpeg", "-y", "-i", p, "-ar", "22050", "-ac", "1", w],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                if os.path.exists(w) and os.path.getsize(w) > 0:
                    norm_paths.append(w)

            if not norm_paths:
                print("  [-] 單詞音檔轉檔皆失敗，降級為 dummy 模式。")
                return self._synthesize_dummy(text, output_path)

            # 3. 產生詞間靜音作為自然停頓（秒數可由 concat_gap_sec 設定）
            silence = None
            if self.concat_gap_sec > 0:
                silence = os.path.join(tmp_dir, "sil.wav")
                subprocess.run(
                    ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
                     "-t", f"{self.concat_gap_sec:.3f}", silence],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )

            # 4. 串接（concat demuxer，詞與詞之間插入靜音）
            list_path = os.path.join(tmp_dir, "list.txt")
            with open(list_path, "w", encoding="utf-8") as f:
                for idx, w in enumerate(norm_paths):
                    if idx > 0 and silence and os.path.exists(silence):
                        f.write(f"file '{silence.replace(chr(92), '/')}'\n")
                    f.write(f"file '{w.replace(chr(92), '/')}'\n")

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            res = subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path,
                 "-ar", "22050", "-ac", "1", output_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            ok = res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
            if ok:
                print(f"  [+] 接音合成完成：{output_path}")
            else:
                print("  [-] ffmpeg 串接失敗，降級為 dummy 模式。")
                return self._synthesize_dummy(text, output_path)
            return ok
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

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
