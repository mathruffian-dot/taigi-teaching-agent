# 臺語教材 AI Agent 統一指令入口 (python -m taigi)
#
# 子指令：
#   doctor    環境健檢（Python/ffmpeg/依賴/設定檔/意傳/萌典連線，附修復指引）
#   tts       台語語音合成（預設意傳媠聲；自動標音、內建限流與降級）
#   piau      漢字 → 臺羅拼音（意傳標音，萌典備援）
#   check     教材內容檢核（華語用字、漢字↔臺羅音節一致性）
#   generate  教材生成（轉呼叫 material_generator）
#   games     互動遊戲網站生成（拖拉配對、聽音揀圖…，吃 generate 的產出資料夾）
#   abtest    TTS A/B 審聽測試（轉呼叫 scripts/tts_ab_test.py）
#
# 慣例：--json 輸出機器可讀 JSON（UTF-8、不轉義）；exit code 0=成功、1=失敗、
#       check 專用 2=有檢核警告。
import argparse
import json
import os
import subprocess
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(PROJECT_ROOT, "src")
for p in (SRC_DIR, PROJECT_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from utils import safe_print  # noqa: E402

print = safe_print

TTS_PROVIDERS = ["ithuan", "concat", "voxcpm", "mms", "yating", "dummy", "config"]


def _emit(args, data: dict, human_lines):
    """依 --json 旗標輸出 JSON 或人類可讀文字。"""
    if getattr(args, "json", False):
        print(json.dumps(data, ensure_ascii=False))
    else:
        for line in human_lines:
            print(line)


# ==================== doctor ====================
def cmd_doctor(args) -> int:
    """
    環境健檢：新使用者（或新機器）第一個指令。每項 ✅/⚠️/❌ 並附修復方式；
    「必要」項目全過 exit 0，否則 exit 1（⚠️ 選配項不影響 exit code）。
    """
    import shutil as _shutil
    import platform
    try:  # 萌典連線沿用專案的寬鬆 TLS 行為，關掉對應警告避免干擾健檢輸出
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass

    results = []  # (等級, 名稱, 狀態, 說明)

    def check(name, required, ok, detail, fix=""):
        mark = "✅" if ok else ("❌" if required else "⚠️")
        results.append({"name": name, "required": required, "ok": bool(ok),
                        "mark": mark, "detail": detail, "fix": fix})

    # 1. Python 版本
    py_ok = sys.version_info >= (3, 10)
    check("Python >= 3.10", True, py_ok, platform.python_version(),
          "請安裝 Python 3.10 以上並重建 .venv（.\\setup.ps1）")

    # 2. 核心依賴
    for mod, pkg in [("requests", "requests"), ("jinja2", "Jinja2"),
                     ("docx", "python-docx"), ("pptx", "python-pptx"), ("PIL", "Pillow")]:
        try:
            __import__(mod)
            check(f"套件 {pkg}", True, True, "已安裝")
        except ImportError:
            check(f"套件 {pkg}", True, False, "未安裝",
                  "執行 .\\setup.ps1 或 pip install -r requirements.txt")

    # 3. ffmpeg（語音轉檔、接音合成必要）
    ff = _shutil.which("ffmpeg")
    check("ffmpeg", True, bool(ff), ff or "PATH 中找不到",
          "winget install Gyan.FFmpeg（或 https://ffmpeg.org 下載後加入 PATH）")

    # 4. config.json
    cfg_exists = os.path.exists(args.config)
    check("config.json", True, cfg_exists,
          args.config if cfg_exists else "不存在",
          "Copy-Item config.example.json config.json")
    base_dir_txt = "（無 config）"
    if cfg_exists:
        try:
            with open(args.config, "r", encoding="utf-8-sig") as f:
                cfg = json.load(f)
            from utils import resolve_output_base_dir
            base = resolve_output_base_dir(cfg)
            os.makedirs(base, exist_ok=True)
            writable = os.access(base, os.W_OK)
            base_dir_txt = base
            check("output.base_dir 可寫入", True, writable, base,
                  "確認 config.json 的 output.base_dir 指向可寫入的本機目錄")
        except Exception as e:
            check("config.json 可解析", True, False, str(e),
                  "檢查 JSON 格式（可與 config.example.json 比對）")

    # 5. 網路服務（教材語音來源）
    def ping(name, required, fn, fix):
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, str(e)[:80]
        check(name, required, ok, detail, fix)

    def ping_ithuan():
        import requests
        r = requests.post("https://hokbu.ithuan.tw/tau", data={"taibun": "台語"}, timeout=10)
        return r.status_code == 200, f"HTTP {r.status_code}（標音／整句合成用）"

    def ping_moedict():
        import requests
        r = requests.get("https://www.moedict.tw/t/%E5%A4%9A%E8%AC%9D.json",
                         verify=False, timeout=10)
        return r.status_code == 200, f"HTTP {r.status_code}（教育部官方音檔用）"

    ping("意傳標音／媠聲服務", False, ping_ithuan,
         "離線時 tts 會降級為 concat／dummy；教材文字類產出不受影響")
    ping("萌典（教育部音檔）", False, ping_moedict,
         "離線時單詞音檔無法下載（已下載過的有快取）")

    # 6. Ollama（選配：AI 大綱生成）
    def ping_ollama():
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        n = len(r.json().get("models", [])) if r.status_code == 200 else 0
        return r.status_code == 200, f"運行中，{n} 個模型"
    ping("Ollama（選配）", False, ping_ollama,
         "未裝也能用：大綱生成會改用離線 Mock。要裝見 README「安裝臺語文字模型」")

    # 輸出
    if getattr(args, "json", False):
        print(json.dumps({"ok": all(r["ok"] for r in results if r["required"]),
                          "checks": results}, ensure_ascii=False))
    else:
        print("🩺 taigi 環境健檢\n" + "─" * 46)
        for r in results:
            print(f" {r['mark']} {r['name']}：{r['detail']}")
            if not r["ok"] and r["fix"]:
                print(f"    ↳ 修復：{r['fix']}")
        required_ok = all(r["ok"] for r in results if r["required"])
        print("─" * 46)
        if required_ok:
            print("✅ 必要項目全部通過！建議的第一條指令（黃金路徑）：")
            print("   .venv\\Scripts\\python -m taigi generate "
                  "--case tests/test_materials/test_case_market_001.json --no-media")
        else:
            print("❌ 有必要項目未通過，請依上方「修復」指引處理後重跑 doctor。")
    return 0 if all(r["ok"] for r in results if r["required"]) else 1


# ==================== tts ====================
def cmd_tts(args) -> int:
    from tts.generator import TaigiTTS

    tts = TaigiTTS(args.config)
    if args.provider != "config":
        tts.provider = args.provider
    output = os.path.abspath(args.output)
    ok = tts.synthesize_sentence(
        args.text, output,
        tailo_numeric=args.tailo_numeric or "",
        tailo_diacritic=args.tailo or "",
    )
    _emit(args, {"ok": bool(ok), "output": output, "provider": tts.provider},
          [f"{'[+] 完成' if ok else '[-] 失敗'}：{output}（provider={tts.provider}）"])
    return 0 if ok else 1


# ==================== piau ====================
def cmd_piau(args) -> int:
    from tailo.piauim import Piauim

    config = {}
    if os.path.exists(args.config):
        with open(args.config, "r", encoding="utf-8-sig") as f:
            config = json.load(f)
    result = Piauim(config).piau(args.text)
    if not result:
        _emit(args, {"ok": False, "text": args.text},
              [f"[-] 標音失敗：「{args.text}」"])
        return 1
    _emit(args, {"ok": True, "text": args.text, **result},
          [f"漢字：{args.text}",
           f"臺羅（KIP）：{result['kip']}",
           f"分詞：{result.get('hanlo', '')}",
           f"來源：{result.get('source', '')}"])
    return 0


# ==================== check ====================
def cmd_check(args) -> int:
    from agent.content_checker import check_lesson_content

    with open(args.file, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    warnings = check_lesson_content(data)
    _emit(args, {"ok": not warnings, "warnings": warnings},
          ([f"⚠️ {w}" for w in warnings] if warnings
           else ["[+] 檢核通過，未發現問題。"]))
    return 2 if warnings else 0


# ==================== generate / abtest（轉呼叫既有進入點）====================
def cmd_generate(args) -> int:
    cmd = [sys.executable, os.path.join(SRC_DIR, "generators", "material_generator.py"),
           "--config", args.config, "--case", args.case]
    if args.output:
        cmd += ["--output", args.output]
    if args.no_media:
        cmd.append("--no-media")
    return subprocess.run(cmd, cwd=PROJECT_ROOT).returncode


def cmd_games(args) -> int:
    from generators.game_generator import GameGenerator
    tpls = [t.strip() for t in args.templates.split(",")] if args.templates else None
    out = GameGenerator(args.config).generate(args.lesson, tpls, args.output)
    print(f"[+] 遊戲網站完成：{os.path.join(out, 'index.html')}")
    return 0


def cmd_abtest(args) -> int:
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, "scripts", "tts_ab_test.py"),
           "--config", args.config]
    if args.engines:
        cmd += ["--engines", args.engines]
    if args.output:
        cmd += ["--output", args.output]
    if args.force:
        cmd.append("--force")
    return subprocess.run(cmd, cwd=PROJECT_ROOT).returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="python -m taigi",
        description="臺語教材 AI Agent 統一指令入口（詳見 AGENTS.md）")
    parser.add_argument("--config", default=os.path.join(PROJECT_ROOT, "config.json"),
                        help="設定檔路徑（預設：專案根目錄 config.json）")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("doctor", help="環境健檢（新機器第一個指令；附修復指引）")
    p.add_argument("--json", action="store_true", help="輸出 JSON")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("tts", help="台語語音合成（預設意傳媠聲，免費、限流 3 句/分鐘已內建節流）")
    p.add_argument("text", help="台語漢字句子")
    p.add_argument("-o", "--output", required=True, help="輸出 WAV 路徑")
    p.add_argument("--provider", choices=TTS_PROVIDERS, default="ithuan",
                   help="語音引擎；config=用 config.json 的 tts.provider（預設 ithuan）")
    p.add_argument("--tailo", default="", help="臺羅調符式（KIP）；不給則自動標音")
    p.add_argument("--tailo-numeric", default="", help="臺羅數字調（mms provider 需要）")
    p.add_argument("--json", action="store_true", help="輸出 JSON")
    p.set_defaults(func=cmd_tts)

    p = sub.add_parser("piau", help="漢字→臺羅標音（意傳，萌典備援）")
    p.add_argument("text", help="台語漢字")
    p.add_argument("--json", action="store_true", help="輸出 JSON")
    p.set_defaults(func=cmd_piau)

    p = sub.add_parser("check", help="教材內容檢核（exit 2=有警告）")
    p.add_argument("file", help="教材 JSON（含 vocabulary/dialogues 欄位）")
    p.add_argument("--json", action="store_true", help="輸出 JSON")
    p.set_defaults(func=cmd_check)

    p = sub.add_parser("generate", help="教材生成（Word/HTML/測驗/音訊…）")
    p.add_argument("--case", required=True, help="測試案例或需求 JSON 路徑")
    p.add_argument("--output", default=None, help="輸出目錄（預設 config 的 output.base_dir）")
    p.add_argument("--no-media", action="store_true", help="跳過音訊與圖片生成")
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("games", help="互動遊戲網站生成（拖拉配對／聽音揀圖）")
    p.add_argument("--lesson", required=True, help="教材產出資料夾（含 lesson_structure.json 與 audio/）")
    p.add_argument("--templates", default=None, help="逗號分隔：match,listen（預設全部）")
    p.add_argument("--output", default=None, help="輸出資料夾（預設 <lesson>/games）")
    p.set_defaults(func=cmd_games)

    p = sub.add_parser("abtest", help="TTS A/B 審聽測試（產出 review.html）")
    p.add_argument("--engines", default=None, help="逗號分隔引擎清單，如 concat,ithuan")
    p.add_argument("--output", default=None, help="輸出目錄")
    p.add_argument("--force", action="store_true", help="重新合成已存在音檔")
    p.set_defaults(func=cmd_abtest)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
