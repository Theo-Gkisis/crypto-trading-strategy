from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, Float,
    String, DateTime, Boolean
)
from sqlalchemy.orm import DeclarativeBase, Session
from config.settings import DATABASE_URL

import logging
logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


class Trade(Base):
    """Κάθε γραμμή = ένα trade που έκανε ο bot."""
    __tablename__ = "trades"

    id         = Column(Integer, primary_key=True)
    symbol     = Column(String, nullable=False)        # "BTC/USDT"
    side       = Column(String, nullable=False)        # "buy" / "sell"
    strategy   = Column(String, nullable=False)        # "grid" / "trend" / "dca"
    price      = Column(Float, nullable=False)         # Τιμή εκτέλεσης
    quantity   = Column(Float, nullable=False)         # Ποσότητα crypto
    amount     = Column(Float, nullable=False)         # Αξία σε USDT
    pnl        = Column(Float, default=0.0)            # Κέρδος/ζημιά σε USDT
    order_id   = Column(String, nullable=True)         # Binance order ID
    timestamp  = Column(DateTime, default=datetime.now)


class DailySummary(Base):
    """Ημερήσια σύνοψη αποτελεσμάτων."""
    __tablename__ = "daily_summaries"

    id           = Column(Integer, primary_key=True)
    date         = Column(String, nullable=False)      # "2026-03-18"
    total_trades = Column(Integer, default=0)
    total_pnl    = Column(Float, default=0.0)
    winning      = Column(Integer, default=0)
    losing       = Column(Integer, default=0)
    timestamp    = Column(DateTime, default=datetime.now)


class Database:
    """Διαχειρίζεται όλες τις εγγραφές στη βάση δεδομένων."""

    def __init__(self):
        self.engine = create_engine(DATABASE_URL, echo=False)
        Base.metadata.create_all(self.engine)
        logger.info("Database initialized")

    # ----------------------------------------------------------
    # TRADES
    # ----------------------------------------------------------

    def save_trade(self, symbol: str, side: str, strategy: str,
                   price: float, quantity: float, amount: float,
                   pnl: float = 0.0, order_id: str = None):
        """Αποθηκεύει ένα trade στη βάση."""
        with Session(self.engine) as session:
            trade = Trade(
                symbol=symbol, side=side, strategy=strategy,
                price=price, quantity=quantity, amount=amount,
                pnl=pnl, order_id=order_id,
            )
            session.add(trade)
            session.commit()
            logger.debug(f"Trade saved: {side} {symbol} @ ${price:.2f}")

    def get_trades(self, symbol: str = None, limit: int = 100) -> list:
        """Επιστρέφει τα τελευταία trades."""
        with Session(self.engine) as session:
            query = session.query(Trade).order_by(Trade.timestamp.desc())
            if symbol:
                query = query.filter(Trade.symbol == symbol)
            return query.limit(limit).all()

    def get_daily_pnl(self) -> float:
        """Συνολικό PnL σημερινής ημέρας."""
        today = datetime.now().strftime("%Y-%m-%d")
        with Session(self.engine) as session:
            trades = session.query(Trade).filter(
                Trade.timestamp >= today
            ).all()
            return sum(t.pnl for t in trades)

    def get_total_pnl(self) -> float:
        """Συνολικό PnL όλων των ημερών."""
        with Session(self.engine) as session:
            trades = session.query(Trade).all()
            return sum(t.pnl for t in trades)

    # ----------------------------------------------------------
    # ΣΤΑΤΙΣΤΙΚΑ
    # ----------------------------------------------------------

    def get_stats(self) -> dict:
        """Επιστρέφει συνολικά στατιστικά."""
        with Session(self.engine) as session:
            all_trades = session.query(Trade).all()

            if not all_trades:
                return {
                    "total_trades": 0,
                    "total_pnl": 0.0,
                    "win_rate": 0.0,
                    "best_trade": 0.0,
                    "worst_trade": 0.0,
                }

            pnls    = [t.pnl for t in all_trades]
            winners = [p for p in pnls if p > 0]

            return {
                "total_trades": len(all_trades),
                "total_pnl":    round(sum(pnls), 4),
                "win_rate":     round(len(winners) / len(pnls) * 100, 1),
                "best_trade":   round(max(pnls), 4),
                "worst_trade":  round(min(pnls), 4),
                "daily_pnl":    round(self.get_daily_pnl(), 4),
            }

    def save_daily_summary(self):
        """Αποθηκεύει ημερήσια σύνοψη (καλείται κάθε βράδυ)."""
        today = datetime.now().strftime("%Y-%m-%d")
        with Session(self.engine) as session:
            trades = session.query(Trade).filter(
                Trade.timestamp >= today
            ).all()

            pnls    = [t.pnl for t in trades]
            winners = len([p for p in pnls if p > 0])
            losers  = len([p for p in pnls if p < 0])

            summary = DailySummary(
                date=today,
                total_trades=len(trades),
                total_pnl=sum(pnls),
                winning=winners,
                losing=losers,
            )
            session.add(summary)
            session.commit()
            logger.info(f"Daily summary saved: {today} | PnL=${sum(pnls):.3f}")
