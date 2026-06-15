# 本土語教學影片自動產生器 (video_generator.py)
import os
import sys
import json
import shutil
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, Any, List

# 安全輸出至 Windows 控制台
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import safe_print
print = safe_print

class TaigiVideoGenerator:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.temp_render_dir = Path(tempfile.gettempdir()) / "taigi-video-render"
        self._ensure_temp_setup()

    def _ensure_temp_setup(self):
        """
        確保 Temp 渲染目錄存在，且安裝了 playwright。
        """
        try:
            self.temp_render_dir.mkdir(parents=True, exist_ok=True)
            package_json = self.temp_render_dir / "package.json"
            if not package_json.exists():
                print("[*] 初始化 Temp 目錄的 npm...")
                subprocess.run(
                    ["npm", "init", "-y"],
                    cwd=str(self.temp_render_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=sys.platform.startswith("win")
                )
            
            node_modules = self.temp_render_dir / "node_modules" / "playwright"
            if not node_modules.exists():
                print("[*] 正在 Temp 目錄安裝 Playwright (避開 GDrive)...")
                subprocess.run(
                    ["npm", "install", "playwright"],
                    cwd=str(self.temp_render_dir),
                    check=True,
                    shell=sys.platform.startswith("win")
                )
                print("[*] 正在安裝 Playwright Chromium 瀏覽器...")
                subprocess.run(
                    ["npx", "playwright", "install", "chromium"],
                    cwd=str(self.temp_render_dir),
                    check=True,
                    shell=sys.platform.startswith("win")
                )
        except Exception as e:
            print(f"[!] 警告: 初始化 Playwright 環境時發生異常: {e}")

    def get_audio_duration(self, file_path: str) -> float:
        """
        使用 ffprobe 取得音訊檔的精確秒數，失敗則回傳預設長度 (3.0s)。
        """
        if not file_path or not os.path.exists(file_path):
            return 3.0
        try:
            # 確保使用 Unicode 安全的引號
            cmd = [
                "ffprobe", "-v", "error", 
                "-show_entries", "format=duration", 
                "-of", "default=noprint_wrappers=1:nokey=1", 
                file_path
            ]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            duration = float(result.stdout.strip())
            return duration
        except Exception as e:
            # print(f"  [-] 無法獲取 {os.path.basename(file_path)} 的時長，採用預設值: {e}")
            return 3.0

    def generate_video(self, lesson_json_path: str, output_mp4_path: str) -> bool:
        """
        自動影片生成流水線 (Option C)。
        """
        lesson_json_path = os.path.abspath(lesson_json_path)
        output_mp4_path = os.path.abspath(output_mp4_path)
        input_dir = os.path.dirname(lesson_json_path)
        
        # 建立 output/renders 資料夾
        renders_dir = os.path.join(input_dir, "renders")
        os.makedirs(renders_dir, exist_ok=True)
        
        print(f"[*] 啟動本土語影片生成，輸入: {lesson_json_path}")
        
        if not os.path.exists(lesson_json_path):
            print(f"[-] 錯誤: 找不到輸入的教材大綱 JSON: {lesson_json_path}")
            return False
            
        with open(lesson_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # 1. 計算每頁時間軸 & 產生音訊 block
        print("[*] 正在分析音檔時長，建立音畫時間軸...")
        
        # 建立臨時音軌目錄
        temp_audio_dir = self.temp_render_dir / "temp_audio"
        if temp_audio_dir.exists():
            shutil.rmtree(temp_audio_dir)
        temp_audio_dir.mkdir(parents=True, exist_ok=True)
        
        slide_timings = []
        dialogue_timings = []
        audio_blocks = []
        
        current_time_ms = 0
        block_idx = 0
        
        # --- 1.1 封面時間 (Slide 0) ---
        cover_dur = 5.0 # 封面停留 5 秒
        slide_timings.append({
            "index": 0,
            "type": "cover",
            "start": current_time_ms,
            "duration": cover_dur * 1000
        })
        # 產生封面靜音檔
        cover_wav = temp_audio_dir / f"block_{block_idx:03d}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(cover_dur), "-ar", "44100", "-ac", "2", str(cover_wav)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        audio_blocks.append(str(cover_wav))
        current_time_ms += int(cover_dur * 1000)
        block_idx += 1
        
        # --- 1.2 詞彙教學頁時間 (Slide 1 ~ N) ---
        for idx, vocab in enumerate(data.get("vocabulary", [])):
            hanji = vocab.get("hanji", "")
            # 取得對應音檔 (通常是音訊檔的相對路徑)
            audio_rel_path = vocab.get("audio_file", "")
            audio_full_path = os.path.join(input_dir, audio_rel_path) if audio_rel_path else ""
            
            dur = self.get_audio_duration(audio_full_path)
            total_dur = dur + 2.5 # 語音時長 + 2.5 秒緩衝
            
            slide_timings.append({
                "index": len(slide_timings),
                "type": "vocab",
                "vocab_index": idx,
                "start": current_time_ms,
                "duration": total_dur * 1000
            })
            
            # 生成該詞彙頁的 padded 音訊 block (重新採樣 44100Hz 雙聲道)
            vocab_wav = temp_audio_dir / f"block_{block_idx:03d}.wav"
            if os.path.exists(audio_full_path):
                subprocess.run([
                    "ffmpeg", "-y", "-i", audio_full_path, 
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", 
                    "-filter_complex", "[0:a]aresample=44100[a0];[a0][1:a]concat=n=2:v=0:a=1[a]", 
                    "-map", "[a]", "-t", str(total_dur), "-ar", "44100", "-ac", "2", str(vocab_wav)
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                # 若無音訊，生成靜音
                subprocess.run([
                    "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", 
                    "-t", str(total_dur), "-ar", "44100", "-ac", "2", str(vocab_wav)
                ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
            audio_blocks.append(str(vocab_wav))
            current_time_ms += int(total_dur * 1000)
            block_idx += 1
            
        # --- 1.3 情境對話頁時間 (Slide N+1) ---
        dialogues = data.get("dialogues", [])
        if dialogues:
            dialogue_slide_index = len(slide_timings)
            dialogue_start_time = current_time_ms
            
            dialogue_sub_blocks = []
            dialogue_slide_dur_ms = 0
            
            for idx, dia in enumerate(dialogues):
                audio_rel_path = dia.get("audio_file", "")
                audio_full_path = os.path.join(input_dir, audio_rel_path) if audio_rel_path else ""
                
                dur = self.get_audio_duration(audio_full_path)
                total_dur = dur + 2.0 # 句子語音 + 2.0 秒緩衝
                
                dialogue_timings.append({
                    "index": idx,
                    "start": dialogue_start_time + dialogue_slide_dur_ms,
                    "duration": total_dur * 1000
                })
                
                # 生成該對話句子的音訊 block
                dia_wav = temp_audio_dir / f"block_{block_idx:03d}.wav"
                if os.path.exists(audio_full_path):
                    subprocess.run([
                        "ffmpeg", "-y", "-i", audio_full_path, 
                        "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", 
                        "-filter_complex", "[0:a]aresample=44100[a0];[a0][1:a]concat=n=2:v=0:a=1[a]", 
                        "-map", "[a]", "-t", str(total_dur), "-ar", "44100", "-ac", "2", str(dia_wav)
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.run([
                        "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", 
                        "-t", str(total_dur), "-ar", "44100", "-ac", "2", str(dia_wav)
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                dialogue_sub_blocks.append(str(dia_wav))
                dialogue_slide_dur_ms += int(total_dur * 1000)
                block_idx += 1
                
            slide_timings.append({
                "index": dialogue_slide_index,
                "type": "dialogue",
                "start": dialogue_start_time,
                "duration": dialogue_slide_dur_ms
            })
            audio_blocks.extend(dialogue_sub_blocks)
            current_time_ms += dialogue_slide_dur_ms
            
        # --- 1.4 總結複習頁時間 (Slide N+2) ---
        review_dur = 6.0 # 複習頁顯示 6 秒
        slide_timings.append({
            "index": len(slide_timings),
            "type": "review",
            "start": current_time_ms,
            "duration": review_dur * 1000
        })
        review_wav = temp_audio_dir / f"block_{block_idx:03d}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(review_dur), "-ar", "44100", "-ac", "2", str(review_wav)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        audio_blocks.append(str(review_wav))
        current_time_ms += int(review_dur * 1000)
        block_idx += 1
        
        # --- 1.5 結語頁時間 (Slide N+3) ---
        ending_dur = 4.0 # 結語頁顯示 4 秒
        slide_timings.append({
            "index": len(slide_timings),
            "type": "ending",
            "start": current_time_ms,
            "duration": ending_dur * 1000
        })
        ending_wav = temp_audio_dir / f"block_{block_idx:03d}.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(ending_dur), "-ar", "44100", "-ac", "2", str(ending_wav)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        audio_blocks.append(str(ending_wav))
        current_time_ms += int(ending_dur * 1000)
        block_idx += 1
        
        # 影片總時長
        total_duration_sec = current_time_ms / 1000.0
        print(f"  [+] 影片規劃完成，總頁數: {len(slide_timings)} 頁，影片時長: {total_duration_sec:.2f} 秒")
        
        # 2. 拼接所有音軌區塊為 master 音訊
        print("[*] 正在使用 FFmpeg 拼接音訊，生成 master_audio.mp3...")
        concat_txt_path = temp_audio_dir / "concat_list.txt"
        with open(concat_txt_path, "w", encoding="utf-8") as f_concat:
            for block in audio_blocks:
                # Windows 上路徑的反斜線在 ffmpeg concat 中需要適配或轉斜線
                block_path = block.replace('\\', '/')
                f_concat.write(f"file '{block_path}'\n")
                
        master_audio_path = self.temp_render_dir / "master_audio.mp3"
        subprocess.run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0", 
            "-i", str(concat_txt_path), 
            "-c:a", "libmp3lame", "-b:a", "192k", 
            str(master_audio_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        print("  [+] Master 音軌生成成功。")
        
        # 3. 生成展示用 HTML
        print("[*] 正在產生影片簡報 HTML (套用 taigi-video-specs.md 規格)...")
        
        # 3.1 準備詞彙 Slides HTML
        slides_html = ""
        # 封面 (Slide 0)
        slides_html += f"""
        <div class="slide cover active" style="background-color: #0B3C30; color: #FAF7EE; justify-content: center; align-items: center; text-align: center;">
            <div style="font-size: 110px; font-weight: 900; letter-spacing: 0.05em; line-height: 1.2;">
                {data.get('title', '臺語本土語課程')}
            </div>
            <div style="font-size: 60px; font-weight: 700; color: #E36414; margin-top: 24px; letter-spacing: 0.05em;">
                台語教學影片
            </div>
            <div style="font-size: 32px; color: #C8941F; margin-top: 50px; font-weight: 500;">
                適用年級：{data.get('grade', '國中')} | 片長：約 {int(total_duration_sec)} 秒
            </div>
        </div>
        """
        
        # 詞彙頁
        for idx, vocab in enumerate(data.get("vocabulary", [])):
            img_path = vocab.get("image_file", "")
            # 若有圖片，載入 HTML
            img_html = ""
            if img_path and os.path.exists(os.path.join(input_dir, img_path)):
                # 我們把圖片拷貝到臨時目錄，讓 HTML 讀取相對路徑
                shutil.copy(os.path.join(input_dir, img_path), self.temp_render_dir / os.path.basename(img_path))
                img_html = f'<div class="img-wrapper"><img src="{os.path.basename(img_path)}"></div>'
            else:
                img_html = '<div class="img-wrapper" style="background: #e9ecef; display:flex; align-items:center; justify-content:center; font-size:40px; color:#826252;">無插圖</div>'
                
            slides_html += f"""
            <div class="slide vocab" style="background-color: #FAF7EE;">
                <div class="left-col">
                    {img_html}
                </div>
                <div class="right-col">
                    <div style="font-size: 26px; color: #826252; font-weight: 700; margin-bottom: 20px;">詞彙認讀 — {idx+1}</div>
                    <div class="hanji">{vocab.get('hanji')}</div>
                    <div class="tailo">{vocab.get('tailo_diacritic')}</div>
                    <div class="zh">{vocab.get('zh_tw')}</div>
                    
                    <div style="border-top: 2px solid #C8941F; margin-top: 40px; padding-top: 20px; width: 100%;">
                        <div style="font-size: 22px; color: #826252; font-weight: 700; margin-bottom: 10px;">例句練習</div>
                        <div style="font-size: 40px; font-weight: 700; color: #0B3C30; line-height:1.3;">{vocab.get('sentence_hanji', '')}</div>
                        <div style="font-size: 28px; font-weight: 500; color: #E36414; margin-top: 8px; line-height:1.3;">{vocab.get('sentence_tailo_diacritic', '')}</div>
                    </div>
                </div>
            </div>
            """
            
        # 對話頁
        if dialogues:
            dialogue_rows_html = ""
            for idx, dia in enumerate(dialogues):
                dialogue_rows_html += f"""
                <div class="dialogue-bubble" id="diag-{idx}">
                    <div class="speaker-name">{dia.get('role')}：</div>
                    <div class="dialogue-text">
                        <div style="font-size: 44px; font-weight: 700; color: #0B3C30;">{dia.get('hanji')}</div>
                        <div style="font-size: 30px; font-weight: 500; color: #E36414; margin-top: 5px;">{dia.get('tailo_diacritic')}</div>
                        <div style="font-size: 24px; color: #826252; margin-top: 4px;">({dia.get('zh_tw')})</div>
                    </div>
                </div>
                """
                
            slides_html += f"""
            <div class="slide dialogue" style="background-color: #FAF7EE; justify-content: flex-start; padding-top: 80px;">
                <div style="font-size: 26px; color: #826252; font-weight: 700; width:100%; text-align:center; margin-bottom: 30px;">情境會話認讀 (聽與說)</div>
                <div class="dialogue-container" style="width: 100%; max-width: 1500px; margin: 0 auto; display: flex; flex-direction: column; gap: 24px;">
                    {dialogue_rows_html}
                </div>
            </div>
            """
            
        # 複習總結頁
        review_items_html = ""
        for idx, vocab in enumerate(data.get("vocabulary", [])):
            review_items_html += f"""
            <div class="review-item">
                <span class="num">{idx+1}</span>
                <span class="hj">{vocab.get('hanji')}</span>
                <span class="tl">{vocab.get('tailo_diacritic')}</span>
                <span class="tr">({vocab.get('zh_tw')})</span>
            </div>
            """
            
        slides_html += f"""
        <div class="slide review" style="background-color: #FAF7EE; justify-content: flex-start; padding-top: 80px;">
            <div style="font-size: 26px; color: #826252; font-weight: 700; width:100%; text-align:center; margin-bottom: 40px;">本課核心詞彙複習</div>
            <div class="review-grid">
                {review_items_html}
            </div>
        </div>
        """
        
        # 結語頁 (Ending Slide)
        slides_html += f"""
        <div class="slide ending" style="background-color: #0B3C30; color: #FAF7EE; justify-content: center; align-items: center; text-align: center;">
            <div style="font-size: 80px; font-weight: 900; letter-spacing: 0.05em; color: #C8941F;">
                多謝觀看！
            </div>
            <div style="font-size: 40px; font-weight: 700; color: #FAF7EE; margin-top: 24px;">
                Tō-siā koan-khàn!
            </div>
            <div style="font-size: 28px; color: rgba(250,247,238,0.7); margin-top: 40px;">
                請多加練習，我們下次再見！
            </div>
        </div>
        """
        
        # 整合 HTML 範本
        html_content = f"""<!DOCTYPE html>
<html lang="zh-Hant">
<head>
  <meta charset="UTF-8">
  <title>教學影片渲染</title>
  <style>
    :root {{
      --paper: #FAF7EE;
      --forest: #0B3C30;
      --coral: #E36414;
      --gold: #C8941F;
      --mud: #826252;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{
      width: 1920px;
      height: 1080px;
      overflow: hidden;
      font-family: "Noto Sans CJK TC", "Microsoft JhengHei", sans-serif;
    }}
    .stage {{
      position: relative;
      width: 1920px;
      height: 1080px;
      background: var(--forest);
    }}
    .slide {{
      position: absolute;
      inset: 0;
      padding: 60px 100px;
      opacity: 0;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: center;
      transition: opacity 0.4s ease;
    }}
    .slide.active {{
      opacity: 1;
    }}
    
    /* 詞彙頁左右排版 */
    .slide.vocab {{
      display: flex;
      flex-direction: row;
      justify-content: space-between;
      align-items: center;
      gap: 60px;
    }}
    .left-col {{
      flex: 4;
      display: flex;
      justify-content: center;
      align-items: center;
    }}
    .right-col {{
      flex: 6;
      display: flex;
      flex-direction: column;
      justify-content: center;
      align-items: flex-start;
      text-align: left;
    }}
    .img-wrapper {{
      border: 4px solid var(--gold);
      border-radius: 16px;
      box-shadow: 0 10px 25px rgba(0,0,0,0.1);
      overflow: hidden;
      width: 460px;
      height: 460px;
    }}
    .img-wrapper img {{
      width: 100%;
      height: 100%;
      object-fit: cover;
    }}
    
    /* 文字尺寸 */
    .hanji {{
      font-size: 110px;
      font-weight: 900;
      color: var(--forest);
      line-height: 1.1;
    }}
    .tailo {{
      font-size: 60px;
      font-weight: 700;
      color: var(--coral);
      margin-top: 12px;
      line-height: 1.1;
    }}
    .zh {{
      font-size: 40px;
      font-weight: 500;
      color: var(--mud);
      margin-top: 16px;
    }}
    
    /* 對話氣泡 */
    .dialogue-bubble {{
      background-color: #ffffff;
      border: 1px solid #e2e8f0;
      border-radius: 16px;
      padding: 24px 40px;
      display: flex;
      gap: 20px;
      opacity: 0.35;
      transform: scale(0.97);
      transition: all 0.4s ease;
      box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }}
    .dialogue-bubble.active {{
      opacity: 1;
      transform: scale(1.0);
      border-color: var(--gold);
      border-width: 2px;
      box-shadow: 0 10px 20px rgba(11,60,48,0.08);
    }}
    .speaker-name {{
      font-size: 36px;
      font-weight: 900;
      color: var(--forest);
      min-width: 150px;
    }}
    .dialogue-text {{
      flex: 1;
    }}
    
    /* 複習網格 */
    .review-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 30px;
      width: 100%;
      max-width: 1600px;
      margin: 0 auto;
    }}
    .review-item {{
      background: #ffffff;
      border-left: 6px solid var(--forest);
      padding: 20px 30px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      gap: 20px;
      box-shadow: 0 4px 6px rgba(0,0,0,0.02);
    }}
    .review-item .num {{
      background: var(--primary-light, #edf6f2);
      color: var(--forest);
      width: 44px;
      height: 44px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: bold;
      font-size: 20px;
    }}
    .review-item .hj {{
      font-size: 48px;
      font-weight: 900;
      color: var(--forest);
    }}
    .review-item .tl {{
      font-size: 28px;
      font-weight: 700;
      color: var(--coral);
      flex: 1;
    }}
    .review-item .tr {{
      font-size: 24px;
      color: var(--mud);
    }}
    
    /* 點擊開始畫面 ( render 模式下隱藏 ) */
    #startScreen {{
      position: absolute;
      inset: 0;
      background: var(--forest);
      color: #FAF7EE;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      z-index: 999;
      cursor: pointer;
      gap: 30px;
    }}
    #startScreen.hidden {{
      display: none;
    }}
  </style>
</head>
<body>
  <div class="stage">
    {slides_html}
    
    <!-- 點擊播放按鈕遮罩 -->
    <div id="startScreen" onclick="startPlay()">
      <div style="font-size: 80px; font-weight: 900;">臺語本土語影片生成器</div>
      <div style="font-size: 32px; color: rgba(250,247,238,0.7);">點擊開始預覽播放</div>
      <div style="width: 100px; height: 100px; border: 3px solid var(--gold); border-radius:50%; display:flex; align-items:center; justify-content:center; font-size:40px; color:var(--gold);">▶</div>
    </div>
  </div>

  <script>
    const SLIDE_TIMINGS = {json.dumps(slide_timings)};
    const DIALOGUE_TIMINGS = {json.dumps(dialogue_timings)};
    
    // 檢查網址參數是否含有 ?render=true
    const urlParams = new URLSearchParams(window.location.search);
    const isRenderMode = urlParams.get('render') === 'true';
    
    if (isRenderMode) {{
      // 錄製模式下直接隱藏遮罩並自動播放
      document.getElementById('startScreen').classList.add('hidden');
      window.onload = () => {{
        setTimeout(startPresentation, 500); // 留一點緩衝時間
      }};
    }}
    
    function startPlay() {{
      document.getElementById('startScreen').classList.add('hidden');
      startPresentation();
    }}
    
    function showSlide(index) {{
      console.log("Switching to slide:", index);
      const slides = document.querySelectorAll('.slide');
      slides.forEach((s, i) => {{
        s.classList.toggle('active', i === index);
      }});
    }}
    
    function highlightDialogue(index) {{
      console.log("Highlighting dialogue bubble:", index);
      const bubbles = document.querySelectorAll('.dialogue-bubble');
      bubbles.forEach((b, i) => {{
        b.classList.toggle('active', i === index);
      }});
    }}
    
    function startPresentation() {{
      console.log("Presentation started...");
      
      // 1. 設定 Slides 切換排程
      for (let s of SLIDE_TIMINGS) {{
        setTimeout(() => {{
          showSlide(s.index);
        }}, s.start);
      }}
      
      // 2. 設定對話高亮排程
      for (let d of DIALOGUE_TIMINGS) {{
        setTimeout(() => {{
          highlightDialogue(d.index);
        }}, d.start);
      }}
    }}
  </script>
</body>
</html>
"""
        html_out_path = self.temp_render_dir / "index.html"
        with open(html_out_path, "w", encoding="utf-8") as f_html:
            f_html.write(html_content)
        print("  [+] HTML 簡報檔案生成成功。")

        # 4. 寫入錄影腳本 record.js
        print("[*] 正在寫入 Playwright 錄影腳本...")
        # 為了使 record.js 在 cmd 執行時不衝突，使用 CJS 格式的 record.js
        record_js_content = f"""
const {{ chromium }} = require('playwright');
const path = require('path');

(async () => {{
  console.log('Launch browser...');
  const browser = await chromium.launch({{
    args: ['--autoplay-policy=no-user-gesture-required', '--mute-audio'],
  }});
  const context = await browser.newContext({{
    viewport: {{ width: 1920, height: 1080 }},
    deviceScaleFactor: 1,
    recordVideo: {{ dir: __dirname, size: {{ width: 1920, height: 1080 }} }},
  }});
  
  const page = await context.newPage();
  const fileUrl = 'file:///' + path.join(__dirname, 'index.html').split(path.sep).join('/') + '?render=true';
  console.log('Navigate to:', fileUrl);
  await page.goto(fileUrl);
  
  // 等待字型載入
  await page.waitForTimeout(1000);
  
  const durationMs = {int(current_time_ms + 1000)};
  console.log('Recording video for ' + durationMs + ' ms...');
  await page.waitForTimeout(durationMs);
  
  // 取得影片物件並在 context.close() 前抓取暫存路徑
  const video = page.video();
  let videoPath = "";
  if (video) {{
    videoPath = await video.path();
    console.log('Playwright temporary video path:', videoPath);
  }}
  
  await context.close();
  await browser.close();
  console.log('Playwright complete.');
  
  // 將產出的影片路徑寫到一個 txt 檔，方便 Python 讀取
  if (videoPath) {{
    const fs = require('fs');
    fs.writeFileSync(path.join(__dirname, 'video_path.txt'), videoPath);
  }}
}})();
"""
        record_js_path = self.temp_render_dir / "record.js"
        with open(record_js_path, "w", encoding="utf-8") as f_rec:
            f_rec.write(record_js_content)
            
        # 5. 執行 Playwright 錄影
        print("[*] 執行 Playwright 錄影 (這需要一點時間)...")
        # 設定 NODE_PATH
        env = os.environ.copy()
        env["NODE_PATH"] = str(self.temp_render_dir / "node_modules")
        
        rec_res = subprocess.run(
            ["node", "record.js"],
            cwd=str(self.temp_render_dir),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=sys.platform.startswith("win")
        )
        
        if rec_res.returncode != 0:
            print(f"[-] 錄影腳本執行失敗: {rec_res.stderr}")
            return False
            
        print("  [+] Playwright 錄影完成。")
        
        # 6. 取得 WebM 檔案路徑
        path_txt = self.temp_render_dir / "video_path.txt"
        if not path_txt.exists():
            print("[-] 錯誤: 錄影腳本未寫入影片路徑文字檔。")
            return False
            
        with open(path_txt, "r", encoding="utf-8") as f_path:
            webm_path = f_path.read().strip()
            
        if not os.path.exists(webm_path):
            print(f"[-] 錯誤: 找不到錄好的 WebM 影片: {webm_path}")
            return False
            
        # 7. MUX 音畫合成
        print("[*] 正在執行 FFmpeg 音畫合併...")
        # 確保 output 資料夾存在
        os.makedirs(os.path.dirname(output_mp4_path), exist_ok=True)
        
        # 合併指令 (加入 -map 0:v:0 -map 1:a:0 防止 WebM 預設覆蓋音訊，加上最長/最短切除)
        mux_cmd = [
            "ffmpeg", "-y", 
            "-i", webm_path, 
            "-i", str(master_audio_path),
            "-map", "0:v:0", 
            "-map", "1:a:0",
            "-c:v", "libx264", 
            "-crf", "20", 
            "-pix_fmt", "yuv420p", 
            "-c:a", "aac", 
            "-b:a", "192k", 
            "-shortest", 
            output_mp4_path
        ]
        
        mux_res = subprocess.run(mux_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if mux_res.returncode != 0:
            print(f"[-] FFmpeg 合併失敗: {mux_res.stderr}")
            return False
            
        print(f"  [+] 成功產生最終教學影片: {output_mp4_path}")
        
        # 8. 清理工作目錄
        try:
            # 刪除臨時 wav blocks
            shutil.rmtree(temp_audio_dir)
            # 刪除影片路徑 txt 和 master_audio
            if path_txt.exists():
                os.remove(path_txt)
            if master_audio_path.exists():
                os.remove(master_audio_path)
            # 刪除 webm
            if os.path.exists(webm_path):
                os.remove(webm_path)
        except Exception as e:
            # 優雅地忽略清理失敗
            pass
            
        return True

if __name__ == "__main__":
    # 支援命令列直接執行
    import argparse
    parser = argparse.ArgumentParser(description="台語本土語影片自動編譯器")
    parser.add_argument("--input", required=True, help="教材大綱 JSON 檔案路徑")
    parser.add_argument("--output", default="output/lesson_video.mp4", help="輸出影片 MP4 檔案路徑")
    parser.add_argument("--config", default="config.json", help="專案設定檔路徑")
    
    args = parser.parse_args()
    
    gen = TaigiVideoGenerator(config_path=args.config)
    success = gen.generate_video(args.input, args.output)
    if success:
        print(f"[+] 影片產生成功: {args.output}")
        sys.exit(0)
    else:
        print("[-] 影片產生失敗")
        sys.exit(1)
