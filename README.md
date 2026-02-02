# Financial Analytics Portfolio
**Bridging Accounting Forensics & Quantamental Investment on Japan Equity**

![Role](https://img.shields.io/badge/Role-Quantamental%20Researcher%20(CPA)-orange)
![Tech](https://img.shields.io/badge/Tech-Python%20%7C%20XBRL%20%7C%20AI%20Augmented-blue)
![Status](https://img.shields.io/badge/Status-Job%20Hunting-green)

## 👤 Introduction

**公認会計士（CPA）** としての監査実務経験と、**データエンジニアリング**を融合させた金融分析プロジェクトのポートフォリオです。

「財務諸表の数値」を単なるデータとして扱うのではなく、その背後にある **「会計方針の選択」「経営者の見積もり」「不正リスクの兆候」** を読み解く**Accounting Forensics**の視点を、アルゴリズムによって実装・自動化することをテーマとしています。

本ポートフォリオに含まれるコードは、プログラミング学習開始から短期間で実務レベルの実装を行うため、**生成AI（LLM）を「実装パートナー」として活用**し、ドメイン知識（要件定義・ロジック設計）を私が、コーディング（実装）をAIが担当する体制で開発されました。

---

## 📂 Projects Overview

本ポートフォリオは、**「守り（Defense）」** と **「攻め（Offense）」** の2つのモジュールで構成されています。

### [01. Accounting Fraud Risk Screener](./01_Accounting_Fraud_Risk)
**【Defense】財務諸表の「歪み」を検知する不正リスクスクリーニング**
*   **概要:** (広義の)発生主義会計における「見積りの裁量」に着目し、粉飾決算や将来の減損リスクが高い企業を抽出するツール。
*   **Core Logic:** Modified Sloan Ratio (Accruals Anomaly), Cash Flow Divergence.
*   **Use Case:** 監査計画におけるリスク評価、FASにおけるデューデリジェンス（DD）の初期スクリーニング。

### [02. Japan Equity Multi-Factor Strategy](./02_Japan_Equity_Multi_Factor_Strategy)
**【Offense】"Accounting Alpha" を狙うクオンツメンタル投資戦略**
*   **概要:** Yartseva (2025) の "Twin Engines" 仮説を日本市場に適応させた投資モデル。「会計鑑識」によるフィルタリングと、バリュエーション・クオリティ指標を組み合わせた戦略の実証。
*   **Core Logic:** Forensic ETL (XBRL Parsing), Robust Z-Scoring, Sector Neutrality.
*   **Performance:** 過去9年間のバックテストにて、リスク調整後リターンの優位性を確認（詳細はリンク先を参照）。


    *(各プロジェクトの実行方法は、それぞれのフォルダ内のREADMEを参照してください。)*

---

## 🛠 Skills & Methodology

*   **Accounting Forensics:** J-GAAP/IFRSの差異分析、不正会計リスクシナリオの策定。
*   **Financial Data Engineering:** データベンダーに依存しない、XBRL（一次情報）からのデータ抽出・正規化。
*   **Development Style:** AI-Augmented Development (Leveraging LLMs for implementation efficiency).

### Certifications
*   公認会計士 (CPA - Japan)
*   統計検定 2級 (準1級学習中)
*   JDLA G検定 (Deep Learning for Generalist)
*   ビジネス実務法務検定 1級

---
*Disclaimer: This repository is for educational and research purposes only.*
