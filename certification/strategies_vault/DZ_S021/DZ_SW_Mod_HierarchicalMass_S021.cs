#region Using declarations
using System;
using System.Globalization;
using NinjaTrader.NinjaScript;
#endregion

// ============================================================================
//  DZ_SW_Mod_HierarchicalMass_S021 — ИЕРАРХИЧЕСКАЯ МАССА, [MOD15], v1.0 (2026-09-28)
//  Роль Filter по умолчанию, Signal при [G05].
//
//  ОКНО — последние [G02] закрытых минуток своей серии, скользящее.
//    P_true       = Σ Close·Vol / Σ Vol                      — взвешенная по объёму цена
//    эшелоны      полные блоки по 5 и 15 минут от КОНЦА окна; закрытие блока — закрытие
//                 его последней минуты, объём — сумма минут блока. Неполный хвост в
//                 эшелон не входит.
//    P_synthetic  = (Σ C·V + w5·Σ C5·V5 + w15·Σ C15·V15) / (Σ V + w5·Σ V5 + w15·Σ V15)
//    Delta_Bias   = (P_synthetic − P_true) / TickSize
//  СМЫСЛ. Объёмы эшелонов по закону сохранения равны объёму окна, поэтому P_synthetic —
//    среднее трёх взвешенных по объёму цен разного разрешения. На росте закрытие блока
//    выше его средней цены: Delta_Bias > 0. Это дрейф цены внутри окна с учётом объёма.
//    Axis = (max High + min Low)/2;  W = 2 · процентиль [G06] от |Close − Axis|;
//    полосы Axis ± W/2;  Slope = Delta_Bias / окно;  Angle = atan(1/|Slope|) в градусах.
//  Угол — монотонная функция наклона и зависит от масштаба графика: он выводится на
//    пульт, в решении не участвует.
//
//  ОТКЛОНЕНО из ТЗ: разнесение свечи на точки O(0 с) → H(20 с) → L(40 с) → C(60 с).
//    Порядок экстремумов внутри минуты по OHLC неизвестен; такое допущение внесло бы
//    систематическое смещение. В формулах окна эти точки и не используются.
//
//  ZERO-GC: кольца и сортировочные массивы — в Attach; строки — только для пульта.
//  ЭКСПЕРИМЕНТЫ — выключены по умолчанию:
//    [G08]/[G09] шлюз сжатия: ширина ниже доли своей скользящей медианы — нейтраль;
//    [G10] устойчивость: направление после K подряд расчётов одного знака.
// ============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
    public class SwHierarchicalMassConfig
    {
        public int Slot = 0;
        public int WindowMinutes = 15;
        public double Weight5 = 1.0, Weight15 = 1.5;
        public double Percentile = 0.85;
        public double BiasThresholdTicks = 2.0;
        public bool SignalMode = false;
        public bool ExpSqueezeGate = false;
        public double ExpSqueezeRatio = 0.6;
        public int ExpPersistBars = 0;
        public int SqueezeLookback = 100;
    }

    public class SwHierarchicalMassModule : SwModule
    {
        private readonly SwHierarchicalMassConfig cfg;
        private double[] cR, vR, hR, lR, dev, wHist, wScratch;
        private int cap, head, count, wHead, wCount;
        private bool ready;
        private double pTrue, pSyn, biasT, axis, upper, lower, widthT, slope, angle;
        private int dir, persistDir, persistN, code;
        private string textCache = ""; private int lastDir = int.MinValue, lastCode = -1;

        public SwHierarchicalMassModule(string id, SwHierarchicalMassConfig config)
        {
            Id = id;
            cfg = config ?? new SwHierarchicalMassConfig();
            Role = cfg.SignalMode ? SwRole.Signal : SwRole.Filter;
        }

        public override void Attach(SwHostView host)
        {
            base.Attach(host);
            int n = Math.Max(2, cfg.WindowMinutes);
            cap = n + 1;
            cR = new double[cap]; vR = new double[cap]; hR = new double[cap]; lR = new double[cap];
            dev = new double[n];
            wHist = new double[Math.Max(10, cfg.SqueezeLookback)]; wScratch = new double[wHist.Length];
            Host.Trace(Id, "HM_ATTACHED", "окно " + n + " мин, веса 5M " + cfg.Weight5 + " и 15M " + cfg.Weight15 + ", порог " + cfg.BiasThresholdTicks + " т");
        }

        private int Idx(int back) { return (head - back + cap) % cap; }

        public override void Compute(int bip)
        {
            if (Host.IsBarCloseOf(cfg.Slot, bip)) OnOwnBar();
            if (bip != Host.ExecBip) return;
            int bar = Host.CurrentBar;
            if (!ready) { Health = SwHealth.Warmup; Emit(SwSignal.Empty(bar)); return; }

            SwSignal s = new SwSignal();
            s.IsReady = true; s.ProducedAtBar = bar;
            s.EntryStopPrice = double.NaN; s.TrailTicksOverride = double.NaN;
            s.Direction = dir;
            s.Verdict = dir != 0 ? SwVerdict.Agree : SwVerdict.Neutral;
            s.Confidence = dir != 0 ? Math.Min(1.0, Math.Abs(biasT) / Math.Max(1e-9, 2.0 * cfg.BiasThresholdTicks)) : 0.0;
            if (dir != lastDir || code != lastCode)
            {
                lastDir = dir; lastCode = code;
                textCache = (code == 2 ? "Масса: сжатие" : code == 3 ? "Масса: знак не устоялся" : dir > 0 ? "Масса: дрейф вверх" : dir < 0 ? "Масса: дрейф вниз" : "Масса: нет дрейфа")
                          + ", смещение " + biasT.ToString("F1") + " т";
            }
            s.Text = textCache;
            Health = SwHealth.Ok;
            Emit(s);
        }

        private void OnOwnBar()
        {
            if (!Host.SlotReady(cfg.Slot, 2)) return;
            double c = Host.CloseOf(cfg.Slot, 0), v = Host.VolumeOf(cfg.Slot, 0);
            if (double.IsNaN(c) || double.IsNaN(v)) return;
            head = (head + 1) % cap; if (count < cap) count++;
            cR[head] = c; vR[head] = Math.Max(0.0, v); hR[head] = Host.HighOf(cfg.Slot, 0); lR[head] = Host.LowOf(cfg.Slot, 0);
            int n = dev.Length;
            if (count < n) return;

            double tick = Host.TickSize > 0 ? Host.TickSize : 1.0;
            double tot = 0, sCV = 0, hi = double.MinValue, lo = double.MaxValue;
            for (int i = 0; i < n; i++)
            {
                int k = Idx(i); tot += vR[k]; sCV += cR[k] * vR[k];
                if (hR[k] > hi) hi = hR[k]; if (lR[k] < lo) lo = lR[k];
            }
            if (tot <= 0) { ready = false; return; }     // окно без объёма — нет массы
            pTrue = sCV / tot;

            double num = sCV, den = tot;
            AddEchelon(5, cfg.Weight5, n, ref num, ref den);
            AddEchelon(15, cfg.Weight15, n, ref num, ref den);
            pSyn = num / den;
            biasT = (pSyn - pTrue) / tick;

            axis = (hi + lo) / 2.0;
            for (int i = 0; i < n; i++) dev[i] = Math.Abs(cR[Idx(i)] - axis);
            Sort(dev, n);
            double w = 2.0 * dev[Math.Min(n - 1, (int)Math.Round(n * cfg.Percentile))];
            upper = axis + w / 2.0; lower = axis - w / 2.0; widthT = w / tick;
            slope = biasT / n;
            angle = Math.Abs(slope) < 1e-4 ? 90.0 : Math.Atan(1.0 / Math.Abs(slope)) * 180.0 / Math.PI;

            wHist[wHead] = widthT; wHead = (wHead + 1) % wHist.Length; if (wCount < wHist.Length) wCount++;

            int raw = biasT >= cfg.BiasThresholdTicks ? 1 : biasT <= -cfg.BiasThresholdTicks ? -1 : 0;
            code = raw != 0 ? 1 : 0; dir = raw;
            if (dir != 0 && cfg.ExpSqueezeGate && wCount >= 20)
            {
                for (int i = 0; i < wCount; i++) wScratch[i] = wHist[i];
                Sort(wScratch, wCount);
                if (widthT < cfg.ExpSqueezeRatio * wScratch[wCount / 2]) { dir = 0; code = 2; }
            }
            if (raw != 0 && raw == persistDir) persistN++; else { persistDir = raw; persistN = raw != 0 ? 1 : 0; }
            if (dir != 0 && cfg.ExpPersistBars > 1 && persistN < cfg.ExpPersistBars) { dir = 0; code = 3; }
            ready = true;
        }

        /// <summary>Полные блоки по k минут от конца окна: закрытие блока — его последняя минута.</summary>
        private void AddEchelon(int k, double weight, int n, ref double num, ref double den)
        {
            if (n < k || weight <= 0) return;
            for (int b = 0; b + k <= n; b += k)
            {
                double vb = 0;
                for (int i = b; i < b + k; i++) vb += vR[Idx(i)];
                num += weight * cR[Idx(b)] * vb; den += weight * vb;
            }
        }

        private static void Sort(double[] a, int n)
        {
            for (int i = 1; i < n; i++) { double x = a[i]; int j = i - 1; while (j >= 0 && a[j] > x) { a[j + 1] = a[j]; j--; } a[j + 1] = x; }
        }

        /// <summary>Телеметрия для пульта — поля по ТЗ. Вызывается, только когда пульт подключён.</summary>
        public override string TelemetryJson(CultureInfo inv)
        {
            if (!ready) return null;
            return "{\"event\":\"hierarchical_mass_update\",\"htf_minutes\":" + dev.Length
                + ",\"p_true\":" + pTrue.ToString("R", inv) + ",\"p_synthetic\":" + pSyn.ToString("R", inv)
                + ",\"delta_bias_ticks\":" + biasT.ToString("F2", inv) + ",\"axis\":" + axis.ToString("R", inv)
                + ",\"upper_band\":" + upper.ToString("R", inv) + ",\"lower_band\":" + lower.ToString("R", inv)
                + ",\"width_ticks\":" + widthT.ToString("F1", inv) + ",\"slope_ticks_min\":" + slope.ToString("F4", inv)
                + ",\"angle_deg\":" + angle.ToString("F1", inv) + "}";
        }

        public string StateLine
        {
            get { return string.Format(CultureInfo.InvariantCulture, "смещение {0:F1} т | ось {1:F2} | ширина {2:F0} т | угол {3:F0}°", biasT, axis, widthT, angle); }
        }
    }
}
