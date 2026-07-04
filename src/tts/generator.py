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

# 意傳「媠聲」語音合成端點（輸入臺羅調符式 KIP，回傳 MP3）
# ⚠️ 展示服務、資源有限：官方限流「1 IP 1 分鐘最多 3 句」，正式量產前應洽意傳科技。
ITHUAN_BANGTSAM_URL = "https://hapsing.ithuan.tw/bangtsam"


class TaigiTTS:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.tts_config = self.config.get("tts", {})
        self.provider = self.tts_config.get("provider", "dummy")
        self.api_key = self.tts_config.get("api_key", "")
        # 接音合成用：單詞官方音檔快取（記憶體 + 磁碟），避免重複查詢萌典
        self._audio_cache_dir = os.path.join(tempfile.gettempdir(), "taigi_moedict_words")
        self._word_audio_cache: Dict[str, Optional[str]] = {}
        # 接音合成停頓秒數（可調，越小越緊湊）：詞間（句內）與標點處（句間）分開設定。
        self.concat_gap_sec = float(self.tts_config.get("concat_gap_sec", 0.06))
        self.concat_phrase_gap_sec = float(self.tts_config.get("concat_phrase_gap_sec", 0.22))
        # 是否修剪單詞音檔頭尾靜音：預設關閉。修剪會削掉入聲(-p/-t/-k/-h)等較弱字尾、
        # 破壞發音，僅在確認無副作用時才開。
        self.concat_trim_silence = bool(self.tts_config.get("concat_trim_silence", False))
        # 本地 MMS TTS（facebook/mms-tts-nan）模型快取，僅在首次使用時載入
        self.mms_model_id = self.tts_config.get("mms_model", "facebook/mms-tts-nan")
        self._mms_model = None
        self._mms_tokenizer = None
        # VoxCPM2 接音設定：以 subprocess 呼叫語音專案的 clone_batch.py（三師爸台語聲音）。
        # torch 裝在語音專案自己的 venv，刻意不裝進本（雲端同步）專案的 venv。
        self.voxcpm_config = self.tts_config.get("voxcpm", {})
        # 意傳媠聲：限流 1 IP 每分鐘 3 句 → 兩次請求間至少隔 ithuan_interval_sec 秒
        self.ithuan_url = self.tts_config.get("ithuan_url", ITHUAN_BANGTSAM_URL)
        self.ithuan_interval_sec = float(self.tts_config.get("ithuan_interval_sec", 21))
        self._ithuan_last_request = 0.0
        self._piauim = None  # 缺臺羅時的漢字→KIP 標音器（延遲載入）

    def _load_config(self, filepath: str) -> Dict[str, Any]:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8-sig") as f:
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
    def synthesize_sentence(self, text: str, output_path: str, tailo_numeric: str = "",
                            tailo_diacritic: str = "") -> bool:
        """
        將自訂句子進行台語語音合成並存檔。
        支援 provider：
          - voxcpm：以三師爸台語聲音用 VoxCPM2 克隆生成（subprocess 呼叫語音專案，可商用）
          - ithuan：意傳「媠聲」線上合成（免費展示服務，輸入臺羅 KIP，限流 3 句/分鐘）
          - yating：雲端 API（需 api_key）
          - concat/moedict：接音合成，串接教育部官方單詞音檔（需 ffmpeg）
          - mms：本地 facebook/mms-tts-nan 神經網路合成（需 torch+transformers，輸入需羅馬字）
          - dummy：靜音佔位
        tailo_numeric：對應的臺羅數字調拼音，mms provider 需要（會轉成白話字餵入模型）。
        tailo_diacritic：對應的臺羅調符式（KIP），voxcpm/ithuan provider 使用；
                         ithuan 缺臺羅時會自動以 Piauim 從漢字標音。
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if self.provider == "voxcpm":
            feed = self._voxcpm_feed_text(text, tailo_diacritic)
            ok = self.synthesize_voxcpm_batch([{"text": feed, "output": output_path}])
            return bool(ok and ok[0])
        if self.provider == "ithuan":
            return self._synthesize_ithuan(text, output_path, tailo_diacritic)
        if self.provider == "yating" and self.api_key:
            return self._synthesize_yating(text, output_path)
        if self.provider == "mms":
            return self._synthesize_mms(text, output_path, tailo_numeric)
        if self.provider in ("concat", "moedict", "moedict_concat"):
            return self._synthesize_concatenative(text, output_path)
        if self.provider == "yating":
            print("  [!] 警告: 已設定 provider 為 yating 但未提供 api_key。自動降級為 dummy 模式。")
        return self._synthesize_dummy(text, output_path)

    # ==================== VoxCPM2（三師爸台語聲音）====================
    def _voxcpm_feed_text(self, hanji: str, tailo_diacritic: str = "") -> str:
        """
        依 input_mode 決定餵給 VoxCPM2 的文字：
          - tailo（預設）：餵台羅調符式（phonetic），發音最可控；缺台羅時退回漢字。
          - hanji：直接餵台語漢字，靠 VoxCPM2 的閩南語方言模型朗讀。
          - hanji_tailo：同時餵漢字與臺羅，讓模型保留語意並參考發音。
        """
        mode = self.voxcpm_config.get("input_mode", "tailo")
        if mode == "tailo":
            return tailo_diacritic.strip() if tailo_diacritic and tailo_diacritic.strip() else hanji
        if mode == "hanji_tailo":
            tailo = (tailo_diacritic or "").strip()
            if tailo:
                return f"{hanji}；臺羅：{tailo}"
            return hanji
        return hanji

    def synthesize_voxcpm_batch(self, items):
        """
        批次以 VoxCPM2 生成（模型只載一次）。items: [{"text":..., "output":...}]。
        回傳與 items 等長的 bool 清單。整批失敗時，每句降級為接音合成。
        """
        if not items:
            return []

        python = self.voxcpm_config.get("python")
        script = self.voxcpm_config.get("script")
        if not python or not os.path.exists(python) or not script or not os.path.exists(script):
            print("  [!] 警告: 找不到 VoxCPM2 的 python 或 clone_batch.py，"
                  "voxcpm 合成降級為接音合成。請檢查 config.json 的 tts.voxcpm.python / script。")
            return [self._synthesize_concatenative(it["text"], it["output"]) for it in items]

        job = {
            "voice": self.voxcpm_config.get("voice", "三師爸台語"),
            "cfg": float(self.voxcpm_config.get("cfg", 2.0)),
            "timesteps": int(self.voxcpm_config.get("timesteps", 10)),
            "normalize": bool(self.voxcpm_config.get("normalize", False)),
            "denoise": bool(self.voxcpm_config.get("denoise", False)),
            "device": self.voxcpm_config.get("device"),
            "items": [{"text": it["text"], "output": os.path.abspath(it["output"])} for it in items],
        }

        tmp_dir = tempfile.mkdtemp(prefix="taigi_voxcpm_")
        job_path = os.path.join(tmp_dir, "jobs.json")
        result_path = os.path.join(tmp_dir, "result.json")
        try:
            with open(job_path, "w", encoding="utf-8") as f:
                json.dump(job, f, ensure_ascii=False)

            print(f"[*] VoxCPM2 批次生成（{len(items)} 句，聲音「{job['voice']}」）...")
            proc = subprocess.run(
                [python, script, job_path, "--result", result_path],
                cwd=os.path.dirname(os.path.abspath(script)),
                capture_output=True, encoding="utf-8", errors="replace",
            )
            if proc.returncode != 0:
                print(f"  [-] VoxCPM2 子程序失敗（return {proc.returncode}），降級接音合成。")
                if proc.stderr:
                    print("      " + proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "")
                return [self._synthesize_concatenative(it["text"], it["output"]) for it in items]

            # 讀回結果，逐句對應 ok
            ok_by_output = {}
            if os.path.exists(result_path):
                with open(result_path, "r", encoding="utf-8") as f:
                    res = json.load(f)
                for r in res.get("results", []):
                    ok_by_output[os.path.abspath(r.get("output", ""))] = bool(r.get("ok"))

            out_flags = []
            for it in items:
                ap = os.path.abspath(it["output"])
                ok = ok_by_output.get(ap, os.path.exists(ap) and os.path.getsize(ap) > 0)
                if not ok:
                    # 個別句失敗 → 該句降級接音合成
                    ok = self._synthesize_concatenative(it["text"], it["output"])
                out_flags.append(ok)
            done = sum(1 for x in out_flags if x)
            print(f"  [+] VoxCPM2 完成 {done}/{len(items)} 句。")
            return out_flags
        except Exception as e:
            print(f"  [-] VoxCPM2 批次合成異常（{e}），降級接音合成。")
            return [self._synthesize_concatenative(it["text"], it["output"]) for it in items]
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    # ==================== 意傳「媠聲」線上合成 ====================
    def _ithuan_kip(self, hanji: str, tailo_diacritic: str = "") -> Optional[str]:
        """取得餵給媠聲的臺羅 KIP：優先用呼叫端提供的調符式，缺才用 Piauim 從漢字標音。"""
        if tailo_diacritic and tailo_diacritic.strip():
            return tailo_diacritic.strip()
        if self._piauim is None:
            try:
                from tailo.piauim import Piauim
            except ImportError:
                sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from tailo.piauim import Piauim
            self._piauim = Piauim(self.config)
        return self._piauim.kip(hanji)

    def _synthesize_ithuan(self, text: str, output_path: str, tailo_diacritic: str = "") -> bool:
        """
        意傳「媠聲」語音合成（hapsing.ithuan.tw/bangtsam）：輸入臺羅調符式 KIP，回傳 MP3，
        再以 ffmpeg 轉 22050Hz 單聲道 WAV。
        ⚠️ 免費展示服務、資源有限：官方限流「1 IP 1 分鐘最多 3 句」，本函式會自動節流；
           正式量產前應洽意傳科技（ithuan.tw）談授權，並於教材標示語音來源。
        失敗（含限流 500）會等一段時間重試一次，仍失敗則降級接音合成。
        """
        import time

        kip = self._ithuan_kip(text, tailo_diacritic)
        if not kip:
            print(f"  [!] 意傳合成需要臺羅 KIP，「{text}」標音失敗，改用接音合成。")
            return self._synthesize_concatenative(text, output_path)

        if not shutil.which("ffmpeg"):
            print("  [!] 警告: 找不到 ffmpeg，無法轉檔，意傳合成降級為接音合成。")
            return self._synthesize_concatenative(text, output_path)

        url = f"{self.ithuan_url}?taibun={urllib.parse.quote(kip)}"
        print(f"[*] 意傳媠聲合成：「{text}」（KIP：{kip}）...")

        for attempt in range(2):
            # 節流：距上次請求不足 interval 就等（限流 3 句/分鐘）
            wait = self.ithuan_interval_sec - (time.time() - self._ithuan_last_request)
            if wait > 0:
                time.sleep(wait)
            try:
                self._ithuan_last_request = time.time()
                res = requests.get(url, headers={"User-Agent": "taigi-teaching-agent/1.0"},
                                   timeout=90)
                if res.status_code == 200 and res.content:
                    tmp_mp3 = output_path + ".ithuan.mp3"
                    with open(tmp_mp3, "wb") as f:
                        f.write(res.content)
                    conv = subprocess.run(
                        ["ffmpeg", "-y", "-i", tmp_mp3, "-ar", "22050", "-ac", "1", output_path],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    os.remove(tmp_mp3)
                    if conv.returncode == 0 and os.path.getsize(output_path) > 0:
                        print(f"  [+] 意傳媠聲合成完成：{output_path}")
                        return True
                    print("  [-] MP3 轉 WAV 失敗。")
                    break
                # 500 多為限流，等滿一分鐘再重試一次
                print(f"  [-] 意傳合成 HTTP {res.status_code}"
                      f"{'，等 65 秒後重試（可能被限流）' if attempt == 0 else ''}")
                if attempt == 0:
                    time.sleep(65)
            except Exception as e:
                print(f"  [-] 意傳合成異常（{e}）"
                      f"{'，等 65 秒後重試' if attempt == 0 else ''}")
                if attempt == 0:
                    time.sleep(65)

        print("  [-] 意傳合成失敗，降級為接音合成。")
        return self._synthesize_concatenative(text, output_path)

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
        # 1. 以標點斷句，再逐句斷詞（保留分句結構，句間給較長停頓）
        clauses = [c for c in re.split(r"[，。！？、；：,.!?\s]+", text) if c]
        clause_segs: List[List[Tuple[str, str]]] = []
        seg_preview: List[str] = []
        for clause in clauses:
            seg = self._segment_for_audio(clause)
            if seg:
                clause_segs.append(seg)
                seg_preview.append("".join(w for w, _ in seg))

        if not clause_segs:
            print("  [-] 句中無任何收錄於萌典的詞，接音合成降級為 dummy 模式。")
            return self._synthesize_dummy(text, output_path)

        print(f"  [*] 斷詞結果（可發音部分）：{' | '.join(seg_preview)}")

        tmp_dir = tempfile.mkdtemp(prefix="taigi_concat_")
        try:
            # 2. 將每個單詞音檔正規化為 22050Hz 單聲道 wav（保留分句結構）；
            #    可選修剪頭尾靜音（預設關閉，修剪會削掉入聲字尾破壞發音）。
            af = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0:"
                  "stop_periods=1:stop_threshold=-45dB:stop_silence=0.02:detection=peak")
            norm_clauses: List[List[str]] = []
            idx = 0
            for seg in clause_segs:
                norm_words: List[str] = []
                for _word, p in seg:
                    w = os.path.join(tmp_dir, f"w{idx:03d}.wav")
                    idx += 1
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
                        norm_words.append(w)
                if norm_words:
                    norm_clauses.append(norm_words)

            if not norm_clauses:
                print("  [-] 單詞音檔轉檔皆失敗，降級為 dummy 模式。")
                return self._synthesize_dummy(text, output_path)

            # 3. 產生兩種停頓靜音：詞間（句內，較短）與標點處（句間，較長）
            def make_silence(seconds: float, name: str) -> Optional[str]:
                if seconds <= 0:
                    return None
                path = os.path.join(tmp_dir, name)
                subprocess.run(
                    ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=22050:cl=mono",
                     "-t", f"{seconds:.3f}", path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                return path if os.path.exists(path) else None

            word_sil = make_silence(self.concat_gap_sec, "sil_word.wav")
            phrase_sil = make_silence(self.concat_phrase_gap_sec, "sil_phrase.wav")

            # 4. 串接（concat demuxer）：句內詞間插短靜音，句與句間插長靜音
            list_path = os.path.join(tmp_dir, "list.txt")
            with open(list_path, "w", encoding="utf-8") as f:
                def write_file(p: str):
                    f.write(f"file '{p.replace(chr(92), '/')}'\n")
                for ci, words in enumerate(norm_clauses):
                    if ci > 0 and phrase_sil:
                        write_file(phrase_sil)
                    for wi, w in enumerate(words):
                        if wi > 0 and word_sil:
                            write_file(word_sil)
                        write_file(w)

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
        呼叫雅婷智慧 (Yating) TTS v2 API 合成語音。
        台語聲音有三種（config 的 tts.yating_voice 可選）：
          tai_female_1（雅婷）／tai_male_1（家豪）／tai_female_2（意晴）
        台語聲音僅支援 16K 取樣率；輸出 LINEAR16（WAV）。
        """
        try:
            voice = self.tts_config.get("yating_voice", "tai_female_1")
            print(f"[*] 正在呼叫雅婷 TTS（{voice}）合成語音：「{text}」...")

            url = "https://tts.api.yating.tw/v2/speeches/short"
            headers = {
                "key": self.api_key,
                "Content-Type": "application/json"
            }
            payload = {
                "input": {
                    "text": text,
                    "type": "text"
                },
                "voice": {
                    "model": voice,
                    "speed": float(self.tts_config.get("yating_speed", 1.0)),
                    "pitch": float(self.tts_config.get("yating_pitch", 1.0)),
                    "energy": float(self.tts_config.get("yating_energy", 1.0))
                },
                "audioConfig": {
                    "encoding": "LINEAR16",
                    "sampleRate": self.tts_config.get("yating_sample_rate", "16K")
                }
            }

            res = requests.post(url, json=payload, headers=headers, timeout=30)
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
