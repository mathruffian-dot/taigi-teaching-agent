# 共享公用模組 (utils.py)
import os
import sys
import builtins


def resolve_output_base_dir(config, default="output"):
    """
    讀取 config 的 output.base_dir 並展開環境變數與 ~。
    config.json 會隨雲端硬碟在多台電腦間同步，base_dir 若寫死絕對路徑
    （如 C:\\Users\\<使用者>\\...）換一台電腦就會失效，
    故建議寫 %USERPROFILE%\\2026本土語\\output，由此函式展開。
    """
    raw = (config.get("output") or {}).get("base_dir") or default
    return os.path.expandvars(os.path.expanduser(raw))

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
