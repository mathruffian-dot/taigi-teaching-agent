from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
TEMP_VIDEO_DIR = Path(tempfile.gettempdir()) / "taigi-video-render"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    ok: bool,
    message: str,
    severity: str = "error",
    details: dict[str, Any] | None = None,
) -> None:
    checks.append({
        "name": name,
        "ok": bool(ok),
        "severity": severity,
        "message": message,
        "details": details or {},
    })


def resolve_command(name: str, prefer_cmd: bool = False) -> str | None:
    candidates: list[str] = []
    if sys.platform.startswith("win") and prefer_cmd:
        candidates.append(f"{name}.cmd")
    candidates.append(name)
    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return None


def command_version(command: str | None, args: list[str] | None = None, timeout: int = 8) -> dict[str, Any]:
    if not command:
        return {"ok": False, "output": ""}
    try:
        proc = subprocess.run(
            [command, *(args or ["--version"])],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        text = (proc.stdout or proc.stderr or "").strip().splitlines()
        return {"ok": proc.returncode == 0, "output": text[0] if text else ""}
    except Exception as exc:
        return {"ok": False, "output": str(exc)}


def check_config(checks: list[dict[str, Any]], config_path: Path) -> dict[str, Any]:
    add_check(
        checks,
        "config_exists",
        config_path.exists(),
        "正式輸出需能讀取專案 config.json。",
        details={"path": str(config_path)},
    )
    if not config_path.exists():
        return {}
    try:
        config = load_json(config_path)
        add_check(checks, "config_json_valid", True, "config.json 必須是可解析的 JSON。")
        return config
    except Exception as exc:
        add_check(
            checks,
            "config_json_valid",
            False,
            "config.json 必須是可解析的 JSON。",
            details={"error": str(exc)},
        )
        return {}


def check_output_dir(checks: list[dict[str, Any]], config: dict[str, Any]) -> None:
    raw = (config.get("output") or {}).get("base_dir", "")
    # base_dir 可含 %USERPROFILE% 等環境變數（config.json 跨電腦同步，路徑勿寫死）
    base_dir = Path(os.path.expandvars(raw)).expanduser() if raw else PROJECT_ROOT / "output"
    if not base_dir.is_absolute():
        base_dir = PROJECT_ROOT / base_dir
    base_text = str(base_dir)
    project_text = str(PROJECT_ROOT)
    is_cloud_like = "我的雲端硬碟" in base_text or "Google Drive" in base_text
    is_under_project = base_text.lower().startswith(project_text.lower())
    add_check(
        checks,
        "output_base_dir_configured",
        bool(raw),
        "正式影音與圖片輸出需設定 output.base_dir。",
        details={"base_dir": base_text},
    )
    add_check(
        checks,
        "output_base_dir_local",
        not is_cloud_like and not is_under_project,
        "大型輸出應放在本機目錄，避免 Google Drive 同步大量影音與圖片。",
        details={"base_dir": base_text, "project_root": project_text},
    )
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        probe = base_dir / ".readiness_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        add_check(checks, "output_base_dir_writable", True, "正式輸出目錄必須可寫入。", details={"base_dir": base_text})
    except Exception as exc:
        add_check(
            checks,
            "output_base_dir_writable",
            False,
            "正式輸出目錄必須可寫入。",
            details={"base_dir": base_text, "error": str(exc)},
        )


def check_tts(checks: list[dict[str, Any]], config: dict[str, Any], attempt_sample: bool) -> None:
    tts = config.get("tts") or {}
    provider = tts.get("provider", "dummy")
    add_check(
        checks,
        "tts_provider_not_dummy",
        provider != "dummy",
        "正式上課版本不能只使用靜音 dummy TTS。",
        details={"provider": provider},
    )
    if provider == "voxcpm":
        voxcpm = tts.get("voxcpm") or {}
        python_path = Path(voxcpm.get("python", ""))
        script_path = Path(voxcpm.get("script", ""))
        add_check(
            checks,
            "voxcpm_python_exists",
            python_path.exists(),
            "VoxCPM2 provider 需要可執行的語音專案 Python。",
            details={"path": str(python_path)},
        )
        add_check(
            checks,
            "voxcpm_script_exists",
            script_path.exists(),
            "VoxCPM2 provider 需要 clone_batch.py 腳本。",
            details={"path": str(script_path)},
        )
        add_check(
            checks,
            "voxcpm_voice_configured",
            bool(voxcpm.get("voice")),
            "VoxCPM2 provider 需要指定三師爸台語聲音。",
            details={"voice": voxcpm.get("voice", "")},
        )
        if python_path.exists():
            version = command_version(str(python_path), ["--version"])
            add_check(
                checks,
                "voxcpm_python_runs",
                version["ok"],
                "語音專案 Python 必須可執行。",
                details=version,
            )
    elif provider in {"concat", "moedict", "moedict_concat"}:
        add_check(
            checks,
            "concat_ffmpeg_available",
            bool(resolve_command("ffmpeg")),
            "接音合成需要 ffmpeg。",
            details={"ffmpeg": resolve_command("ffmpeg") or ""},
        )
    elif provider == "yating":
        add_check(
            checks,
            "yating_api_key_configured",
            bool(tts.get("api_key")),
            "雅婷 TTS provider 需要 api_key。",
        )
    elif provider == "mms":
        add_check(
            checks,
            "mms_provider_review_license",
            False,
            "MMS provider 為非商業授權，正式教材需確認授權用途。",
            severity="warning",
            details={"provider": provider},
        )

    if attempt_sample:
        try:
            out = Path(tempfile.gettempdir()) / "taigi_readiness_tts.wav"
            out.unlink(missing_ok=True)
            if provider == "voxcpm":
                voxcpm = tts.get("voxcpm") or {}
                python_path = Path(voxcpm.get("python", ""))
                script_path = Path(voxcpm.get("script", ""))
                input_mode = voxcpm.get("input_mode", "tailo")
                if input_mode == "tailo":
                    text = "Tshài-se"
                elif input_mode == "hanji_tailo":
                    text = "菜蔬；臺羅：Tshài-se"
                else:
                    text = "菜蔬"
                with tempfile.TemporaryDirectory(prefix="taigi_readiness_voxcpm_") as tmp:
                    tmp_dir = Path(tmp)
                    job_path = tmp_dir / "jobs.json"
                    result_path = tmp_dir / "result.json"
                    job = {
                        "voice": voxcpm.get("voice", "三師爸台語"),
                        "cfg": float(voxcpm.get("cfg", 2.0)),
                        "timesteps": int(voxcpm.get("timesteps", 10)),
                        "normalize": bool(voxcpm.get("normalize", False)),
                        "denoise": bool(voxcpm.get("denoise", False)),
                        "device": voxcpm.get("device"),
                        "items": [{"text": text, "output": str(out)}],
                    }
                    job_path.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
                    proc = subprocess.run(
                        [str(python_path), str(script_path), str(job_path), "--result", str(result_path)],
                        cwd=str(script_path.parent),
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=600,
                    )
                    result = load_json(result_path) if result_path.exists() else {}
                    item = ((result.get("results") or [{}])[0]) if isinstance(result, dict) else {}
                    size = out.stat().st_size if out.exists() else 0
                    ok = (
                        proc.returncode == 0
                        and bool(result.get("ok"))
                        and bool(item.get("ok"))
                        and size > 16_000
                    )
                    details = {
                        "path": str(out),
                        "size": size,
                        "returncode": proc.returncode,
                        "duration": item.get("duration"),
                    }
                    if not ok:
                        details["stdout_tail"] = "\n".join((proc.stdout or "").splitlines()[-6:])
                        details["stderr_tail"] = "\n".join((proc.stderr or "").splitlines()[-6:])
                    add_check(
                        checks,
                        "tts_sample_generation",
                        ok,
                        "VoxCPM2 必須直接產生真實非空音檔，不可降級為 dummy。",
                        details=details,
                    )
                    return
            if str(PROJECT_ROOT / "src") not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT / "src"))
            from tts.generator import TaigiTTS

            ok = TaigiTTS(str(PROJECT_ROOT / "config.json")).synthesize_sentence(
                "菜蔬",
                str(out),
                tailo_numeric="tshai3-se1",
                tailo_diacritic="tshài-se",
            )
            size = out.stat().st_size if out.exists() else 0
            add_check(
                checks,
                "tts_sample_generation",
                bool(ok and size > 16_000),
                "真實 TTS 樣本必須能產生非 dummy 的非空音檔。",
                details={"path": str(out), "size": size},
            )
        except Exception as exc:
            add_check(
                checks,
                "tts_sample_generation",
                False,
                "真實 TTS 樣本必須能產生非空音檔。",
                details={"error": str(exc)},
            )
    else:
        add_check(
            checks,
            "tts_sample_generation",
            False,
            "尚未執行真實 TTS 樣本；可加上 -AttemptTtsSample 進一步驗證。",
            severity="warning",
        )


def check_piauim(checks: list[dict[str, Any]], config: dict[str, Any], live_network: bool) -> None:
    piauim = config.get("piauim") or {}
    provider = piauim.get("provider", "ithuan")
    add_check(
        checks,
        "piauim_provider_enabled",
        provider != "off",
        "正式輸出應啟用漢字轉臺羅標音，降低 LLM 拼音錯誤。",
        details={"provider": provider},
    )
    if live_network:
        try:
            if str(PROJECT_ROOT / "src") not in sys.path:
                sys.path.insert(0, str(PROJECT_ROOT / "src"))
            from tailo.piauim import Piauim

            result = Piauim(config).kip("菜市仔")
            add_check(
                checks,
                "piauim_live_sample",
                bool(result),
                "標音服務需能替樣本文字產生臺羅。",
                details={"sample": "菜市仔", "kip": result or ""},
            )
        except Exception as exc:
            add_check(
                checks,
                "piauim_live_sample",
                False,
                "標音服務需能替樣本文字產生臺羅。",
                details={"error": str(exc)},
            )
    else:
        add_check(
            checks,
            "piauim_live_sample",
            False,
            "尚未執行標音服務連線樣本；可加上 -LiveNetwork 進一步驗證。",
            severity="warning",
        )


def check_image_generation(checks: list[dict[str, Any]], live_network: bool) -> None:
    if live_network:
        try:
            import requests

            requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
            res = requests.get("https://aihorde.net/api/v2/status/heartbeat", timeout=8, verify=False)
            add_check(
                checks,
                "image_generation_endpoint_reachable",
                200 <= res.status_code < 500,
                "AI Horde 免費匿名生圖端點需可連線。",
                details={"status_code": res.status_code},
            )
        except Exception as exc:
            curl = resolve_command("curl")
            if curl:
                try:
                    proc = subprocess.run(
                        [curl, "-L", "-k", "-s", "-o", "-", "-w", "%{http_code}", "https://aihorde.net/api/v2/status/heartbeat"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=12,
                    )
                    status_text = (proc.stdout or "")[-3:]
                    status = int(status_text) if status_text.isdigit() else 0
                    add_check(
                        checks,
                        "image_generation_endpoint_reachable",
                        200 <= status < 500,
                        "AI Horde 免費匿名生圖端點需可連線。",
                        details={"status_code": status, "fallback": "curl", "requests_error": str(exc)},
                    )
                    return
                except Exception as curl_exc:
                    add_check(
                        checks,
                        "image_generation_endpoint_reachable",
                        False,
                        "AI Horde 免費匿名生圖端點需可連線。",
                        details={"requests_error": str(exc), "curl_error": str(curl_exc)},
                    )
                    return
            add_check(
                checks,
                "image_generation_endpoint_reachable",
                False,
                "AI Horde 免費匿名生圖端點需可連線。",
                details={"error": str(exc)},
            )
    else:
        add_check(
            checks,
            "image_generation_endpoint_reachable",
            False,
            "尚未執行生圖端點連線檢查；可加上 -LiveNetwork 進一步驗證。",
            severity="warning",
        )


def check_video_tools(checks: list[dict[str, Any]]) -> None:
    commands = {
        "node": resolve_command("node"),
        "npm": resolve_command("npm", prefer_cmd=True),
        "npx": resolve_command("npx", prefer_cmd=True),
        "ffmpeg": resolve_command("ffmpeg"),
        "ffprobe": resolve_command("ffprobe"),
    }
    for name, command in commands.items():
        version_args = ["-version"] if name in {"ffmpeg", "ffprobe"} else ["--version"]
        version = command_version(command, version_args)
        add_check(
            checks,
            f"video_tool_{name}",
            bool(command) and version["ok"],
            f"教學影片生成需要 {name} 可執行。",
            details={"command": command or "", "version": version.get("output", "")},
        )
    playwright_dir = TEMP_VIDEO_DIR / "node_modules" / "playwright"
    add_check(
        checks,
        "playwright_cached_in_temp",
        playwright_dir.exists(),
        "Playwright 應安裝於系統暫存目錄，避免 node_modules 進入 Google Drive。",
        severity="warning",
        details={"path": str(playwright_dir), "temp_render_dir": str(TEMP_VIDEO_DIR)},
    )


def check_official_assets(checks: list[dict[str, Any]]) -> None:
    required = [
        PROJECT_ROOT / "data" / "official_materials" / "catalog.json",
        PROJECT_ROOT / "data" / "official_materials" / "analysis" / "official_material_bank.json",
        PROJECT_ROOT / "data" / "official_materials" / "analysis" / "official_generation_packs.json",
    ]
    missing = [str(path.relative_to(PROJECT_ROOT)) for path in required if not path.exists()]
    add_check(
        checks,
        "official_assets_ready_for_generation",
        not missing,
        "正式輸出需能引用已整理官方教材與生成素材。",
        details={"missing": missing},
    )


def write_reports(report: dict[str, Any], json_path: Path, md_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# 正式輸出模式 Readiness 稽核",
        "",
        f"產生時間：{report['generated_at']}",
        f"結果：{'必要項目通過' if report['ok'] else '必要項目未通過'}",
        "",
        "## 必要項目",
        "",
    ]
    for check in report["checks"]:
        if check["severity"] != "error":
            continue
        mark = "通過" if check["ok"] else "未通過"
        lines.append(f"- [{mark}] {check['name']}：{check['message']}")
    warnings = [check for check in report["checks"] if check["severity"] != "error"]
    if warnings:
        lines.extend(["", "## 提醒項目", ""])
        for check in warnings:
            mark = "通過" if check["ok"] else "待確認"
            lines.append(f"- [{mark}] {check['name']}：{check['message']}")
    lines.extend([
        "",
        "## 使用方式",
        "",
        "```powershell",
        "powershell -ExecutionPolicy Bypass -File .\\scripts\\audit-formal-output-readiness.ps1",
        "powershell -ExecutionPolicy Bypass -File .\\scripts\\audit-formal-output-readiness.ps1 -LiveNetwork",
        "powershell -ExecutionPolicy Bypass -File .\\scripts\\audit-formal-output-readiness.ps1 -AttemptTtsSample",
        "powershell -ExecutionPolicy Bypass -File .\\scripts\\audit-formal-output-readiness.ps1 -LiveNetwork -AttemptTtsSample",
        "```",
        "",
    ])
    md_path.write_text("\n".join(lines), encoding="utf-8")


def audit_formal_output_readiness(
    config_path: Path = PROJECT_ROOT / "config.json",
    live_network: bool = False,
    attempt_tts_sample: bool = False,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    config = check_config(checks, config_path)
    if config:
        check_output_dir(checks, config)
        check_tts(checks, config, attempt_tts_sample)
        check_piauim(checks, config, live_network)
    check_image_generation(checks, live_network)
    check_video_tools(checks)
    check_official_assets(checks)
    ok = all(check["ok"] for check in checks if check["severity"] == "error")
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "ok": ok,
        "live_network": live_network,
        "attempt_tts_sample": attempt_tts_sample,
        "checks": checks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="稽核正式輸出模式需要的本機與外部能力。")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config.json"))
    parser.add_argument("--live-network", action="store_true", help="執行標音與生圖端點的連線樣本檢查")
    parser.add_argument("--attempt-tts-sample", action="store_true", help="實際產生一小段 TTS 樣本")
    parser.add_argument("--json", default=str(DOCS_DIR / "formal-output-readiness.json"))
    parser.add_argument("--markdown", default=str(DOCS_DIR / "formal-output-readiness.md"))
    args = parser.parse_args()

    report = audit_formal_output_readiness(
        Path(args.config),
        live_network=args.live_network,
        attempt_tts_sample=args.attempt_tts_sample,
    )
    write_reports(report, Path(args.json), Path(args.markdown))
    print(json.dumps({
        "ok": report["ok"],
        "warnings": sum(1 for check in report["checks"] if check["severity"] != "error" and not check["ok"]),
        "failed_required": [
            check["name"]
            for check in report["checks"]
            if check["severity"] == "error" and not check["ok"]
        ],
    }, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
