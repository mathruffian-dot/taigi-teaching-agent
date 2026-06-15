# 本地語音 API 服務器 (server.py)
import os
import sys
import tempfile
import uvicorn
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# 將當前目錄與父目錄加入搜尋路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
sys.path.append(os.path.dirname(current_dir))

from stt.generator import TaigiSTT

app = FastAPI(title="Taigi ASR Local Server")

# 以專案根目錄的 config.json 為準（避免以 src 為工作目錄啟動時讀不到設定而默默降級為 dummy）
project_root = os.path.dirname(current_dir)
config_path = os.path.join(project_root, "config.json")

# 啟動時建立單一 STT 實例並重用，避免每次請求重新載入 whisper 模型（耗時且吃記憶體）
stt = TaigiSTT(config_path)

# 設定 CORS 中間件，允許離線網頁 (file:/// 協議) 跨網域請求
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "status": "ok",
        "message": "Taigi ASR Local Server is running. Ready for speech-to-text requests."
    }

@app.post("/api/stt")
async def speech_to_text_endpoint(
    file: UploadFile = File(...),
    target_text: str = Form("")
):
    """
    語音轉文字 API 接口
    - file: 瀏覽器錄音上傳的音訊檔案 (一般為 audio/webm 或 audio/wav)
    - target_text: 預期的台語漢字，用於 Dummy ASR 模擬比對
    """
    # 決定副檔名並保存為臨時檔案
    suffix = os.path.splitext(file.filename)[1] if file.filename else ".webm"
    if not suffix:
        suffix = ".webm"
        
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, f"upload_{os.urandom(8).hex()}{suffix}")
    
    try:
        # 寫入上傳的音訊資料
        with open(temp_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
            
        # 使用啟動時建立的全域 STT 實例執行辨識（模型已快取）
        recognized_text = stt.speech_to_text(temp_path, target_text)
        return {"text": recognized_text}
        
    except Exception as e:
        print(f"[-] 伺服器處理 ASR 發生異常: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
        
    finally:
        # 清除臨時檔案
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

if __name__ == "__main__":
    # 啟動本地伺服器，運行於 127.0.0.1:8000
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
