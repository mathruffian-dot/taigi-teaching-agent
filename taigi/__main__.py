# 臺語教材 AI Agent 統一指令入口 (python -m taigi)
#
# 子指令：
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
