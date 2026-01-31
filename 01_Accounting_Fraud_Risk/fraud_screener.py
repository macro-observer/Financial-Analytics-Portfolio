# -*- coding: utf-8 -*-
"""
会計不正リスクスクリーニングツール v1.0.0
Simple Financial Fraud Detection Tool

Author: macro-observer (CPA / Financial Auditor)
Date: 2025-01-22
License: MIT
"""

from __future__ import annotations

import os
import sys
import re
import io
import math
import time
import zipfile
import logging
import asyncio
import urllib.parse
import warnings
import html
import getpass
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any, Union

# サードパーティ製ライブラリ
import pandas as pd
import aiohttp
import feedparser
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import nest_asyncio

# ==========================================
# 初期設定
# ==========================================

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 環境変数読み込み
load_dotenv()

# 警告の抑制
warnings.simplefilter(action='ignore', category=FutureWarning)
warnings.simplefilter(action='ignore', category=UserWarning)

# asyncioのイベントループ競合回避
nest_asyncio.apply()

# メタ情報
__title__ = 'Simple Financial Fraud Detection Tool'
__version__ = '1.0.0'
__author__ = 'CPA Developer'


# ==========================================
# 1. Configクラス (定数・設定管理)
# ==========================================
class Config:
    """
    アプリケーション全体の定数・設定を一元管理するクラス。
    """
    # --- News API Settings ---
    NEWS_ROLES = "CFO OR 最高財務責任者 OR 財務 OR 経理 OR 役員"
    NEWS_ACTIONS = "辞任 OR 退任 OR 交代 OR 辞職 OR 更迭 OR 解任"
    NEWS_RISK_KEYWORDS = ["更迭", "一身上", "突然", "不正", "処分", "不明朗", "交代", "異動"]
    NEWS_SHORT_TERM_KEYWORDS = ["短期間", "わずか", "就任直後", "ヶ月", "スピード"]

    # --- JPX Settings ---
    JPX_URL = "https://www.jpx.co.jp/markets/statistics-equities/misc/01.html"

    # --- Financial / Sector Settings ---
    FINANCIAL_SECTORS = ['銀行業', '証券、商品先物取引業', '保険業', 'その他金融業']
    BIG4_KEYWORDS = ["トーマツ", "あずさ", "新日本", "PwC", "ＰｗＣ", "あらた", "Deloitte", "EY", "KPMG"]
    MANUFACTURING_SECTORS = [
        '水産・農林業', '鉱業', '建設業', '食料品', '繊維製品', 'パルプ・紙', '化学',
        '医薬品', '石油・石炭製品', 'ゴム製品', 'ガラス・土石製品', '鉄鋼', '非鉄金属',
        '金属製品', '機械', '電気機器', '輸送用機器', '精密機器', 'その他製品'
    ]

    # --- XBRL Parsing Priority Map ---
    # 会計基準ごとのタグ名の揺らぎを吸収するためのマッピング
    PRIORITY_MAP_SINGLE = {
        'Sales': [
            'OrdinaryIncomeSummaryOfBusinessResults',           # J-GAAP
            'RevenueIFRSSummaryOfBusinessResults',              # IFRS
            'RevenuesUSGAAPSummaryOfBusinessResults',           # US-GAAP
            'NetSalesSummaryOfBusinessResults',
            'SalesAndFinancialServicesRevenueIFRS',
            'TotalNetRevenuesIFRS', 'SalesRevenuesIFRS', 'OperatingRevenuesIFRSKeyFinancialData',
            'OrdinaryRevenue', 'OperatingRevenue1', 'Revenue', 'NetSales', 'Revenues'
        ],
        'OpIncome': [
            'OperatingProfitLossIFRSSummaryOfBusinessResults',  # IFRS
            'OperatingIncomeLossSummaryOfBusinessResults',      # US-GAAP
            'OrdinaryIncomeLossSummaryOfBusinessResults',       # J-GAAP
            'OrdinaryProfit', 'OrdinaryIncome', 'OrdinaryIncomeLoss',
            'OperatingProfit', 'OperatingIncome',
            'OperatingProfitLossIFRS', 'ProfitLossFromOperatingActivities',
            'ProfitLossBeforeTaxIFRSSummaryOfBusinessResults',
            'ProfitLossBeforeTaxUSGAAPSummaryOfBusinessResults',
            'ProfitLossBeforeTaxIFRS'
        ],
        'NetIncome': [
            'ProfitLossAttributableToOwnersOfParentIFRSSummaryOfBusinessResults',
            'NetIncomeLossAttributableToOwnersOfParentUSGAAPSummaryOfBusinessResults',
            'ProfitLossAttributableToOwnersOfParentSummaryOfBusinessResults',
            'ProfitLossAttributableToOwnersOfParent', 'NetIncome', 'ProfitLoss'
        ],
        'TotalAssets': [
            'TotalAssetsIFRSSummaryOfBusinessResults',
            'TotalAssetsUSGAAPSummaryOfBusinessResults',
            'TotalAssetsSummaryOfBusinessResults',
            'AssetsIFRS', 'Assets', 'TotalAssets'
        ],
        'NetAssets': [
            'NetAssetsSummaryOfBusinessResults', 'EquityIFRS', 'TotalEquity', 'NetAssets'
        ],
        'OpCashFlow': [
            'NetCashProvidedByUsedInOperatingActivitiesSummaryOfBusinessResults',
            'NetCashProvidedByUsedInOperatingActivities',
            'CashFlowsFromUsedInOperatingActivitiesIFRSSummaryOfBusinessResults',
            'CashFlowsFromUsedInOperatingActivitiesUSGAAPSummaryOfBusinessResults'
        ],
        'CurrentAssets': ['CurrentAssets', 'AssetsCurrent', 'CurrentAssetsIFRS'],
        'CurrentLiabilities': ['CurrentLiabilities', 'LiabilitiesCurrent'],
        'RetainedEarnings': ['RetainedEarnings', 'RetainedEarningsIFRS'],
        'CashAndEquivalents': ['CashAndCashEquivalents', 'CashAndDeposits'],
        'PPE': ['PropertyPlantAndEquipment', 'PropertyPlantAndEquipmentNet']
    }

    # --- XBRL Summation Groups ---
    # 複数のタグを合算する必要がある項目
    XBRL_TAG_GROUPS = {
        'Receivables': [
            'AccountsReceivableTrade', 'NotesReceivableTrade', 'TradeAndOtherReceivables',
            'TradeAndOtherReceivables3CAIFRS', 'TradeAndOtherReceivablesCAIFRS',
            'TradeReceivablesOtherReceivablesAndContractAssetsCAIFRS',
            'ReceivablesRelatedToFinancialServicesCAIFRS', 'NotesAndAccountsReceivableTradeAndContractAssets',
            # IFRS/Financials
            'TradeReceivables2AssetsIFRS', 'LeaseReceivablesCA', 'AccountsReceivableInstallmentSalesCALEA',
            'OperatingLoansCA', 'LoansInCreditCardBusinessAssetsIFRS', 'LoansInBankingBusinessAssetsIFRS',
            'InstallmentLoans', 'NetInvestmentInLeases', 'LoansToCustomers', 'FinanceLeaseReceivables',
            'InvestmentInDirectFinancingLeases', 'OperatingLoans', 'LeaseInvestmentAssets',
            'Loans', 'InstallmentReceivables'
        ],
        'Inventory': [
            'Inventories', 'MerchandiseAndFinishedGoods', 'WorkInProcess',
            'InventoriesCAIFRS', 'MerchandiseCAIFRS', 'FinishedGoodsCAIFRS', 'RawMaterialsAndSuppliesCAIFRS',
            'InventoriesIFRS', 'InventoriesAssetsIFRS', 'RealEstateForSale', 'RealEstateUnderDevelopment',
            'RealEstateForSaleInProcess', 'OperationalInvestmentSecurities',
            'FinancialAssetsForTheSecuritiesBusinessAssetsIFRS',
            # ORIX / US GAAP Specific
            'RealEstateHeldForSale', 'RealEstateUnderDevelopment', 'AdvancesForRealEstate',
            'TradingSecurities', 'MarketableSecurities', 'Merchandise'
        ],
        'Payables': [
            'AccountsPayableTrade', 'NotesPayableTrade', 'TradeAndOtherPayables',
            'TradeAndOtherPayables3CLIFRS', 'TradeAndOtherPayablesCLIFRS',
            'AccountsPayableTradeLiabilitiesIFRS', 'NotesAndAccountsPayableTrade',
            'FinancialLiabilitiesForSecuritiesBusinessLiabilitiesIFRS'
        ]
    }


# ==========================================
# 2. ユーティリティ関数
# ==========================================
def get_config() -> tuple[str, list[str]]:
    """
    APIキーと対象企業コードを取得する。
    1. 環境変数 (.env)
    2. Google Colab Secrets (互換性維持)
    3. 手入力 (getpass優先、失敗時はinput)
    """
    api_key = None

    # 1. 環境変数 & Colab Secrets
    api_key = os.getenv("EDINET_API_KEY")
    
    if not api_key:
        try:
            from google.colab import userdata
            api_key = userdata.get('EDINET_API_KEY')
            logger.info("Google Colab SecretsからAPIキーを読み込みました。")
        except (ImportError, AttributeError, Exception):
            pass

    # 2. 手入力 (修正: getpassを試行し、型エラー時はinputにフォールバック)
    if not api_key:
        print("APIキーが見つかりませんでした。")
        try:
            # 機密性保護のため、まずはgetpassを試行
            raw_input = getpass.getpass('EDINET API Keyを入力してください: ')
            
            # Google Colab等の一部環境でgetpassが辞書型オブジェクトを返すバグへの対策
            if not isinstance(raw_input, str):
                raise ValueError("getpass returned non-string object")
                
            api_key = raw_input
            
        except (Exception, ValueError):
            # getpassが正常に機能しない場合のみ、標準入力を使用
            print("※セキュリティ入力(getpass)が利用できない環境のため、標準入力を使用します。")
            api_key = input('EDINET API Keyを入力してください: ')

        # 共通のクリーニング処理
        if api_key:
            api_key = str(api_key).strip().replace('"', '').replace("'", "")

    if not api_key:
        raise ValueError("API Key was not entered.")

    # 企業コードの取得
    env_codes = os.getenv("TARGET_CODES")
    
    # Colab Secrets互換
    if not env_codes:
        try:
            from google.colab import userdata
            env_codes = userdata.get('TARGET_CODES')
        except: pass

    if env_codes:
        code_input = env_codes
        logger.info("保存された設定から企業コードを読み込みました。")
    else:
        print(f"\n[{__title__} v{__version__}]")
        print("分析したい企業コードを入力してください（最大10社、全角/半角スペース区切り）")
        print(f"銘柄コード検索: {Config.JPX_URL}")
        print("例: 6758 9984 8306 (Enterで決定)")
        code_input = input('Company Codes: ')

    codes = [c for c in re.split(r'[ 　]+', code_input.strip()) if c][:10]
    if not codes:
        raise ValueError("Company Code was not entered.")

    return api_key, codes


# ==========================================
# 3. 各種クライアントクラス
# ==========================================

class NewsClient:
    """Google News RSSを利用してCFO/役員の辞任情報を検索するクラス。"""
    
    def __init__(self):
        self.base_url = "https://news.google.com/rss/search"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def check_cfo_news(self, company_name: str) -> tuple[list[dict[str, str]], str]:
        query = f'"{company_name}" ({Config.NEWS_ROLES}) ({Config.NEWS_ACTIONS})'
        params = {"q": query, "hl": "ja", "gl": "JP", "ceid": "JP:ja"}
        rss_url = f"{self.base_url}?{urllib.parse.urlencode(params)}"

        try:
            feed = feedparser.parse(rss_url, request_headers=self.headers)
            if hasattr(feed, 'status') and feed.status != 200:
                logger.warning(f"News feed status error: {feed.status} for {company_name}")
                return [], "⚠️ 取得失敗 (接続エラー)"

            news_results = []
            overall_verdict = "✅ 正常 (関連ニュースなし)"

            for entry in feed.entries[:5]:
                title = entry.title
                status = "INFO"
                if any(k in title for k in Config.NEWS_SHORT_TERM_KEYWORDS):
                    status = "🚨 OUT (短期間)"
                    overall_verdict = "🚨 OUT (CFO/役員の短期間辞任あり)"
                elif any(k in title for k in Config.NEWS_RISK_KEYWORDS):
                    status = "⚠️ 警戒"
                    if "OUT" not in overall_verdict: overall_verdict = "⚠️ 警戒 (不穏な辞任)"

                news_results.append({"title": title, "date": entry.published, "status": status})
            return news_results, overall_verdict
        except Exception as e:
            logger.error(f"News API Error for {company_name}: {e}")
            return [], "⚠️ 取得失敗 (API/Networkエラー)"


class JpxClient:
    """JPXから業種データを取得するクラス。"""

    def __init__(self):
        self.jpx_url = Config.JPX_URL
        self.base_host = "https://www.jpx.co.jp"
        self.sector_map = {}

    async def fetch_sector_data(self):
        print("JPX公式サイトから最新の業種データを取得中...", end="")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.jpx_url) as res:
                    if res.status != 200:
                        logger.warning(f"JPX access failed. Status: {res.status}")
                        return
                    text = await res.text()
            soup = BeautifulSoup(text, 'html.parser')
            link = soup.find('a', href=re.compile(r'data_j\.xls'))
            if not link:
                logger.warning("JPX excel link not found.")
                return
            
            # pandasのExcel読み込みにはopenpyxlかxlrdが必要。
            # HTMLから取得したバイナリデータとして処理するか、URLを渡す
            excel_url = self.base_host + link['href']
            # 注: 実際のスクリプト実行ではSSL証明書エラー等が出る場合があるため、pandasで直接読む
            try:
                df = pd.read_excel(excel_url)
            except Exception:
                # 失敗時はrequests等でバイナリ取得してBytesIO経由などの実装が必要だが、
                # 簡易化のためpandasの機能に依存
                logger.warning("Failed to read Excel directly from URL.")
                return

            for _, row in df.iterrows():
                code = str(row.get('コード', ''))[:4]
                sector = row.get('33業種区分', '不明')
                if code: self.sector_map[code] = sector.strip()
            print(" 完了")
        except Exception as e:
            logger.error(f"JPX fetch sector data failed: {e}")
            print(" 失敗")

    def get_sector(self, code: str) -> str:
        return self.sector_map.get(code[:4], "不明")


class EdinetClient:
    """EDINET API v2連携クラス。"""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.edinet-fsa.go.jp/api/v2"
        self.semaphore = asyncio.Semaphore(5)
        self.doc_cache = {}

    async def prefetch_metadata(self, session: aiohttp.ClientSession, target_codes: List[str]):
        print(f"\nAPIアクセス: メタデータスキャン中（過去2年）...")
        dates = [datetime.now().date() - timedelta(days=i) for i in range(365 * 2)]

        async def fetch_date(date_obj):
            url = f"{self.base_url}/documents.json"
            params = {"date": date_obj.strftime("%Y-%m-%d"), "type": 2, "Subscription-Key": self.api_key}
            try:
                async with self.semaphore:
                    async with session.get(url, params=params, timeout=15) as res:
                        if res.status != 200: return
                        data = await res.json()
                        for item in data.get('results', []):
                            sec_code = str(item.get('secCode', ''))[:4]
                            if sec_code in target_codes and item.get('docTypeCode') == '120':
                                if sec_code not in self.doc_cache: self.doc_cache[sec_code] = []
                                self.doc_cache[sec_code].append(item)
            except Exception as e:
                logger.error(f"Metadata fetch failed for {date_obj}: {e}")

        tasks = [fetch_date(d) for d in dates]
        for i in range(0, len(tasks), 50):
            await asyncio.gather(*tasks[i:i+50])
            print(f"\r スキャン進捗: {min(i + 50, len(tasks))}/{len(tasks)} 日完了", end="")
        print("\n メタデータ取得完了")

    async def get_target_document(self, session: aiohttp.ClientSession, sec_code_prefix: str) -> Optional[Dict[str, Any]]:
        docs = self.doc_cache.get(sec_code_prefix)
        if not docs: return None
        docs.sort(key=lambda x: x.get('submitDateTime', ''), reverse=True)
        return docs[0]

    async def fetch_xbrl_zip(self, session: aiohttp.ClientSession, doc_id: str) -> Optional[bytes]:
        url = f"{self.base_url}/documents/{doc_id}"
        params = {"type": 1, "Subscription-Key": self.api_key}
        try:
            async with self.semaphore:
                async with session.get(url, params=params, timeout=60) as res:
                    return await res.read() if res.status == 200 else None
        except Exception as e:
            logger.error(f"XBRL Zip download failed for {doc_id}: {e}")
            return None


# ==========================================
# 4. 解析・分析ロジック
# ==========================================

class XbrlParser:
    """XBRL解析クラス。"""

    def parse_data(self, zip_bytes: bytes) -> tuple[pd.DataFrame | None, dict[str, Any] | None]:
        if not zip_bytes: return None, None
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                xbrl_files = [f for f in z.namelist() if f.endswith('.xbrl') and 'PublicDoc' in f]
                if not xbrl_files: return None, None

                priority_map_single = Config.PRIORITY_MAP_SINGLE
                df_combined = pd.DataFrame(index=list(priority_map_single.keys()) + ['Receivables', 'Inventory', 'Payables'],
                                           columns=['Current', 'Previous'], dtype='float64').fillna(0.0)

                gov_info_combined = {'Auditor': '不明', 'PeriodEnd': None, 'Standard': 'Japan GAAP', 'isConsolidated': True, 'Industry': 'General',
                                     'related_party_hits': 0, 'related_party_amount': 0.0}

                # 1. Metadata Extraction
                for filename in xbrl_files:
                    with z.open(filename) as f:
                        soup = BeautifulSoup(f.read().decode('utf-8', errors='replace'), 'lxml-xml')
                        info = self._extract_dei_and_audit_info(soup)
                        if info['PeriodEnd']: gov_info_combined['PeriodEnd'] = info['PeriodEnd']
                        if info['Auditor'] != '不明': gov_info_combined['Auditor'] = info['Auditor']
                        if info['Standard'] != 'Japan GAAP': gov_info_combined['Standard'] = info['Standard']
                        if gov_info_combined['PeriodEnd'] and gov_info_combined['Auditor'] != '不明': break

                seen_group_tags = set()
                current_priorities = {}
                for cat in priority_map_single.keys():
                    for per in ['Current', 'Previous']:
                        current_priorities[(cat, per)] = float('inf')

                # 2. Data Extraction
                for filename in xbrl_files:
                    with z.open(filename) as f:
                        content = f.read().decode('utf-8', errors='replace')
                        soup = BeautifulSoup(content, 'lxml-xml')

                        target_date = gov_info_combined.get('PeriodEnd')
                        if not target_date:
                             target_date = self._infer_period_end(soup)
                             if target_date and not gov_info_combined['PeriodEnd']:
                                 gov_info_combined['PeriodEnd'] = target_date

                        ctx_map = self._map_contexts_strict(soup, target_date)
                        self._merge_financials(soup, ctx_map, df_combined, seen_group_tags, current_priorities)

                        gov_info_combined['related_party_hits'] += str(soup).count("関連当事者")
                        gov_info_combined['related_party_amount'] += self._extract_related_party_amounts(soup)

                return df_combined, gov_info_combined
        except Exception as e:
            logger.error(f"XBRL Parsing Error: {e}")
            return None, None

    def _infer_period_end(self, soup: BeautifulSoup) -> str | None:
        dates = []
        for ctx in soup.find_all(re.compile(r'.*context$')):
            period = ctx.find(re.compile(r'.*period$'))
            if period:
                date_tag = period.find(re.compile(r'.*(instant|endDate)$'))
                if date_tag: dates.append(date_tag.text.strip())
        return max(dates) if dates else None

    def _extract_dei_and_audit_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        info = {'Auditor': '不明', 'PeriodEnd': None, 'Standard': 'Japan GAAP', 'isConsolidated': True}

        def clean_auditor_name(raw_text: str) -> str:
            if not raw_text: return '不明'
            text = BeautifulSoup(raw_text, "html.parser").get_text()
            text = html.unescape(text)
            text = re.sub(r'[\s\u3000]+', ' ', text).strip()
            text = re.sub(r'(?:監査法人|会計監査人)の名称[:：]?', '', text)
            text = re.sub(r'当社の監査公認会計士等は[、,]', '', text)
            text = re.sub(r'業務を執行した公認会計士', '', text)
            text = re.sub(r'^[\s:：>＞・等]+|[\s:：>＞・]+$', '', text).strip()
            return text

        try:
            tags = soup.find_all(lambda t: 'DEI' in t.name)
            for t in tags:
                name, text = t.name, t.text.strip()
                if 'CurrentPeriodEndDate' in name: info['PeriodEnd'] = text
                if 'AccountingStandards' in name: info['Standard'] = text
                if 'WhetherConsolidatedFinancialStatementsArePrepared' in name:
                    info['isConsolidated'] = (text.lower() == 'true')
                if any(x in name for x in ['AuditFirmName', 'AuditFirmDescription', 'AuditFirm']):
                    match = re.search(r'((?:PwC|ＰｗＣ|EY|ＥＹ|有限責任|監査法人|Deloitte|KPMG).*監査法人)', text, re.IGNORECASE)
                    if match: info['Auditor'] = clean_auditor_name(match.group(1))

            if info['Auditor'] == '不明':
                audit_tags = soup.find_all(lambda t: any(k in t.name for k in ['NoteOnIndependentAudit', 'IndependentAuditorsReport', 'Auditor', 'AuditFirm', 'CorporateGovernance', 'Audits']))
                for tag in audit_tags:
                    text = tag.get_text()
                    if not text: continue
                    normalized_text = re.sub(r'[\s\u3000]+', ' ', text)
                    match = re.search(r'(?:監査法人|会計監査人)の名称\s*[:：]?\s*(.*?監査法人)', normalized_text)
                    if match:
                        info['Auditor'] = clean_auditor_name(match.group(1))
                        break

                    keywords = [
                        r'有限責任\s*あずさ\s*監査法人', r'有限責任\s*監査法人\s*トーマツ', r'ＥＹ\s*新日本\s*有限責任\s*監査法人',
                        r'ＰｗＣ\s*Ｊａｐａｎ\s*有限責任\s*監査法人', r'ＰｗＣ\s*あらた\s*有限責任\s*監査法人',
                        r'太陽\s*有限責任\s*監査法人', r'仰星\s*監査法人', r'三優\s*監査法人'
                    ]
                    for kw in keywords:
                        match = re.search(kw, normalized_text)
                        if match:
                            info['Auditor'] = clean_auditor_name(match.group(0))
                            break
                    if info['Auditor'] != '不明': break

            if info['Auditor'] == '不明':
                text_sample = soup.get_text()[:50000]
                match = re.search(r'((?:PwC|ＰｗＣ|EY|ＥＹ|有限責任|監査法人|Deloitte|KPMG)[\s\u3000]*[^\s\u3000]+監査法人)', text_sample, re.IGNORECASE)
                if match: info['Auditor'] = clean_auditor_name(match.group(1))
        except Exception:
            pass
        return info

    def _map_contexts_strict(self, soup: BeautifulSoup, target_date_str: str | None) -> dict[str, str]:
        ctx_map = {}
        if not target_date_str: return {}
        try:
            target_dt = datetime.strptime(target_date_str, "%Y-%m-%d")
            prev_dt = target_dt.replace(year=target_dt.year - 1)
            target_dates = {target_date_str, (target_dt + timedelta(days=1)).strftime("%Y-%m-%d")}
            prev_dates = {prev_dt.strftime("%Y-%m-%d"), (prev_dt + timedelta(days=1)).strftime("%Y-%m-%d")}
        except: return {}

        contexts = soup.find_all(re.compile(r'.*context$'))
        for ctx in contexts:
            cid = ctx.get('id', '')
            is_nc = 'NonConsolidated' in cid
            if 'Separate' in cid or 'Individual' in cid: continue
            if any(x in cid for x in ['Segment', 'Row', 'Column']): continue

            has_member = ctx.find(re.compile(r'.*explicitMember$'))
            if has_member:
                member_str = str(has_member)
                if not ('ConsolidatedMember' in member_str or (is_nc and 'NonConsolidatedMember' in member_str)):
                    continue

            period = ctx.find(re.compile(r'.*period$'))
            if not period: continue
            date_tag = period.find(re.compile(r'.*(instant|endDate)$'))
            if date_tag:
                dt_text = date_tag.text.strip()
                if dt_text in target_dates: ctx_map[cid] = 'Current_NC' if is_nc else 'Current'
                elif dt_text in prev_dates: ctx_map[cid] = 'Previous_NC' if is_nc else 'Previous'
        return ctx_map

    def _merge_financials(self, soup: BeautifulSoup, ctx_map: dict, df: pd.DataFrame, seen_group: set, priorities: dict):
        priority_map_single = Config.PRIORITY_MAP_SINGLE
        for col in ['Current', 'Previous']:
            col_nc = col + '_NC'
            for cat, tag_list in priority_map_single.items():
                for idx, pattern in enumerate(tag_list):
                    if idx >= priorities[(cat, col)]: continue
                    elements = soup.find_all(lambda t: t.name and t.name.split(':')[-1] == pattern)
                    found_val = None
                    for el in elements:
                        c_type = ctx_map.get(el.get('contextRef'))
                        if c_type == col:
                            try: found_val = float(el.text.strip()); break
                            except: continue
                        elif c_type == col_nc and (found_val is None):
                            try: found_val = float(el.text.strip())
                            except: continue
                    if found_val is not None:
                        df.at[cat, col] = found_val
                        priorities[(cat, col)] = idx
                        break

            for cat, tag_list in Config.XBRL_TAG_GROUPS.items():
                for pattern in tag_list:
                    elements = soup.find_all(lambda t: t.name and t.name.split(':')[-1] == pattern)
                    val_c = 0.0
                    found_c = False
                    for el in elements:
                        if ctx_map.get(el.get('contextRef')) == col:
                            try:
                                val_c += float(el.text.strip())
                                found_c = True
                            except: continue

                    if found_c:
                        key = (pattern, col)
                        if key not in seen_group:
                            df.at[cat, col] += val_c
                            seen_group.add(key)
                    else:
                        val_nc = 0.0
                        found_nc = False
                        for el in elements:
                            if ctx_map.get(el.get('contextRef')) == col_nc:
                                try:
                                    val_nc += float(el.text.strip())
                                    found_nc = True
                                except: continue
                        if found_nc:
                            key = (pattern, col)
                            if key not in seen_group:
                                df.at[cat, col] += val_nc
                                seen_group.add(key)

    def _extract_related_party_amounts(self, soup: BeautifulSoup) -> float:
        total = 0.0
        for t in soup.find_all(lambda t: t.name and 'RelatedPartyTransactions' in t.name and 'Amount' in t.name):
            try: total += abs(float(t.text.strip()))
            except: continue
        return total


class FinancialAnalyzer:
    """財務指標計算クラス。"""

    def __init__(self):
        self.financial_sectors = Config.FINANCIAL_SECTORS
        self.big4_keywords = Config.BIG4_KEYWORDS
        self.manufacturing_sectors = Config.MANUFACTURING_SECTORS

    def is_financial_company(self, name: str, sector: str = "") -> bool:
        if any(k in (name or "") for k in ["銀行", "証券", "保険", "リース", "投資"]): return True
        return sector in self.financial_sectors

    def check_auditor(self, auditor_name: str) -> tuple[str, str]:
        name = auditor_name or "不明"
        is_big4 = any(k in name for k in self.big4_keywords)
        res = "✅ 安心 (Big4/大手)" if is_big4 else "⚠ 注意 (準大手・中小)"
        return name, res

    def check_big_bath(self, df: pd.DataFrame) -> tuple[float | None, str]:
        try:
            ni, ta = df.at['NetIncome', 'Current'], df.at['TotalAssets', 'Current']
            if not ta or ta == 0: return None, "-"
            ratio = ni / ta
            verdict = "✅ 正常"
            if ratio < -0.10: verdict = "⚠️ ビッグ・バス疑い"
            elif ratio < -0.05: verdict = "⚠ 赤字"
            return ratio, verdict
        except Exception as e:
            logger.error(f"Big Bath Check Error: {e}")
            return None, "-"

    def check_related_party(self, hits: int, amount: float, sales: float) -> tuple[int, float, str]:
        verdict = "✅ 正常" if hits <= 5 else "⚠ 注意" if hits <= 20 else "🚨 異常"
        ratio = (amount / sales) if sales and sales > 0 else 0
        if ratio > 0.10: verdict += " (金額大)"
        return hits, ratio, verdict

    def check_late_filing(self, period_end_str: str, submit_date_str: str) -> tuple[int | None, str]:
        if not period_end_str or not submit_date_str: return None, "-"
        try:
            p_end = datetime.strptime(period_end_str[:10], "%Y-%m-%d")
            s_date = datetime.strptime(submit_date_str[:10], "%Y-%m-%d")
            delta = (s_date - p_end).days
            verdict = "✅ 適正" if delta <= 100 else "⚠️ 遅延疑い"
            return delta, verdict
        except Exception as e:
            logger.error(f"Late Filing Check Error: {e}")
            return None, "-"

    def calc_f_score(self, df: pd.DataFrame) -> tuple[float | None, str]:
        try:
            c, p = df['Current'], df['Previous']
            avg_assets = (c['TotalAssets'] + p['TotalAssets']) / 2
            if not avg_assets or avg_assets == 0: return None, "データ不足"

            rsst_acc = ((c['CurrentAssets'] - c['CurrentLiabilities']) - (p['CurrentAssets'] - p['CurrentLiabilities'])) / avg_assets
            ch_rec = (c['Receivables'] - p['Receivables']) / avg_assets
            ch_inv = (c['Inventory'] - p['Inventory']) / avg_assets

            pred = -7.893 + 0.79*rsst_acc + 2.518*ch_rec + 1.191*ch_inv
            prob = 1 / (1 + math.exp(-pred))
            verdict = "⚠️ 高リスク" if prob > 0.01 else "✅ 低リスク"
            return prob, f"{prob:.4%} ({verdict})"
        except Exception as e:
            logger.error(f"F-Score Calculation Error: {e}")
            return None, "計算エラー"

    def calc_sloan_ratio(self, df: pd.DataFrame, sector: str = "不明") -> tuple[float | None, str]:
        try:
            ni, ocf, ta = df.at['NetIncome', 'Current'], df.at['OpCashFlow', 'Current'], df.at['TotalAssets', 'Current']
            if not ta or ta == 0: return None, "データ不足"
            ratio = (ni - ocf) / ta

            threshold = 0.25 if sector in ["情報・通信業", "サービス業"] else 0.10
            verdict = "✅ 適正"
            if abs(ratio) > threshold: verdict = "⚠ 注意"
            return ratio, f"{ratio:.2%} -> {verdict} (基準: ±{threshold:.0%})"
        except Exception as e:
            logger.error(f"Sloan Ratio Calculation Error: {e}")
            return None, "-"

    def calc_turnover(self, df: pd.DataFrame) -> dict[str, dict[str, Any]] | None:
        try:
            c, p = df['Current'], df['Previous']
            if not c['Sales'] or c['Sales'] == 0: return None

            res = {}
            for item, label in [('Receivables', 'Rec'), ('Inventory', 'Inv'), ('Payables', 'Pay')]:
                if c[item] and c[item] > 0:
                    tc = (c[item]/c['Sales'])*12
                    has_prev = False
                    diff = None
                    if p[item] and p['Sales']:
                        tp = (p[item]/p['Sales'])*12
                        diff = tc - tp
                        has_prev = True

                    verdict = "✅ 適正"
                    if diff and diff > 1.0:
                        if item == 'Receivables': verdict = "⚠️ 長期化"
                        elif item == 'Inventory': verdict = "⚠️ 過剰在庫"
                        elif item == 'Payables': verdict = "⚠️ 支払遅延"

                    res[label] = {'val': tc, 'diff': diff, 'verdict': verdict, 'has_prev': has_prev}
                else:
                    res[label] = None
            return res
        except Exception as e:
            logger.error(f"Turnover Calculation Error: {e}")
            return None

    def calc_z_score(self, df: pd.DataFrame, name: str, sector: str) -> tuple[float | None, str]:
        if self.is_financial_company(name, sector): return None, "ℹ️ 参考値 (金融業のため適用外)"
        try:
            c = df['Current']
            ta = c['TotalAssets']
            if not ta or ta == 0: return None, "データ不足"
            x1 = (c['CurrentAssets'] - c['CurrentLiabilities']) / ta
            x2 = (c['RetainedEarnings'] / ta) if c['RetainedEarnings'] else 0
            x3 = c['OpIncome'] / ta
            x4 = c['NetAssets'] / max(1, ta - c['NetAssets'])

            if sector in self.manufacturing_sectors:
                z = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*(c['Sales']/ta)
                if z < 1.23: verdict = "⚠️ 危険域"
                elif z < 2.90: verdict = "⚠ 要注意 (グレーゾーン)"
                else: verdict = "✅ 健全"
            else:
                z = 6.56*x1 + 3.26*x2 + 6.72*x3 + 1.05*x4
                verdict = "⚠️ 危険域" if z < 1.1 else "✅ 健全"

            return z, f"{z:.2f} ({verdict})"
        except Exception as e:
            logger.error(f"Z-Score Calculation Error: {e}")
            return None, "-"


# ==========================================
# 5. メイン処理・実行エントリーポイント
# ==========================================

async def process_company(session, code, client, parser, analyzer, news_client, jpx):
    """1社分の分析処理を実行し、レポートを出力するメインロジック。"""
    doc = await client.get_target_document(session, code)
    if not doc:
        logger.warning(f"No document found for {code}")
        return
    
    name = doc.get('filerName', 'Unknown')
    sector = jpx.get_sector(code)
    submit_date = doc.get('submitDateTime', '')[:10]

    # 並行してニュースを取得
    news_res, news_verdict = news_client.check_cfo_news(name)

    # XBRLダウンロードと解析
    zip_bytes = await client.fetch_xbrl_zip(session, doc['docID'])
    df_data, gov_info = parser.parse_data(zip_bytes)
    if df_data is None:
        logger.warning(f"Failed to parse XBRL for {code}")
        return

    # --- レポート出力 ---
    print("\n" + "="*80)
    print(f"【分析レポート】 {code} {name} (業種: {sector})")
    print("="*80)
    print(f"\n【取得データ確認 (単位: 百万円) (基準: {gov_info.get('Standard')})】")
    print(f"{'':<15} {'Current':>15} {'Previous':>15}")
    for row in ['Sales', 'OpIncome', 'NetIncome', 'OpCashFlow', 'TotalAssets', 'Receivables', 'Inventory', 'Payables']:
        val_c = df_data.at[row, 'Current']
        val_p = df_data.at[row, 'Previous']
        c_disp = f"{val_c/1e6:,.0f}" if val_c else "-"
        p_disp = f"{val_p/1e6:,.0f}" if val_p else "-"

        label = "Op/Ord Income" if row == "OpIncome" else row
        print(f"{label:<15} {c_disp:>15} {p_disp:>15}")
    print("-" * 50)

    # I. ガバナンス・定性リスク分析
    print("\n【I. ガバナンス・定性リスク分析】")
    print(f"[1] 辞任ニュース監視: {news_verdict}")
    if news_res:
        for n in news_res: print(f"      - [{n['status']}] {n['title']} ({n['date'][:10]})")

    aud_name, aud_res = analyzer.check_auditor(gov_info['Auditor'])
    print(f"\n[2] 監査法人: {aud_name} -> {aud_res}")
    print("    【判定基準】Big4(トーマツ/あずさ/EY/PwC)を含む大手監査法人か否か。")

    bb_val, bb_res = analyzer.check_big_bath(df_data)
    bb_disp = f"{bb_val:.2%}" if bb_val is not None else "-"
    print(f"\n[3] ビッグ・バス: {bb_disp} -> {bb_res}")
    print("    【判定基準】総資産当期純利益率(ROA)が-10%未満の巨額赤字。")

    rp_hits, rp_ratio, rp_res = analyzer.check_related_party(
        int(gov_info['related_party_hits']), 
        gov_info['related_party_amount'], 
        df_data.at['Sales', 'Current']
    )
    print(f"\n[4] 関連当事者分析\n    言及数: {rp_hits}回 / 取引額比: {rp_ratio:.2%}\n    判定: {rp_res}")
    print("    【判定基準】30回以上、または売上対比10%超で異常値。")

    days, late_res = analyzer.check_late_filing(gov_info['PeriodEnd'], submit_date)
    print(f"\n[5] 提出遅延: 決算から{days}日経過 -> {late_res}")
    print("    【判定基準】決算日から提出日まで100日超（通常は90日以内）。")

    # II. 財務数値・定量リスク分析
    print("\n【II. 財務数値・定量リスク分析 (時系列比較)】")
    is_fin = analyzer.is_financial_company(name, sector)
    f_prob, f_res = analyzer.calc_f_score(df_data)
    print(f"[1] Dechow F-Score: {f_res}")
    if is_fin: print("    ℹ️ 【参考】金融事業が含まれるため参考値です。")

    s_val, s_res = analyzer.calc_sloan_ratio(df_data, sector)
    print(f"\n[2] スローン・レシオ: {s_res}")

    print(f"\n[3] 回転期間分析")
    turns = analyzer.calc_turnover(df_data)
    if turns:
        label_map = {'Rec': '売上債権', 'Inv': '棚卸資産', 'Pay': '仕入債務'}
        for k, v in turns.items():
            label = label_map.get(k, k)
            if v:
                diff_str = f"{v['diff']:+.1f}" if v['has_prev'] and v['diff'] is not None else "-"
                print(f"    {label}: {v['val']:.1f}ヶ月 (前差 {diff_str}) -> {v['verdict']}")
            else:
                print(f"    {label}: - (データなし)")
        if is_fin:
            print("    ℹ️ 【注釈】金融・リース業のため参考値です。")
    else:
        print("    (売上高データなしのため計算不可)")

    z_val, z_res = analyzer.calc_z_score(df_data, name, sector)
    print(f"\n[4] アルトマンZスコア: {z_res}")
    print("=" * 80)


async def main_async():
    """非同期メイン処理"""
    try:
        api_key, codes = get_config()
    except ValueError as e:
        logger.error(str(e))
        return

    jpx = JpxClient()
    await jpx.fetch_sector_data()
    
    client = EdinetClient(api_key)
    parser, analyzer, news = XbrlParser(), FinancialAnalyzer(), NewsClient()
    
    async with aiohttp.ClientSession() as session:
        await client.prefetch_metadata(session, codes)
        tasks = [process_company(session, c, client, parser, analyzer, news, jpx) for c in codes]
        await asyncio.gather(*tasks)


def main():
    """エントリーポイント"""
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n処理を中断しました")
    except Exception as e:
        logger.error(f"予期せぬエラーが発生しました: {e}")

if __name__ == "__main__":
    main()
