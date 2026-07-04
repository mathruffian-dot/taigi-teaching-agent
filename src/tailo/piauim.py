# 漢字 → 台羅自動標音模組 (piauim.py)
#
# 用途：把台語「漢字」轉成「台羅拼音（調符式 KIP）」，取代讓 LLM 自己標音。
# LLM 產的漢字選字很好（有上下文），但臺羅常標不準；本模組改用權威標音引擎重標。
#
# 標音來源（依序）：
#   1. ithuan：意傳科技「媠聲／鬥拍字」標音 API（hokbu.ithuan.tw/tau）。
#      會做斷詞＋上下文多音字判斷，回傳教育部台羅調符式，最準。需連線。
#   2. moedict：萌典逐詞查台羅，離線可快取，但無上下文、多音字較弱。
#   3. None：兩者皆失敗 → 回傳 None，呼叫端保留原本（LLM）的拼音。
#
# 結果以磁碟 + 記憶體快取，避免同句重複打 API。

import os
import sys
import json
import tempfile
import urllib.parse
import urllib.request
from typing import Dict, Any, Optional

# 關閉 verify=False 的警告（萌典 fallback 沿用既有寬鬆 TLS 行為）
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except Exception:
    pass

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from utils import safe_print
    print = safe_print
except Exception:
    pass

ITHUAN_TAU_URL = "https://hokbu.ithuan.tw/tau"
MOEDICT_API = "https://www.moedict.tw/t/{}.json"


class Piauim:
    """漢字→台羅標音器。"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        config = config or {}
        pconf = config.get("piauim", {}) if isinstance(config, dict) else {}
        # 主要標音來源：ithuan（預設）/ moedict / off
        self.provider = pconf.get("provider", "ithuan")
        self.ithuan_url = pconf.get("ithuan_url", ITHUAN_TAU_URL)
        self.timeout = float(pconf.get("timeout", 20))
        self.enable_moedict_fallback = bool(pconf.get("moedict_fallback", True))
        # 快取
        self._mem_cache: Dict[str, Optional[Dict[str, str]]] = {}
        self._cache_dir = os.path.join(tempfile.gettempdir(), "taigi_piauim_cache")
        os.makedirs(self._cache_dir, exist_ok=True)

    # ==================== 對外介面 ====================
    def piau(self, hanji: str) -> Optional[Dict[str, str]]:
        """
        把一段台語漢字標音。回傳：
          {"kip": "ta̍k-ke hó", "hanlo": "逐-家｜ta̍k-ke ...", "source": "ithuan"}
        失敗回傳 None。kip 即台羅調符式，可直接餵 VoxCPM2。
        """
        if not hanji or not hanji.strip():
            return None
        key = hanji.strip()
        if key in self._mem_cache:
            return self._mem_cache[key]

        cached = self._read_disk_cache(key)
        if cached is not None:
            self._mem_cache[key] = cached
            return cached

        result: Optional[Dict[str, str]] = None
        if self.provider == "ithuan":
            result = self._piau_ithuan(key)
            if result is None and self.enable_moedict_fallback:
                result = self._piau_moedict(key)
        elif self.provider == "moedict":
            result = self._piau_moedict(key)
        # provider == "off" → 不標音

        self._mem_cache[key] = result
        if result is not None:
            self._write_disk_cache(key, result)
        return result

    def kip(self, hanji: str) -> Optional[str]:
        """只取台羅調符式字串（給 VoxCPM2 用）。失敗回傳 None。"""
        r = self.piau(hanji)
        return r["kip"] if r else None

    # ==================== 意傳標音 ====================
    def _piau_ithuan(self, hanji: str) -> Optional[Dict[str, str]]:
        try:
            data = urllib.parse.urlencode({"taibun": hanji}).encode("utf-8")
            req = urllib.request.Request(
                self.ithuan_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                payload = json.loads(r.read().decode("utf-8"))
            kip = (payload.get("KIP") or "").strip()
            hanlo = (payload.get("分詞") or "").strip()
            if not kip:
                print(f"  [-] 意傳標音回傳空 KIP：「{hanji}」")
                return None
            return {"kip": kip, "hanlo": hanlo, "source": "ithuan"}
        except Exception as e:
            print(f"  [-] 意傳標音失敗（{e}）：「{hanji}」")
            return None

    # ==================== 萌典逐詞備援 ====================
    def _piau_moedict(self, hanji: str) -> Optional[Dict[str, str]]:
        """整串丟萌典查台羅（適合單詞；長句多半查不到，回 None 由呼叫端保留原值）。"""
        try:
            import requests  # 萌典備援才需要 requests；意傳路徑用 stdlib 即可
        except Exception:
            return self._piau_moedict_stdlib(hanji)
        try:
            url = MOEDICT_API.format(urllib.parse.quote(hanji))
            res = requests.get(url, verify=False, timeout=self.timeout)
            if res.status_code != 200:
                return None
            data = res.json()
            tailo = None
            if "h" in data and data["h"]:
                # 萌典台語詞條的台羅在 T 欄位
                tailo = data["h"][0].get("T")
            if not tailo:
                return None
            return {"kip": tailo.strip(), "hanlo": f"{hanji}｜{tailo.strip()}", "source": "moedict"}
        except Exception:
            return None

    def _piau_moedict_stdlib(self, hanji: str) -> Optional[Dict[str, str]]:
        try:
            import ssl
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            url = MOEDICT_API.format(urllib.parse.quote(hanji))
            with urllib.request.urlopen(url, timeout=self.timeout, context=ctx) as r:
                data = json.loads(r.read().decode("utf-8"))
            tailo = data.get("h", [{}])[0].get("T") if data.get("h") else None
            if not tailo:
                return None
            return {"kip": tailo.strip(), "hanlo": f"{hanji}｜{tailo.strip()}", "source": "moedict"}
        except Exception:
            return None

    # ==================== 快取 ====================
    def _cache_path(self, key: str) -> str:
        # 以 hash 命名避免檔名含非法字元
        import hashlib
        h = hashlib.md5(key.encode("utf-8")).hexdigest()
        return os.path.join(self._cache_dir, f"{h}.json")

    def _read_disk_cache(self, key: str) -> Optional[Dict[str, str]]:
        path = self._cache_path(key)
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    obj = json.load(f)
                # 確認是同一個 key（避免 hash 碰撞）
                if obj.get("_key") == key:
                    return obj.get("result")
            except Exception:
                return None
        return None

    def _write_disk_cache(self, key: str, result: Dict[str, str]) -> None:
        try:
            with open(self._cache_path(key), "w", encoding="utf-8") as f:
                json.dump({"_key": key, "result": result}, f, ensure_ascii=False)
        except Exception:
            pass


if __name__ == "__main__":
    # 簡單手動測試（需連線）
    p = Piauim()
    for s in ["菜市仔", "逐家好，今仔日天氣真好。", "我欲去學校讀冊。"]:
        r = p.piau(s)
        print(f"{s} -> {r}")
