import warnings

from src.config import AlchemyConfig
from src.data_loader import MarketDataLoader
from src.model import AlchemyAlphaModel
from src.engine import BacktestEngine

def main():
    # 実運用モードのため警告を抑制
    warnings.filterwarnings("ignore")
    
    print("============================================================")
    print("   Alchemy Japan Equity Screener (Production Mode)")
    print("   Target: High Quality, Value & Accounting Integrity")
    print("============================================================")
    
    # 1. Initialize Components (Dependency Injection)
    print(">>> Initializing System Components...")
    config = AlchemyConfig()
    
    # APIキー有無の確認（Warningのみ）
    if not config.EDINET_API_KEY:
        print("   [Info] EDINET_API_KEY not found. Fetching metadata might be limited.")

    loader = MarketDataLoader(config)
    model = AlchemyAlphaModel(config)
    
    # Engineにコンポーネントを注入
    engine = BacktestEngine(config, model, loader)
    
    # 2. Run Live Screening
    # 本日時点のデータでスクリーニングを実行し、Top 30を表示
    engine.run_live_screening(top_n=30)

if __name__ == "__main__":
    main()
