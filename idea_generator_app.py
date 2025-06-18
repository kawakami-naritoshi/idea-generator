import streamlit as st
import pandas as pd
import re
import time
import os
from PIL import Image
from io import BytesIO

# ======================================================
# 1. Streamlit アプリの設定
# ======================================================

st.set_page_config(page_title="Idea AI Generator II", layout="wide")

# アプリ名称を適度に目立たせる
st.markdown("""
<style>
    .app-header {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 8px;
        margin-bottom: 1.5rem;
        border-left: 5px solid #4285F4;
    }
    .app-title {
        font-size: 2.2rem;
        font-weight: 600;
        color: #333;
        margin: 0;
    }
    .app-subtitle {
        font-size: 1.1rem;
        color: #666;
        margin-top: 0.5rem;
    }
</style>

<div class="app-header">
    <h1 class="app-title">Idea AI Generator II</h1>
    <p class="app-subtitle">特許データベースから革新的なソリューションを生成するAIアプリ</p>
</div>
""", unsafe_allow_html=True)

# ======================================================
# 2. 必要なライブラリのインポート
# ======================================================

# Google Gemini関連のインポート
try:
    # テキスト生成用のインポート
    import google.generativeai as genai
    # 画像生成用のインポート
    from google import genai as genai_client
    from google.genai import types
except ImportError:
    st.error("""
    **Google Generative AIパッケージがインストールされていません。**
    
    以下のコマンドを実行してインストールしてください：
    ```
    pip install -r requirements.txt
    ```
    
    または個別にインストールする場合：
    ```
    pip install google-generativeai
    pip install streamlit pandas pillow
    ```
    """)
    st.stop()

# ======================================================
# 3. ユーティリティ関数
# ======================================================

def extract_percentage(percentage_str):
    """文字列からパーセンテージの数値を抽出する関数"""
    try:
        # 数字のみを抽出
        match = re.search(r'(\d+(?:\.\d+)?)', str(percentage_str))
        if match:
            return float(match.group(1))
        return 0.0
    except Exception:
        return 0.0

def load_data(uploaded_file):
    """アップロードされたExcelファイルからデータを読み込む関数"""
    try:
        df = pd.read_excel(uploaded_file)
        st.success(f"データの読み込みに成功しました。行数: {len(df)}行")
        return df
    except Exception as e:
        st.error(f"データの読み込み中にエラーが発生しました: {e}")
        return None

# ======================================================
# 4. Gemini関連の関数
# ======================================================

def calculate_wait_time(model):
    """モデルに基づいて適切な待機時間を計算する関数"""
    if model == "gemini-2.0-flash-lite":
        # 30RPM（1分間に30リクエスト）の制限に対応
        return 60 / 30  # 1リクエストあたり2秒
    # 他のモデルの場合は短い待機時間を返す
    return 0.1

def generate_relevance_gemini(api_key, text, query, progress_bar=None, progress_count=None, total_items=None, max_retries=3, backoff_time=2):
    """Gemini APIを使用して、テキストとクエリの関連度を評価する関数"""
    # モデル名を固定
    model = "gemini-2.0-flash-lite"
    
    # Gemini APIの設定
    genai.configure(api_key=api_key)
    
    # プロンプトの作成
    prompt = f"""次の文章の内容と、「{query}」という文章との関連性を人間の感覚で判断し、パーセンテージで示してください。
出力はパーセンテージの数値のみでお願いします。例えば「75%」ではなく「75」のように数字だけを出力してください。

文章:
{text}"""

    # Gemini APIの呼び出し
    for attempt in range(max_retries):
        try:
            model_instance = genai.GenerativeModel(model)
            response = model_instance.generate_content(prompt)
            
            # 進捗バーを更新
            if progress_bar is not None and progress_count is not None and total_items is not None:
                progress_bar.progress(progress_count / total_items)
                
            return response.text.strip()
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = backoff_time * (2 ** attempt)  # 指数バックオフ
                st.warning(f"Gemini APIエラー: {e}。{sleep_time}秒待機します...")
                time.sleep(sleep_time)
            else:
                st.error(f"Gemini API最大リトライ回数に達しました。エラー: {e}")
                raise

def generate_solution_gemini(api_key, text, query, product_type, max_retries=3, backoff_time=2):
    """Gemini APIを使用して、ソリューション案を生成する関数"""
    # モデル名を固定
    model = "gemini-2.5-flash"
    
    # Gemini APIの設定
    genai.configure(api_key=api_key)

    # プロンプトの作成
    prompt = f"""次の文章は、「{query}」という要求に関連する技術の文章群です。
これら文章群の内容を組合わせて、{query}というニーズに対応する{product_type}の新規なソリューション案を考えてください。
以下の4つの観点から説明してください：
1. 製品名：製品のキャッチーな名称
2. 製品コンセプト：3-4行程度の製品の全体像の説明 
3. ユーザー体験：一般ユーザーに訴求する物語風の文章
4. 製品ソリューション詳細：技術者に訴求する具体的な成分や仕組みを示す技術的に詳細な文章

文章群:
{text}"""

    # Gemini APIの呼び出し
    for attempt in range(max_retries):
        try:
            model_instance = genai.GenerativeModel(model)
            response = model_instance.generate_content(prompt)
            return response.text
        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = backoff_time * (2 ** attempt)  # 指数バックオフ
                st.warning(f"Gemini APIエラー: {e}。{sleep_time}秒待機します...")
                time.sleep(sleep_time)
            else:
                st.error(f"Gemini API最大リトライ回数に達しました。エラー: {e}")
                raise

def generate_image_from_solution(api_key, solution_text, query, product_type, max_retries=3, backoff_time=2):
    """Gemini APIを使用して、ソリューション案から画像を生成する関数"""
    # モデル名を固定
    model = "gemini-2.0-flash-preview-image-generation"
    
    # 画像生成用のGemini API設定
    # APIキーを環境変数にセット
    os.environ["GOOGLE_API_KEY"] = api_key
    client = genai_client.Client()

    # プロンプトの作成（ソリューション内容に基づいた画像生成プロンプト）
    prompt = f"""以下は{product_type}に関するソリューション案の文章です。
・この文章からソリューションの特徴（外観、材質、形状、機能など）を理解し、その特徴を反映したリアルな製品の写真を生成してください。
・必ず製品が明確に見える構図で、特徴が分かる美しい写真にしてください。
・ソリューション案に記載されている「ユーザー体験」や物語のシーンの中でのソリューションを視覚化してください。
・登場する人物の表情は幸せそうで、楽しんでいる雰囲気を出した写真としてください。

ソリューション案:
{solution_text[:10000]}"""  # 10000字制限としてAPIに渡す

    # Gemini画像生成APIの呼び出し
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['Text', 'Image']
                )
            )

            # 画像の取得
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    image = Image.open(BytesIO(part.inline_data.data))
                    return image

            st.warning("画像が生成されませんでした。")
            return None

        except Exception as e:
            if attempt < max_retries - 1:
                sleep_time = backoff_time * (2 ** attempt)  # 指数バックオフ
                st.warning(f"Gemini 画像生成APIエラー: {e}。{sleep_time}秒待機します...")
                time.sleep(sleep_time)
            else:
                st.error(f"Gemini 画像生成API最大リトライ回数に達しました。エラー: {e}")
                return None

# ======================================================
# 5. アプリのレイアウト設定
# ======================================================

# サイドバーの設定
with st.sidebar:
    st.header("設定")
    
    # APIキー入力
    gemini_api_key = st.text_input("Google Gemini API キー", type="password", help="関連度評価、ソリューション生成、画像生成に使用されます", key="gemini_api_key")
    
    # モデル設定（固定）
    st.info("モデル設定：\n- 関連度評価: gemini-2.0-flash-lite\n- ソリューション生成: gemini-2.5-flash\n- 画像生成: gemini-2.0-flash-preview-image-generation")
    
    # ファイルアップロード
    uploaded_file = st.file_uploader("特許データベース (Excel)", type=["xlsx"], help="特許データを含むExcelファイル", key="patent_excel_file")
    
    # 高度な設定（折りたたみ可能）
    with st.expander("高度な設定", expanded=False):
        top_n = st.slider("抽出する関連特許数", 5, 50, 20, help="関連度の高い上位何件を使用するか", key="top_n_slider")
        max_retries = st.slider("API最大リトライ回数", 1, 10, 3, help="API呼び出しに失敗した場合のリトライ回数", key="max_retries_slider")
        backoff_time = st.slider("初期バックオフ時間（秒）", 1, 10, 2, help="リトライ間の待機時間の初期値", key="backoff_time_slider")

# メインエリアの入力
st.header("ソリューション生成")
user_query = st.text_input("あなたのニーズを入力してください", "環境に優しい包装材が欲しい", key="user_query")
product_type = st.text_input("製品カテゴリ（例：飲料、食品、電子機器、化粧品など）", "飲料", key="product_type")

# ======================================================
# 6. メイン処理
# ======================================================

# 分析開始ボタンを目立たせる
st.markdown("""
<style>
    .start-button-container {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 1rem;
        margin: 1.5rem 0;
        text-align: center;
        border: 1px solid #e9ecef;
    }
    .start-button-info {
        font-size: 0.95rem;
        color: #666;
        margin-bottom: 0.75rem;
    }
    /* ボタンのカスタマイズ */
    .stButton > button {
        background-color: #4285F4;
        color: white;
        font-size: 1.1rem;
        font-weight: 500;
        padding: 0.6rem 2rem;
        border-radius: 6px;
        border: none;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
        transition: all 0.2s ease;
    }
    .stButton > button:hover {
        background-color: #3367D6;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.15);
        transform: translateY(-2px);
    }
</style>

<div class="start-button-container">
    <p class="start-button-info">設定が完了したら左下の「分析開始」ボタンを押してください</p>
</div>
""", unsafe_allow_html=True)

# 分析開始ボタン
start_analysis = st.button("🔍 分析開始", key="start_button")

if start_analysis:
    # 入力チェック
    if not uploaded_file:
        st.error("特許データベースのExcelファイルをアップロードしてください。")
        st.stop()
    
    if not gemini_api_key:
        st.error("Google Gemini APIキーを入力してください。")
        st.stop()
    
    # タブを作成
    tab1, tab2, tab3 = st.tabs(["関連度評価", "ソリューション案", "製品イメージ"])
    
    # データの読み込み
    with st.spinner("特許データを読み込んでいます..."):
        df = load_data(uploaded_file)
        if df is None:
            st.stop()
    
    # 要約列が存在するか確認
    if '要約' not in df.columns:
        st.error("データフレームに'要約'列が見つかりません")
        st.stop()
    
    # 進捗表示付きで関連度の評価
    with tab1:
        st.subheader(f"「{user_query}」に対する特許要約の関連度を評価")
        
        # 進捗バーの準備（有効な要約の数をカウント）
        valid_summaries = df['要約'].dropna().count()
        progress_bar = st.progress(0)
        progress_text = st.empty()
        
        # 関連度評価
        df['relevance_str'] = ""
        progress_count = 0
        total_items = valid_summaries
        
        for i, row in df.iterrows():
            if pd.notna(row['要約']):
                progress_text.text(f"進捗: {progress_count+1}/{total_items} 特許要約を評価中...")
                
                # 関連度評価
                relevance = generate_relevance_gemini(
                    gemini_api_key, 
                    row['要約'], 
                    user_query, 
                    progress_bar, 
                    progress_count+1, 
                    total_items,
                    max_retries,
                    backoff_time
                )
                df.at[i, 'relevance_str'] = relevance
                progress_count += 1
                
                # モデルに基づいて待機時間を調整（RPM制限対応）
                wait_time = calculate_wait_time("gemini-2.0-flash-lite")
                time.sleep(wait_time)
        
        # 関連度を数値に変換
        with st.spinner("関連度を数値に変換しています..."):
            df['relevance'] = df['relevance_str'].apply(extract_percentage)
        
        # 関連度上位N件を抽出
        with st.spinner(f"関連度上位{top_n}件を抽出しています..."):
            top_n_relevance = df.nlargest(top_n, 'relevance')
        
        # 結果を表示
        st.subheader(f"関連度上位{top_n}件の特許要約")
        st.dataframe(top_n_relevance[['要約', 'relevance']])
    
    # 上位N件の要約を結合
    solutions_list = top_n_relevance['要約'].tolist()
    all_solutions_combined = ' '.join(solutions_list)
    
    # ソリューションの生成（Gemini）
    with tab2:
        st.subheader(f"「{user_query}」に対する{product_type}のソリューション案")
        with st.spinner(f"「{user_query}」に関するソリューションをGeminiで生成しています..."):
            recommend_solution_gemini = generate_solution_gemini(
                gemini_api_key, 
                all_solutions_combined, 
                user_query,
                product_type,
                max_retries,
                backoff_time
            )
        
        # 結果を表示
        st.write(recommend_solution_gemini)
    
    # ソリューションから画像を生成
    with tab3:
        st.subheader(f"「{user_query}」の{product_type}製品イメージ")
        if recommend_solution_gemini:
            with st.spinner(f"「{user_query}」に関する画像をGeminiで生成しています..."):
                product_image = generate_image_from_solution(
                    gemini_api_key, 
                    recommend_solution_gemini, 
                    user_query,
                    product_type,
                    max_retries,
                    backoff_time
                )
            
            if product_image:
                # 画像のサイズを取得
                img_width, img_height = product_image.size
                
                # 画像を半分のサイズでリサイズ
                new_width = img_width // 2
                new_height = img_height // 2
                resized_image = product_image.resize((new_width, new_height))
                
                # リサイズされた画像を表示
                st.image(resized_image, caption=f"「{user_query}」の{product_type}製品イメージ", use_container_width=False)
                
                # 画像ダウンロードボタン
                buf = BytesIO()
                product_image.save(buf, format="PNG")  # 元のサイズの画像をダウンロード用に保存
                byte_im = buf.getvalue()
                
                st.download_button(
                    label="製品画像をダウンロード",
                    data=byte_im,
                    file_name="product_solution_image.png",
                    mime="image/png",
                    key="download_button"
                )
            else:
                st.error("画像の生成に失敗しました。")
        else:
            st.error("ソリューションが生成されなかったため、画像生成をスキップしました。")
else:
    # アプリの説明
    st.markdown("""
    このアプリは、特許データベースを分析し、ユーザーの要望に合った革新的なソリューションを生成します。
    
    ### 🚀 主な機能
    
    - **関連度評価**: 特許データベースから入力された要望に関連する特許を自動的に分析
    - **ソリューション生成**: 関連特許の知見を組み合わせた革新的なソリューションを生成
    - **製品イメージ**: ソリューションに基づいた製品のビジュアルイメージを生成
    
    ### 📝 使い方
    
    1. サイドバーでGoogle Gemini APIキーを設定します
    2. 特許データベースのExcelファイルをアップロードします（'要約'列を含むもの）
    3. ニーズを入力します（例：「環境に優しい包装材が欲しい」）
    4. 製品カテゴリを選択します（例：「飲料」「食品」「電子機器」など）
    5. 「分析開始」ボタンをクリックします
    
    ### ⚙️ 処理の流れ
    
    1. Gemini APIを使用して、各特許要約とユーザー要望との関連度を評価
    2. 関連度の高い特許要約を抽出して分析
    3. Gemini APIを使用して、抽出された特許要約を元に革新的なソリューションを生成
    4. Gemini APIを使用して、生成されたソリューションに基づく製品画像を生成
    
    ### ⚠️ 注意事項
    
    - 本アプリは特許第7672120号の技術を使用しています。
    - 本アプリはデモンストレーション用ですので、個人的な実施に留めてくださるようお願いします。
    """)
    
# ======================================================
# 7. フッター
# ======================================================

st.markdown("---")
st.markdown("© 2025 Idea AI Generator II")
