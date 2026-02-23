import time
import os
import re
import subprocess
import sys
import hashlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from google import genai
from dotenv import load_dotenv

# ---------------------------------------------------------
# 1. 物理的基盤（DEGRADATION PREVENTION & MEMORY SYSTEM）
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DIRS = {k: os.path.join(BASE_DIR, k) for k in ["order", "original", "workspace", "reviews"]}
for d in DIRS.values(): os.makedirs(d, exist_ok=True)

# 記憶の階層
L1_MEMORY_FILE = os.path.join(DIRS["workspace"], "memory.txt")       # 短期記憶（次ターンへのバトン）
L2_MEMORY_FILE = os.path.join(DIRS["workspace"], "core_lessons.md")  # 長期記憶（絶対不変の黄金律）

# ---------------------------------------------------------
# 2. ユーティリティ（API・検証・世代管理）
# ---------------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def call_ai(prompt, role):
    for attempt in range(3):
        try:
            res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            if res.text: return res.text
            raise ValueError("API returned empty response.")
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"  ⚠️ 制限到達({attempt+1}/3): 30秒待機...")
                time.sleep(30)
            else: raise e
    raise RuntimeError(f"{role} failed.")

def get_latest_v(raw_name):
    files = [f for f in os.listdir(DIRS["workspace"]) if f.startswith(raw_name)]
    versions = [int(m.group(1)) for f in files if (m := re.search(r"_v(\d+)\.", f))]
    return max(versions) if versions else 0

def run_reality_check(file_path):
    ext = os.path.splitext(file_path)[1]
    if ext == ".py":
        res = subprocess.run([sys.executable, "-m", "py_compile", file_path], capture_output=True, text=True)
        return "PASS (Syntax OK)" if res.returncode == 0 else f"FAIL (Syntax Error):\n{res.stderr}"
    return f"UNKNOWN_EXT ({ext})"

# ---------------------------------------------------------
# 3. 記憶整理官（Librarian） - 睡眠時の教訓抽出
# ---------------------------------------------------------
def run_librarian(raw_name, final_review):
    print(f"\n🧠 [LIBRARIAN ACTIVE] 狩りが完了しました。記憶の整理（L2キャッシュ更新）を開始します。")
    
    # 現在の長期記憶を取得
    current_l2 = open(L2_MEMORY_FILE, "r", encoding="utf-8").read() if os.path.exists(L2_MEMORY_FILE) else "まだ教訓はない。"

    lib_prompt = f"""Role: Librarian (記憶整理官).
あなたは過去の失敗から普遍的な教訓を抽出し、AIが二度と愚かなミスを繰り返さないための「黄金律」を管理する存在だ。

【現在の長期記憶 (L2 Cache)】
{current_l2}

【今回の狩りの最終結果 (Review)】
{final_review}

【指令】
上記を統合し、「このプロジェクトにおいて、絶対に犯してはならないルールや、得られた新しい設計指針」を【最大5箇条のマークダウンリスト】で出力せよ。
古くて不要になったルールは捨て、本質的な教訓だけを残すこと。出力は5箇条のリストのみとし、挨拶や解説は一切不要。"""
    
    new_l2 = call_ai(lib_prompt, "Librarian")
    
    with open(L2_MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write(new_l2)
    print("  ✔️ 長期記憶 (core_lessons.md) を最適化・更新しました。")

# ---------------------------------------------------------
# 4. 実行エンジン（Agentic Workflow with Memory）
# ---------------------------------------------------------
def run_evolution(target_file, is_new_order=False, loop_count=1):
    MAX_LOOP = 5
    base = os.path.basename(target_file)
    raw = base.split('_v')[0]
    ext = os.path.splitext(base)[1]

    # 指令の取得
    order_path = os.path.join(DIRS["order"], "order.txt")
    order = open(order_path, "r", encoding="utf-8").read().strip() if os.path.exists(order_path) else "現状維持"
    
    # 記憶のロード
    if is_new_order and loop_count == 1:
        # 新規指令時は短期記憶のみリセット
        l1_memory = "INITIAL_STATE"
        with open(L1_MEMORY_FILE, "w", encoding="utf-8") as f: f.write(l1_memory)
    else:
        l1_memory = open(L1_MEMORY_FILE, "r", encoding="utf-8").read() if os.path.exists(L1_MEMORY_FILE) else "NO_L1_MEMORY"

    l2_memory = open(L2_MEMORY_FILE, "r", encoding="utf-8").read() if os.path.exists(L2_MEMORY_FILE) else "NO_L2_MEMORY"

    # 前世代の確保
    prev_code = open(target_file, "r", encoding="utf-8").read() if os.path.exists(target_file) else ""

    next_v = get_latest_v(raw) + (1 if is_new_order else 0)
    if next_v == 0: next_v = 1
    save_path = os.path.join(DIRS["workspace"], f"{raw}_v{next_v}{ext}")

    print(f"\n[🐺 EVOLVING v{next_v}] (Loop: {loop_count}/{MAX_LOOP})")

    # --- PHASE 1: Architect (記憶を参照した生成) ---
    arch_prompt = f"""Role: Architect.
【指令】: {order}
【短期記憶 (直近の反省)】: {l1_memory}
【長期記憶 (絶対の黄金律)】:
{l2_memory}

【前世代のコード (これをデグレさせるな)】:
{prev_code}

記憶と指令に従い、修正したコードのみを全文出力せよ。説明不要。"""
    
    new_code = call_ai(arch_prompt, "Architect")
    with open(save_path, "w", encoding="utf-8") as f: f.write(new_code)
    
    # --- PHASE 2: Reality Check ---
    test_res = run_reality_check(save_path)
    print(f"  🔬 Test: {test_res.splitlines()[0]}")

    # --- PHASE 3: Reviewer (破壊的監査とバトン作成) ---
    rev_prompt = f"""Role: Destructive Auditor.
前世代と比較し、指令の達成度とデグレの有無を監査せよ。

【比較対象】
前世代: {prev_code[:2000]}...
今回生成: {new_code[:2000]}...
物理テスト: {test_res}
指令: {order}

【出力形式厳守】
1行目: [STATUS: DONE / CONTINUE / ABORT] (デグレやエラーがあれば必ずCONTINUE)
2行目以降: 【🐾 短期記憶のバトン】として、次のArchitectが修正すべき点を簡潔に書け。"""
    
    review = call_ai(rev_prompt, "Reviewer")
    
    # レビューの保存と短期記憶(L1)の更新
    with open(os.path.join(DIRS["reviews"], f"{raw}_v{next_v}_rev.txt"), "w", encoding="utf-8") as f: f.write(review)
    
    l1_match = re.search(r"【🐾 短期記憶のバトン】(.*)", review, re.DOTALL)
    new_l1 = l1_match.group(1).strip() if l1_match else f"STATUS: {review.splitlines()[0]}"
    with open(L1_MEMORY_FILE, "w", encoding="utf-8") as f: f.write(new_l1)

    # --- PHASE 4: 自律判定とLibrarianの起動 ---
    status_line = review.splitlines()[0]
    if "[STATUS: CONTINUE]" in status_line and loop_count < MAX_LOOP:
        print(f"  🐺 追跡継続。エラーまたは未達あり。")
        time.sleep(20)
        run_evolution_safe(save_path, is_new_order=True, loop_count=loop_count + 1)
    elif "[STATUS: DONE]" in status_line:
        print(f"🏁 MISSION COMPLETE: v{next_v}")
        # 狩り完了時のみ、Librarianを起動して長期記憶(L2)を整理する
        run_librarian(raw, review)
    else:
        print(f"🛑 EXIT: {status_line}")

def run_evolution_safe(path, is_new_order, loop_count):
    try:
        run_evolution(path, is_new_order, loop_count)
    except Exception as e:
        print(f"❌ 致命的エラー: {e}")

# ---------------------------------------------------------
# 5. 起動と監視
# ---------------------------------------------------------
def boot_sequence():
    print("\n" + "="*60)
    print(f"🐺 MECH-WOLF v6.0 [SELF-EVOLUTION MEMORY SYSTEM]")
    print("="*60)
    originals = [f for f in os.listdir(DIRS["original"]) if os.path.isfile(os.path.join(DIRS["original"], f))]
    for f in originals:
        run_evolution_safe(os.path.join(DIRS["original"], f), is_new_order=True, loop_count=1)

class Handler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory: return
        if "order.txt" in event.src_path:
            print("\n📡 指令更新を検知。群れを解き放ちます。")
            boot_sequence()

if __name__ == "__main__":
    boot_sequence()
    obs = Observer()
    obs.schedule(Handler(), BASE_DIR, recursive=True)
    obs.start()
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        obs.stop()
    obs.join()