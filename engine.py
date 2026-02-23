import os
import glob
import time
from google import genai
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

DIRS = {k: os.path.join(BASE_DIR, k) for k in ["order", "workspace", "stages"]}
for d in DIRS.values(): os.makedirs(d, exist_ok=True)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

def call_llm(prompt):
    for attempt in range(3):
        try:
            res = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            if res.text: return res.text
            raise ValueError("Empty response")
        except Exception as e:
            if "429" in str(e): time.sleep(30)
            else: raise e
    raise RuntimeError("LLM API failed.")

def run_pipeline():
    print("🚀 [ENGINE START] Universal Pipeline Processing...")
    
    # 1. 目的（Order）の読み込み
    order_path = os.path.join(DIRS["order"], "order.txt")
    if not os.path.exists(order_path):
        print("🛑 停止: order.txt がありません。")
        return
    current_context = open(order_path, "r", encoding="utf-8").read().strip()
    print(f"📄 ORDER LOADED: {current_context[:50]}...")

    # 2. Stages（外部プロンプト群）の取得と順次実行
    stage_files = sorted(glob.glob(os.path.join(DIRS["stages"], "*.txt")))
    if not stage_files:
        print("🛑 停止: stages/ にプロンプトファイルがありません。")
        return

    for stage_file in stage_files:
        stage_name = os.path.basename(stage_file)
        print(f"\n⚙️ [STAGE EXECUTING]: {stage_name}")
        
        # 外部ファイルから「このステージでのAIの役割・思想・指示」を読み込む
        stage_instruction = open(stage_file, "r", encoding="utf-8").read().strip()
        
        # プロンプトの合成：【ステージの指示】＋【前段までの文脈/結果】
        combined_prompt = f"""
{stage_instruction}

【現在の文脈 / 前ステージからの入力】:
{current_context}
"""
        # AI実行
        result = call_llm(combined_prompt)
        
        # 結果の保存と、次ステージへのバトンタッチ（Contextの更新）
        out_path = os.path.join(DIRS["workspace"], f"output_{stage_name}")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(result)
        
        current_context = result # 出力を次の入力とする（パイプライン）
        print(f"✔️ {stage_name} 完了。結果をworkspaceに出力しました。")

    print("\n🏁 [ENGINE FINISHED] 全ステージのパイプライン処理が完了しました。")

if __name__ == "__main__":
    run_pipeline()