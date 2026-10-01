//+------------------------------------------------------------------+
//| GoldSupplyDemand.mq5                                             |
//| Supply/demand zone EA for XAUUSD, first-touch limit entries.     |
//|                                                                  |
//| ZONE (demand; supply is the mirror)                              |
//|   base     1..InpBaseMax candles, each range <= InpBaseATR x ATR |
//|   leg-out  next candle: range >= InpLegATR x ATR, body >= 60% of |
//|            its range, closes above the base's highest high       |
//|   proximal highest body of the base      -> buy limit here       |
//|   distal   lowest low of base + leg-out  -> stop below this      |
//|   height   proximal-distal <= InpMaxZoneATR x ATR                |
//| ORDER      one pending at a time; a newer zone replaces it.      |
//|            Cancelled after InpLifeBars, or when a bar closes     |
//|            beyond the distal line before it fills.               |
//| STOP       distal -/+ InpStopBufATR x ATR                        |
//| TARGET     InpRR x risk                                          |
//| SIZE       InpRiskPct of equity per trade                        |
//| FILTERS    EMA trend, max spread, and no new orders near         |
//|            scheduled US news times (server time)                 |
//|                                                                  |
//| Backtest of these rules on COMEX gold futures (GC=F), 1bp cost,  |
//| defaults, scripts/supply_demand.py in the pinescript repo:       |
//|   1h  2 years   77 trades  29.9% win  PF 0.80  -11.5R            |
//|   30m 59 days   14 trades  50.0% win  PF 1.82   +6.0R            |
//|   15m 59 days   33 trades  45.5% win  PF 1.48   +9.3R            |
//| On 15m and 30m the first half of the sample made money and the   |
//| second half lost. The only 2-year test loses. Run it on demo     |
//| first.                                                           |
//+------------------------------------------------------------------+
#property copyright "neofinn/pinescript"
#property version   "1.00"

#include <Trade/Trade.mqh>

//--- zone detection
input ENUM_TIMEFRAMES InpTF          = PERIOD_M15; // Timeframe for zones
input int             InpATRPeriod   = 14;         // ATR period
input int             InpBaseMax     = 3;          // Max base candles
input double          InpBaseATR     = 0.8;        // Base candle max range (x ATR)
input double          InpLegATR      = 1.5;        // Leg-out min range (x ATR)
input double          InpMaxZoneATR  = 2.0;        // Max zone height (x ATR)
//--- trade
input double          InpRiskPct     = 1.0;        // Risk per trade (% equity)
input double          InpRR          = 2.0;        // Reward : risk
input double          InpStopBufATR  = 0.1;        // Stop buffer beyond distal (x ATR)
input int             InpLifeBars    = 48;         // Pending order life (bars)
input bool            InpTrend       = true;       // Trend filter: trade with EMA
input int             InpEMAPeriod   = 200;        // Trend EMA period
input int             InpMaxSpread   = 60;         // Max spread to place order (points)
//--- news window (SERVER time; defaults suit a GMT+3 broker in US summer time)
input bool            InpNewsFilter  = true;       // Block new orders near news
input string          InpNewsTimes   = "15:30,16:30,17:00,21:00"; // HH:MM, server time
input int             InpNewsMinutes = 15;         // Minutes before/after each time
input bool            InpNewsCancel  = true;       // Also cancel pending inside window
//--- misc
input long            InpMagic       = 260930;     // Magic number
input bool            InpDraw        = true;       // Draw zones on chart

CTrade   trade;
int      hATR = INVALID_HANDLE, hEMA = INVALID_HANDLE;
datetime lastBar = 0;
// the one live pending order
ulong    pTicket = 0;
int      pSide   = 0;
double   pDistal = 0;
datetime pExpiry = 0;
int      newsMin[];          // news times as minutes after midnight

//+------------------------------------------------------------------+
int OnInit()
{
   hATR = iATR(_Symbol, InpTF, InpATRPeriod);
   hEMA = iMA(_Symbol, InpTF, InpEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);
   if(hATR == INVALID_HANDLE || hEMA == INVALID_HANDLE)
   {
      Print("Indicator handle failed");
      return INIT_FAILED;
   }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   ParseNews();
   // Zone state is not persisted; remove our stale pendings after a restart.
   DeleteOurPendings();
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(hATR);
   IndicatorRelease(hEMA);
}

//+------------------------------------------------------------------+
void OnTick()
{
   if(InpNewsFilter && InpNewsCancel && InNewsWindow() && pTicket != 0)
      CancelPending("news window");

   datetime t = iTime(_Symbol, InpTF, 0);
   if(t == 0 || t == lastBar)
      return;
   lastBar = t;

   ManagePending();
   DetectZone();
}

//+------------------------------------------------------------------+
//| Cancel the pending order on expiry or invalidation (bar 1 close)|
//+------------------------------------------------------------------+
void ManagePending()
{
   if(pTicket == 0)
      return;
   if(!OrderSelect(pTicket))          // filled or removed
   {
      pTicket = 0;
      return;
   }
   double c1 = iClose(_Symbol, InpTF, 1);
   if(TimeCurrent() >= pExpiry)
      CancelPending("expired");
   else if((pSide == 1 && c1 < pDistal) || (pSide == -1 && c1 > pDistal))
      CancelPending("zone broken");
}

//+------------------------------------------------------------------+
//| Bar 1 is the candidate leg-out, bars 2.. are the base            |
//+------------------------------------------------------------------+
void DetectZone()
{
   double atrBuf[1], emaBuf[1];
   if(CopyBuffer(hATR, 0, 2, 1, atrBuf) != 1 || CopyBuffer(hEMA, 0, 1, 1, emaBuf) != 1)
      return;
   double A = atrBuf[0];
   if(A <= 0)
      return;

   double o1 = iOpen(_Symbol, InpTF, 1), h1 = iHigh(_Symbol, InpTF, 1);
   double l1 = iLow(_Symbol, InpTF, 1),  c1 = iClose(_Symbol, InpTF, 1);
   double rng = h1 - l1;
   if(rng < InpLegATR * A || MathAbs(c1 - o1) < 0.6 * rng)
      return;

   int k = 0;
   while(k < InpBaseMax)
   {
      int s = 2 + k;
      if(iHigh(_Symbol, InpTF, s) - iLow(_Symbol, InpTF, s) > InpBaseATR * A)
         break;
      k++;
   }
   if(k == 0)
      return;

   double bHi = -DBL_MAX, bLo = DBL_MAX, bodyHi = -DBL_MAX, bodyLo = DBL_MAX;
   for(int s = 2; s < 2 + k; s++)
   {
      double o = iOpen(_Symbol, InpTF, s), c = iClose(_Symbol, InpTF, s);
      bHi    = MathMax(bHi, iHigh(_Symbol, InpTF, s));
      bLo    = MathMin(bLo, iLow(_Symbol, InpTF, s));
      bodyHi = MathMax(bodyHi, MathMax(o, c));
      bodyLo = MathMin(bodyLo, MathMin(o, c));
   }

   int side = 0;
   double prox = 0, dist = 0;
   if(c1 > o1 && c1 > bHi)
   {
      if(InpTrend && c1 < emaBuf[0]) return;
      side = 1;  prox = bodyHi; dist = MathMin(bLo, l1);
   }
   else if(c1 < o1 && c1 < bLo)
   {
      if(InpTrend && c1 > emaBuf[0]) return;
      side = -1; prox = bodyLo; dist = MathMax(bHi, h1);
   }
   else
      return;

   if(prox == dist || MathAbs(prox - dist) > InpMaxZoneATR * A)
      return;

   datetime t0 = iTime(_Symbol, InpTF, 1 + k);
   if(InpDraw)
      DrawZone(side, t0, prox, dist);

   if(HasOurPosition())
      return;                       // one position at a time
   if(InpNewsFilter && InNewsWindow())
      return;
   if(SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpread)
      return;

   PlaceOrder(side, prox, dist, A);
}

//+------------------------------------------------------------------+
void PlaceOrder(int side, double prox, double dist, double A)
{
   double tick  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double minD  = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;

   double entry = NormPrice(prox, tick);
   double sl    = NormPrice(dist - side * InpStopBufATR * A, tick);
   double risk  = MathAbs(entry - sl);
   double tp    = NormPrice(entry + side * InpRR * risk, tick);

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   // a limit must sit on the far side of the market, outside the stops level
   if(side == 1  && entry >= ask - minD) return;
   if(side == -1 && entry <= bid + minD) return;
   if(risk < minD || risk <= 0) return;

   double lots = LotsForRisk(risk);
   if(lots <= 0)
   {
      PrintFormat("Zone skipped: %.2f%% risk is below the minimum lot", InpRiskPct);
      return;
   }

   if(pTicket != 0)
      CancelPending("replaced by newer zone");

   bool ok = (side == 1)
      ? trade.BuyLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "SD demand")
      : trade.SellLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "SD supply");
   if(!ok)
   {
      PrintFormat("Order failed: %d %s", trade.ResultRetcode(), trade.ResultRetcodeDescription());
      return;
   }
   pTicket = trade.ResultOrder();
   pSide   = side;
   pDistal = dist;
   pExpiry = TimeCurrent() + InpLifeBars * PeriodSeconds(InpTF);
}

//+------------------------------------------------------------------+
double LotsForRisk(double priceRisk)
{
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickVal  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE_LOSS);
   if(tickVal <= 0) tickVal = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   if(tickSize <= 0 || tickVal <= 0) return 0;

   double money   = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
   double perLot  = priceRisk / tickSize * tickVal;
   double step    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lots    = MathFloor(money / perLot / step) * step;   // round down, never up
   if(lots < vmin) return 0;                                    // do not oversize
   return MathMin(lots, vmax);
}

double NormPrice(double p, double tick)
{
   return NormalizeDouble(MathRound(p / tick) * tick, _Digits);
}

//+------------------------------------------------------------------+
bool HasOurPosition()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
      if(PositionGetTicket(i) > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol
         && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return true;
   return false;
}

void CancelPending(string why)
{
   if(pTicket != 0 && OrderSelect(pTicket))
   {
      if(trade.OrderDelete(pTicket))
         PrintFormat("Pending %I64u cancelled: %s", pTicket, why);
   }
   pTicket = 0;
}

void DeleteOurPendings()
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      ulong t = OrderGetTicket(i);
      if(t > 0 && OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagic)
         trade.OrderDelete(t);
   }
}

//+------------------------------------------------------------------+
void ParseNews()
{
   ArrayResize(newsMin, 0);
   string parts[];
   int n = StringSplit(InpNewsTimes, ',', parts);
   for(int i = 0; i < n; i++)
   {
      string hm[];
      StringTrimLeft(parts[i]);
      StringTrimRight(parts[i]);
      if(StringSplit(parts[i], ':', hm) != 2) continue;
      int m = (int)StringToInteger(hm[0]) * 60 + (int)StringToInteger(hm[1]);
      int sz = ArraySize(newsMin);
      ArrayResize(newsMin, sz + 1);
      newsMin[sz] = m;
   }
}

bool InNewsWindow()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int now = dt.hour * 60 + dt.min;
   for(int i = 0; i < ArraySize(newsMin); i++)
   {
      int d = now - newsMin[i];
      if(d < 0) d = -d;
      if(1440 - d < d) d = 1440 - d;
      if(d <= InpNewsMinutes) return true;
   }
   return false;
}

//+------------------------------------------------------------------+
void DrawZone(int side, datetime t0, double prox, double dist)
{
   string name = StringFormat("SD_%s_%I64d", side == 1 ? "D" : "S", (long)t0);
   if(ObjectFind(0, name) >= 0) return;
   datetime t1 = t0 + (InpLifeBars + 2) * PeriodSeconds(InpTF);
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, t0, prox, t1, dist);
   ObjectSetInteger(0, name, OBJPROP_COLOR, side == 1 ? clrSeaGreen : clrIndianRed);
   ObjectSetInteger(0, name, OBJPROP_FILL, true);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
}
//+------------------------------------------------------------------+
