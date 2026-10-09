#region Using declarations
using System;
using NinjaTrader.NinjaScript;
#endregion

// ============================================================================
//  DZ_SW_Mod_DualBreakout_S021 — ПРОБОЙ ДИАПАЗОНА ДВУХ СЕССИЙ
//  Роль Signal, v2.0 (2026-09-22)
//
//  ОДИН ЭКЗЕМПЛЯР — ОДИН ПРОФИЛЬ — ОДИН СЧЁТ. Профили Чикаго и Берлин не
//  смешиваются: каждый работает отдельной стратегией на своём счёте со своим
//  поясом окон [M81]. Общего состояния между экземплярами нет.
//
//  ЭТАЛОН — контрольный бэктест DZ_BT_DualBreakout_S021.py. Каждое решение
//  модуля сверено с ним; расхождение означало бы, что живая торговля ведёт
//  себя не так, как проверено.
//
//  ПРАВИЛА
//    направление утра   знак среднего/СКО 10 доходностей закрытых баров 4H
//    направление вечера тренд дня: закрытие до 14:30 против открытия от 07:00
//    боковик            ATR(20)/ATR(40) на 15M ниже 0.85 — простая средняя
//    снимки 15M и 4H    бары, закрытые СТРОГО ДО начала окна: не позже минус 1 мин
//    база               бары с открытием в окне базы; не меньше MinBaseBars
//    ширина базы        от 15 до 45 тиков включительно
//    вход               стоп-ордер на экстремум базы ± 1 тик, работает с ПЕРВОЙ
//                       минуты окна: решение принимается на последнем баре базы
//    повторный вход     после выхода, пока окно открыто; ордер ставится только
//                       когда закрытие бара по входную сторону уровня
//    трейлинг           задаётся сессией и передаётся финансовому модулю
//
//  ИСПРАВЛЕНО В v2.0 ПО СВЕРКЕ С ЭТАЛОНОМ
//    1. Решение на последнем баре базы, а не на первом баре окна: прежде ордер
//       работал с 07:01 и пропускал вход на первой минуте. В исследовании на
//       07:00 приходилось 3 856 входов из 63 660.
//    2. Снимки 15M и 4H — строго до окна. Прежде брался бар, закрывшийся ровно в
//       момент начала окна.
//    3. ATR — простая средняя, как в регламенте, а не по Уайлдеру.
//    4. Вечер — по тренду дня. Прежде дополнительно требовалось совпадение с 4H.
//    5. Закрытие тренда дня — последний бар ДО 14:30, а не бар 14:30.
//    6. Минимум баров базы: при неполных данных сессия блокируется.
//
//  ПОЯС ОКОН — America/Chicago для данных исследования, подтверждено. Для
//  второго счёта — Europe/Berlin: те же часы означают другую фазу рынка.
//
//  МЕТКА БАРА. NinjaTrader помечает бар временем закрытия. Время открытия
//  получается вычитанием длительности бара.
// ============================================================================

namespace NinjaTrader.NinjaScript
{
    /// <summary>Часовой пояс, в котором заданы окна.</summary>
    public enum SwWindowZone { Berlin, Chicago, NewYork, London, Utc }

    /// <summary>Фаза сессии.</summary>
    public enum SwBreakoutPhase { Idle, Building, Armed, Blocked, Traded, Expired }

    /// <summary>Чем задаётся направление вечерней сессии.</summary>
    public enum SwEveningDir
    {
        DayTrend,   // закрытие до 14:30 против открытия от 07:00 — как в исследовании
        H4,         // знак наклона 4H, как утром
        Both        // оба обязаны совпасть
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    /// <summary>Границы одной сессии, ЧЧММСС в поясе окон, по времени ОТКРЫТИЯ бара.</summary>
    public class SwSessionSpec
    {
        public bool Enabled = true;
        public string Name = "";
        public int BaseStart, BaseEnd;
        public int SignalStart, SignalEnd;
        public int SessionEnd;
        public double TrailTicks;
    }

    public class SwDualBreakoutConfig
    {
        public int M1Slot = 1;
        public int M15Slot = 3;
        public int H4Slot = 4;
        public int M1BarMinutes = 1;

        public SwWindowZone Zone = SwWindowZone.Chicago;

        public SwSessionSpec Morning = new SwSessionSpec
        {
            Name = "УТРО", BaseStart = 60000, BaseEnd = 65959,
            SignalStart = 70000, SignalEnd = 95959, SessionEnd = 143000, TrailTicks = 15
        };
        public SwSessionSpec Evening = new SwSessionSpec
        {
            Name = "ВЕЧЕР", BaseStart = 170000, BaseEnd = 175959,
            SignalStart = 180000, SignalEnd = 195959, SessionEnd = 213000, TrailTicks = 10
        };

        public double MinRangeTicks = 15;
        public double MaxRangeTicks = 45;
        public int MinBaseBars = 50;
        public int TrendBars = 10;
        public int AtrFast = 20;
        public int AtrSlow = 40;
        public double FlatThreshold = 0.85;
        public int EntryOffsetTicks = 1;
        public SwEveningDir EveningDir = SwEveningDir.DayTrend;
        public int MaxEntriesPerSession = 0;     // 0 — без ограничения
        public bool CloseAtSessionEnd = true;
    }

    /// <summary>Состояние одной сессии на текущий день.</summary>
    public class SwSessionState
    {
        public SwBreakoutPhase Phase = SwBreakoutPhase.Idle;
        public DateTime Day = DateTime.MinValue;
        public double High = double.NaN, Low = double.NaN;
        public int BaseBars;
        public double RangeTicks = double.NaN;
        public int Direction;
        public double EntryStop = double.NaN;
        public double NormVolSnap = double.NaN;
        public int TrendSnap;
        public int Entries;
        public string BlockReason = string.Empty;

        public void ResetFor(DateTime day)
        {
            Phase = SwBreakoutPhase.Idle; Day = day;
            High = Low = RangeTicks = EntryStop = NormVolSnap = double.NaN;
            BaseBars = 0; Direction = 0; TrendSnap = 0; Entries = 0;
            BlockReason = string.Empty;
        }
    }

    /// <summary>
    /// Снимок старшей серии: два последних значения с временем закрытия их баров.
    /// Решение принимается в момент, когда бар, закрывающийся ровно в начале
    /// окна, мог быть уже обработан платформой, а мог и нет — порядок серий с
    /// одинаковой меткой не гарантирован. Хранение двух значений позволяет всегда
    /// взять бар, закрытый строго до окна, независимо от этого порядка.
    /// </summary>
    public class SwHtfSnap
    {
        public double LastVal = double.NaN, PrevVal = double.NaN;
        public DateTime LastClose = DateTime.MinValue, PrevClose = DateTime.MinValue;

        public void Push(double v, DateTime closeZ)
        {
            PrevVal = LastVal; PrevClose = LastClose;
            LastVal = v; LastClose = closeZ;
        }

        public double Get(DateTime limit)
        {
            if (LastClose != DateTime.MinValue && LastClose <= limit) return LastVal;
            if (PrevClose != DateTime.MinValue && PrevClose <= limit) return PrevVal;
            return double.NaN;
        }
    }

    public class SwDualBreakoutModule : SwModule
    {
        private readonly SwDualBreakoutConfig cfg;

        private TimeZoneInfo zoneInfo, sourceZone;
        private bool zonesOk;

        // --- 4H ---
        private double[] ret;
        private int retCount, retIdx;
        private double prevH4Close = double.NaN;
        private readonly SwHtfSnap snapH4 = new SwHtfSnap();

        // --- 15M: кольцо истинных диапазонов для простой средней ---
        private double[] trRing;
        private int trCount, trIdx;
        private double prevM15Close = double.NaN;
        private readonly SwHtfSnap snapNv = new SwHtfSnap();

        // --- тренд дня ---
        private double dayOpen = double.NaN, dayClose = double.NaN;
        private DateTime dayOfTrend = DateTime.MinValue;

        private readonly SwSessionState morning = new SwSessionState();
        private readonly SwSessionState evening = new SwSessionState();

        private int lastPosSide;
        private int armedCount, trades, blkRange, blkFlat, blkTrend, blkDay, blkBase;

        public SwDualBreakoutModule(string id, SwDualBreakoutConfig config)
        {
            Id = id;
            Role = SwRole.Signal;
            cfg = config ?? new SwDualBreakoutConfig();
        }

        public override void Attach(SwHostView host)
        {
            base.Attach(host);
            ret = new double[Math.Max(2, cfg.TrendBars)];
            trRing = new double[Math.Max(2, Math.Max(cfg.AtrFast, cfg.AtrSlow))];
            ResolveZones();

            Host.Trace(Id, "DBO_ATTACHED", "пояс окон " + cfg.Zone
                + ", утро " + Span(cfg.Morning) + ", вечер " + Span(cfg.Evening)
                + ", база " + cfg.MinRangeTicks + "–" + cfg.MaxRangeTicks + " т, вечер по " + cfg.EveningDir);
            if (!zonesOk)
                Host.Trace(Id, "DBO_ZONE_FAULT", "пояс не разрешён: окна не применяются, вход закрыт");
        }

        private static string Span(SwSessionSpec s)
        {
            if (!s.Enabled) return "выкл";
            return Hm(s.BaseStart) + "–" + Hm(s.BaseEnd) + " / " + Hm(s.SignalStart) + "–" + Hm(s.SignalEnd)
                 + " / выход " + Hm(s.SessionEnd);
        }

        private static string Hm(int v) { return (v / 10000).ToString("00") + ":" + ((v / 100) % 100).ToString("00"); }

        #region Время

        private void ResolveZones()
        {
            zonesOk = false;
            string[] ids;
            switch (cfg.Zone)
            {
                case SwWindowZone.Chicago: ids = new[] { "Central Standard Time", "America/Chicago" }; break;
                case SwWindowZone.NewYork: ids = new[] { "Eastern Standard Time", "America/New_York" }; break;
                case SwWindowZone.London:  ids = new[] { "GMT Standard Time", "Europe/London" }; break;
                case SwWindowZone.Utc:     zoneInfo = TimeZoneInfo.Utc; ids = null; break;
                default:                   ids = new[] { "W. Europe Standard Time", "Europe/Berlin" }; break;
            }
            if (ids != null)
                foreach (string zid in ids)
                {
                    try { zoneInfo = TimeZoneInfo.FindSystemTimeZoneById(zid); break; }
                    catch { zoneInfo = null; }
                }
            if (zoneInfo == null) return;

            try { sourceZone = NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo; }
            catch { sourceZone = null; }
            if (sourceZone == null) sourceZone = TimeZoneInfo.Local;
            zonesOk = true;
        }

        /// <summary>Метка платформы — в пояс окон, без сдвига.</summary>
        private DateTime ToZone(DateTime stamp)
        {
            DateTime u = DateTime.SpecifyKind(stamp, DateTimeKind.Unspecified);
            try
            {
                if (sourceZone.IsInvalidTime(u)) u = u.AddHours(1);
                DateTime utc = TimeZoneInfo.ConvertTimeToUtc(u, sourceZone);
                return TimeZoneInfo.ConvertTimeFromUtc(DateTime.SpecifyKind(utc, DateTimeKind.Utc), zoneInfo);
            }
            catch { return u; }
        }

        /// <summary>Время ОТКРЫТИЯ минутного бара в поясе окон.</summary>
        private DateTime BarOpenZ(DateTime closeStamp)
        {
            return ToZone(closeStamp.AddMinutes(-Math.Max(1, cfg.M1BarMinutes)));
        }

        private static int Hms(DateTime t) { return t.Hour * 10000 + t.Minute * 100 + t.Second; }
        private static bool In(int now, int a, int b) { return now >= a && now <= b; }
        private static TimeSpan ToSpan(int v) { return new TimeSpan(v / 10000, (v / 100) % 100, v % 100); }

        #endregion

        public override void Compute(int bip)
        {
            if (Host.IsBarCloseOf(cfg.H4Slot, bip)) UpdateH4();
            if (Host.IsBarCloseOf(cfg.M15Slot, bip)) UpdateM15();
            if (Host.IsBarCloseOf(cfg.M1Slot, bip) && zonesOk) UpdateSessions();

            if (bip != Host.ExecBip) return;
            int bar = Host.CurrentBar;

            if (!zonesOk)
            {
                Health = SwHealth.Faulted;
                Emit(SwSignal.Empty(bar));
                return;
            }

            DateTime nowZ = BarOpenZ(Host.TimeOf(cfg.M1Slot, 0));
            int hms = Hms(nowZ);
            int pos = Host.PositionSide;

            if (pos != 0 && lastPosSide == 0)
            {
                trades++;
                if (morning.Phase == SwBreakoutPhase.Armed) { morning.Phase = SwBreakoutPhase.Traded; morning.Entries++; }
                if (evening.Phase == SwBreakoutPhase.Armed) { evening.Phase = SwBreakoutPhase.Traded; evening.Entries++; }
            }
            if (pos == 0 && lastPosSide != 0)
            {
                Rearm(morning, cfg.Morning, hms);
                Rearm(evening, cfg.Evening, hms);
            }
            lastPosSide = pos;

            // Закрытие по окончании сессии. Требование повторяется каждый бар до
            // исполнения; исполнитель пропускает не больше одного выхода на бар.
            if (cfg.CloseAtSessionEnd && pos != 0 && SessionEndReached(hms))
            {
                SwAction a = SwAction.None(bar);
                a.Kind = SwActionKind.FullExit;
                a.Reason = "окончание сессии " + nowZ.ToString("HH:mm") + " (" + cfg.Zone + ")";
                Emit(a);
            }

            SwSessionState armed = null; SwSessionSpec spec = null;
            if (morning.Phase == SwBreakoutPhase.Armed) { armed = morning; spec = cfg.Morning; }
            else if (evening.Phase == SwBreakoutPhase.Armed) { armed = evening; spec = cfg.Evening; }

            SwSignal s = new SwSignal();
            s.IsReady = true;
            s.ProducedAtBar = bar;
            s.EntryStopPrice = double.NaN;
            s.TrailTicksOverride = double.NaN;

            if (armed == null || pos != 0)
            {
                s.Direction = 0;
                s.Text = "утро " + morning.Phase + ", вечер " + evening.Phase;
            }
            else
            {
                // Сигнал подтверждается каждый бар, пока окно открыто: прекращение
                // сигнала снимает стоп-ордер. Ордер ставится исполнителем, только
                // когда закрытие бара по входную сторону уровня.
                s.Direction = armed.Direction;
                s.Confidence = 1.0;
                s.EntryStopPrice = armed.EntryStop;
                s.TrailTicksOverride = spec.TrailTicks;
                s.Text = spec.Name + " " + (armed.Direction > 0 ? "LONG" : "SHORT") + " стоп @ "
                       + armed.EntryStop.ToString("F2") + ", вход №" + (armed.Entries + 1);
            }

            Health = SwHealth.Ok;
            Emit(s);
        }

        #region 4H и 15M

        private void UpdateH4()
        {
            if (!Host.SlotReady(cfg.H4Slot, 1)) return;
            double c = Host.CloseOf(cfg.H4Slot, 0);
            if (double.IsNaN(c) || c <= 0) return;

            if (!double.IsNaN(prevH4Close) && prevH4Close > 0)
            {
                ret[retIdx] = (c - prevH4Close) / prevH4Close;
                retIdx = (retIdx + 1) % ret.Length;
                if (retCount < ret.Length) retCount++;

                if (retCount >= ret.Length)
                {
                    double m = 0; for (int i = 0; i < ret.Length; i++) m += ret[i];
                    m /= ret.Length;
                    double v = 0; for (int i = 0; i < ret.Length; i++) v += (ret[i] - m) * (ret[i] - m);
                    double sd = Math.Sqrt(v / ret.Length);
                    double slope = m / (sd + 1e-8);
                    snapH4.Push(slope > 0 ? 1 : slope < 0 ? -1 : 0, ToZone(Host.TimeOf(cfg.H4Slot, 0)));
                }
            }
            prevH4Close = c;
        }

        /// <summary>
        /// NormVol = SMA(TR, быстр) / SMA(TR, медл) на закрытых барах 15M.
        /// Простая средняя, как в регламенте и контрольном бэктесте.
        /// </summary>
        private void UpdateM15()
        {
            if (!Host.SlotReady(cfg.M15Slot, 1)) return;
            double h = Host.HighOf(cfg.M15Slot, 0), l = Host.LowOf(cfg.M15Slot, 0), c = Host.CloseOf(cfg.M15Slot, 0);
            if (double.IsNaN(h) || double.IsNaN(l) || double.IsNaN(c)) return;

            double tr = double.IsNaN(prevM15Close) ? h - l
                      : Math.Max(h - l, Math.Max(Math.Abs(h - prevM15Close), Math.Abs(l - prevM15Close)));
            prevM15Close = c;

            trRing[trIdx] = tr;
            trIdx = (trIdx + 1) % trRing.Length;
            if (trCount < trRing.Length) trCount++;

            int slow = Math.Max(1, cfg.AtrSlow), fast = Math.Max(1, cfg.AtrFast);
            if (trCount < Math.Max(slow, fast)) return;

            double sf = 0, ss = 0;
            for (int k = 1; k <= Math.Max(slow, fast); k++)
            {
                double x = trRing[(trIdx - k + trRing.Length) % trRing.Length];
                if (k <= fast) sf += x;
                if (k <= slow) ss += x;
            }
            double nv = (sf / fast) / (ss / slow + 1e-8);
            snapNv.Push(nv, ToZone(Host.TimeOf(cfg.M15Slot, 0)));
        }

        #endregion

        #region Сессии

        private void UpdateSessions()
        {
            DateTime t = BarOpenZ(Host.TimeOf(cfg.M1Slot, 0));
            int hms = Hms(t);

            // Тренд дня: открытие первого бара от начала утреннего окна, закрытие
            // последнего бара ДО утреннего выхода. Так же в контрольном бэктесте.
            if (t.Date != dayOfTrend) { dayOfTrend = t.Date; dayOpen = dayClose = double.NaN; }
            if (hms >= cfg.Morning.SignalStart && hms < cfg.Morning.SessionEnd)
            {
                if (double.IsNaN(dayOpen)) dayOpen = Host.OpenOf(cfg.M1Slot, 0);
                dayClose = Host.CloseOf(cfg.M1Slot, 0);
            }

            if (cfg.Morning.Enabled) Step(morning, cfg.Morning, t, hms, false);
            if (cfg.Evening.Enabled) Step(evening, cfg.Evening, t, hms, true);
        }

        private void Step(SwSessionState st, SwSessionSpec sp, DateTime t, int hms, bool isEvening)
        {
            if (st.Day != t.Date && hms >= sp.BaseStart) st.ResetFor(t.Date);

            if (In(hms, sp.BaseStart, sp.BaseEnd))
            {
                if (st.Phase == SwBreakoutPhase.Idle) st.Phase = SwBreakoutPhase.Building;
                if (st.Phase != SwBreakoutPhase.Building) return;

                double h = Host.HighOf(cfg.M1Slot, 0), l = Host.LowOf(cfg.M1Slot, 0);
                if (!double.IsNaN(h) && !double.IsNaN(l))
                {
                    st.High = double.IsNaN(st.High) ? h : Math.Max(st.High, h);
                    st.Low = double.IsNaN(st.Low) ? l : Math.Min(st.Low, l);
                    st.BaseBars++;
                }

                // РЕШЕНИЕ НА ПОСЛЕДНЕМ БАРЕ БАЗЫ. Ордер, выставленный по его закрытию,
                // работает уже на первой минуте окна. Решение на первом баре окна
                // пропускало бы вход на этой минуте.
                int next = Hms(t.AddMinutes(Math.Max(1, cfg.M1BarMinutes)));
                if (In(next, sp.SignalStart, sp.SignalEnd)) Decide(st, sp, isEvening, t.Date);
                return;
            }

            // Запасной путь: последний бар базы отсутствовал в данных.
            if (st.Phase == SwBreakoutPhase.Building && In(hms, sp.SignalStart, sp.SignalEnd))
            {
                Decide(st, sp, isEvening, t.Date);
                return;
            }

            if ((st.Phase == SwBreakoutPhase.Armed || st.Phase == SwBreakoutPhase.Building) && hms > sp.SignalEnd)
            {
                st.Phase = SwBreakoutPhase.Expired;
                Host.Trace(Id, "DBO_EXPIRED", sp.Name + ": окно сигналов закрыто без входа");
            }
        }

        /// <summary>Порядок проверок — как в контрольном бэктесте.</summary>
        private void Decide(SwSessionState st, SwSessionSpec sp, bool isEvening, DateTime date)
        {
            double tick = Host.TickSize;
            DateTime limit = date + ToSpan(sp.SignalStart) - TimeSpan.FromMinutes(1);
            double nv = snapNv.Get(limit);
            double tr4 = snapH4.Get(limit);
            st.NormVolSnap = nv;
            st.TrendSnap = double.IsNaN(tr4) ? 0 : (int)tr4;

            if (st.BaseBars < cfg.MinBaseBars || tick <= 0)
            { blkBase++; Block(st, sp, "NO_BASE_DATA: баров базы " + st.BaseBars + " < " + cfg.MinBaseBars); return; }

            st.RangeTicks = Math.Round((st.High - st.Low) / tick, 6);
            if (st.RangeTicks < cfg.MinRangeTicks)
            { blkRange++; Block(st, sp, "RANGE_LOW: " + st.RangeTicks.ToString("F0") + " т"); return; }
            if (st.RangeTicks > cfg.MaxRangeTicks)
            { blkRange++; Block(st, sp, "RANGE_HIGH: " + st.RangeTicks.ToString("F0") + " т"); return; }
            if (double.IsNaN(nv))
            { blkFlat++; Block(st, sp, "NORMVOL_NOT_READY"); return; }
            if (nv < cfg.FlatThreshold)
            { blkFlat++; Block(st, sp, "FLAT: NormVol " + nv.ToString("F2")); return; }

            int dir;
            if (isEvening && cfg.EveningDir != SwEveningDir.H4)
            {
                if (double.IsNaN(dayOpen) || double.IsNaN(dayClose))
                { blkDay++; Block(st, sp, "DAYTREND_MISSING"); return; }
                int dayDir = dayClose >= dayOpen ? 1 : -1;
                if (cfg.EveningDir == SwEveningDir.Both)
                {
                    if (double.IsNaN(tr4) || tr4 == 0) { blkTrend++; Block(st, sp, "NO_TREND"); return; }
                    if ((int)tr4 != dayDir) { blkTrend++; Block(st, sp, "DIR_CONFLICT"); return; }
                }
                dir = dayDir;
            }
            else
            {
                if (double.IsNaN(tr4) || tr4 == 0) { blkTrend++; Block(st, sp, "NO_TREND"); return; }
                dir = (int)tr4;
            }

            st.Direction = dir;
            st.EntryStop = dir > 0 ? st.High + cfg.EntryOffsetTicks * tick : st.Low - cfg.EntryOffsetTicks * tick;
            st.Phase = SwBreakoutPhase.Armed;
            armedCount++;
            Host.Trace(Id, "DBO_ARMED", sp.Name + " " + (dir > 0 ? "LONG" : "SHORT")
                + " стоп-вход @ " + st.EntryStop.ToString("F2") + ", база " + st.RangeTicks.ToString("F0")
                + " т, NormVol " + nv.ToString("F2") + ", 4H " + st.TrendSnap);
        }

        private void Rearm(SwSessionState st, SwSessionSpec sp, int hms)
        {
            if (st.Phase != SwBreakoutPhase.Traded) return;
            if (!In(hms, sp.SignalStart, sp.SignalEnd)) return;
            if (cfg.MaxEntriesPerSession > 0 && st.Entries >= cfg.MaxEntriesPerSession) return;
            st.Phase = SwBreakoutPhase.Armed;
            Host.Trace(Id, "DBO_REARMED", sp.Name + ": стоп-вход взведён снова, вход №" + (st.Entries + 1)
                + " — исполнится после возврата цены за уровень " + st.EntryStop.ToString("F2"));
        }

        private void Block(SwSessionState st, SwSessionSpec sp, string why)
        {
            st.Phase = SwBreakoutPhase.Blocked;
            st.BlockReason = why;
            Host.Trace(Id, "DBO_BLOCKED", sp.Name + ": " + why);
        }

        private bool SessionEndReached(int hms)
        {
            bool m = cfg.Morning.Enabled && morning.Phase == SwBreakoutPhase.Traded
                     && hms >= cfg.Morning.SessionEnd && hms < cfg.Evening.BaseStart;
            bool e = cfg.Evening.Enabled && evening.Phase == SwBreakoutPhase.Traded
                     && hms >= cfg.Evening.SessionEnd;
            return m || e;
        }

        #endregion

        #region Диагностика

        public string StateLine
        {
            get
            {
                return string.Format("{0} | утро {1} {2} | вечер {3} {4} | взведено {5}, сделок {6} | блок: база {7} ширина {8} боковик {9} тренд {10} день {11}",
                    cfg.Zone, morning.Phase, double.IsNaN(morning.RangeTicks) ? "" : morning.RangeTicks.ToString("F0") + "т",
                    evening.Phase, double.IsNaN(evening.RangeTicks) ? "" : evening.RangeTicks.ToString("F0") + "т",
                    armedCount, trades, blkBase, blkRange, blkFlat, blkTrend, blkDay);
            }
        }

        #endregion
    }
}
