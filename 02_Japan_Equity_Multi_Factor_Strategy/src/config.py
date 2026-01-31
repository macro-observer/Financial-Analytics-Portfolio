import os
from dataclasses import dataclass, field
from typing import List, Dict, Union

# --- Environment Setup ---
# ローカル開発用に .env ファイルから環境変数を読み込む
# サーバーやColabなど、ライブラリが存在しない環境でもエラーにならないよう処理
try:
    from dotenv import load_dotenv
    # カレントディレクトリまたは親ディレクトリの .env をロード
    # override=False (デフォルト) なので、システム環境変数が既にある場合はそちらが優先されます
    load_dotenv() 
except ImportError:
    pass

@dataclass
class AlchemyConfig:
    """戦略のパラメータおよび定数を一元管理するクラス"""

    # --- API Key Logic ---
    def _get_api_key() -> str:
        # 優先順位 1: 環境変数 (ローカルの .env または システム環境変数)
        key = os.getenv("EDINET_API_KEY")
        if key: return key

        # 優先順位 2: Google Colabのシークレット (Colab環境用)
        try:
            from google.colab import userdata
            return userdata.get('EDINET_API_KEY')
        except (ImportError, AttributeError, Exception):
            # Colabでない、またはキー未設定の場合は無視
            pass
            
        return ""

    EDINET_API_KEY: str = field(default_factory=_get_api_key)

    # --- Filtering Criteria ---
    MIN_MARKET_CAP_B: float = 5.0      # 最小時価総額 (億円)
    MAX_MARKET_CAP_B: float = 1000.0   # 最大時価総額 (億円) - 小型株効果狙い
    MAX_FCF_YIELD: float = 0.80        # FCF利回りの異常値除外
    MIN_PBR: float = 0.10              # PBRの異常値除外

    # --- Scoring Weights (Yartseva 2025 based) ---
    # Value(40%), Quality(30%) をコアエンジンとし、日本市場のPBR是正トレンドを考慮
    WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        'VAL': 0.40, 
        'ROA': 0.30, 
        'TECH': 0.175, 
        'SIZE': 0.125
    })
    
    TECH_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        'RANGE': 0.80, # Price Position
        'MOM': 0.20    # 1M Momentum
    })

    # --- XBRL Tag Mapping (Forensic ETL) ---
    # J-GAAP, IFRS, US-GAAPのタグ揺らぎを吸収するマッピング
    XBRL_TAG_MAP: Dict[str, List[str]] = field(default_factory=lambda: {
        'Assets': ['TotalAssets', 'Assets', 'AssetsIFRS', 'TotalAssetsIFRSSummaryOfBusinessResults', 'AssetsUSGAAP', 'jppfs_cor_TotalAssets', 'ifrs-full_Assets'],
        'NetAssets': ['NetAssets', 'TotalNetAssets', 'NetAssetsSummaryOfBusinessResults', 'TotalEquity', 'Equity', 'jppfs_cor_NetAssets', 'ifrs-full_Equity'],
        'Cash': ['CashAndDeposits', 'CashAndCashEquivalents', 'CashAndCashEquivalentsIFRS', 'jppfs_cor_CashAndDeposits', 'ifrs-full_CashAndCashEquivalents'],
        'Debt': ['ShortTermLoansPayable', 'CurrentPortionOfLongTermLoansPayable', 'LongTermLoansPayable', 'BondsPayable', 'InterestBearingDebt', 'BorrowingsCurrent', 'BorrowingsNonCurrent'],
        'OpIncome': ['OperatingIncome', 'OperatingIncomeLoss', 'OperatingProfit', 'OperatingProfitIFRS', 'jppfs_cor_OperatingIncome'],
        'NetIncome': ['CurrentNetIncome', 'NetIncome', 'ProfitLoss', 'Profit', 'NetIncomeLoss', 'jppfs_cor_CurrentNetIncome', 'ifrs-full_ProfitLoss', 'ProfitLossAttributableToOwnersOfParent'],
        'Depreciation': ['Depreciation', 'DepreciationAndAmortization', 'DepreciationAndAmortizationOpeCF', 'DepreciationExpense', 'AmortizationExpense'],
        'IssuedShares': [
            'TotalNumberOfIssuedSharesSummaryOfBusinessResults', 'TotalNumberOfIssuedShares', 'IssuedShares', 'NumberOfSharesIssued',
            'NumberOfSharesIssuedSharesVotingRights', 'NumberOfIssuedSharesAsOfFiscalYearEndIssuedSharesTotalNumberOfSharesEtc',
            'NumberOfIssuedSharesAsOfFilingDateIssuedSharesTotalNumberOfSharesEtc', 'jppfs_cor_TotalNumberOfIssuedShares'
        ],
        'TreasuryShares': [
            'TreasuryStockNumberOfShares', 'jppfs_cor_TreasuryStockNumberOfShares', 'NumberOfSharesHeldInOwnNameTreasurySharesEtc',
            'TotalNumberOfSharesHeldTreasurySharesEtc', 'TreasuryStock', 'TreasuryShares'
        ],
        'OpeCF': ['NetCashProvidedByUsedInOperatingActivities', 'CashFlowsFromOperatingActivities', 'CashFlowsFromUsedInOperatingActivities'],
        'Capex': [
            'PurchaseOfPropertyPlantAndEquipmentInvCF', 'PurchaseOfPropertyPlantAndEquipment', 'PurchaseOfTangibleFixedAssets',
            'PaymentsForPropertyPlantAndEquipment', 'IncreaseInPropertyPlantAndEquipmentAndIntangibleAssets',
            'CapitalExpendituresOverviewOfCapitalExpendituresEtc', 'CapitalExpenditures'
        ]
    })

    # --- Sector Mapping (TOPIX-17 Custom Mapping) ---
    SECTOR_MAP_17: Dict[Union[str, int], str] = field(default_factory=lambda: {
        'Fishery, Agriculture and Forestry': 'Foods', 50: 'Foods', 
        'Mining': 'Energy Resources', 1050: 'Energy Resources', 
        'Construction': 'Construction & Materials', 2050: 'Construction & Materials',
        'Foods': 'Foods', 3050: 'Foods', 
        'Textiles & Apparels': 'Raw Materials & Chemicals', 3100: 'Raw Materials & Chemicals', 
        'Pulp & Paper': 'Raw Materials & Chemicals', 3150: 'Raw Materials & Chemicals',
        'Chemicals': 'Raw Materials & Chemicals', 3200: 'Raw Materials & Chemicals', 
        'Pharmaceutical': 'Pharmaceutical', 3250: 'Pharmaceutical', 
        'Oil & Coal Products': 'Energy Resources', 3300: 'Energy Resources',
        'Rubber Products': 'Automobiles & Transportation Equipment', 3350: 'Automobiles & Transportation Equipment', 
        'Glass & Ceramics Products': 'Construction & Materials', 3400: 'Construction & Materials',
        'Iron & Steel': 'Steel & Nonferrous Metals', 3450: 'Steel & Nonferrous Metals', 
        'Nonferrous Metals': 'Steel & Nonferrous Metals', 3500: 'Steel & Nonferrous Metals', 
        'Metal Products': 'Construction & Materials', 3550: 'Construction & Materials',
        'Machinery': 'Machinery', 3600: 'Machinery', 
        'Electric Appliances': 'Electric Appliances & Precision Instruments', 3650: 'Electric Appliances & Precision Instruments', 
        'Transportation Equipment': 'Automobiles & Transportation Equipment', 3700: 'Automobiles & Transportation Equipment',
        'Precision Instruments': 'Electric Appliances & Precision Instruments', 3750: 'Electric Appliances & Precision Instruments', 
        'Other Products': 'Construction & Materials', 3800: 'Construction & Materials', 
        'Electric Power & Gas': 'Electric Power & Gas', 4050: 'Electric Power & Gas',
        'Land Transportation': 'Transportation & Logistics', 5050: 'Transportation & Logistics', 
        'Marine Transportation': 'Transportation & Logistics', 5100: 'Transportation & Logistics', 
        'Air Transportation': 'Transportation & Logistics', 5150: 'Transportation & Logistics',
        'Warehousing & Harbor Transportation Services': 'Transportation & Logistics', 5200: 'Transportation & Logistics', 
        'Information & Communication': 'IT & Services', 5250: 'IT & Services', 
        'Wholesale Trade': 'Commercial & Wholesale Trade', 6050: 'Commercial & Wholesale Trade',
        'Retail Trade': 'Retail Trade', 6100: 'Retail Trade', 
        'Banks': 'Banks', 7050: 'Banks', 
        'Securities & Commodity Futures': 'Financials (Ex Banks)', 7100: 'Financials (Ex Banks)', 
        'Insurance': 'Financials (Ex Banks)', 7150: 'Financials (Ex Banks)',
        'Other Financing Business': 'Financials (Ex Banks)', 7200: 'Financials (Ex Banks)', 
        'Real Estate': 'Real Estate', 8050: 'Real Estate', 
        'Services': 'IT & Services', 9050: 'IT & Services'
    })
