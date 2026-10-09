#region Using declarations
using System;
using NinjaTrader.NinjaScript;
#endregion

// ============================================================================
//  DZ_SW_Mod_HurstKernel_S021 — ЯДРО С ШИРИНОЙ ОКНА ПО ХЁРСТУ, [MOD10], v1.0 (2026-09-27)
//  Роль Filter по умолчанию, Signal при [H10].
//
//  СОСТАВ
//    регрессия  НЕ переписана: вычислитель SwAdaptiveKernelEngine из MOD9, уже
//               сверенный с numpy до десятого знака (постулат «одна величина — один
//               источник»). Епанечников, локальная прямая либо Надарая–Ватсон,
//               ранний выход по компактному носителю — в нём.
//    ширина     по показателю Хёрста: персистентный рынок — окно шире, антиперсистентный —
//               уже; отображение [H07]–[H08] → [H05]–[H06].
//
//  ПОКАЗАТЕЛЬ ХЁРСТА ИСПРАВЛЕН. Формула ТЗ H = ln(R/S)/ln(N) на одном окне смещена: для
//  случайного блуждания даёт не 0.5, а около 0.55, и имеет большой разброс. Здесь R/S
//  считается на нескольких масштабах n = N, N/2, N/4 … ≥ 8, из каждого вычитается
//  ожидаемое для независимых приращений E[R/S]ₙ (Anis–Lloyd с поправкой Peters), и
//  H = 0.5 + наклон регрессии (ln R/S − ln E[R/S]) по ln n. Для блуждания — 0.5.
//
//  ZERO-GC. Все буферы — в Attach; ожидаемые E[R/S] по масштабам — тоже, один раз.
//
//  ЭКСПЕРИМЕНТЫ — выключены по умолчанию:
//    [H11]/[H12] шлюз блуждания: |H − 0.5| меньше полосы — нейтраль, трендовой информации нет;
//    [H13] обратное отображение: антиперсистентный рынок — окно шире (подавить шум);
//    [H14] уверенность по Хёрсту: уверенность наклона умножается на силу персистентности.
// ============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
    public class SwHurstKernelConfig
    {
        public int Slot = 1;
        public SwRegressionType Regression = SwRegressionType.LocalLinear;
        public SwKernelType Kernel = SwKernelType.Epanechnikov;
        public int HurstPeriod = 128;
        public int MinBandwidth = 8, MaxBandwidth = 40;
        // Уровень случайного блуждания ЭТОГО оценщика при окне 128 — 0.47 по моделированию
        // (400 рядов), а не 0.5: поправка Аниса–Ллойда на малых масштабах перекомпенсирует.
        // Разброс оценки на 128 доходностях — 0.08, столько же, сколько эффект режима (±0.06):
        // на коротком окне ширина следует шуму. Для устойчивости — окно 256 и больше.
        public double RwLevel = 0.47;
        public double HLow = 0.37, HHigh = 0.57;
        public double SlopeThresholdTicks = 0.5;
        public bool SignalMode = false;
        public bool ExpRandomWalkGate = false;
        public double ExpGateBand = 0.03;
        public bool ExpInverseMap = false;
        public bool ExpHurstConfidence = false;
    }

    public class SwHurstKernelModule : SwModule
    {
        private readonly SwHurstKernelConfig cfg;
        private readonly SwAdaptiveKernelEngine eng = new SwAdaptiveKernelEngine();

        private double[] closeRing, retRing, yBuf, mult;
        private int cap, cCount, cHead, rCount, rHead;

        private int[] scaleN; private double[] logN, logE; private int nScales;

        private double hurst = 0.5, alpha = double.NaN, beta = double.NaN, prevAlpha = double.NaN;
        private int hUsed, fits;
        private string textCache = ""; private int lastDir = int.MinValue, lastCode = -1;

        public SwHurstKernelModule(string id, SwHurstKernelConfig config)
        {
            Id = id;
            cfg = config ?? new SwHurstKernelConfig();
            Role = cfg.SignalMode ? SwRole.Signal : SwRole.Filter;
        }

        public override void Attach(SwHostView host)
        {
            base.Attach(host);
            int N = Math.Max(16, cfg.HurstPeriod);
            cap = Math.Max(cfg.MaxBandwidth, N) + 2;
            closeRing = new double[cap];
            retRing = new double[N];
            yBuf = new double[cfg.MaxBandwidth + 2];
            mult = new double[cfg.MaxBandwidth + 2];
            for (int i = 0; i < mult.Length; i++) mult[i] = 1.0;

            // Масштабы n = N, N/2, … ≥ 8 и ожидаемое E[R/S]ₙ для независимых приращений.
            int cnt = 0; for (int n = N; n >= 8; n /= 2) cnt++;
            scaleN = new int[cnt]; logN = new double[cnt]; logE = new double[cnt];
            nScales = 0;
            for (int n = N; n >= 8; n /= 2)
            {
                scaleN[nScales] = n; logN[nScales] = Math.Log(n); logE[nScales] = Math.Log(ExpectedRS(n)); nScales++;
            }
            Host.Trace(Id, "HK_ATTACHED", "окно Хёрста " + N + ", масштабов " + nScales + ", ширина " + cfg.MinBandwidth + "–"
                + cfg.MaxBandwidth + ", " + cfg.Regression + ", роль " + Role);
        }

        /// <summary>
        /// E[R/S]ₙ = ((n − ½)/n) · Γ((n−1)/2) / (√π·Γ(n/2)) · Σᵢ₌₁ⁿ⁻¹ √((n−i)/i) — Anis–Lloyd, Peters.
        /// Отношение гамма-функций — точной рекурсией r(n+2) = r(n)·(n−1)/n без логарифма гаммы:
        /// в .NET Framework его нет. Вызывается только в Attach.
        /// </summary>
        private static double ExpectedRS(int n)
        {
            double r = (n % 2 == 0) ? Math.Sqrt(Math.PI) : 2.0 / Math.Sqrt(Math.PI);
            for (int m = (n % 2 == 0) ? 2 : 3; m < n; m += 2) r *= (m - 1.0) / m;
            double s = 0; for (int i = 1; i < n; i++) s += Math.Sqrt((double)(n - i) / i);
            return ((n - 0.5) / n) * (r / Math.Sqrt(Math.PI)) * s;
        }

        public override void Compute(int bip)
        {
            if (Host.IsBarCloseOf(cfg.Slot, bip)) OnOwnBar();
            if (bip != Host.ExecBip) return;

            int bar = Host.CurrentBar;
            if (fits == 0 || rCount < retRing.Length)
            {
                Health = SwHealth.Warmup;
                Emit(SwSignal.Empty(bar));
                return;
            }

            double tick = Host.TickSize > 0 ? Host.TickSize : 1.0;
            double slopeT = double.IsNaN(beta) ? 0.0 : beta / tick;
            int dir = Math.Abs(slopeT) >= cfg.SlopeThresholdTicks ? Math.Sign(slopeT) : 0;
            int code = dir != 0 ? 1 : 0;
            if (dir != 0 && cfg.ExpRandomWalkGate && Math.Abs(hurst - cfg.RwLevel) < cfg.ExpGateBand) { dir = 0; code = 2; }

            double conf = dir != 0 ? Math.Min(1.0, Math.Abs(slopeT) / Math.Max(1e-9, 4.0 * cfg.SlopeThresholdTicks)) : 0.0;
            if (cfg.ExpHurstConfidence) conf *= Math.Max(0.0, Math.Min(1.0, (hurst - cfg.RwLevel) / 0.1));

            SwSignal s = new SwSignal();
            s.IsReady = true; s.ProducedAtBar = bar;
            s.EntryStopPrice = double.NaN; s.TrailTicksOverride = double.NaN;
            s.Direction = dir;
            s.Verdict = dir != 0 ? SwVerdict.Agree : SwVerdict.Neutral;
            s.Confidence = conf;
            if (dir != lastDir || code != lastCode)
            {
                lastDir = dir; lastCode = code;
                textCache = (code == 2 ? "Хёрст: блуждание" : dir > 0 ? "Хёрст-ядро: вверх" : dir < 0 ? "Хёрст-ядро: вниз" : "Хёрст-ядро: плоско")
                          + ", H " + hurst.ToString("F2") + ", окно " + hUsed;
            }
            s.Text = textCache;
            Health = SwHealth.Ok;
            Emit(s);
        }

        private void OnOwnBar()
        {
            if (!Host.SlotReady(cfg.Slot, 2)) return;
            double c = Host.CloseOf(cfg.Slot, 0);
            if (double.IsNaN(c) || c <= 0) return;

            double prev = cCount > 0 ? closeRing[cHead] : double.NaN;
            cHead = (cHead + 1) % cap; closeRing[cHead] = c; if (cCount < cap) cCount++;
            if (!double.IsNaN(prev) && prev > 0)
            {
                rHead = (rHead + 1) % retRing.Length; retRing[rHead] = Math.Log(c / prev);
                if (rCount < retRing.Length) rCount++;
            }
            if (rCount >= retRing.Length) hurst = HurstRS();

            // Отображение Хёрста в ширину окна.
            double t = (hurst - cfg.HLow) / Math.Max(1e-9, cfg.HHigh - cfg.HLow);
            t = Math.Max(0.0, Math.Min(1.0, t));
            if (cfg.ExpInverseMap) t = 1.0 - t;
            int hb = (int)Math.Round(cfg.MinBandwidth + t * (cfg.MaxBandwidth - cfg.MinBandwidth));
            hb = Math.Max(3, Math.Min(Math.Min(cCount, yBuf.Length - 1), hb));
            if (hb < 3) return;
            hUsed = hb;

            for (int i = 0; i < hb; i++) yBuf[i] = closeRing[(cHead - i + cap) % cap];
            eng.Fit(yBuf, mult, hb, hb, cfg.Kernel, cfg.Regression);
            if (!eng.Ok) return;

            alpha = eng.Alpha;
            beta = cfg.Regression == SwRegressionType.NadarayaWatson
                 ? (double.IsNaN(prevAlpha) ? 0.0 : alpha - prevAlpha) : eng.Beta;
            prevAlpha = alpha;
            fits++;
        }

        /// <summary>
        /// Показатель Хёрста по нескольким масштабам с вычетом ожидаемого R/S блуждания.
        /// Окна одного масштаба не перекрываются; R/S масштаба — среднее по окнам.
        /// </summary>
        private double HurstRS()
        {
            int N = retRing.Length;
            double sx = 0, sy = 0, sxx = 0, sxy = 0; int m = 0;
            for (int j = 0; j < nScales; j++)
            {
                int n = scaleN[j], windows = N / n;
                double acc = 0; int ok = 0;
                for (int w = 0; w < windows; w++)
                {
                    double mean = 0;
                    for (int i = 0; i < n; i++) mean += Ret(w * n + i);
                    mean /= n;
                    double cum = 0, mn = 0, mx = 0, ss = 0;
                    for (int i = 0; i < n; i++)
                    {
                        double d = Ret(w * n + i) - mean;
                        cum += d; ss += d * d;
                        if (cum < mn) mn = cum; if (cum > mx) mx = cum;
                    }
                    double sd = Math.Sqrt(ss / n);
                    if (sd > 0) { acc += (mx - mn) / sd; ok++; }
                }
                if (ok == 0) continue;
                double x = logN[j], y = Math.Log(acc / ok) - logE[j];
                sx += x; sy += y; sxx += x * x; sxy += x * y; m++;
            }
            if (m < 2) return 0.5;
            double den = m * sxx - sx * sx;
            return den > 0 ? 0.5 + (m * sxy - sx * sy) / den : 0.5;
        }

        /// <summary>k-я доходность окна по порядку времени, от старой к новой.</summary>
        private double Ret(int k) { return retRing[(rHead - (retRing.Length - 1) + k + 2 * retRing.Length) % retRing.Length]; }

        public string StateLine
        {
            get
            {
                double tick = Host != null && Host.TickSize > 0 ? Host.TickSize : 1.0;
                return string.Format("H {0:F3} → окно {1} | {2} | наклон {3:F2} т/бар",
                    hurst, hUsed, cfg.Regression == SwRegressionType.LocalLinear ? "LL" : "NW",
                    double.IsNaN(beta) ? 0.0 : beta / tick);
            }
        }
    }
}
