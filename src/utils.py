# 共享公用模組 (utils.py)
import sys
import builtins

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
