#region Using declarations
using System;
using System.Collections.Generic;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
#endregion

// ============================================================================
//  DZ_SW_Financial_S021 — ФИНАНСОВЫЙ МОДУЛЬ УПРАВЛЕНИЯ ПОЗИЦИЕЙ, v1.0
//
//  Подключается к коммутатору DZ_SW_Hub_S021. Ордеров НЕ создаёт: порождает
//  только требования SwAction, которые исполняет SwExecutionModule.
//
//  ТРИ УРОКА ПРЕДЫДУЩЕЙ СИСТЕМЫ, ЗАЛОЖЕННЫЕ В ОСНОВАНИЕ.
//
//  1. СТУПЕНИ СЧИТАЮТСЯ ПО ПОДТВЕРЖДЁННЫМ ИСПОЛНЕНИЯМ, а не по факту отправки
//     заявки. Отправленная ступень может быть отклонена, отменена или
//     исполнена частично. Источник истины — OnExecutionUpdate коммутатора.
//     В прежней системе каскад строился на отправке, и уровень безубытка
//     привязывался к цене, по которой ничего не исполнилось.
//
//  2. ЗАПРЕТ ПЕРЕНОСА СТОПА ПОСЛЕ ПЕРВОЙ ФИКСАЦИИ подавляет ОБЕ ветви:
//     и безубыток, и трейлинг. Подавление одной делает запрет формальным,
//     потому что защиту продолжает двигать вторая.
//
//  3. БЕЗУБЫТОК И ТРЕЙЛИНГ НЕ СПОРЯТ. Когда оба хотят двинуть стоп, берётся
//     уровень, СИЛЬНЕЕ сокращающий риск. Кто именно предложил — неважно.
//
//  ЕДИНИЦЫ ИЗМЕРЕНИЯ. Внутри модуля всё считается в тиках; деньги возникают
//  только на границе через TickValue = TickSize × PointValue. Это устраняет
//  класс ошибок, где доллар движения цены путается с долларом результата.
// ============================================================================

namespace NinjaTrader.NinjaScript
{
    /// <summary>Как определяется объём позиции.</summary>
    public enum SwSizingMode
    {
        FixedQuantity,
        RiskMoneyPerTrade,
        RiskPercentOfEquity
    }

    /// <summary>Как задаётся стартовый стоп.</summary>
    public enum SwStopMode
    {
        FixedTicks,
        PriceDollars,      // доллары ДВИЖЕНИЯ ЦЕНЫ, не результата
        AtrMultiple
    }

    /// <summary>В чём измеряется расстояние до ступеней фиксации.</summary>
    public enum SwStepDistanceMode
    {
        FixedTicks,
        PriceDollars,
        RMultiple          // доли начального риска; финансово корректная мера
    }

    /// <summary>Когда переносить стоп в безубыток.</summary>
    public enum SwBreakevenMode
    {
        Off,
        AfterStep1,
        AfterStep2,
        AtRMultiple
    }

    /// <summary>Режим трейлинга.</summary>
    public enum SwTrailMode
    {
        Off,
        FixedDistance,     // фиксированное расстояние от экстремума
        AtrMultiple,       // множитель ATR от экстремума
        StepLock           // после каждой ступени стоп на уровень предыдущей
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    /// <summary>
    /// Настройки финансового модуля. Заполняются коммутатором из свойств
    /// окна параметров один раз при подключении.
    /// </summary>
    public class SwFinancialConfig
    {
        // --- объём ---
        public SwSizingMode SizingMode = SwSizingMode.FixedQuantity;
        public int FixedQuantity = 1;
        public double RiskMoneyPerTrade = 0;
        public double AccountEquityReference = 0;
        public double RiskPercentOfEquity = 0.5;
        public int MinQuantity = 1;
        public int MaxQuantity = 5;

        // --- издержки ---
        public double RoundTurnCostPerContract = 0;
        public int SlippageReserveTicks = 2;

        // --- стартовый стоп ---
        public SwStopMode StopMode = SwStopMode.FixedTicks;
        public int StopFixedTicks = 40;
        public double StopPriceDollars = 0;
        public double StopAtrMultiple = 2.0;

        // --- ступени ---
        public bool UseScaleOut = false;
        public int ScaleSteps = 2;
        public SwStepDistanceMode StepDistanceMode = SwStepDistanceMode.RMultiple;
        public int StepFixedTicks = 40;
        public double StepPriceDollars = 0;
        public double StepRMultiple = 1.0;
        public int ContractsOnStep1 = 1;
        public int ContractsPerStep = 0;     // 0 — делить автоматически
        public bool KeepRunner = true;

        // --- безубыток ---
        public SwBreakevenMode BreakevenMode = SwBreakevenMode.Off;
        public double BreakevenAtR = 1.0;
        public int BreakevenOffsetTicks = 2;

        // --- трейлинг ---
        public SwTrailMode TrailMode = SwTrailMode.Off;
        public double TrailActivateAtR = 1.0;
        public int TrailFixedTicks = 40;
        public double TrailAtrMultiple = 2.5;

        // --- защита ---
        public bool DisableStopMoveAfterStep1 = false;
        public int MinBarsBetweenStopMoves = 0;

        /// <summary>
        /// Сколько баров ждать подтверждения запрошенной ступени. По истечении
        /// запрос считается потерянным и очередь снимается с блокировки.
        /// </summary>
        public int StepConfirmTimeoutBars = 3;

        /// <summary>
        /// Порог безубытка и трейлинга — по лучшей цене позиции (MFE), как в
        /// исследовании и контрольном бэктесте. Иначе — по закрытию бара.
        /// </summary>
        public bool BreakevenOnBestPrice = true;
    }

    /// <summary>
    /// ФИНАНСОВЫЙ МОДУЛЬ. Считает объём, стартовый стоп, ступени, безубыток
    /// и трейлинг. Ордеров не создаёт.
    /// </summary>
    public class SwFinancialManager
    {
        private readonly DZ_SW_Hub_S021 hub;
        private readonly SwFinancialConfig cfg;

        // --- состояние сделки ---
        private int side;                     // +1 long, -1 short, 0 вне рынка
        private double entryPrice;
        private int entryBar;
        private int initialQty;
        private double initialStopPrice;
        private double riskTicks;             // R в тиках, база всех R-кратных величин

        private int stepsFilled;              // ПОДТВЕРЖДЁННЫХ ступеней
        private int stepsRequested;
        private int stepRequestBar = -1;      // бар запроса неподтверждённой ступени
        public int StepTimeouts;
        private readonly Dictionary<int, double> stepFillPrice = new Dictionary<int, double>();
        private readonly Dictionary<int, int> stepFillQty = new Dictionary<int, int>();

        private double currentStop = double.NaN;

        // Трейлинг этой сделки в тиках. Задаётся сигналом при входе; без
        // этого утренняя и вечерняя сделки шли бы с одним расстоянием, а
        // исследование требует 15 и 10 тиков соответственно.
        private double tradeTrailTicks = double.NaN;
        private int lastStopMoveBar = -1;
        private double bestPrice = double.NaN;
        private bool breakevenDone;

        // --- диагностика ---
        public int SizingBlocks, StepsRequestedTotal, StepsConfirmedTotal;
        public int StopMovesRequested, StopMovesSuppressed;
        public string LastNote = "—";

        public SwFinancialManager(DZ_SW_Hub_S021 h, SwFinancialConfig c)
        {
            hub = h; cfg = c;
        }

        #region Деньги и объём

        /// <summary>Стоимость одного тика одного контракта.</summary>
        private double TickValue
        {
            get { return hub.HubTickSize * hub.HubPointValue; }
        }

        /// <summary>
        /// Расстояние стопа в тиках по выбранному режиму.
        /// Режим PriceDollars означает доллары ДВИЖЕНИЯ ЦЕНЫ: для микрозолота
        /// с шагом 0.10 значение 25.0 даёт 250 тиков. Путаница этой величины
        /// с денежным результатом — источник ошибок на порядок.
        /// </summary>
        public double StopDistanceTicks()
        {
            switch (cfg.StopMode)
            {
                case SwStopMode.PriceDollars:
                    return hub.HubTickSize > 0 ? cfg.StopPriceDollars / hub.HubTickSize : 0;

                case SwStopMode.AtrMultiple:
                {
                    double atr = hub.HubAtrTicks;
                    return atr > 0 ? atr * cfg.StopAtrMultiple : cfg.StopFixedTicks;
                }

                default:
                    return cfg.StopFixedTicks;
            }
        }

        /// <summary>
        /// Полный риск одного контракта в деньгах: ход стопа плюс издержки
        /// круга плюс резерв на проскальзывание. Без последних двух слагаемых
        /// расчётный объём систематически завышается.
        /// </summary>
        public double TotalRiskPerContract()
        {
            double tv = TickValue;
            if (tv <= 0) return 0;

            double stopTicks = StopDistanceTicks();
            if (stopTicks <= 0) return 0;

            return stopTicks * tv
                 + cfg.RoundTurnCostPerContract
                 + cfg.SlippageReserveTicks * tv;
        }

        /// <summary>
        /// Объём позиции. Возвращает ноль, когда вход невозможен, и пишет
        /// причину в LastNote: молчаливый отказ недопустим.
        /// </summary>
        public int ResolveQuantity(out string note)
        {
            note = string.Empty;

            if (cfg.SizingMode == SwSizingMode.FixedQuantity)
                return Clamp(cfg.FixedQuantity);

            double risk = TotalRiskPerContract();
            if (risk <= 0)
            {
                note = "риск на контракт не определён: проверьте стоп и шаг цены";
                SizingBlocks++;
                return 0;
            }

            double budget;
            if (cfg.SizingMode == SwSizingMode.RiskMoneyPerTrade)
            {
                budget = cfg.RiskMoneyPerTrade;
                if (budget <= 0)
                {
                    note = "бюджет риска равен нулю";
                    SizingBlocks++;
                    return 0;
                }
            }
            else
            {
                double eq = cfg.AccountEquityReference;
                if (eq <= 0)
                {
                    note = "расчётный капитал равен нулю";
                    SizingBlocks++;
                    return 0;
                }
                budget = eq * cfg.RiskPercentOfEquity / 100.0;
            }

            int q = (int)Math.Floor(budget / risk);
            if (q < cfg.MinQuantity)
            {
                note = "расчётный объём " + q + " меньше минимума " + cfg.MinQuantity
                     + " (риск на контракт " + risk.ToString("F2") + ")";
                SizingBlocks++;
                return 0;
            }

            note = "бюджет " + budget.ToString("F2") + " / риск " + risk.ToString("F2")
                 + " = " + q + " конт.";
            return Clamp(q);
        }

        private int Clamp(int q)
        {
            if (q < cfg.MinQuantity) q = cfg.MinQuantity;
            if (q > cfg.MaxQuantity) q = cfg.MaxQuantity;
            return Math.Max(1, q);
        }

        /// <summary>
        /// Минимальный отступ безубытка, покрывающий издержки круга.
        /// При меньшем значении срабатывание безубыточного стопа даёт убыток.
        /// </summary>
        public int MinimumBreakevenOffsetTicks()
        {
            double tv = TickValue;
            if (tv <= 0 || cfg.RoundTurnCostPerContract <= 0) return 0;
            return (int)Math.Ceiling(cfg.RoundTurnCostPerContract / tv);
        }

        #endregion

        #region Жизненный цикл сделки

        /// <summary>Вызывается коммутатором при подтверждённом входе.</summary>
        public void OnTradeOpened(int dir, double avgPrice, int qty, int bar)
        {
            side = dir;
            entryPrice = avgPrice;
            entryBar = bar;
            initialQty = qty;

            riskTicks = StopDistanceTicks();

            double ov = hub.HubPendingTrailOverride;
            tradeTrailTicks = ov > 0 ? ov : hub.HubTrailDistance;
            hub.HubPendingTrailOverride = double.NaN;
            initialStopPrice = dir > 0
                ? entryPrice - riskTicks * hub.HubTickSize
                : entryPrice + riskTicks * hub.HubTickSize;

            currentStop = initialStopPrice;
            bestPrice = avgPrice;
            stepsFilled = 0; stepsRequested = 0; stepRequestBar = -1;
            breakevenDone = false;
            lastStopMoveBar = -1;
            stepFillPrice.Clear(); stepFillQty.Clear();

            LastNote = "вход " + (dir > 0 ? "LONG" : "SHORT") + " x" + qty
                     + ", R = " + riskTicks.ToString("F0") + " тиков";
            hub.HubTrace("FIN", "TRADE_OPENED", LastNote);
        }

        public void OnTradeClosed()
        {
            side = 0;
            stepsFilled = 0; stepsRequested = 0;
            currentStop = double.NaN;
            bestPrice = double.NaN;
            breakevenDone = false;
            stepFillPrice.Clear(); stepFillQty.Clear();
        }

        /// <summary>
        /// ПОДТВЕРЖДЁННОЕ ИСПОЛНЕНИЕ СТУПЕНИ. Вызывается коммутатором из
        /// OnExecutionUpdate. Это единственный путь, по которому ступень
        /// считается состоявшейся. Отправка заявки таковым не является.
        /// </summary>
        public void OnStepExecution(int stepNumber, double price, int qty)
        {
            if (stepNumber <= 0) return;

            int had; stepFillQty.TryGetValue(stepNumber, out had);
            double avg; stepFillPrice.TryGetValue(stepNumber, out avg);

            int now = had + qty;
            if (now > 0) avg = (avg * had + price * qty) / now;

            stepFillQty[stepNumber] = now;
            stepFillPrice[stepNumber] = avg;

            if (stepNumber > stepsFilled)
            {
                stepsFilled = stepNumber;
                stepRequestBar = -1;
                StepsConfirmedTotal++;
                hub.HubTrace("FIN", "STEP_CONFIRMED",
                    "ступень " + stepNumber + ": " + now + " конт. по " + avg.ToString("F2"));
            }
        }

        #endregion

        #region Оценка на баре

        /// <summary>
        /// Главный метод. Складывает требования в общий ящик коммутатора.
        /// Ордеров не создаёт.
        /// </summary>
        public void Evaluate(int bar, List<SwAction> outbox)
        {
            int pos = hub.HubPositionSide;

            if (pos == 0) { if (side != 0) OnTradeClosed(); return; }
            if (side == 0) return;                 // вход ещё не подтверждён
            if (riskTicks <= 0) return;

            // На баре входа безубыток и трейлинг не включаются, и лучшая цена не
            // обновляется: неизвестно, был ли максимум бара после входа. Так же
            // поступает контрольный бэктест.
            if (bar == entryBar) return;

            double px = hub.HubClose(0);

            bestPrice = side > 0
                ? Math.Max(double.IsNaN(bestPrice) ? px : bestPrice, hub.HubHigh(0))
                : Math.Min(double.IsNaN(bestPrice) ? px : bestPrice, hub.HubLow(0));

            double profitTicks = (side > 0 ? px - entryPrice : entryPrice - px) / hub.HubTickSize;
            double rNow = profitTicks / riskTicks;

            // ---------- 1. Ступени фиксации ----------
            if (cfg.UseScaleOut) EvaluateScaleOut(bar, profitTicks, outbox);

            // ---------- 2. Перенос стопа ----------
            // Два кандидата вычисляются независимо, затем берётся тот,
            // что СИЛЬНЕЕ сокращает риск. Спора между безубытком и
            // трейлингом не возникает по построению.
            // ЕДИНЫЙ ИСТОЧНИК ФАКТИЧЕСКОГО СТОПА — исполнитель. Прежде модуль
            // запоминал новый стоп до того, как исполнитель его принял, и не
            // знал о переносах, сделанных другими модулями сопровождения.
            // Две копии «текущего стопа» расходились.
            double actual = hub.HubCurrentStop;
            if (!double.IsNaN(actual)) currentStop = actual;

            double basisPx = cfg.BreakevenOnBestPrice ? bestPrice : px;
            double rBasis = ((side > 0 ? basisPx - entryPrice : entryPrice - basisPx) / hub.HubTickSize) / riskTicks;
            double candBe = ComputeBreakeven(rBasis);
            double candTr = ComputeTrail(rBasis);

            double target = BetterStop(candBe, candTr);
            if (double.IsNaN(target)) return;

            // ЗАПРЕТ ПОСЛЕ ПЕРВОЙ ФИКСАЦИИ — подавляет ОБЕ ветви сразу.
            if (cfg.DisableStopMoveAfterStep1 && stepsFilled >= 1)
            {
                StopMovesSuppressed++;
                LastNote = "перенос подавлен: после первой фиксации стоп не двигается";
                hub.HubTrace("FIN", "STOP_SUPPRESSED", LastNote);
                return;
            }

            if (cfg.MinBarsBetweenStopMoves > 0 && lastStopMoveBar >= 0
                && bar - lastStopMoveBar < cfg.MinBarsBetweenStopMoves)
                return;

            // Движение только в сторону сокращения риска.
            if (!double.IsNaN(currentStop))
            {
                bool better = side > 0 ? target > currentStop : target < currentStop;
                if (!better) return;
            }

            SwAction a = SwAction.None(bar);
            a.Kind = SwActionKind.MoveStop;
            a.Price = target;
            a.Reason = DescribeStopSource(candBe, candTr, target, rNow);
            outbox.Add(a);

            // currentStop здесь НЕ присваивается: принятие решает исполнитель,
            // и фактическое значение будет прочитано у него на следующем баре.
            lastStopMoveBar = bar;
            StopMovesRequested++;
            LastNote = a.Reason;
        }

        private void EvaluateScaleOut(int bar, double profitTicks, List<SwAction> outbox)
        {
            // ТАЙМАУТ ПОДТВЕРЖДЕНИЯ. Ожидание подтверждения верно, но без
            // предела оно превращается в тупик: если исполнитель отклонил
            // ступень арбитражем — например, выход по линии пришёлся на тот
            // же бар, — подтверждение не придёт никогда. Прежде это означало,
            // что до конца сделки не будет ни одной ступени и не наступит
            // безубыток AfterStep1.
            if (stepsRequested > stepsFilled && stepRequestBar >= 0
                && bar - stepRequestBar > Math.Max(1, cfg.StepConfirmTimeoutBars))
            {
                StepTimeouts++;
                hub.HubTrace("FIN", "STEP_TIMEOUT",
                    "ступень " + stepsRequested + " не подтверждена за "
                    + (bar - stepRequestBar) + " баров, запрос снят");
                stepsRequested = stepsFilled;
                stepRequestBar = -1;
            }

            if (stepsRequested >= cfg.ScaleSteps) return;

            // Следующая ступень считается от ПОДТВЕРЖДЁННЫХ, а не отправленных:
            // отклонённая заявка не должна сдвигать очередь.
            int next = stepsFilled + 1;
            if (next > cfg.ScaleSteps) return;
            if (stepsRequested >= next) return;     // эта уже отправлена, ждём подтверждения

            double needTicks = StepDistanceTicks(next);
            if (needTicks <= 0 || profitTicks < needTicks) return;

            int qty = StepQuantity(next);
            if (qty <= 0) return;

            SwAction a = SwAction.None(bar);
            a.Kind = SwActionKind.PartialExit;
            a.Quantity = qty;
            a.Tag = "STEP" + next;
            a.Reason = "ступень " + next + " при +" + profitTicks.ToString("F0")
                     + " тиков (нужно " + needTicks.ToString("F0") + ")";
            outbox.Add(a);

            stepsRequested = next;
            stepRequestBar = bar;
            StepsRequestedTotal++;
            hub.HubTrace("FIN", "STEP_REQUESTED", a.Reason + ", " + qty + " конт.");
        }

        private double StepDistanceTicks(int stepNumber)
        {
            switch (cfg.StepDistanceMode)
            {
                case SwStepDistanceMode.PriceDollars:
                    return hub.HubTickSize > 0
                        ? stepNumber * cfg.StepPriceDollars / hub.HubTickSize : 0;

                case SwStepDistanceMode.RMultiple:
                    return stepNumber * cfg.StepRMultiple * riskTicks;

                default:
                    return stepNumber * cfg.StepFixedTicks;
            }
        }

        private int StepQuantity(int stepNumber)
        {
            int open = hub.HubPositionQty;
            int reserve = cfg.KeepRunner ? 1 : 0;

            int want;
            if (stepNumber == 1 && cfg.ContractsOnStep1 > 0)
                want = cfg.ContractsOnStep1;
            else if (cfg.ContractsPerStep > 0)
                want = cfg.ContractsPerStep;
            else
            {
                int divisor = Math.Max(1, cfg.ScaleSteps + reserve);
                want = Math.Max(1, initialQty / divisor);
            }

            return Math.Max(0, Math.Min(want, open - reserve));
        }

        private double ComputeBreakeven(double rNow)
        {
            if (breakevenDone) return double.NaN;

            bool due;
            switch (cfg.BreakevenMode)
            {
                case SwBreakevenMode.AfterStep1: due = stepsFilled >= 1; break;
                case SwBreakevenMode.AfterStep2: due = stepsFilled >= 2; break;
                case SwBreakevenMode.AtRMultiple: due = rNow >= cfg.BreakevenAtR; break;
                default: return double.NaN;
            }
            if (!due) return double.NaN;

            // Отступ не меньше того, что покрывает издержки круга.
            int off = Math.Max(cfg.BreakevenOffsetTicks, MinimumBreakevenOffsetTicks());

            breakevenDone = true;
            return side > 0
                ? entryPrice + off * hub.HubTickSize
                : entryPrice - off * hub.HubTickSize;
        }

        private double ComputeTrail(double rNow)
        {
            if (cfg.TrailMode == SwTrailMode.Off) return double.NaN;
            if (rNow < cfg.TrailActivateAtR) return double.NaN;

            switch (cfg.TrailMode)
            {
                case SwTrailMode.FixedDistance:
                {
                    double tt = tradeTrailTicks > 0 ? tradeTrailTicks : cfg.TrailFixedTicks;
                    return side > 0
                        ? bestPrice - tt * hub.HubTickSize
                        : bestPrice + tt * hub.HubTickSize;
                }

                case SwTrailMode.AtrMultiple:
                {
                    double atr = hub.HubAtrTicks;
                    if (atr <= 0) return double.NaN;
                    double d = atr * cfg.TrailAtrMultiple * hub.HubTickSize;
                    return side > 0 ? bestPrice - d : bestPrice + d;
                }

                case SwTrailMode.StepLock:
                {
                    // После ступени k стоп встаёт на уровень ступени k-1.
                    // При k = 1 это цена входа: прибыль первой ступени
                    // фиксируется, а остаток ведётся без риска.
                    if (stepsFilled < 1) return double.NaN;
                    int prev = stepsFilled - 1;
                    double lockTicks = prev == 0 ? 0 : StepDistanceTicks(prev);
                    return side > 0
                        ? entryPrice + lockTicks * hub.HubTickSize
                        : entryPrice - lockTicks * hub.HubTickSize;
                }

                default: return double.NaN;
            }
        }

        /// <summary>Из двух кандидатов берётся сильнее сокращающий риск.</summary>
        private double BetterStop(double a, double b)
        {
            if (double.IsNaN(a)) return b;
            if (double.IsNaN(b)) return a;
            return side > 0 ? Math.Max(a, b) : Math.Min(a, b);
        }

        private string DescribeStopSource(double be, double tr, double chosen, double rNow)
        {
            string who;
            if (!double.IsNaN(be) && Math.Abs(chosen - be) < 1e-9) who = "безубыток";
            else if (!double.IsNaN(tr) && Math.Abs(chosen - tr) < 1e-9) who = "трейлинг " + cfg.TrailMode;
            else who = "перенос";

            return who + " → " + chosen.ToString("F2")
                 + " (R = " + rNow.ToString("F2") + ", ступеней " + stepsFilled + ")";
        }

        #endregion

        #region Диагностика

        public double CurrentR
        {
            get
            {
                if (side == 0 || riskTicks <= 0) return 0;
                double px = hub.HubClose(0);
                double p = (side > 0 ? px - entryPrice : entryPrice - px) / hub.HubTickSize;
                return p / riskTicks;
            }
        }

        /// <summary>Открытый риск в деньгах: расстояние до текущего стопа.</summary>
        public double OpenRiskMoney
        {
            get
            {
                if (side == 0 || double.IsNaN(currentStop)) return 0;
                double px = hub.HubClose(0);
                double ticks = (side > 0 ? px - currentStop : currentStop - px) / hub.HubTickSize;
                return -ticks * TickValue * hub.HubPositionQty;   // отрицательно = риск
            }
        }

        public string StatusLine
        {
            get
            {
                if (side == 0)
                    return "вне рынка | R-база " + StopDistanceTicks().ToString("F0")
                         + " тиков, риск/контракт " + TotalRiskPerContract().ToString("F2");

                return string.Format("{0} x{1} @ {2:F2} | R {3:F2} | стоп {4} | ступеней {5}/{6} | открытый риск {7:F2}",
                    side > 0 ? "LONG" : "SHORT", hub.HubPositionQty, entryPrice,
                    CurrentR,
                    double.IsNaN(currentStop) ? "—" : currentStop.ToString("F2"),
                    stepsFilled, cfg.ScaleSteps, OpenRiskMoney);
            }
        }

        public string SummaryLine
        {
            get
            {
                return "ступеней запрошено " + StepsRequestedTotal
                     + ", подтверждено " + StepsConfirmedTotal
                     + ", переносов стопа " + StopMovesRequested
                     + ", подавлено " + StopMovesSuppressed
                     + ", таймаутов ступеней " + StepTimeouts
                     + ", отказов расчёта объёма " + SizingBlocks;
            }
        }

        #endregion
    }
}
