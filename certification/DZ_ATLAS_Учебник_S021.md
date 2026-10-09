# Стратегия S021 и терминал «Атлас» — учебник и план исследования параметров

**Версия:** 1.0 (2026-10-01) · **Сгенерирован** `DZ_BOOK_Generate.py` из `DZ_SW_Hub_S021.cs` (314 настроек), правил лаборатории и графа связей. Пересобирается после каждого изменения кода.

**Три уровня утверждений:** *механика* — из кода; *гипотеза* — следствие механики, требует проверки; *результат* — только из лаборатории. Учебник содержит первые два уровня; третий пишется аудитом лаборатории.


# Часть I. Теория

## Глава 1. Предмет и метод

Стратегия S021 — **модульная система принятия решений** на фьючерсах на золото и серебро. Её единица — не индикатор, а модуль с ролью: сигнал, фильтр, сопровождение, выход, объём. Коммутатор собирает голоса модулей в решение и исполняет его из единственной точки. Отсюда метод учебника: каждая настройка изучается **внутри своей роли**, и её влияние описывается через то, как она меняет поток решений.

Три уровня описания различаются строго:
1. **Механика** — что настройка делает в коде. Это факт, проверяемый чтением исходника.
2. **Поведенческая гипотеза** — как механика должна сказаться на сделках: числе, доле прибыльных, среднем выигрыше, просадке. Это следствие механики, но не измерение.
3. **Эмпирический результат** — что показала лаборатория на сертифицированных данных с поправкой на число испытаний. Только этот уровень даёт право менять рабочий шаблон.

## Глава 2. Рынок как объект: что известно и что неизвестно

**Известно** из минутного бара: открытие, максимум, минимум, закрытие, объём, время. **Неизвестно**: порядок максимума и минимума внутри бара, распределение объёма по цене внутри бара, очередь заявок. Отсюда постулат худшего пути: если стоп и цель достижимы в одном баре, первым считается неблагоприятное событие. Любая модель, «знающая» порядок внутри бара, систематически завышает результат.

**Сессия золота** (CME Globex) открывается в 17:00 по Чикаго, то есть в 00:00 по Берлину. Утренняя ликвидность Европы и открытие Нью-Йорка дают два окна направленного движения — на этом построен двойной пробой.

**Режимы.** Цена чередует направленные участки и участки возврата к среднему. Показатель Хёрста H > 0,5 говорит о персистентности, H < 0,5 — об антиперсистентности. Оценка H на коротком окне шумна: разброс ~0,08 при 128 доходностях сопоставим с самим эффектом режима (±0,06). Поэтому фильтры режима — гипотезы, требующие доказательства, а не очевидные улучшения.

## Глава 3. Двойной пробой — ядро входа

**База** — диапазон перед окном входа, снятый строго до начала окна. **Вход** — стоп-ордер за границей базы на минутной серии. **Фильтры базы:** ширина в тиках в коридоре `[W31]…[W32]`, длина базы не меньше `[W33]` баров, отношение быстрой и медленной волатильности ниже `[W34]` (база должна быть «плоской»). **Вечер** торгуется только по тренду дня.

**Механика риска.** Уровень входа — граница базы, поэтому широкая база означает дальний противоположный край: связь `max_range_ticks → stop_ticks` в графе. Безубыток на +15 тиков при стопе 200 — это 0,075R: доля сделок, закрытых около нуля, растёт, а доля прибыльных падает. Это структурное соотношение `stop/(stop+trigger)`.

**Поведенческие модели пробоя:**
- *ложный вынос* — пробой и возврат в базу; второй, истинный пробой — отдельная сделка (правило повторного входа `[W39]`);
- *пробой на сжатии* — плоская база перед новостью; фильтр плоскости повышает долю таких входов;
- *пробой на усталости* — широкая база в конце движения; верхняя граница ширины их отсекает.

## Глава 4. Ядерная регрессия и её родственники

**Адаптивное ядро (MOD9).** Локальная прямая или Надарая–Ватсон с ядром Епанечникова на последних h барах; наклон — направление. Ширина h — компромисс смещения и разброса: узкое окно следует шуму, широкое запаздывает. Адаптивная ширина меняет h по волатильности.

**Ядро по Хёрсту (MOD10)** — тот же вычислитель, ширина задаётся показателем Хёрста по нескольким масштабам с поправкой Аниса–Ллойда. Уровень блуждания этого оценщика при окне 128 — 0,47, а не 0,5.

**Классификатор Лоренца (MOD11)** — k ближайших соседей в пространстве признаков с расстоянием Лоренца `Σ ln(1+|x−y|)`, менее чувствительным к выбросам, чем евклидово. Сосед голосует, только если его исход уже известен (`i + H ≤ t`) — иначе заглядывание. Цель — доходность в единицах ATR.

## Глава 5. Канал Калмана, рычаг свечи, иерархическая масса

**Калман (MOD13)** оценивает скрытый уровень цены; полосы — неопределённость оценки. Пробой полосы — сигнал, наклон — выход. Период и ширина полос задают баланс между запаздыванием и ложными пробоями.

**Рычаг свечи (MOD14)** — голос кластеров объёма: где внутри свечи сосредоточен объём относительно её тела. Порог голоса в единицах z отсекает незначимые смещения.

**Иерархическая масса (MOD15)**: `P_true` — взвешенная по объёму цена окна; `P_synthetic` — среднее трёх таких цен разного разрешения (1, 5, 15 минут). Их разность — дрейф цены внутри окна с учётом объёма. Угол — монотонная функция наклона, решений не принимает.

## Глава 6. Риск, объём, выходы

**Начальный риск** `[E03]` задаёт масштаб: все прочие расстояния в тиках осмысленны только относительно него. **Безубыток** переводит стоп за цену входа после триггера; отступ покрывает издержки круга и проскальзывание. **Трейлинг** подтягивает стоп за ценой; трейлинг короче триггера безубытка подтягивает стоп выше безубытка сразу. **Охрана** ограничивает день: после предела потерь или прибыли входы закрыты.

## Глава 7. Статистика доказательства

**Переподгонка** — выбор параметров, удачных на истории случайно. Её цена растёт с числом испытаний N: лучший из N наборов без всякого преимущества даёт Шарп около `E[max] ≈ (1−γ)Φ⁻¹(1−1/N) + γΦ⁻¹(1−1/(Ne))` в единицах σ (Бейли, Лопес де Прадо). Для N = 100 это ~2,5σ.

**DSR** — вероятность, что лучший Шарп выше этого порога с учётом длины выборки, асимметрии и эксцесса. **PBO (CSCV)** — доля разбиений истории, где лучший на одной половине хуже медианы на другой. **Плато** — устойчивость к соседним значениям: оптимум, окружённый хорошими соседями, переносится в будущее лучше одиночного пика. **Проверка вперёд** — единственная проверка на данных, которых выбор не видел; её эффективность — отношение доходности вне выборки к доходности в выборке.

## Глава 8. Порядок исследования и его логика

Порядок этапов следует причинности: **структура и волатильность** определяют, какие базы вообще существуют; **ядра входа** — какие из них торгуются; **фильтры** — какие входы отсеиваются; **риск** — масштаб позиции; **выходы** — судьбу открытой позиции. Оптимизировать выходы раньше входов — значит подгонять выходы под поток входов, который ещё изменится.

Внутри этапа: **сначала режим разработчика** — изолированная сетка каждого параметра, чтобы увидеть форму отклика; **затем умный режим** — параметр вместе со связанными по графу, чтобы проверить, что оптимум не держится на одном соседе; **затем вся стратегия** — совместная узкая сетка подтверждённых параметров этапа ±1 шаг и проверка вперёд. Параметр, отклонённый на любом проходе, замораживается на текущем значении, а его ветка останавливается.


# Часть II. Меню стратегии

| Группа | Модуль | Назначение | Настроек |
|---|---|---|---|
| 00 | Пул серий данных | какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей | 13 |
| 01 | Слоты модулей | какие модули включены; включение — структурная гипотеза, а не числовой параметр | 15 |
| 02 | Решение | как голоса сигналов и фильтров сводятся в вход: пороги уверенности и согласия | 3 |
| 03 | Исполнение | режим без ордеров, стоп по умолчанию, серия исполнения | 4 |
| 04 | Настройки модулей | PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение | 78 |
| 05 | Финансовый модуль | объём, начальный риск, безубыток, трейлинг, ступени выхода | 31 |
| 06 | Управление позицией (устаревшее) | сохранено для совместимости шаблонов; не исследуется | 4 |
| 07 | Диагностика | журнал и панель; на торговлю не влияет | 12 |
| 08 | Пробой: окна и фильтры | двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг | 23 |
| 09 | Адаптивное ядро | ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11 | 19 |
| 10 | Классификатор Лоренца | ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон | 22 |
| 11 | Ядро по Хёрсту | ширина окна регрессии по показателю Хёрста | 15 |
| 12 | Сигнал с ПК | внешний сигнал файлом; инфраструктура | 5 |
| 13 | Визуализация | отрисовка событий модулей | 2 |
| 14 | Пульт реального времени | WebSocket, схема меню, пресеты | 5 |
| 15 | Канал Калмана | сглаженный уровень, полосы, пробой и выход по наклону | 32 |
| 16 | Рычаг свечи | голос кластеров объёма внутри свечи | 20 |
| 17 | Иерархическая масса | дрейф взвешенной по объёму цены по эшелонам 1, 5, 15 минут | 11 |

Классы: защитных 59, структурных 109, числовых 146.

# Часть III. Связи настроек

| A | B | Правило | Обоснование |
|---|---|---|---|
| `DboMinRangeTicks` | `DboMaxRangeTicks` | связь графа | границы одного окна допуска ширины базы |
| `DboMaxRangeTicks` | `StopLossTicks` | связь графа | уровень входа — граница базы; широкая база означает дальний противоположный край |
| `DboAtrFast` | `DboAtrSlow` | связь графа | NormVol — их отношение |
| `DboAtrFast` | `DboFlatThreshold` | связь графа | порог сравнивается с отношением, зависящим от обоих периодов |
| `DboAtrSlow` | `DboFlatThreshold` | связь графа | то же |
| `KalLowerSlot` | `KalHigherSlot` | KalLowerSlot < KalHigherSlot | пара Low/High: нижняя граница меньше верхней |
| `KalLowerSlot` | `KalHigherSlot` | KalLowerSlot < KalHigherSlot | пара Lower/Higher: нижняя граница меньше верхней |
| `HmExpSqueeze` | `HmExpSqueezeRatio` | HmExpSqueezeRatio действует при HmExpSqueeze = true | числовой параметр эксперимента без флага не влияет |
| `HmExpSqueeze` | `HmExpPersist` | HmExpPersist действует при HmExpSqueeze = true | числовой параметр эксперимента без флага не влияет |
| `PacLowInternalBos` | `PacHighInternalBos` | PacLowInternalBos < PacHighInternalBos | пара Low/High: нижняя граница меньше верхней |
| `PacLowInternalChoch` | `PacHighInternalChoch` | PacLowInternalChoch < PacHighInternalChoch | пара Low/High: нижняя граница меньше верхней |
| `PacLowInternalChochPlus` | `PacHighInternalChochPlus` | PacLowInternalChochPlus < PacHighInternalChochPlus | пара Low/High: нижняя граница меньше верхней |
| `PacLowSwingBos` | `PacHighSwingBos` | PacLowSwingBos < PacHighSwingBos | пара Low/High: нижняя граница меньше верхней |
| `PacLowSwingChoch` | `PacHighSwingChoch` | PacLowSwingChoch < PacHighSwingChoch | пара Low/High: нижняя граница меньше верхней |
| `PacLowSwingChochPlus` | `PacHighSwingChochPlus` | PacLowSwingChochPlus < PacHighSwingChochPlus | пара Low/High: нижняя граница меньше верхней |
| `KerAdaptMin` | `KerAdaptMax` | KerAdaptMin < KerAdaptMax | пара Min/Max: нижняя граница меньше верхней |
| `KalEntryWindowMin` | `KalEntryWindowMax` | KalEntryWindowMin < KalEntryWindowMax | пара Min/Max: нижняя граница меньше верхней |
| `KalEscortWindowMin` | `KalEscortWindowMax` | KalEscortWindowMin < KalEscortWindowMax | пара Min/Max: нижняя граница меньше верхней |
| `AStopMultiplierLowVol` | `AStopMultiplierHighVol` | AStopMultiplierLowVol < AStopMultiplierHighVol | пара Low/High: нижняя граница меньше верхней |
| `AStopLowVolPercentile` | `AStopHighVolPercentile` | AStopLowVolPercentile < AStopHighVolPercentile | пара Low/High: нижняя граница меньше верхней |
| `DboMinRangeTicks` | `DboMaxRangeTicks` | DboMinRangeTicks < DboMaxRangeTicks | пара Min/Max: нижняя граница меньше верхней |
| `DboAtrFast` | `DboAtrSlow` | DboAtrFast < DboAtrSlow | пара Fast/Slow: нижняя граница меньше верхней |
| `KerExpTGate` | `KerExpTMin` | KerExpTMin действует при KerExpTGate = true | числовой параметр эксперимента без флага не влияет |
| `KerExpFastSlow` | `KerExpTMin` | KerExpTMin действует при KerExpFastSlow = true | числовой параметр эксперимента без флага не влияет |
| `KerExpSkill` | `KerExpTMin` | KerExpTMin действует при KerExpSkill = true | числовой параметр эксперимента без флага не влияет |
| `LorExpKernelVote` | `LorExpPrecisionMin` | LorExpPrecisionMin действует при LorExpKernelVote = true | числовой параметр эксперимента без флага не влияет |
| `LorExpPrecisionGate` | `LorExpPrecisionMin` | LorExpPrecisionMin действует при LorExpPrecisionGate = true | числовой параметр эксперимента без флага не влияет |
| `LorExpAgreeKernel` | `LorExpPrecisionMin` | LorExpPrecisionMin действует при LorExpAgreeKernel = true | числовой параметр эксперимента без флага не влияет |
| `HkMinBandwidth` | `HkMaxBandwidth` | HkMinBandwidth < HkMaxBandwidth | пара Min/Max: нижняя граница меньше верхней |
| `HkHLow` | `HkHHigh` | HkHLow < HkHHigh | пара Low/High: нижняя граница меньше верхней |
| `HkExpGate` | `HkExpGateBand` | HkExpGateBand действует при HkExpGate = true | числовой параметр эксперимента без флага не влияет |
| `HkExpInverse` | `HkExpGateBand` | HkExpGateBand действует при HkExpInverse = true | числовой параметр эксперимента без флага не влияет |
| `HkExpConfidence` | `HkExpGateBand` | HkExpGateBand действует при HkExpConfidence = true | числовой параметр эксперимента без флага не влияет |
| `PacLowerSlot` | `PacHigherSlot` | PacLowerSlot < PacHigherSlot | пара Low/High: нижняя граница меньше верхней |
| `PacLowerSlot` | `PacHigherSlot` | PacLowerSlot < PacHigherSlot | пара Lower/Higher: нижняя граница меньше верхней |
| `MinQuantity` | `MaxQuantity` | MinQuantity < MaxQuantity | пара Min/Max: нижняя граница меньше верхней |

# Часть IV. План исследования — шаг за шагом

Каждый этап проходится в три волны: **(А) режим разработчика** — изолированная сетка каждого числового параметра по порядку ниже; **(Б) умный режим** — параметр со связанными; **(В) вся стратегия** — совместная узкая сетка подтверждённых параметров этапа ±1 шаг и проверка вперёд. Структурные параметры этапа проверяются после волны А как гипотезы «вкл/выкл» при подтверждённых числовых.

## Этап 1. Структура рынка и волатильность — 45 настроек

| Шаг | Настройка | Класс | Исполнитель | Сетка |
|---|---|---|---|---|
| 1.1 | `[M01] PacLowerSlot` | STRUCTURAL | — | [] |
| 1.2 | `[M02] PacHigherSlot` | STRUCTURAL | — | [] |
| 1.3 | `[M03] PacUseHigher` | STRUCTURAL | — | [False, True] |
| 1.4 | `[M04] PacInternalStrength` | NUMERIC | исполнитель модулей на ПК | [2, 3, 4, 6] |
| 1.5 | `[M05] PacSwingStrength` | NUMERIC | исполнитель модулей на ПК | [5, 8, 10, 15, 20] |
| 1.6 | `[M06] PacBreakBy` | STRUCTURAL | — | ['BarClose', 'BarExtreme'] |
| 1.7 | `[M07] TimeForceFlatten` | STRUCTURAL | — | [False, True] |
| 1.8 | `[M21] RegimeSlot` | STRUCTURAL | — | [] |
| 1.9 | `[M22] RegimeWindow` | NUMERIC | исполнитель модулей на ПК | [30, 45, 60, 90, 120] |
| 1.10 | `[M23] RegimeAllow` | STRUCTURAL | — | ['PersistentOnly', 'MeanRevertOnly', 'AnyExceptRan |
| 1.11 | `[M81] DboWindowZone` | STRUCTURAL | — | ['Berlin', 'Chicago', 'NewYork', 'London', 'Utc'] |
| 1.12 | `[M82] DboUseMorning` | STRUCTURAL | — | [False, True] |
| 1.13 | `[M83] DboUseEvening` | STRUCTURAL | — | [False, True] |
| 1.14 | `[M84] DboM1Slot` | STRUCTURAL | — | [] |
| 1.15 | `[M85] DboM15Slot` | STRUCTURAL | — | [] |
| 1.16 | `[M86] DboH4Slot` | STRUCTURAL | — | [] |
| 1.17 | `[M87] PacLowInternalBos` | STRUCTURAL | — | [False, True] |
| 1.18 | `[M88] PacLowInternalChoch` | STRUCTURAL | — | [False, True] |
| 1.19 | `[M89] PacLowInternalChochPlus` | STRUCTURAL | — | [False, True] |
| 1.20 | `[M90] PacLowSwingBos` | STRUCTURAL | — | [False, True] |
| 1.21 | `[M91] PacLowSwingChoch` | STRUCTURAL | — | [False, True] |
| 1.22 | `[M92] PacLowSwingChochPlus` | STRUCTURAL | — | [False, True] |
| 1.23 | `[M93] PacHighInternalBos` | STRUCTURAL | — | [False, True] |
| 1.24 | `[M94] PacHighInternalChoch` | STRUCTURAL | — | [False, True] |
| 1.25 | `[M95] PacHighInternalChochPlus` | STRUCTURAL | — | [False, True] |
| 1.26 | `[M96] PacHighSwingBos` | STRUCTURAL | — | [False, True] |
| 1.27 | `[M97] PacHighSwingChoch` | STRUCTURAL | — | [False, True] |
| 1.28 | `[M98] PacHighSwingChochPlus` | STRUCTURAL | — | [False, True] |
| 1.29 | `[M99] PacConfidenceBos` | NUMERIC | исполнитель модулей на ПК | [0.2, 0.3, 0.4, 0.5, 0.6] |
| 1.30 | `[M100] PacConfidenceChoch` | NUMERIC | исполнитель модулей на ПК | [0.325, 0.4875, 0.65, 0.8125, 0.975] |
| 1.31 | `[M101] PacConfidenceChochPlus` | NUMERIC | исполнитель модулей на ПК | [0.425, 0.6375, 0.85, 1.0625, 1.275] |
| 1.32 | `[M102] PacHigherTimeframeBonus` | NUMERIC | исполнитель модулей на ПК | [0.05, 0.075, 0.1, 0.125, 0.15] |
| 1.33 | `[M104] RegimeAggregationQ` | NUMERIC | исполнитель модулей на ПК | [1, 2, 3, 4] |
| 1.34 | `[M105] RegimeVarianceMode` | STRUCTURAL | — | ['HeteroskedasticRobust', 'Homoskedastic'] |
| 1.35 | `[M106] RegimeZThreshold` | NUMERIC | исполнитель модулей на ПК | [0.98, 1.47, 1.96, 2.45, 2.94] |
| 1.36 | `[M107] RegimeRequireDriftAgreement` | STRUCTURAL | — | [False, True] |
| 1.37 | `[M108] RegimeDriftZThreshold` | NUMERIC | исполнитель модулей на ПК | [0.98, 1.47, 1.96, 2.45, 2.94] |
| 1.38 | `[W42] DboM1BarMinutes` | NUMERIC | исполнитель модулей на ПК | [1, 2] |
| 1.39 | `[W31] DboMinRangeTicks` | NUMERIC | оптимизатор на ПК | [10, 15, 20] |
| 1.40 | `[W32] DboMaxRangeTicks` | NUMERIC | оптимизатор на ПК | [35, 45, 55, 65] |
| 1.41 | `[W33] DboMinBaseBars` | NUMERIC | оптимизатор на ПК | [40, 50, 55] |
| 1.42 | `[W35] DboAtrFast` | NUMERIC | оптимизатор на ПК | [10, 15, 20, 30] |
| 1.43 | `[W36] DboAtrSlow` | NUMERIC | оптимизатор на ПК | [30, 40, 60, 80] |
| 1.44 | `[W34] DboFlatThreshold` | NUMERIC | оптимизатор на ПК | [0.75, 0.8, 0.85, 0.9, 0.95] |
| 1.45 | `[W37] DboTrendBars` | NUMERIC | оптимизатор на ПК | [5, 8, 10, 15, 20] |

**Волна В этапа 1:** совместная сетка подтверждённых числовых параметров (18) ±1 шаг вокруг их подтверждённых значений; ограничения из Части III; проверка вперёд 180/45/30 дней; критерии — эффективность ≥ 0,60, PBO ≤ 0,25. Только после неё этап закрыт.

## Этап 2. Ядра сигналов входа — 84 настроек

| Шаг | Настройка | Класс | Исполнитель | Сетка |
|---|---|---|---|---|
| 2.1 | `[M11] TrfpLine1Slot` | STRUCTURAL | — | [] |
| 2.2 | `[M12] TrfpLine2Slot` | STRUCTURAL | — | [] |
| 2.3 | `[M13] TrfpLine3Slot` | STRUCTURAL | — | [] |
| 2.4 | `[M14] TrfpUseLine3` | STRUCTURAL | — | [False, True] |
| 2.5 | `[M15] TrfpPeriod` | NUMERIC | исполнитель модулей на ПК | [50, 75, 100, 150, 200] |
| 2.6 | `[M16] TrfpMultiplier` | NUMERIC | исполнитель модулей на ПК | [1.5, 2.25, 3.0, 3.75, 4.5] |
| 2.7 | `[M103] TrfpPeriodNeutralPolicy` | STRUCTURAL | — | ['CountsAsDisagree', 'CountsAsAgree'] |
| 2.8 | `[W11] DboMorningBaseStart` | NUMERIC | исполнитель модулей на ПК | [30000, 45000, 60000, 90000, 120000] |
| 2.9 | `[W12] DboMorningBaseEnd` | NUMERIC | исполнитель модулей на ПК | [32980, 49469, 65959, 98938, 131918] |
| 2.10 | `[W13] DboMorningSignalStart` | NUMERIC | исполнитель модулей на ПК | [35000, 52500, 70000, 105000, 140000] |
| 2.11 | `[W14] DboMorningSignalEnd` | NUMERIC | исполнитель модулей на ПК | [47980, 71969, 95959, 143938, 191918] |
| 2.12 | `[W15] DboMorningSessionEnd` | NUMERIC | исполнитель модулей на ПК | [71500, 107250, 143000, 214500, 235959] |
| 2.13 | `[W21] DboEveningBaseStart` | NUMERIC | исполнитель модулей на ПК | [85000, 127500, 170000, 235959] |
| 2.14 | `[W22] DboEveningBaseEnd` | NUMERIC | исполнитель модулей на ПК | [87980, 131969, 175959, 235959] |
| 2.15 | `[W23] DboEveningSignalStart` | NUMERIC | исполнитель модулей на ПК | [90000, 135000, 180000, 235959] |
| 2.16 | `[W24] DboEveningSignalEnd` | NUMERIC | исполнитель модулей на ПК | [97980, 146969, 195959, 235959] |
| 2.17 | `[W25] DboEveningSessionEnd` | NUMERIC | исполнитель модулей на ПК | [106500, 159750, 213000, 235959] |
| 2.18 | `[W38] DboEntryOffsetTicks` | NUMERIC | исполнитель модулей на ПК | [1, 2] |
| 2.19 | `[W39] DboMaxEntries` | NUMERIC | оптимизатор на ПК | [0, 1, 2, 3] |
| 2.20 | `[W40] DboEveningDir` | STRUCTURAL | — | ['DayTrend', 'H4', 'Both'] |
| 2.21 | `[W41] DboCloseAtSessionEnd` | STRUCTURAL | — | [False, True] |
| 2.22 | `[C01] KalRole` | STRUCTURAL | — | ['Filter', 'Signal'] |
| 2.23 | `[C02] KalLowerSlot` | STRUCTURAL | — | [] |
| 2.24 | `[C03] KalCurrentSlot` | STRUCTURAL | — | [] |
| 2.25 | `[C04] KalHigherSlot` | STRUCTURAL | — | [] |
| 2.26 | `[C05] KalPeriod` | NUMERIC | исполнитель модулей на ПК | [10, 15, 20, 30, 40] |
| 2.27 | `[C06] KalBandSigma` | NUMERIC | исполнитель модулей на ПК | [1.0, 1.5, 2.0, 2.5, 3.0] |
| 2.28 | `[C07] KalPolicy` | STRUCTURAL | — | ['TrendDirection', 'TrendOnly', 'NoRange'] |
| 2.29 | `[C08] KalBands` | STRUCTURAL | — | ['GaussianSemiDeviation', 'KalmanInnovation'] |
| 2.30 | `[C09] KalEntryWindowMin` | NUMERIC | исполнитель модулей на ПК | [5, 8, 10, 15, 20] |
| 2.31 | `[C10] KalEntryWindowMax` | NUMERIC | исполнитель модулей на ПК | [20, 30, 40, 60, 80] |
| 2.32 | `[C11] KalEscortWindowMin` | NUMERIC | исполнитель модулей на ПК | [15, 22, 30, 45, 60] |
| 2.33 | `[C12] KalEscortWindowMax` | NUMERIC | исполнитель модулей на ПК | [60, 90, 120, 180, 240] |
| 2.34 | `[C13] KalFlatTilt` | NUMERIC | исполнитель модулей на ПК | [0.2, 0.3, 0.4, 0.5, 0.6] |
| 2.35 | `[C14] KalSymmetryMax` | NUMERIC | исполнитель модулей на ПК | [0.15, 0.225, 0.3, 0.375, 0.45] |
| 2.36 | `[C15] KalRangeConfirmBars` | NUMERIC | исполнитель модулей на ПК | [1] |
| 2.37 | `[C16] KalTrendZ` | NUMERIC | исполнитель модулей на ПК | [1.5, 2.25, 3.0, 3.75, 4.5] |
| 2.38 | `[C17] KalTrendTilt` | NUMERIC | исполнитель модулей на ПК | [0.3, 0.45, 0.6, 0.75, 0.9] |
| 2.39 | `[C18] KalCompressionRatio` | NUMERIC | исполнитель модулей на ПК | [0.375, 0.5625, 0.75, 0.9375, 1.125] |
| 2.40 | `[C19] KalExpansionRatio` | NUMERIC | исполнитель модулей на ПК | [0.675, 1.0125, 1.35, 1.6875, 2.025] |
| 2.41 | `[C20] KalDirectionTf` | STRUCTURAL | — | ['Current', 'Higher'] |
| 2.42 | `[C21] KalEscortTf` | STRUCTURAL | — | ['Current', 'Higher'] |
| 2.43 | `[C22] KalRequireHigherAgreement` | STRUCTURAL | — | [False, True] |
| 2.44 | `[C23] KalSignalBars` | NUMERIC | исполнитель модулей на ПК | [1, 2] |
| 2.45 | `[C24] KalEscortStop` | STRUCTURAL | — | [False, True] |
| 2.46 | `[C25] KalStopOffsetTicks` | NUMERIC | исполнитель модулей на ПК | [1, 2, 3, 4] |
| 2.47 | `[C26] KalExitOnSlopeFlip` | STRUCTURAL | — | [False, True] |
| 2.48 | `[C27] KalExitConfirmBars` | NUMERIC | исполнитель модулей на ПК | [1, 2, 3, 4] |
| 2.49 | `[C28] KalResearch` | STRUCTURAL | — | [False, True] |
| 2.50 | `[C29] KalResearchHorizon` | NUMERIC | исполнитель модулей на ПК | [10, 15, 20, 30, 40] |
| 2.51 | `[C30] KalRangeHoldBars` | NUMERIC | исполнитель модулей на ПК | [5, 8, 10, 15, 20] |
| 2.52 | `[C31] KalWarmupPeriods` | NUMERIC | исполнитель модулей на ПК | [2, 3, 4, 6] |
| 2.53 | `[C32] KalProvisionalDisplay` | STRUCTURAL | — | [False, True] |
| 2.54 | `[B01] LevRole` | STRUCTURAL | — | ['Filter', 'Signal'] |
| 2.55 | `[B02] LevAnalysisSlot` | STRUCTURAL | — | [] |
| 2.56 | `[B03] LevClusterSlot` | STRUCTURAL | — | [] |
| 2.57 | `[B04] LevClusters` | NUMERIC | исполнитель модулей на ПК | [5, 8, 10, 15, 20] |
| 2.58 | `[B05] LevVoteZ` | NUMERIC | исполнитель модулей на ПК | [0.25, 0.375, 0.5, 0.625, 0.75] |
| 2.59 | `[B06] LevPolicy` | STRUCTURAL | — | ['DirectionOnly', 'BlockMiddle'] |
| 2.60 | `[B07] LevWeight` | STRUCTURAL | — | ['Volume', 'Ticks'] |
| 2.61 | `[B08] LevFulcrum` | STRUCTURAL | — | ['RangeMid', 'BodyMid'] |
| 2.62 | `[B09] LevMeasure` | STRUCTURAL | — | ['Both', 'Lever', 'MedianCenter'] |
| 2.63 | `[B10] LevSmoothCandles` | NUMERIC | исполнитель модулей на ПК | [2, 3, 4, 6] |
| 2.64 | `[B11] LevScaleWindow` | NUMERIC | исполнитель модулей на ПК | [25, 38, 50, 75, 100] |
| 2.65 | `[B12] LevSignalWithTrend` | STRUCTURAL | — | [False, True] |
| 2.66 | `[B13] LevTrendWindow` | NUMERIC | исполнитель модулей на ПК | [10, 15, 20, 30, 40] |
| 2.67 | `[B14] LevSignalBars` | NUMERIC | исполнитель модулей на ПК | [1, 2] |
| 2.68 | `[B15] LevExitAgainst` | STRUCTURAL | — | [False, True] |
| 2.69 | `[B16] LevExitConfirm` | NUMERIC | исполнитель модулей на ПК | [1, 2, 3, 4] |
| 2.70 | `[B17] LevMinHeightTicks` | NUMERIC | исполнитель модулей на ПК | [2, 3, 4, 5, 6, 8] |
| 2.71 | `[B18] LevFinalize` | STRUCTURAL | — | ['Auto', 'Exact', 'Fast'] |
| 2.72 | `[B19] LevResearch` | STRUCTURAL | — | [False, True] |
| 2.73 | `[B20] LevResearchHorizon` | NUMERIC | исполнитель модулей на ПК | [2, 4, 5, 8, 10] |
| 2.74 | `[G01] HmSlot` | STRUCTURAL | — | [] |
| 2.75 | `[G02] HmWindow` | NUMERIC | исполнитель модулей на ПК | [8, 11, 15, 22, 30] |
| 2.76 | `[G03] HmWeight5` | NUMERIC | исполнитель модулей на ПК | [0.5, 0.75, 1.0, 1.25, 1.5] |
| 2.77 | `[G04] HmWeight15` | NUMERIC | исполнитель модулей на ПК | [0.75, 1.125, 1.5, 1.875, 2.25] |
| 2.78 | `[G05] HmSignalMode` | STRUCTURAL | — | [False, True] |
| 2.79 | `[G06] HmPercentile` | NUMERIC | исполнитель модулей на ПК | [0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99] |
| 2.80 | `[G07] HmBiasThreshold` | NUMERIC | исполнитель модулей на ПК | [1.0, 1.5, 2.0, 2.5, 3.0] |
| 2.81 | `[G08] HmExpSqueeze` | STRUCTURAL | — | [False, True] |
| 2.82 | `[G09] HmExpSqueezeRatio` | NUMERIC | исполнитель модулей на ПК | [0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75] |
| 2.83 | `[G10] HmExpPersist` | NUMERIC | исполнитель модулей на ПК | [1] |
| 2.84 | `[G11] HmSqueezeLookback` | NUMERIC | исполнитель модулей на ПК | [50, 75, 100, 150, 200] |

**Волна В этапа 2:** совместная сетка подтверждённых числовых параметров (50) ±1 шаг вокруг их подтверждённых значений; ограничения из Части III; проверка вперёд 180/45/30 дней; критерии — эффективность ≥ 0,60, PBO ≤ 0,25. Только после неё этап закрыт.

## Этап 3. Статистические фильтры — 59 настроек

| Шаг | Настройка | Класс | Исполнитель | Сетка |
|---|---|---|---|---|
| 3.1 | `[D01] RequireAllSignalsAgree` | STRUCTURAL | — | [False, True] |
| 3.2 | `[D02] MinConfidence` | NUMERIC | исполнитель модулей на ПК | [0.0, 0.05, 0.1, 0.15] |
| 3.3 | `[D03] FilterMissingBlocksEntry` | STRUCTURAL | — | [False, True] |
| 3.4 | `[K50] KerKernel` | STRUCTURAL | — | ['Epanechnikov', 'Triangular', 'Tricube', 'Cosine' |
| 3.5 | `[K51] KerRegression` | STRUCTURAL | — | ['LocalLinear', 'NadarayaWatson'] |
| 3.6 | `[K52] KerSlot` | STRUCTURAL | — | [] |
| 3.7 | `[K53] KerBandwidth` | NUMERIC | исполнитель модулей на ПК | [10, 15, 20, 30, 40] |
| 3.8 | `[K54] KerAdaptive` | STRUCTURAL | — | [False, True] |
| 3.9 | `[K55] KerVolumeWeighting` | STRUCTURAL | — | [False, True] |
| 3.10 | `[K56] KerVolumeGamma` | NUMERIC | исполнитель модулей на ПК | [0.5, 0.75, 1.0, 1.25, 1.5] |
| 3.11 | `[K57] KerVolumeScale` | STRUCTURAL | — | ['Robust', 'Standard'] |
| 3.12 | `[K58] KerVolumeWindow` | NUMERIC | исполнитель модулей на ПК | [25, 38, 50, 75, 100] |
| 3.13 | `[K59] KerSlopeThreshold` | NUMERIC | исполнитель модулей на ПК | [0.25, 0.375, 0.5, 0.625, 0.75] |
| 3.14 | `[K60] KerDivergence` | STRUCTURAL | — | ['Neutral', 'Veto', 'RequestPartialExit'] |
| 3.15 | `[K61] KerExpTGate` | STRUCTURAL | — | [False, True] |
| 3.16 | `[K63] KerExpFastSlow` | STRUCTURAL | — | [False, True] |
| 3.17 | `[K64] KerExpSkill` | STRUCTURAL | — | [False, True] |
| 3.18 | `[K62] KerExpTMin` | NUMERIC | исполнитель модулей на ПК | [1.0, 1.5, 2.0, 2.5, 3.0] |
| 3.19 | `[K65] KerSignalMode` | STRUCTURAL | — | [False, True] |
| 3.20 | `[K66] KerAdaptMin` | NUMERIC | исполнитель модулей на ПК | [0.25, 0.375, 0.5, 0.625, 0.75] |
| 3.21 | `[K67] KerAdaptMax` | NUMERIC | исполнитель модулей на ПК | [1.0, 1.5, 2.0, 2.5, 3.0] |
| 3.22 | `[K68] KerSkillWindow` | NUMERIC | исполнитель модулей на ПК | [50, 75, 100, 150, 200] |
| 3.23 | `[L01] LorSlot` | STRUCTURAL | — | [] |
| 3.24 | `[L02] LorLookback` | NUMERIC | исполнитель модулей на ПК | [1000, 1500, 2000, 3000, 4000] |
| 3.25 | `[L03] LorNeighbors` | NUMERIC | исполнитель модулей на ПК | [8, 12, 16, 24, 32] |
| 3.26 | `[L04] LorStride` | NUMERIC | исполнитель модулей на ПК | [2, 3, 4, 6, 8] |
| 3.27 | `[L05] LorHorizon` | NUMERIC | исполнитель модулей на ПК | [2, 3, 4, 6, 8] |
| 3.28 | `[L06] LorVoteThreshold` | NUMERIC | исполнитель модулей на ПК | [0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65] |
| 3.29 | `[L07] LorYeoJohnson` | STRUCTURAL | — | [False, True] |
| 3.30 | `[L08] LorRefitBars` | NUMERIC | исполнитель модулей на ПК | [50, 75, 100, 150, 200] |
| 3.31 | `[L09] LorFitWindow` | NUMERIC | исполнитель модулей на ПК | [250, 375, 500, 750, 1000] |
| 3.32 | `[L10] LorKalmanQ` | NUMERIC | исполнитель модулей на ПК | [0.005, 0.0075, 0.01, 0.0125, 0.015] |
| 3.33 | `[L11] LorKalmanR` | NUMERIC | исполнитель модулей на ПК | [0.5, 0.75, 1.0, 1.25, 1.5] |
| 3.34 | `[L12] LorSignalMode` | STRUCTURAL | — | [False, True] |
| 3.35 | `[L13] LorExpKernelVote` | STRUCTURAL | — | [False, True] |
| 3.36 | `[L14] LorExpPrecisionGate` | STRUCTURAL | — | [False, True] |
| 3.37 | `[L16] LorExpAgreeKernel` | STRUCTURAL | — | [False, True] |
| 3.38 | `[L15] LorExpPrecisionMin` | NUMERIC | исполнитель модулей на ПК | [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8] |
| 3.39 | `[L17] LorMethod` | STRUCTURAL | — | ['KnnVote', 'NadarayaWatson', 'Consensus'] |
| 3.40 | `[L18] LorNwKernel` | STRUCTURAL | — | ['Epanechnikov', 'Triangular', 'Tricube', 'Cosine' |
| 3.41 | `[L19] LorNwBandMult` | NUMERIC | исполнитель модулей на ПК | [0.25, 0.375, 0.5, 0.625, 0.75] |
| 3.42 | `[L20] LorNwThreshold` | NUMERIC | исполнитель модулей на ПК | [0.05, 0.075, 0.1, 0.125, 0.15] |
| 3.43 | `[L21] LorNwMinEff` | NUMERIC | исполнитель модулей на ПК | [5.0, 7.5, 10.0, 12.5, 15.0] |
| 3.44 | `[L22] LorEvalWindow` | NUMERIC | исполнитель модулей на ПК | [100, 150, 200, 300, 400] |
| 3.45 | `[H01] HkSlot` | STRUCTURAL | — | [] |
| 3.46 | `[H02] HkRegression` | STRUCTURAL | — | ['LocalLinear', 'NadarayaWatson'] |
| 3.47 | `[H03] HkKernel` | STRUCTURAL | — | ['Epanechnikov', 'Triangular', 'Tricube', 'Cosine' |
| 3.48 | `[H04] HkHurstPeriod` | NUMERIC | исполнитель модулей на ПК | [64, 96, 128, 192, 256] |
| 3.49 | `[H05] HkMinBandwidth` | NUMERIC | исполнитель модулей на ПК | [4, 6, 8, 12, 16] |
| 3.50 | `[H06] HkMaxBandwidth` | NUMERIC | исполнитель модулей на ПК | [20, 30, 40, 60, 80] |
| 3.51 | `[H07] HkHLow` | NUMERIC | исполнитель модулей на ПК | [0.22, 0.27, 0.32, 0.37, 0.42, 0.47, 0.52] |
| 3.52 | `[H08] HkHHigh` | NUMERIC | исполнитель модулей на ПК | [0.42, 0.47, 0.52, 0.57, 0.62, 0.67, 0.72] |
| 3.53 | `[H09] HkSlopeThreshold` | NUMERIC | исполнитель модулей на ПК | [0.25, 0.375, 0.5, 0.625, 0.75] |
| 3.54 | `[H10] HkSignalMode` | STRUCTURAL | — | [False, True] |
| 3.55 | `[H11] HkExpGate` | STRUCTURAL | — | [False, True] |
| 3.56 | `[H13] HkExpInverse` | STRUCTURAL | — | [False, True] |
| 3.57 | `[H14] HkExpConfidence` | STRUCTURAL | — | [False, True] |
| 3.58 | `[H12] HkExpGateBand` | NUMERIC | исполнитель модулей на ПК | [0.0, 0.03, 0.08, 0.13, 0.18] |
| 3.59 | `[H15] HkRwLevel` | NUMERIC | исполнитель модулей на ПК | [0.32, 0.37, 0.42, 0.47, 0.52, 0.57, 0.62] |

**Волна В этапа 3:** совместная сетка подтверждённых числовых параметров (31) ±1 шаг вокруг их подтверждённых значений; ограничения из Части III; проверка вперёд 180/45/30 дней; критерии — эффективность ≥ 0,60, PBO ≤ 0,25. Только после неё этап закрыт.

## Этап 4. Риск и объём — 29 настроек

| Шаг | Настройка | Класс | Исполнитель | Сетка |
|---|---|---|---|---|
| 4.1 | `[E03] StopLossTicks` | NUMERIC | оптимизатор на ПК | [100, 150, 200, 250, 300] |
| 4.2 | `[M31] GuardDailyLoss` | NUMERIC | Strategy Analyzer | [0.0] |
| 4.3 | `[M32] GuardDailyProfit` | NUMERIC | Strategy Analyzer | [0.0] |
| 4.4 | `[M33] GuardBreachAction` | STRUCTURAL | — | ['BlockNewEntries', 'BlockAndFlatten'] |
| 4.5 | `[M34] GuardRestartPolicy` | STRUCTURAL | — | ['BlockUntilNextSession', 'AssumeZeroPnl'] |
| 4.6 | `[M109] GuardUseDailyGuard` | STRUCTURAL | — | [False, True] |
| 4.7 | `[M110] GuardUseProfitLock` | STRUCTURAL | — | [False, True] |
| 4.8 | `[M111] GuardProfitLockArmAt` | NUMERIC | Strategy Analyzer | [0.0] |
| 4.9 | `[M112] GuardProfitLockGiveBackPct` | NUMERIC | Strategy Analyzer | [12.5, 18.75, 25.0, 31.25, 37.5] |
| 4.10 | `[M113] GuardUseNewsFilter` | STRUCTURAL | — | [False, True] |
| 4.11 | `[M114] GuardMinutesBefore` | NUMERIC | Strategy Analyzer | [8, 11, 15, 22, 30] |
| 4.12 | `[M115] GuardMinutesAfter` | NUMERIC | Strategy Analyzer | [15, 22, 30, 45, 60] |
| 4.13 | `[M116] GuardMinImpact` | NUMERIC | Strategy Analyzer | [2, 3, 4, 6] |
| 4.14 | `[M117] GuardMissingCalendarBlocks` | STRUCTURAL | — | [False, True] |
| 4.15 | `[F01] SizingMode` | STRUCTURAL | — | ['FixedQuantity', 'RiskMoneyPerTrade', 'RiskPercen |
| 4.16 | `[F02] RiskMoneyPerTrade` | NUMERIC | Strategy Analyzer | [0.0] |
| 4.17 | `[F03] AccountEquityReference` | NUMERIC | Strategy Analyzer | [0.0] |
| 4.18 | `[F04] RiskPercentOfEquity` | NUMERIC | Strategy Analyzer | [0.25, 0.375, 0.5, 0.625, 0.75] |
| 4.19 | `[F05] MinQuantity` | NUMERIC | Strategy Analyzer | [1, 2] |
| 4.20 | `[F06] MaxQuantity` | NUMERIC | Strategy Analyzer | [2, 4, 5, 8, 10] |
| 4.21 | `[F07] RoundTurnCostPerContract` | NUMERIC | Strategy Analyzer | [0.0] |
| 4.22 | `[F08] SlippageReserveTicks` | NUMERIC | Strategy Analyzer | [1, 2, 3, 4] |
| 4.23 | `[F11] StopMode` | STRUCTURAL | — | ['FixedTicks', 'PriceDollars', 'AtrMultiple'] |
| 4.24 | `[F12] StopPriceDollars` | NUMERIC | Strategy Analyzer | [0.0] |
| 4.25 | `[F13] StopAtrMultiple` | NUMERIC | Strategy Analyzer | [1.0, 1.5, 2.0, 2.5, 3.0] |
| 4.26 | `[F14] AtrPeriod` | NUMERIC | Strategy Analyzer | [7, 10, 14, 21, 28] |
| 4.27 | `[F21] UseScaleOut` | STRUCTURAL | — | [False, True] |
| 4.28 | `[F29] KeepRunner` | STRUCTURAL | — | [False, True] |
| 4.29 | `[F52] MinBarsBetweenStopMoves` | NUMERIC | Strategy Analyzer | [1] |

**Волна В этапа 4:** совместная сетка подтверждённых числовых параметров (19) ±1 шаг вокруг их подтверждённых значений; ограничения из Части III; проверка вперёд 180/45/30 дней; критерии — эффективность ≥ 0,60, PBO ≤ 0,25. Только после неё этап закрыт.

## Этап 5. Сопровождение и выходы — 38 настроек

| Шаг | Настройка | Класс | Исполнитель | Сетка |
|---|---|---|---|---|
| 5.1 | `[M41] AStopSlot` | STRUCTURAL | — | [] |
| 5.2 | `[M42] AStopAtrPeriod` | NUMERIC | Strategy Analyzer | [5, 8, 10, 15, 20] |
| 5.3 | `[M43] AStopWidthMode` | STRUCTURAL | — | ['Fixed', 'VolatilityBuckets'] |
| 5.4 | `[M44] AStopFixedMultiplier` | NUMERIC | Strategy Analyzer | [1.5, 2.25, 3.0, 3.75, 4.5] |
| 5.5 | `[M51] EscortLineNumber` | NUMERIC | Strategy Analyzer | [1, 2, 3] |
| 5.6 | `[M52] EscortTrigger` | STRUCTURAL | — | ['LineFlip', 'PriceCross', 'FlipOrCross'] |
| 5.7 | `[M53] EscortConfirmBars` | NUMERIC | Strategy Analyzer | [1, 2] |
| 5.8 | `[M118] AStopMultiplierLowVol` | NUMERIC | Strategy Analyzer | [1.0, 1.5, 2.0, 2.5, 3.0] |
| 5.9 | `[M119] AStopMultiplierMidVol` | NUMERIC | Strategy Analyzer | [1.5, 2.25, 3.0, 3.75, 4.5] |
| 5.10 | `[M120] AStopMultiplierHighVol` | NUMERIC | Strategy Analyzer | [2.0, 3.0, 4.0, 5.0, 6.0] |
| 5.11 | `[M121] AStopVolRankLookback` | NUMERIC | Strategy Analyzer | [50, 75, 100, 150, 200] |
| 5.12 | `[M122] AStopLowVolPercentile` | NUMERIC | Strategy Analyzer | [16.5, 24.75, 33.0, 41.25, 49.5] |
| 5.13 | `[M123] AStopHighVolPercentile` | NUMERIC | Strategy Analyzer | [33.5, 50.25, 67.0, 83.75, 100.5] |
| 5.14 | `[M124] AStopWarmupBars` | NUMERIC | Strategy Analyzer | [30, 45, 60, 90, 120] |
| 5.15 | `[M125] AStopRequireProtectiveSide` | STRUCTURAL | — | [False, True] |
| 5.16 | `[M126] AStopMinBarsBetweenRequests` | NUMERIC | Strategy Analyzer | [1, 2] |
| 5.17 | `[M127] EscortFullExit` | STRUCTURAL | — | [False, True] |
| 5.18 | `[M128] EscortPartialQuantity` | NUMERIC | Strategy Analyzer | [1, 2] |
| 5.19 | `[M129] EscortMinBarsInTrade` | NUMERIC | Strategy Analyzer | [1, 2] |
| 5.20 | `[M130] EscortStaleAfterBars` | NUMERIC | Strategy Analyzer | [25, 38, 50, 75, 100] |
| 5.21 | `[F22] ScaleSteps` | NUMERIC | Strategy Analyzer | [1, 2, 3, 4] |
| 5.22 | `[F23] StepDistanceMode` | STRUCTURAL | — | ['FixedTicks', 'PriceDollars', 'RMultiple'] |
| 5.23 | `[F24] StepFixedTicks` | NUMERIC | Strategy Analyzer | [20, 30, 40, 50, 60, 80] |
| 5.24 | `[F25] StepPriceDollars` | NUMERIC | Strategy Analyzer | [0.0] |
| 5.25 | `[F26] StepRMultiple` | NUMERIC | Strategy Analyzer | [0.5, 0.75, 1.0, 1.25, 1.5] |
| 5.26 | `[F27] ContractsOnStep1` | NUMERIC | Strategy Analyzer | [1, 2] |
| 5.27 | `[F28] ContractsPerStep` | NUMERIC | Strategy Analyzer | [1] |
| 5.28 | `[F31] BreakevenMode` | STRUCTURAL | — | ['Off', 'AfterStep1', 'AfterStep2', 'AtRMultiple'] |
| 5.29 | `[F32] BreakevenOffsetTicks` | NUMERIC | оптимизатор на ПК | [1, 2, 3] |
| 5.30 | `[F33] BreakevenAtR` | NUMERIC | Strategy Analyzer | [0.5, 0.75, 1.0, 1.25, 1.5] |
| 5.31 | `[F34] BreakevenOnBestPrice` | STRUCTURAL | — | [False, True] |
| 5.32 | `[F41] TrailMode` | STRUCTURAL | — | ['Off', 'FixedDistance', 'AtrMultiple', 'StepLock' |
| 5.33 | `[F42] TrailActivateAtR` | NUMERIC | Strategy Analyzer | [0.5, 0.75, 1.0, 1.25, 1.5] |
| 5.34 | `[F43] TrailAtrMultiple` | NUMERIC | Strategy Analyzer | [1.25, 1.875, 2.5, 3.125, 3.75] |
| 5.35 | `[F51] DisableStopMoveAfterStep1` | STRUCTURAL | — | [False, True] |
| 5.36 | `[F53] StepConfirmTimeoutBars` | NUMERIC | Strategy Analyzer | [2, 3, 4, 6] |
| 5.37 | `[W16] DboMorningTrailTicks` | NUMERIC | оптимизатор на ПК | [8, 10, 15, 20, 25, 30] |
| 5.38 | `[W26] DboEveningTrailTicks` | NUMERIC | оптимизатор на ПК | [6, 8, 10, 15, 20] |

**Волна В этапа 5:** совместная сетка подтверждённых числовых параметров (28) ±1 шаг вокруг их подтверждённых значений; ограничения из Части III; проверка вперёд 180/45/30 дней; критерии — эффективность ≥ 0,60, PBO ≤ 0,25. Только после неё этап закрыт.


# Часть V. Настройки — полное описание


## Этап 1. Структура рынка и волатильность

### Шаг 1.1 · [M01] PacLowerSlot — Структура: слот младшего ТФ

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула для младшего таймфрейма структуры.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacHigherSlot` — PacLowerSlot < PacHigherSlot; пара Low/High: нижняя граница меньше верхней.
- `PacHigherSlot` — PacLowerSlot < PacHigherSlot; пара Lower/Higher: нижняя граница меньше верхней.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.2 · [M02] PacHigherSlot — Структура: слот старшего ТФ

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 2. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула для старшего таймфрейма.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacLowerSlot` — PacLowerSlot < PacHigherSlot; пара Low/High: нижняя граница меньше верхней.
- `PacLowerSlot` — PacLowerSlot < PacHigherSlot; пара Lower/Higher: нижняя граница меньше верхней.

**Порядок:** исследуется после `PacLowerSlot`, `PacLowerSlot` — родитель должен быть VALIDATED.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.3 · [M03] PacUseHigher — Структура: использовать старший ТФ

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Выключение оставляет только младшую структуру.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.4 · [M04] PacInternalStrength — Структура: сила внутренней

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 3. **Пределы в коде:** 1.0 … 100.0.

**Механика (из кода):** Баров слева и справа для подтверждения мелкой опорной точки. Задаёт запаздывание подтверждения.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [2, 3, 4, 6] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[2, 3, 4, 6]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `PacInternalStrength` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.5 · [M05] PacSwingStrength — Структура: сила свинговой

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 10. **Пределы в коде:** 1.0 … 200.0.

**Механика (из кода):** То же для крупной структуры. Больше значение — реже и надёжнее события, больше запаздывание.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [5, 8, 10, 15, 20] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[5, 8, 10, 15, 20]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `PacSwingStrength` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.6 · [M06] PacBreakBy — Структура: чем подтверждается пробой

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** SwPacBreakBy. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwPacBreakBy.BarClose. **Пределы в коде:** — … —. **Значения:** BarClose, BarExtreme.

**Механика (из кода):** BarClose строже и надёжнее. BarExtreme раньше, но чаще ложно.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** BarClose, BarExtreme — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.7 · [M07] TimeForceFlatten — Время: закрывать позицию на жёсткой границе

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Включено — в 22:30 по Берлину модуль времени требует закрыть открытую позицию. Выключено — только запрещаются новые входы, позиция остаётся до закрытия сессии. По умолчанию включено: удержание позиции через технический перерыв CME несёт риск разрыва.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.8 · [M21] RegimeSlot — Режим: слот серии

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула для расчёта отношения дисперсий.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.9 · [M22] RegimeWindow — Режим: длина окна

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 60. **Пределы в коде:** 30.0 … 250.0.

**Механика (из кода):** Число приращений. При шестидесяти значимым признаётся отклонение около 0.26; при двадцати около 0.45, что практически недостижимо.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [30, 45, 60, 90, 120] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[30, 45, 60, 90, 120]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `RegimeWindow` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.10 · [M23] RegimeAllow — Режим: какой допускает вход

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** SwRegimeAllow. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwRegimeAllow.Any. **Пределы в коде:** — … —. **Значения:** PersistentOnly, MeanRevertOnly, AnyExceptRandomWalk, Any.

**Механика (из кода):** PersistentOnly для трендовых входов, MeanRevertOnly для контртрендовых, Any выключает фильтр.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** PersistentOnly, MeanRevertOnly, AnyExceptRandomWalk, Any — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.11 · [M81] DboWindowZone — Пробой: часовой пояс окон

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** SwWindowZone. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwWindowZone.Chicago. **Пределы в коде:** — … —. **Значения:** Berlin, Chicago, NewYork, London, Utc.

**Механика (из кода):** В каком поясе заданы окна: база 06:00–06:59 и 17:00–17:59, сигналы 07:00–09:59 и 18:00–19:59, сброс 14:30 и 21:30. Chicago — пояс данных исследования, подтверждён. Berlin — отдельный профиль регламента: те же часы означают другую фазу рынка; запускается вторым экземпляром на втором счёте.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Berlin, Chicago, NewYork, London, Utc — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.12 · [M82] DboUseMorning — Пробой: утренняя сессия

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** База 06:00–06:59, сигналы 07:00–09:59, сброс 14:30, трейлинг 15 тиков.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.13 · [M83] DboUseEvening — Пробой: вечерняя сессия

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** База 17:00–17:59, сигналы 18:00–19:59, сброс 21:30, трейлинг 10 тиков, направление обязано совпасть с трендом дня.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.14 · [M84] DboM1Slot — Пробой: слот минутной серии

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Серия, по которой строится база и определяется пробой. Должна быть минутной.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.15 · [M85] DboM15Slot — Пробой: слот серии 15M

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 3. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Серия 15 минут для фильтра боковика NormVol.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.16 · [M86] DboH4Slot — Пробой: слот серии 4H

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 4. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Серия 240 минут для старшего контура направления.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.17 · [M87] PacLowInternalBos — LowInternalBos

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.LowInternalBos: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacHighInternalBos` — PacLowInternalBos < PacHighInternalBos; пара Low/High: нижняя граница меньше верхней.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.18 · [M88] PacLowInternalChoch — LowInternalChoch

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.LowInternalChoch: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacHighInternalChoch` — PacLowInternalChoch < PacHighInternalChoch; пара Low/High: нижняя граница меньше верхней.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.19 · [M89] PacLowInternalChochPlus — LowInternalChochPlus

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.LowInternalChochPlus: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacHighInternalChochPlus` — PacLowInternalChochPlus < PacHighInternalChochPlus; пара Low/High: нижняя граница меньше верхней.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.20 · [M90] PacLowSwingBos — LowSwingBos

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.LowSwingBos: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacHighSwingBos` — PacLowSwingBos < PacHighSwingBos; пара Low/High: нижняя граница меньше верхней.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.21 · [M91] PacLowSwingChoch — LowSwingChoch

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.LowSwingChoch: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacHighSwingChoch` — PacLowSwingChoch < PacHighSwingChoch; пара Low/High: нижняя граница меньше верхней.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.22 · [M92] PacLowSwingChochPlus — LowSwingChochPlus

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.LowSwingChochPlus: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacHighSwingChochPlus` — PacLowSwingChochPlus < PacHighSwingChochPlus; пара Low/High: нижняя граница меньше верхней.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.23 · [M93] PacHighInternalBos — HighInternalBos

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.HighInternalBos: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacLowInternalBos` — PacLowInternalBos < PacHighInternalBos; пара Low/High: нижняя граница меньше верхней.

**Порядок:** исследуется после `PacLowInternalBos` — родитель должен быть VALIDATED.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.24 · [M94] PacHighInternalChoch — HighInternalChoch

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.HighInternalChoch: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacLowInternalChoch` — PacLowInternalChoch < PacHighInternalChoch; пара Low/High: нижняя граница меньше верхней.

**Порядок:** исследуется после `PacLowInternalChoch` — родитель должен быть VALIDATED.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.25 · [M95] PacHighInternalChochPlus — HighInternalChochPlus

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.HighInternalChochPlus: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacLowInternalChochPlus` — PacLowInternalChochPlus < PacHighInternalChochPlus; пара Low/High: нижняя граница меньше верхней.

**Порядок:** исследуется после `PacLowInternalChochPlus` — родитель должен быть VALIDATED.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.26 · [M96] PacHighSwingBos — HighSwingBos

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.HighSwingBos: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacLowSwingBos` — PacLowSwingBos < PacHighSwingBos; пара Low/High: нижняя граница меньше верхней.

**Порядок:** исследуется после `PacLowSwingBos` — родитель должен быть VALIDATED.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.27 · [M97] PacHighSwingChoch — HighSwingChoch

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.HighSwingChoch: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacLowSwingChoch` — PacLowSwingChoch < PacHighSwingChoch; пара Low/High: нижняя граница меньше верхней.

**Порядок:** исследуется после `PacLowSwingChoch` — родитель должен быть VALIDATED.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.28 · [M98] PacHighSwingChochPlus — HighSwingChochPlus

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.HighSwingChochPlus: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `PacLowSwingChochPlus` — PacLowSwingChochPlus < PacHighSwingChochPlus; пара Low/High: нижняя граница меньше верхней.

**Порядок:** исследуется после `PacLowSwingChochPlus` — родитель должен быть VALIDATED.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.29 · [M99] PacConfidenceBos — ConfidenceBos

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.40. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.ConfidenceBos: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.2, 0.3, 0.4, 0.5, 0.6] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.2, 0.3, 0.4, 0.5, 0.6]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `PacConfidenceBos` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.30 · [M100] PacConfidenceChoch — ConfidenceChoch

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.65. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.ConfidenceChoch: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.325, 0.4875, 0.65, 0.8125, 0.975] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.325, 0.4875, 0.65, 0.8125, 0.975]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `PacConfidenceChoch` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.31 · [M101] PacConfidenceChochPlus — ConfidenceChochPlus

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.85. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.ConfidenceChochPlus: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.425, 0.6375, 0.85, 1.0625, 1.275] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.425, 0.6375, 0.85, 1.0625, 1.275]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `PacConfidenceChochPlus` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.32 · [M102] PacHigherTimeframeBonus — HigherTimeframeBonus

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.10. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwPacConfig.HigherTimeframeBonus: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.05, 0.075, 0.1, 0.125, 0.15] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.05, 0.075, 0.1, 0.125, 0.15]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `PacHigherTimeframeBonus` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.33 · [M104] RegimeAggregationQ — AggregationQ

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 2. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwRegimeConfig.AggregationQ: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2, 3, 4] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2, 3, 4]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `RegimeAggregationQ` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.34 · [M105] RegimeVarianceMode — VarianceMode

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** SwRegimeVariance. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwRegimeVariance.HeteroskedasticRobust. **Пределы в коде:** — … —. **Значения:** HeteroskedasticRobust, Homoskedastic.

**Механика (из кода):** Поле SwRegimeConfig.VarianceMode: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** HeteroskedasticRobust, Homoskedastic — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.35 · [M106] RegimeZThreshold — ZThreshold

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1.96. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwRegimeConfig.ZThreshold: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.98, 1.47, 1.96, 2.45, 2.94] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.98, 1.47, 1.96, 2.45, 2.94]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `RegimeZThreshold` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.36 · [M107] RegimeRequireDriftAgreement — RequireDriftAgreement

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwRegimeConfig.RequireDriftAgreement: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 1.37 · [M108] RegimeDriftZThreshold — DriftZThreshold

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1.96. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwRegimeConfig.DriftZThreshold: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.98, 1.47, 1.96, 2.45, 2.94] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.98, 1.47, 1.96, 2.45, 2.94]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `RegimeDriftZThreshold` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.38 · [W42] DboM1BarMinutes — M1BarMinutes

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 1. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwDualBreakoutConfig.M1BarMinutes: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboM1BarMinutes` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.39 · [W31] DboMinRangeTicks — Ширина базы, минимум, тиков

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** double. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 15. **Пределы в коде:** 0.0 … 10000.0.

**Механика (из кода):** Уже — рынок спит, вход запрещён.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Слишком малое значение — срабатывания на шуме; слишком большое — механизм почти не срабатывает.

**Класс и исполнитель:** NUMERIC; оптимизатор на ПК. Эталонное имя: `min_range_ticks`.

**Связанные настройки:**

- `DboMaxRangeTicks` — связь графа; границы одного окна допуска ширины базы.
- `DboMaxRangeTicks` — DboMinRangeTicks < DboMaxRangeTicks; пара Min/Max: нижняя граница меньше верхней.

**Коридор и шаг:** [10, 15, 20] — правило: сетка графа эталона. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[10, 15, 20]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboMinRangeTicks` + `DboMaxRangeTicks`, `DboMaxRangeTicks` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.40 · [W32] DboMaxRangeTicks — Ширина базы, максимум, тиков

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** double. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 45. **Пределы в коде:** 0.0 … 10000.0.

**Механика (из кода):** Шире — рынок перерастянут, вход запрещён.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Слишком малое значение — срабатывания на шуме; слишком большое — механизм почти не срабатывает.

**Класс и исполнитель:** NUMERIC; оптимизатор на ПК. Эталонное имя: `max_range_ticks`.

**Связанные настройки:**

- `DboMinRangeTicks` — связь графа; границы одного окна допуска ширины базы.
- `StopLossTicks` — связь графа; уровень входа — граница базы; широкая база означает дальний противоположный край.
- `DboMinRangeTicks` — DboMinRangeTicks < DboMaxRangeTicks; пара Min/Max: нижняя граница меньше верхней.

**Порядок:** исследуется после `DboMinRangeTicks`, `DboMinRangeTicks` — родитель должен быть VALIDATED.

**Коридор и шаг:** [35, 45, 55, 65] — правило: сетка графа эталона. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[35, 45, 55, 65]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboMaxRangeTicks` + `DboMinRangeTicks`, `StopLossTicks`, `DboMinRangeTicks` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.41 · [W33] DboMinBaseBars — Минимум баров базы

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 50. **Пределы в коде:** 1.0 … 1000.0.

**Механика (из кода):** Меньше — данные неполны, сессия блокируется.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; оптимизатор на ПК. Эталонное имя: `min_base_bars`.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [40, 50, 55] — правило: сетка графа эталона. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[40, 50, 55]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboMinBaseBars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.42 · [W35] DboAtrFast — ATR быстрый, баров 15M

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 20. **Пределы в коде:** 1.0 … 500.0.

**Механика (из кода):** Простая средняя истинного диапазона.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; оптимизатор на ПК. Эталонное имя: `atr_fast`.

**Связанные настройки:**

- `DboAtrSlow` — связь графа; NormVol — их отношение.
- `DboFlatThreshold` — связь графа; порог сравнивается с отношением, зависящим от обоих периодов.
- `DboAtrSlow` — DboAtrFast < DboAtrSlow; пара Fast/Slow: нижняя граница меньше верхней.

**Коридор и шаг:** [10, 15, 20, 30] — правило: сетка графа эталона. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[10, 15, 20, 30]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboAtrFast` + `DboAtrSlow`, `DboFlatThreshold`, `DboAtrSlow` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.43 · [W36] DboAtrSlow — ATR медленный, баров 15M

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 40. **Пределы в коде:** 1.0 … 500.0.

**Механика (из кода):** Простая средняя истинного диапазона.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; оптимизатор на ПК. Эталонное имя: `atr_slow`.

**Связанные настройки:**

- `DboAtrFast` — связь графа; NormVol — их отношение.
- `DboFlatThreshold` — связь графа; то же.
- `DboAtrFast` — DboAtrFast < DboAtrSlow; пара Fast/Slow: нижняя граница меньше верхней.

**Порядок:** исследуется после `DboAtrFast`, `DboAtrFast` — родитель должен быть VALIDATED.

**Коридор и шаг:** [30, 40, 60, 80] — правило: сетка графа эталона. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[30, 40, 60, 80]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboAtrSlow` + `DboAtrFast`, `DboFlatThreshold`, `DboAtrFast` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.44 · [W34] DboFlatThreshold — Порог NormVol

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.85. **Пределы в коде:** 0.0 … 5.0.

**Механика (из кода):** ATR быстрый / ATR медленный на 15M ниже порога — боковик, вход запрещён.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; оптимизатор на ПК. Эталонное имя: `flat_threshold`.

**Связанные настройки:**

- `DboAtrFast` — связь графа; порог сравнивается с отношением, зависящим от обоих периодов.
- `DboAtrSlow` — связь графа; то же.

**Порядок:** исследуется после `DboAtrFast`, `DboAtrSlow` — родитель должен быть VALIDATED.

**Коридор и шаг:** [0.75, 0.8, 0.85, 0.9, 0.95] — правило: сетка графа эталона. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.75, 0.8, 0.85, 0.9, 0.95]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboFlatThreshold` + `DboAtrFast`, `DboAtrSlow` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 1.45 · [W37] DboTrendBars — Баров 4H для наклона

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 10. **Пределы в коде:** 2.0 … 200.0.

**Механика (из кода):** Число доходностей закрытых баров 4H в расчёте направления.

**Поведенческая гипотеза:** меняет набор баз и режимов, из которых вообще возможен вход: сильнее всего влияет на ЧИСЛО сделок и их распределение по дням. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; оптимизатор на ПК. Эталонное имя: `trend_bars`.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [5, 8, 10, 15, 20] — правило: сетка графа эталона. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[5, 8, 10, 15, 20]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboTrendBars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.


## Этап 2. Ядра сигналов входа

### Шаг 2.1 · [M11] TrfpLine1Slot — Линии: слот линии 1

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула для первой линии.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.2 · [M12] TrfpLine2Slot — Линии: слот линии 2

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 2. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула для второй линии.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.3 · [M13] TrfpLine3Slot — Линии: слот линии 3

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 3. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула для третьей линии.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.4 · [M14] TrfpUseLine3 — Линии: использовать третью

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Выключение оставляет голосование двух линий.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.5 · [M15] TrfpPeriod — Линии: период сглаживания

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 100. **Пределы в коде:** 2.0 … 2000.0.

**Механика (из кода):** Период двойного сглаживания диапазона. Он же задаёт прогрев каждой линии.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [50, 75, 100, 150, 200] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[50, 75, 100, 150, 200]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `TrfpPeriod` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.6 · [M16] TrfpMultiplier — Линии: множитель ширины

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 3.0. **Пределы в коде:** 0.1 … 50.0.

**Механика (из кода):** Ширина диапазона. Больше значение — реже развороты линии.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1.5, 2.25, 3.0, 3.75, 4.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1.5, 2.25, 3.0, 3.75, 4.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `TrfpMultiplier` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.7 · [M103] TrfpPeriodNeutralPolicy — NeutralPolicy

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** SwTrfpNeutralPolicy. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwTrfpNeutralPolicy.CountsAsDisagree. **Пределы в коде:** — … —. **Значения:** CountsAsDisagree, CountsAsAgree.

**Механика (из кода):** Поле SwTrfpConfig.NeutralPolicy: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** CountsAsDisagree, CountsAsAgree — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.8 · [W11] DboMorningBaseStart — Утро: база, начало

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 60000. **Пределы в коде:** 0.0 … 235959.0.

**Механика (из кода):** Время ЧЧММСС в поясе окон [M81], по времени открытия бара.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [30000, 45000, 60000, 90000, 120000] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[30000, 45000, 60000, 90000, 120000]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboMorningBaseStart` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.9 · [W12] DboMorningBaseEnd — Утро: база, конец

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 65959. **Пределы в коде:** 0.0 … 235959.0.

**Механика (из кода):** Время ЧЧММСС в поясе окон [M81], по времени открытия бара.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [32980, 49469, 65959, 98938, 131918] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[32980, 49469, 65959, 98938, 131918]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboMorningBaseEnd` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.10 · [W13] DboMorningSignalStart — Утро: окно сигналов, начало

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 70000. **Пределы в коде:** 0.0 … 235959.0.

**Механика (из кода):** Время ЧЧММСС в поясе окон [M81], по времени открытия бара.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [35000, 52500, 70000, 105000, 140000] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[35000, 52500, 70000, 105000, 140000]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboMorningSignalStart` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.11 · [W14] DboMorningSignalEnd — Утро: окно сигналов, конец

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 95959. **Пределы в коде:** 0.0 … 235959.0.

**Механика (из кода):** Время ЧЧММСС в поясе окон [M81], по времени открытия бара.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [47980, 71969, 95959, 143938, 191918] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[47980, 71969, 95959, 143938, 191918]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboMorningSignalEnd` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.12 · [W15] DboMorningSessionEnd — Утро: выход по времени

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 143000. **Пределы в коде:** 0.0 … 235959.0.

**Механика (из кода):** Время ЧЧММСС в поясе окон [M81], по времени открытия бара. Выход — принудительное закрытие позиции сессии.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [71500, 107250, 143000, 214500, 235959] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[71500, 107250, 143000, 214500, 235959]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboMorningSessionEnd` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.13 · [W21] DboEveningBaseStart — Вечер: база, начало

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 170000. **Пределы в коде:** 0.0 … 235959.0.

**Механика (из кода):** Время ЧЧММСС в поясе окон [M81], по времени открытия бара.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [85000, 127500, 170000, 235959] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[85000, 127500, 170000, 235959]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboEveningBaseStart` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.14 · [W22] DboEveningBaseEnd — Вечер: база, конец

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 175959. **Пределы в коде:** 0.0 … 235959.0.

**Механика (из кода):** Время ЧЧММСС в поясе окон [M81], по времени открытия бара.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [87980, 131969, 175959, 235959] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[87980, 131969, 175959, 235959]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboEveningBaseEnd` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.15 · [W23] DboEveningSignalStart — Вечер: окно сигналов, начало

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 180000. **Пределы в коде:** 0.0 … 235959.0.

**Механика (из кода):** Время ЧЧММСС в поясе окон [M81], по времени открытия бара.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [90000, 135000, 180000, 235959] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[90000, 135000, 180000, 235959]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboEveningSignalStart` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.16 · [W24] DboEveningSignalEnd — Вечер: окно сигналов, конец

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 195959. **Пределы в коде:** 0.0 … 235959.0.

**Механика (из кода):** Время ЧЧММСС в поясе окон [M81], по времени открытия бара.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [97980, 146969, 195959, 235959] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[97980, 146969, 195959, 235959]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboEveningSignalEnd` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.17 · [W25] DboEveningSessionEnd — Вечер: выход по времени

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 213000. **Пределы в коде:** 0.0 … 235959.0.

**Механика (из кода):** Время ЧЧММСС в поясе окон [M81], по времени открытия бара. Выход — принудительное закрытие позиции сессии.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [106500, 159750, 213000, 235959] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[106500, 159750, 213000, 235959]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboEveningSessionEnd` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.18 · [W38] DboEntryOffsetTicks — Отступ входа от границы базы, тиков

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 100.0.

**Механика (из кода):** Стоп-ордер ставится на экстремум базы плюс отступ.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком малое значение — срабатывания на шуме; слишком большое — механизм почти не срабатывает.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2] — правило: тики: целые кратные шагу цены, ×0,5…×2. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboEntryOffsetTicks` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.19 · [W39] DboMaxEntries — Предел входов за сессию

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 100.0.

**Механика (из кода):** 0 — без ограничения. Повторный вход — только после возврата цены за уровень.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; оптимизатор на ПК. Эталонное имя: `max_entries_per_session`.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0, 1, 2, 3] — правило: сетка графа эталона. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0, 1, 2, 3]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboMaxEntries` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.20 · [W40] DboEveningDir — Направление вечера

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** SwEveningDir. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwEveningDir.DayTrend. **Пределы в коде:** — … —. **Значения:** DayTrend, H4, Both.

**Механика (из кода):** DayTrend — по тренду дня, как в исследовании. H4 — по наклону 4H. Both — оба обязаны совпасть.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** DayTrend, H4, Both — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.21 · [W41] DboCloseAtSessionEnd — Закрывать позицию по окончании сессии

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Выход по времени [W15] и [W25].

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.22 · [C01] KalRole — Роль

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** SwKalmanRole. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwKalmanRole.Filter. **Пределы в коде:** — … —. **Значения:** Filter, Signal.

**Механика (из кода):** Роль модуля в конвейере.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Filter, Signal — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.23 · [C02] KalLowerSlot — Младшая серия

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула 0–4.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `KalHigherSlot` — KalLowerSlot < KalHigherSlot; пара Low/High: нижняя граница меньше верхней.
- `KalHigherSlot` — KalLowerSlot < KalHigherSlot; пара Lower/Higher: нижняя граница меньше верхней.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.24 · [C03] KalCurrentSlot — Текущая серия

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула 0–4.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.25 · [C04] KalHigherSlot — Старшая серия

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 3. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула 0–4.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `KalLowerSlot` — KalLowerSlot < KalHigherSlot; пара Low/High: нижняя граница меньше верхней.
- `KalLowerSlot` — KalLowerSlot < KalHigherSlot; пара Lower/Higher: нижняя граница меньше верхней.

**Порядок:** исследуется после `KalLowerSlot`, `KalLowerSlot` — родитель должен быть VALIDATED.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.26 · [C05] KalPeriod — Период

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 20. **Пределы в коде:** 2.0 … 500.0.

**Механика (из кода):** Окно фильтра, баров.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [10, 15, 20, 30, 40] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[10, 15, 20, 30, 40]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalPeriod` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.27 · [C06] KalBandSigma — Ширина полос, σ

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 2.0. **Пределы в коде:** 0.1 … 10.0.

**Механика (из кода):** Множитель полос канала.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1.0, 1.5, 2.0, 2.5, 3.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1.0, 1.5, 2.0, 2.5, 3.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalBandSigma` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.28 · [C07] KalPolicy — Политика фильтра

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** SwKalmanFilterPolicy. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwKalmanFilterPolicy.TrendDirection. **Пределы в коде:** — … —. **Значения:** TrendDirection, TrendOnly, NoRange.

**Механика (из кода):** Как канал голосует за направление.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** TrendDirection, TrendOnly, NoRange — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.29 · [C08] KalBands — Bands

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** SwKalmanBands. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwKalmanBands.GaussianSemiDeviation. **Пределы в коде:** — … —. **Значения:** GaussianSemiDeviation, KalmanInnovation.

**Механика (из кода):** Поле SwKalmanConfig.Bands: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** GaussianSemiDeviation, KalmanInnovation — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.30 · [C09] KalEntryWindowMin — EntryWindowMin

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 10. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.EntryWindowMin: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `KalEntryWindowMax` — KalEntryWindowMin < KalEntryWindowMax; пара Min/Max: нижняя граница меньше верхней.

**Коридор и шаг:** [5, 8, 10, 15, 20] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[5, 8, 10, 15, 20]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalEntryWindowMin` + `KalEntryWindowMax` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.31 · [C10] KalEntryWindowMax — EntryWindowMax

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 40. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.EntryWindowMax: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `KalEntryWindowMin` — KalEntryWindowMin < KalEntryWindowMax; пара Min/Max: нижняя граница меньше верхней.

**Порядок:** исследуется после `KalEntryWindowMin` — родитель должен быть VALIDATED.

**Коридор и шаг:** [20, 30, 40, 60, 80] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[20, 30, 40, 60, 80]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalEntryWindowMax` + `KalEntryWindowMin` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.32 · [C11] KalEscortWindowMin — EscortWindowMin

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 30. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.EscortWindowMin: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `KalEscortWindowMax` — KalEscortWindowMin < KalEscortWindowMax; пара Min/Max: нижняя граница меньше верхней.

**Коридор и шаг:** [15, 22, 30, 45, 60] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[15, 22, 30, 45, 60]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalEscortWindowMin` + `KalEscortWindowMax` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.33 · [C12] KalEscortWindowMax — EscortWindowMax

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 120. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.EscortWindowMax: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `KalEscortWindowMin` — KalEscortWindowMin < KalEscortWindowMax; пара Min/Max: нижняя граница меньше верхней.

**Порядок:** исследуется после `KalEscortWindowMin` — родитель должен быть VALIDATED.

**Коридор и шаг:** [60, 90, 120, 180, 240] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[60, 90, 120, 180, 240]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalEscortWindowMax` + `KalEscortWindowMin` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.34 · [C13] KalFlatTilt — FlatTilt

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.4. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.FlatTilt: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.2, 0.3, 0.4, 0.5, 0.6] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.2, 0.3, 0.4, 0.5, 0.6]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalFlatTilt` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.35 · [C14] KalSymmetryMax — SymmetryMax

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.3. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.SymmetryMax: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.15, 0.225, 0.3, 0.375, 0.45] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.15, 0.225, 0.3, 0.375, 0.45]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalSymmetryMax` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.36 · [C15] KalRangeConfirmBars — RangeConfirmBars

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 0. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.RangeConfirmBars: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalRangeConfirmBars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.37 · [C16] KalTrendZ — TrendZ

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 3.0. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.TrendZ: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1.5, 2.25, 3.0, 3.75, 4.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1.5, 2.25, 3.0, 3.75, 4.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalTrendZ` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.38 · [C17] KalTrendTilt — TrendTilt

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.6. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.TrendTilt: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.3, 0.45, 0.6, 0.75, 0.9] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.3, 0.45, 0.6, 0.75, 0.9]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalTrendTilt` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.39 · [C18] KalCompressionRatio — CompressionRatio

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.75. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.CompressionRatio: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.375, 0.5625, 0.75, 0.9375, 1.125] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.375, 0.5625, 0.75, 0.9375, 1.125]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalCompressionRatio` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.40 · [C19] KalExpansionRatio — ExpansionRatio

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1.35. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.ExpansionRatio: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.675, 1.0125, 1.35, 1.6875, 2.025] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.675, 1.0125, 1.35, 1.6875, 2.025]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalExpansionRatio` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.41 · [C20] KalDirectionTf — DirectionTf

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** SwKalmanTfChoice. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwKalmanTfChoice.Higher. **Пределы в коде:** — … —. **Значения:** Current, Higher.

**Механика (из кода):** Поле SwKalmanConfig.DirectionTf: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Current, Higher — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.42 · [C21] KalEscortTf — EscortTf

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** SwKalmanTfChoice. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwKalmanTfChoice.Current. **Пределы в коде:** — … —. **Значения:** Current, Higher.

**Механика (из кода):** Поле SwKalmanConfig.EscortTf: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Current, Higher — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.43 · [C22] KalRequireHigherAgreement — RequireHigherAgreement

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.RequireHigherAgreement: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.44 · [C23] KalSignalBars — SignalBars

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 1. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.SignalBars: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalSignalBars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.45 · [C24] KalEscortStop — EscortStop

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.EscortStop: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.46 · [C25] KalStopOffsetTicks — StopOffsetTicks

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 2. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.StopOffsetTicks: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком малое значение — срабатывания на шуме; слишком большое — механизм почти не срабатывает.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2, 3, 4] — правило: тики: целые кратные шагу цены, ×0,5…×2. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2, 3, 4]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalStopOffsetTicks` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.47 · [C26] KalExitOnSlopeFlip — ExitOnSlopeFlip

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.ExitOnSlopeFlip: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.48 · [C27] KalExitConfirmBars — ExitConfirmBars

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 2. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.ExitConfirmBars: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2, 3, 4] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2, 3, 4]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalExitConfirmBars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.49 · [C28] KalResearch — Research

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.Research: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.50 · [C29] KalResearchHorizon — ResearchHorizon

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 20. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.ResearchHorizon: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [10, 15, 20, 30, 40] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[10, 15, 20, 30, 40]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalResearchHorizon` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.51 · [C30] KalRangeHoldBars — RangeHoldBars

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 10. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.RangeHoldBars: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [5, 8, 10, 15, 20] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[5, 8, 10, 15, 20]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalRangeHoldBars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.52 · [C31] KalWarmupPeriods — WarmupPeriods

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 3. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.WarmupPeriods: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [2, 3, 4, 6] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[2, 3, 4, 6]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KalWarmupPeriods` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.53 · [C32] KalProvisionalDisplay — ProvisionalDisplay

**Группа:** 15 · Канал Калмана (сглаженный уровень, полосы, пробой и выход по наклону). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwKalmanConfig.ProvisionalDisplay: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.54 · [B01] LevRole — Роль

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** SwLeverRole. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwLeverRole.Filter. **Пределы в коде:** — … —. **Значения:** Filter, Signal.

**Механика (из кода):** Роль модуля в конвейере.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Filter, Signal — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.55 · [B02] LevAnalysisSlot — Серия анализа

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула 0–4.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.56 · [B03] LevClusterSlot — Серия кластеров

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула 0–4.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.57 · [B04] LevClusters — Кластеров

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 10. **Пределы в коде:** 2.0 … 100.0.

**Механика (из кода):** Число кластеров объёма.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [5, 8, 10, 15, 20] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[5, 8, 10, 15, 20]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LevClusters` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.58 · [B05] LevVoteZ — Порог голоса, z

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.5. **Пределы в коде:** 0.0 … 10.0.

**Механика (из кода):** Порог значимости голоса.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.25, 0.375, 0.5, 0.625, 0.75] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.25, 0.375, 0.5, 0.625, 0.75]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LevVoteZ` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.59 · [B06] LevPolicy — Политика

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** SwLeverPolicy. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwLeverPolicy.DirectionOnly. **Пределы в коде:** — … —. **Значения:** DirectionOnly, BlockMiddle.

**Механика (из кода):** Как рычаг голосует.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** DirectionOnly, BlockMiddle — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.60 · [B07] LevWeight — Weight

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** SwLeverWeight. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwLeverWeight.Volume. **Пределы в коде:** — … —. **Значения:** Volume, Ticks.

**Механика (из кода):** Поле SwLeverConfig.Weight: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Volume, Ticks — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.61 · [B08] LevFulcrum — Fulcrum

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** SwLeverFulcrum. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwLeverFulcrum.RangeMid. **Пределы в коде:** — … —. **Значения:** RangeMid, BodyMid.

**Механика (из кода):** Поле SwLeverConfig.Fulcrum: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** RangeMid, BodyMid — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.62 · [B09] LevMeasure — Measure

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** SwLeverMeasure. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwLeverMeasure.Both. **Пределы в коде:** — … —. **Значения:** Both, Lever, MedianCenter.

**Механика (из кода):** Поле SwLeverConfig.Measure: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Both, Lever, MedianCenter — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.63 · [B10] LevSmoothCandles — SmoothCandles

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 3. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwLeverConfig.SmoothCandles: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [2, 3, 4, 6] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[2, 3, 4, 6]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LevSmoothCandles` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.64 · [B11] LevScaleWindow — ScaleWindow

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 50. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwLeverConfig.ScaleWindow: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [25, 38, 50, 75, 100] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[25, 38, 50, 75, 100]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LevScaleWindow` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.65 · [B12] LevSignalWithTrend — SignalWithTrend

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwLeverConfig.SignalWithTrend: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.66 · [B13] LevTrendWindow — TrendWindow

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 20. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwLeverConfig.TrendWindow: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [10, 15, 20, 30, 40] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[10, 15, 20, 30, 40]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LevTrendWindow` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.67 · [B14] LevSignalBars — SignalBars

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 1. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwLeverConfig.SignalBars: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LevSignalBars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.68 · [B15] LevExitAgainst — ExitAgainst

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwLeverConfig.ExitAgainst: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.69 · [B16] LevExitConfirm — ExitConfirm

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 2. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwLeverConfig.ExitConfirm: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2, 3, 4] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2, 3, 4]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LevExitConfirm` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.70 · [B17] LevMinHeightTicks — MinHeightTicks

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** int. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 4. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwLeverConfig.MinHeightTicks: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком малое значение — срабатывания на шуме; слишком большое — механизм почти не срабатывает.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [2, 3, 4, 5, 6, 8] — правило: тики: целые кратные шагу цены, ×0,5…×2. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[2, 3, 4, 5, 6, 8]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LevMinHeightTicks` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.71 · [B18] LevFinalize — Finalize

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** SwLeverFinalize. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwLeverFinalize.Auto. **Пределы в коде:** — … —. **Значения:** Auto, Exact, Fast.

**Механика (из кода):** Поле SwLeverConfig.Finalize: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Auto, Exact, Fast — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.72 · [B19] LevResearch — Research

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwLeverConfig.Research: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.73 · [B20] LevResearchHorizon — ResearchHorizon

**Группа:** 16 · Рычаг свечи (голос кластеров объёма внутри свечи). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 5. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwLeverConfig.ResearchHorizon: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [2, 4, 5, 8, 10] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[2, 4, 5, 8, 10]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LevResearchHorizon` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.74 · [G01] HmSlot — Серия

**Группа:** 17 · Иерархическая масса (дрейф взвешенной по объёму цены по эшелонам 1, 5, 15 минут). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула с минутками, 0–4.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.75 · [G02] HmWindow — Окно, минут

**Группа:** 17 · Иерархическая масса (дрейф взвешенной по объёму цены по эшелонам 1, 5, 15 минут). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 15. **Пределы в коде:** 5.0 … 480.0.

**Механика (из кода):** Длина окна расчёта; эшелоны — полные блоки 5 и 15 минут от конца окна.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [8, 11, 15, 22, 30] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[8, 11, 15, 22, 30]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HmWindow` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.76 · [G03] HmWeight5 — Вес эшелона 5M

**Группа:** 17 · Иерархическая масса (дрейф взвешенной по объёму цены по эшелонам 1, 5, 15 минут). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1.0. **Пределы в коде:** 0.0 … 10.0.

**Механика (из кода):** Вес 5-минутного эшелона в синтетическом узле.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.5, 0.75, 1.0, 1.25, 1.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.5, 0.75, 1.0, 1.25, 1.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HmWeight5` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.77 · [G04] HmWeight15 — Вес эшелона 15M

**Группа:** 17 · Иерархическая масса (дрейф взвешенной по объёму цены по эшелонам 1, 5, 15 минут). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1.5. **Пределы в коде:** 0.0 … 10.0.

**Механика (из кода):** Вес 15-минутного эшелона; 1,5 по ТЗ.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.75, 1.125, 1.5, 1.875, 2.25] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.75, 1.125, 1.5, 1.875, 2.25]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HmWeight15` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.78 · [G05] HmSignalMode — Режим сигнала

**Группа:** 17 · Иерархическая масса (дрейф взвешенной по объёму цены по эшелонам 1, 5, 15 минут). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Выключено — фильтр.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.79 · [G06] HmPercentile — Процентиль ширины

**Группа:** 17 · Иерархическая масса (дрейф взвешенной по объёму цены по эшелонам 1, 5, 15 минут). **Тип:** double. **Единица:** доля — порог или пропорция от 0 до 1; увеличение ужесточает отбор.
**По умолчанию:** 0.85. **Пределы в коде:** 0.5 … 0.99.

**Механика (из кода):** Процентиль отклонений от оси для ширины коридора; 0,85 по ТЗ.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Крайние значения вырождают механизм: пропускает всё или ничего.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99] — правило: доля 0–1: шаг 0,05 вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HmPercentile` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.80 · [G07] HmBiasThreshold — Порог смещения, тиков

**Группа:** 17 · Иерархическая масса (дрейф взвешенной по объёму цены по эшелонам 1, 5, 15 минут). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 2.0. **Пределы в коде:** 0.0 … 100.0.

**Механика (из кода):** |смещение| ниже порога — нейтраль.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1.0, 1.5, 2.0, 2.5, 3.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1.0, 1.5, 2.0, 2.5, 3.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HmBiasThreshold` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.81 · [G08] HmExpSqueeze — Шлюз сжатия

**Группа:** 17 · Иерархическая масса (дрейф взвешенной по объёму цены по эшелонам 1, 5, 15 минут). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Ширина ниже доли своей медианы — нейтраль. ЭКСПЕРИМЕНТ: выключено по умолчанию.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `HmExpSqueezeRatio` — HmExpSqueezeRatio действует при HmExpSqueeze = true; числовой параметр эксперимента без флага не влияет.
- `HmExpPersist` — HmExpPersist действует при HmExpSqueeze = true; числовой параметр эксперимента без флага не влияет.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 2.82 · [G09] HmExpSqueezeRatio — Доля медианы для сжатия

**Группа:** 17 · Иерархическая масса (дрейф взвешенной по объёму цены по эшелонам 1, 5, 15 минут). **Тип:** double. **Единица:** доля — порог или пропорция от 0 до 1; увеличение ужесточает отбор.
**По умолчанию:** 0.6. **Пределы в коде:** 0.1 … 1.0.

**Механика (из кода):** Для [G08].

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Крайние значения вырождают механизм: пропускает всё или ничего.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `HmExpSqueeze` — HmExpSqueezeRatio действует при HmExpSqueeze = true; числовой параметр эксперимента без флага не влияет.

**Порядок:** исследуется после `HmExpSqueeze` — родитель должен быть VALIDATED.

**Коридор и шаг:** [0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75] — правило: доля 0–1: шаг 0,05 вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.45, 0.5, 0.55, 0.6, 0.65, 0.7, 0.75]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HmExpSqueezeRatio` + `HmExpSqueeze` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.83 · [G10] HmExpPersist — Устойчивость знака, расчётов

**Группа:** 17 · Иерархическая масса (дрейф взвешенной по объёму цены по эшелонам 1, 5, 15 минут). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 20.0.

**Механика (из кода):** Направление после K подряд расчётов одного знака; 0 — выключено. ЭКСПЕРИМЕНТ: выключено по умолчанию.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `HmExpSqueeze` — HmExpPersist действует при HmExpSqueeze = true; числовой параметр эксперимента без флага не влияет.

**Порядок:** исследуется после `HmExpSqueeze` — родитель должен быть VALIDATED.

**Коридор и шаг:** [1] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HmExpPersist` + `HmExpSqueeze` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 2.84 · [G11] HmSqueezeLookback — SqueezeLookback

**Группа:** 17 · Иерархическая масса (дрейф взвешенной по объёму цены по эшелонам 1, 5, 15 минут). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 100. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwHierarchicalMassConfig.SqueezeLookback: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет момент и направление входа: влияет на ДОЛЮ прибыльных и среднюю величину сделки. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [50, 75, 100, 150, 200] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[50, 75, 100, 150, 200]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HmSqueezeLookback` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.


## Этап 3. Статистические фильтры

### Шаг 3.1 · [D01] RequireAllSignalsAgree — Требовать согласия всех сигналов

**Группа:** 02 · Решение (как голоса сигналов и фильтров сводятся в вход: пороги уверенности и согласия). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Включено — вход только при совпадении направления всех готовых модулей роли Signal. Выключено — решает знак суммы голосов.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.2 · [D02] MinConfidence — Минимальная уверенность

**Группа:** 02 · Решение (как голоса сигналов и фильтров сводятся в вход: пороги уверенности и согласия). **Тип:** double. **Единица:** доля — порог или пропорция от 0 до 1; увеличение ужесточает отбор.
**По умолчанию:** 0.0. **Пределы в коде:** 0.0 … 1.0.

**Механика (из кода):** Порог средней уверенности по голосующим модулям. Ноль отключает проверку.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Крайние значения вырождают механизм: пропускает всё или ничего.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.0, 0.05, 0.1, 0.15] — правило: доля 0–1: шаг 0,05 вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.0, 0.05, 0.1, 0.15]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `MinConfidence` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.3 · [D03] FilterMissingBlocksEntry — Отсутствие вердикта фильтра блокирует вход

**Группа:** 02 · Решение (как голоса сигналов и фильтров сводятся в вход: пороги уверенности и согласия). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Включено — если фильтр подключён, но вердикта не дал, вход запрещён. Выключено — молчание фильтра считается согласием.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.4 · [K50] KerKernel — Ядро

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** SwKernelType. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwKernelType.Epanechnikov. **Пределы в коде:** — … —. **Значения:** Epanechnikov, Triangular, Tricube, Cosine, Gaussian.

**Механика (из кода):** Epanechnikov — минимальная среднеквадратичная ошибка. Остальные отличаются по эффективности на 1–2%. Автовыбор по таймфрейму не предусмотрен: запаздывание определяет ширина окна и тип регрессии, а не форма ядра.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Epanechnikov, Triangular, Tricube, Cosine, Gaussian — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.5 · [K51] KerRegression — Тип регрессии

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** SwRegressionType. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwRegressionType.LocalLinear. **Пределы в коде:** — … —. **Значения:** LocalLinear, NadarayaWatson.

**Механика (из кода):** LocalLinear — локальная прямая, без смещения на краю при линейном тренде. NadarayaWatson — взвешенное среднее; на тренде отстаёт на несколько баров.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** LocalLinear, NadarayaWatson — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.6 · [K52] KerSlot — Слот серии

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** 0 — график, 1–4 — слоты пула [S50]–[S80]. Подгонка — на закрытии бара этой серии.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.7 · [K53] KerBandwidth — Ширина окна, баров

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 20. **Пределы в коде:** 5.0 … 200.0.

**Механика (из кода):** Базовая ширина носителя ядра.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [10, 15, 20, 30, 40] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[10, 15, 20, 30, 40]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KerBandwidth` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.8 · [K54] KerAdaptive — Адаптивная ширина окна

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Окно умножается на ATR(20)/ATR(5) в пределах 0,5–2: при всплеске волатильности короче, в затишье длиннее.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.9 · [K55] KerVolumeWeighting — Вес по объёму

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Множитель веса 1 + γ·z, ограниченный от 0,1 до 4. Выключено: тяготение подгонки к барам с высоким объёмом — обычно к новостным всплескам — не проверено.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.10 · [K56] KerVolumeGamma — Множитель γ веса объёма

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1.0. **Пределы в коде:** 0.0 … 5.0.

**Механика (из кода):** 0 — вес не зависит от объёма.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.5, 0.75, 1.0, 1.25, 1.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.5, 0.75, 1.0, 1.25, 1.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KerVolumeGamma` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.11 · [K57] KerVolumeScale — Нормировка объёма

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** SwVolumeScale. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwVolumeScale.Robust. **Пределы в коде:** — … —. **Значения:** Robust, Standard.

**Механика (из кода):** Robust — медиана и MAD, не искажается одиночными всплесками. Standard — среднее и СКО.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Robust, Standard — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.12 · [K58] KerVolumeWindow — Окно статистики объёма, баров

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 50. **Пределы в коде:** 5.0 … 500.0.

**Механика (из кода):** По скольким барам считаются центр и разброс объёма.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [25, 38, 50, 75, 100] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[25, 38, 50, 75, 100]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KerVolumeWindow` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.13 · [K59] KerSlopeThreshold — Порог наклона, тиков на бар

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.5. **Пределы в коде:** 0.0 … 10.0.

**Механика (из кода):** Ниже — нейтраль; выше — согласие в сторону наклона, вход против него запрещается.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.25, 0.375, 0.5, 0.625, 0.75] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.25, 0.375, 0.5, 0.625, 0.75]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KerSlopeThreshold` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.14 · [K60] KerDivergence — Действие при развороте наклона против позиции

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** SwKernelDivergenceAction. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwKernelDivergenceAction.Neutral. **Пределы в коде:** — … —. **Значения:** Neutral, Veto, RequestPartialExit.

**Механика (из кода):** Neutral — только запись в трассировку. Veto — запрет нового входа, пока разворот длится. RequestPartialExit — требование закрыть 2/3 позиции один раз за эпизод; не проверено на истории.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Neutral, Veto, RequestPartialExit — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.15 · [K61] KerExpTGate — Значимость наклона

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Направление учитывается, только если t-статистика наклона выше [K62]. t приближённая: остатки автокоррелированы, и значимость завышена. ЭКСПЕРИМЕНТ: выключено по умолчанию, требует проверки на истории.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `KerExpTMin` — KerExpTMin действует при KerExpTGate = true; числовой параметр эксперимента без флага не влияет.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.16 · [K63] KerExpFastSlow — Пересечение быстрой и медленной прямых

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Направление — знак разности быстрой (окно вдвое короче) и медленной прямых вместо знака наклона. ЭКСПЕРИМЕНТ: выключено по умолчанию, требует проверки на истории.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `KerExpTMin` — KerExpTMin действует при KerExpFastSlow = true; числовой параметр эксперимента без флага не влияет.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.17 · [K64] KerExpSkill — Самопроверка предсказательной силы

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Прогноз прямой на бар вперёд сравнивается с наивным «цена не изменится». Не лучше наивного — модуль уходит в нейтраль. На случайном блуждании наивный прогноз оптимален. ЭКСПЕРИМЕНТ: выключено по умолчанию, требует проверки на истории.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `KerExpTMin` — KerExpTMin действует при KerExpSkill = true; числовой параметр эксперимента без флага не влияет.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.18 · [K62] KerExpTMin — Порог t-статистики

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 2.0. **Пределы в коде:** 0.0 … 20.0.

**Механика (из кода):** Для [K61].

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `KerExpTGate` — KerExpTMin действует при KerExpTGate = true; числовой параметр эксперимента без флага не влияет.
- `KerExpFastSlow` — KerExpTMin действует при KerExpFastSlow = true; числовой параметр эксперимента без флага не влияет.
- `KerExpSkill` — KerExpTMin действует при KerExpSkill = true; числовой параметр эксперимента без флага не влияет.

**Порядок:** исследуется после `KerExpTGate`, `KerExpFastSlow`, `KerExpSkill` — родитель должен быть VALIDATED.

**Коридор и шаг:** [1.0, 1.5, 2.0, 2.5, 3.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1.0, 1.5, 2.0, 2.5, 3.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KerExpTMin` + `KerExpTGate`, `KerExpFastSlow`, `KerExpSkill` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.19 · [K65] KerSignalMode — Режим сигнала

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Выключено — роль фильтра. Включено — роль сигнала: модуль голосует за направление наравне с другими сигнальными модулями.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.20 · [K66] KerAdaptMin — AdaptMin

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.5. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwAdaptiveKernelConfig.AdaptMin: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `KerAdaptMax` — KerAdaptMin < KerAdaptMax; пара Min/Max: нижняя граница меньше верхней.

**Коридор и шаг:** [0.25, 0.375, 0.5, 0.625, 0.75] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.25, 0.375, 0.5, 0.625, 0.75]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KerAdaptMin` + `KerAdaptMax` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.21 · [K67] KerAdaptMax — AdaptMax

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 2.0. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwAdaptiveKernelConfig.AdaptMax: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `KerAdaptMin` — KerAdaptMin < KerAdaptMax; пара Min/Max: нижняя граница меньше верхней.

**Порядок:** исследуется после `KerAdaptMin` — родитель должен быть VALIDATED.

**Коридор и шаг:** [1.0, 1.5, 2.0, 2.5, 3.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1.0, 1.5, 2.0, 2.5, 3.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KerAdaptMax` + `KerAdaptMin` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.22 · [K68] KerSkillWindow — SkillWindow

**Группа:** 09 · Адаптивное ядро (ядерная регрессия с адаптивной шириной окна; общий вычислитель MOD9–MOD11). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 100. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwAdaptiveKernelConfig.SkillWindow: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [50, 75, 100, 150, 200] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[50, 75, 100, 150, 200]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `KerSkillWindow` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.23 · [L01] LorSlot — Слот серии

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** 0 — график, 1–4 — слоты пула.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.24 · [L02] LorLookback — Окно поиска, баров

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 2000. **Пределы в коде:** 100.0 … 10000.0.

**Механика (из кода):** Сколько баров прошлого просматривается в поиске соседей.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1000, 1500, 2000, 3000, 4000] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1000, 1500, 2000, 3000, 4000]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorLookback` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.25 · [L03] LorNeighbors — Число соседей K

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 16. **Пределы в коде:** 1.0 … 100.0.

**Механика (из кода):** Сколько ближайших ситуаций голосует.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [8, 12, 16, 24, 32] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[8, 12, 16, 24, 32]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorNeighbors` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.26 · [L04] LorStride — Шаг выборки соседей

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 4. **Пределы в коде:** 1.0 … 50.0.

**Механика (из кода):** Соседние бары делят будущее окно и голосуют почти одинаково; шаг снижает эту зависимость.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [2, 3, 4, 6, 8] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[2, 3, 4, 6, 8]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorStride` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.27 · [L05] LorHorizon — Горизонт метки, баров

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 4. **Пределы в коде:** 1.0 … 100.0.

**Механика (из кода):** Метка соседа — знак приращения за H баров вперёд. Сосед допускается, только если его исход уже известен.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [2, 3, 4, 6, 8] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[2, 3, 4, 6, 8]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorHorizon` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.28 · [L06] LorVoteThreshold — Порог перевеса голосов

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** double. **Единица:** доля — порог или пропорция от 0 до 1; увеличение ужесточает отбор.
**По умолчанию:** 0.5. **Пределы в коде:** 0.0 … 1.0.

**Механика (из кода):** Доля перевеса 0–1, ниже которой модуль нейтрален.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Крайние значения вырождают механизм: пропускает всё или ничего.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65] — правило: доля 0–1: шаг 0,05 вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.35, 0.4, 0.45, 0.5, 0.55, 0.6, 0.65]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorVoteThreshold` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.29 · [L07] LorYeoJohnson — Нормализация Йео–Джонсона

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** λ по максимуму правдоподобия на прошлом окне; работает и с отрицательными значениями, в отличие от Бокса–Кокса.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.30 · [L08] LorRefitBars — Пересчёт нормализации, баров

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 100. **Пределы в коде:** 10.0 … 5000.0.

**Механика (из кода):** Как часто пересчитываются параметры — только по прошлым данным.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [50, 75, 100, 150, 200] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[50, 75, 100, 150, 200]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorRefitBars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.31 · [L09] LorFitWindow — Окно нормализации, баров

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 500. **Пределы в коде:** 50.0 … 5000.0.

**Механика (из кода):** По скольким барам оцениваются λ и масштаб.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [250, 375, 500, 750, 1000] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[250, 375, 500, 750, 1000]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorFitWindow` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.32 · [L10] LorKalmanQ — Калман: шум процесса Q

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.01. **Пределы в коде:** 1e-06 … 100.0.

**Механика (из кода):** Больше — скорость реагирует быстрее.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.005, 0.0075, 0.01, 0.0125, 0.015] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.005, 0.0075, 0.01, 0.0125, 0.015]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorKalmanQ` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.33 · [L11] LorKalmanR — Калман: шум измерения R

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1.0. **Пределы в коде:** 1e-06 … 1000.0.

**Механика (из кода):** Больше — фильтр сильнее сглаживает.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.5, 0.75, 1.0, 1.25, 1.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.5, 0.75, 1.0, 1.25, 1.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorKalmanR` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.34 · [L12] LorSignalMode — Режим сигнала

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Выключено — фильтр; включено — голосует за направление как сигнал.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.35 · [L13] LorExpKernelVote — Голос с гауссовым весом

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Вес соседа exp(−d²/2h²) по расстоянию Лоренца вместо равного. ЭКСПЕРИМЕНТ: выключено по умолчанию.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `LorExpPrecisionMin` — LorExpPrecisionMin действует при LorExpKernelVote = true; числовой параметр эксперимента без флага не влияет.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.36 · [L14] LorExpPrecisionGate — Самопроверка точности

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Причинная скользящая точность против эталона «монетки» с той же частотой исхода; ниже порога или не выше эталона — нейтраль. ЭКСПЕРИМЕНТ: выключено по умолчанию.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `LorExpPrecisionMin` — LorExpPrecisionMin действует при LorExpPrecisionGate = true; числовой параметр эксперимента без флага не влияет.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.37 · [L16] LorExpAgreeKernel — Согласие с адаптивным ядром

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Направление против тренда [MOD9] — нейтраль. Требует включённого [MOD9]. ЭКСПЕРИМЕНТ: выключено по умолчанию.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `LorExpPrecisionMin` — LorExpPrecisionMin действует при LorExpAgreeKernel = true; числовой параметр эксперимента без флага не влияет.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.38 · [L15] LorExpPrecisionMin — Порог точности

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** double. **Единица:** доля — порог или пропорция от 0 до 1; увеличение ужесточает отбор.
**По умолчанию:** 0.65. **Пределы в коде:** 0.0 … 1.0.

**Механика (из кода):** Для [L14].

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Крайние значения вырождают механизм: пропускает всё или ничего.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `LorExpKernelVote` — LorExpPrecisionMin действует при LorExpKernelVote = true; числовой параметр эксперимента без флага не влияет.
- `LorExpPrecisionGate` — LorExpPrecisionMin действует при LorExpPrecisionGate = true; числовой параметр эксперимента без флага не влияет.
- `LorExpAgreeKernel` — LorExpPrecisionMin действует при LorExpAgreeKernel = true; числовой параметр эксперимента без флага не влияет.

**Порядок:** исследуется после `LorExpKernelVote`, `LorExpPrecisionGate`, `LorExpAgreeKernel` — родитель должен быть VALIDATED.

**Коридор и шаг:** [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8] — правило: доля 0–1: шаг 0,05 вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorExpPrecisionMin` + `LorExpKernelVote`, `LorExpPrecisionGate`, `LorExpAgreeKernel` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.39 · [L17] LorMethod — Метод решения

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** SwLorentzMethod. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwLorentzMethod.KnnVote. **Пределы в коде:** — … —. **Значения:** KnnVote, NadarayaWatson, Consensus.

**Механика (из кода):** KnnVote — K ближайших, голос по знаку исхода. NadarayaWatson — взвешенное ядром среднее будущей доходности всех допустимых ситуаций. Consensus — направление, только если оба согласны.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** KnnVote, NadarayaWatson, Consensus — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.40 · [L18] LorNwKernel — Ядро Надарая–Ватсона

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** SwKernelType. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwKernelType.Gaussian. **Пределы в коде:** — … —. **Значения:** Epanechnikov, Triangular, Tricube, Cosine, Gaussian.

**Механика (из кода):** Gaussian по умолчанию; компактные ядра обнуляют дальние ситуации.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Epanechnikov, Triangular, Tricube, Cosine, Gaussian — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.41 · [L19] LorNwBandMult — Ширина ядра, доля медианы расстояний

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.5. **Пределы в коде:** 0.05 … 10.0.

**Механика (из кода):** σ ядра = множитель × медиана расстояний Лоренца. Меньше — решение по ближайшим, больше — по всем.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.25, 0.375, 0.5, 0.625, 0.75] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.25, 0.375, 0.5, 0.625, 0.75]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorNwBandMult` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.42 · [L20] LorNwThreshold — Порог прогноза, ATR

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.10. **Пределы в коде:** 0.0 … 5.0.

**Механика (из кода):** |прогноз доходности за H баров| в ATR ниже порога — нейтраль.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.05, 0.075, 0.1, 0.125, 0.15] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.05, 0.075, 0.1, 0.125, 0.15]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorNwThreshold` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.43 · [L21] LorNwMinEff — Минимальный эффективный объём

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 10. **Пределы в коде:** 1.0 … 1000.0.

**Механика (из кода):** (Σw)²/Σw² ниже порога — нейтраль: решение держалось бы на одной-двух ситуациях.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [5.0, 7.5, 10.0, 12.5, 15.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[5.0, 7.5, 10.0, 12.5, 15.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorNwMinEff` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.44 · [L22] LorEvalWindow — EvalWindow

**Группа:** 10 · Классификатор Лоренца (ближайшие соседи в пространстве признаков с расстоянием Лоренца; Надарая–Ватсон). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 200. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwLorentzianConfig.EvalWindow: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [100, 150, 200, 300, 400] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[100, 150, 200, 300, 400]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `LorEvalWindow` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.45 · [H01] HkSlot — Слот серии

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** 0 — график, 1–4 — слоты пула.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.46 · [H02] HkRegression — Тип регрессии

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** SwRegressionType. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwRegressionType.LocalLinear. **Пределы в коде:** — … —. **Значения:** LocalLinear, NadarayaWatson.

**Механика (из кода):** LocalLinear — без запаздывания на тренде; NadarayaWatson — отстаёт.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** LocalLinear, NadarayaWatson — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.47 · [H03] HkKernel — Ядро

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** SwKernelType. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwKernelType.Epanechnikov. **Пределы в коде:** — … —. **Значения:** Epanechnikov, Triangular, Tricube, Cosine, Gaussian.

**Механика (из кода):** Епанечников по умолчанию.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Epanechnikov, Triangular, Tricube, Cosine, Gaussian — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.48 · [H04] HkHurstPeriod — Окно Хёрста, доходностей

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 128. **Пределы в коде:** 16.0 … 4096.0.

**Механика (из кода):** Разброс оценки при 128 — 0,08, равен эффекту режима. Для устойчивости — 256 и больше.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [64, 96, 128, 192, 256] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[64, 96, 128, 192, 256]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HkHurstPeriod` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.49 · [H05] HkMinBandwidth — Ширина окна, минимум

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 8. **Пределы в коде:** 3.0 … 500.0.

**Механика (из кода):** Баров.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `HkMaxBandwidth` — HkMinBandwidth < HkMaxBandwidth; пара Min/Max: нижняя граница меньше верхней.

**Коридор и шаг:** [4, 6, 8, 12, 16] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[4, 6, 8, 12, 16]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HkMinBandwidth` + `HkMaxBandwidth` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.50 · [H06] HkMaxBandwidth — Ширина окна, максимум

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 40. **Пределы в коде:** 4.0 … 1000.0.

**Механика (из кода):** Баров.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `HkMinBandwidth` — HkMinBandwidth < HkMaxBandwidth; пара Min/Max: нижняя граница меньше верхней.

**Порядок:** исследуется после `HkMinBandwidth` — родитель должен быть VALIDATED.

**Коридор и шаг:** [20, 30, 40, 60, 80] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[20, 30, 40, 60, 80]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HkMaxBandwidth` + `HkMinBandwidth` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.51 · [H07] HkHLow — Хёрст, нижняя граница отображения

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** double. **Единица:** доля — порог или пропорция от 0 до 1; увеличение ужесточает отбор.
**По умолчанию:** 0.37. **Пределы в коде:** 0.0 … 1.0.

**Механика (из кода):** H ниже — минимальная ширина.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Крайние значения вырождают механизм: пропускает всё или ничего.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `HkHHigh` — HkHLow < HkHHigh; пара Low/High: нижняя граница меньше верхней.

**Коридор и шаг:** [0.22, 0.27, 0.32, 0.37, 0.42, 0.47, 0.52] — правило: доля 0–1: шаг 0,05 вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.22, 0.27, 0.32, 0.37, 0.42, 0.47, 0.52]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HkHLow` + `HkHHigh` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.52 · [H08] HkHHigh — Хёрст, верхняя граница отображения

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** double. **Единица:** доля — порог или пропорция от 0 до 1; увеличение ужесточает отбор.
**По умолчанию:** 0.57. **Пределы в коде:** 0.0 … 1.0.

**Механика (из кода):** H выше — максимальная ширина.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Крайние значения вырождают механизм: пропускает всё или ничего.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `HkHLow` — HkHLow < HkHHigh; пара Low/High: нижняя граница меньше верхней.

**Порядок:** исследуется после `HkHLow` — родитель должен быть VALIDATED.

**Коридор и шаг:** [0.42, 0.47, 0.52, 0.57, 0.62, 0.67, 0.72] — правило: доля 0–1: шаг 0,05 вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.42, 0.47, 0.52, 0.57, 0.62, 0.67, 0.72]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HkHHigh` + `HkHLow` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.53 · [H09] HkSlopeThreshold — Порог наклона, тиков на бар

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.5. **Пределы в коде:** 0.0 … 10.0.

**Механика (из кода):** Ниже — нейтраль.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.25, 0.375, 0.5, 0.625, 0.75] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.25, 0.375, 0.5, 0.625, 0.75]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HkSlopeThreshold` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.54 · [H10] HkSignalMode — Режим сигнала

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Выключено — фильтр.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.55 · [H11] HkExpGate — Шлюз блуждания

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** H в полосе [H12] вокруг уровня блуждания — нейтраль. ЭКСПЕРИМЕНТ: выключено по умолчанию.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `HkExpGateBand` — HkExpGateBand действует при HkExpGate = true; числовой параметр эксперимента без флага не влияет.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.56 · [H13] HkExpInverse — Обратное отображение

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Антиперсистентный рынок — окно шире. ЭКСПЕРИМЕНТ: выключено по умолчанию.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `HkExpGateBand` — HkExpGateBand действует при HkExpInverse = true; числовой параметр эксперимента без флага не влияет.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.57 · [H14] HkExpConfidence — Уверенность по Хёрсту

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Уверенность наклона умножается на силу персистентности. ЭКСПЕРИМЕНТ: выключено по умолчанию.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:**

- `HkExpGateBand` — HkExpGateBand действует при HkExpConfidence = true; числовой параметр эксперимента без флага не влияет.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 3.58 · [H12] HkExpGateBand — Полоса шлюза

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** double. **Единица:** доля — порог или пропорция от 0 до 1; увеличение ужесточает отбор.
**По умолчанию:** 0.03. **Пределы в коде:** 0.0 … 0.5.

**Механика (из кода):** Для [H11].

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Крайние значения вырождают механизм: пропускает всё или ничего.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:**

- `HkExpGate` — HkExpGateBand действует при HkExpGate = true; числовой параметр эксперимента без флага не влияет.
- `HkExpInverse` — HkExpGateBand действует при HkExpInverse = true; числовой параметр эксперимента без флага не влияет.
- `HkExpConfidence` — HkExpGateBand действует при HkExpConfidence = true; числовой параметр эксперимента без флага не влияет.

**Порядок:** исследуется после `HkExpGate`, `HkExpInverse`, `HkExpConfidence` — родитель должен быть VALIDATED.

**Коридор и шаг:** [0.0, 0.03, 0.08, 0.13, 0.18] — правило: доля 0–1: шаг 0,05 вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.0, 0.03, 0.08, 0.13, 0.18]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HkExpGateBand` + `HkExpGate`, `HkExpInverse`, `HkExpConfidence` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 3.59 · [H15] HkRwLevel — Уровень блуждания оценщика

**Группа:** 11 · Ядро по Хёрсту (ширина окна регрессии по показателю Хёрста). **Тип:** double. **Единица:** доля — порог или пропорция от 0 до 1; увеличение ужесточает отбор.
**По умолчанию:** 0.47. **Пределы в коде:** 0.0 … 1.0.

**Механика (из кода):** 0,47 при окне 128 по моделированию; для другого окна — откалибровать на перемешанных данных.

**Поведенческая гипотеза:** отсеивает часть входов: число сделок падает; гипотеза полезна, только если доля прибыльных растёт быстрее, чем падает число. Крайние значения вырождают механизм: пропускает всё или ничего.

**Класс и исполнитель:** NUMERIC; исполнитель модулей на ПК.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.32, 0.37, 0.42, 0.47, 0.52, 0.57, 0.62] — правило: доля 0–1: шаг 0,05 вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.32, 0.37, 0.42, 0.47, 0.52, 0.57, 0.62]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `HkRwLevel` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.


## Этап 4. Риск и объём

### Шаг 4.1 · [E03] StopLossTicks — Стартовый стоп, тиков

**Группа:** 03 · Исполнение (режим без ордеров, стоп по умолчанию, серия исполнения). **Тип:** int. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 40. **Пределы в коде:** 1.0 … 10000.0.

**Механика (из кода):** Защитный стоп, выставляемый исполнителем при входе.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Слишком малое значение — срабатывания на шуме; слишком большое — механизм почти не срабатывает.

**Класс и исполнитель:** NUMERIC; оптимизатор на ПК. Эталонное имя: `stop_ticks`.

**Связанные настройки:**

- `DboMaxRangeTicks` — связь графа; уровень входа — граница базы; широкая база означает дальний противоположный край.

**Порядок:** исследуется после `DboMaxRangeTicks` — родитель должен быть VALIDATED.

**Коридор и шаг:** [100, 150, 200, 250, 300] — правило: сетка графа эталона. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[100, 150, 200, 250, 300]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `StopLossTicks` + `DboMaxRangeTicks` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.2 · [M31] GuardDailyLoss — Риск: дневной лимит убытка

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 1000000.0.

**Механика (из кода):** Ноль отключает. Валюта счёта.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `GuardDailyLoss` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.3 · [M32] GuardDailyProfit — Риск: дневной лимит прибыли

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 1000000.0.

**Механика (из кода):** Ноль отключает.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `GuardDailyProfit` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.4 · [M33] GuardBreachAction — Риск: действие при пробитии

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** SwGuardBreachAction. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwGuardBreachAction.BlockNewEntries. **Пределы в коде:** — … —. **Значения:** BlockNewEntries, BlockAndFlatten.

**Механика (из кода):** BlockNewEntries или BlockAndFlatten.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** BlockNewEntries, BlockAndFlatten — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 4.5 · [M34] GuardRestartPolicy — Риск: поведение при перезапуске

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** SwGuardRestartPolicy. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwGuardRestartPolicy.BlockUntilNextSession. **Пределы в коде:** — … —. **Значения:** BlockUntilNextSession, AssumeZeroPnl.

**Механика (из кода):** BlockUntilNextSession безопасно: история сделок экземпляра обнуляется при Disable и Enable, это проверено на сборке 8.1.8.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** BlockUntilNextSession, AssumeZeroPnl — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 4.6 · [M109] GuardUseDailyGuard — UseDailyGuard

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwGuardConfig.UseDailyGuard: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 4.7 · [M110] GuardUseProfitLock — UseProfitLock

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwGuardConfig.UseProfitLock: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 4.8 · [M111] GuardProfitLockArmAt — ProfitLockArmAt

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.0. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwGuardConfig.ProfitLockArmAt: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `GuardProfitLockArmAt` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.9 · [M112] GuardProfitLockGiveBackPct — ProfitLockGiveBackPct

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 25.0. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwGuardConfig.ProfitLockGiveBackPct: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [12.5, 18.75, 25.0, 31.25, 37.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[12.5, 18.75, 25.0, 31.25, 37.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `GuardProfitLockGiveBackPct` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.10 · [M113] GuardUseNewsFilter — UseNewsFilter

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwGuardConfig.UseNewsFilter: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 4.11 · [M114] GuardMinutesBefore — MinutesBefore

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 15. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwGuardConfig.MinutesBefore: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [8, 11, 15, 22, 30] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[8, 11, 15, 22, 30]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `GuardMinutesBefore` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.12 · [M115] GuardMinutesAfter — MinutesAfter

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 30. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwGuardConfig.MinutesAfter: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [15, 22, 30, 45, 60] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[15, 22, 30, 45, 60]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `GuardMinutesAfter` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.13 · [M116] GuardMinImpact — MinImpact

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 3. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwGuardConfig.MinImpact: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [2, 3, 4, 6] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[2, 3, 4, 6]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `GuardMinImpact` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.14 · [M117] GuardMissingCalendarBlocks — MissingCalendarBlocks

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwGuardConfig.MissingCalendarBlocks: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 4.15 · [F01] SizingMode — Режим расчёта объёма

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** SwSizingMode. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwSizingMode.FixedQuantity. **Пределы в коде:** — … —. **Значения:** FixedQuantity, RiskMoneyPerTrade, RiskPercentOfEquity.

**Механика (из кода):** FixedQuantity — брать [E02]. RiskMoneyPerTrade — от денежного бюджета риска. RiskPercentOfEquity — от процента расчётного капитала. В двух последних объём вычисляется как бюджет, делённый на полный риск контракта, и отказ при нехватке бюджета записывается в трассировку, а не игнорируется.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** FixedQuantity, RiskMoneyPerTrade, RiskPercentOfEquity — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 4.16 · [F02] RiskMoneyPerTrade — Бюджет риска на сделку

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0. **Пределы в коде:** — … —.

**Механика (из кода):** Деньги на одну сделку при режиме RiskMoneyPerTrade.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `RiskMoneyPerTrade` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.17 · [F03] AccountEquityReference — Расчётный капитал

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0. **Пределы в коде:** — … —.

**Механика (из кода):** Ручное значение капитала при режиме RiskPercentOfEquity. Живой капитал счёта намеренно не читается: он недетерминирован между прогонами.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `AccountEquityReference` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.18 · [F04] RiskPercentOfEquity — Риск на сделку, процент

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0.5. **Пределы в коде:** 0.01 … 100.0.

**Механика (из кода):** Доля расчётного капитала на одну сделку.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.25, 0.375, 0.5, 0.625, 0.75] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.25, 0.375, 0.5, 0.625, 0.75]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `RiskPercentOfEquity` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.19 · [F05] MinQuantity — Минимум контрактов

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1. **Пределы в коде:** 1.0 … 1000.0.

**Механика (из кода):** Расчётный объём ниже этого значения означает отказ от входа, а не округление вверх.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:**

- `MaxQuantity` — MinQuantity < MaxQuantity; пара Min/Max: нижняя граница меньше верхней.

**Коридор и шаг:** [1, 2] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `MinQuantity` + `MaxQuantity` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.20 · [F06] MaxQuantity — Максимум контрактов

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 5. **Пределы в коде:** 1.0 … 1000.0.

**Механика (из кода):** Жёсткий верхний предел. Если он ниже, чем требует структура ступеней, часть ступеней не сработает.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:**

- `MinQuantity` — MinQuantity < MaxQuantity; пара Min/Max: нижняя граница меньше верхней.

**Порядок:** исследуется после `MinQuantity` — родитель должен быть VALIDATED.

**Коридор и шаг:** [2, 4, 5, 8, 10] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[2, 4, 5, 8, 10]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `MaxQuantity` + `MinQuantity` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.21 · [F07] RoundTurnCostPerContract — Издержки круга на контракт

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 10000.0.

**Механика (из кода):** Комиссия обеих сторон плюс биржевые сборы. Входит в полный риск контракта и в минимальный отступ безубытка.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `RoundTurnCostPerContract` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.22 · [F08] SlippageReserveTicks — Резерв на проскальзывание, тиков

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** int. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 2. **Пределы в коде:** 0.0 … 1000.0.

**Механика (из кода):** Добавляется к риску контракта при расчёте объёма. Без него объём систематически завышается.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Слишком малое значение — срабатывания на шуме; слишком большое — механизм почти не срабатывает.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2, 3, 4] — правило: тики: целые кратные шагу цены, ×0,5…×2. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2, 3, 4]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `SlippageReserveTicks` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.23 · [F11] StopMode — Режим стартового стопа

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** SwStopMode. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwStopMode.FixedTicks. **Пределы в коде:** — … —. **Значения:** FixedTicks, PriceDollars, AtrMultiple.

**Механика (из кода):** FixedTicks — в тиках. PriceDollars — в долларах ДВИЖЕНИЯ ЦЕНЫ, не результата: для микрозолота с шагом 0.10 значение 25 даёт 250 тиков. AtrMultiple — множитель ATR.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** FixedTicks, PriceDollars, AtrMultiple — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 4.24 · [F12] StopPriceDollars — Стоп, долларов движения цены

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 100000.0.

**Механика (из кода):** Действует при режиме PriceDollars. Путаница этой величины с денежным результатом даёт ошибку на порядок.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `StopPriceDollars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.25 · [F13] StopAtrMultiple — Множитель ATR для стопа

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 2.0. **Пределы в коде:** 0.1 … 50.0.

**Механика (из кода):** Действует при режиме AtrMultiple.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1.0, 1.5, 2.0, 2.5, 3.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1.0, 1.5, 2.0, 2.5, 3.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `StopAtrMultiple` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.26 · [F14] AtrPeriod — Период ATR

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 14. **Пределы в коде:** 2.0 … 500.0.

**Механика (из кода):** Общий для стопа и трейлинга. Индикатор создаётся один раз при загрузке данных.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [7, 10, 14, 21, 28] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[7, 10, 14, 21, 28]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `AtrPeriod` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 4.27 · [F21] UseScaleOut — Включить ступенчатую фиксацию

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Частичное закрытие позиции по мере движения цены.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 4.28 · [F29] KeepRunner — Оставлять остаток

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Последний контракт не закрывается ступенями и ведётся трейлингом.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 4.29 · [F52] MinBarsBetweenStopMoves — Минимум баров между переносами стопа

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 1000.0.

**Механика (из кода):** Антидребезг. Ноль разрешает перенос на каждом баре.

**Поведенческая гипотеза:** меняет масштаб риска: влияет на ПРОСАДКУ и абсолютную прибыль сильнее, чем на долю прибыльных. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `MinBarsBetweenStopMoves` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.


## Этап 5. Сопровождение и выходы

### Шаг 5.1 · [M41] AStopSlot — Адапт.стоп: слот серии

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Слот пула для расчёта линии.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** выбор серии — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 5.2 · [M42] AStopAtrPeriod — Адапт.стоп: период

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 10. **Пределы в коде:** 2.0 … 200.0.

**Механика (из кода):** Период сглаживания истинного диапазона.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [5, 8, 10, 15, 20] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[5, 8, 10, 15, 20]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `AStopAtrPeriod` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.3 · [M43] AStopWidthMode — Адапт.стоп: режим ширины

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** SwAdaptiveWidth. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwAdaptiveWidth.VolatilityBuckets. **Пределы в коде:** — … —. **Значения:** Fixed, VolatilityBuckets.

**Механика (из кода):** Fixed или VolatilityBuckets по рангу волатильности.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Fixed, VolatilityBuckets — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 5.4 · [M44] AStopFixedMultiplier — Адапт.стоп: множитель

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 3.0. **Пределы в коде:** 0.1 … 50.0.

**Механика (из кода):** Действует при режиме Fixed.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1.5, 2.25, 3.0, 3.75, 4.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1.5, 2.25, 3.0, 3.75, 4.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `AStopFixedMultiplier` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.5 · [M51] EscortLineNumber — Выход: номер линии

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 2. **Пределы в коде:** 1.0 … 3.0.

**Механика (из кода):** Какая линия ведёт позицию: 1, 2 или 3.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2, 3] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2, 3]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `EscortLineNumber` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.6 · [M52] EscortTrigger — Выход: повод

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** SwEscortExitTrigger. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwEscortExitTrigger.LineFlip. **Пределы в коде:** — … —. **Значения:** LineFlip, PriceCross, FlipOrCross.

**Механика (из кода):** LineFlip, PriceCross или FlipOrCross.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** LineFlip, PriceCross, FlipOrCross — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 5.7 · [M53] EscortConfirmBars — Выход: подтверждение, баров

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 1. **Пределы в коде:** 1.0 … 100.0.

**Механика (из кода):** Сколько баров подряд линия держит встречное направление. Единица — реакция на первый разворот.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `EscortConfirmBars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.8 · [M118] AStopMultiplierLowVol — MultiplierLowVol

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 2.0. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwAdaptiveStopConfig.MultiplierLowVol: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:**

- `AStopMultiplierHighVol` — AStopMultiplierLowVol < AStopMultiplierHighVol; пара Low/High: нижняя граница меньше верхней.

**Коридор и шаг:** [1.0, 1.5, 2.0, 2.5, 3.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1.0, 1.5, 2.0, 2.5, 3.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `AStopMultiplierLowVol` + `AStopMultiplierHighVol` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.9 · [M119] AStopMultiplierMidVol — MultiplierMidVol

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 3.0. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwAdaptiveStopConfig.MultiplierMidVol: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1.5, 2.25, 3.0, 3.75, 4.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1.5, 2.25, 3.0, 3.75, 4.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `AStopMultiplierMidVol` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.10 · [M120] AStopMultiplierHighVol — MultiplierHighVol

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 4.0. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwAdaptiveStopConfig.MultiplierHighVol: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:**

- `AStopMultiplierLowVol` — AStopMultiplierLowVol < AStopMultiplierHighVol; пара Low/High: нижняя граница меньше верхней.

**Порядок:** исследуется после `AStopMultiplierLowVol` — родитель должен быть VALIDATED.

**Коридор и шаг:** [2.0, 3.0, 4.0, 5.0, 6.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[2.0, 3.0, 4.0, 5.0, 6.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `AStopMultiplierHighVol` + `AStopMultiplierLowVol` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.11 · [M121] AStopVolRankLookback — VolRankLookback

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 100. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwAdaptiveStopConfig.VolRankLookback: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [50, 75, 100, 150, 200] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[50, 75, 100, 150, 200]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `AStopVolRankLookback` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.12 · [M122] AStopLowVolPercentile — LowVolPercentile

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 33.0. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwAdaptiveStopConfig.LowVolPercentile: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:**

- `AStopHighVolPercentile` — AStopLowVolPercentile < AStopHighVolPercentile; пара Low/High: нижняя граница меньше верхней.

**Коридор и шаг:** [16.5, 24.75, 33.0, 41.25, 49.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[16.5, 24.75, 33.0, 41.25, 49.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `AStopLowVolPercentile` + `AStopHighVolPercentile` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.13 · [M123] AStopHighVolPercentile — HighVolPercentile

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 67.0. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwAdaptiveStopConfig.HighVolPercentile: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:**

- `AStopLowVolPercentile` — AStopLowVolPercentile < AStopHighVolPercentile; пара Low/High: нижняя граница меньше верхней.

**Порядок:** исследуется после `AStopLowVolPercentile` — родитель должен быть VALIDATED.

**Коридор и шаг:** [33.5, 50.25, 67.0, 83.75, 100.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[33.5, 50.25, 67.0, 83.75, 100.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `AStopHighVolPercentile` + `AStopLowVolPercentile` | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.14 · [M124] AStopWarmupBars — WarmupBars

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 60. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwAdaptiveStopConfig.WarmupBars: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [30, 45, 60, 90, 120] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[30, 45, 60, 90, 120]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `AStopWarmupBars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.15 · [M125] AStopRequireProtectiveSide — RequireProtectiveSide

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwAdaptiveStopConfig.RequireProtectiveSide: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 5.16 · [M126] AStopMinBarsBetweenRequests — MinBarsBetweenRequests

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 1. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwAdaptiveStopConfig.MinBarsBetweenRequests: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `AStopMinBarsBetweenRequests` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.17 · [M127] EscortFullExit — FullExit

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwEscortLineConfig.FullExit: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 5.18 · [M128] EscortPartialQuantity — PartialQuantity

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwEscortLineConfig.PartialQuantity: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `EscortPartialQuantity` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.19 · [M129] EscortMinBarsInTrade — MinBarsInTrade

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 1. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwEscortLineConfig.MinBarsInTrade: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `EscortMinBarsInTrade` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.20 · [M130] EscortStaleAfterBars — StaleAfterBars

**Группа:** 04 · Настройки модулей (PAC (структура), TRFP (линии), время, режим, охрана, адаптивный стоп, сопровождение). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 50. **Пределы в коде:** — … —.

**Механика (из кода):** Поле SwEscortLineConfig.StaleAfterBars: восстановлено в меню — модуль его знал, меню нет. Значение по умолчанию — из конфигурации модуля.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [25, 38, 50, 75, 100] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[25, 38, 50, 75, 100]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `EscortStaleAfterBars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.21 · [F22] ScaleSteps — Количество ступеней

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 2. **Пределы в коде:** 1.0 … 10.0.

**Механика (из кода):** Сколько раз позиция фиксируется частично.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2, 3, 4] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2, 3, 4]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `ScaleSteps` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.22 · [F23] StepDistanceMode — Мера расстояния ступеней

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** SwStepDistanceMode. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwStepDistanceMode.RMultiple. **Пределы в коде:** — … —. **Значения:** FixedTicks, PriceDollars, RMultiple.

**Механика (из кода):** FixedTicks и PriceDollars задают абсолютное расстояние. RMultiple задаёт его в долях начального риска: ступень при 1R означает, что заработано столько же, сколько поставлено. Это финансово корректная мера, не зависящая от инструмента.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** FixedTicks, PriceDollars, RMultiple — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 5.23 · [F24] StepFixedTicks — Шаг ступени, тиков

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** int. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 40. **Пределы в коде:** 1.0 … 100000.0.

**Механика (из кода):** Действует при режиме FixedTicks.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Слишком малое значение — срабатывания на шуме; слишком большое — механизм почти не срабатывает.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [20, 30, 40, 50, 60, 80] — правило: тики: целые кратные шагу цены, ×0,5…×2. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[20, 30, 40, 50, 60, 80]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `StepFixedTicks` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.24 · [F25] StepPriceDollars — Шаг ступени, долларов цены

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 100000.0.

**Механика (из кода):** Действует при режиме PriceDollars.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.0] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.0]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `StepPriceDollars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.25 · [F26] StepRMultiple — Шаг ступени, долей R

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1.0. **Пределы в коде:** 0.1 … 20.0.

**Механика (из кода):** Действует при режиме RMultiple. Значение 1.0 ставит первую ступень на расстоянии начального риска.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.5, 0.75, 1.0, 1.25, 1.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.5, 0.75, 1.0, 1.25, 1.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `StepRMultiple` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.26 · [F27] ContractsOnStep1 — Контрактов на первой ступени

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 1000.0.

**Механика (из кода):** Объём первой фиксации, независимый от деления остальной позиции. Ноль возвращает первую ступень под общее правило [F28].

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `ContractsOnStep1` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.27 · [F28] ContractsPerStep — Контрактов на ступень

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 1000.0.

**Механика (из кода):** Ноль означает автоматическое деление объёма с учётом остатка под линию.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `ContractsPerStep` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.28 · [F31] BreakevenMode — Режим безубытка

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** SwBreakevenMode. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwBreakevenMode.Off. **Пределы в коде:** — … —. **Значения:** Off, AfterStep1, AfterStep2, AtRMultiple.

**Механика (из кода):** Off, AfterStep1, AfterStep2 или AtRMultiple. Учитываются ПОДТВЕРЖДЁННЫЕ ступени: отправленная, но не исполненная заявка безубыток не включает.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Off, AfterStep1, AfterStep2, AtRMultiple — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 5.29 · [F32] BreakevenOffsetTicks — Отступ безубытка, тиков

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** int. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 2. **Пределы в коде:** 0.0 … 10000.0.

**Механика (из кода):** Смещение в сторону прибыли. Модуль автоматически поднимает его до величины, покрывающей издержки круга: при меньшем значении срабатывание безубыточного стопа даёт убыток. Предупреждение печатается при загрузке.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Слишком малое значение — срабатывания на шуме; слишком большое — механизм почти не срабатывает.

**Класс и исполнитель:** NUMERIC; оптимизатор на ПК. Эталонное имя: `be_offset_ticks`.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1, 2, 3] — правило: сетка графа эталона. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1, 2, 3]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `BreakevenOffsetTicks` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.30 · [F33] BreakevenAtR — Безубыток при R

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1.0. **Пределы в коде:** 0.01 … 20.0.

**Механика (из кода):** Порог в долях начального риска при режиме AtRMultiple.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.5, 0.75, 1.0, 1.25, 1.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.5, 0.75, 1.0, 1.25, 1.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `BreakevenAtR` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.31 · [F34] BreakevenOnBestPrice — Безубыток и трейлинг по максимуму

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Включено — порог безубытка и включения трейлинга считается по лучшей цене позиции (MFE), как в исследовании и контрольном бэктесте. Выключено — по закрытию бара, позже и реже.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 5.32 · [F41] TrailMode — Режим трейлинга

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** SwTrailMode. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** SwTrailMode.Off. **Пределы в коде:** — … —. **Значения:** Off, FixedDistance, AtrMultiple, StepLock.

**Механика (из кода):** Off. FixedDistance — фиксированное расстояние от экстремума. AtrMultiple — множитель ATR от экстремума. StepLock — после ступени k стоп встаёт на уровень ступени k минус один; при первой ступени это цена входа.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Вариант выбирается по проверке вперёд, а не по лучшему бэктесту.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** Off, FixedDistance, AtrMultiple, StepLock — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 5.33 · [F42] TrailActivateAtR — Включать трейлинг при R

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1.0. **Пределы в коде:** 0.0 … 20.0.

**Механика (из кода):** Порог в долях начального риска, ниже которого трейлинг не работает.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [0.5, 0.75, 1.0, 1.25, 1.5] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[0.5, 0.75, 1.0, 1.25, 1.5]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `TrailActivateAtR` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.34 · [F43] TrailAtrMultiple — Множитель ATR для трейлинга

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** double. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 2.5. **Пределы в коде:** 0.1 … 50.0.

**Механика (из кода):** Действует при режиме AtrMultiple.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Ищется плато, а не пик: множитель с острым оптимумом почти наверняка подогнан.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [1.25, 1.875, 2.5, 3.125, 3.75] — правило: множитель: ±50% вокруг текущего. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[1.25, 1.875, 2.5, 3.125, 3.75]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `TrailAtrMultiple` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.35 · [F51] DisableStopMoveAfterStep1 — Запретить перенос стопа после первой фиксации

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Подавляет ОБЕ ветви: и безубыток, и трейлинг. Подавление одной делало бы запрет формальным, потому что защиту продолжает двигать вторая.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Включение оправдано, только если проверка вперёд лучше при включённом флаге.

**Класс и исполнитель:** STRUCTURAL; —.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Гипотеза к проверке:** False, True — сравнить варианты при подтверждённых числовых параметрах этапа; решает проверка вперёд, а не лучший бэктест.

### Шаг 5.36 · [F53] StepConfirmTimeoutBars — Таймаут подтверждения ступени, баров

**Группа:** 05 · Финансовый модуль (объём, начальный риск, безубыток, трейлинг, ступени выхода). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 3. **Пределы в коде:** 1.0 … 100.0.

**Механика (из кода):** Сколько баров ждать подтверждения запрошенной ступени. По истечении запрос считается потерянным и очередь снимается с блокировки. Без таймаута ступень, отклонённая арбитражем, блокировала бы все следующие ступени до конца сделки.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Слишком короткое окно — сигнал следует шуму; слишком длинное — сигнал запаздывает к развороту.

**Класс и исполнитель:** NUMERIC; Strategy Analyzer.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [2, 3, 4, 6] — правило: окно в барах: геометрическая сетка ×0,5…×2 — равная относительная чувствительность. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[2, 3, 4, 6]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `StepConfirmTimeoutBars` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.37 · [W16] DboMorningTrailTicks — Утро: трейлинг, тиков

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** double. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 15. **Пределы в коде:** 1.0 … 10000.0.

**Механика (из кода):** Расстояние трейлинга сделок этой сессии. Передаётся финансовому модулю с сигналом.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Слишком малое значение — срабатывания на шуме; слишком большое — механизм почти не срабатывает.

**Класс и исполнитель:** NUMERIC; оптимизатор на ПК. Эталонное имя: `trail_morning_ticks`.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [8, 10, 15, 20, 25, 30] — правило: сетка графа эталона. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[8, 10, 15, 20, 25, 30]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboMorningTrailTicks` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.

### Шаг 5.38 · [W26] DboEveningTrailTicks — Вечер: трейлинг, тиков

**Группа:** 08 · Пробой: окна и фильтры (двойной пробой утреннего и вечернего диапазона: окна, база, волатильность, тренд дня, повторные входы, трейлинг). **Тип:** double. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 10. **Пределы в коде:** 1.0 … 10000.0.

**Механика (из кода):** Расстояние трейлинга сделок этой сессии. Передаётся финансовому модулю с сигналом.

**Поведенческая гипотеза:** меняет судьбу открытой позиции: влияет на соотношение среднего выигрыша и проигрыша и на долю сделок около нуля. Слишком малое значение — срабатывания на шуме; слишком большое — механизм почти не срабатывает.

**Класс и исполнитель:** NUMERIC; оптимизатор на ПК. Эталонное имя: `trail_evening_ticks`.

**Связанные настройки:** жёстких связей нет; функционально — настройки той же группы. Во волне Б кластер — сама настройка и подтверждённые параметры её модуля.

**Коридор и шаг:** [6, 8, 10, 15, 20] — правило: сетка графа эталона. Коридор не выходит за пределы кода.

| Проход | Что выполнить | Принять, если | Отклонить, если |
|---|---|---|---|
| А. Разработчик | сетка `[6, 8, 10, 15, 20]`, прочие — текущие | плато: сырой лучший не дальше шага от лучшего на плато | одиночный пик |
| Б. Умный | `DboEveningTrailTicks` + параметры модуля | сделок ≥ 150, PF ≥ 1,35, просадка не хуже −3 500, дрейф ≤ 25% | любой критерий не выполнен |
| В. Система | совместная сетка этапа ±1 шаг, проверка вперёд 180/45/30 | эффективность ≥ 0,60, PBO ≤ 0,25 | иначе — заморозить на текущем значении |

**Как читать отклик:** монотонный рост к краю коридора — коридор сдвинуть и повторить волну А, это не оптимум; широкое плато — признак устойчивой механики; два разделённых пика — механизм работает в двух режимах рынка, проверить разбиение по годам.


## Вне исследования: защитные и служебные

### [S50] UseSeries1 — Серия 1 включена

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Слот 1 пула дополнительных серий. Объявляется в State.Configure и после запуска не меняется: AddDataSeries работает только там. Порядок слотов фиксирует индексы, перестановка заставит модули читать чужие бары.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [S51] Series1Type — Серия 1 — тип

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** BarsPeriodType. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** BarsPeriodType.Minute. **Пределы в коде:** — … —.

**Механика (из кода):** Тип периода серии слота 1.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [S52] Series1Value — Серия 1 — значение

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1. **Пределы в коде:** — … —.

**Механика (из кода):** Значение периода серии слота 1.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [S60] UseSeries2 — Серия 2 включена

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Слот 2 пула дополнительных серий. Объявляется в State.Configure и после запуска не меняется: AddDataSeries работает только там. Порядок слотов фиксирует индексы, перестановка заставит модули читать чужие бары.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [S61] Series2Type — Серия 2 — тип

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** BarsPeriodType. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** BarsPeriodType.Minute. **Пределы в коде:** — … —.

**Механика (из кода):** Тип периода серии слота 2.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [S62] Series2Value — Серия 2 — значение

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 5. **Пределы в коде:** — … —.

**Механика (из кода):** Значение периода серии слота 2.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [S70] UseSeries3 — Серия 3 включена

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Слот 3 пула дополнительных серий. Объявляется в State.Configure и после запуска не меняется: AddDataSeries работает только там. Порядок слотов фиксирует индексы, перестановка заставит модули читать чужие бары.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [S71] Series3Type — Серия 3 — тип

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** BarsPeriodType. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** BarsPeriodType.Minute. **Пределы в коде:** — … —.

**Механика (из кода):** Тип периода серии слота 3.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [S72] Series3Value — Серия 3 — значение

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 15. **Пределы в коде:** — … —.

**Механика (из кода):** Значение периода серии слота 3.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [S80] UseSeries4 — Серия 4 включена

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Слот 4 пула дополнительных серий. Объявляется в State.Configure и после запуска не меняется: AddDataSeries работает только там. Порядок слотов фиксирует индексы, перестановка заставит модули читать чужие бары.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [S81] Series4Type — Серия 4 — тип

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** BarsPeriodType. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** BarsPeriodType.Minute. **Пределы в коде:** — … —.

**Механика (из кода):** Тип периода серии слота 4.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [S82] Series4Value — Серия 4 — значение

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 60. **Пределы в коде:** — … —.

**Механика (из кода):** Значение периода серии слота 4.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [S90] ExecSeriesSlot — Серия исполнения — слот

**Группа:** 00 · Пул серий данных (какие таймфреймы видит стратегия; слоты 0–4 — общие серии для всех модулей). **Тип:** int. **Единица:** слот серии — выбирает таймфрейм данных; структурное решение.
**По умолчанию:** 0. **Пределы в коде:** 0.0 … 4.0.

**Механика (из кода):** Какая серия обслуживает такт решения и отправку заявок. Ноль — серия графика, 1..4 — слоты пула. Обычно это самая быстрая из загруженных: от неё зависит момент входа.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD1] Slot1Enabled — Слот 1 — структура, сигнал

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Включение первого слота. Подключение конкретного модуля выполняется в методе BuildSlots.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD2] Slot2Enabled — Слот 2 — линии, фильтр

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Включение второго слота.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD3] Slot3Enabled — Слот 3 — время, фильтр

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Включение третьего слота. По умолчанию пуст: подключите свой модуль в BuildSlots.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD4] Slot4Enabled — Слот 4 — режим рынка, фильтр

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Включение четвёртого слота. По умолчанию пуст.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD5] Slot5Enabled — Слот 5 — риск, фильтр

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Дневные лимиты убытка и прибыли, новостные паузы, блокировка после перезапуска. Последний барьер: ни один сигнальный модуль его не обходит.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD6] Slot6Enabled — Слот 6 — адаптивный стоп, сопровождение

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Сопровождение линией, расширяющейся с волатильностью. Ордеров не создаёт: просит о переносе стопа.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD7] Slot7Enabled — Слот 7 — выход по линии

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Закрытие при развороте линии против позиции. ТРЕБУЕТ включённого слота 2: без модуля линий не подключается, о чём сообщает при загрузке.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD8] Slot8Enabled — Слот 8 — пробой диапазона двух сессий, сигнал

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Утренний и вечерний пробой базы с фильтрами 4H и 15M по выводам исследования GC 2007–2026. Входит отложенным стоп-ордером до пробоя. ТРЕБУЕТ серий M1, M15 и 4H в пуле [S50]-[S80]. С модулем времени [MOD3] конфликтует по окнам.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD9] Slot9Enabled — Слот 9 — адаптивное ядро

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Локальная линейная регрессия цены с ядром компактного носителя. Роль — фильтр, либо сигнал при [K65].

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD10] Slot10Enabled — Слот 10 — ядро с шириной по Хёрсту

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Ядерная регрессия MOD9 с шириной окна по исправленному показателю Хёрста. Роль — фильтр; сигнал при [H10].

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD11] Slot11Enabled — Слот 11 — классификатор Лоренца

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** K ближайших по расстоянию Лоренца на нормализованных признаках. Роль — фильтр, подтверждающий входы; сигнал при [L12].

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD12] Slot12Enabled — Слот 12 — сигнал с ПК

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Сигнал, записанный Python на ПК. Ордеров с ПК нет. Устаревший сигнал закрывает вход.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD13] Slot13Enabled — Слот 13 — канал Калмана

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Канал Калмана: диапазон, пробой, выход по наклону. Роль — [C01].

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD14] Slot14Enabled — Слот 14 — рычаг свечи

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Рычаг свечи: голос кластеров объёма. Роль — [B01].

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [MOD15] Slot15Enabled — Слот 15 — иерархическая масса

**Группа:** 01 · Слоты модулей (какие модули включены; включение — структурная гипотеза, а не числовой параметр). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Дрейф взвешенной по объёму цены внутри окна по эшелонам 1, 5 и 15 минут.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [E01] DryRunMode — Режим без отправки ордеров

**Группа:** 03 · Исполнение (режим без ордеров, стоп по умолчанию, серия исполнения). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Включено — исполнитель только записывает намерения в трассировку, заявки не отправляются. Значение по умолчанию включено: боевой режим требует осознанного переключения.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [E02] DefaultQuantity — Объём по умолчанию

**Группа:** 03 · Исполнение (режим без ордеров, стоп по умолчанию, серия исполнения). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 1. **Пределы в коде:** 1.0 … 1000.0.

**Механика (из кода):** Объём входа, когда модуль роли Sizing не подключён.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [E04] MinBarsInTrade — Минимум баров в сделке

**Группа:** 03 · Исполнение (режим без ордеров, стоп по умолчанию, серия исполнения). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 1. **Пределы в коде:** 0.0 … 500.0.

**Механика (из кода):** Защита от закрытия на баре входа.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [P01] EnablePositionManager — Включить управление позицией

**Группа:** 06 · Управление позицией (устаревшее) (сохранено для совместимости шаблонов; не исследуется). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Встроенный модуль сопровождения: безубыток и трейлинг. Требований на закрытие не порождает, только перенос стопа.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [P02] BreakevenAfterTicks — Безубыток после, тиков

**Группа:** 06 · Управление позицией (устаревшее) (сохранено для совместимости шаблонов; не исследуется). **Тип:** int. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 30. **Пределы в коде:** 0.0 … 10000.0.

**Механика (из кода):** УСТАРЕЛО. Оставлено для совместимости шаблонов. Управление безубытком перешло к [F31] и [F33].

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [P04] TrailAfterTicks — Трейлинг после, тиков

**Группа:** 06 · Управление позицией (устаревшее) (сохранено для совместимости шаблонов; не исследуется). **Тип:** int. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 60. **Пределы в коде:** 0.0 … 10000.0.

**Механика (из кода):** УСТАРЕЛО. Управление трейлингом перешло к [F41] и [F42].

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [P05] TrailDistanceTicks — Дистанция трейлинга, тиков

**Группа:** 06 · Управление позицией (устаревшее) (сохранено для совместимости шаблонов; не исследуется). **Тип:** int. **Единица:** тики — расстояние в шагах цены; увеличение делает механизм реже срабатывающим и дальним.
**По умолчанию:** 40. **Пределы в коде:** 1.0 … 10000.0.

**Механика (из кода):** Расстояние трейлинга в тиках при режиме [F41] FixedDistance.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [T01] EnableTracing — Включить трассировку

**Группа:** 07 · Диагностика (журнал и панель; на торговлю не влияет). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Кольцевой буфер событий: отправка, приём, потеря, отказ, решение. Основной инструмент разбора чёрного ящика.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [T02] PrintTraceToOutput — Печатать трассировку в Output

**Группа:** 07 · Диагностика (журнал и панель; на торговлю не влияет). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Дублирование каждой записи в окно Output. На длинных прогонах сильно замедляет — включать для разбора.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [T03] TraceBufferSize — Размер буфера трассировки

**Группа:** 07 · Диагностика (журнал и панель; на торговлю не влияет). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 200. **Пределы в коде:** 10.0 … 5000.0.

**Механика (из кода):** Сколько последних событий хранить в памяти.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [T04] PanelTraceLines — Строк трассировки на панели

**Группа:** 07 · Диагностика (журнал и панель; на торговлю не влияет). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 6. **Пределы в коде:** 0.0 … 40.0.

**Механика (из кода):** Сколько последних событий показывать на панели.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [T05] SilentAfterBars — Считать молчанием после, баров

**Группа:** 07 · Диагностика (журнал и панель; на торговлю не влияет). **Тип:** int. **Единица:** бары — длина памяти; увеличение сглаживает и запаздывает, уменьшение ускоряет и шумит.
**По умолчанию:** 5. **Пределы в коде:** 1.0 … 1000.0.

**Механика (из кода):** Сколько баров без отправки считать отказом модуля выдавать сигнал.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [T10] ShowHubPanel — Показывать панель

**Группа:** 07 · Диагностика (журнал и панель; на торговлю не влияет). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** true. **Пределы в коде:** — … —.

**Механика (из кода):** Панель состояния: модули, здоровье, счётчики, решение, исполнение, трассировка.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [T11] PanelPosition — Положение панели

**Группа:** 07 · Диагностика (журнал и панель; на торговлю не влияет). **Тип:** TextPosition. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** TextPosition.TopLeft. **Пределы в коде:** — … —.

**Механика (из кода):** Угол графика.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [T12] PanelFontSize — Размер шрифта

**Группа:** 07 · Диагностика (журнал и панель; на торговлю не влияет). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 11. **Пределы в коде:** 6.0 … 24.0.

**Механика (из кода):** Кегль моноширинного шрифта панели.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [T21] OkBrush — Цвет исправного состояния

**Группа:** 07 · Диагностика (журнал и панель; на торговлю не влияет). **Тип:** Brush. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** Brushes.LimeGreen. **Пределы в коде:** — … —.

**Механика (из кода):** Все модули работают.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [T22] WarnBrush — Цвет предупреждения

**Группа:** 07 · Диагностика (журнал и панель; на торговлю не влияет). **Тип:** Brush. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** Brushes.Gold. **Пределы в коде:** — … —.

**Механика (из кода):** Прогрев, молчание или застой хотя бы одного модуля.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [T23] FaultBrush — Цвет отказа

**Группа:** 07 · Диагностика (журнал и панель; на торговлю не влияет). **Тип:** Brush. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** Brushes.OrangeRed. **Пределы в коде:** — … —.

**Механика (из кода):** Хотя бы один модуль бросил исключение.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [T24] IdleBrush — Цвет простоя

**Группа:** 07 · Диагностика (журнал и панель; на торговлю не влияет). **Тип:** Brush. **Единица:** перечисление — выбирает вариант механизма; исследуется сравнением вариантов при прочих равных.
**По умолчанию:** Brushes.Gray. **Пределы в коде:** — … —.

**Механика (из кода):** Модули выключены или не подключены.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [Q01] FsPath — Файл сигнала

**Группа:** 12 · Сигнал с ПК (внешний сигнал файлом; инфраструктура). **Тип:** string. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments), "NinjaTrader 8", "dz_export", "dz_signal.csv"). **Пределы в коде:** — … —.

**Механика (из кода):** Полный путь к файлу, который пишет DZ_PC_SignalBridge.py.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [Q02] FsMaxAge — Свежесть, секунд

**Группа:** 12 · Сигнал с ПК (внешний сигнал файлом; инфраструктура). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 120. **Пределы в коде:** 1.0 … 86400.0.

**Механика (из кода):** Сигнал старше — отвергается: ПК остановился.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [Q03] FsMaxLag — Отставание, баров

**Группа:** 12 · Сигнал с ПК (внешний сигнал файлом; инфраструктура). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 2. **Пределы в коде:** 1.0 … 100.0.

**Механика (из кода):** Сигнал с ПК всегда на бар позже; больше допуска — отвергается.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [Q04] FsSignalMode — Режим сигнала

**Группа:** 12 · Сигнал с ПК (внешний сигнал файлом; инфраструктура). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Выключено — фильтр.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [Q05] FsMinConfidence — Минимальная уверенность

**Группа:** 12 · Сигнал с ПК (внешний сигнал файлом; инфраструктура). **Тип:** double. **Единица:** доля — порог или пропорция от 0 до 1; увеличение ужесточает отбор.
**По умолчанию:** 0.0. **Пределы в коде:** 0.0 … 1.0.

**Механика (из кода):** Ниже — направление обнуляется.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [V01] VisualsEnabled — Визуализация модулей

**Группа:** 13 · Визуализация (отрисовка событий модулей). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Разрешает модулям выдавать события визуального слоя. Этап 0: события принимаются, отрисовка — следующий шаг.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [V02] VisualDebugEnabled — Отладочная визуализация

**Группа:** 13 · Визуализация (отрисовка событий модулей). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Дополнительные отладочные события модулей. Требует [V01].

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [U01] WsEnabled — Сервер пульта

**Группа:** 14 · Пульт реального времени (WebSocket, схема меню, пресеты). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** WebSocket на 127.0.0.1 для пульта «Атласа». Поднимается только в реальном времени, не в Strategy Analyzer.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [U02] WsPort — Порт

**Группа:** 14 · Пульт реального времени (WebSocket, схема меню, пресеты). **Тип:** int. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** 8088. **Пределы в коде:** 1024.0 … 65535.0.

**Механика (из кода):** Порт на 127.0.0.1. Две стратегии на одном ПК — разные порты.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [U03] WsAllowCommands — Разрешить команды пульта

**Группа:** 14 · Пульт реального времени (WebSocket, схема меню, пресеты). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** Пауза входов, возобновление, закрыть позицию. Выключено — пульт только наблюдает. Ключ — в dz_export\\atlas_ws_token.txt.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [U04] ExportSchema — Выгрузить схему меню

**Группа:** 14 · Пульт реального времени (WebSocket, схема меню, пресеты). **Тип:** bool. **Единица:** флаг — включает механизм целиком; исследуется как гипотеза «лучше ли с ним, чем без него».
**По умолчанию:** false. **Пределы в коде:** — … —.

**Механика (из кода):** При запуске пишет dz_export\\hub_menu_schema.json: все настройки с индексами, типами, пределами и умолчаниями — для конфигуратора задач.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

### [U05] PresetFile — Файл пресета

**Группа:** 14 · Пульт реального времени (WebSocket, схема меню, пресеты). **Тип:** string. **Единица:** множитель — масштаб механизма; увеличение расширяет полосы или пороги.
**По умолчанию:** "". **Пределы в коде:** — … —.

**Механика (из кода):** Имя файла в dz_export\\presets. Применяется при запуске: всё или ничего; режим без ордеров и доступ пульта пресет не меняет. Пусто — без пресета.

**Исследование:** не проводится — настройка защитная или служебная; её перебор раздувает число испытаний и не говорит ничего о рынке.

