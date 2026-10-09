		#region Using declarations
		using System;
		using System.Collections.Generic;
		using System.ComponentModel;
		using System.ComponentModel.DataAnnotations;
		using System.Text;
		using System.Windows.Media;
		using System.Xml.Serialization;
		using NinjaTrader.Cbi;
		using NinjaTrader.Data;
		using NinjaTrader.Gui;
		using NinjaTrader.Gui.Tools;
		using NinjaTrader.NinjaScript;
		using NinjaTrader.NinjaScript.DrawingTools;
		using NinjaTrader.NinjaScript.Indicators; // тип ATR в объявлении поля
		#endregion
		
		// ============================================================================
		// DZ_SW_Hub_S021 — КОММУТАТОР ТОРГОВОЙ СИСТЕМЫ, v1.0 (2026-09-19)
		//
		// НАЗНАЧЕНИЕ. Одно ядро, к которому подключаются вычислительные модули.
		// Ядро отвечает за жизненный цикл, диспетчеризацию по сериям, сбор сигналов,
		// трассировку, обнаружение потерь и единственную точку выставления заявок.
		// Модули отвечают только за вычисление. Про ордера они не знают ничего и
		// вызвать их физически не могут: доступа к ордерному API у них нет.
		//
		// ТРИ МЕХАНИЗМА, РАДИ КОТОРЫХ ВСЁ ПОСТРОЕНО.
		//
		// 1. ДВУСТОРОННИЙ УЧЁТ СИГНАЛОВ. Модуль не возвращает значение, а кладёт его
		// в собственный ящик вызовом Emit. Коммутатор ящик разбирает. Счётчик
		// отправленных и счётчик принятых ведутся независимо. Их расхождение и
		// есть потеря сигнала — она обнаруживается, а не остаётся незамеченной.
		//
		// 2. ИЗОЛЯЦИЯ ОТКАЗА. Каждый вызов модуля обёрнут. Исключение переводит
		// модуль в состояние Faulted и НЕ останавливает систему. Упавший модуль
		// исключается из решения, остальные продолжают работать.
		//
		// 3. ЕДИНСТВЕННАЯ ТОЧКА ОРДЕРОВ. Вызовы EnterLong, EnterShort, ExitLong,
		// ExitShort и SetStopLoss встречаются ровно в одном классе —
		// SwExecutionModule. Ни ядро, ни прочие модули их не содержат.
		//
		// ЧЕГО ПЛАТФОРМА НЕ ПОЗВОЛЯЕТ, И ЭТО УЧТЕНО В АРХИТЕКТУРЕ.
		// - AddDataSeries работает только в State.Configure: пул серий объявляется
		// заранее и зеркалируется, подключённый позже модуль свои серии добавить
		// не может;
		// - свойства окна параметров статичны: настройки слотов объявлены заранее
		// блоками, динамического добавления нет;
		// - partial class — это компиляция, не рантайм: подключение означает
		// включение заранее скомпилированного слота, а не загрузку кода на лету.
		// ============================================================================
		
		namespace NinjaTrader.NinjaScript
		{
		// Перечисления объявлены в РОДИТЕЛЬСКОМ пространстве имён намеренно:
		// сгенерированные обёртки лежат в Indicators, MarketAnalyzerColumns и
		// Strategies, и объявление внутри одного из них даёт CS0246.
		
		/// <summary>Роль модуля в конвейере решения.</summary>
		public enum SwRole
		{
		Signal, // порождает кандидата направления
		Filter, // накладывает вето
		Sizing, // определяет объём
		Escort, // сопровождение открытой позиции
		Exit // требование закрытия
		}
		
		/// <summary>Состояние здоровья модуля.</summary>
		public enum SwHealth
		{
		Disabled, // выключен настройкой
		NotAttached, // не создан
		Warmup, // прогревается
		Ok, // работает и отдаёт сигналы
		Silent, // не отдаёт сигнал дольше допустимого
		Stale, // отдаёт сигнал со старым номером бара
		Faulted // бросил исключение
		}
		
		/// <summary>Что требует модуль сопровождения или выхода.</summary>
		public enum SwActionKind
		{
		None,
		MoveStop,
		PartialExit,
		FullExit
		}
		
		/// <summary>Вердикт фильтра.</summary>
		public enum SwVerdict
		{
		Neutral,
		Agree,
		Veto
		}
		}
		
		namespace NinjaTrader.NinjaScript.Strategies
		{
		#region Контракты обмена
		
		/// <summary>
		/// ЕДИНСТВЕННЫЙ тип обмена «модуль → коммутатор» для ролей Signal и Filter.
		/// Модуль обязан заполнить ProducedAtBar: по нему обнаруживается застой.
		/// </summary>
		public struct SwSignal
		{
		public string SignalId;          // идентификатор сигнала для журнала (Pac, Kalman, Lever)
		public string ShortDescription;  // краткое описание для журнала
		public int Direction; // +1 long, 0 нет, -1 short
		public double Confidence; // 0..1, субъективная шкала модуля
		public SwVerdict Verdict; // для роли Filter
		public bool IsReady; // прогрев завершён
		public int ProducedAtBar; // номер бара ИСПОЛНЯЮЩЕЙ серии
		public string Text; // короткая диагностика
		
		/// <summary>
		/// Уровень отложенного стоп-входа. Ноль или NaN — вход по рынку.
		/// Положительное значение — исполнитель выставляет стоп-ордер на этот
		/// уровень ДО пробоя, и вход происходит в момент касания, без задержки
		/// до закрытия бара.
		/// </summary>
		public double EntryStopPrice;
		
		/// <summary>Трейлинг этой сделки в тиках. Ноль или NaN — общий [P05].</summary>
		public double TrailTicksOverride;
		
		public static SwSignal Empty(int bar)
		{
		SwSignal s = new SwSignal();
		s.Direction = 0; s.Confidence = 0; s.Verdict = SwVerdict.Neutral;
		s.IsReady = false; s.ProducedAtBar = bar; s.Text = "нет данных";
		s.EntryStopPrice = double.NaN; s.TrailTicksOverride = double.NaN;
		return s;
		}
		}
		
		/// <summary>Требование модуля Escort или Exit. Ордер НЕ создаёт.</summary>
		public struct SwAction
		{
		public string Source;   // источник требования: "FIN" и т. п.
		public string Code;     // код причины: "STEP", код источника стопа
		public SwActionKind Kind;
		public double Price; // уровень стопа для MoveStop
		public int Quantity; // объём для PartialExit
		public int ProducedAtBar;
		public string Reason;
		public string Tag; // метка ступени: по ней исполнение опознаётся
		
		public static SwAction None(int bar)
		{
		SwAction a = new SwAction();
		a.Kind = SwActionKind.None; a.Price = double.NaN;
		a.Quantity = 0; a.ProducedAtBar = bar; a.Reason = string.Empty; a.Tag = string.Empty;
		return a;
		}
		}
		
		/// <summary>Запись трассировки. Кольцевой буфер фиксированного размера.</summary>
		public sealed class SwTraceEntry
		{
		public int Bar;
		public DateTime Time;
		public string Module;
		public string Event;
		public string Detail;
		}
		
		#endregion
		
		#region Базовый класс модуля
		
		/// <summary>
		/// БАЗОВЫЙ КЛАСС ПОДКЛЮЧАЕМОГО МОДУЛЯ.
		///
		/// Наследник обязан переопределить Compute. Всё остальное — учёт,
		/// здоровье, изоляция отказа — берёт на себя коммутатор.
		///
		/// ЖЁСТКОЕ ПРАВИЛО. Модуль не имеет доступа к ордерному API. Поле Host
		/// объявлено как SwHostView — урезанное представление коммутатора,
		/// через которое видны только бары, время и параметры. Вызвать EnterLong
		/// из модуля невозможно физически, а не по договорённости.
		/// </summary>
		public abstract class SwModule
		{
		public string Id = "unnamed";
		public SwRole Role = SwRole.Signal;
		public SwHealth Health = SwHealth.NotAttached;
		
		protected SwHostView Host;
		
		// --- двусторонний учёт ---
		private readonly Queue<SwSignal> outboxSignal = new Queue<SwSignal>();
		private readonly Queue<SwAction> outboxAction = new Queue<SwAction>();
		
		public long EmitCount; // сколько модуль ОТПРАВИЛ
		public long CollectCount; // сколько коммутатор ПРИНЯЛ
		public long LostCount; // расхождение, накопленное
		public long FaultCount;
		public int LastEmitBar = -1;
		public string LastFaultText = string.Empty;
		
		public SwSignal LastSignal;
		public SwAction LastAction;
		
		/// <summary>Однократная привязка. Создание тяжёлых объектов — здесь.</summary>
		public virtual void Attach(SwHostView host)
		{
		Host = host;
		Health = SwHealth.Warmup;
		}
		
		/// <summary>
		/// Единственный метод, который обязан реализовать наследник.
		/// Результат НЕ возвращается, а кладётся в ящик вызовом Emit.
		/// Так коммутатор способен отличить «модуль промолчал» от
		/// «модуль отдал, но до коммутатора не дошло».
		/// </summary>
		public abstract void Compute(int barsInProgress);
		
		/// <summary>Отправка сигнала. Только этот путь считается отправкой.</summary>
		/// <summary>Событие визуального слоя. Этап 0: принимается коммутатором без отрисовки.</summary>
		/// <summary>Телеметрия модуля для пульта: JSON-объект или null. Вызывается, только когда пульт подключён.</summary>
		public virtual string TelemetryJson(System.Globalization.CultureInfo inv) { return null; }

		protected void EmitVisual(SwVisualEvent e)
		{
			if (Host != null) Host.AcceptVisual(Id, e);
		}

		protected void Emit(SwSignal s)
		{
		outboxSignal.Enqueue(s);
		EmitCount++;
		LastEmitBar = s.ProducedAtBar;
		}
		
		/// <summary>Отправка требования. Только этот путь считается отправкой.</summary>
		protected void Emit(SwAction a)
		{
		outboxAction.Enqueue(a);
		EmitCount++;
		LastEmitBar = a.ProducedAtBar;
		}
		
		/// <summary>Разбор ящика коммутатором. Возвращает число принятых.</summary>
		public int DrainSignals(List<SwSignal> into)
		{
		int c = 0;
		while (outboxSignal.Count > 0)
		{
		SwSignal s = outboxSignal.Dequeue();
		into.Add(s);
		LastSignal = s;
		CollectCount++; c++;
		}
		return c;
		}
		
		public int DrainActions(List<SwAction> into)
		{
		int c = 0;
		while (outboxAction.Count > 0)
		{
		SwAction a = outboxAction.Dequeue();
		into.Add(a);
		LastAction = a;
		CollectCount++; c++;
		}
		return c;
		}
		
		public int PendingInOutbox { get { return outboxSignal.Count + outboxAction.Count; } }
		
		public void MarkFault(string text)
		{
		Health = SwHealth.Faulted;
		FaultCount++;
		LastFaultText = text ?? "без текста";
		}
		}
		
		/// <summary>
		/// УРЕЗАННОЕ ПРЕДСТАВЛЕНИЕ КОММУТАТОРА ДЛЯ МОДУЛЯ.
		///
		/// Содержит только то, что модулю нужно для вычисления. Ордерного API
		/// здесь нет и не появится: это и есть техническая гарантия того, что
		/// модуль не выставит заявку в обход исполнителя.
		/// </summary>
		public sealed class SwHostView
		{
		private readonly DZ_SW_Hub_S021 hub;
		internal SwHostView(DZ_SW_Hub_S021 h) { hub = h; }
		public double MinConfidence { get { return hub.MinConfidence; } }

		// --- визуальный слой, журнал сигналов, каналы (этап 0: приём без отрисовки) ---
		public bool VisualOn(SwVisualRole role) { return hub.VisualsEnabled; }
		public bool VisualDebugOn { get { return hub.VisualsEnabled && hub.VisualDebugEnabled; } }
		internal void AcceptVisual(string moduleId, SwVisualEvent e) { hub.HubVisual(moduleId, e); }
		public void RequestSignalJournalEntry(string moduleId, DateTime time, string signalId, int direction,
			double confidence, string description, string reason)
		{
			Trace(moduleId, "SIGNAL_JOURNAL", time.ToString("yyyy-MM-dd HH:mm") + " " + signalId + " " + direction
				+ " " + confidence.ToString("F2") + " " + description + " | " + reason);
		}
		public void SetChannelPlot(int track, int line, double value, int variant) { hub.HubChannelPlot(track, line, value, variant); }
		
		public int CurrentBar { get { return hub.HubCurrentBar; } }
		public int ExecBip { get { return hub.HubExecBip; } }
		public DateTime Time { get { return hub.HubTime; } }
		public double TickSize { get { return hub.HubTickSize; } }
		
		public double Close(int barsAgo) { return hub.HubClose(barsAgo); }
		public double Open(int barsAgo) { return hub.HubOpen(barsAgo); }
		public double High(int barsAgo) { return hub.HubHigh(barsAgo); }
		public double Low(int barsAgo) { return hub.HubLow(barsAgo); }
		
		// --- доступ к произвольной серии пула ---
		//
		// Модуль, работающий на собственном таймфрейме, обязан получать
		// значения ТОЛЬКО через эти методы. Прямого доступа к BarsArray у него
		// нет: иначе он смог бы обойти проверку готовности и прочитать бар,
		// которого ещё не существует.
		
		/// <summary>Номер BarsInProgress слота. 0 — серия графика.</summary>
		public int Bip(int slot) { return hub.ResolveSlot(slot); }
		
		/// <summary>Загружена ли серия слота.</summary>
		public bool SlotLoaded(int slot) { return hub.IsSlotLoaded(slot); }
		
		/// <summary>Номер текущего бара серии слота. Минус один — данных нет.</summary>
		public int BarOf(int slot) { return hub.HubBarOf(slot); }
		
		/// <summary>Готовность серии слота: есть ли нужное число баров.</summary>
		public bool SlotReady(int slot, int needBars) { return hub.HubSlotReady(slot, needBars); }
		
		public double CloseOf(int slot, int barsAgo) { return hub.HubValueOf(slot, barsAgo, 0); }
		public double OpenOf(int slot, int barsAgo) { return hub.HubValueOf(slot, barsAgo, 1); }
		public double HighOf(int slot, int barsAgo) { return hub.HubValueOf(slot, barsAgo, 2); }
		public double LowOf(int slot, int barsAgo) { return hub.HubValueOf(slot, barsAgo, 3); }
		public double VolumeOf(int slot, int barsAgo) { return hub.HubValueOf(slot, barsAgo, 4); }
		public DateTime TimeOf(int slot, int barsAgo) { return hub.HubTimeOf(slot, barsAgo); }
		
		/// <summary>Закрылся ли на этом такте бар слота. Для модулей на старших ТФ.</summary>
		public bool IsBarCloseOf(int slot, int currentBip) { return hub.ResolveSlot(slot) == currentBip; }
		
		/// <summary>Текущее направление позиции: +1, 0, -1. Только чтение.</summary>
		public int PositionSide { get { return hub.HubPositionSide; } }
		public int PositionQuantity { get { return hub.HubPositionQty; } }
		public double PositionAvgPrice { get { return hub.HubPositionAvg; } }
		
		/// <summary>Запись в общую трассировку из модуля.</summary>
		/// <summary>Реализованный результат стратегии. Только чтение.</summary>
		public double RealizedPnl { get { return hub.HubRealizedPnl; } }
		
		/// <summary>Число завершённых сделок. В режиме без ордеров ноль.</summary>
		public int RealizedTradeCount { get { return hub.HubRealizedTradeCount; } }
		
		/// <summary>Первый бар новой торговой сессии по шаблону торговых часов.</summary>
		public bool IsFirstBarOfSession { get { return hub.HubIsFirstBarOfSession; } }
		
		/// <summary>Стоимость одного тика одного контракта.</summary>
		public double TickValue { get { return hub.HubTickSize * hub.HubPointValue; } }
		
		public void Trace(string moduleId, string ev, string detail)
		{
		hub.HubTrace(moduleId, ev, detail);
		}
		}
		
		#endregion
		
		#region Демонстрационные модули
		
		/// <summary>
		/// ОБРАЗЕЦ МОДУЛЯ РОЛИ Signal. Пересечение двух скользящих средних,
		/// посчитанных вручную: сторонних индикаторов модуль не создаёт, чтобы
		/// образец оставался самодостаточным.
		/// </summary>
		public class SwDemoSignalModule : SwModule
		{
		private readonly int fast, slow;
		
		public SwDemoSignalModule(string id, int fastLen, int slowLen)
		{
		Id = id; Role = SwRole.Signal;
		fast = Math.Max(2, fastLen); slow = Math.Max(3, slowLen);
		}
		
		public override void Compute(int bip)
		{
		if (bip != Host.ExecBip) return;
		
		int bar = Host.CurrentBar;
		if (bar < slow + 2)
		{
		Health = SwHealth.Warmup;
		Emit(SwSignal.Empty(bar));
		return;
		}
		
		double f = 0, s = 0;
		for (int i = 0; i < fast; i++) f += Host.Close(i);
		for (int i = 0; i < slow; i++) s += Host.Close(i);
		f /= fast; s /= slow;
		
		SwSignal sig = new SwSignal();
		sig.IsReady = true;
		sig.ProducedAtBar = bar;
		sig.Direction = f > s ? 1 : f < s ? -1 : 0;
		sig.Confidence = Math.Min(1.0, Math.Abs(f - s) / Math.Max(Host.TickSize, 1e-9) / 20.0);
		sig.Text = "MA " + fast + "/" + slow + " " + (sig.Direction > 0 ? "up" : sig.Direction < 0 ? "dn" : "flat");
		
		Health = SwHealth.Ok;
		Emit(sig);
		}
		}
		
		/// <summary>ОБРАЗЕЦ МОДУЛЯ РОЛИ Filter. Запрещает вход против длинного окна.</summary>
		public class SwDemoFilterModule : SwModule
		{
		private readonly int lookback;
		
		public SwDemoFilterModule(string id, int lb)
		{
		Id = id; Role = SwRole.Filter; lookback = Math.Max(5, lb);
		}
		
		public override void Compute(int bip)
		{
		if (bip != Host.ExecBip) return;
		
		int bar = Host.CurrentBar;
		if (bar < lookback + 2)
		{
		Health = SwHealth.Warmup;
		Emit(SwSignal.Empty(bar));
		return;
		}
		
		double now = Host.Close(0), then = Host.Close(lookback);
		
		SwSignal sig = new SwSignal();
		sig.IsReady = true;
		sig.ProducedAtBar = bar;
		sig.Direction = now > then ? 1 : now < then ? -1 : 0;
		sig.Verdict = sig.Direction == 0 ? SwVerdict.Neutral : SwVerdict.Agree;
		sig.Confidence = 1.0;
		sig.Text = "тренд " + lookback + " баров " + (sig.Direction > 0 ? "вверх" : sig.Direction < 0 ? "вниз" : "плоско");
		
		Health = SwHealth.Ok;
		Emit(sig);
		}
		}
		
		#endregion
		
		public class DZ_SW_Hub_S021 : Strategy
		

    {
        private const string HubVersion = "DZ_SW_Hub_S021-v1.0 (2026-09-19)";
        private const string PanelTag = "DZ_SW_HUB_PANEL";

        #region Состояние ядра

        private readonly List<SwModule> modules = new List<SwModule>();
        private SwHostView hostView;

        private readonly List<SwSignal> bufSignals = new List<SwSignal>();
        private readonly List<SwSignal> bufFilters = new List<SwSignal>();
        private readonly List<SwAction> bufActions = new List<SwAction>();

        // Сток для сигналов модулей, чья роль не голосует и не накладывает вето.
        // Они разбираются, чтобы счётчики отправленного и принятого сходились,
        // но в решение не попадают.
        private readonly List<SwSignal> bufIgnored = new List<SwSignal>();

        private readonly List<SwTraceEntry> trace = new List<SwTraceEntry>();

        private SwExecutionModule exec;
        private SwFinancialManager fin;

        // Типизированные ссылки на модули: нужны только панели, чтобы
        // показывать их собственные строки состояния. Логика через них
        // не идёт — она идёт через общий список modules.
        private SwPacStructureModule refPac;
        private SwTrfpVoteModule refTrfp;
        private SwTimeWindowModule refTime;
        private SwRegimeModule refRegime;
        private SwAdaptiveStopModule refAStop;
        private SwEscortLineExitModule refEscort;
        private SwRiskGuardModule refGuard;
        private SwDualBreakoutModule refDbo;
        private SwAdaptiveKernelModule refKer;
        private SwLorentzianModule refLor;
        private SwHurstKernelModule refHk;
        private SwFileSignalModule refFs;
        private SwKalmanChannelModule refKal;
        private SwLeverModule refLev;
        private SwHierarchicalMassModule refHm;
        private SwFinancialConfig finCfg;

        private int execBip;

        // Индексы BarsInProgress для четырёх слотов пула. Ноль означает,
        // что слот выключен и обращение к нему уводится на серию графика.
        private readonly int[] seriesBip = new int[4];

        /// <summary>Номер BarsInProgress по номеру слота: 0 — график, 1..4 — пул.</summary>
        internal int ResolveSlot(int slot)
        {
            if (slot < 1 || slot > 4) return 0;
            return seriesBip[slot - 1];
        }

        /// <summary>Загружена ли серия слота. Выключенный слот уводится на график.</summary>
        internal bool IsSlotLoaded(int slot)
        {
            return slot >= 1 && slot <= 4 && seriesBip[slot - 1] > 0;
        }

        // ВИРТУАЛЬНАЯ ПОЗИЦИЯ РЕЖИМА БЕЗ ОРДЕРОВ.
        //
        // Без неё цепочка обрывается: заявки не отправляются, значит
        // OnExecutionUpdate не вызывается, значит финансовый модуль не узнаёт
        // о входе и молчит. Режим без ордеров — рекомендованный первый шаг
        // проверки, и он обязан прогонять весь конвейер целиком, иначе
        // проверяется не система, а её обрубок.
        private int virtSide;
        private int virtQty;
        private double virtAvg;
        private double virtStop = double.NaN;

        // Реализованный результат виртуальных сделок. Нужен риск-модулю:
        // без него дневные лимиты в режиме без ордеров не проверялись бы,
        // и главная защита осталась бы непротестированной.
        private double virtRealizedPnl;

        // Трейлинг, заданный сигналом для следующей сделки. Финансовый модуль
        // забирает его при открытии сделки.
        internal double HubPendingTrailOverride = double.NaN;

        // Виртуальный отложенный стоп-вход. Выставляется на баре t и
        // проверяется на баре t+1: ордер, поставленный по закрытию бара,
        // работает в течение следующего. Проверка на том же баре t была бы
        // заглядыванием: этот бар уже известен целиком.
        private int virtEntryDir;
        private double virtEntryStop = double.NaN;
        private int virtEntryQty;
        private int virtEntryArmedBar = -1;
        private int decisionsMade, entriesRequested, entriesBlocked, lossesDetected;
        private string lastDecisionText = "—";

        #endregion

        #region Доступ для SwHostView

        internal int HubCurrentBar { get { return CurrentBars[execBip]; } }
        internal int HubExecBip { get { return execBip; } }
        internal DateTime HubTime { get { return Times[execBip][0]; } }
        internal double HubTickSize { get { return TickSize; } }
        internal double HubClose(int b) { return Closes[execBip][b]; }

        internal int HubBarOf(int slot)
        {
            int bip = ResolveSlot(slot);
            try { return CurrentBars[bip]; } catch { return -1; }
        }

        /// <summary>
        /// Готовность серии. Проверка обязательна ДО обращения к барам:
        /// руководство NinjaTrader прямо требует сверять CurrentBars[] перед
        /// доступом к series[barsAgo], иначе возможно обращение к
        /// несуществующему бару.
        /// </summary>
        internal bool HubSlotReady(int slot, int needBars)
        {
            int bip = ResolveSlot(slot);
            try { return CurrentBars[bip] >= Math.Max(0, needBars); } catch { return false; }
        }

        /// <summary>Значение серии слота. kind: 0 close, 1 open, 2 high, 3 low.</summary>
        internal double HubValueOf(int slot, int barsAgo, int kind)
        {
            int bip = ResolveSlot(slot);
            try
            {
                if (CurrentBars[bip] < barsAgo) return double.NaN;
                switch (kind)
                {
                    case 1: return Opens[bip][barsAgo];
                    case 2: return Highs[bip][barsAgo];
                    case 3: return Lows[bip][barsAgo];
                    case 4: return Volumes[bip][barsAgo];
                    default: return Closes[bip][barsAgo];
                }
            }
            catch { return double.NaN; }
        }

        internal DateTime HubTimeOf(int slot, int barsAgo)
        {
            int bip = ResolveSlot(slot);
            try
            {
                if (CurrentBars[bip] < barsAgo) return DateTime.MinValue;
                return Times[bip][barsAgo];
            }
            catch { return DateTime.MinValue; }
        }
        internal double HubOpen(int b) { return Opens[execBip][b]; }
        internal double HubHigh(int b) { return Highs[execBip][b]; }
        internal double HubLow(int b) { return Lows[execBip][b]; }

        internal int HubPositionSide
        {
            get
            {
                if (DryRunMode) return virtSide;
                if (Position == null) return 0;
                return Position.MarketPosition == MarketPosition.Long ? 1
                     : Position.MarketPosition == MarketPosition.Short ? -1 : 0;
            }
        }
        internal int HubPositionQty
        {
            get { return DryRunMode ? virtQty : (Position == null ? 0 : Position.Quantity); }
        }
        internal double HubPositionAvg
        {
            get { return DryRunMode ? virtAvg : (Position == null ? 0 : Position.AveragePrice); }
        }

        /// <summary>Открытие виртуальной позиции исполнителем.</summary>
        internal void HubVirtualOpen(int dir, int qty, double price, int bar)
        {
            virtSide = dir; virtQty = qty; virtAvg = price; virtStop = double.NaN;
            if (fin != null) fin.OnTradeOpened(dir, price, qty, bar);
        }

        /// <summary>Виртуальная частичная фиксация с немедленным подтверждением.</summary>
        internal void HubVirtualPartial(int stepNumber, int qty, double price)
        {
            if (virtSide == 0) return;
            virtRealizedPnl += (virtSide > 0 ? price - virtAvg : virtAvg - price)
                             * qty * HubPointValue;
            virtQty = Math.Max(0, virtQty - qty);
            if (fin != null && stepNumber > 0) fin.OnStepExecution(stepNumber, price, qty);
            if (virtQty == 0) HubVirtualClose("ступень закрыла остаток", price);
        }

        internal void HubVirtualSetStop(double price) { virtStop = price; }

        /// <summary>
        /// Закрытие виртуальной позиции по ЯВНО переданной цене.
        ///
        /// Прежде любое закрытие оценивалось по уровню стопа — в том числе
        /// полный выход по требованию модуля и закрытие остатка ступенью.
        /// Для длинной позиции стоп ниже рынка, и каждый такой выход занижал
        /// результат прогона. Цену знает только вызывающий: стоп — уровень
        /// стопа, выход по требованию — рынок, ступень — цену ступени.
        /// </summary>
        internal void HubVirtualClose(string why, double exitPx)
        {
            if (virtSide == 0) return;
            if (double.IsNaN(exitPx) || exitPx <= 0) exitPx = Closes[execBip][0];
            virtRealizedPnl += (virtSide > 0 ? exitPx - virtAvg : virtAvg - exitPx)
                             * virtQty * HubPointValue;
            HubTrace("EXEC", "DRY_CLOSED", why + ", было " + virtQty + " конт.");
            virtSide = 0; virtQty = 0; virtAvg = 0; virtStop = double.NaN;
            if (fin != null) fin.OnTradeClosed();
        }

        /// <summary>
        /// Срабатывание виртуального стопа. Проверяется по экстремумам бара:
        /// закрытие оставило бы стоп неисполненным на проколах и завысило бы
        /// результат прогона.
        /// </summary>
        internal void HubVirtualArmEntry(int dir, int qty, double stopPx, int bar)
        {
            virtEntryDir = dir; virtEntryQty = qty; virtEntryStop = stopPx; virtEntryArmedBar = bar;
        }

        /// <summary>
        /// Исполнение виртуального стоп-входа на баре после выставления.
        ///
        /// ПОРЯДОК СОБЫТИЙ ВНУТРИ БАРА ПРИНИМАЕТСЯ ПЕССИМИСТИЧНЫМ. Если бар
        /// одновременно достиг уровня входа и стартового стопа, по OHLC нельзя
        /// узнать, что было раньше. Принимается худшее: вход, затем стоп.
        /// Именно выгодный выбор порядка внутри минутного бара — наиболее
        /// вероятная причина неправдоподобных 93% прибыльных сделок в
        /// исследовании, на котором построен модуль пробоя. Режим без ордеров
        /// не повторяет эту ошибку.
        /// </summary>
        private void CheckVirtualEntry()
        {
            if (!DryRunMode || virtEntryArmedBar < 0 || virtSide != 0) return;

            int bar = CurrentBars[execBip];
            if (bar != virtEntryArmedBar + 1)
            {
                // Ордер не был подтверждён сигналом на прошлом баре — снят.
                if (bar > virtEntryArmedBar + 1) virtEntryArmedBar = -1;
                return;
            }

            double hi = Highs[execBip][0], lo = Lows[execBip][0], op = Opens[execBip][0];
            bool touched = virtEntryDir > 0 ? hi >= virtEntryStop : lo <= virtEntryStop;
            if (!touched) return;

            // Разрыв через уровень: исполнение по открытию, хуже уровня.
            double fill = virtEntryStop;
            if (virtEntryDir > 0 && op > virtEntryStop) fill = op;
            if (virtEntryDir < 0 && op < virtEntryStop) fill = op;

            virtEntryArmedBar = -1;

            double stopDist = HubInitialStopTicks * TickSize;
            double stopPx = HubRoundTick(virtEntryDir > 0 ? fill - stopDist : fill + stopDist);

            HubVirtualOpen(virtEntryDir, virtEntryQty, fill, bar);
            HubVirtualSetStop(stopPx);
            if (exec != null) exec.OnVirtualStopEntryFilled(virtEntryDir, stopPx, bar);
            HubTrace("EXEC", "DRY_STOP_ENTRY_FILLED", (virtEntryDir > 0 ? "LONG" : "SHORT")
                + " @ " + fill.ToString("F2") + (fill != virtEntryStop ? " (разрыв)" : "")
                + ", стоп " + stopPx.ToString("F2"));

            // Пессимизм: если тот же бар дошёл и до стопа — позиция выбита.
            bool stopSameBar = virtEntryDir > 0 ? lo <= stopPx : hi >= stopPx;
            if (stopSameBar)
                HubVirtualClose("стоп на баре входа — принят худший порядок событий внутри бара", stopPx);
        }

        private void CheckVirtualStop()
        {
            if (!DryRunMode || virtSide == 0 || double.IsNaN(virtStop)) return;

            bool hit = virtSide > 0 ? Lows[execBip][0] <= virtStop
                                    : Highs[execBip][0] >= virtStop;
            if (!hit) return;

            // РАЗРЫВ ЧЕРЕЗ СТОП. Если бар открылся уже за стопом, реальное
            // исполнение произошло бы по открытию, а не по уровню стопа.
            // Оценка по уровню стопа на разрыве завысила бы результат.
            double open = Opens[execBip][0];
            double fill = virtStop;
            if (virtSide > 0 && open < virtStop) fill = open;
            if (virtSide < 0 && open > virtStop) fill = open;

            HubVirtualClose("виртуальный стоп " + virtStop.ToString("F2")
                + (fill != virtStop ? ", разрыв, исполнение по открытию " + fill.ToString("F2") : ""),
                fill);
        }

        internal void HubTrace(string module, string ev, string detail)
        {
            if (!EnableTracing) return;

            SwTraceEntry e = new SwTraceEntry();
            e.Bar = CurrentBars[execBip];
            try { e.Time = Times[execBip][0]; } catch { e.Time = DateTime.MinValue; }
            e.Module = module; e.Event = ev; e.Detail = detail;

            trace.Add(e);
            while (trace.Count > Math.Max(10, TraceBufferSize)) trace.RemoveAt(0);

            if (PrintTraceToOutput)
                Print("[HUB] бар " + e.Bar + "  " + module + "  " + ev
                    + (string.IsNullOrEmpty(detail) ? "" : "  | " + detail));
        }

        #endregion

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "DZ_SW_Hub_S021";
                Description = "Коммутатор торговой системы. Подключаемые вычислительные модули, "
                            + "трассировка сигналов, обнаружение потерь, единственная точка ордеров.";

                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 30;
                BarsRequiredToTrade = 20;
                IsInstantiatedOnEachOptimizationIteration = false;

                // --- слоты ---
                Slot1Enabled = true;
                Slot2Enabled = true;
                Slot3Enabled = true;
                Slot4Enabled = false;
                Slot5Enabled = true;
                Slot6Enabled = false;
                Slot7Enabled = false;

                PacLowerSlot = 1; PacHigherSlot = 2; PacUseHigher = true;
                PacInternalStrength = 3; PacSwingStrength = 10;
                PacBreakBy = SwPacBreakBy.BarClose;

                TrfpLine1Slot = 1; TrfpLine2Slot = 2; TrfpLine3Slot = 3;
                TrfpUseLine3 = false; TrfpPeriod = 100; TrfpMultiplier = 3.0;

                RegimeSlot = 1; RegimeWindow = 60; RegimeAllow = SwRegimeAllow.Any;

                GuardDailyLoss = 0; GuardDailyProfit = 0;
                GuardBreachAction = SwGuardBreachAction.BlockNewEntries;
                GuardRestartPolicy = SwGuardRestartPolicy.BlockUntilNextSession;

                AStopSlot = 1; AStopAtrPeriod = 10;
                AStopWidthMode = SwAdaptiveWidth.VolatilityBuckets;
                AStopFixedMultiplier = 3.0;

                EscortLineNumber = 2;
                EscortTrigger = SwEscortExitTrigger.LineFlip;
                EscortConfirmBars = 1;

                // --- решение ---
                RequireAllSignalsAgree = false;
                MinConfidence = 0.0;
                FilterMissingBlocksEntry = false;

                // --- исполнение ---
                DryRunMode = true;
                VisualsEnabled = false;
                VisualDebugEnabled = false;
                WsEnabled = false;
                WsPort = 8088;
                WsAllowCommands = false;
                ExportSchema = false;
                PresetFile = "";
                Slot13Enabled = false; Slot14Enabled = false; Slot15Enabled = false;
                KalRole = SwKalmanRole.Filter; KalLowerSlot = 1; KalCurrentSlot = 0; KalHigherSlot = 3; KalPeriod = 20; KalBandSigma = 2.0; KalPolicy = SwKalmanFilterPolicy.TrendDirection;
                LevRole = SwLeverRole.Filter; LevAnalysisSlot = 0; LevClusterSlot = 1; LevClusters = 10; LevVoteZ = 0.5; LevPolicy = SwLeverPolicy.DirectionOnly;
                HmSlot = 0; HmWindow = 15; HmWeight5 = 1.0; HmWeight15 = 1.5; HmSignalMode = false; HmPercentile = 0.85; HmBiasThreshold = 2.0;
                HmExpSqueeze = false; HmExpSqueezeRatio = 0.6; HmExpPersist = 0;
                DefaultQuantity = 1;
                StopLossTicks = 40;
                MinBarsInTrade = 1;

                // --- управление позицией ---
                EnablePositionManager = true;

                SizingMode = SwSizingMode.FixedQuantity;
                RiskMoneyPerTrade = 0; AccountEquityReference = 0; RiskPercentOfEquity = 0.5;
                MinQuantity = 1; MaxQuantity = 5;
                RoundTurnCostPerContract = 0; SlippageReserveTicks = 2;
                StopMode = SwStopMode.FixedTicks; StopPriceDollars = 0; StopAtrMultiple = 2.0;
                AtrPeriod = 14;
                UseScaleOut = false; ScaleSteps = 2;
                StepDistanceMode = SwStepDistanceMode.RMultiple;
                StepFixedTicks = 40; StepPriceDollars = 0; StepRMultiple = 1.0;
                ContractsOnStep1 = 1; ContractsPerStep = 0; KeepRunner = true;
                BreakevenMode = SwBreakevenMode.Off; BreakevenAtR = 1.0;
                TrailMode = SwTrailMode.Off; TrailActivateAtR = 1.0; TrailAtrMultiple = 2.5;
                BreakevenOffsetTicks = 2;
                DisableStopMoveAfterStep1 = false; MinBarsBetweenStopMoves = 0;
                StepConfirmTimeoutBars = 3;
                TimeForceFlatten = true;

                Slot8Enabled = false;
                DboWindowZone = SwWindowZone.Chicago;
                DboUseMorning = true;
                DboUseEvening = true;
                DboM1Slot = 1; DboM15Slot = 3; DboH4Slot = 4;
                DboMorningBaseStart = 60000; DboMorningBaseEnd = 65959;
                DboMorningSignalStart = 70000; DboMorningSignalEnd = 95959;
                DboMorningSessionEnd = 143000; DboMorningTrailTicks = 15;
                DboEveningBaseStart = 170000; DboEveningBaseEnd = 175959;
                DboEveningSignalStart = 180000; DboEveningSignalEnd = 195959;
                DboEveningSessionEnd = 213000; DboEveningTrailTicks = 10;
                DboMinRangeTicks = 15; DboMaxRangeTicks = 45; DboMinBaseBars = 50;
                DboFlatThreshold = 0.85; DboAtrFast = 20; DboAtrSlow = 40; DboTrendBars = 10;
                DboEntryOffsetTicks = 1; DboMaxEntries = 0;
                DboEveningDir = SwEveningDir.DayTrend; DboCloseAtSessionEnd = true;
                BreakevenOnBestPrice = true;

                Slot9Enabled = false;
                KerKernel = SwKernelType.Epanechnikov; KerRegression = SwRegressionType.LocalLinear;
                KerSlot = 1; KerBandwidth = 20; KerAdaptive = true;
                KerVolumeWeighting = false; KerVolumeGamma = 1.0;
                KerVolumeScale = SwVolumeScale.Robust; KerVolumeWindow = 50;
                KerSlopeThreshold = 0.5; KerDivergence = SwKernelDivergenceAction.Neutral;
                KerExpTGate = false; KerExpTMin = 2.0; KerExpFastSlow = false; KerExpSkill = false;
                KerSignalMode = false;

                Slot11Enabled = false;
                LorSlot = 1; LorLookback = 2000; LorNeighbors = 16; LorStride = 4; LorHorizon = 4;
                LorVoteThreshold = 0.5; LorYeoJohnson = true; LorRefitBars = 100; LorFitWindow = 500;
                LorKalmanQ = 0.01; LorKalmanR = 1.0; LorSignalMode = false;
                LorExpKernelVote = false;
                Slot12Enabled = false; FsPath = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "NinjaTrader 8", "dz_export", "dz_signal.csv");
                FsMaxAge = 120; FsMaxLag = 2; FsSignalMode = false; FsMinConfidence = 0.0;
                LorMethod = SwLorentzMethod.KnnVote; LorNwKernel = SwKernelType.Gaussian;
                LorNwBandMult = 0.5; LorNwThreshold = 0.10; LorNwMinEff = 10;
                Slot10Enabled = false; HkSlot = 1; HkRegression = SwRegressionType.LocalLinear; HkKernel = SwKernelType.Epanechnikov;
                HkHurstPeriod = 128; HkMinBandwidth = 8; HkMaxBandwidth = 40; HkHLow = 0.37; HkHHigh = 0.57; HkRwLevel = 0.47;
                HkSlopeThreshold = 0.5; HkSignalMode = false; HkExpGate = false; HkExpGateBand = 0.03; HkExpInverse = false; HkExpConfidence = false; LorExpPrecisionGate = false; LorExpPrecisionMin = 0.65; LorExpAgreeKernel = false;
                BreakevenAfterTicks = 30;
                TrailAfterTicks = 60;
                TrailDistanceTicks = 40;

                // --- диагностика ---
                EnableTracing = true;
                PrintTraceToOutput = false;
                TraceBufferSize = 200;
                SilentAfterBars = 5;
                ShowHubPanel = true;
                PanelPosition = TextPosition.TopLeft;
                PanelFontSize = 11;
                PanelTraceLines = 6;
                UseSeries1 = false; Series1Type = BarsPeriodType.Minute; Series1Value = 1;
                UseSeries2 = false; Series2Type = BarsPeriodType.Minute; Series2Value = 5;
                UseSeries3 = false; Series3Type = BarsPeriodType.Minute; Series3Value = 15;
                UseSeries4 = false; Series4Type = BarsPeriodType.Minute; Series4Value = 60;
                ExecSeriesSlot = 0;

                OkBrush = Brushes.LimeGreen;
                WarnBrush = Brushes.Gold;
                FaultBrush = Brushes.OrangeRed;
                IdleBrush = Brushes.Gray;
            	CaptureSchemaDefaults();   // последней строкой SetDefaults: присвоены все умолчания
            }
            else if (State == State.Configure)
            {
            	ApplyPreset();                       // до объявления серий: и серии берутся из пресета
            	if (ExportSchema) ExportMenuSchema();
                // Пул серий объявляется здесь и только здесь. Подключённый
                // позже модуль свои серии добавить не может — ограничение
                // платформы, а не выбор архитектуры.
                // ПУЛ СЕРИЙ. Объявляется здесь и только здесь: AddDataSeries
                // работает исключительно в State.Configure. Модуль, подключённый
                // позже, свою серию добавить не может — ограничение платформы.
                //
                // Порядок объявления ФИКСИРУЕТ индексы. Менять порядок нельзя:
                // модули обращаются к сериям по номеру слота, и перестановка
                // заставит их читать чужие бары молча, без ошибки.
                int next = 1;
                for (int k = 0; k < 4; k++) seriesBip[k] = 0;

                if (UseSeries1) { AddDataSeries(Series1Type, Series1Value); seriesBip[0] = next++; }
                if (UseSeries2) { AddDataSeries(Series2Type, Series2Value); seriesBip[1] = next++; }
                if (UseSeries3) { AddDataSeries(Series3Type, Series3Value); seriesBip[2] = next++; }
                if (UseSeries4) { AddDataSeries(Series4Type, Series4Value); seriesBip[3] = next++; }

                // Серия исполнения: 0 — график, 1..4 — слоты пула.
                execBip = ResolveSlot(ExecSeriesSlot);
            }
            else if (State == State.DataLoaded)
            {
                hostView = new SwHostView(this);

                // ATR создаётся здесь, не в горячем пути. Нужен только режимам
                // стопа и трейлинга, опирающимся на волатильность.
                try { hubAtr = ATR(BarsArray[execBip], Math.Max(2, AtrPeriod)); }
                catch { hubAtr = null; }

                exec = new SwExecutionModule(this);

                finCfg = BuildFinancialConfig();
                fin = new SwFinancialManager(this, finCfg);

                int minBe = fin.MinimumBreakevenOffsetTicks();
                if (finCfg.BreakevenMode != SwBreakevenMode.Off
                    && finCfg.BreakevenOffsetTicks < minBe)
                    Print("[HUB-ВНИМАНИЕ] [F32] отступ безубытка " + finCfg.BreakevenOffsetTicks
                        + " тиков не покрывает издержки круга: нужно не меньше " + minBe
                        + ". Срабатывание безубыточного стопа даст убыток.");

                BuildSlots();

                foreach (SwModule m in modules)
                {
                    try { m.Attach(hostView); }
                    catch (Exception ex) { m.MarkFault(ex.Message); }
                }

                ValidateSlotReferences();

                HubTrace("HUB", "ATTACHED", modules.Count + " модулей, execBip=" + execBip);
                Print("[HUB] " + HubVersion + "  модулей " + modules.Count
                    + "  серия исполнения bip=" + execBip
                    + "  режим " + (DryRunMode ? "БЕЗ ОРДЕРОВ" : "БОЕВОЙ"));
            }
            else if (State == State.Realtime)
            {
            	StartRemote();   // пульт — только в реальном времени
            }
            else if (State == State.Terminated)
            {
            	if (ws != null) { ws.Stop(); ws = null; }
                PrintSummary();
                try { RemoveDrawObject(PanelTag); } catch { }
            }
        }

        /// <summary>
        /// СБОРКА СЛОТОВ. Здесь оркестратор заменяет демонстрационные модули
        /// своими. Ничего, кроме этого метода, для подключения менять не нужно.
        /// </summary>
        private void BuildSlots()
        {
            modules.Clear();
            refPac = null; refTrfp = null; refTime = null;
            refRegime = null; refAStop = null; refEscort = null; refGuard = null; refDbo = null; refKer = null; refLor = null; refHk = null; refFs = null; refKal = null; refLev = null; refHm = null;

            // ================================================================
            //  СБОРКА КОНВЕЙЕРА.
            //
            //  Порядок добавления не влияет на результат: ядро опрашивает все
            //  модули и сводит вердикты. Но порядок влияет на читаемость
            //  панели, поэтому идёт по конвейеру: сигнал, фильтры, риск,
            //  сопровождение, выход.
            //
            //  ЗАВИСИМОСТИ, КОТОРЫЕ НЕЛЬЗЯ НАРУШИТЬ.
            //    выход по линии    требует модуля линий;
            //    риск-модуль       требует модуля времени для новостных пауз.
            //  Оба получают ссылку и сообщают о застое, если зависимость
            //  не опрашивается.
            // ================================================================

            // ---------- СИГНАЛ ----------
            if (Slot1Enabled)
            {
                SwPacConfig pac = new SwPacConfig();
                pac.LowerSlot = PacLowerSlot;
                pac.HigherSlot = PacHigherSlot;
                pac.UseHigherTimeframe = PacUseHigher;
                pac.InternalStrength = PacInternalStrength;
                pac.SwingStrength = PacSwingStrength;
                pac.BreakBy = PacBreakBy;

                refPac = new SwPacStructureModule("SIG-Структура", pac);
                modules.Add(refPac);
            }

            // ---------- СИГНАЛ: пробой диапазона двух сессий ----------
            if (Slot8Enabled)
            {
                SwDualBreakoutConfig dc = new SwDualBreakoutConfig();
                dc.Zone = DboWindowZone;
                dc.Morning.Enabled = DboUseMorning;
                dc.Evening.Enabled = DboUseEvening;
                dc.M1Slot = DboM1Slot;
                dc.M15Slot = DboM15Slot;
                dc.H4Slot = DboH4Slot;

                dc.Morning.BaseStart = DboMorningBaseStart;   dc.Morning.BaseEnd = DboMorningBaseEnd;
                dc.Morning.SignalStart = DboMorningSignalStart; dc.Morning.SignalEnd = DboMorningSignalEnd;
                dc.Morning.SessionEnd = DboMorningSessionEnd; dc.Morning.TrailTicks = DboMorningTrailTicks;
                dc.Evening.BaseStart = DboEveningBaseStart;   dc.Evening.BaseEnd = DboEveningBaseEnd;
                dc.Evening.SignalStart = DboEveningSignalStart; dc.Evening.SignalEnd = DboEveningSignalEnd;
                dc.Evening.SessionEnd = DboEveningSessionEnd; dc.Evening.TrailTicks = DboEveningTrailTicks;

                dc.MinRangeTicks = DboMinRangeTicks; dc.MaxRangeTicks = DboMaxRangeTicks;
                dc.MinBaseBars = DboMinBaseBars; dc.FlatThreshold = DboFlatThreshold;
                dc.AtrFast = DboAtrFast; dc.AtrSlow = DboAtrSlow; dc.TrendBars = DboTrendBars;
                dc.EntryOffsetTicks = DboEntryOffsetTicks; dc.MaxEntriesPerSession = DboMaxEntries;
                dc.EveningDir = DboEveningDir; dc.CloseAtSessionEnd = DboCloseAtSessionEnd;

                // Имя несёт профиль: в журнале и на панели сразу видно, какой счёт это.
                refDbo = new SwDualBreakoutModule("SIG-Пробой-" + DboWindowZone, dc);
                modules.Add(refDbo);
            }

            // ---------- АДАПТИВНОЕ ЯДРО: фильтр либо исследовательский сигнал ----------
            if (Slot9Enabled)
            {
                SwAdaptiveKernelConfig kc = new SwAdaptiveKernelConfig();
                kc.Kernel = KerKernel; kc.Regression = KerRegression; kc.Slot = KerSlot;
                kc.Bandwidth = KerBandwidth; kc.AdaptiveBandwidth = KerAdaptive;
                kc.VolumeWeighting = KerVolumeWeighting; kc.VolumeGamma = KerVolumeGamma;
                kc.VolumeScale = KerVolumeScale; kc.VolumeWindow = KerVolumeWindow;
                kc.SlopeThresholdTicks = KerSlopeThreshold; kc.Divergence = KerDivergence;
                kc.ExpSlopeTGate = KerExpTGate; kc.ExpTMin = KerExpTMin;
                kc.ExpFastSlowCross = KerExpFastSlow; kc.ExpSkillCheck = KerExpSkill;
                kc.SignalMode = KerSignalMode;
                refKer = new SwAdaptiveKernelModule(KerSignalMode ? "SIG-Ядро" : "FLT-Ядро", kc);
                modules.Add(refKer);
            }

            // ---------- СИГНАЛ С ПК ----------
            // ---------- КАНАЛ КАЛМАНА [MOD13], РЫЧАГ СВЕЧИ [MOD14], ИЕРАРХИЧЕСКАЯ МАССА [MOD15] ----------
            if (Slot13Enabled)
            {
            	SwKalmanConfig kalc = new SwKalmanConfig();
            	kalc.Role = KalRole; kalc.LowerSlot = KalLowerSlot; kalc.CurrentSlot = KalCurrentSlot; kalc.HigherSlot = KalHigherSlot;
            	kalc.Period = KalPeriod; kalc.BandSigma = KalBandSigma; kalc.Policy = KalPolicy;
            	refKal = new SwKalmanChannelModule("KAL-Канал", kalc);
            	modules.Add(refKal);
            }
            if (Slot14Enabled)
            {
            	SwLeverConfig levc = new SwLeverConfig();
            	levc.Role = LevRole; levc.AnalysisSlot = LevAnalysisSlot; levc.ClusterSlot = LevClusterSlot;
            	levc.Clusters = LevClusters; levc.VoteZ = LevVoteZ; levc.Policy = LevPolicy;
            	refLev = new SwLeverModule("LEV-Рычаг", levc);
            	modules.Add(refLev);
            }
            if (Slot15Enabled)
            {
            	SwHierarchicalMassConfig hmc = new SwHierarchicalMassConfig();
            	hmc.Slot = HmSlot; hmc.WindowMinutes = HmWindow; hmc.Weight5 = HmWeight5; hmc.Weight15 = HmWeight15;
            	hmc.Percentile = HmPercentile; hmc.BiasThresholdTicks = HmBiasThreshold; hmc.SignalMode = HmSignalMode;
            	hmc.ExpSqueezeGate = HmExpSqueeze; hmc.ExpSqueezeRatio = HmExpSqueezeRatio; hmc.ExpPersistBars = HmExpPersist;
            	refHm = new SwHierarchicalMassModule(HmSignalMode ? "SIG-Масса" : "FLT-Масса", hmc);
            	modules.Add(refHm);
            }

            if (Slot12Enabled)
            {
                SwFileSignalConfig fc = new SwFileSignalConfig();
                fc.Path = FsPath; fc.MaxAgeSeconds = FsMaxAge; fc.MaxLagBars = FsMaxLag;
                fc.SignalMode = FsSignalMode; fc.MinConfidence = FsMinConfidence;
                refFs = new SwFileSignalModule(FsSignalMode ? "SIG-ПК" : "FLT-ПК", fc);
                modules.Add(refFs);
            }

            // ---------- ЯДРО С ШИРИНОЙ ПО ХЁРСТУ ----------
            if (Slot10Enabled)
            {
                SwHurstKernelConfig hc = new SwHurstKernelConfig();
                hc.Slot = HkSlot; hc.Regression = HkRegression; hc.Kernel = HkKernel; hc.HurstPeriod = HkHurstPeriod;
                hc.MinBandwidth = HkMinBandwidth; hc.MaxBandwidth = HkMaxBandwidth; hc.HLow = HkHLow; hc.HHigh = HkHHigh;
                hc.RwLevel = HkRwLevel; hc.SlopeThresholdTicks = HkSlopeThreshold; hc.SignalMode = HkSignalMode;
                hc.ExpRandomWalkGate = HkExpGate; hc.ExpGateBand = HkExpGateBand; hc.ExpInverseMap = HkExpInverse;
                hc.ExpHurstConfidence = HkExpConfidence;
                refHk = new SwHurstKernelModule(HkSignalMode ? "SIG-Хёрст" : "FLT-Хёрст", hc);
                modules.Add(refHk);
            }

            // ---------- КЛАССИФИКАТОР ЛОРЕНЦА: после ядра, чтобы получить ссылку на него ----------
            if (Slot11Enabled)
            {
                SwLorentzianConfig lc = new SwLorentzianConfig();
                lc.Slot = LorSlot; lc.Lookback = LorLookback; lc.Neighbors = LorNeighbors; lc.Stride = LorStride;
                lc.Horizon = LorHorizon; lc.VoteThreshold = LorVoteThreshold; lc.UseYeoJohnson = LorYeoJohnson;
                lc.RefitBars = LorRefitBars; lc.FitWindow = LorFitWindow; lc.KalmanQ = LorKalmanQ; lc.KalmanR = LorKalmanR;
                lc.SignalMode = LorSignalMode; lc.ExpKernelVote = LorExpKernelVote; lc.ExpPrecisionGate = LorExpPrecisionGate;
                lc.ExpPrecisionMin = LorExpPrecisionMin; lc.ExpAgreeKernel = LorExpAgreeKernel;
                lc.Method = LorMethod; lc.NwKernel = LorNwKernel; lc.NwBandMult = LorNwBandMult;
                lc.NwThreshold = LorNwThreshold; lc.NwMinEff = LorNwMinEff;
                refLor = new SwLorentzianModule(LorSignalMode ? "SIG-Лоренц" : "FLT-Лоренц", lc, refKer);
                modules.Add(refLor);
            }

            // ---------- ФИЛЬТРЫ ----------
            if (Slot2Enabled)
            {
                SwTrfpConfig t = new SwTrfpConfig();
                t.Line1.Slot = TrfpLine1Slot; t.Line1.Period = TrfpPeriod; t.Line1.Multiplier = TrfpMultiplier;
                t.Line2.Slot = TrfpLine2Slot; t.Line2.Period = TrfpPeriod; t.Line2.Multiplier = TrfpMultiplier;
                t.Line3.Slot = TrfpLine3Slot; t.Line3.Period = TrfpPeriod; t.Line3.Multiplier = TrfpMultiplier;
                t.Line3.Enabled = TrfpUseLine3;
                t.WarmupBarsPerLine = TrfpPeriod;

                refTrfp = new SwTrfpVoteModule("FLT-Линии", t);
                modules.Add(refTrfp);
            }

            if (Slot3Enabled)
            {
                SwTimeConfig tc = new SwTimeConfig();
                tc.OutsidePolicy = TimeForceFlatten
                    ? SwTimeOutsidePolicy.RequestFlatten
                    : SwTimeOutsidePolicy.BlockNewEntriesOnly;
                refTime = new SwTimeWindowModule("FLT-Время", tc);
                modules.Add(refTime);
            }

            if (Slot4Enabled)
            {
                SwRegimeConfig rc = new SwRegimeConfig();
                rc.Slot = RegimeSlot;
                rc.WindowLength = RegimeWindow;
                rc.Allow = RegimeAllow;

                refRegime = new SwRegimeModule("FLT-Режим", rc);
                modules.Add(refRegime);
            }

            // ---------- РИСК ----------
            if (Slot5Enabled)
            {
                SwGuardConfig gc = new SwGuardConfig();
                gc.DailyLossLimit = GuardDailyLoss;
                gc.DailyProfitLimit = GuardDailyProfit;
                gc.BreachAction = GuardBreachAction;
                gc.RestartPolicy = GuardRestartPolicy;

                // Риск-модуль получает часы: второй независимый расчёт
                // берлинского времени разошёлся бы с первым молча.
                refGuard = new SwRiskGuardModule("RSK-Лимиты", gc, refTime);
                modules.Add(refGuard);
            }

            // ---------- СОПРОВОЖДЕНИЕ ----------
            if (Slot6Enabled)
            {
                SwAdaptiveStopConfig ac = new SwAdaptiveStopConfig();
                ac.Slot = AStopSlot;
                ac.AtrPeriod = AStopAtrPeriod;
                ac.WidthMode = AStopWidthMode;
                ac.FixedMultiplier = AStopFixedMultiplier;

                refAStop = new SwAdaptiveStopModule("ESC-Стоп", ac);
                modules.Add(refAStop);
            }

            // ---------- ВЫХОД ----------
            if (Slot7Enabled)
            {
                if (refTrfp == null)
                {
                    // Зависимость не удовлетворена. Модуль не создаётся вовсе:
                    // создать его и позволить читать пустые значения хуже,
                    // чем честно сообщить о невозможности.
                    Print("[HUB-ВНИМАНИЕ] [S71] выход по линии требует модуля линий [S21]. "
                        + "Слот не подключён.");
                }
                else
                {
                    SwEscortLineConfig ec = new SwEscortLineConfig();
                    ec.LineNumber = EscortLineNumber;
                    ec.Trigger = EscortTrigger;
                    ec.ConfirmBars = EscortConfirmBars;

                    refEscort = new SwEscortLineExitModule("EXT-ЛинияВыход", refTrfp, ec);
                    modules.Add(refEscort);
                }
            }

            foreach (SwModule m in modules)
                if (m.Health == SwHealth.NotAttached) m.Health = SwHealth.Warmup;
        }

        protected override void OnBarUpdate()
        {
            // ---------- 1. Опрос модулей НА КАЖДОЙ СЕРИИ ----------
            //
            // Опрос идёт до проверки серии исполнения намеренно. Модуль на
            // старшем таймфрейме обязан увидеть закрытие СВОЕГО бара, иначе
            // он не сможет обновить состояние вовремя. Какой такт ему нужен,
            // модуль решает сам по аргументу bip: именно для этого он и
            // передаётся.
            foreach (SwModule m in modules)
            {
                if (m.Health == SwHealth.Disabled) continue;

                long before = m.EmitCount;
                try
                {
                    m.Compute(BarsInProgress);
                }
                catch (Exception ex)
                {
                    m.MarkFault(ex.Message);
                    HubTrace(m.Id, "FAULT", ex.GetType().Name + ": " + ex.Message);
                    continue;   // упавший модуль исключён, система работает
                }

                if (BarsInProgress == execBip && m.EmitCount == before && m.Health == SwHealth.Ok)
                    HubTrace(m.Id, "NO_EMIT", "модуль отработал, но ничего не отправил");
            }

            // Разбор ящиков, решение и исполнение — только в такте серии
            // исполнения. Заявки отправляются из одного места и в одном такте.
            if (BarsInProgress != execBip) return;
            if (CurrentBars[execBip] < BarsRequiredToTrade) return;

            int bar = CurrentBars[execBip];

            // ---------- 2. Разбор ящиков и обнаружение потерь ----------
            bufSignals.Clear(); bufFilters.Clear(); bufActions.Clear(); bufIgnored.Clear();

            foreach (SwModule m in modules)
            {
                if (m.Health == SwHealth.Disabled || m.Health == SwHealth.Faulted) continue;

                // Разбираются ОБА ящика любого модуля, независимо от роли.
                //
                // Роль определяет, куда идут СИГНАЛЫ: в голосование либо в вето.
                // Но требование закрыть позицию может прийти от модуля любой
                // роли. Фильтр времени требует закрытия на жёсткой границе дня,
                // риск-модуль — при пробитии дневного лимита. Прежде у фильтров
                // разбирался только ящик сигналов, и их требования застревали
                // навсегда: принудительное закрытие не срабатывало никогда.
                int got = 0;
                if (m.Role == SwRole.Signal) got += m.DrainSignals(bufSignals);
                else if (m.Role == SwRole.Filter) got += m.DrainSignals(bufFilters);
                else got += m.DrainSignals(bufIgnored);   // Escort/Exit/Sizing не голосуют и не вето

                got += m.DrainActions(bufActions);

                // ПОТЕРЯ ПЕРВОГО РОДА: в ящике осталось непринятое.
                if (m.PendingInOutbox > 0)
                {
                    m.LostCount += m.PendingInOutbox;
                    lossesDetected += m.PendingInOutbox;
                    HubTrace(m.Id, "SIGNAL_LOST",
                        "в ящике осталось " + m.PendingInOutbox + " непринятых");
                }

                // ПОТЕРЯ ВТОРОГО РОДА: расхождение счётчиков.
                if (m.EmitCount != m.CollectCount)
                {
                    long diff = m.EmitCount - m.CollectCount;
                    if (diff > m.LostCount)
                    {
                        lossesDetected++;
                        HubTrace(m.Id, "COUNTER_MISMATCH",
                            "отправлено " + m.EmitCount + ", принято " + m.CollectCount);
                    }
                }

                // ЗАСТОЙ: сигнал приходит, но с номером старого бара.
                if (got > 0 && m.LastSignal.ProducedAtBar > 0
                    && m.LastSignal.ProducedAtBar < bar - 1)
                {
                    m.Health = SwHealth.Stale;
                    HubTrace(m.Id, "STALE", "бар сигнала " + m.LastSignal.ProducedAtBar
                        + ", текущий " + bar);
                }

                // МОЛЧАНИЕ: ничего не приходит дольше допустимого.
                if (m.LastEmitBar >= 0 && bar - m.LastEmitBar > Math.Max(1, SilentAfterBars))
                {
                    if (m.Health != SwHealth.Silent)
                    {
                        m.Health = SwHealth.Silent;
                        HubTrace(m.Id, "SILENT", "молчит " + (bar - m.LastEmitBar) + " баров");
                    }
                }
                else if (got > 0 && m.Health == SwHealth.Silent)
                {
                    m.Health = SwHealth.Ok;
                    HubTrace(m.Id, "RECOVERED", "сигналы возобновились");
                }
            }

            ProcessRemote(bar);   // команды пульта: до исполнения требований

            // ---------- 3. Виртуальный стоп и сопровождение ----------
            CheckVirtualEntry();
            CheckVirtualStop();

            if (EnablePositionManager && fin != null)
            {
                try { fin.Evaluate(bar, bufActions); }
                catch (Exception ex) { HubTrace("FIN", "FAULT", ex.Message); }
            }

            // ---------- 4. Исполнение требований ----------
            foreach (SwAction a in bufActions)
            {
                if (a.Kind == SwActionKind.None) continue;
                exec.Handle(a, bar);
            }

            // ---------- 5. Решение о входе ----------
            if (HubPositionSide == 0) EvaluateEntry(bar);

            PublishSnapshot(bar); // снимок пульту: очередь, сеть поток стратегии не держит

            // ---------- 6. Панель ----------
            if (ShowHubPanel) RenderPanel(bar);
        }

        /// <summary>
        /// ПРОВЕРКА ССЫЛОК МОДУЛЕЙ НА СЛОТЫ ПУЛА.
        ///
        /// Невключённый слот молча уводится на серию графика. Без этой
        /// проверки конфигурация по умолчанию — где все слоты пула выключены,
        /// а модули ссылаются на слоты 1, 2 и 3 — дала бы вырожденный расчёт:
        /// младший и старший таймфрейм структуры оказались бы одной серией,
        /// и события старшего дублировали бы события младшего. Ошибки при
        /// этом нет, результат просто неверен.
        /// </summary>
        private void ValidateSlotReferences()
        {
            int problems = 0;

            if (Slot1Enabled)
            {
                problems += CheckSlot("[M01] структура, младший ТФ", PacLowerSlot);
                if (PacUseHigher)
                {
                    problems += CheckSlot("[M02] структура, старший ТФ", PacHigherSlot);
                    if (ResolveSlot(PacLowerSlot) == ResolveSlot(PacHigherSlot))
                    {
                        problems++;
                        Print("[HUB-ВНИМАНИЕ] [M01][M02] младший и старший таймфрейм структуры "
                            + "указывают на ОДНУ серию bip=" + ResolveSlot(PacLowerSlot)
                            + ". События старшего будут дублировать младший. Включите слоты пула "
                            + "[S50]-[S80] либо выключите [M03].");
                    }
                }
            }

            if (Slot2Enabled)
            {
                problems += CheckSlot("[M11] линия 1", TrfpLine1Slot);
                problems += CheckSlot("[M12] линия 2", TrfpLine2Slot);
                if (TrfpUseLine3) problems += CheckSlot("[M13] линия 3", TrfpLine3Slot);
            }

            if (Slot4Enabled) problems += CheckSlot("[M21] режим рынка", RegimeSlot);

            if (Slot8Enabled)
            {
                problems += CheckSlot("[M84] пробой, минутная серия", DboM1Slot);
                problems += CheckSlot("[M85] пробой, серия 15M", DboM15Slot);
                problems += CheckSlot("[M86] пробой, серия 4H", DboH4Slot);

                // У модуля пробоя собственные окна. Фильтр времени с другими
                // окнами молча срезал бы большую часть его входов: при окнах по
                // умолчанию теряется половина утреннего окна сигналов (пауза
                // 08:00–09:30) и три четверти вечернего (запрет входов с 18:30).
                if (Slot3Enabled)
                {
                    problems++;
                    Print("[HUB-ВНИМАНИЕ] [MOD8][MOD3] модуль пробоя работает по собственным окнам, "
                        + "а фильтр времени накладывает свои. Входы вне пересечения окон будут "
                        + "запрещены без явной причины в логике пробоя. Для пробоя выключите [MOD3].");
                }

                // Минутная серия пробоя обязана быть серией исполнения. Иначе на одной
                // метке времени серия исполнения может быть обработана раньше, и ордер
                // встанет на минуту позже — пропуская вход на первой минуте окна.
                if (ResolveSlot(DboM1Slot) != execBip)
                {
                    problems++;
                    Print("[HUB-ВНИМАНИЕ] [M84][S90] минутная серия пробоя (bip=" + ResolveSlot(DboM1Slot)
                        + ") не совпадает с серией исполнения (bip=" + execBip + "). Установите [S90] равным [M84].");
                }

                problems += CheckWindows("[W11]-[W15] утро", DboUseMorning, DboMorningBaseStart, DboMorningBaseEnd,
                                         DboMorningSignalStart, DboMorningSignalEnd, DboMorningSessionEnd);
                problems += CheckWindows("[W21]-[W25] вечер", DboUseEvening, DboEveningBaseStart, DboEveningBaseEnd,
                                         DboEveningSignalStart, DboEveningSignalEnd, DboEveningSessionEnd);

                Print("[HUB] пробой: профиль " + DboWindowZone + ". Один экземпляр — один профиль — один счёт.");

                if (Slot1Enabled)
                    Print("[HUB-ВНИМАНИЕ] [MOD8][MOD1] включены два источника сигнала: структура и пробой. "
                        + "Решение принимается голосованием, см. [D01].");

                if (DboWindowZone != SwWindowZone.Chicago)
                    Print("[HUB-ВНИМАНИЕ] [M81] пояс окон пробоя = " + DboWindowZone
                        + ". Данные исследования — в поясе Chicago; иной пояс означает другую фазу рынка и отдельную, непроверенную гипотезу.");
            }
            if (Slot6Enabled) problems += CheckSlot("[M41] адаптивный стоп", AStopSlot);
            if (Slot9Enabled) problems += CheckSlot("[K52] адаптивное ядро", KerSlot);
            if (Slot11Enabled) problems += CheckSlot("[L01] классификатор Лоренца", LorSlot);
            if (Slot10Enabled) problems += CheckSlot("[H01] ядро по Хёрсту", HkSlot);
            if (Slot13Enabled) problems += CheckSlot("[C02] Калман, младшая серия", KalLowerSlot) + CheckSlot("[C04] Калман, старшая серия", KalHigherSlot);
            if (Slot14Enabled) problems += CheckSlot("[B02] рычаг, серия анализа", LevAnalysisSlot) + CheckSlot("[B03] рычаг, серия кластеров", LevClusterSlot);
            if (Slot15Enabled) problems += CheckSlot("[G01] масса, серия", HmSlot);

            if (problems == 0)
                Print("[HUB] ссылки модулей на слоты пула: замечаний нет");
            else
                Print("[HUB-ВНИМАНИЕ] ссылок на невключённые слоты: " + problems
                    + ". Расчёт идёт, но на серии графика, а не на задуманной.");
        }

        /// <summary>
        /// Порядок границ сессии: база, затем окно сигналов, затем выход; без
        /// перехода через полночь. Нарушение делает сессию молча нерабочей.
        /// </summary>
        private int CheckWindows(string who, bool on, int b0, int b1, int s0, int s1, int x)
        {
            if (!on) return 0;
            bool ok = b0 < b1 && b1 < s0 && s0 <= s1 && s1 < x && x <= 235959;
            if (ok) return 0;
            Print("[HUB-ВНИМАНИЕ] " + who + " границы нарушают порядок «база < окно сигналов < выход» "
                + "или переходят через полночь: " + b0 + "–" + b1 + " / " + s0 + "–" + s1 + " / " + x
                + ". Сессия работать не будет.");
            return 1;
        }

        private int CheckSlot(string who, int slot)
        {
            if (slot == 0) return 0;              // явная ссылка на график
            if (IsSlotLoaded(slot)) return 0;

            Print("[HUB-ВНИМАНИЕ] " + who + " ссылается на слот " + slot
                + ", но этот слот пула выключен — расчёт уйдёт на серию графика.");
            return 1;
        }

        /// <summary>
        /// СВЕДЕНИЕ СИГНАЛОВ В РЕШЕНИЕ. Ядро не вычисляет направление само —
        /// оно только сводит то, что отдали модули роли Signal, и применяет
        /// вето модулей роли Filter.
        /// </summary>
        private void EvaluateEntry(int bar)
        {
        	if (remotePauseEntries) return;   // пульт: новые входы приостановлены
            if (bufSignals.Count == 0) return;

            int sum = 0, votes = 0;
            double conf = 0;
            bool anyNotReady = false;

            foreach (SwSignal s in bufSignals)
            {
                if (!s.IsReady) { anyNotReady = true; continue; }
                if (s.Direction == 0) continue;
                sum += s.Direction; votes++; conf += s.Confidence;
            }

            if (votes == 0) return;
            if (anyNotReady && RequireAllSignalsAgree) return;

            int dir;
            if (RequireAllSignalsAgree)
                dir = Math.Abs(sum) == votes ? Math.Sign(sum) : 0;
            else
                dir = Math.Sign(sum);

            if (dir == 0) return;

            conf /= votes;
            if (conf < MinConfidence)
            {
                entriesBlocked++;
                lastDecisionText = "объединённая уверенность " + conf.ToString("F2")
                                 + " ниже порога " + MinConfidence.ToString("F2");
                HubTrace("HUB", "ENTRY_BLOCKED", lastDecisionText);
                return;
            }

            // --- вето фильтров ---
            bool hasFilterModule = false;
            foreach (SwModule m in modules)
                if (m.Role == SwRole.Filter && m.Health != SwHealth.Disabled) hasFilterModule = true;

            if (hasFilterModule && bufFilters.Count == 0 && FilterMissingBlocksEntry)
            {
                entriesBlocked++;
                lastDecisionText = "фильтр подключён, но вердикта не дал";
                HubTrace("HUB", "ENTRY_BLOCKED", lastDecisionText);
                return;
            }

            foreach (SwSignal f in bufFilters)
            {
                // НЕГОТОВЫЙ ФИЛЬТР ЗАКРЫВАЕТ ВХОД, а не пропускает.
                //
                // Прежде неготовый фильтр пропускался. Структура рынка готова
                // через два десятка баров, а линии на пятнадцатиминутке при
                // периоде 100 прогреваются двадцать пять часов. Всё это время
                // сигналы шли бы в рынок без фильтра — в самый ненадёжный
                // период. Отказ по неготовности безопаснее для капитала.
                if (!f.IsReady)
                {
                    entriesBlocked++;
                    lastDecisionText = "фильтр не прогрет: " + (f.Text ?? "—");
                    HubTrace("HUB", "ENTRY_BLOCKED", lastDecisionText);
                    return;
                }

                if (f.Verdict == SwVerdict.Veto
                    || (f.Direction != 0 && f.Direction != dir))
                {
                    entriesBlocked++;
                    lastDecisionText = "вето фильтра: " + f.Text;
                    HubTrace("HUB", "ENTRY_BLOCKED", lastDecisionText);
                    return;
                }
            }

            decisionsMade++;
            entriesRequested++;
            lastDecisionText = (dir > 0 ? "LONG" : "SHORT")
                             + "  голосов " + votes + "  уверенность " + conf.ToString("F2");
            HubTrace("HUB", "ENTRY_DECISION", lastDecisionText);

            int qty = DefaultQuantity;
            if (fin != null)
            {
                string note;
                int q = fin.ResolveQuantity(out note);
                if (q <= 0)
                {
                    entriesBlocked++;
                    lastDecisionText = "объём не рассчитан: " + note;
                    HubTrace("FIN", "SIZING_BLOCK", note);
                    return;
                }
                qty = q;
                HubTrace("FIN", "SIZING", note);
            }

            // Уровень стоп-входа и трейлинг берутся у сигнала, давшего
            // направление. Сигнал без уровня означает вход по рынку.
            double entryStop = double.NaN, trailOv = double.NaN;
            foreach (SwSignal sg in bufSignals)
            {
                if (!sg.IsReady || sg.Direction != dir) continue;
                if (sg.EntryStopPrice > 0) entryStop = sg.EntryStopPrice;
                if (sg.TrailTicksOverride > 0) trailOv = sg.TrailTicksOverride;
                if (entryStop > 0) break;
            }

            exec.RequestEntry(dir, qty, bar, lastDecisionText, entryStop, trailOv);
        }

        /// <summary>
        /// ИСТОЧНИК ИСТИНЫ ОБ ИСПОЛНЕНИЯХ. Отправка заявки исполнением не
        /// является: она может быть отклонена, отменена или исполнена
        /// частично. Ступени финансового модуля считаются только здесь.
        /// </summary>
        protected override void OnExecutionUpdate(Execution execution, string executionId,
            double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (fin == null || execution == null || execution.Order == null) return;

            try
            {
                string nm = execution.Order.Name;
                if (string.IsNullOrEmpty(nm)) return;

                // Подтверждение входа.
                if (nm == "SW_LONG" || nm == "SW_SHORT")
                {
                    if (Position != null && Position.MarketPosition != MarketPosition.Flat)
                        fin.OnTradeOpened(
                            Position.MarketPosition == MarketPosition.Long ? 1 : -1,
                            Position.AveragePrice, Position.Quantity, CurrentBars[execBip]);
                    return;
                }

                // Подтверждение ступени: метка STEPn зашита в имя заявки.
                int idx = nm.IndexOf("STEP", StringComparison.Ordinal);
                if (idx >= 0)
                {
                    int num;
                    if (int.TryParse(nm.Substring(idx + 4), out num))
                        fin.OnStepExecution(num, price, quantity);
                }
            }
            catch (Exception ex) { HubTrace("FIN", "EXEC_FAULT", ex.Message); }
        }

        protected override void OnPositionUpdate(Position position, double averagePrice,
            int quantity, MarketPosition marketPosition)
        {
            if (fin == null) return;
            if (marketPosition == MarketPosition.Flat && quantity == 0)
                fin.OnTradeClosed();
        }

        #region Панель и сводка

        private Brush HealthBrush(SwHealth h)
        {
            switch (h)
            {
                case SwHealth.Ok: return OkBrush ?? Brushes.LimeGreen;
                case SwHealth.Warmup:
                case SwHealth.Silent:
                case SwHealth.Stale: return WarnBrush ?? Brushes.Gold;
                case SwHealth.Faulted: return FaultBrush ?? Brushes.OrangeRed;
                default: return IdleBrush ?? Brushes.Gray;
            }
        }

        private static string HealthText(SwHealth h)
        {
            switch (h)
            {
                case SwHealth.Ok: return "OK     ";
                case SwHealth.Warmup: return "ПРОГРЕВ";
                case SwHealth.Silent: return "МОЛЧИТ ";
                case SwHealth.Stale: return "ЗАСТОЙ ";
                case SwHealth.Faulted: return "ОТКАЗ  ";
                case SwHealth.Disabled: return "ВЫКЛ   ";
                default: return "НЕТ    ";
            }
        }

        private void RenderPanel(int bar)
        {
            if (ChartControl == null) return;

            try
            {
                var sb = new StringBuilder();
                sb.AppendLine(HubVersion + (DryRunMode ? "   [БЕЗ ОРДЕРОВ]" : "   [БОЕВОЙ]"));
                sb.AppendLine("бар " + bar + "   серия исполнения bip=" + execBip);
                sb.AppendLine(new string('-', 64));
                sb.AppendLine("МОДУЛЬ                РОЛЬ     СОСТОЯНИЕ  ОТПР/ПРИН  ПОТЕРИ");

                foreach (SwModule m in modules)
                {
                    sb.AppendLine(string.Format("{0,-21} {1,-8} {2}  {3,5}/{4,-5} {5,6}",
                        Cut(m.Id, 21), m.Role, HealthText(m.Health),
                        m.EmitCount, m.CollectCount, m.LostCount));

                    string last = m.Role == SwRole.Escort || m.Role == SwRole.Exit
                        ? (m.LastAction.Kind == SwActionKind.None ? "—" : m.LastAction.Kind + " " + m.LastAction.Reason)
                        : (m.LastSignal.Text ?? "—");
                    sb.AppendLine("    " + Cut(last, 58));

                    if (m.Health == SwHealth.Faulted)
                        sb.AppendLine("    ОТКАЗ: " + Cut(m.LastFaultText, 50));
                }

                sb.AppendLine(new string('-', 64));
                sb.AppendLine("РЕШЕНИЕ: " + Cut(lastDecisionText, 54));
                sb.AppendLine("входов запрошено " + entriesRequested
                            + "   заблокировано " + entriesBlocked
                            + "   потерь сигнала " + lossesDetected);
                sb.AppendLine("ИСПОЛНЕНИЕ: " + Cut(exec != null ? exec.StatusText : "—", 50));
                sb.AppendLine("ФИНАНСЫ:    " + Cut(fin != null ? fin.StatusLine : "—", 50));

                if (refPac != null) sb.AppendLine("  структура: " + Cut(refPac.StateLine, 52));
                if (refTrfp != null) sb.AppendLine("  линии:     " + Cut(refTrfp.StateLine, 52));
                if (refTime != null) sb.AppendLine("  время:     " + Cut(refTime.StateLine, 52));
                if (refRegime != null) sb.AppendLine("  режим:     " + Cut(refRegime.StateLine, 52));
                if (refGuard != null) sb.AppendLine("  риск:      " + Cut(refGuard.StateLine, 52));
                if (refAStop != null) sb.AppendLine("  адапт.стоп:" + Cut(refAStop.StateLine, 52));
                if (refEscort != null) sb.AppendLine("  выход:     " + Cut(refEscort.StateLine, 52));
                if (refDbo != null) sb.AppendLine("  пробой:    " + Cut(refDbo.StateLine, 52));
                if (refKer != null) sb.AppendLine("  ядро:      " + Cut(refKer.StateLine, 52));
                if (refLor != null) sb.AppendLine("  Лоренц:    " + Cut(refLor.StateLine, 52));
                if (refHk != null) sb.AppendLine("  Хёрст:     " + Cut(refHk.StateLine, 52));
                if (refFs != null) sb.AppendLine("  ПК:        " + Cut(refFs.StateLine, 52));
                if (refHm != null) sb.AppendLine("  Масса:     " + Cut(refHm.StateLine, 52));
                sb.Append("ПОЗИЦИЯ: " + (HubPositionSide == 0 ? "вне рынка"
                    : (HubPositionSide > 0 ? "LONG " : "SHORT ") + HubPositionQty
                      + " @ " + HubPositionAvg.ToString("F2")));

                if (EnableTracing && trace.Count > 0)
                {
                    sb.AppendLine();
                    sb.AppendLine(new string('-', 64));
                    int show = Math.Min(PanelTraceLines, trace.Count);
                    for (int i = trace.Count - show; i < trace.Count; i++)
                    {
                        SwTraceEntry e = trace[i];
                        sb.AppendLine(string.Format("{0,6} {1,-16} {2,-16} {3}",
                            e.Bar, Cut(e.Module, 16), Cut(e.Event, 16), Cut(e.Detail, 24)));
                    }
                }

                // Цвет панели — худшее состояние среди модулей: неисправность
                // не должна теряться среди исправных.
                SwHealth worst = SwHealth.Ok;
                foreach (SwModule m in modules)
                {
                    if (m.Health == SwHealth.Faulted) { worst = SwHealth.Faulted; break; }
                    if (m.Health == SwHealth.Silent || m.Health == SwHealth.Stale
                        || m.Health == SwHealth.Warmup) worst = SwHealth.Warmup;
                }

                Draw.TextFixed(this, PanelTag, sb.ToString(), PanelPosition,
                               HealthBrush(worst), new SimpleFont("Consolas", Math.Max(6, PanelFontSize)),
                               Brushes.Transparent, Brushes.Black, 70);
            }
            catch { }
        }

        private static string Cut(string s, int n)
        {
            if (string.IsNullOrEmpty(s)) return string.Empty;
            return s.Length <= n ? s : s.Substring(0, n - 1) + "…";
        }

        private void PrintSummary()
        {
            var sb = new StringBuilder();
            sb.AppendLine("[HUB-ИТОГ] " + HubVersion);
            sb.AppendLine("  решений " + decisionsMade + ", входов запрошено " + entriesRequested
                + ", заблокировано " + entriesBlocked + ", потерь сигнала " + lossesDetected);

            foreach (SwModule m in modules)
                sb.AppendLine("  " + m.Id + "  роль " + m.Role + "  состояние " + m.Health
                    + "  отправлено " + m.EmitCount + "  принято " + m.CollectCount
                    + "  потеряно " + m.LostCount + "  отказов " + m.FaultCount
                    + (m.FaultCount > 0 ? "  последний: " + m.LastFaultText : ""));

            if (exec != null) sb.AppendLine("  исполнение: " + exec.SummaryText);
            if (fin != null) sb.AppendLine("  финансы: " + fin.SummaryLine);
            Print(sb.ToString());
        }

        #endregion

        /// <summary>
        /// Сборка настроек финансового модуля из свойств окна параметров.
        /// Выполняется один раз при подключении: рантайм-переоценка настроек
        /// сделала бы поведение невоспроизводимым между прогонами.
        /// </summary>
        private SwFinancialConfig BuildFinancialConfig()
        {
            SwFinancialConfig c = new SwFinancialConfig();

            c.SizingMode = SizingMode;
            c.FixedQuantity = DefaultQuantity;
            c.RiskMoneyPerTrade = RiskMoneyPerTrade;
            c.AccountEquityReference = AccountEquityReference;
            c.RiskPercentOfEquity = RiskPercentOfEquity;
            c.MinQuantity = MinQuantity;
            c.MaxQuantity = MaxQuantity;

            c.RoundTurnCostPerContract = RoundTurnCostPerContract;
            c.SlippageReserveTicks = SlippageReserveTicks;

            c.StopMode = StopMode;
            c.StopFixedTicks = StopLossTicks;
            c.StopPriceDollars = StopPriceDollars;
            c.StopAtrMultiple = StopAtrMultiple;

            c.UseScaleOut = UseScaleOut;
            c.ScaleSteps = ScaleSteps;
            c.StepDistanceMode = StepDistanceMode;
            c.StepFixedTicks = StepFixedTicks;
            c.StepPriceDollars = StepPriceDollars;
            c.StepRMultiple = StepRMultiple;
            c.ContractsOnStep1 = ContractsOnStep1;
            c.ContractsPerStep = ContractsPerStep;
            c.KeepRunner = KeepRunner;

            c.BreakevenMode = BreakevenMode;
            c.BreakevenAtR = BreakevenAtR;
            c.BreakevenOffsetTicks = BreakevenOffsetTicks;

            c.TrailMode = TrailMode;
            c.TrailActivateAtR = TrailActivateAtR;
            c.TrailFixedTicks = TrailDistanceTicks;
            c.TrailAtrMultiple = TrailAtrMultiple;

            c.DisableStopMoveAfterStep1 = DisableStopMoveAfterStep1;
            c.MinBarsBetweenStopMoves = MinBarsBetweenStopMoves;
            c.StepConfirmTimeoutBars = StepConfirmTimeoutBars;
            c.BreakevenOnBestPrice = BreakevenOnBestPrice;

            return c;
        }




        #region Свойства — Калман, рычаг, масса
        [NinjaScriptProperty]
        [Display(Name = "[MOD13] Слот 13 — канал Калмана", Order = 23, GroupName = "1 · Слоты модулей",
        	Description = "Канал Калмана: диапазон, пробой, выход по наклону. Роль — [C01].")]
        public bool Slot13Enabled { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "[MOD14] Слот 14 — рычаг свечи", Order = 24, GroupName = "1 · Слоты модулей",
        	Description = "Рычаг свечи: голос кластеров объёма. Роль — [B01].")]
        public bool Slot14Enabled { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "[MOD15] Слот 15 — иерархическая масса", Order = 25, GroupName = "1 · Слоты модулей",
        	Description = "Дрейф взвешенной по объёму цены внутри окна по эшелонам 1, 5 и 15 минут.")]
        public bool Slot15Enabled { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "[C01] Роль", Order = 1, GroupName = "15 · Канал Калмана",
        	Description = "Роль модуля в конвейере.")]
        public SwKalmanRole KalRole { get; set; }
        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[C02] Младшая серия", Order = 2, GroupName = "15 · Канал Калмана",
        	Description = "Слот пула 0–4.")]
        public int KalLowerSlot { get; set; }
        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[C03] Текущая серия", Order = 3, GroupName = "15 · Канал Калмана",
        	Description = "Слот пула 0–4.")]
        public int KalCurrentSlot { get; set; }
        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[C04] Старшая серия", Order = 4, GroupName = "15 · Канал Калмана",
        	Description = "Слот пула 0–4.")]
        public int KalHigherSlot { get; set; }
        [NinjaScriptProperty]
        [Range(2, 500)]
        [Display(Name = "[C05] Период", Order = 5, GroupName = "15 · Канал Калмана",
        	Description = "Окно фильтра, баров.")]
        public int KalPeriod { get; set; }
        [NinjaScriptProperty]
        [Range(0.1, 10.0)]
        [Display(Name = "[C06] Ширина полос, σ", Order = 6, GroupName = "15 · Канал Калмана",
        	Description = "Множитель полос канала.")]
        public double KalBandSigma { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "[C07] Политика фильтра", Order = 7, GroupName = "15 · Канал Калмана",
        	Description = "Как канал голосует за направление.")]
        public SwKalmanFilterPolicy KalPolicy { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "[B01] Роль", Order = 1, GroupName = "16 · Рычаг свечи",
        	Description = "Роль модуля в конвейере.")]
        public SwLeverRole LevRole { get; set; }
        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[B02] Серия анализа", Order = 2, GroupName = "16 · Рычаг свечи",
        	Description = "Слот пула 0–4.")]
        public int LevAnalysisSlot { get; set; }
        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[B03] Серия кластеров", Order = 3, GroupName = "16 · Рычаг свечи",
        	Description = "Слот пула 0–4.")]
        public int LevClusterSlot { get; set; }
        [NinjaScriptProperty]
        [Range(2, 100)]
        [Display(Name = "[B04] Кластеров", Order = 4, GroupName = "16 · Рычаг свечи",
        	Description = "Число кластеров объёма.")]
        public int LevClusters { get; set; }
        [NinjaScriptProperty]
        [Range(0.0, 10.0)]
        [Display(Name = "[B05] Порог голоса, z", Order = 5, GroupName = "16 · Рычаг свечи",
        	Description = "Порог значимости голоса.")]
        public double LevVoteZ { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "[B06] Политика", Order = 6, GroupName = "16 · Рычаг свечи",
        	Description = "Как рычаг голосует.")]
        public SwLeverPolicy LevPolicy { get; set; }
        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[G01] Серия", Order = 1, GroupName = "17 · Иерархическая масса",
        	Description = "Слот пула с минутками, 0–4.")]
        public int HmSlot { get; set; }
        [NinjaScriptProperty]
        [Range(5, 480)]
        [Display(Name = "[G02] Окно, минут", Order = 2, GroupName = "17 · Иерархическая масса",
        	Description = "Длина окна расчёта; эшелоны — полные блоки 5 и 15 минут от конца окна.")]
        public int HmWindow { get; set; }
        [NinjaScriptProperty]
        [Range(0.0, 10.0)]
        [Display(Name = "[G03] Вес эшелона 5M", Order = 3, GroupName = "17 · Иерархическая масса",
        	Description = "Вес 5-минутного эшелона в синтетическом узле.")]
        public double HmWeight5 { get; set; }
        [NinjaScriptProperty]
        [Range(0.0, 10.0)]
        [Display(Name = "[G04] Вес эшелона 15M", Order = 4, GroupName = "17 · Иерархическая масса",
        	Description = "Вес 15-минутного эшелона; 1,5 по ТЗ.")]
        public double HmWeight15 { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "[G05] Режим сигнала", Order = 5, GroupName = "17 · Иерархическая масса",
        	Description = "Выключено — фильтр.")]
        public bool HmSignalMode { get; set; }
        [NinjaScriptProperty]
        [Range(0.5, 0.99)]
        [Display(Name = "[G06] Процентиль ширины", Order = 6, GroupName = "17 · Иерархическая масса",
        	Description = "Процентиль отклонений от оси для ширины коридора; 0,85 по ТЗ.")]
        public double HmPercentile { get; set; }
        [NinjaScriptProperty]
        [Range(0.0, 100.0)]
        [Display(Name = "[G07] Порог смещения, тиков", Order = 7, GroupName = "17 · Иерархическая масса",
        	Description = "|смещение| ниже порога — нейтраль.")]
        public double HmBiasThreshold { get; set; }
        [NinjaScriptProperty]
        [Display(Name = "[G08] Шлюз сжатия", Order = 8, GroupName = "17 · Иерархическая масса",
        	Description = "Ширина ниже доли своей медианы — нейтраль. ЭКСПЕРИМЕНТ: выключено по умолчанию.")]
        public bool HmExpSqueeze { get; set; }
        [NinjaScriptProperty]
        [Range(0.1, 1.0)]
        [Display(Name = "[G09] Доля медианы для сжатия", Order = 9, GroupName = "17 · Иерархическая масса",
        	Description = "Для [G08].")]
        public double HmExpSqueezeRatio { get; set; }
        [NinjaScriptProperty]
        [Range(0, 20)]
        [Display(Name = "[G10] Устойчивость знака, расчётов", Order = 10, GroupName = "17 · Иерархическая масса",
        	Description = "Направление после K подряд расчётов одного знака; 0 — выключено. ЭКСПЕРИМЕНТ: выключено по умолчанию.")]
        public int HmExpPersist { get; set; }
        #endregion

        #region Схема меню и пресеты — цепочка без Excel
        // Схема — рефлексия над [NinjaScriptProperty] СКОМПИЛИРОВАННОЙ сборки: источник тот же, что торгует.
        // Пресет — всё или ничего; защитные свойства пресетом не меняются.
        private static System.Collections.Generic.Dictionary<string, object> schemaDefaults;
        private static readonly string[] PresetDenied = { "DryRunMode", "WsEnabled", "WsAllowCommands", "ExportSchema", "PresetFile" };

        private System.Collections.Generic.List<System.Reflection.PropertyInfo> MenuProperties()
        {
        	var list = new System.Collections.Generic.List<System.Reflection.PropertyInfo>();
        	foreach (System.Reflection.PropertyInfo p in GetType().GetProperties(System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance))
        		if (p.CanRead && p.CanWrite && Attribute.GetCustomAttribute(p, typeof(NinjaScriptPropertyAttribute)) != null) list.Add(p);
        	return list;
        }

        /// <summary>Значения по умолчанию — один раз, в конце SetDefaults, когда присвоены все.</summary>
        private void CaptureSchemaDefaults()
        {
        	if (schemaDefaults != null) return;
        	var d = new System.Collections.Generic.Dictionary<string, object>();
        	foreach (System.Reflection.PropertyInfo p in MenuProperties()) { try { d[p.Name] = p.GetValue(this, null); } catch { } }
        	schemaDefaults = d;
        }

        private static string JStr(string v) { return "\"" + (v ?? "").Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\r", " ").Replace("\n", " ") + "\""; }

        private static string JVal(object v)
        {
        	if (v == null) return "null";
        	if (v is bool) return (bool)v ? "true" : "false";
        	if (v is Enum || v is string) return JStr(v.ToString());
        	if (v is int || v is long || v is double || v is float || v is decimal)
        	{
        		double x = Convert.ToDouble(v, System.Globalization.CultureInfo.InvariantCulture);
        		return double.IsNaN(x) || double.IsInfinity(x) ? "null" : x.ToString("R", System.Globalization.CultureInfo.InvariantCulture);
        	}
        	return "null";
        }

        /// <summary>[U04]: схема меню в dz_export\\hub_menu_schema.json — индекс, имя, тип, пределы, умолчание, текущее значение, группа.</summary>
        private void ExportMenuSchema()
        {
        	try
        	{
        		var props = MenuProperties();
        		var sb = new System.Text.StringBuilder(65536);
        		sb.Append("{\"schema\":\"DZ-HUB-MENU-SCHEMA-v1\",\"strategy\":").Append(JStr(Name))
        			.Append(",\"exported_local\":").Append(JStr(DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss")))
        			.Append(",\"count\":").Append(props.Count).Append(",\"properties\":[");
        		bool first = true;
        		foreach (System.Reflection.PropertyInfo p in props)
        		{
        			DisplayAttribute d = Attribute.GetCustomAttribute(p, typeof(DisplayAttribute)) as DisplayAttribute;
        			RangeAttribute r = Attribute.GetCustomAttribute(p, typeof(RangeAttribute)) as RangeAttribute;
        			string label = d != null && d.GetName() != null ? d.GetName() : p.Name;
        			int close = label.IndexOf(']');
        			string idx = label.StartsWith("[") && close > 1 ? label.Substring(1, close - 1) : "";
        			Type t = p.PropertyType;
        			string type = t == typeof(bool) ? "bool" : t == typeof(int) ? "int" : t == typeof(double) ? "double" : t == typeof(string) ? "string" : t.IsEnum ? "enum" : t.Name;
        			object def = null;
        			if (schemaDefaults != null) schemaDefaults.TryGetValue(p.Name, out def);
        			if (!first) sb.Append(',');
        			first = false;
        			sb.Append("{\"index\":").Append(JStr(idx)).Append(",\"name\":").Append(JStr(p.Name)).Append(",\"label\":").Append(JStr(label))
        				.Append(",\"type\":").Append(JStr(type))
        				.Append(",\"min\":").Append(r != null ? JVal(Convert.ToDouble(r.Minimum, System.Globalization.CultureInfo.InvariantCulture)) : "null")
        				.Append(",\"max\":").Append(r != null ? JVal(Convert.ToDouble(r.Maximum, System.Globalization.CultureInfo.InvariantCulture)) : "null")
        				.Append(",\"default\":").Append(JVal(def)).Append(",\"value\":").Append(JVal(p.GetValue(this, null)))
        				.Append(",\"group\":").Append(JStr(d != null ? d.GetGroupName() : ""))
        				.Append(",\"order\":").Append(d != null && d.GetOrder().HasValue ? d.GetOrder().Value.ToString() : "null")
        				.Append(",\"description\":").Append(JStr(d != null ? d.GetDescription() : ""));
        			if (t.IsEnum)
        			{
        				sb.Append(",\"enum\":[");
        				string[] names = Enum.GetNames(t);
        				for (int i = 0; i < names.Length; i++) { if (i > 0) sb.Append(','); sb.Append(JStr(names[i])); }
        				sb.Append(']');
        			}
        			sb.Append('}');
        		}
        		sb.Append("]}");
        		string dir = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "NinjaTrader 8", "dz_export");
        		System.IO.Directory.CreateDirectory(dir);
        		string path = System.IO.Path.Combine(dir, "hub_menu_schema.json");
        		System.IO.File.WriteAllText(path, sb.ToString(), new System.Text.UTF8Encoding(false));
        		Print("[DZ_SCHEMA] " + path + ": свойств " + props.Count);
        	}
        	catch (Exception ex) { Print("[DZ_SCHEMA] выгрузка не выполнена: " + ex.Message); }
        }

        /// <summary>[U05]: пресет из dz_export\\presets. Всё или ничего; защитные свойства не меняются.</summary>
        private void ApplyPreset()
        {
        	if (string.IsNullOrWhiteSpace(PresetFile)) return;
        	string dir = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "NinjaTrader 8", "dz_export", "presets");
        	string path = System.IO.Path.IsPathRooted(PresetFile) ? PresetFile : System.IO.Path.Combine(dir, PresetFile);
        	string json;
        	try { json = System.IO.File.ReadAllText(path); }
        	catch (Exception ex) { Print("[DZ_PRESET] ОТКАЗ: файл не читается: " + ex.Message); return; }
        	if (json.IndexOf("\"DZ_SW_Hub_S021\"", StringComparison.Ordinal) < 0) { Print("[DZ_PRESET] ОТКАЗ: пресет не для DZ_SW_Hub_S021"); return; }
        	string err;
        	var raw = ParsePresetParams(json, out err);
        	if (raw == null) { Print("[DZ_PRESET] ОТКАЗ: " + err); return; }
        	var byName = new System.Collections.Generic.Dictionary<string, System.Reflection.PropertyInfo>();
        	foreach (System.Reflection.PropertyInfo p in MenuProperties()) byName[p.Name] = p;
        	var plan = new System.Collections.Generic.List<System.Collections.Generic.KeyValuePair<System.Reflection.PropertyInfo, object>>();
        	var errors = new System.Collections.Generic.List<string>();
        	foreach (var kv in raw)
        	{
        		System.Reflection.PropertyInfo p;
        		if (Array.IndexOf(PresetDenied, kv.Key) >= 0) { errors.Add(kv.Key + ": защитное свойство, пресетом не меняется"); continue; }
        		if (!byName.TryGetValue(kv.Key, out p)) { errors.Add(kv.Key + ": такого свойства нет"); continue; }
        		object v;
        		string e = ConvertPresetValue(p, kv.Value.Key, kv.Value.Value, out v);
        		if (e != null) { errors.Add(kv.Key + ": " + e); continue; }
        		plan.Add(new System.Collections.Generic.KeyValuePair<System.Reflection.PropertyInfo, object>(p, v));
        	}
        	if (errors.Count > 0) { Print("[DZ_PRESET] ОТКАЗ, не применено ничего: " + string.Join("; ", errors)); return; }
        	foreach (var kv in plan) kv.Key.SetValue(this, kv.Value, null);
        	Print("[DZ_PRESET] применён " + path + ": настроек " + plan.Count);
        }

        private static string ConvertPresetValue(System.Reflection.PropertyInfo p, string s, bool isString, out object v)
        {
        	v = null;
        	Type t = p.PropertyType;
        	var inv = System.Globalization.CultureInfo.InvariantCulture;
        	if (t == typeof(bool)) { if (isString || (s != "true" && s != "false")) return "ожидалось true или false"; v = s == "true"; }
        	else if (t == typeof(int)) { int x; if (isString || !int.TryParse(s, System.Globalization.NumberStyles.Integer, inv, out x)) return "ожидалось целое"; v = x; }
        	else if (t == typeof(double)) { double x; if (isString || !double.TryParse(s, System.Globalization.NumberStyles.Float, inv, out x)) return "ожидалось число"; v = x; }
        	else if (t.IsEnum) { if (!isString || !Enum.IsDefined(t, s)) return "нет значения " + s + " в перечислении " + t.Name; v = Enum.Parse(t, s); }
        	else if (t == typeof(string)) { if (!isString) return "ожидалась строка"; v = s; }
        	else return "тип " + t.Name + " пресетом не задаётся";
        	RangeAttribute r = Attribute.GetCustomAttribute(p, typeof(RangeAttribute)) as RangeAttribute;
        	if (r != null && (t == typeof(int) || t == typeof(double)))
        	{
        		double x = Convert.ToDouble(v, inv), lo = Convert.ToDouble(r.Minimum, inv), hi = Convert.ToDouble(r.Maximum, inv);
        		if (x < lo || x > hi) return "значение " + x.ToString(inv) + " вне предела " + lo.ToString(inv) + "…" + hi.ToString(inv);
        	}
        	return null;
        }

        /// <summary>Плоский объект "params": ключ → (значение, строка ли). Вложенные значения не принимаются.</summary>
        private static System.Collections.Generic.Dictionary<string, System.Collections.Generic.KeyValuePair<string, bool>> ParsePresetParams(string json, out string err)
        {
        	err = null;
        	var d = new System.Collections.Generic.Dictionary<string, System.Collections.Generic.KeyValuePair<string, bool>>();
        	int i = json.IndexOf("\"params\"", StringComparison.Ordinal);
        	if (i < 0) { err = "нет раздела params"; return null; }
        	i = json.IndexOf('{', i);
        	if (i < 0) { err = "раздел params не объект"; return null; }
        	i++;
        	while (true)
        	{
        		while (i < json.Length && (char.IsWhiteSpace(json[i]) || json[i] == ',')) i++;
        		if (i >= json.Length) { err = "файл оборван"; return null; }
        		if (json[i] == '}') break;
        		if (json[i] != '"') { err = "ожидался ключ"; return null; }
        		string key = ReadJsonString(json, ref i);
        		while (i < json.Length && char.IsWhiteSpace(json[i])) i++;
        		if (key == null || i >= json.Length || json[i] != ':') { err = "ошибка после ключа " + key; return null; }
        		i++;
        		while (i < json.Length && char.IsWhiteSpace(json[i])) i++;
        		if (i >= json.Length) { err = "файл оборван"; return null; }
        		if (json[i] == '"') { string sv = ReadJsonString(json, ref i); if (sv == null) { err = "строка оборвана"; return null; } d[key] = new System.Collections.Generic.KeyValuePair<string, bool>(sv, true); }
        		else if (json[i] == '{' || json[i] == '[') { err = key + ": вложенные значения не принимаются"; return null; }
        		else
        		{
        			int j = i;
        			while (j < json.Length && json[j] != ',' && json[j] != '}') j++;
        			d[key] = new System.Collections.Generic.KeyValuePair<string, bool>(json.Substring(i, j - i).Trim(), false);
        			i = j;
        		}
        	}
        	return d;
        }

        private static string ReadJsonString(string s, ref int i)
        {
        	var sb = new System.Text.StringBuilder();
        	i++;
        	while (i < s.Length)
        	{
        		char c = s[i++];
        		if (c == '"') return sb.ToString();
        		if (c != '\\') { sb.Append(c); continue; }
        		if (i >= s.Length) return null;
        		char e = s[i++];
        		if (e == 'n') sb.Append('\n'); else if (e == 't') sb.Append('\t'); else if (e == 'u') { i += 4; sb.Append('?'); } else sb.Append(e);
        	}
        	return null;
        }

        [NinjaScriptProperty]
        [Display(Name = "[U04] Выгрузить схему меню", Order = 4, GroupName = "14 · Пульт реального времени",
        	Description = "При запуске пишет dz_export\\hub_menu_schema.json: все настройки с индексами, типами, пределами и умолчаниями — для конфигуратора задач.")]
        public bool ExportSchema { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[U05] Файл пресета", Order = 5, GroupName = "14 · Пульт реального времени",
        	Description = "Имя файла в dz_export\\presets. Применяется при запуске: всё или ничего; режим без ордеров и доступ пульта пресет не меняет. Пусто — без пресета.")]
        public string PresetFile { get; set; }
        #endregion

        #region Пульт реального времени — WebSocket
        // Сервер поднимается при переходе в реальное время: в Strategy Analyzer и на истории
        // его нет. Поток стратегии только кладёт снимок в очередь и забирает команды.
        private SwWsBridge ws;
        private bool remotePauseEntries, remoteFlattenPending;
        private readonly System.Text.StringBuilder wsSb = new System.Text.StringBuilder(4096);

        private void StartRemote()
        {
        	if (!WsEnabled || ws != null) return;
        	string tokenFile = System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
        		"NinjaTrader 8", "dz_export", "atlas_ws_token.txt");
        	ws = new SwWsBridge(WsPort, tokenFile, WsAllowCommands);
        	ws.Start();
        }

        /// <summary>Команды пульта — в потоке стратегии. «Закрыть» — обычным действием FullExit через единственную точку ордеров.</summary>
        private void ProcessRemote(int bar)
        {
        	if (ws == null) return;
        	string s;
        	while (ws.TryTakeLog(out s)) HubTrace("HUB", "WS", s);
        	while (ws.TryTakeCommand(out s))
        	{
        		if (s == "pause") { remotePauseEntries = true; HubTrace("HUB", "REMOTE_PAUSE", "пульт: новые входы приостановлены"); }
        		else if (s == "resume") { remotePauseEntries = false; HubTrace("HUB", "REMOTE_RESUME", "пульт: входы возобновлены"); }
        		else if (s == "flatten") { remoteFlattenPending = true; HubTrace("HUB", "REMOTE_FLATTEN", "пульт: закрыть позицию"); }
        	}
        	if (remoteFlattenPending)
        	{
        		remoteFlattenPending = false;
        		if (HubPositionSide != 0)
        		{
        			SwAction a = SwAction.None(bar);
        			a.Kind = SwActionKind.FullExit; a.Reason = "ПУЛЬТ: закрыть позицию"; a.Tag = "REMOTE";
        			bufActions.Add(a);
        		}
        	}
        }

        private static string WsEsc(string v)
        {
        	return string.IsNullOrEmpty(v) ? "" : v.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", " ").Replace("\r", " ");
        }

        private static string WsNum(double v) { return double.IsNaN(v) || double.IsInfinity(v) ? "null" : v.ToString(System.Globalization.CultureInfo.InvariantCulture); }

        /// <summary>Снимок бара для пульта. Время — UTC, секунды; центр масс = (H + L + C) / 3.</summary>
        private void PublishSnapshot(int bar)
        {
        	if (ws == null || ws.ClientCount == 0) return;
        	DateTime tUtc;
        	try { tUtc = TimeZoneInfo.ConvertTimeToUtc(DateTime.SpecifyKind(Times[execBip][0], DateTimeKind.Unspecified), NinjaTrader.Core.Globals.GeneralOptions.TimeZoneInfo); }
        	catch { tUtc = DateTime.SpecifyKind(Times[execBip][0], DateTimeKind.Utc); }
        	long ts = (long)(tUtc - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalSeconds;
        	double o = Opens[execBip][0], h = Highs[execBip][0], l = Lows[execBip][0], c = Closes[execBip][0];
        	wsSb.Clear();
        	wsSb.Append("{\"t\":\"bar\",\"ts\":").Append(ts).Append(",\"o\":").Append(WsNum(o)).Append(",\"h\":").Append(WsNum(h))
        		.Append(",\"l\":").Append(WsNum(l)).Append(",\"c\":").Append(WsNum(c)).Append(",\"com\":").Append(WsNum((h + l + c) / 3.0))
        		.Append(",\"pos\":").Append(HubPositionSide).Append(",\"qty\":").Append(Position != null ? Position.Quantity : 0)
        		.Append(",\"avg\":").Append(WsNum(Position != null ? Position.AveragePrice : 0)).Append(",\"pnl\":").Append(WsNum(HubRealizedPnl))
        		.Append(",\"paused\":").Append(remotePauseEntries ? "true" : "false").Append(",\"dry\":").Append(DryRunMode ? "true" : "false")
        		.Append(",\"vis\":").Append(visualTotal)
        		.Append(",\"ch\":[").Append(WsNum(channelPlot[0, 0])).Append(',').Append(WsNum(channelPlot[0, 1])).Append(',').Append(WsNum(channelPlot[0, 2])).Append(']')
        		.Append(",\"mods\":[");
        	bool first = true;
        	foreach (SwModule m in modules)
        	{
        		if (!first) wsSb.Append(','); first = false;
        		SwSignal sg = m.LastSignal;
        		wsSb.Append("{\"id\":\"").Append(WsEsc(m.Id)).Append("\",\"role\":\"").Append(m.Role).Append("\",\"health\":\"").Append(m.Health)
        			.Append("\",\"dir\":").Append(sg.Direction).Append(",\"conf\":").Append(WsNum(sg.Confidence))
        			.Append(",\"txt\":\"").Append(WsEsc(sg.Text)).Append('"');
			string tj = m.TelemetryJson(System.Globalization.CultureInfo.InvariantCulture);
			if (tj != null) wsSb.Append(",\"x\":").Append(tj);
			wsSb.Append('}');
        	}
        	wsSb.Append("]}");
        	ws.Publish(wsSb.ToString());
        }

        [NinjaScriptProperty]
        [Display(Name = "[U01] Сервер пульта", Order = 1, GroupName = "14 · Пульт реального времени",
        	Description = "WebSocket на 127.0.0.1 для пульта «Атласа». Поднимается только в реальном времени, не в Strategy Analyzer.")]
        public bool WsEnabled { get; set; }

        [NinjaScriptProperty]
        [Range(1024, 65535)]
        [Display(Name = "[U02] Порт", Order = 2, GroupName = "14 · Пульт реального времени",
        	Description = "Порт на 127.0.0.1. Две стратегии на одном ПК — разные порты.")]
        public int WsPort { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[U03] Разрешить команды пульта", Order = 3, GroupName = "14 · Пульт реального времени",
        	Description = "Пауза входов, возобновление, закрыть позицию. Выключено — пульт только наблюдает. Ключ — в dz_export\\atlas_ws_token.txt.")]
        public bool WsAllowCommands { get; set; }
        #endregion

        #region Визуальный слой — приём событий модулей
        // Этап 0: события складываются в заранее выделенное кольцо; отрисовка — следующий шаг.
        private readonly SwVisualEvent[] visualRing = new SwVisualEvent[512];
        private int visualHead, visualTotal;
        private readonly double[,] channelPlot = new double[8, 3];

        internal void HubVisual(string moduleId, SwVisualEvent e)
        {
        	visualRing[visualHead] = e;
        	visualHead = (visualHead + 1) % visualRing.Length;
        	visualTotal++;
        }

        internal void HubChannelPlot(int track, int line, double value, int variant)
        {
        	if (track >= 0 && track < 8 && line >= 0 && line < 3) channelPlot[track, line] = value;
        }

        internal int VisualEventsTotal { get { return visualTotal; } }

        [NinjaScriptProperty]
        [Display(Name = "[V01] Визуализация модулей", Order = 1, GroupName = "13 · Визуализация",
        	Description = "Разрешает модулям выдавать события визуального слоя. Этап 0: события принимаются, отрисовка — следующий шаг.")]
        public bool VisualsEnabled { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[V02] Отладочная визуализация", Order = 2, GroupName = "13 · Визуализация",
        	Description = "Дополнительные отладочные события модулей. Требует [V01].")]
        public bool VisualDebugEnabled { get; set; }
        #endregion

        #region Свойства — слоты

        [NinjaScriptProperty] [Display(Name = "[MOD1] Слот 1 — структура, сигнал", Order = 1, GroupName = "1 · Слоты модулей",
            Description = "Включение первого слота. Подключение конкретного модуля выполняется в методе BuildSlots.")]
        public bool Slot1Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "[MOD2] Слот 2 — линии, фильтр", Order = 3, GroupName = "1 · Слоты модулей",
            Description = "Включение второго слота.")]
        public bool Slot2Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "[MOD3] Слот 3 — время, фильтр", Order = 5, GroupName = "1 · Слоты модулей",
            Description = "Включение третьего слота. По умолчанию пуст: подключите свой модуль в BuildSlots.")]
        public bool Slot3Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "[MOD5] Слот 5 — риск, фильтр", Order = 15, GroupName = "1 · Слоты модулей",
            Description = "Дневные лимиты убытка и прибыли, новостные паузы, блокировка после перезапуска. Последний барьер: ни один сигнальный модуль его не обходит.")]
        public bool Slot5Enabled { get; set; }

        [NinjaScriptProperty] [Display(Name = "[MOD6] Слот 6 — адаптивный стоп, сопровождение", Order = 16, GroupName = "1 · Слоты модулей",
            Description = "Сопровождение линией, расширяющейся с волатильностью. Ордеров не создаёт: просит о переносе стопа.")]
        public bool Slot6Enabled { get; set; }

        [NinjaScriptProperty] [Display(Name = "[MOD8] Слот 8 — пробой диапазона двух сессий, сигнал", Order = 18, GroupName = "1 · Слоты модулей",
            Description = "Утренний и вечерний пробой базы с фильтрами 4H и 15M по выводам исследования GC 2007–2026. Входит отложенным стоп-ордером до пробоя. ТРЕБУЕТ серий M1, M15 и 4H в пуле [S50]-[S80]. С модулем времени [MOD3] конфликтует по окнам.")]
        public bool Slot8Enabled { get; set; }

        [NinjaScriptProperty] [Display(Name = "[MOD7] Слот 7 — выход по линии", Order = 17, GroupName = "1 · Слоты модулей",
            Description = "Закрытие при развороте линии против позиции. ТРЕБУЕТ включённого слота 2: без модуля линий не подключается, о чём сообщает при загрузке.")]
        public bool Slot7Enabled { get; set; }

        [NinjaScriptProperty] [Display(Name = "[MOD4] Слот 4 — режим рынка, фильтр", Order = 7, GroupName = "1 · Слоты модулей",
            Description = "Включение четвёртого слота. По умолчанию пуст.")]
        public bool Slot4Enabled { get; set; }
        [NinjaScriptProperty] [Display(Name = "[S50] Серия 1 включена", Order = 13, GroupName = "0 · Пул серий данных",
            Description = "Слот 1 пула дополнительных серий. Объявляется в State.Configure и после запуска не меняется: AddDataSeries работает только там. Порядок слотов фиксирует индексы, перестановка заставит модули читать чужие бары.")]
        public bool UseSeries1 { get; set; }

        [NinjaScriptProperty] [Display(Name = "[S51] Серия 1 — тип", Order = 14, GroupName = "0 · Пул серий данных",
            Description = "Тип периода серии слота 1.")]
        public BarsPeriodType Series1Type { get; set; }

        [NinjaScriptProperty] [Range(1, int.MaxValue)]
        [Display(Name = "[S52] Серия 1 — значение", Order = 15, GroupName = "0 · Пул серий данных",
            Description = "Значение периода серии слота 1.")]
        public int Series1Value { get; set; }

        [NinjaScriptProperty] [Display(Name = "[S60] Серия 2 включена", Order = 16, GroupName = "0 · Пул серий данных",
            Description = "Слот 2 пула дополнительных серий. Объявляется в State.Configure и после запуска не меняется: AddDataSeries работает только там. Порядок слотов фиксирует индексы, перестановка заставит модули читать чужие бары.")]
        public bool UseSeries2 { get; set; }

        [NinjaScriptProperty] [Display(Name = "[S61] Серия 2 — тип", Order = 17, GroupName = "0 · Пул серий данных",
            Description = "Тип периода серии слота 2.")]
        public BarsPeriodType Series2Type { get; set; }

        [NinjaScriptProperty] [Range(1, int.MaxValue)]
        [Display(Name = "[S62] Серия 2 — значение", Order = 18, GroupName = "0 · Пул серий данных",
            Description = "Значение периода серии слота 2.")]
        public int Series2Value { get; set; }

        [NinjaScriptProperty] [Display(Name = "[S70] Серия 3 включена", Order = 19, GroupName = "0 · Пул серий данных",
            Description = "Слот 3 пула дополнительных серий. Объявляется в State.Configure и после запуска не меняется: AddDataSeries работает только там. Порядок слотов фиксирует индексы, перестановка заставит модули читать чужие бары.")]
        public bool UseSeries3 { get; set; }

        [NinjaScriptProperty] [Display(Name = "[S71] Серия 3 — тип", Order = 20, GroupName = "0 · Пул серий данных",
            Description = "Тип периода серии слота 3.")]
        public BarsPeriodType Series3Type { get; set; }

        [NinjaScriptProperty] [Range(1, int.MaxValue)]
        [Display(Name = "[S72] Серия 3 — значение", Order = 21, GroupName = "0 · Пул серий данных",
            Description = "Значение периода серии слота 3.")]
        public int Series3Value { get; set; }

        [NinjaScriptProperty] [Display(Name = "[S80] Серия 4 включена", Order = 22, GroupName = "0 · Пул серий данных",
            Description = "Слот 4 пула дополнительных серий. Объявляется в State.Configure и после запуска не меняется: AddDataSeries работает только там. Порядок слотов фиксирует индексы, перестановка заставит модули читать чужие бары.")]
        public bool UseSeries4 { get; set; }

        [NinjaScriptProperty] [Display(Name = "[S81] Серия 4 — тип", Order = 23, GroupName = "0 · Пул серий данных",
            Description = "Тип периода серии слота 4.")]
        public BarsPeriodType Series4Type { get; set; }

        [NinjaScriptProperty] [Range(1, int.MaxValue)]
        [Display(Name = "[S82] Серия 4 — значение", Order = 24, GroupName = "0 · Пул серий данных",
            Description = "Значение периода серии слота 4.")]
        public int Series4Value { get; set; }

        [NinjaScriptProperty] [Range(0, 4)]
        [Display(Name = "[S90] Серия исполнения — слот", Order = 30, GroupName = "0 · Пул серий данных",
            Description = "Какая серия обслуживает такт решения и отправку заявок. Ноль — серия графика, 1..4 — слоты пула. Обычно это самая быстрая из загруженных: от неё зависит момент входа.")]
        public int ExecSeriesSlot { get; set; }

        #endregion

        #region Свойства — пробой: окна и фильтры

        [NinjaScriptProperty]
        [Range(0, 235959)]
        [Display(Name = "[W11] Утро: база, начало", Order = 11, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Время ЧЧММСС в поясе окон [M81], по времени открытия бара.")]
        public int DboMorningBaseStart { get; set; }

        [NinjaScriptProperty]
        [Range(0, 235959)]
        [Display(Name = "[W12] Утро: база, конец", Order = 12, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Время ЧЧММСС в поясе окон [M81], по времени открытия бара.")]
        public int DboMorningBaseEnd { get; set; }

        [NinjaScriptProperty]
        [Range(0, 235959)]
        [Display(Name = "[W13] Утро: окно сигналов, начало", Order = 13, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Время ЧЧММСС в поясе окон [M81], по времени открытия бара.")]
        public int DboMorningSignalStart { get; set; }

        [NinjaScriptProperty]
        [Range(0, 235959)]
        [Display(Name = "[W14] Утро: окно сигналов, конец", Order = 14, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Время ЧЧММСС в поясе окон [M81], по времени открытия бара.")]
        public int DboMorningSignalEnd { get; set; }

        [NinjaScriptProperty]
        [Range(0, 235959)]
        [Display(Name = "[W15] Утро: выход по времени", Order = 15, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Время ЧЧММСС в поясе окон [M81], по времени открытия бара. Выход — принудительное закрытие позиции сессии.")]
        public int DboMorningSessionEnd { get; set; }

        [NinjaScriptProperty]
        [Range(1.0, 10000.0)]
        [Display(Name = "[W16] Утро: трейлинг, тиков", Order = 16, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Расстояние трейлинга сделок этой сессии. Передаётся финансовому модулю с сигналом.")]
        public double DboMorningTrailTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0, 235959)]
        [Display(Name = "[W21] Вечер: база, начало", Order = 21, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Время ЧЧММСС в поясе окон [M81], по времени открытия бара.")]
        public int DboEveningBaseStart { get; set; }

        [NinjaScriptProperty]
        [Range(0, 235959)]
        [Display(Name = "[W22] Вечер: база, конец", Order = 22, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Время ЧЧММСС в поясе окон [M81], по времени открытия бара.")]
        public int DboEveningBaseEnd { get; set; }

        [NinjaScriptProperty]
        [Range(0, 235959)]
        [Display(Name = "[W23] Вечер: окно сигналов, начало", Order = 23, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Время ЧЧММСС в поясе окон [M81], по времени открытия бара.")]
        public int DboEveningSignalStart { get; set; }

        [NinjaScriptProperty]
        [Range(0, 235959)]
        [Display(Name = "[W24] Вечер: окно сигналов, конец", Order = 24, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Время ЧЧММСС в поясе окон [M81], по времени открытия бара.")]
        public int DboEveningSignalEnd { get; set; }

        [NinjaScriptProperty]
        [Range(0, 235959)]
        [Display(Name = "[W25] Вечер: выход по времени", Order = 25, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Время ЧЧММСС в поясе окон [M81], по времени открытия бара. Выход — принудительное закрытие позиции сессии.")]
        public int DboEveningSessionEnd { get; set; }

        [NinjaScriptProperty]
        [Range(1.0, 10000.0)]
        [Display(Name = "[W26] Вечер: трейлинг, тиков", Order = 26, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Расстояние трейлинга сделок этой сессии. Передаётся финансовому модулю с сигналом.")]
        public double DboEveningTrailTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 10000.0)]
        [Display(Name = "[W31] Ширина базы, минимум, тиков", Order = 31, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Уже — рынок спит, вход запрещён.")]
        public double DboMinRangeTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 10000.0)]
        [Display(Name = "[W32] Ширина базы, максимум, тиков", Order = 32, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Шире — рынок перерастянут, вход запрещён.")]
        public double DboMaxRangeTicks { get; set; }

        [NinjaScriptProperty]
        [Range(1, 1000)]
        [Display(Name = "[W33] Минимум баров базы", Order = 33, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Меньше — данные неполны, сессия блокируется.")]
        public int DboMinBaseBars { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 5.0)]
        [Display(Name = "[W34] Порог NormVol", Order = 34, GroupName = "8 · Пробой: окна и фильтры",
            Description = "ATR быстрый / ATR медленный на 15M ниже порога — боковик, вход запрещён.")]
        public double DboFlatThreshold { get; set; }

        [NinjaScriptProperty]
        [Range(1, 500)]
        [Display(Name = "[W35] ATR быстрый, баров 15M", Order = 35, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Простая средняя истинного диапазона.")]
        public int DboAtrFast { get; set; }

        [NinjaScriptProperty]
        [Range(1, 500)]
        [Display(Name = "[W36] ATR медленный, баров 15M", Order = 36, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Простая средняя истинного диапазона.")]
        public int DboAtrSlow { get; set; }

        [NinjaScriptProperty]
        [Range(2, 200)]
        [Display(Name = "[W37] Баров 4H для наклона", Order = 37, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Число доходностей закрытых баров 4H в расчёте направления.")]
        public int DboTrendBars { get; set; }

        [NinjaScriptProperty]
        [Range(0, 100)]
        [Display(Name = "[W38] Отступ входа от границы базы, тиков", Order = 38, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Стоп-ордер ставится на экстремум базы плюс отступ.")]
        public int DboEntryOffsetTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0, 100)]
        [Display(Name = "[W39] Предел входов за сессию", Order = 39, GroupName = "8 · Пробой: окна и фильтры",
            Description = "0 — без ограничения. Повторный вход — только после возврата цены за уровень.")]
        public int DboMaxEntries { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[W40] Направление вечера", Order = 40, GroupName = "8 · Пробой: окна и фильтры",
            Description = "DayTrend — по тренду дня, как в исследовании. H4 — по наклону 4H. Both — оба обязаны совпасть.")]
        public SwEveningDir DboEveningDir { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[W41] Закрывать позицию по окончании сессии", Order = 41, GroupName = "8 · Пробой: окна и фильтры",
            Description = "Выход по времени [W15] и [W25].")]
        public bool DboCloseAtSessionEnd { get; set; }

        #endregion

        [NinjaScriptProperty]
        [Display(Name = "[F34] Безубыток и трейлинг по максимуму", Order = 34, GroupName = "5 · Финансовый модуль",
            Description = "Включено — порог безубытка и включения трейлинга считается по лучшей цене позиции (MFE), как в исследовании и контрольном бэктесте. Выключено — по закрытию бара, позже и реже.")]
        public bool BreakevenOnBestPrice { get; set; }

        #region Свойства — адаптивное ядро

        [NinjaScriptProperty]
        [Display(Name = "[MOD9] Слот 9 — адаптивное ядро", Order = 19, GroupName = "1 · Слоты модулей",
            Description = "Локальная линейная регрессия цены с ядром компактного носителя. Роль — фильтр, либо сигнал при [K65].")]
        public bool Slot9Enabled { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[K50] Ядро", Order = 50, GroupName = "9 · Адаптивное ядро",
            Description = "Epanechnikov — минимальная среднеквадратичная ошибка. Остальные отличаются по эффективности на 1–2%. Автовыбор по таймфрейму не предусмотрен: запаздывание определяет ширина окна и тип регрессии, а не форма ядра.")]
        public SwKernelType KerKernel { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[K51] Тип регрессии", Order = 51, GroupName = "9 · Адаптивное ядро",
            Description = "LocalLinear — локальная прямая, без смещения на краю при линейном тренде. NadarayaWatson — взвешенное среднее; на тренде отстаёт на несколько баров.")]
        public SwRegressionType KerRegression { get; set; }

        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[K52] Слот серии", Order = 52, GroupName = "9 · Адаптивное ядро",
            Description = "0 — график, 1–4 — слоты пула [S50]–[S80]. Подгонка — на закрытии бара этой серии.")]
        public int KerSlot { get; set; }

        [NinjaScriptProperty]
        [Range(5, 200)]
        [Display(Name = "[K53] Ширина окна, баров", Order = 53, GroupName = "9 · Адаптивное ядро",
            Description = "Базовая ширина носителя ядра.")]
        public int KerBandwidth { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[K54] Адаптивная ширина окна", Order = 54, GroupName = "9 · Адаптивное ядро",
            Description = "Окно умножается на ATR(20)/ATR(5) в пределах 0,5–2: при всплеске волатильности короче, в затишье длиннее.")]
        public bool KerAdaptive { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[K55] Вес по объёму", Order = 55, GroupName = "9 · Адаптивное ядро",
            Description = "Множитель веса 1 + γ·z, ограниченный от 0,1 до 4. Выключено: тяготение подгонки к барам с высоким объёмом — обычно к новостным всплескам — не проверено.")]
        public bool KerVolumeWeighting { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 5.0)]
        [Display(Name = "[K56] Множитель γ веса объёма", Order = 56, GroupName = "9 · Адаптивное ядро",
            Description = "0 — вес не зависит от объёма.")]
        public double KerVolumeGamma { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[K57] Нормировка объёма", Order = 57, GroupName = "9 · Адаптивное ядро",
            Description = "Robust — медиана и MAD, не искажается одиночными всплесками. Standard — среднее и СКО.")]
        public SwVolumeScale KerVolumeScale { get; set; }

        [NinjaScriptProperty]
        [Range(5, 500)]
        [Display(Name = "[K58] Окно статистики объёма, баров", Order = 58, GroupName = "9 · Адаптивное ядро",
            Description = "По скольким барам считаются центр и разброс объёма.")]
        public int KerVolumeWindow { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 10.0)]
        [Display(Name = "[K59] Порог наклона, тиков на бар", Order = 59, GroupName = "9 · Адаптивное ядро",
            Description = "Ниже — нейтраль; выше — согласие в сторону наклона, вход против него запрещается.")]
        public double KerSlopeThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[K60] Действие при развороте наклона против позиции", Order = 60, GroupName = "9 · Адаптивное ядро",
            Description = "Neutral — только запись в трассировку. Veto — запрет нового входа, пока разворот длится. RequestPartialExit — требование закрыть 2/3 позиции один раз за эпизод; не проверено на истории.")]
        public SwKernelDivergenceAction KerDivergence { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[K61] Значимость наклона", Order = 61, GroupName = "9 · Адаптивное ядро",
            Description = "Направление учитывается, только если t-статистика наклона выше [K62]. t приближённая: остатки автокоррелированы, и значимость завышена. ЭКСПЕРИМЕНТ: выключено по умолчанию, требует проверки на истории.")]
        public bool KerExpTGate { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 20.0)]
        [Display(Name = "[K62] Порог t-статистики", Order = 62, GroupName = "9 · Адаптивное ядро",
            Description = "Для [K61].")]
        public double KerExpTMin { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[K63] Пересечение быстрой и медленной прямых", Order = 63, GroupName = "9 · Адаптивное ядро",
            Description = "Направление — знак разности быстрой (окно вдвое короче) и медленной прямых вместо знака наклона. ЭКСПЕРИМЕНТ: выключено по умолчанию, требует проверки на истории.")]
        public bool KerExpFastSlow { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[K64] Самопроверка предсказательной силы", Order = 64, GroupName = "9 · Адаптивное ядро",
            Description = "Прогноз прямой на бар вперёд сравнивается с наивным «цена не изменится». Не лучше наивного — модуль уходит в нейтраль. На случайном блуждании наивный прогноз оптимален. ЭКСПЕРИМЕНТ: выключено по умолчанию, требует проверки на истории.")]
        public bool KerExpSkill { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[K65] Режим сигнала", Order = 65, GroupName = "9 · Адаптивное ядро",
            Description = "Выключено — роль фильтра. Включено — роль сигнала: модуль голосует за направление наравне с другими сигнальными модулями.")]
        public bool KerSignalMode { get; set; }

        #endregion

        #region Свойства — классификатор Лоренца

        [NinjaScriptProperty]
        [Display(Name = "[L17] Метод решения", Order = 17, GroupName = "10 · Классификатор Лоренца",
            Description = "KnnVote — K ближайших, голос по знаку исхода. NadarayaWatson — взвешенное ядром среднее будущей доходности всех допустимых ситуаций. Consensus — направление, только если оба согласны.")]
        public SwLorentzMethod LorMethod { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[L18] Ядро Надарая–Ватсона", Order = 18, GroupName = "10 · Классификатор Лоренца",
            Description = "Gaussian по умолчанию; компактные ядра обнуляют дальние ситуации.")]
        public SwKernelType LorNwKernel { get; set; }

        [NinjaScriptProperty]
        [Range(0.05, 10.0)]
        [Display(Name = "[L19] Ширина ядра, доля медианы расстояний", Order = 19, GroupName = "10 · Классификатор Лоренца",
            Description = "σ ядра = множитель × медиана расстояний Лоренца. Меньше — решение по ближайшим, больше — по всем.")]
        public double LorNwBandMult { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 5.0)]
        [Display(Name = "[L20] Порог прогноза, ATR", Order = 20, GroupName = "10 · Классификатор Лоренца",
            Description = "|прогноз доходности за H баров| в ATR ниже порога — нейтраль.")]
        public double LorNwThreshold { get; set; }

        [NinjaScriptProperty]
        [Range(1.0, 1000.0)]
        [Display(Name = "[L21] Минимальный эффективный объём", Order = 21, GroupName = "10 · Классификатор Лоренца",
            Description = "(Σw)²/Σw² ниже порога — нейтраль: решение держалось бы на одной-двух ситуациях.")]
        public double LorNwMinEff { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[MOD11] Слот 11 — классификатор Лоренца", Order = 21, GroupName = "1 · Слоты модулей",
            Description = "K ближайших по расстоянию Лоренца на нормализованных признаках. Роль — фильтр, подтверждающий входы; сигнал при [L12].")]
        public bool Slot11Enabled { get; set; }

        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[L01] Слот серии", Order = 1, GroupName = "10 · Классификатор Лоренца",
            Description = "0 — график, 1–4 — слоты пула.")]
        public int LorSlot { get; set; }

        [NinjaScriptProperty]
        [Range(100, 10000)]
        [Display(Name = "[L02] Окно поиска, баров", Order = 2, GroupName = "10 · Классификатор Лоренца",
            Description = "Сколько баров прошлого просматривается в поиске соседей.")]
        public int LorLookback { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "[L03] Число соседей K", Order = 3, GroupName = "10 · Классификатор Лоренца",
            Description = "Сколько ближайших ситуаций голосует.")]
        public int LorNeighbors { get; set; }

        [NinjaScriptProperty]
        [Range(1, 50)]
        [Display(Name = "[L04] Шаг выборки соседей", Order = 4, GroupName = "10 · Классификатор Лоренца",
            Description = "Соседние бары делят будущее окно и голосуют почти одинаково; шаг снижает эту зависимость.")]
        public int LorStride { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "[L05] Горизонт метки, баров", Order = 5, GroupName = "10 · Классификатор Лоренца",
            Description = "Метка соседа — знак приращения за H баров вперёд. Сосед допускается, только если его исход уже известен.")]
        public int LorHorizon { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "[L06] Порог перевеса голосов", Order = 6, GroupName = "10 · Классификатор Лоренца",
            Description = "Доля перевеса 0–1, ниже которой модуль нейтрален.")]
        public double LorVoteThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[L07] Нормализация Йео–Джонсона", Order = 7, GroupName = "10 · Классификатор Лоренца",
            Description = "λ по максимуму правдоподобия на прошлом окне; работает и с отрицательными значениями, в отличие от Бокса–Кокса.")]
        public bool LorYeoJohnson { get; set; }

        [NinjaScriptProperty]
        [Range(10, 5000)]
        [Display(Name = "[L08] Пересчёт нормализации, баров", Order = 8, GroupName = "10 · Классификатор Лоренца",
            Description = "Как часто пересчитываются параметры — только по прошлым данным.")]
        public int LorRefitBars { get; set; }

        [NinjaScriptProperty]
        [Range(50, 5000)]
        [Display(Name = "[L09] Окно нормализации, баров", Order = 9, GroupName = "10 · Классификатор Лоренца",
            Description = "По скольким барам оцениваются λ и масштаб.")]
        public int LorFitWindow { get; set; }

        [NinjaScriptProperty]
        [Range(0.000001, 100.0)]
        [Display(Name = "[L10] Калман: шум процесса Q", Order = 10, GroupName = "10 · Классификатор Лоренца",
            Description = "Больше — скорость реагирует быстрее.")]
        public double LorKalmanQ { get; set; }

        [NinjaScriptProperty]
        [Range(0.000001, 1000.0)]
        [Display(Name = "[L11] Калман: шум измерения R", Order = 11, GroupName = "10 · Классификатор Лоренца",
            Description = "Больше — фильтр сильнее сглаживает.")]
        public double LorKalmanR { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[L12] Режим сигнала", Order = 12, GroupName = "10 · Классификатор Лоренца",
            Description = "Выключено — фильтр; включено — голосует за направление как сигнал.")]
        public bool LorSignalMode { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[L13] Голос с гауссовым весом", Order = 13, GroupName = "10 · Классификатор Лоренца",
            Description = "Вес соседа exp(−d²/2h²) по расстоянию Лоренца вместо равного. ЭКСПЕРИМЕНТ: выключено по умолчанию.")]
        public bool LorExpKernelVote { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[L14] Самопроверка точности", Order = 14, GroupName = "10 · Классификатор Лоренца",
            Description = "Причинная скользящая точность против эталона «монетки» с той же частотой исхода; ниже порога или не выше эталона — нейтраль. ЭКСПЕРИМЕНТ: выключено по умолчанию.")]
        public bool LorExpPrecisionGate { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "[L15] Порог точности", Order = 15, GroupName = "10 · Классификатор Лоренца",
            Description = "Для [L14].")]
        public double LorExpPrecisionMin { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[L16] Согласие с адаптивным ядром", Order = 16, GroupName = "10 · Классификатор Лоренца",
            Description = "Направление против тренда [MOD9] — нейтраль. Требует включённого [MOD9]. ЭКСПЕРИМЕНТ: выключено по умолчанию.")]
        public bool LorExpAgreeKernel { get; set; }

        #endregion

        #region Свойства — ядро по Хёрсту

        [NinjaScriptProperty]
        [Display(Name = "[MOD10] Слот 10 — ядро с шириной по Хёрсту", Order = 20, GroupName = "1 · Слоты модулей",
            Description = "Ядерная регрессия MOD9 с шириной окна по исправленному показателю Хёрста. Роль — фильтр; сигнал при [H10].")]
        public bool Slot10Enabled { get; set; }

        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[H01] Слот серии", Order = 1, GroupName = "11 · Ядро по Хёрсту",
            Description = "0 — график, 1–4 — слоты пула.")]
        public int HkSlot { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[H02] Тип регрессии", Order = 2, GroupName = "11 · Ядро по Хёрсту",
            Description = "LocalLinear — без запаздывания на тренде; NadarayaWatson — отстаёт.")]
        public SwRegressionType HkRegression { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[H03] Ядро", Order = 3, GroupName = "11 · Ядро по Хёрсту",
            Description = "Епанечников по умолчанию.")]
        public SwKernelType HkKernel { get; set; }

        [NinjaScriptProperty]
        [Range(16, 4096)]
        [Display(Name = "[H04] Окно Хёрста, доходностей", Order = 4, GroupName = "11 · Ядро по Хёрсту",
            Description = "Разброс оценки при 128 — 0,08, равен эффекту режима. Для устойчивости — 256 и больше.")]
        public int HkHurstPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(3, 500)]
        [Display(Name = "[H05] Ширина окна, минимум", Order = 5, GroupName = "11 · Ядро по Хёрсту",
            Description = "Баров.")]
        public int HkMinBandwidth { get; set; }

        [NinjaScriptProperty]
        [Range(4, 1000)]
        [Display(Name = "[H06] Ширина окна, максимум", Order = 6, GroupName = "11 · Ядро по Хёрсту",
            Description = "Баров.")]
        public int HkMaxBandwidth { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "[H07] Хёрст, нижняя граница отображения", Order = 7, GroupName = "11 · Ядро по Хёрсту",
            Description = "H ниже — минимальная ширина.")]
        public double HkHLow { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "[H08] Хёрст, верхняя граница отображения", Order = 8, GroupName = "11 · Ядро по Хёрсту",
            Description = "H выше — максимальная ширина.")]
        public double HkHHigh { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "[H15] Уровень блуждания оценщика", Order = 15, GroupName = "11 · Ядро по Хёрсту",
            Description = "0,47 при окне 128 по моделированию; для другого окна — откалибровать на перемешанных данных.")]
        public double HkRwLevel { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 10.0)]
        [Display(Name = "[H09] Порог наклона, тиков на бар", Order = 9, GroupName = "11 · Ядро по Хёрсту",
            Description = "Ниже — нейтраль.")]
        public double HkSlopeThreshold { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[H10] Режим сигнала", Order = 10, GroupName = "11 · Ядро по Хёрсту",
            Description = "Выключено — фильтр.")]
        public bool HkSignalMode { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[H11] Шлюз блуждания", Order = 11, GroupName = "11 · Ядро по Хёрсту",
            Description = "H в полосе [H12] вокруг уровня блуждания — нейтраль. ЭКСПЕРИМЕНТ: выключено по умолчанию.")]
        public bool HkExpGate { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 0.5)]
        [Display(Name = "[H12] Полоса шлюза", Order = 12, GroupName = "11 · Ядро по Хёрсту",
            Description = "Для [H11].")]
        public double HkExpGateBand { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[H13] Обратное отображение", Order = 13, GroupName = "11 · Ядро по Хёрсту",
            Description = "Антиперсистентный рынок — окно шире. ЭКСПЕРИМЕНТ: выключено по умолчанию.")]
        public bool HkExpInverse { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[H14] Уверенность по Хёрсту", Order = 14, GroupName = "11 · Ядро по Хёрсту",
            Description = "Уверенность наклона умножается на силу персистентности. ЭКСПЕРИМЕНТ: выключено по умолчанию.")]
        public bool HkExpConfidence { get; set; }

        #endregion

        #region Свойства — сигнал с ПК

        [NinjaScriptProperty]
        [Display(Name = "[MOD12] Слот 12 — сигнал с ПК", Order = 22, GroupName = "1 · Слоты модулей",
            Description = "Сигнал, записанный Python на ПК. Ордеров с ПК нет. Устаревший сигнал закрывает вход.")]
        public bool Slot12Enabled { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[Q01] Файл сигнала", Order = 1, GroupName = "12 · Сигнал с ПК",
            Description = "Полный путь к файлу, который пишет DZ_PC_SignalBridge.py.")]
        public string FsPath { get; set; }

        [NinjaScriptProperty]
        [Range(1, 86400)]
        [Display(Name = "[Q02] Свежесть, секунд", Order = 2, GroupName = "12 · Сигнал с ПК",
            Description = "Сигнал старше — отвергается: ПК остановился.")]
        public int FsMaxAge { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "[Q03] Отставание, баров", Order = 3, GroupName = "12 · Сигнал с ПК",
            Description = "Сигнал с ПК всегда на бар позже; больше допуска — отвергается.")]
        public int FsMaxLag { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[Q04] Режим сигнала", Order = 4, GroupName = "12 · Сигнал с ПК",
            Description = "Выключено — фильтр.")]
        public bool FsSignalMode { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1.0)]
        [Display(Name = "[Q05] Минимальная уверенность", Order = 5, GroupName = "12 · Сигнал с ПК",
            Description = "Ниже — направление обнуляется.")]
        public double FsMinConfidence { get; set; }

        #endregion

        #region Свойства — настройки модулей

        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[M01] Структура: слот младшего ТФ", Order = 1, GroupName = "4 · Настройки модулей",
            Description = "Слот пула для младшего таймфрейма структуры.")]
        public int PacLowerSlot { get; set; }

        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[M02] Структура: слот старшего ТФ", Order = 2, GroupName = "4 · Настройки модулей",
            Description = "Слот пула для старшего таймфрейма.")]
        public int PacHigherSlot { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[M03] Структура: использовать старший ТФ", Order = 3, GroupName = "4 · Настройки модулей",
            Description = "Выключение оставляет только младшую структуру.")]
        public bool PacUseHigher { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "[M04] Структура: сила внутренней", Order = 4, GroupName = "4 · Настройки модулей",
            Description = "Баров слева и справа для подтверждения мелкой опорной точки. Задаёт запаздывание подтверждения.")]
        public int PacInternalStrength { get; set; }

        [NinjaScriptProperty]
        [Range(1, 200)]
        [Display(Name = "[M05] Структура: сила свинговой", Order = 5, GroupName = "4 · Настройки модулей",
            Description = "То же для крупной структуры. Больше значение — реже и надёжнее события, больше запаздывание.")]
        public int PacSwingStrength { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[M06] Структура: чем подтверждается пробой", Order = 6, GroupName = "4 · Настройки модулей",
            Description = "BarClose строже и надёжнее. BarExtreme раньше, но чаще ложно.")]
        public SwPacBreakBy PacBreakBy { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[M81] Пробой: часовой пояс окон", Order = 81, GroupName = "4 · Настройки модулей",
            Description = "В каком поясе заданы окна: база 06:00–06:59 и 17:00–17:59, сигналы 07:00–09:59 и 18:00–19:59, сброс 14:30 и 21:30. Chicago — пояс данных исследования, подтверждён. Berlin — отдельный профиль регламента: те же часы означают другую фазу рынка; запускается вторым экземпляром на втором счёте.")]
        public SwWindowZone DboWindowZone { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[M82] Пробой: утренняя сессия", Order = 82, GroupName = "4 · Настройки модулей",
            Description = "База 06:00–06:59, сигналы 07:00–09:59, сброс 14:30, трейлинг 15 тиков.")]
        public bool DboUseMorning { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[M83] Пробой: вечерняя сессия", Order = 83, GroupName = "4 · Настройки модулей",
            Description = "База 17:00–17:59, сигналы 18:00–19:59, сброс 21:30, трейлинг 10 тиков, направление обязано совпасть с трендом дня.")]
        public bool DboUseEvening { get; set; }

        [NinjaScriptProperty] [Range(0, 4)]
        [Display(Name = "[M84] Пробой: слот минутной серии", Order = 84, GroupName = "4 · Настройки модулей",
            Description = "Серия, по которой строится база и определяется пробой. Должна быть минутной.")]
        public int DboM1Slot { get; set; }

        [NinjaScriptProperty] [Range(0, 4)]
        [Display(Name = "[M85] Пробой: слот серии 15M", Order = 85, GroupName = "4 · Настройки модулей",
            Description = "Серия 15 минут для фильтра боковика NormVol.")]
        public int DboM15Slot { get; set; }

        [NinjaScriptProperty] [Range(0, 4)]
        [Display(Name = "[M86] Пробой: слот серии 4H", Order = 86, GroupName = "4 · Настройки модулей",
            Description = "Серия 240 минут для старшего контура направления.")]
        public int DboH4Slot { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[M07] Время: закрывать позицию на жёсткой границе", Order = 7, GroupName = "4 · Настройки модулей",
            Description = "Включено — в 22:30 по Берлину модуль времени требует закрыть открытую позицию. Выключено — только запрещаются новые входы, позиция остаётся до закрытия сессии. По умолчанию включено: удержание позиции через технический перерыв CME несёт риск разрыва.")]
        public bool TimeForceFlatten { get; set; }

        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[M11] Линии: слот линии 1", Order = 11, GroupName = "4 · Настройки модулей",
            Description = "Слот пула для первой линии.")]
        public int TrfpLine1Slot { get; set; }

        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[M12] Линии: слот линии 2", Order = 12, GroupName = "4 · Настройки модулей",
            Description = "Слот пула для второй линии.")]
        public int TrfpLine2Slot { get; set; }

        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[M13] Линии: слот линии 3", Order = 13, GroupName = "4 · Настройки модулей",
            Description = "Слот пула для третьей линии.")]
        public int TrfpLine3Slot { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[M14] Линии: использовать третью", Order = 14, GroupName = "4 · Настройки модулей",
            Description = "Выключение оставляет голосование двух линий.")]
        public bool TrfpUseLine3 { get; set; }

        [NinjaScriptProperty]
        [Range(2, 2000)]
        [Display(Name = "[M15] Линии: период сглаживания", Order = 15, GroupName = "4 · Настройки модулей",
            Description = "Период двойного сглаживания диапазона. Он же задаёт прогрев каждой линии.")]
        public int TrfpPeriod { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 50.0)]
        [Display(Name = "[M16] Линии: множитель ширины", Order = 16, GroupName = "4 · Настройки модулей",
            Description = "Ширина диапазона. Больше значение — реже развороты линии.")]
        public double TrfpMultiplier { get; set; }

        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[M21] Режим: слот серии", Order = 21, GroupName = "4 · Настройки модулей",
            Description = "Слот пула для расчёта отношения дисперсий.")]
        public int RegimeSlot { get; set; }

        [NinjaScriptProperty]
        [Range(30, 250)]
        [Display(Name = "[M22] Режим: длина окна", Order = 22, GroupName = "4 · Настройки модулей",
            Description = "Число приращений. При шестидесяти значимым признаётся отклонение около 0.26; при двадцати около 0.45, что практически недостижимо.")]
        public int RegimeWindow { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[M23] Режим: какой допускает вход", Order = 23, GroupName = "4 · Настройки модулей",
            Description = "PersistentOnly для трендовых входов, MeanRevertOnly для контртрендовых, Any выключает фильтр.")]
        public SwRegimeAllow RegimeAllow { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1000000.0)]
        [Display(Name = "[M31] Риск: дневной лимит убытка", Order = 31, GroupName = "4 · Настройки модулей",
            Description = "Ноль отключает. Валюта счёта.")]
        public double GuardDailyLoss { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 1000000.0)]
        [Display(Name = "[M32] Риск: дневной лимит прибыли", Order = 32, GroupName = "4 · Настройки модулей",
            Description = "Ноль отключает.")]
        public double GuardDailyProfit { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[M33] Риск: действие при пробитии", Order = 33, GroupName = "4 · Настройки модулей",
            Description = "BlockNewEntries или BlockAndFlatten.")]
        public SwGuardBreachAction GuardBreachAction { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[M34] Риск: поведение при перезапуске", Order = 34, GroupName = "4 · Настройки модулей",
            Description = "BlockUntilNextSession безопасно: история сделок экземпляра обнуляется при Disable и Enable, это проверено на сборке 8.1.8.")]
        public SwGuardRestartPolicy GuardRestartPolicy { get; set; }

        [NinjaScriptProperty]
        [Range(0, 4)]
        [Display(Name = "[M41] Адапт.стоп: слот серии", Order = 41, GroupName = "4 · Настройки модулей",
            Description = "Слот пула для расчёта линии.")]
        public int AStopSlot { get; set; }

        [NinjaScriptProperty]
        [Range(2, 200)]
        [Display(Name = "[M42] Адапт.стоп: период", Order = 42, GroupName = "4 · Настройки модулей",
            Description = "Период сглаживания истинного диапазона.")]
        public int AStopAtrPeriod { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[M43] Адапт.стоп: режим ширины", Order = 43, GroupName = "4 · Настройки модулей",
            Description = "Fixed или VolatilityBuckets по рангу волатильности.")]
        public SwAdaptiveWidth AStopWidthMode { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 50.0)]
        [Display(Name = "[M44] Адапт.стоп: множитель", Order = 44, GroupName = "4 · Настройки модулей",
            Description = "Действует при режиме Fixed.")]
        public double AStopFixedMultiplier { get; set; }

        [NinjaScriptProperty]
        [Range(1, 3)]
        [Display(Name = "[M51] Выход: номер линии", Order = 51, GroupName = "4 · Настройки модулей",
            Description = "Какая линия ведёт позицию: 1, 2 или 3.")]
        public int EscortLineNumber { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[M52] Выход: повод", Order = 52, GroupName = "4 · Настройки модулей",
            Description = "LineFlip, PriceCross или FlipOrCross.")]
        public SwEscortExitTrigger EscortTrigger { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "[M53] Выход: подтверждение, баров", Order = 53, GroupName = "4 · Настройки модулей",
            Description = "Сколько баров подряд линия держит встречное направление. Единица — реакция на первый разворот.")]
        public int EscortConfirmBars { get; set; }

        #endregion

        #region Свойства — решение

        [NinjaScriptProperty] [Display(Name = "[D01] Требовать согласия всех сигналов", Order = 1, GroupName = "2 · Решение",
            Description = "Включено — вход только при совпадении направления всех готовых модулей роли Signal. Выключено — решает знак суммы голосов.")]
        public bool RequireAllSignalsAgree { get; set; }

        [NinjaScriptProperty] [Range(0.0, 1.0)]
        [Display(Name = "[D02] Минимальная уверенность", Order = 2, GroupName = "2 · Решение",
            Description = "Порог средней уверенности по голосующим модулям. Ноль отключает проверку.")]
        public double MinConfidence { get; set; }

        [NinjaScriptProperty] [Display(Name = "[D03] Отсутствие вердикта фильтра блокирует вход", Order = 3, GroupName = "2 · Решение",
            Description = "Включено — если фильтр подключён, но вердикта не дал, вход запрещён. Выключено — молчание фильтра считается согласием.")]
        public bool FilterMissingBlocksEntry { get; set; }

        #endregion

        #region Свойства — исполнение

        [NinjaScriptProperty] [Display(Name = "[E01] Режим без отправки ордеров", Order = 1, GroupName = "3 · Исполнение",
            Description = "Включено — исполнитель только записывает намерения в трассировку, заявки не отправляются. Значение по умолчанию включено: боевой режим требует осознанного переключения.")]
        public bool DryRunMode { get; set; }

        [NinjaScriptProperty] [Range(1, 1000)]
        [Display(Name = "[E02] Объём по умолчанию", Order = 2, GroupName = "3 · Исполнение",
            Description = "Объём входа, когда модуль роли Sizing не подключён.")]
        public int DefaultQuantity { get; set; }

        [NinjaScriptProperty] [Range(1, 10000)]
        [Display(Name = "[E03] Стартовый стоп, тиков", Order = 3, GroupName = "3 · Исполнение",
            Description = "Защитный стоп, выставляемый исполнителем при входе.")]
        public int StopLossTicks { get; set; }

        [NinjaScriptProperty] [Range(0, 500)]
        [Display(Name = "[E04] Минимум баров в сделке", Order = 4, GroupName = "3 · Исполнение",
            Description = "Защита от закрытия на баре входа.")]
        public int MinBarsInTrade { get; set; }

        #endregion

        #region Свойства — финансовый модуль

        [NinjaScriptProperty]
        [Display(Name = "[F01] Режим расчёта объёма", Order = 1, GroupName = "5 · Финансовый модуль",
            Description = "FixedQuantity — брать [E02]. RiskMoneyPerTrade — от денежного бюджета риска. RiskPercentOfEquity — от процента расчётного капитала. В двух последних объём вычисляется как бюджет, делённый на полный риск контракта, и отказ при нехватке бюджета записывается в трассировку, а не игнорируется.")]
        public SwSizingMode SizingMode { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, double.MaxValue)]
        [Display(Name = "[F02] Бюджет риска на сделку", Order = 2, GroupName = "5 · Финансовый модуль",
            Description = "Деньги на одну сделку при режиме RiskMoneyPerTrade.")]
        public double RiskMoneyPerTrade { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, double.MaxValue)]
        [Display(Name = "[F03] Расчётный капитал", Order = 3, GroupName = "5 · Финансовый модуль",
            Description = "Ручное значение капитала при режиме RiskPercentOfEquity. Живой капитал счёта намеренно не читается: он недетерминирован между прогонами.")]
        public double AccountEquityReference { get; set; }

        [NinjaScriptProperty]
        [Range(0.01, 100.0)]
        [Display(Name = "[F04] Риск на сделку, процент", Order = 4, GroupName = "5 · Финансовый модуль",
            Description = "Доля расчётного капитала на одну сделку.")]
        public double RiskPercentOfEquity { get; set; }

        [NinjaScriptProperty]
        [Range(1, 1000)]
        [Display(Name = "[F05] Минимум контрактов", Order = 5, GroupName = "5 · Финансовый модуль",
            Description = "Расчётный объём ниже этого значения означает отказ от входа, а не округление вверх.")]
        public int MinQuantity { get; set; }

        [NinjaScriptProperty]
        [Range(1, 1000)]
        [Display(Name = "[F06] Максимум контрактов", Order = 6, GroupName = "5 · Финансовый модуль",
            Description = "Жёсткий верхний предел. Если он ниже, чем требует структура ступеней, часть ступеней не сработает.")]
        public int MaxQuantity { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 10000.0)]
        [Display(Name = "[F07] Издержки круга на контракт", Order = 7, GroupName = "5 · Финансовый модуль",
            Description = "Комиссия обеих сторон плюс биржевые сборы. Входит в полный риск контракта и в минимальный отступ безубытка.")]
        public double RoundTurnCostPerContract { get; set; }

        [NinjaScriptProperty]
        [Range(0, 1000)]
        [Display(Name = "[F08] Резерв на проскальзывание, тиков", Order = 8, GroupName = "5 · Финансовый модуль",
            Description = "Добавляется к риску контракта при расчёте объёма. Без него объём систематически завышается.")]
        public int SlippageReserveTicks { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[F11] Режим стартового стопа", Order = 11, GroupName = "5 · Финансовый модуль",
            Description = "FixedTicks — в тиках. PriceDollars — в долларах ДВИЖЕНИЯ ЦЕНЫ, не результата: для микрозолота с шагом 0.10 значение 25 даёт 250 тиков. AtrMultiple — множитель ATR.")]
        public SwStopMode StopMode { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 100000.0)]
        [Display(Name = "[F12] Стоп, долларов движения цены", Order = 12, GroupName = "5 · Финансовый модуль",
            Description = "Действует при режиме PriceDollars. Путаница этой величины с денежным результатом даёт ошибку на порядок.")]
        public double StopPriceDollars { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 50.0)]
        [Display(Name = "[F13] Множитель ATR для стопа", Order = 13, GroupName = "5 · Финансовый модуль",
            Description = "Действует при режиме AtrMultiple.")]
        public double StopAtrMultiple { get; set; }

        [NinjaScriptProperty]
        [Range(2, 500)]
        [Display(Name = "[F14] Период ATR", Order = 14, GroupName = "5 · Финансовый модуль",
            Description = "Общий для стопа и трейлинга. Индикатор создаётся один раз при загрузке данных.")]
        public int AtrPeriod { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[F21] Включить ступенчатую фиксацию", Order = 21, GroupName = "5 · Финансовый модуль",
            Description = "Частичное закрытие позиции по мере движения цены.")]
        public bool UseScaleOut { get; set; }

        [NinjaScriptProperty]
        [Range(1, 10)]
        [Display(Name = "[F22] Количество ступеней", Order = 22, GroupName = "5 · Финансовый модуль",
            Description = "Сколько раз позиция фиксируется частично.")]
        public int ScaleSteps { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[F23] Мера расстояния ступеней", Order = 23, GroupName = "5 · Финансовый модуль",
            Description = "FixedTicks и PriceDollars задают абсолютное расстояние. RMultiple задаёт его в долях начального риска: ступень при 1R означает, что заработано столько же, сколько поставлено. Это финансово корректная мера, не зависящая от инструмента.")]
        public SwStepDistanceMode StepDistanceMode { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100000)]
        [Display(Name = "[F24] Шаг ступени, тиков", Order = 24, GroupName = "5 · Финансовый модуль",
            Description = "Действует при режиме FixedTicks.")]
        public int StepFixedTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 100000.0)]
        [Display(Name = "[F25] Шаг ступени, долларов цены", Order = 25, GroupName = "5 · Финансовый модуль",
            Description = "Действует при режиме PriceDollars.")]
        public double StepPriceDollars { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 20.0)]
        [Display(Name = "[F26] Шаг ступени, долей R", Order = 26, GroupName = "5 · Финансовый модуль",
            Description = "Действует при режиме RMultiple. Значение 1.0 ставит первую ступень на расстоянии начального риска.")]
        public double StepRMultiple { get; set; }

        [NinjaScriptProperty]
        [Range(0, 1000)]
        [Display(Name = "[F27] Контрактов на первой ступени", Order = 27, GroupName = "5 · Финансовый модуль",
            Description = "Объём первой фиксации, независимый от деления остальной позиции. Ноль возвращает первую ступень под общее правило [F28].")]
        public int ContractsOnStep1 { get; set; }

        [NinjaScriptProperty]
        [Range(0, 1000)]
        [Display(Name = "[F28] Контрактов на ступень", Order = 28, GroupName = "5 · Финансовый модуль",
            Description = "Ноль означает автоматическое деление объёма с учётом остатка под линию.")]
        public int ContractsPerStep { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[F29] Оставлять остаток", Order = 29, GroupName = "5 · Финансовый модуль",
            Description = "Последний контракт не закрывается ступенями и ведётся трейлингом.")]
        public bool KeepRunner { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[F31] Режим безубытка", Order = 31, GroupName = "5 · Финансовый модуль",
            Description = "Off, AfterStep1, AfterStep2 или AtRMultiple. Учитываются ПОДТВЕРЖДЁННЫЕ ступени: отправленная, но не исполненная заявка безубыток не включает.")]
        public SwBreakevenMode BreakevenMode { get; set; }

        [NinjaScriptProperty]
        [Range(0, 10000)]
        [Display(Name = "[F32] Отступ безубытка, тиков", Order = 32, GroupName = "5 · Финансовый модуль",
            Description = "Смещение в сторону прибыли. Модуль автоматически поднимает его до величины, покрывающей издержки круга: при меньшем значении срабатывание безубыточного стопа даёт убыток. Предупреждение печатается при загрузке.")]
        public int BreakevenOffsetTicks { get; set; }

        [NinjaScriptProperty]
        [Range(0.01, 20.0)]
        [Display(Name = "[F33] Безубыток при R", Order = 33, GroupName = "5 · Финансовый модуль",
            Description = "Порог в долях начального риска при режиме AtRMultiple.")]
        public double BreakevenAtR { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[F41] Режим трейлинга", Order = 41, GroupName = "5 · Финансовый модуль",
            Description = "Off. FixedDistance — фиксированное расстояние от экстремума. AtrMultiple — множитель ATR от экстремума. StepLock — после ступени k стоп встаёт на уровень ступени k минус один; при первой ступени это цена входа.")]
        public SwTrailMode TrailMode { get; set; }

        [NinjaScriptProperty]
        [Range(0.0, 20.0)]
        [Display(Name = "[F42] Включать трейлинг при R", Order = 42, GroupName = "5 · Финансовый модуль",
            Description = "Порог в долях начального риска, ниже которого трейлинг не работает.")]
        public double TrailActivateAtR { get; set; }

        [NinjaScriptProperty]
        [Range(0.1, 50.0)]
        [Display(Name = "[F43] Множитель ATR для трейлинга", Order = 43, GroupName = "5 · Финансовый модуль",
            Description = "Действует при режиме AtrMultiple.")]
        public double TrailAtrMultiple { get; set; }

        [NinjaScriptProperty]
        [Display(Name = "[F51] Запретить перенос стопа после первой фиксации", Order = 51, GroupName = "5 · Финансовый модуль",
            Description = "Подавляет ОБЕ ветви: и безубыток, и трейлинг. Подавление одной делало бы запрет формальным, потому что защиту продолжает двигать вторая.")]
        public bool DisableStopMoveAfterStep1 { get; set; }

        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name = "[F53] Таймаут подтверждения ступени, баров", Order = 53, GroupName = "5 · Финансовый модуль",
            Description = "Сколько баров ждать подтверждения запрошенной ступени. По истечении запрос считается потерянным и очередь снимается с блокировки. Без таймаута ступень, отклонённая арбитражем, блокировала бы все следующие ступени до конца сделки.")]
        public int StepConfirmTimeoutBars { get; set; }

        [NinjaScriptProperty]
        [Range(0, 1000)]
        [Display(Name = "[F52] Минимум баров между переносами стопа", Order = 52, GroupName = "5 · Финансовый модуль",
            Description = "Антидребезг. Ноль разрешает перенос на каждом баре.")]
        public int MinBarsBetweenStopMoves { get; set; }

        #endregion

        #region Свойства — управление позицией

        [NinjaScriptProperty] [Display(Name = "[P01] Включить управление позицией", Order = 1, GroupName = "6 · Управление позицией (устаревшее)",
            Description = "Встроенный модуль сопровождения: безубыток и трейлинг. Требований на закрытие не порождает, только перенос стопа.")]
        public bool EnablePositionManager { get; set; }

        [NinjaScriptProperty] [Range(0, 10000)]
        [Display(Name = "[P02] Безубыток после, тиков", Order = 2, GroupName = "6 · Управление позицией (устаревшее)",
            Description = "УСТАРЕЛО. Оставлено для совместимости шаблонов. Управление безубытком перешло к [F31] и [F33].")]
        public int BreakevenAfterTicks { get; set; }

        [NinjaScriptProperty] [Range(0, 10000)]
        [Display(Name = "[P04] Трейлинг после, тиков", Order = 4, GroupName = "6 · Управление позицией (устаревшее)",
            Description = "УСТАРЕЛО. Управление трейлингом перешло к [F41] и [F42].")]
        public int TrailAfterTicks { get; set; }

        [NinjaScriptProperty] [Range(1, 10000)]
        [Display(Name = "[P05] Дистанция трейлинга, тиков", Order = 5, GroupName = "6 · Управление позицией (устаревшее)",
            Description = "Расстояние трейлинга в тиках при режиме [F41] FixedDistance.")]
        public int TrailDistanceTicks { get; set; }

        #endregion

        #region Свойства — диагностика

        [NinjaScriptProperty] [Display(Name = "[T01] Включить трассировку", Order = 1, GroupName = "7 · Диагностика",
            Description = "Кольцевой буфер событий: отправка, приём, потеря, отказ, решение. Основной инструмент разбора чёрного ящика.")]
        public bool EnableTracing { get; set; }

        [NinjaScriptProperty] [Display(Name = "[T02] Печатать трассировку в Output", Order = 2, GroupName = "7 · Диагностика",
            Description = "Дублирование каждой записи в окно Output. На длинных прогонах сильно замедляет — включать для разбора.")]
        public bool PrintTraceToOutput { get; set; }

        [NinjaScriptProperty] [Range(10, 5000)]
        [Display(Name = "[T03] Размер буфера трассировки", Order = 3, GroupName = "7 · Диагностика",
            Description = "Сколько последних событий хранить в памяти.")]
        public int TraceBufferSize { get; set; }

        [NinjaScriptProperty] [Range(0, 40)]
        [Display(Name = "[T04] Строк трассировки на панели", Order = 4, GroupName = "7 · Диагностика",
            Description = "Сколько последних событий показывать на панели.")]
        public int PanelTraceLines { get; set; }

        [NinjaScriptProperty] [Range(1, 1000)]
        [Display(Name = "[T05] Считать молчанием после, баров", Order = 5, GroupName = "7 · Диагностика",
            Description = "Сколько баров без отправки считать отказом модуля выдавать сигнал.")]
        public int SilentAfterBars { get; set; }

        [NinjaScriptProperty] [Display(Name = "[T10] Показывать панель", Order = 10, GroupName = "7 · Диагностика",
            Description = "Панель состояния: модули, здоровье, счётчики, решение, исполнение, трассировка.")]
        public bool ShowHubPanel { get; set; }

        [NinjaScriptProperty] [Display(Name = "[T11] Положение панели", Order = 11, GroupName = "7 · Диагностика",
            Description = "Угол графика.")]
        public TextPosition PanelPosition { get; set; }

        [NinjaScriptProperty] [Range(6, 24)]
        [Display(Name = "[T12] Размер шрифта", Order = 12, GroupName = "7 · Диагностика",
            Description = "Кегль моноширинного шрифта панели.")]
        public int PanelFontSize { get; set; }

        [XmlIgnore] [Display(Name = "[T21] Цвет исправного состояния", Order = 21, GroupName = "7 · Диагностика",
            Description = "Все модули работают.")]
        public Brush OkBrush { get; set; }
        [Browsable(false)] public string OkBrushSerialize
        { get { return new BrushConverter().ConvertToString(OkBrush); } set { OkBrush = (Brush)new BrushConverter().ConvertFromString(value); } }

        [XmlIgnore] [Display(Name = "[T22] Цвет предупреждения", Order = 22, GroupName = "7 · Диагностика",
            Description = "Прогрев, молчание или застой хотя бы одного модуля.")]
        public Brush WarnBrush { get; set; }
        [Browsable(false)] public string WarnBrushSerialize
        { get { return new BrushConverter().ConvertToString(WarnBrush); } set { WarnBrush = (Brush)new BrushConverter().ConvertFromString(value); } }

        [XmlIgnore] [Display(Name = "[T23] Цвет отказа", Order = 23, GroupName = "7 · Диагностика",
            Description = "Хотя бы один модуль бросил исключение.")]
        public Brush FaultBrush { get; set; }
        [Browsable(false)] public string FaultBrushSerialize
        { get { return new BrushConverter().ConvertToString(FaultBrush); } set { FaultBrush = (Brush)new BrushConverter().ConvertFromString(value); } }

        [XmlIgnore] [Display(Name = "[T24] Цвет простоя", Order = 24, GroupName = "7 · Диагностика",
            Description = "Модули выключены или не подключены.")]
        public Brush IdleBrush { get; set; }
        [Browsable(false)] public string IdleBrushSerialize
        { get { return new BrushConverter().ConvertToString(IdleBrush); } set { IdleBrush = (Brush)new BrushConverter().ConvertFromString(value); } }

        #endregion

        #region Внутренний доступ для исполнителя

        // Исполнитель — вложенный класс: только он имеет доступ к ордерному API
        // родителя. Вынесение его в отдельный файл потребовало бы открыть этот
        // доступ шире, чего архитектура не допускает.

        internal bool HubDryRun { get { return DryRunMode; } }
        internal int HubBreakevenAfter { get { return BreakevenAfterTicks; } }
        internal int HubBreakevenOffset { get { return BreakevenOffsetTicks; } }
        internal int HubTrailAfter { get { return TrailAfterTicks; } }
        internal int HubTrailDistance { get { return TrailDistanceTicks; } }
        /// <summary>
        /// Реализованный результат СТРАТЕГИИ, не счёта.
        ///
        /// Источник намеренно ограничен собственными сделками: ручная
        /// торговля и другие стратегии на том же счёте не должны закрывать
        /// исправную позицию этой.
        ///
        /// ОГРАНИЧЕНИЕ, ПОДТВЕРЖДЁННОЕ ЭМПИРИЧЕСКИ на сборке 8.1.8:
        /// история сделок экземпляра ОБНУЛЯЕТСЯ при Disable и Enable.
        /// Восстановить дневной результат после перезапуска невозможно;
        /// риск-модуль обязан это учитывать, а не делать вид, что помнит.
        /// </summary>
        internal double HubRealizedPnl
        {
            get
            {
                if (DryRunMode) return virtRealizedPnl;
                try { return SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit; }
                catch { return 0; }
            }
        }

        internal int HubRealizedTradeCount
        {
            get
            {
                if (DryRunMode) return 0;
                try { return SystemPerformance.AllTrades.Count; } catch { return 0; }
            }
        }

        internal bool HubIsFirstBarOfSession
        {
            get { try { return Bars != null && Bars.IsFirstBarOfSession; } catch { return false; } }
        }

        internal double HubPointValue
        {
            get
            {
                try { return Instrument.MasterInstrument.PointValue; } catch { return 1.0; }
            }
        }

        /// <summary>ATR в ТИКАХ. Создаётся один раз в DataLoaded.</summary>
        internal double HubAtrTicks
        {
            get
            {
                try
                {
                    if (hubAtr == null || TickSize <= 0) return 0;
                    return hubAtr[0] / TickSize;
                }
                catch { return 0; }
            }
        }
        private ATR hubAtr;
        internal int HubStopTicks { get { return StopLossTicks; } }

        /// <summary>
        /// ЕДИНЫЙ ИСТОЧНИК РАССТОЯНИЯ СТАРТОВОГО СТОПА.
        ///
        /// Прежде исполнитель ставил стоп всегда по [E03] в тиках, а
        /// финансовый модуль считал R через [F11] с долларами цены и ATR.
        /// При [F11] = AtrMultiple реальный стоп стоял на одном расстоянии,
        /// а объём рассчитывался под другое — позиция могла оказаться в разы
        /// крупнее задуманной. Теперь оба берут расстояние отсюда.
        /// </summary>
        internal double HubInitialStopTicks
        {
            get
            {
                if (fin != null)
                {
                    double t = fin.StopDistanceTicks();
                    if (t > 0 && !double.IsNaN(t)) return t;
                }
                return StopLossTicks;
            }
        }

        /// <summary>Фактический стоп по данным исполнителя. Единственный источник истины.</summary>
        internal double HubCurrentStop { get { return exec != null ? exec.CurrentStop : double.NaN; } }
        internal int HubMinBars { get { return MinBarsInTrade; } }

        internal Order HubEnter(int dir, int qty, string sig)
        {
            return dir > 0 ? EnterLong(execBip, qty, sig) : EnterShort(execBip, qty, sig);
        }

        /// <summary>
        /// Отложенный стоп-вход. Сигнатура проверена по руководству NinjaTrader:
        /// EnterLongStopMarket(int barsInProgressIndex, bool isLiveUntilCancelled,
        /// int quantity, double stopPrice, string signalName).
        /// isLiveUntilCancelled = false: ордер живёт, пока его подтверждают
        /// каждый бар; прекращение сигнала снимает вход по закрытию окна.
        /// </summary>
        internal Order HubEnterStop(int dir, int qty, double stopPrice, string sig)
        {
            return dir > 0 ? EnterLongStopMarket(execBip, false, qty, stopPrice, sig)
                           : EnterShortStopMarket(execBip, false, qty, stopPrice, sig);
        }

        internal Order HubExit(int dir, int qty, string sig, string fromSig)
        {
            return dir > 0 ? ExitLong(execBip, qty, sig, fromSig)
                           : ExitShort(execBip, qty, sig, fromSig);
        }

        internal void HubSetStop(string fromSig, double price)
        {
            SetStopLoss(fromSig, CalculationMode.Price, price, false);
        }

        internal double HubRoundTick(double p)
        {
            try { return Instrument.MasterInstrument.RoundToTickSize(p); } catch { return p; }
        }

        internal bool HubExitPending
        {
            get
            {
                try
                {
                    for (int i = Orders.Count - 1; i >= 0 && i >= Orders.Count - 30; i--)
                    {
                        Order o = Orders[i];
                        if (o == null) continue;
                        if (o.OrderState == OrderState.Working || o.OrderState == OrderState.Accepted
                            || o.OrderState == OrderState.Submitted)
                        {
                            if (o.Name != null && o.Name.StartsWith("SW_EXIT")) return true;
                        }
                    }
                }
                catch { }
                return false;
            }
        }

        #endregion
    }

    #region Исполнитель — ЕДИНСТВЕННАЯ точка ордеров

    /// <summary>
    /// ЕДИНСТВЕННЫЙ КЛАСС, ВЫСТАВЛЯЮЩИЙ ЗАЯВКИ.
    ///
    /// Ни ядро, ни подключаемые модули ордерных вызовов не содержат. Все
    /// обращения к EnterLong, ExitLong и SetStopLoss проходят здесь и нигде
    /// более. Это проверяемо машинным поиском по файлу.
    ///
    /// Арбитраж встроен: один выход на один бар серии исполнения, кто бы его
    /// ни инициировал. Слот такта занимает первый успевший источник.
    /// </summary>
    public class SwExecutionModule
    {
        private const string SigLong = "SW_LONG";
        private const string SigShort = "SW_SHORT";

        private readonly DZ_SW_Hub_S021 hub;

        private int lastExitBar = -1;
        private int entryBar = -1;
        private int side;
        private double lastStop = double.NaN;

        public int EntriesSent, ExitsSent, StopMoves, Rejected, ArbitrationBlocks;
        public string StatusText = "готов";

        public SwExecutionModule(DZ_SW_Hub_S021 h) { hub = h; }

        /// <summary>Разбор метки вида STEP3. Ноль означает «не ступень».</summary>
        private static int ParseStepTag(string tag)
        {
            if (string.IsNullOrEmpty(tag)) return 0;
            int i = tag.IndexOf("STEP", StringComparison.Ordinal);
            if (i < 0) return 0;
            int num;
            return int.TryParse(tag.Substring(i + 4), out num) ? num : 0;
        }

        /// <summary>Фактический стоп. Все прочие копии обязаны читать его отсюда.</summary>
        public double CurrentStop { get { return lastStop; } }

        public string SummaryText
        {
            get
            {
                return "входов " + EntriesSent + ", выходов " + ExitsSent
                     + ", переносов стопа " + StopMoves + ", отклонено " + Rejected
                     + ", блокировок арбитража " + ArbitrationBlocks;
            }
        }

        /// <summary>Запрос входа от ядра.</summary>
        public int StopEntriesArmed, StopEntryRefreshes;

        /// <summary>Вызывается ядром при исполнении виртуального стоп-входа.</summary>
        public void OnVirtualStopEntryFilled(int dir, double stopPx, int bar)
        {
            EntriesSent++;
            side = dir; entryBar = bar; lastStop = stopPx;
            StatusText = "DRY стоп-вход исполнен " + (dir > 0 ? "LONG" : "SHORT") + ", стоп " + stopPx.ToString("F2");
        }

        public void RequestEntry(int dir, int qty, int bar, string reason)
        {
            RequestEntry(dir, qty, bar, reason, double.NaN, double.NaN);
        }

        public void RequestEntry(int dir, int qty, int bar, string reason, double entryStop, double trailOverride)
        {
            if (hub.HubPositionSide != 0) { ArbitrationBlocks++; return; }
            if (qty < 1) qty = 1;

            hub.HubPendingTrailOverride = trailOverride > 0 ? trailOverride : double.NaN;

            // ---------- ОТЛОЖЕННЫЙ СТОП-ВХОД ----------
            if (entryStop > 0 && !double.IsNaN(entryStop))
            {
                double lvl = hub.HubRoundTick(entryStop);

                // Уровень обязан быть по нужную сторону рынка: стоп на покупку
                // выше цены, на продажу ниже. Иначе платформа отклонит ордер,
                // а если он уже пройден — это не вход на пробое, а погоня.
                double px = hub.HubClose(0);
                bool valid = dir > 0 ? lvl > px : lvl < px;
                if (!valid)
                {
                    StatusText = "стоп-вход пропущен: уровень " + lvl.ToString("F2") + " уже пройден ценой " + px.ToString("F2");
                    hub.HubTrace("EXEC", "STOP_ENTRY_SKIPPED", StatusText);
                    return;
                }

                if (hub.HubDryRun)
                {
                    hub.HubVirtualArmEntry(dir, qty, lvl, bar);
                    StopEntryRefreshes++;
                    StatusText = "DRY стоп-вход " + (dir > 0 ? "LONG" : "SHORT") + " @ " + lvl.ToString("F2");
                    return;
                }

                string ssig = dir > 0 ? SigLong : SigShort;
                double sdist = hub.HubInitialStopTicks * hub.HubTickSize;
                double sstop = hub.HubRoundTick(dir > 0 ? lvl - sdist : lvl + sdist);
                try
                {
                    // Защита задаётся до входа и отсчитывается от УРОВНЯ ВХОДА,
                    // а не от текущей цены: вход произойдёт на уровне.
                    hub.HubSetStop(ssig, sstop);
                    Order so = hub.HubEnterStop(dir, qty, lvl, ssig);
                    if (so == null) { Rejected++; hub.HubTrace("EXEC", "ENTRY_REJECTED", "стоп-вход не создан"); return; }

                    StopEntryRefreshes++;
                    lastStop = sstop; side = dir; entryBar = bar;
                    StatusText = "стоп-вход " + (dir > 0 ? "LONG" : "SHORT") + " @ " + lvl.ToString("F2") + ", стоп " + sstop.ToString("F2");
                }
                catch (Exception ex)
                {
                    Rejected++;
                    hub.HubTrace("EXEC", "ENTRY_FAULT", "стоп-вход: " + ex.Message);
                }
                return;
            }

            if (hub.HubDryRun)
            {
                EntriesSent++;
                side = dir; entryBar = bar;

                double px = hub.HubClose(0);
                double stopPx0 = hub.HubRoundTick(
                    dir > 0 ? px - hub.HubInitialStopTicks * hub.HubTickSize
                            : px + hub.HubInitialStopTicks * hub.HubTickSize);

                // Виртуальный вход прогоняет весь конвейер: финансовый модуль
                // получает подтверждение и начинает считать ступени, безубыток
                // и трейлинг ровно так же, как в бою.
                hub.HubVirtualOpen(dir, qty, px, bar);
                hub.HubVirtualSetStop(stopPx0);
                lastStop = stopPx0;

                StatusText = "DRY вход " + (dir > 0 ? "LONG" : "SHORT") + " x" + qty
                           + " @ " + px.ToString("F2") + ", стоп " + stopPx0.ToString("F2");
                hub.HubTrace("EXEC", "DRY_ENTRY", StatusText + " | " + reason);
                return;
            }

            string sig = dir > 0 ? SigLong : SigShort;
            double stopPx = hub.HubRoundTick(
                dir > 0 ? hub.HubClose(0) - hub.HubInitialStopTicks * hub.HubTickSize
                        : hub.HubClose(0) + hub.HubInitialStopTicks * hub.HubTickSize);

            try
            {
                hub.HubSetStop(sig, stopPx);
                Order o = hub.HubEnter(dir, qty, sig);

                if (o == null)
                {
                    Rejected++;
                    StatusText = "ОТКАЗ: заявка не создана";
                    hub.HubTrace("EXEC", "ENTRY_REJECTED", reason);
                    return;
                }

                EntriesSent++;
                side = dir; entryBar = bar; lastStop = stopPx;
                StatusText = "вход " + (dir > 0 ? "LONG" : "SHORT") + " x" + qty
                           + ", стоп " + stopPx.ToString("F2");
                hub.HubTrace("EXEC", "ENTRY_SENT", StatusText);
            }
            catch (Exception ex)
            {
                Rejected++;
                StatusText = "ИСКЛЮЧЕНИЕ: " + ex.Message;
                hub.HubTrace("EXEC", "ENTRY_FAULT", ex.Message);
            }
        }

        /// <summary>Обработка требования модуля Escort или Exit.</summary>
        public void Handle(SwAction a, int bar)
        {
            int pos = hub.HubPositionSide;
            if (pos == 0) return;

            // Общий арбитраж: один выход на бар.
            if (a.Kind == SwActionKind.FullExit || a.Kind == SwActionKind.PartialExit)
            {
                if (bar - entryBar < hub.HubMinBars) { ArbitrationBlocks++; return; }
                if (lastExitBar == bar)
                {
                    ArbitrationBlocks++;
                    hub.HubTrace("EXEC", "ARBITRATION", "выход уже инициирован на баре " + bar);
                    return;
                }
                if (hub.HubExitPending)
                {
                    ArbitrationBlocks++;
                    hub.HubTrace("EXEC", "ARBITRATION", "работает предыдущий выход");
                    return;
                }
            }

            switch (a.Kind)
            {
                case SwActionKind.MoveStop:
                {
                    if (double.IsNaN(a.Price) || a.Price <= 0) return;

                    // Стоп двигается ТОЛЬКО в сторону сокращения риска.
                    if (!double.IsNaN(lastStop))
                    {
                        bool better = pos > 0 ? a.Price > lastStop : a.Price < lastStop;
                        if (!better) return;
                    }

                    double px = hub.HubRoundTick(a.Price);

                    if (hub.HubDryRun)
                    {
                        StopMoves++; lastStop = px;
                        hub.HubVirtualSetStop(px);
                        StatusText = "DRY стоп → " + px.ToString("F2");
                        hub.HubTrace("EXEC", "DRY_STOP", StatusText + " | " + a.Reason);
                        return;
                    }

                    try
                    {
                        hub.HubSetStop(pos > 0 ? SigLong : SigShort, px);
                        StopMoves++; lastStop = px;
                        StatusText = "стоп → " + px.ToString("F2");
                        hub.HubTrace("EXEC", "STOP_MOVED", StatusText + " | " + a.Reason);
                    }
                    catch (Exception ex)
                    {
                        Rejected++;
                        hub.HubTrace("EXEC", "STOP_FAULT", ex.Message);
                    }
                    return;
                }

                case SwActionKind.PartialExit:
                case SwActionKind.FullExit:
                {
                    int qty = a.Kind == SwActionKind.FullExit
                        ? hub.HubPositionQty
                        : Math.Max(1, Math.Min(a.Quantity, hub.HubPositionQty - 1));

                    if (qty <= 0) return;

                    if (hub.HubDryRun)
                    {
                        ExitsSent++; lastExitBar = bar;
                        double fill = hub.HubClose(0);

                        if (a.Kind == SwActionKind.FullExit)
                        {
                            hub.HubVirtualClose("полный выход: " + a.Reason, fill);
                        }
                        else
                        {
                            // Номер ступени извлекается из метки: без него
                            // подтверждение не с чем связать, и финансовый
                            // модуль ждал бы его бесконечно.
                            int stepNum = ParseStepTag(a.Tag);
                            hub.HubVirtualPartial(stepNum, qty, fill);
                        }

                        StatusText = "DRY выход x" + qty + " (" + a.Kind + ")";
                        hub.HubTrace("EXEC", "DRY_EXIT", StatusText + " | " + a.Reason);
                        return;
                    }

                    try
                    {
                        string exitName = "SW_EXIT_" + a.Kind
                            + (string.IsNullOrEmpty(a.Tag) ? "" : "_" + a.Tag);

                        Order o = hub.HubExit(pos, qty, exitName,
                                              pos > 0 ? SigLong : SigShort);
                        if (o == null) { Rejected++; return; }

                        ExitsSent++; lastExitBar = bar;
                        StatusText = "выход x" + qty + " (" + a.Kind + ")";
                        hub.HubTrace("EXEC", "EXIT_SENT", StatusText + " | " + a.Reason);
                    }
                    catch (Exception ex)
                    {
                        Rejected++;
                        hub.HubTrace("EXEC", "EXIT_FAULT", ex.Message);
                    }
                    return;
                }
            }
        }
    }

    #endregion

    // Класс SwPositionManager удалён: его заменил SwFinancialManager
    // из файла DZ_SW_Financial_S021.cs. Простое сопровождение безубытком и
    // трейлингом вошло в него как частный случай.

}
