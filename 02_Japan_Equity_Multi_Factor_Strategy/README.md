# Japan Equity Multi-Factor Strategy: Integrating Quality, Value, and Earnings Quality

Integrating Earnings Quality Analysis with Quantitative Factors on JPX

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Role](https://img.shields.io/badge/Role-Quantamental_Researcher_(CPA)-orange)
![Dev](https://img.shields.io/badge/Dev-AI_Augmented-purple)
![Status](https://img.shields.io/badge/Status-Research_Prototype-green)

<br> [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](http://colab.research.google.com/github/macro-observer/Financial-Analytics-Portfolio/blob/main/02_Japan_Equity_Multi_Factor_Strategy/analysis_demo.ipynb)
[![View Research Report](https://img.shields.io/badge/View_Research_Report-181717?style=for-the-badge&logo=github&logoColor=white)](https://github.com/macro-observer/Financial-Analytics-Portfolio/blob/main/02_Japan_Equity_Multi_Factor_Strategy/analysis_demo.ipynb)

## 📌 Executive Summary

本リポジトリは、Yartseva (2025) *"The Alchemy of Multibagger Stocks"* の実証研究を日本市場（JPX）向けに実装したクオンツメンタル戦略のプロトタイプです。

従来のファクター投資（Value, Quality, Momentum）に対し、**公認会計士（CPA）としての専門的知見に基づく「利益の質（Earnings Quality）の定量評価」** を統合しました。
加工済みデータベンダーに依存せず、EDINET（金融庁開示システム）の一次情報であるXBRLを直接解析し、財務数値の裏側にある「会計上の見積もりの歪み」を定量的に評価してスクリーニングを行う点が特徴です。

---

## 🏗 System Architecture

```mermaid
graph LR
    Data[<b>Market & Financial Data</b><br>EDINET / Yahoo Finance] --> ETL[<b>Data Processing</b><br>Automated Data Cleaning]
    ETL --> Algo[<b>Quantitative Analysis</b><br>Factor Modeling & Scoring]
    Algo --> Result((<b>Investment<br>Decision</b>))

    style Data fill:#fff3e0,stroke:#ff9800
    style ETL fill:#e1f5fe,stroke:#0277bd
    style Algo fill:#e8f5e9,stroke:#2e7d32
    style Result fill:#fce4ec,stroke:#c2185b,stroke-width:2px
```

---

## 🛠 Development Approach: "AI-Augmented Research"

**Disclaimer on Coding & Implementation:**

本プロジェクトは、著者の**プログラミング学習開始から3週間**という短期間で、実務レベルの実装（非同期処理、クラス設計等）を実現するため、**生成AI（LLM）を「実装パートナー」として全面的に活用**して構築されました。

*   **Role of Human (CPA / Architect):**
    *   **要件定義:** Yartseva (2025) の理論解釈および日本市場への適応戦略の立案。
    *   **ドメインロジック設計:** XBRLタグのマッピング定義（J-GAAP/IFRS）、Modified Sloan Ratioの計算ロジック策定、Look-ahead Bias排除のルール設計。
    *   **品質管理:** AIが生成したコードのロジックレビュー、および財務データの整合性検証。
*   **Role of AI (Junior Engineer):**
    *   **実装:** Python構文の実装、`asyncio`を用いた非同期処理の記述、クラス構造のリファクタリング。

著者は、**会計・財務のドメイン知識（Domain Expertise）**と**AI技術**を組み合わせることで、エンジニアリングの壁を越えて「高度な金融ロジックを即座に社会実装できる」ことを実証するポートフォリオとして本コードを作成しました。

---

## 🚀 Strategy Edge: "Openness & Reproducibility"

ブラックボックスな加工済みデータではなく、 **「検証可能性（Reproducibility）」** を最優先する設計思想に基づいています。

### 1. Data Source Strategy (Open & Reproducible)
本プロジェクトの核心である「財務ファンダメンタルズ分析」においては、ブラックボックス化された有料データベースに依存せず、**日本の法定開示システム（EDINET）から一次情報（XBRL）を直接取得・解析するパイプライン**を確立しています。

* **Core Logic (Accounting):** XBRL解析から指標算出までの全工程をコード化し、データベンダーの仕様変更に左右されない**透明性と再現性**を担保。
* **Market Data (Validation):** 検証用データとしてオープンソース`yfinance`を採用。アーキテクチャはデータ取得層（Loader）とロジック層（Model）が明確に分離された**モジュラー設計（Modular Architecture）** を採用しており、実務運用においてはLoader部分のアダプターを差し替えるだけで、Bloomberg等の高品質フィードへ接続可能です。

### 2. Risk Management (Modified Sloan Ratio)
現在の収益認識会計基準（支配移転モデル）においても、進捗率や引当金の見積もりには**経営者の裁量**が介入します。
*   **Logic:** 日本基準特有の特別損益項目を考慮し、営業利益ではなく**当期純利益（Net Income）**と**営業CF**の乖離に着目。
*   **Detection:** `(|Net Income - OpeCF| / Avg Assets) > 0.10` の銘柄を「利益の質が低い（Aggressive Accruals）」として除外。

---

## 📊 Methodology

### The Logic (Localization Strategy)
Yartseva (2025) の "Twin Engines" 仮説を日本市場へ適応（Localize）させるため、以下の調整を行っています。

| Factor | Weight | Indicator | Rationale (Hypothesis-Driven) |
| :--- | :--- | :--- | :--- |
| **Value** | **40%** | **PBR**, FCF Yield | 短期的な純利益ノイズを避けるためPERではなく**PBR**を採用。<br>東証の資本コスト意識改革（PBR1倍割れ）トレンドを考慮しオーバーウェイト。 |
| **Quality** | **30%** | **ROA** | EPS成長の持続性を担保するコア指標。<br>資産効率性を重視し、Qualityの低いバリュー株（Value Trap）を回避。 |
| **Technical**| 17.5%| Momentum, Range | 順張り（Momentum）と逆張り（Price Position）の組み合わせ。 |
| **Size** | 12.5%| Log(Market Cap) | 小型株効果（Small-Cap Premium）の捕捉。 |

---

## 📈 Backtest Performance (Reference)

2016年から2025年（約9年間）における年次リバランス（Annual Rebalancing）検証結果の参考値です。
「会計品質」によるフィルタリングが、リスク調整後リターンの向上に寄与しています。

| Portfolio | CAGR | Sharpe Ratio | Max Drawdown | Win Rate |
| :--- | :--- | :--- | :--- | :--- |
| **Top 10 Picks** | **22.8%** | **0.63** | **-15.5%** | **77.8%** |
| **Top 30 Picks** | **17.4%** | **1.21** | **-9.2%** | **88.9%** |

*Note: Top 30ポートフォリオにおいて Sharpe Ratio 1.21 を記録しており、ボラティリティを抑えた安定的な運用が可能であることを示唆しています。詳細は [analysis_demo.ipynb](./analysis_demo.ipynb) を参照してください。*

---

## ⚠️ Critical Limitations (Professional Skepticism)

本モデルの評価にあたっては、以下のデータ制約およびバイアスを考慮する必要があります。これらの制約がパフォーマンスを過大評価させている可能性に注意が必要です。

1.  **Survivorship Bias (Theoretical Ceiling):**
    *   検証対象が「現在の上場企業」に基づいているため、過去の倒産・上場廃止銘柄が含まれていません。バックテスト結果は**理論上の上限値（Theoretical Ceiling）** であり、実運用においては倒産コスト分だけ劣後する可能性が高いです。
2.  **Data Coverage Constraint:**
    *   EDINET APIの仕様等により、特に2016年〜2017年のデータにおいて**約11%の取得漏れ**が発生しています。これは経営不振による決算遅延企業等のデータが欠損している（Systematic Bias）可能性があります。
3.  **Liquidity Risk:**
    *   推奨銘柄には時価総額50億円〜の小型株が含まれます。マーケットインパクト（スリッページ）は考慮されていません。
4.  **Market Data Reliability (Demo Source):**
    *   本プロジェクトではデモンストレーション用に `yfinance` (非公式API) を使用しています。実運用（Production）で求められる厳密なCorporate Action（株式分割・併合等）の調整精度を保証するものではなく、結果にノイズが含まれる可能性があります。実務適用にあたっては、BloombergやRefinitiv等の公式ベンダー経由のデータフィードへの置換を前提としています。
---

## 📂 Repository Structure

保守性と可読性を高めるため、モジュール構成を採用しています。

```text
02_Japan_Equity_Multi_Factor_Strategy/
│
├── japan_equity_screener.py  # 【Production】本番用スクリーニング実行スクリプト (Entry Point)
├── analysis_demo.ipynb       # 【Research】戦略ロジックの詳細解説とバックテスト結果
├── requirements.txt          # 依存ライブラリ
├── README.md                 # ドキュメント（本ファイル）
│
└── src/                      # 【Core Modules】
    ├── __init__.py
    ├── config.py             # 設定管理・XBRLタグマッピング (AlchemyConfig)
    ├── data_loader.py        # データ収集・XBRL解析 (MarketDataLoader, RobustXBRLParser)
    ├── model.py              # アルファ算出・スコアリング (AlchemyAlphaModel)
    └── engine.py             # バックテスト・リスク分析 (BacktestEngine)
```

---

## 🚀 Usage

1. **Prerequisites & Installation:**
   *Python 3.10以上が必要です。*

   ```
   pip install -r requirements.txt
   ```

2. **API Key Setup:**
   *本ツールは財務データの取得に EDINET API を使用します。*
*ルートディレクトリに `.env` ファイルを作成し、APIキーを以下のように記述してください。*

   ```
   EDINET_API_KEY=your_api_key_here
   ```


3. **スクリーニングの実行:**
   *直近の有価証券報告書データと株価を取得し、現在推奨される銘柄リスト（Top 30）を出力します。*

   ```
   python japan_equity_screener.py
   ```
---

## 👤 About the Author
**Quantamental Researcher (CPA)**

公認会計士（Certified Public Accountant）として監査法人にて法定監査業務に従事。監査の視点と、データサイエンスを融合させた**クオンツメンタル（Quantamental）** 投資戦略の分析を行っています。
*   **Focus:** Accounting Forensics, Financial Data Analysis (J-GAAP/IFRS), Auditing.
*   **Certifications:** CPA (Japan), Japan Statistical Society Certificate Grade 2, JDLA Deep Learning for GENERAL (AI/Deep Learning), The Japan Business Law Examination Grade 1.
*   **Tech Stack:** Python (pandas, numpy, scipy, lxml), XBRL Parsing, Async I/O (AI-Augmented).

**📚 References**
*   Yartseva, A. (2025). The Alchemy of Multibagger Stocks. CAFE Working Paper No.33. [Available at BCU Open Access](https://www.open-access.bcu.ac.uk/16180/)　
*   Sloan, R. G. (1996). Do Stock Prices Fully Reflect Information in Accruals and Cash Flows about Future Earnings? The Accounting Review.

---

Disclaimer: This project is for educational and research purposes only. Not intended as financial advice.
