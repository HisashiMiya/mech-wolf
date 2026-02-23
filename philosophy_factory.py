import time
import os
import re
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from google import genai
from dotenv import load_dotenv

# ---------------------------------------------------------
# 1. 概念錬成の基盤
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DIRS = {k: os.path.join(BASE_DIR, k) for k in ["order", "original", "workspace", "reviews"]}
for d in DIRS.values(): os.makedirs(d, exist_ok=True)

L1_MEMORY_FILE = os.path.join(DIRS["workspace"], "short_term_debate.txt")
L2_MEMORY_FILE = os.path.join(DIRS["workspace"], "core_philosophy.md")

# ---------------------------------------------------------
# 2. 思考エンジン
# ---------------------------------------------------------
GEMINI_MODEL = os.getenv("GEMINI_MODEL")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def call_ai(prompt, role):
    for attempt in range(3):
        try:
            res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            if res.text: return res.text
            raise ValueError("Empty response.")
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                print(f"  ⚠️ 思考過熱({attempt+1}/3): 30秒冷却...")
                time.sleep(30)
            else: raise e
    raise RuntimeError(f"{role} failed.")

def get_latest_v(raw_name):
    files = [f for f in os.listdir(DIRS["workspace"]) if f.startswith(raw_name)]
    versions = [int(m.group(1)) for f in files if (m := re.search(r"_v(\d+)\.", f))]
    return max(versions) if versions else 0

# ---------------------------------------------------------
# 3. 哲人（Librarian） - 普遍的真理の抽出
# ---------------------------------------------------------
def run_philosopher(raw_name, final_review):
    print(f"\n🧠 [PHILOSOPHER ACTIVE] 議論が収束しました。思想の結晶化（L2キャッシュ更新）を開始します。")
    current_l2 = open(L2_MEMORY_FILE, "r", encoding="utf-8").read() if os.path.exists(L2_MEMORY_FILE) else "まだ哲学はない。"

    lib_prompt = f"""Role: 真理の探究者 (Philosopher).
あなたは、今回の激しい議論と試行錯誤から「普遍的な真理や設計思想」を抽出し、長期記憶として定着させる役割を持つ。

【現在のコア哲学 (L2 Cache)】
{current_l2}

【今回の議論の結論 (Review)】
{final_review}

【指令】
上記を統合し、「今後、どのような設計や思想を考える上でも絶対に守るべき黄金律」を【最大5箇条のマークダウンリスト】で出力せよ。
枝葉末節のテクニックは捨て、本質（なぜ失敗するのか、どうあるべきか）のみを残すこと。"""
    
    new_l2 = call_ai(lib_prompt, "Philosopher")
    with open(L2_MEMORY_FILE, "w", encoding="utf-8") as f: f.write(new_l2)
    print("  ✔️ コア哲学 (core_philosophy.md) を昇華しました。")

# ---------------------------------------------------------
# 4. 概念錬成エンジン（Ideation Workflow）
# ---------------------------------------------------------
def run_ideation(target_file, is_new_order=False, loop_count=1):
    MAX_LOOP = 5
    base = os.path.basename(target_file)
    raw = base.split('_v')[0]
    ext = os.path.splitext(base)[1]

    order_path = os.path.join(DIRS["order"], "order.txt")
    order = open(order_path, "r", encoding="utf-8").read().strip() if os.path.exists(order_path) else "現状維持"
    
    if is_new_order and loop_count == 1:
        l1_memory = "【新たな探求の開始】"
        with open(L1_MEMORY_FILE, "w", encoding="utf-8") as f: f.write(l1_memory)
    else:
        l1_memory = open(L1_MEMORY_FILE, "r", encoding="utf-8").read() if os.path.exists(L1_MEMORY_FILE) else ""

    l2_memory = open(L2_MEMORY_FILE, "r", encoding="utf-8").read() if os.path.exists(L2_MEMORY_FILE) else "哲学なし"
    prev_concept = open(target_file, "r", encoding="utf-8").read() if os.path.exists(target_file) else ""

    next_v = get_latest_v(raw) + (1 if is_new_order else 0)
    if next_v == 0: next_v = 1
    save_path = os.path.join(DIRS["workspace"], f"{raw}_v{next_v}{ext}")

    print(f"\n[🌀 CONCEPT EVOLUTION v{next_v}] (Loop: {loop_count}/{MAX_LOOP})")

    # --- PHASE 1: Architect (概念の拡張と再構築) ---
    arch_prompt = f"""Role: 概念構築者 (Concept Architect).
あなたは与えられた思想・設計・戦略を、より高次元の「完成された形」へと昇華させる天才だ。

【探求のテーマ/指令】: {order}
【短期記憶 (直近の議論・反省)】: {l1_memory}
【コア哲学 (絶対の判断基準)】: {l2_memory}
【現在の概念/設計 (これを叩き直せ)】:
{prev_concept}

記憶と哲学に従い、矛盾を排除し、より強固で洗練された【設計・思想の全文】を出力せよ。説明不要。"""
    
    new_concept = call_ai(arch_prompt, "Architect")
    with open(save_path, "w", encoding="utf-8") as f: f.write(new_concept)
    
    # --- PHASE 2: Stress Tester (悪魔の代弁者による極限シミュレーション) ---
    print(f"  🌪️ Stress Test: 概念の耐衝撃テストを実行中...")
    stress_prompt = f"""Role: 悪魔の代弁者 (Red Teamer).
以下の設計・思想に対し、「現実の残酷さ」「極端なエッジケース」「人間の心理的バイアス」をぶつけ、論理が崩壊する【死角】を1つだけ見つけ出せ。
対象概念:
{new_concept}"""
    stress_test_result = call_ai(stress_prompt, "StressTester")
    print(f"  ⚠️ 発見された死角: {stress_test_result.splitlines()[0][:50]}...")

    # --- PHASE 3: Destructive Auditor (極限監査とバトン) ---
    rev_prompt = f"""Role: 破壊的監査官.
あなたは冷徹な論理の番人だ。Architectの概念と、発見された死角を元に、この思想が「本物」か判定せよ。

【対象の概念】: {new_concept}
【発見された死角】: {stress_test_result}

【判断プロトコル（厳守）】
1. 事実と仮定の分離: 願望や物語に引っ張られていないか？
2. 死角先行: 発見された死角によって、この設計は致命的に崩壊しないか？
3. 反証条件: この思想が「間違っていた」と事後確認できる明確な基準はあるか？

【出力形式】
1行目: [STATUS: DONE / CONTINUE / ABORT] (死角への対策が不十分なら必ずCONTINUE)
2行目以降: 【🐾 思考のバトン】として、次のArchitectが解決すべき論理的矛盾や穴を簡潔に書け。"""
    
    review = call_ai(rev_prompt, "Reviewer")
    
    with open(os.path.join(DIRS["reviews"], f"{raw}_v{next_v}_rev.txt"), "w", encoding="utf-8") as f: f.write(review)
    
    l1_match = re.search(r"【🐾 思考のバトン】(.*)", review, re.DOTALL)
    new_l1 = l1_match.group(1).strip() if l1_match else f"STATUS: {review.splitlines()[0]}"
    with open(L1_MEMORY_FILE, "w", encoding="utf-8") as f: f.write(new_l1)

    status_line = review.splitlines()[0]
    if "[STATUS: CONTINUE]" in status_line and loop_count < MAX_LOOP:
        print(f"  🐺 思想に隙あり。再構築へ移行。")
        time.sleep(20)
        run_ideation_safe(save_path, is_new_order=True, loop_count=loop_count + 1)
    elif "[STATUS: DONE]" in status_line:
        print(f"🏁 概念の結晶化完了: v{next_v}")
        run_philosopher(raw, review)
    else:
        print(f"🛑 探求終了: {status_line}")

def run_ideation_safe(path, is_new_order, loop_count):
    try:
        run_ideation(path, is_new_order, loop_count)
    except Exception as e:
        print(f"❌ 致命的エラー: {e}")

# ---------------------------------------------------------
# 5. 起動と監視
# ---------------------------------------------------------
def boot_sequence():
    print("\n" + "="*60)
    print(f"👁️ PHILOSOPHY FACTORY [思想・設計工房] ACTIVE")
    print("="*60)
    originals = [f for f in os.listdir(DIRS["original"]) if os.path.isfile(os.path.join(DIRS["original"], f))]
    for f in originals:
        run_ideation_safe(os.path.join(DIRS["original"], f), is_new_order=True, loop_count=1)

class Handler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.is_directory: return
        if "order.txt" in event.src_path:
            print("\n📡 新たな探求テーマを検知。思考を開始します。")
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