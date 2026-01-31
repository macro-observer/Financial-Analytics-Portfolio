import os
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import List

from .config import AlchemyConfig
from .model import AlchemyAlphaModel
from .data_loader import MarketDataLoader

class BacktestEngine:
    """
    データ(Loader)とロジック(Model)を組み合わせて実行するエンジン。
    過去検証(Backtest)と本番実行(Live)の両方を担当する。
    """
    def __init__(self, config: AlchemyConfig, model: AlchemyAlphaModel, data_loader: MarketDataLoader):
        self.config = config
        self.model = model
        self.loader = data_loader

    # ==========================================
    # [View Layer] 表示・可視化機能
    # ==========================================
    def display_top_picks(self, df_res: pd.DataFrame, top_n: int = 30) -> None:
        if df_res.empty: return
        print("-" * 110)
        has_return = 'Actual_Return' in df_res.columns
        header = f"{'Code':<6} {'Name':<18} {'Sector':<18} {'Price':>8} {'Mkv(B)':>8} {'P_Rng':>6} {'Mom1M':>7} {'FCF%':>7} {'PBR':>6} {'ROA':>6} {'Score':>6}"
        if has_return: header += f" {'Return':>7}"
        print(header); print("-" * 110)
        
        for _, row in df_res.head(top_n).iterrows():
            try:
                name = str(row['Name'])[:16] + '..' if len(str(row['Name'])) > 16 else str(row['Name'])
                sec = str(row['Sector17'])[:16] + '..' if len(str(row['Sector17'])) > 16 else str(row['Sector17'])
                fcf_y, pbr, roa = row.get('FCF_Yield',0), row.get('PBR',0), row.get('ROA',0)
                
                line = (f"{str(row['Code']):<6} {name:<18} {sec:<18} {row['Price']:>8,.0f} {row['MarketCap_B']:>8.1f} {row['Price_Range']:>6.2f} "
                        f"{row['Momentum_1M']:>7.1%} {fcf_y:>7.1%} {pbr:>6.2f} {roa:>6.1%} {row['Total_Score']:>6.2f}")
                if has_return: line += f" {row.get('Actual_Return', 0.0):>7.1%}"
                print(line)
            except: continue
        print("-" * 110)

    def visualize_results(self, df_res: pd.DataFrame, top_n: int = 30) -> None:
        print(">>> [Visualizing] Generating Strategy Analytics Charts...")
        if df_res.empty: return
        top_picks = df_res.sort_values('Total_Score', ascending=False).head(top_n)
        
        sns.set(style="whitegrid")
        try:
            import japanize_matplotlib
            plt.rcParams['font.family'] = 'IPAexGothic'
        except ImportError:
            pass

        plt.figure(figsize=(20, 12)); plt.subplots_adjust(hspace=0.3)
        
        plt.subplot(2, 2, 1)
        sns.scatterplot(data=df_res, x='FCF_Yield', y='ROA', color='lightgray', alpha=0.5, label='Universe')
        sns.scatterplot(data=top_picks, x='FCF_Yield', y='ROA', color='red', s=100, marker='*', label='Top Picks')
        plt.title('Quality (ROA) vs Value (FCF Yield) Map', fontsize=14, fontweight='bold'); plt.legend()
        
        plt.subplot(2, 2, 2)
        sns.histplot(data=df_res, x='Total_Score', kde=True, bins=30, color='steelblue')
        if not top_picks.empty: plt.axvline(top_picks['Total_Score'].min(), color='red', linestyle='--', label='Cutoff')
        plt.title('Total Score Distribution', fontsize=14, fontweight='bold'); plt.legend()
        
        plt.subplot(2, 1, 2)
        try:
            order = df_res.groupby('Sector17')['Total_Score'].median().sort_values(ascending=False).index
            sns.boxplot(data=df_res, x='Sector17', y='Total_Score', order=order, palette='viridis')
            plt.title('Sector-Neutrality Check', fontsize=14, fontweight='bold'); plt.xticks(rotation=45, ha='right')
        except: pass
        plt.tight_layout(); plt.show()

    def _calc_cumulative(self, returns_list: List[float]) -> float:
        res = 1.0
        for r in returns_list: res *= (1.0 + r)
        return res - 1.0

    # ==========================================
    # [Execution Layer] バックテスト実行ロジック
    # ==========================================
    def run_period(self, entry_date: str, exit_date: str, scan_days_back: int = 120, display_top: bool = True) -> pd.DataFrame:
        print(f"\n   Processing: {entry_date} -> {exit_date}")
        
        # 1. Pipeline: Load Data (from Loader)
        df_merged = self.loader.load_dataset_for_backtest(entry_date, exit_date, scan_days_back)
        if df_merged.empty:
            print("   [Skip] No data available.")
            return pd.DataFrame()

        # 2. Pipeline: Calculate Alpha (from Model)
        df_final = self.model.run(df_merged)

        # 3. Pipeline: Report
        if display_top and not df_final.empty:
            print(f"   [Top Picks for {entry_date}]")
            self.display_top_picks(df_final, top_n=20)
            top = df_final.iloc[0]
            ret_str = f", Return: {top['Actual_Return']:.1%}" if 'Actual_Return' in top else ""
            print(f"   -> Top 1: {top['Name']} (Score: {top['Total_Score']:.2f}{ret_str})")
        return df_final

    def run_annual_rebalancing_strategy(self, start_year: int = 2016, end_year: int = 2025):
        print("\n" + "#"*80 + "\n>>> STRATEGY 1: Annual Rebalancing\n" + "#"*80)
        history_returns = {10: [], 15: [], 20: [], 30: []}
        for year in range(start_year, end_year):
            df_result = self.run_period(f"{year}-06-30", f"{year+1}-06-30")
            if not df_result.empty:
                metrics = []
                for n in history_returns.keys():
                    avg_ret = df_result.head(n)['Actual_Return'].mean()
                    history_returns[n].append(avg_ret)
                    metrics.append(f"Top{n}: {avg_ret:>6.1%}")
                print(f"   [Year {year} Result] " + " | ".join(metrics))
            else:
                for n in history_returns.keys(): history_returns[n].append(0.0)

        # 集計結果の表示
        print("\n" + "="*80)
        print(">>> STRATEGY 1 SUMMARY: Cumulative Returns (Rebalanced)")
        print("="*80)
        print(f"{'Top N':<8} | {'3 Years':<10} | {'5 Years':<10} | {'9 Years':<10} | {'Avg Annual':<10}")
        print("-" * 60)

        for n in sorted(history_returns.keys()):
            hist = history_returns[n]
            if not hist: continue
            cum_3y = self._calc_cumulative(hist[-3:]) if len(hist) >= 3 else float('nan')
            cum_5y = self._calc_cumulative(hist[-5:]) if len(hist) >= 5 else float('nan')
            cum_9y = self._calc_cumulative(hist[-9:]) if len(hist) >= 9 else float('nan')
            avg_ann = sum(hist) / len(hist)

            def fmt(v): return f"{v:>9.1%}" if not pd.isna(v) else "   N/A   "
            print(f"Top {n:<4} | {fmt(cum_3y)} | {fmt(cum_5y)} | {fmt(cum_9y)} | {avg_ann:>9.1%}")
        print("="*80)

    def run_buy_and_hold_strategy(self, start_years: List[int], final_exit_date: str):
        print("\n" + "#"*80 + "\n>>> STRATEGY 2: Buy & Hold\n" + "#"*80)
        print(f"{'Entry Date':<12} | {'Duration':<10} | {'Top 10':<10} | {'Top 15':<10} | {'Top 20':<10} | {'Top 30':<10}\n" + "-" * 75)
        for start_year in start_years:
            entry_date = f"{start_year}-06-30"
            if entry_date > final_exit_date: continue
            df_bh = self.run_period(entry_date, final_exit_date, display_top=False)
            if not df_bh.empty:
                dur = round((datetime.datetime.strptime(final_exit_date, "%Y-%m-%d") - datetime.datetime.strptime(entry_date, "%Y-%m-%d")).days / 365.25, 1)
                r = {n: df_bh.head(n)['Actual_Return'].mean() for n in [10, 15, 20, 30]}
                print(f"{entry_date:<12} | {dur} Years   | {r[10]:>9.1%} | {r[15]:>9.1%} | {r[20]:>9.1%} | {r[30]:>9.1%}")
        print("="*80)

    # ==========================================
    # [Live Layer] ライブスクリーニング実行
    # ==========================================
    def run_live_screening(self, top_n: int = 50):
        """本日時点のデータでスクリーニングを実行"""
        print("\n" + "="*50 + "\n>>> STARTING LIVE SCREENING...\n" + "="*50)
        today_dt = datetime.date.today()
        today_str = today_dt.strftime("%Y-%m-%d")
        db_filename = f'alchemy_live_{today_str}.csv'
        
        # 1. Pipeline: Load Data (Cache or Fresh)
        if os.path.exists(db_filename):
            print(f">>> Loading live cache: {today_str}...")
            df_merged = pd.read_csv(db_filename)
            df_merged['Code'] = df_merged['Code'].astype(str)
        else:
            # Loaderの機能を組み合わせてライブデータを構築
            df_jpx = self.loader.get_target_list()
            if df_jpx.empty: return
            
            # 過去1年分のXBRLをスキャンして最新を見つける
            doc_map = self.loader.scan_disclosure_metadata(set(df_jpx['Code']), today_dt, days_back=365)
            df_fin = self.loader.download_xbrl_data(doc_map, reference_date=today_dt)
            if df_fin.empty:
                print(">>> No financial data found."); return

            # 最新株価取得
            df_price = self.loader.fetch_current_prices(df_fin['Code'].unique().tolist())
            
            # 結合
            df_merged = df_jpx.merge(df_fin, on='Code', how='inner').merge(df_price, on='Code', how='inner')
            df_merged['DocTitle'] = df_merged['Code'].map(lambda c: doc_map.get(c, {}).get('docDescription', ''))
            df_merged.to_csv(db_filename, index=False)
            print(f">>> [ETL Complete] Data saved: {db_filename}")

        # 2. Pipeline: Calculate Alpha
        df_final = self.model.run(df_merged)

        # 3. Pipeline: Report
        self.display_top_picks(df_final, top_n=top_n)
        self.visualize_results(df_final, top_n=top_n)
