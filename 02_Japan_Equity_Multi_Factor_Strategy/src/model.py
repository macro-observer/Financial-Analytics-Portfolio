import pandas as pd
import numpy as np
from typing import Dict, List
from .config import AlchemyConfig

class AlchemyAlphaModel:
    """論文ロジックの実装クラス（純粋関数的動作）"""
    def __init__(self, config: AlchemyConfig):
        self.config = config

    def calculate_factors(self, df_merged: pd.DataFrame) -> pd.DataFrame:
        print(">>> [Model] Calculating Fundamentals & Risk Checks...")
        df = df_merged.copy()
        cols_to_num = ['Price_Raw', 'RealShares', 'NetDebt', 'FCF', 'EBITDA', 'Assets', 'NetAssets',
                       'Prev_Assets', 'Prev_EBITDA', 'Price_Range', 'Momentum_1M', 'Asset_Growth',
                       'OpIncome', 'NetIncome', 'OpeCF']
        for c in cols_to_num:
            if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0.0)

        if 'MarketCap' not in df.columns or df['MarketCap'].sum() == 0:
             df['MarketCap'] = df['Price_Raw'] * df['RealShares']
        df = df[df['MarketCap'] > 0].copy()

        df['TEV'] = df['MarketCap'] + df['NetDebt']
        df['TEV'] = np.where(df['TEV'] <= 0, df['MarketCap'], df['TEV'])
        df['TEV_B'] = df['TEV'] / 1e9
        df['MarketCap_B'] = df['MarketCap'] / 1e9
        df['FCF_Yield'] = df['FCF'] / df['MarketCap']
        df['ROA'] = np.where(df['Assets'] > 0, df['EBITDA'] / df['Assets'], 0.0)
        df['PBR'] = np.where(df['NetAssets'] > 0, df['MarketCap'] / df['NetAssets'], np.nan)

        df['Delta_Assets'] = df['Assets'] - df['Prev_Assets']
        df['Delta_EBITDA'] = df['EBITDA'] - df['Prev_EBITDA']
        prev_roa = np.where(df['Prev_Assets'] > 0, df['Prev_EBITDA'] / df['Prev_Assets'], 0.05)
        required_growth = df['Delta_Assets'] * np.maximum(prev_roa, 0.05)
        df['Is_Efficient'] = np.where(df['Delta_Assets'] > 0, df['Delta_EBITDA'] >= required_growth, True)

        # Forensic Check: Modified Sloan Ratio
        avg_assets = np.where(df['Prev_Assets'] > 0, (df['Assets'] + df['Prev_Assets']) / 2.0, df['Assets'])
        avg_assets = np.where(avg_assets == 0, np.nan, avg_assets)
        if 'NetIncome' not in df.columns: df['NetIncome'] = 0.0
        
        # 営業利益ではなくNetIncomeを使用(Modified Sloan)
        net_income = np.where(df['NetIncome'] != 0, df['NetIncome'], df['OpIncome'])
        df['Sloan_Ratio'] = (net_income - df['OpeCF']) / avg_assets
        df['Fraud_Flag'] = np.where(df['Sloan_Ratio'].abs() > 0.10, 1, 0)

        cols = ['Code', 'Name', 'Sector', 'Market', 'Price', 'MarketCap_B', 'TEV_B', 'Price_Range',
                'Momentum_1M', 'FCF_Yield', 'PBR', 'ROA', 'Asset_Growth', 'Is_Efficient', 'FCF',
                'DocTitle', 'Actual_Return', 'Exit_Price', 'Fraud_Flag', 'Sloan_Ratio']
        if 'DocTitle' not in df.columns: df['DocTitle'] = ''
        return df[[c for c in cols if c in df.columns]].copy()

    def _calc_robust_z(self, series: pd.Series, use_log: bool = False) -> np.ndarray:
        vals = pd.to_numeric(series, errors='coerce').fillna(0).values
        if use_log: vals = np.log1p(np.maximum(vals, 1e-9))
        median = np.median(vals)
        mad = np.median(np.abs(vals - median))
        if mad == 0: return np.zeros(len(vals))
        z = 0.6745 * (vals - median) / mad
        return np.clip(z, -3.5, 3.5)

    def compute_scores(self, df_res: pd.DataFrame) -> pd.DataFrame:
        print(">>> [Model] Scoring & Ranking... (Sector Neutral)")
        if df_res.empty: return pd.DataFrame()
        df_res['Sector17'] = df_res['Sector'].map(self.config.SECTOR_MAP_17).fillna('Others')

        df_res['z_fcf'] = df_res.groupby('Sector17')['FCF_Yield'].transform(lambda x: self._calc_robust_z(x, False))
        df_res['z_roa'] = df_res.groupby('Sector17')['ROA'].transform(lambda x: self._calc_robust_z(x, False))
        df_res['z_mom'] = df_res.groupby('Sector17')['Momentum_1M'].transform(lambda x: self._calc_robust_z(x, False))
        
        df_res['Price_Range'] = df_res['Price_Range'].fillna(0.5)
        df_res['z_tech'] = -df_res.groupby('Sector17')['Price_Range'].transform(lambda x: self._calc_robust_z(x, False))
        df_res['z_pbr'] = -df_res.groupby('Sector17')['PBR'].transform(lambda x: self._calc_robust_z(x, True))
        df_res['z_size'] = -df_res.groupby('Sector17')['TEV_B'].transform(lambda x: self._calc_robust_z(x, True))

        w, wt = self.config.WEIGHTS, self.config.TECH_WEIGHTS
        df_res['S_Val'] = (df_res['z_fcf'] * 0.6 + df_res['z_pbr'] * 0.4)
        df_res['S_ROA'] = df_res['z_roa']
        df_res['S_Tech'] = (df_res['z_tech'] * wt['RANGE']) + (df_res['z_mom'] * wt['MOM'])
        df_res['S_Size'] = df_res['z_size']

        m_fcf = self._calc_robust_z(df_res['FCF_Yield'], False)
        m_pbr = self._calc_robust_z(df_res['PBR'], True)
        m_roa = self._calc_robust_z(df_res['ROA'], False)
        df_res['M_Val'] = (m_fcf * 0.6 + (-m_pbr) * 0.4)
        df_res['M_ROA'] = m_roa

        df_res['Total_Score'] = ((df_res['S_Val'] * 0.7 + df_res['M_Val'] * 0.3) * w['VAL'] +
                                 (df_res['S_ROA'] * 0.7 + df_res['M_ROA'] * 0.3) * w['ROA'] +
                                 df_res['S_Tech'] * w['TECH'] + df_res['S_Size'] * w['SIZE'])
        return df_res

    def apply_filters(self, df_scored: pd.DataFrame) -> pd.DataFrame:
        c = self.config
        initial_count = len(df_scored)
        mask = (
            (df_scored['MarketCap_B'] >= c.MIN_MARKET_CAP_B) &
            (df_scored['MarketCap_B'] < c.MAX_MARKET_CAP_B) &
            (df_scored['FCF_Yield'] < c.MAX_FCF_YIELD) &
            (df_scored['PBR'] > c.MIN_PBR) &
            (df_scored['FCF'] > 0) &
            (df_scored['Asset_Growth'] >= 0) &
            (df_scored['Is_Efficient'] == True) &
            (df_scored['Fraud_Flag'] == 0)
        )
        df = df_scored[mask].copy()
        print(f"   -> Ranked & Filtered: {initial_count} -> {len(df)}")
        return df.sort_values('Total_Score', ascending=False)

    def run(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        df_factors = self.calculate_factors(df_raw)
        df_scored = self.compute_scores(df_factors)
        return self.apply_filters(df_scored)
