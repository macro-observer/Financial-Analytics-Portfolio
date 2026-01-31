import os
import io
import zipfile
import datetime
import time
import asyncio
import logging
import concurrent.futures
from typing import List, Tuple, Optional, Dict, Any, Set, Union

import requests
import pandas as pd
import yfinance as yf
import aiohttp
from lxml import etree
from tqdm.asyncio import tqdm_asyncio
from tqdm import tqdm

# 共通設定のインポート
from .config import AlchemyConfig

# 環境設定 (Colab/Jupyter用)
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass

logging.getLogger('yfinance').setLevel(logging.CRITICAL)

# --- Network Helpers ---
async def fetch_with_retry_async(session: aiohttp.ClientSession, url: str, params: Optional[Dict] = None, max_retries: int = 3) -> Optional[bytes]:
    headers = {"User-Agent": "Mozilla/5.0"}
    for attempt in range(max_retries):
        try:
            async with session.get(url, params=params, headers=headers, timeout=30) as response:
                if response.status == 200: return await response.read()
                elif response.status in [404, 403]: return None
        except Exception as e:
            if attempt == max_retries - 1: logging.error(f"Network error {url}: {str(e)}")
        await asyncio.sleep(1 * (2 ** attempt))
    return None

def fetch_sync(url: str, params: Optional[Dict] = None) -> Optional[requests.Response]:
    time.sleep(0.5)
    try:
        res = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if res.status_code == 200: return res
        elif res.status_code == 403: print(f"Auth Error (403): Check API Key for {url}")
    except Exception as e:
        logging.error(f"Sync fetch error {url}: {e}")
    return None

# --- XBRL Parser Logic (Forensic ETL) ---
class RobustXBRLParser:
    """XBRLコンテンツの解析を担当するクラス。コンテキスト(時点)を厳密に分離する。"""
    def __init__(self, xbrl_content: bytes, config: AlchemyConfig, reference_date: Optional[datetime.date] = None):
        self.tree = etree.fromstring(xbrl_content)
        self.config = config
        self.reference_date = reference_date if reference_date else datetime.date.today()
        self.contexts: Dict[str, Dict[str, Any]] = {}
        self._parse_contexts()
        self.target_date: Optional[datetime.date] = None
        self._determine_target_date()

    def _parse_contexts(self) -> None:
        for ctx in self.tree.xpath(".//*[local-name()='context']"):
            cid = ctx.get("id")
            if not cid: continue
            period = ctx.xpath(".//*[local-name()='period']")
            if not period: continue

            start_date, end_date, p_type = None, None, "unknown"
            instant = period[0].xpath(".//*[local-name()='instant']")
            if instant:
                try:
                    text = instant[0].text.strip()
                    end_date = datetime.datetime.strptime(text, "%Y-%m-%d").date()
                    start_date = end_date
                    p_type = "instant"
                except: pass
            else:
                s_elem = period[0].xpath(".//*[local-name()='startDate']")
                e_elem = period[0].xpath(".//*[local-name()='endDate']")
                if s_elem and e_elem:
                    try:
                        s_text, e_text = s_elem[0].text.strip(), e_elem[0].text.strip()
                        start_date = datetime.datetime.strptime(s_text, "%Y-%m-%d").date()
                        end_date = datetime.datetime.strptime(e_text, "%Y-%m-%d").date()
                        p_type = "duration"
                    except: pass

            if not end_date: continue
            if end_date > self.reference_date + datetime.timedelta(days=90): continue
            is_consolidated = 'NonConsolidated' not in cid and 'Separate' not in cid
            self.contexts[cid] = {'type': p_type, 'start': start_date, 'end': end_date, 'is_consolidated': is_consolidated}

    def _determine_target_date(self) -> None:
        if not self.contexts: return
        anchor_tags = ['NetAssets', 'Assets', 'AssetsIFRS', 'TotalAssetsIFRSSummaryOfBusinessResults', 'Sales', 'OperatingIncome']
        candidate_dates = []
        for tag in anchor_tags:
            nodes = self.tree.xpath(f".//*[local-name()='{tag}']")
            for node in nodes:
                cid = node.get("contextRef")
                if cid in self.contexts and node.text and node.text.strip():
                    candidate_dates.append(self.contexts[cid]['end'])

        if not candidate_dates: candidate_dates = [c['end'] for c in self.contexts.values()]
        threshold = self.reference_date + datetime.timedelta(days=90)
        valid_dates = [d for d in candidate_dates if d <= threshold]
        self.target_date = max(valid_dates) if valid_dates else self.reference_date

    def get_value(self, tag_keys: List[str], rank: int = 0, prefer_consolidated: bool = True, annualize: bool = False) -> Tuple[float, int]:
        candidates = []
        if not self.contexts or not self.target_date: return 0.0, 0
        target = self.target_date
        if rank > 0:
            try: target = self.target_date.replace(year=self.target_date.year - rank)
            except ValueError: target = self.target_date - datetime.timedelta(days=365 * rank)

        margin_days = 90
        for key in tag_keys:
            nodes = self.tree.xpath(f".//*[local-name()='{key}']")
            for node in nodes:
                cid = node.get("contextRef")
                if not cid or cid not in self.contexts: continue
                val_str = node.text
                if not val_str or not val_str.strip(): continue
                ctx = self.contexts[cid]

                score = 0
                if ctx['is_consolidated'] == prefer_consolidated: score += 1000
                score -= len(cid)
                cid_lower = cid.lower()
                is_prior_context = 'prior' in cid_lower or 'prev' in cid_lower or 'ly' in cid_lower
                date_diff = abs((ctx['end'] - target).days)

                if rank == 1 and is_prior_context:
                    if ctx['end'] < self.target_date:
                        score += 8000; date_diff = 0
                if date_diff > margin_days: continue

                try:
                    val = float(val_str)
                    scale = node.get('scale')
                    if scale: val *= (10 ** int(scale))
                    if node.get('sign') == '-': val *= -1.0
                    if rank == 0 and is_prior_context: score -= 5000
                    elif rank == 1 and is_prior_context: score += 5000

                    duration_days = 0
                    if ctx['type'] == 'duration':
                        duration_days = (ctx['end'] - ctx['start']).days
                        if annualize:
                            if 80 <= duration_days <= 100: val *= 4.0
                            elif 170 <= duration_days <= 200: val *= 2.0
                            elif 260 <= duration_days <= 280: val *= (12.0/9.0)
                            elif duration_days < 350 and duration_days > 0: val *= (365.0 / duration_days)
                    candidates.append((score, val, duration_days))
                except: continue

        if not candidates: return 0.0, 0
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1], candidates[0][2]

    def extract_metrics(self) -> Dict[str, Union[float, str]]:
        data = {}
        if not self.target_date: return {}
        tag_map = self.config.XBRL_TAG_MAP

        data['Assets'], _ = self.get_value(tag_map['Assets'], 0, annualize=False)
        data['NetAssets'], _ = self.get_value(tag_map['NetAssets'], 0, annualize=False)
        data['Cash'], _ = self.get_value(tag_map['Cash'], 0, annualize=False)
        debt = 0.0
        for tag in tag_map['Debt']:
            v, _ = self.get_value([tag], 0, annualize=False)
            debt += v
        data['Debt'] = debt
        data['IssuedShares'], _ = self.get_value(tag_map['IssuedShares'], 0, prefer_consolidated=False, annualize=False)
        raw_treasury, _ = self.get_value(tag_map['TreasuryShares'], 0, annualize=False)
        data['TreasuryShares'] = abs(raw_treasury)
        data['OpIncome'], dur_days = self.get_value(tag_map['OpIncome'], 0, annualize=True)
        data['NetIncome'], _ = self.get_value(tag_map['NetIncome'], 0, annualize=True)
        data['Depreciation'], _ = self.get_value(tag_map['Depreciation'], 0, annualize=True)
        data['OpeCF'], _ = self.get_value(tag_map['OpeCF'], 0, annualize=True)
        raw_capex, _ = self.get_value(tag_map['Capex'], 0, annualize=True)
        data['Capex'] = abs(raw_capex)

        if data['IssuedShares'] > 0 and data['TreasuryShares'] > data['IssuedShares']:
            data['TreasuryShares'] = 0.0
        data['RealShares'] = max(data['IssuedShares'] - data['TreasuryShares'], 0)
        if data['RealShares'] == 0 and data['IssuedShares'] > 0: data['RealShares'] = data['IssuedShares']

        data['EBITDA'] = data['OpIncome'] + data['Depreciation']
        data['NetDebt'] = data['Debt'] - data['Cash']
        data['FCF'] = data['OpeCF'] - data['Capex']

        prev_Assets, _ = self.get_value(tag_map['Assets'], 1, annualize=False)
        prev_OpIncome, _ = self.get_value(tag_map['OpIncome'], 1, annualize=True)
        prev_Depreciation, _ = self.get_value(tag_map['Depreciation'], 1, annualize=True)
        prev_EBITDA = prev_OpIncome + prev_Depreciation
        data['Prev_Assets'] = prev_Assets
        data['Prev_EBITDA'] = prev_EBITDA
        raw_asset_growth = (data['Assets'] - prev_Assets) / prev_Assets if prev_Assets > 0 else 0.0
        data['Asset_Growth'] = raw_asset_growth * 2.0 if 150 <= dur_days < 250 else raw_asset_growth
        data['PeriodEnd'] = self.target_date
        return data

# --- Market Data Loader ---
class MarketDataLoader:
    """外部データソース(EDINET, Yahoo)との通信およびデータセット構築(ETL)を担当"""
    def __init__(self, config: AlchemyConfig):
        self.config = config

    def get_target_list(self) -> pd.DataFrame:
        print(">>> [Loader] Fetching JPX Listed Companies...")
        url = "https://www.jpx.co.jp/english/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_e.xls"
        res = fetch_sync(url)
        if not res: return pd.DataFrame()
        try:
            df = pd.read_excel(io.BytesIO(res.content))
            cols = {c: c for c in df.columns}
            code_col = next((c for c in cols if 'Local Code' in str(c) or 'Code' in str(c)), 'Code')
            name_col = next((c for c in cols if 'Company Name' in str(c) or 'Name' in str(c)), 'Name')
            market_col = next((c for c in cols if 'Section/Products' in str(c) or 'Market' in str(c)), 'Market')
            sec_col = next((c for c in cols if '33 Sector' in str(c)), 'Sector')
            df = df.rename(columns={code_col: 'Code', name_col: 'Name', sec_col: 'Sector', market_col: 'Market'})
            df['Code'] = df['Code'].astype(str)
            df = df[df['Code'].str.len() == 4]
            return df[df['Market'].astype(str).str.contains('Standard|Growth', case=False)]
        except Exception as e:
            logging.error(f"JPX List Error: {e}")
            return pd.DataFrame()

    def scan_disclosure_metadata(self, target_codes: Set[str], reference_date: datetime.date, days_back: int) -> Dict[str, Dict[str, Any]]:
        print(f">>> [Loader] Scanning Disclosure Info ({days_back} Days prior to {reference_date})...")
        if not self.config.EDINET_API_KEY:
            print("   [Warning] API Key is missing.")
        
        doc_map = {}
        base_url = "https://disclosure.edinet-fsa.go.jp/api/v2/documents.json"
        dates = [reference_date - datetime.timedelta(days=i) for i in range(days_back)]
        
        for d in tqdm(dates, desc="Metadata"):
            res = fetch_sync(base_url, {'date': d, 'type': 2, 'Subscription-Key': self.config.EDINET_API_KEY})
            if not res: continue
            try:
                for item in res.json().get('results', []):
                    sec_code = item.get('secCode')
                    if not sec_code: continue
                    code = sec_code[:4]
                    if code not in target_codes: continue
                    dtype = item['docTypeCode']
                    desc = item.get('docDescription', '')
                    is_target = False
                    if dtype in ['010', '120', '130', '150']: is_target = True
                    elif dtype == '140' and any(q in desc for q in ['第2', '第２', '第二', 'Quarter']): is_target = True
                    if is_target:
                        if code not in doc_map: doc_map[code] = item
            except: continue
        return doc_map

    async def _process_xbrl_task(self, session: aiohttp.ClientSession, code: str, doc_info: Dict[str, Any], semaphore: asyncio.Semaphore, reference_date: datetime.date) -> Optional[Dict[str, Any]]:
        async with semaphore:
            url = f"https://disclosure.edinet-fsa.go.jp/api/v2/documents/{doc_info['docID']}"
            content = await fetch_with_retry_async(session, url, {'type': 1, 'Subscription-Key': self.config.EDINET_API_KEY})
            if not content: return None
            try:
                with zipfile.ZipFile(io.BytesIO(content)) as z:
                    xbrl_files = [f for f in z.namelist() if f.endswith('.xbrl') and 'PublicDoc' in f]
                    if not xbrl_files: return None
                    with z.open(xbrl_files[0]) as f:
                        parser = RobustXBRLParser(f.read(), self.config, reference_date)
                        metrics = parser.extract_metrics()
                        metrics['Code'] = code
                        return metrics
            except Exception as e:
                # logging.warning(f"XBRL process error for {code}: {e}")
                return None

    def download_xbrl_data(self, doc_map: Dict[str, Dict[str, Any]], reference_date: datetime.date) -> pd.DataFrame:
        print(f">>> [Loader] XBRL Async Download & Parsing (Tasks: {len(doc_map)})...")
        if not doc_map: return pd.DataFrame()
        async def _run_async_etl():
            semaphore = asyncio.Semaphore(10)
            tasks = []
            async with aiohttp.ClientSession() as session:
                for code, info in doc_map.items():
                    tasks.append(self._process_xbrl_task(session, code, info, semaphore, reference_date))
                results = await tqdm_asyncio.gather(*tasks)
            return [r for r in results if r is not None]

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import nest_asyncio
                nest_asyncio.apply()
                df_fin = loop.run_until_complete(_run_async_etl())
            else:
                df_fin = asyncio.run(_run_async_etl())
        except RuntimeError:
            df_fin = asyncio.run(_run_async_etl())
            
        return pd.DataFrame(df_fin)

    def fetch_historical_prices(self, codes: List[str], entry_date_str: str, exit_date_str: str) -> pd.DataFrame:
        print(f">>> [Loader] Fetching Historical Prices (PIT: {entry_date_str} to {exit_date_str})...")
        if not codes: return pd.DataFrame()
        tickers = [f"{c}.T" for c in codes]
        target_dt = datetime.datetime.strptime(entry_date_str, "%Y-%m-%d").date()
        eval_dt = datetime.datetime.strptime(exit_date_str, "%Y-%m-%d").date()
        
        def get_historical_info(ticker_symbol: str) -> Optional[Dict[str, float]]:
            try:
                t = yf.Ticker(ticker_symbol)
                hist_start = (target_dt - datetime.timedelta(days=400)).strftime("%Y-%m-%d")
                hist_end = (eval_dt + datetime.timedelta(days=10)).strftime("%Y-%m-%d")
                hist_adj = t.history(start=hist_start, end=hist_end, auto_adjust=True)
                if hist_adj.empty: return None
                hist_raw = t.history(start=hist_start, end=hist_end, auto_adjust=False)
                if hist_raw.empty: hist_raw = hist_adj.copy()

                def get_price(d, df, method='close'):
                    if df.index.tz is not None: df.index = df.index.tz_localize(None)
                    mask = df.index.date <= d if method == 'close' else df.index.date > d
                    sub = df[mask]
                    if sub.empty: return None
                    return sub.iloc[-1]['Close'] if method == 'close' else sub.iloc[0]['Open']

                entry_raw = get_price(target_dt, hist_raw, 'close')
                entry_adj = get_price(target_dt, hist_adj, 'open')
                exit_adj = get_price(eval_dt, hist_adj, 'close')

                if not entry_raw: return None
                entry_p = entry_adj if entry_adj else entry_raw
                exit_p = exit_adj if exit_adj else 0.0

                mom_dt = (pd.Timestamp(target_dt) - pd.DateOffset(months=1)).date()
                mom_p = get_price(mom_dt, hist_adj, 'close')
                momentum = (entry_p / mom_p - 1.0) if mom_p and mom_p > 0 else 0.0

                p_range = 0.5
                try:
                    mask_rng = (hist_raw.index.date > target_dt - datetime.timedelta(days=365)) & (hist_raw.index.date <= target_dt)
                    sub = hist_raw[mask_rng]
                    if not sub.empty:
                        h, l = sub['High'].max(), sub['Low'].min()
                        if h > l: p_range = (entry_raw - l) / (h - l)
                except: pass

                return {
                    'Code': ticker_symbol.replace('.T', ''), 'Price_Raw': float(entry_raw),
                    'Price': float(entry_p), 'Exit_Price': float(exit_p),
                    'Actual_Return': (exit_p / entry_p - 1.0) if entry_p > 0 and exit_p > 0 else 0.0,
                    'Price_Range': float(p_range), 'Momentum_1M': float(momentum)
                }
            except: return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(tqdm(executor.map(get_historical_info, tickers), total=len(tickers), desc="Threaded Fetch"))
        return pd.DataFrame([r for r in results if r is not None])

    def fetch_current_prices(self, codes: List[str]) -> pd.DataFrame:
        print(f">>> [Loader] Fetching Prices & Market Cap (Symbols: {len(codes)})...")
        if not codes: return pd.DataFrame()
        tickers = [f"{c}.T" for c in codes]

        def get_info(ticker_symbol: str) -> Optional[Dict[str, float]]:
            try:
                t = yf.Ticker(ticker_symbol)
                fi = t.fast_info
                price = fi.last_price
                if pd.isna(price): return None
                mkt_cap = fi.market_cap
                if pd.isna(mkt_cap): mkt_cap = price * t.info.get('sharesOutstanding', 0)
                
                high52, low52 = fi.year_high, fi.year_low
                price_range = (price - low52)/(high52 - low52) if high52 > low52 else 0.5
                
                momentum_1m = 0.0
                try:
                    hist = t.history(period="1mo")
                    if not hist.empty: momentum_1m = (price / hist['Close'].iloc[0]) - 1.0
                except: pass

                return {
                    'Code': ticker_symbol.replace('.T', ''), 'Price_Raw': float(price), 'Price': float(price),
                    'MarketCap': float(mkt_cap) if mkt_cap else 0.0, 'Price_Range': float(price_range), 'Momentum_1M': float(momentum_1m)
                }
            except: return None

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(tqdm(executor.map(get_info, tickers), total=len(tickers)))
        return pd.DataFrame([r for r in results if r is not None])
    
    def load_dataset_for_backtest(self, entry_date: str, exit_date: str, scan_days_back: int = 120) -> pd.DataFrame:
        """
        バックテスト用の完成されたデータセットを提供するメソッド
        Engine内にあった「キャッシュ確認・XBRL取得・結合」の全ロジックをここに集約。
        """
        snapshot_file = f'alchemy_snapshot_{entry_date}.csv'
        
        # 1. 財務データ (キャッシュ確認 or 作成)
        if os.path.exists(snapshot_file):
            print(f"   [Loader] Loading financial snapshot: {entry_date} ...", end="")
            df_fin_merged = pd.read_csv(snapshot_file)
            df_fin_merged['Code'] = df_fin_merged['Code'].astype(str)
            print(" Done.")
        else:
            print(f"   [Loader] Generating new snapshot for {entry_date}...")
            df_jpx = self.get_target_list()
            if df_jpx.empty: return pd.DataFrame()
            
            entry_dt = datetime.datetime.strptime(entry_date, "%Y-%m-%d").date()
            doc_map = self.scan_disclosure_metadata(set(df_jpx['Code']), entry_dt, days_back=scan_days_back)
            df_xbrl = self.download_xbrl_data(doc_map, reference_date=entry_dt)
            
            if df_xbrl.empty: return pd.DataFrame()
            
            df_fin_merged = df_jpx.merge(df_xbrl, on='Code', how='inner')
            df_fin_merged['DocTitle'] = df_fin_merged['Code'].map(lambda c: doc_map.get(c, {}).get('docDescription', ''))
            df_fin_merged.to_csv(snapshot_file, index=False)
        
        # 2. 株価データ (都度取得)
        df_price = self.fetch_historical_prices(df_fin_merged['Code'].unique().tolist(), entry_date, exit_date)
        if df_price.empty: return pd.DataFrame()

        # 3. 結合して返却
        return df_fin_merged.merge(df_price, on='Code', how='inner')
