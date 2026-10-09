#region Using declarations
using System;
using NinjaTrader.NinjaScript;
#endregion

// ============================================================================
//  DZ_SW_Mod_Lorentzian_S021 — КЛАССИФИКАТОР ЛОРЕНЦА, [MOD11], v1.1 (2026-09-27)
//  Роль Filter по умолчанию — подтверждение входов PAC; Signal при [L12].
//
//  КОНВЕЙЕР
//    1. Пять признаков на закрытии бара своей серии: волатильность ATR/цена,
//       скорость фильтра Калмана, RSI, плотность объёма, смещение от центра масс.
//    2. Нормализация: предварительная стандартизация → Йео–Джонсон с λ,
//       оцененным по максимуму правдоподобия на скользящем окне → z-оценка.
//       Параметры пересчитываются раз в [L08] баров и только по прошлым данным.
//    3. Расстояние Лоренца: d = Σ ln(1 + |xᵢ − yᵢ|) — логарифм гасит выбросы.
//    4. K ближайших соседей за [L02] баров с шагом [L04].
//
//  ЗАЩИТА ОТ ЗАГЛЯДЫВАНИЯ — главное свойство модуля.
//    Метка соседа i — знак приращения цены за H баров ВПЕРЁД от i. Сосед
//    допускается, только если i + H ≤ t: его исход уже известен. Без этого
//    правила классификатор голосует будущим, и его точность на истории — фикция.
//    Шаг выборки соседей снижает зависимость соседних меток: соседние бары
//    делят большую часть будущего окна, и их голоса почти не независимы.
//
//  ZERO-GC. Все буферы создаются в Attach; на такте бара выделений нет.
//
//  ЭКСПЕРИМЕНТЫ — выключены по умолчанию:
//    [L13] голос с гауссовым весом по расстоянию Лоренца вместо равного;
//    [L14]/[L15] самопроверка: причинная скользящая точность против базовой
//          частоты класса; ниже порога — модуль уходит в нейтраль;
//    [L16] согласие с трендом адаптивного ядра [MOD9]: расхождение — нейтраль.
// ============================================================================

namespace NinjaTrader.NinjaScript
{
    /// <summary>Метод решения по прошлым ситуациям — выбор пользователя [L17].</summary>
    public enum SwLorentzMethod
    {
        KnnVote,          // K ближайших, голос по знаку исхода
        NadarayaWatson,   // взвешенное ядром среднее будущей доходности ВСЕХ допустимых ситуаций
        Consensus         // направление, только если оба метода согласны
    }
}

namespace NinjaTrader.NinjaScript.Strategies
{
    public class SwLorentzianConfig
    {
        public int Slot = 1;
        public int Lookback = 2000;
        public int Neighbors = 16;
        public int Stride = 4;
        public int Horizon = 4;
        public double VoteThreshold = 0.5;       // доля перевеса голосов для направления
        public bool UseYeoJohnson = true;
        public int RefitBars = 100;
        public int FitWindow = 500;
        public double KalmanQ = 0.01, KalmanR = 1.0;
        public bool SignalMode = false;
        public bool ExpKernelVote = false;
        public bool ExpPrecisionGate = false;
        public double ExpPrecisionMin = 0.65;
        public int EvalWindow = 200;
        public bool ExpAgreeKernel = false;

        // --- Надарая–Ватсон в пространстве признаков ---
        public SwLorentzMethod Method = SwLorentzMethod.KnnVote;
        public SwKernelType NwKernel = SwKernelType.Gaussian;
        public double NwBandMult = 0.5;       // σ ядра = множитель × медиана расстояний
        public double NwThreshold = 0.10;     // |прогноз| в ATR, ниже — нейтраль
        public double NwMinEff = 10;          // минимальный эффективный объём выборки
    }

    public class SwLorentzianModule : SwModule
    {
        private const int F = 5;
        private readonly SwLorentzianConfig cfg;
        private readonly SwAdaptiveKernelModule kernel;

        // --- кольцевые хранилища: признаки и закрытия по бару своей серии ---
        private double[,] raw;
        private double[] closeRing, scratch;
        private int cap, count, head;

        // --- параметры нормализации по признакам ---
        private readonly double[] preMu = new double[F], preSd = new double[F], lam = new double[F];
        private readonly double[] postMu = new double[F], postSd = new double[F];
        private bool normReady;
        private int sinceRefit;

        // --- K ближайших ---
        private double[] kDist; private int[] kLab; private int kN;

        // --- Надарая–Ватсон: расстояния и доходности кандидатов, ATR по барам ---
        private double[] nwD, nwY, nwScratch, atrRing;
        private int nwN;
        private double nwPred = double.NaN, nwEff;
        private int knnDir, nwDir;

        // --- состояние признаков ---
        private double atr, prevClose = double.NaN, rsiUp, rsiDn;
        private int rsiN;
        private double kx = double.NaN, kv, p00 = 1, p01, p11 = 1;
        private double[] volRing, tpvRing; private int volIdx, volCnt;

        // --- решение и самопроверка ---
        private int dir; private double strength;
        private int[] predRing; private int predHead, predCnt;
        private bool[] evalHit, evalUp, evalLong; private int evalHead, evalCnt;
        private int predsTotal;
        private string textCache = ""; private int lastDir = int.MinValue, lastCode = -1;

        public SwLorentzianModule(string id, SwLorentzianConfig config, SwAdaptiveKernelModule kernelModule)
        {
            Id = id;
            cfg = config ?? new SwLorentzianConfig();
            kernel = kernelModule;
            Role = cfg.SignalMode ? SwRole.Signal : SwRole.Filter;
        }

        public override void Attach(SwHostView host)
        {
            base.Attach(host);
            cap = Math.Max(cfg.Lookback, cfg.FitWindow) + cfg.Horizon + 2;
            raw = new double[cap, F];
            closeRing = new double[cap];
            scratch = new double[Math.Max(10, cfg.FitWindow)];
            kDist = new double[Math.Max(1, cfg.Neighbors)];
            kLab = new int[Math.Max(1, cfg.Neighbors)];
            int maxCand = cfg.Lookback / Math.Max(1, cfg.Stride) + 2;
            nwD = new double[maxCand]; nwY = new double[maxCand]; nwScratch = new double[maxCand];
            atrRing = new double[cap];
            volRing = new double[20]; tpvRing = new double[20];
            predRing = new int[Math.Max(1, cfg.Horizon) + 1];
            evalHit = new bool[Math.Max(10, cfg.EvalWindow)];
            evalUp = new bool[Math.Max(10, cfg.EvalWindow)];
            evalLong = new bool[Math.Max(10, cfg.EvalWindow)];
            for (int f = 0; f < F; f++) { preSd[f] = 1; postSd[f] = 1; lam[f] = 1; }
            Host.Trace(Id, "LOR_ATTACHED", "окно " + cfg.Lookback + ", K " + cfg.Neighbors + ", шаг " + cfg.Stride
                + ", горизонт " + cfg.Horizon + (cfg.UseYeoJohnson ? ", Йео–Джонсон" : "") + ", роль " + Role);
            if (cfg.ExpAgreeKernel && kernel == null)
                Host.Trace(Id, "LOR_NO_KERNEL", "согласие с ядром включено, но [MOD9] не подключён — проверка пропускается");
        }

        public override void Compute(int bip)
        {
            if (Host.IsBarCloseOf(cfg.Slot, bip)) OnOwnBar();
            if (bip != Host.ExecBip) return;

            int bar = Host.CurrentBar;
            if (!normReady || count < cfg.Horizon + cfg.Neighbors * cfg.Stride + 2)
            {
                Health = SwHealth.Warmup;
                Emit(SwSignal.Empty(bar));
                return;
            }

            int d = dir, code = d != 0 ? 1 : 0;
            double prec = Precision(), baseRate = BaseRate();
            // Порог — абсолютная точность [L15] И превышение над эталоном «монетки».
            if (d != 0 && cfg.ExpPrecisionGate && evalCnt >= evalHit.Length
                && (prec < cfg.ExpPrecisionMin || !(prec > baseRate))) { d = 0; code = 2; }
            if (d != 0 && cfg.ExpAgreeKernel && kernel != null)
            {
                int kd = KernelDir();
                if (kd != 0 && kd != d) { d = 0; code = 3; }
            }

            SwSignal s = new SwSignal();
            s.IsReady = true; s.ProducedAtBar = bar;
            s.EntryStopPrice = double.NaN; s.TrailTicksOverride = double.NaN;
            s.Direction = d;
            s.Verdict = d != 0 ? SwVerdict.Agree : SwVerdict.Neutral;
            s.Confidence = d != 0 ? Math.Min(1.0, strength) : 0.0;

            if (d != lastDir || code != lastCode)
            {
                lastDir = d; lastCode = code;
                textCache = (code == 2 ? "Лоренц: точность ниже порога" : code == 3 ? "Лоренц: против ядра"
                          : d > 0 ? "Лоренц: вверх" : d < 0 ? "Лоренц: вниз" : "Лоренц: нет перевеса")
                          + ", перевес " + strength.ToString("F2");
            }
            s.Text = textCache;
            Health = SwHealth.Ok;
            Emit(s);
        }

        private int KernelDir()
        {
            // Направление ядра — по его последнему сигналу; модуль ядра голосует через ту же структуру.
            return kernel.LastSignal.IsReady ? kernel.LastSignal.Direction : 0;
        }

        #region Бар своей серии: признаки, самопроверка, нормализация, классификация

        private void OnOwnBar()
        {
            if (!Host.SlotReady(cfg.Slot, 22)) return;
            double h = Host.HighOf(cfg.Slot, 0), l = Host.LowOf(cfg.Slot, 0), c = Host.CloseOf(cfg.Slot, 0);
            double v = Host.VolumeOf(cfg.Slot, 0);
            if (double.IsNaN(c) || c <= 0) return;

            // --- признаки ---
            double tr = double.IsNaN(prevClose) ? h - l : Math.Max(h - l, Math.Max(Math.Abs(h - prevClose), Math.Abs(l - prevClose)));
            atr = double.IsNaN(prevClose) ? tr : atr + (tr - atr) / 14.0;
            double chg = double.IsNaN(prevClose) ? 0 : c - prevClose;
            rsiN++;
            rsiUp += ((chg > 0 ? chg : 0) - rsiUp) / Math.Min(14, rsiN);
            rsiDn += ((chg < 0 ? -chg : 0) - rsiDn) / Math.Min(14, rsiN);
            double rsi = rsiDn > 0 ? 100 - 100 / (1 + rsiUp / rsiDn) : 100;

            // Калман: уровень и скорость, модель постоянной скорости.
            if (double.IsNaN(kx)) { kx = c; kv = 0; }
            else
            {
                double xp = kx + kv, q = cfg.KalmanQ, r = cfg.KalmanR;
                double a00 = p00 + 2 * p01 + p11 + q, a01 = p01 + p11, a11 = p11 + q;
                double s = a00 + r, g0 = a00 / s, g1 = a01 / s, e = c - xp;
                kx = xp + g0 * e; kv = kv + g1 * e;
                p00 = (1 - g0) * a00; p01 = (1 - g0) * a01; p11 = a11 - g1 * a01;
            }

            volRing[volIdx] = v; tpvRing[volIdx] = v * (h + l + c) / 3.0;
            volIdx = (volIdx + 1) % volRing.Length; if (volCnt < volRing.Length) volCnt++;
            double vs = 0, tps = 0; for (int i = 0; i < volCnt; i++) { vs += volRing[i]; tps += tpvRing[i]; }
            double vdens = vs > 0 ? v / (vs / volCnt) : 1.0;
            double com = vs > 0 ? tps / vs : c;
            prevClose = c;

            // --- запись в кольцо ---
            head = (head + 1) % cap; if (count < cap) count++;
            double a = atr > 0 ? atr : 1e-9;
            raw[head, 0] = atr / c;
            raw[head, 1] = kv / a;
            raw[head, 2] = rsi;
            raw[head, 3] = vdens;
            raw[head, 4] = (c - com) / a;
            closeRing[head] = c;
            atrRing[head] = a;

            Evaluate();
            if (++sinceRefit >= cfg.RefitBars || !normReady) { if (Refit()) sinceRefit = 0; }
            if (normReady) Classify();
        }

        private int Idx(int back) { return (head - back + cap) % cap; }

        /// <summary>
        /// Причинная самопроверка: прогноз, сделанный H баров назад, сверяется с тем,
        /// что произошло. Точность сравнивается с базовой частотой класса: при частоте
        /// роста 60% точность 65% означает перевес всего в 5 пунктов.
        /// </summary>
        private void Evaluate()
        {
            if (predCnt > cfg.Horizon && count > cfg.Horizon)
            {
                int pred = predRing[(predHead - cfg.Horizon + predRing.Length) % predRing.Length];
                bool up = closeRing[head] > closeRing[Idx(cfg.Horizon)];
                if (pred != 0)
                {
                    evalHit[evalHead] = (pred > 0) == up;
                    evalUp[evalHead] = up;          // фактический исход
                    evalLong[evalHead] = pred > 0;  // направление прогноза
                    evalHead = (evalHead + 1) % evalHit.Length; if (evalCnt < evalHit.Length) evalCnt++;
                    predsTotal++;
                }
            }
        }

        public double Precision()
        {
            if (evalCnt == 0) return double.NaN;
            int n = 0; for (int i = 0; i < evalCnt; i++) if (evalHit[i]) n++;
            return (double)n / evalCnt;
        }

        /// <summary>
        /// Эталон точности: «монетка» с рыночной частотой роста p и тем же соотношением
        /// прогнозов вверх и вниз. Её точность = доля_вверх·p + доля_вниз·(1−p). Точность
        /// классификатора имеет смысл только как превышение над этим числом.
        /// </summary>
        public double BaseRate()
        {
            if (evalCnt == 0) return double.NaN;
            int up = 0, lng = 0;
            for (int i = 0; i < evalCnt; i++) { if (evalUp[i]) up++; if (evalLong[i]) lng++; }
            double p = (double)up / evalCnt, fl = (double)lng / evalCnt;
            return fl * p + (1 - fl) * (1 - p);
        }

        #endregion

        #region Нормализация: стандартизация → Йео–Джонсон → z-оценка

        private static double YJ(double x, double l)
        {
            if (x >= 0) return Math.Abs(l) < 1e-9 ? Math.Log(x + 1) : (Math.Pow(x + 1, l) - 1) / l;
            return Math.Abs(l - 2) < 1e-9 ? -Math.Log(1 - x) : -(Math.Pow(1 - x, 2 - l) - 1) / (2 - l);
        }

        /// <summary>Логарифм правдоподобия Йео–Джонсона с точностью до константы.</summary>
        private double LogLik(int n, double l)
        {
            double m = 0; for (int i = 0; i < n; i++) m += YJ(scratch[i], l); m /= n;
            double v = 0, j = 0;
            for (int i = 0; i < n; i++) { double y = YJ(scratch[i], l) - m; v += y * y; j += Math.Sign(scratch[i]) * Math.Log(Math.Abs(scratch[i]) + 1); }
            v /= n;
            return v > 0 ? -0.5 * n * Math.Log(v) + (l - 1) * j : double.NegativeInfinity;
        }

        /// <summary>
        /// Пересчёт параметров по окну [L09] ПРОШЛЫХ баров. λ ищется золотым сечением
        /// на [−2; 2]. Используются только бары, уже записанные в кольцо: будущего нет.
        /// </summary>
        private bool Refit()
        {
            int n = Math.Min(count, cfg.FitWindow);
            if (n < 50) return false;
            for (int f = 0; f < F; f++)
            {
                double m = 0; for (int i = 0; i < n; i++) m += raw[Idx(i), f]; m /= n;
                double v = 0; for (int i = 0; i < n; i++) { double z = raw[Idx(i), f] - m; v += z * z; }
                preMu[f] = m; preSd[f] = Math.Sqrt(v / Math.Max(1, n - 1)); if (!(preSd[f] > 0)) preSd[f] = 1;
                for (int i = 0; i < n; i++) scratch[i] = (raw[Idx(i), f] - preMu[f]) / preSd[f];

                double lo = -2, hi = 2, gr = 0.6180339887;
                if (cfg.UseYeoJohnson)
                {
                    double x1 = hi - gr * (hi - lo), x2 = lo + gr * (hi - lo), f1 = LogLik(n, x1), f2 = LogLik(n, x2);
                    for (int it = 0; it < 30; it++)
                    {
                        if (f1 < f2) { lo = x1; x1 = x2; f1 = f2; x2 = lo + gr * (hi - lo); f2 = LogLik(n, x2); }
                        else { hi = x2; x2 = x1; f2 = f1; x1 = hi - gr * (hi - lo); f1 = LogLik(n, x1); }
                    }
                    lam[f] = 0.5 * (lo + hi);
                }
                else lam[f] = 1.0;

                double pm = 0; for (int i = 0; i < n; i++) pm += YJ(scratch[i], lam[f]); pm /= n;
                double pv = 0; for (int i = 0; i < n; i++) { double y = YJ(scratch[i], lam[f]) - pm; pv += y * y; }
                postMu[f] = pm; postSd[f] = Math.Sqrt(pv / Math.Max(1, n - 1)); if (!(postSd[f] > 0)) postSd[f] = 1;
            }
            normReady = true;
            return true;
        }

        private double Z(int back, int f)
        {
            return (YJ((raw[Idx(back), f] - preMu[f]) / preSd[f], lam[f]) - postMu[f]) / postSd[f];
        }

        #endregion

        #region K ближайших по расстоянию Лоренца

        private void Classify()
        {
            int K = kDist.Length; kN = 0; nwN = 0;
            double q0 = Z(0, 0), q1 = Z(0, 1), q2 = Z(0, 2), q3 = Z(0, 3), q4 = Z(0, 4);
            int maxBack = Math.Min(count - 1, cfg.Lookback);

            // Соседи — только с известным исходом: back ≥ H. Шаг снижает зависимость меток.
            for (int back = cfg.Horizon; back <= maxBack; back += Math.Max(1, cfg.Stride))
            {
                if (back + 0 > count - 1) break;
                double d = Math.Log(1 + Math.Abs(q0 - Z(back, 0))) + Math.Log(1 + Math.Abs(q1 - Z(back, 1)))
                         + Math.Log(1 + Math.Abs(q2 - Z(back, 2))) + Math.Log(1 + Math.Abs(q3 - Z(back, 3)))
                         + Math.Log(1 + Math.Abs(q4 - Z(back, 4)));
                int lab = closeRing[Idx(back - cfg.Horizon)] > closeRing[Idx(back)] ? 1 : -1;

                // Для Надарая–Ватсона — доходность за H баров в ATR на момент ситуации:
                // регрессии нужна величина хода, а не только знак.
                if (nwN < nwD.Length)
                {
                    double at = atrRing[Idx(back)];
                    nwD[nwN] = d;
                    nwY[nwN] = at > 0 ? (closeRing[Idx(back - cfg.Horizon)] - closeRing[Idx(back)]) / at : 0.0;
                    nwN++;
                }

                if (kN < K) { Insert(d, lab, kN); kN++; }
                else if (d < kDist[K - 1]) Insert(d, lab, K - 1);
            }

            double sw = 0, vote = 0, h2 = 0;
            if (cfg.ExpKernelVote && kN > 0) { double md = kDist[kN / 2]; h2 = md > 0 ? 2 * md * md : 1; }
            for (int i = 0; i < kN; i++)
            {
                double w = cfg.ExpKernelVote ? Math.Exp(-kDist[i] * kDist[i] / h2) : 1.0;
                sw += w; vote += w * kLab[i];
            }
            double knnStrength = sw > 0 ? Math.Abs(vote) / sw : 0;
            knnDir = knnStrength >= cfg.VoteThreshold ? Math.Sign(vote) : 0;

            double nwStrength = 0; nwDir = 0; nwPred = double.NaN; nwEff = 0;
            if (cfg.Method != SwLorentzMethod.KnnVote && nwN >= 3) nwStrength = NadarayaWatson();

            switch (cfg.Method)
            {
                case SwLorentzMethod.NadarayaWatson: dir = nwDir; strength = nwStrength; break;
                case SwLorentzMethod.Consensus:
                    dir = (knnDir != 0 && knnDir == nwDir) ? knnDir : 0;
                    strength = dir != 0 ? Math.Min(knnStrength, nwStrength) : 0;
                    break;
                default: dir = knnDir; strength = knnStrength; break;
            }

            predRing[predHead] = dir; predHead = (predHead + 1) % predRing.Length; if (predCnt < predRing.Length + cfg.Horizon + 1) predCnt++;
        }

        /// <summary>
        /// Надарая–Ватсон в пространстве признаков: ŷ = Σ K(dᵢ/h)·yᵢ / Σ K(dᵢ/h) по ВСЕМ
        /// допустимым ситуациям. Ширина h = 3 · множитель · медиана расстояний: у гауссова ядра
        /// вычислителя MOD9 z = 3u, поэтому σ = множитель × медиана. Функция ядра — из MOD9,
        /// не переписана. Эффективный объём (Σw)²/Σw² защищает от решения по одной-двум точкам.
        /// </summary>
        private double NadarayaWatson()
        {
            for (int i = 0; i < nwN; i++) nwScratch[i] = nwD[i];
            for (int i = 1; i < nwN; i++)
            {
                double key = nwScratch[i]; int j = i - 1;
                while (j >= 0 && nwScratch[j] > key) { nwScratch[j + 1] = nwScratch[j]; j--; }
                nwScratch[j + 1] = key;
            }
            double med = nwScratch[nwN / 2];
            double h = 3.0 * Math.Max(1e-9, cfg.NwBandMult * med);

            double sw = 0, sw2 = 0, sy = 0;
            for (int i = 0; i < nwN; i++)
            {
                double w = SwAdaptiveKernelEngine.K(cfg.NwKernel, nwD[i] / h);
                if (w <= 0) continue;
                sw += w; sw2 += w * w; sy += w * nwY[i];
            }
            if (sw <= 0) return 0;
            nwPred = sy / sw;
            nwEff = sw * sw / Math.Max(1e-12, sw2);
            if (nwEff < cfg.NwMinEff || Math.Abs(nwPred) < cfg.NwThreshold) return 0;
            nwDir = Math.Sign(nwPred);
            return Math.Min(1.0, Math.Abs(nwPred) / (2.0 * Math.Max(1e-9, cfg.NwThreshold)));
        }

        /// <summary>Вставка в отсортированный массив длины K без выделения памяти.</summary>
        private void Insert(double d, int lab, int pos)
        {
            int j = pos;
            while (j > 0 && kDist[j - 1] > d) { kDist[j] = kDist[j - 1]; kLab[j] = kLab[j - 1]; j--; }
            kDist[j] = d; kLab[j] = lab;
        }

        #endregion

        public string StateLine
        {
            get
            {
                return string.Format("{0} | K {1}, NW {2:F2} ATR (эфф. {3:F0}) → {4} | точность {5:P0} при базе {6:P0} ({7})",
                    cfg.Method, knnDir > 0 ? "↑" : knnDir < 0 ? "↓" : "—", double.IsNaN(nwPred) ? 0.0 : nwPred, nwEff,
                    dir > 0 ? "вверх" : dir < 0 ? "вниз" : "нет", Precision(), BaseRate(), evalCnt);
            }
        }
    }
}
