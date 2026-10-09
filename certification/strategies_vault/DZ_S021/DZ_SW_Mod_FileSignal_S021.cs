#region Using declarations
using System;
using System.Globalization;
using System.IO;
using NinjaTrader.NinjaScript;
#endregion

// ============================================================================
//  DZ_SW_Mod_FileSignal_S021 — МОСТ «ПК → СТРАТЕГИЯ», [MOD12], v1.0 (2026-09-27)
//  Роль Filter по умолчанию, Signal при [Q04].
//
//  ЧТО ДЕЛАЕТ. Читает сигнал, который Python на ПК записал в файл, и передаёт его в
//  голосование коммутатора. ОРДЕРОВ С ПК НЕТ: исполнение остаётся в единственной точке
//  коммутатора со всеми защитами.
//
//  ФОРМАТ ФАЙЛА — одна строка, пишется атомарно (временный файл + os.replace):
//    seq,bar_open_utc,period_min,produced_utc,direction,confidence,text
//
//  ПРОВЕРКИ — сигнал отвергается, если:
//    1. файл не читается или строка не разбирается;
//    2. produced_utc старше [Q02] секунд — ПК остановился;
//    3. закрытие бара сигнала отстаёт от текущего больше чем на [Q03] периодов;
//    4. seq не вырос с прошлого принятого — повтор старого сигнала после перезапуска ПК.
//  Отвергнутый сигнал делает модуль НЕГОТОВЫМ, и по правилу коммутатора неготовый
//  фильтр запрещает вход.
//
//  ЗАДЕРЖКА. Python считает по бару, который уже закрылся, поэтому стратегия видит
//  его результат на закрытии следующего бара: сигнал с ПК всегда на бар позже.
//  Допуск [Q03] по умолчанию — 2 периода.
// ============================================================================

namespace NinjaTrader.NinjaScript.Strategies
{
    public class SwFileSignalConfig
    {
        public string Path = "";
        public int MaxAgeSeconds = 120;
        public int MaxLagBars = 2;
        public bool SignalMode = false;
        public double MinConfidence = 0.0;
    }

    public class SwFileSignalModule : SwModule
    {
        private readonly SwFileSignalConfig cfg;
        private TimeZoneInfo platformTz;
        private long lastSeq = -1;
        private int accepted, rejected;
        private string lastReason = "нет данных";
        private SwSignal lastGood;
        private bool haveGood;

        public SwFileSignalModule(string id, SwFileSignalConfig config)
        {
            Id = id;
            cfg = config ?? new SwFileSignalConfig();
            Role = cfg.SignalMode ? SwRole.Signal : SwRole.Filter;
        }

        public override void Attach(SwHostView host)
        {
            base.Attach(host);
            try { platformTz = NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo; } catch { platformTz = null; }
            if (platformTz == null) platformTz = TimeZoneInfo.Local;
            Host.Trace(Id, "FS_ATTACHED", "файл " + cfg.Path + ", свежесть " + cfg.MaxAgeSeconds + " с, отставание ≤ "
                + cfg.MaxLagBars + " бар., роль " + Role);
        }

        public override void Compute(int bip)
        {
            if (bip != Host.ExecBip) return;
            int bar = Host.CurrentBar;

            string why;
            SwSignal s;
            if (TryRead(bar, out s, out why))
            {
                accepted++; lastReason = why; lastGood = s; haveGood = true;
                Health = SwHealth.Ok;
                Emit(s);
                return;
            }

            // Отказ закрывает вход: неготовый сигнал, а не последний удачный.
            rejected++;
            if (why != lastReason) Host.Trace(Id, "FS_REJECTED", why);
            lastReason = why;
            Health = SwHealth.Stale;
            Emit(SwSignal.Empty(bar));
        }

        private bool TryRead(int bar, out SwSignal s, out string why)
        {
            s = SwSignal.Empty(bar);
            string line;
            try
            {
                using (var fs = new FileStream(cfg.Path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                using (var rd = new StreamReader(fs))
                    line = rd.ReadLine();
            }
            catch (Exception ex) { why = "файл не читается: " + ex.Message; return false; }
            if (string.IsNullOrEmpty(line)) { why = "файл пуст"; return false; }

            string[] p = line.Split(new[] { ',' }, 7);
            if (p.Length < 6) { why = "строка не разбирается"; return false; }

            var inv = CultureInfo.InvariantCulture;
            long seq; DateTime barOpen, produced; int period, dir; double conf;
            if (!long.TryParse(p[0], NumberStyles.Integer, inv, out seq)
                || !DateTime.TryParse(p[1], inv, DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out barOpen)
                || !int.TryParse(p[2], NumberStyles.Integer, inv, out period)
                || !DateTime.TryParse(p[3], inv, DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal, out produced)
                || !int.TryParse(p[4], NumberStyles.Integer, inv, out dir)
                || !double.TryParse(p[5], NumberStyles.Float, inv, out conf))
            { why = "поля не разбираются"; return false; }

            // 2. Свежесть по часам: ПК остановился — сигнал устарел, даже если рынок стоит.
            double age = (DateTime.UtcNow - produced).TotalSeconds;
            if (age > cfg.MaxAgeSeconds) { why = "сигнал старше " + cfg.MaxAgeSeconds + " с (" + age.ToString("F0") + " с)"; return false; }

            // 3. Отставание по барам: закрытие бара сигнала против закрытия текущего бара.
            DateTime nowClose;
            try { nowClose = TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(Host.Time, DateTimeKind.Unspecified), platformTz); }
            catch { why = "время бара не переводится в UTC"; return false; }
            double lagMin = (nowClose - barOpen.AddMinutes(period)).TotalMinutes;
            if (lagMin < 0 || lagMin > cfg.MaxLagBars * Math.Max(1, period))
            { why = "бар сигнала отстаёт на " + lagMin.ToString("F0") + " мин"; return false; }

            // 4. Номер обязан расти; равный номер — тот же сигнал, он принимается повторно.
            if (seq < lastSeq) { why = "номер сигнала уменьшился: повтор старого"; return false; }
            lastSeq = seq;

            s.IsReady = true;
            s.ProducedAtBar = bar;
            s.EntryStopPrice = double.NaN; s.TrailTicksOverride = double.NaN;
            s.Direction = conf >= cfg.MinConfidence ? Math.Sign(dir) : 0;
            s.Confidence = Math.Max(0.0, Math.Min(1.0, conf));
            s.Verdict = s.Direction != 0 ? SwVerdict.Agree : SwVerdict.Neutral;
            s.Text = p.Length > 6 ? "ПК: " + p[6] : "ПК";
            why = "принят №" + seq + ", отставание " + lagMin.ToString("F0") + " мин, возраст " + age.ToString("F0") + " с";
            return true;
        }

        public string StateLine
        {
            get { return string.Format("принято {0}, отвергнуто {1} | {2}", accepted, rejected, lastReason); }
        }
    }
}
