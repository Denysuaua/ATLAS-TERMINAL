# Движки оптимизации «Атласа» — руководство разработчика

**Версия:** 1.0 (2026-09-30) · **Основа:** `DZ_OPT_Engine_S021.py` v1.3, `DZ_OPT_WFA.py` v1.0, `DZ_ATLAS_Service.py` v1.0, `DZ_BT_DualBreakout_S021.py`, `DZ_OPT_Graph_DualBreakout.json`. Разделы 4 и 5 сгенерированы из графа и из реального прогона.

## 1. Контур

```
пульт (atlas_dashboard.html) ──POST /task──▶ DZ_ATLAS_Service.py ──▶ task_queue/ ──▶ running/ ──▶ done/ | failed/
                                                   │
                                                   ├─ задача ─▶ DZ_OPT_Engine_S021.py run ──▶ DZ_BT_DualBreakout_S021 (эталон)
                                                   └─ план WFA ─▶ DZ_OPT_WFA.py ──▶ оптимизатор по окнам: обучение, затем проверка
данные: DZ_DATA_Sanitizer ──▶ DZ_CERT_Data (data_certified/<СИМВОЛ>/) ──▶ оптимизатор по "data": "<СИМВОЛ>"
доверие: run_manifest.json (data_sha256) ──▶ DZ_AUDIT_Gatekeeper ◀── сертификат данных, паспорт инструмента, печать эмулятора
```

## 2. Задача `task.json`

| Ключ | Обязателен | Смысл |
|---|---|---|
| `task_id` | нет | имя папки результатов; иначе метка времени |
| `data` | да | путь к CSV **или** символ инструмента: `"MGC"` → `data_certified/MGC/MGC_M1.npz` с проверкой сертификата |
| `data_root` | нет | корень сертифицированных данных, по умолчанию `data_certified` |
| `instrument` | нет | ключ профиля в `instrument_profiles` графа: tick, usd_per_tick, комиссия |
| `mode` | да | `dev` — `optimize`; `param` — `target` + `depth`; `system` — `hypothesis` |
| `optimize` | dev | `{эталонное_имя: [значения]}` |
| `target, depth` | param | целевые параметры и глубина соседей по рёбрам графа |
| `hypothesis` | system | имя группы в `groups` графа |
| `base` | нет | фиксированные значения эталонных параметров; перекрывают профиль |
| `constraints` | нет | строки `a < b`; невозможные комбинации отбрасываются до запуска; неизвестное имя — отказ |
| `start, end` | нет | период; конец не включается |
| `objective` | нет | метрика цели, по умолчанию `SharpeDaily` |
| `max_trials` | нет | больше комбинаций — случайная выборка с зерном `seed` |
| `select` | нет | `plateau` (по умолчанию) или `raw` |
| `profile` | нет | `chicago` или `berlin` |
| `nt_template` | нет | шаблон NinjaTrader для правки лучшими значениями |

План проверки вперёд: `{"plan": "DZ-WFA-v1", "plan_id", "task": {…без периода…}, "windows": [{"train": [с, по), "test": [с, по)}]}`.

## 3. Выходы

| Файл | Содержимое |
|---|---|
| `results/<task_id>/summary.json` | итог — ключи ниже |
| `results/<task_id>/run_manifest.json` | `engine`, `task_id`, `data_sha256`, `data_file`, `data_certificate`, `period`, `instrument` — связь с сертификатом для шлюза |
| `results/<task_id>/best_trades.csv` | сделки лучшего набора |
| `results/<task_id>/trials.csv` | все испытания и метрики |
| `trials_registry.csv` | совокупный реестр испытаний проекта — основа дефлированного Шарпа |
| `results/<plan_id>_wfa.json / .csv` | проверка вперёд по окнам и в целом |
| `results/_service_status.json` | состояние очереди службы |

Ключи `summary.json` (из реального прогона): `engine`, `task_id`, `mode`, `space`, `trials_this_task`, `trials_cumulative`, `grid_total`, `objective`, `best_raw`, `best_plateau`, `best_selected`, `metrics_best_raw`, `metrics_best_plateau`, `deflated_sharpe`, `expected_max_sharpe_null`, `pbo`, `verdict`, `nt_values`, `data_sha256`, `data_file`, `data_certificate`, `period`.

**Массивы `.npz`.** Очиститель и кэш: `t, o, h, l, c, v`. Сертифицированные: `t_open, t_close, o, h, l, c, v`. Время — наносекунды UTC. Оптимизатор читает оба вида.

## 4. Параметры: эталон ↔ граф ↔ NinjaTrader

| Эталон (Python) | Свойство коммутатора | Индекс | По умолчанию | Диапазон в графе |
|---|---|---|---|---|
| `stop_ticks` | `StopLossTicks` | [E03] | 200 | [100, 150, 200, 250, 300] |
| `be_trigger_ticks` | — нет свойства | [F33] | 15 | [10, 15, 20, 25, 30] |
| `be_offset_ticks` | `BreakevenOffsetTicks` | [F32] | 1 | [1, 2, 3] |
| `trail_morning_ticks` | `DboMorningTrailTicks` | [W16] | 15 | [8, 10, 15, 20, 25, 30] |
| `trail_evening_ticks` | `DboEveningTrailTicks` | [W26] | 10 | [6, 8, 10, 15, 20] |
| `min_range_ticks` | `DboMinRangeTicks` | [W31] | 15 | [10, 15, 20] |
| `max_range_ticks` | `DboMaxRangeTicks` | [W32] | 45 | [35, 45, 55, 65] |
| `min_base_bars` | `DboMinBaseBars` | [W33] | 50 | [40, 50, 55] |
| `flat_threshold` | `DboFlatThreshold` | [W34] | 0.85 | [0.75, 0.8, 0.85, 0.9, 0.95] |
| `atr_fast` | `DboAtrFast` | [W35] | 20 | [10, 15, 20, 30] |
| `atr_slow` | `DboAtrSlow` | [W36] | 40 | [30, 40, 60, 80] |
| `trend_bars` | `DboTrendBars` | [W37] | 10 | [5, 8, 10, 15, 20] |
| `max_entries_per_session` | `DboMaxEntries` | [W39] | 0 | [0, 1, 2, 3] |

Профили инструментов (`instrument_profiles`):

- **MGC** — 3 контракта MGC по 1 доллару за тик. Диапазоны — стартовые для золота, не сертифицированные. Эталону передаётся: `{"tick": 0.1, "usd_per_tick": 3.0, "commission_rt_usd": 1.32}`.
- **GC** — 1 контракт GC: 10 долларов за тик. Комиссию укажите по своему тарифу. Эталону передаётся: `{"tick": 0.1, "usd_per_tick": 10.0, "commission_rt_usd": 4.5}`.

## 5. Изменения этой редакции — «было / стало»

**`DZ_OPT_Engine_S021.py → load_cache`**  
Было: `z["t"]` — только кэш очистителя.  
Стало: `z["t"]` или `z["t_open"]`.  
Основание: сертифицированные массивы хранят время открытия под именем `t_open`.

**`DZ_OPT_Engine_S021.py → run_task, данные`**  
Было: `"data": "MGC"` — попытка открыть `MGC` как CSV и падение.  
Стало: символ → `data_certified/MGC/MGC_M1.npz`; перед расчётом — проверка сертификата (П11), при расхождении — отказ.  
Основание: пункт Б ТЗ; данные берутся только сертифицированные.

**`DZ_OPT_Engine_S021.py → итог`**  
Было: отпечатка данных нет.  
Стало: `data_sha256` в `summary.json` и `run_manifest.json` — та же формула, что у очистителя.  
Основание: пункт В ТЗ: шлюз доказывает, что прогон сделан на сертифицированных данных.

**`DZ_OPT_Engine_S021.py → base`**  
Было: профиля инструмента нет.  
Стало: `instrument` задачи → `instrument_profiles[…].reference` → эталон (`tick`, `usd_per_tick`, `commission_rt_usd`).  
Основание: пункт Г ТЗ: эталон уже имеет эти поля; результат в долларах соответствует инструменту.

**`DZ_OPT_Graph_DualBreakout.json`**  
Было: профилей нет.  
Стало: `instrument_profiles` для MGC и GC со стартовыми диапазонами стопа и трейлинга.  
Основание: диапазоны — стартовые, не сертифицированные: их подтверждает оптимизация и проверка вперёд.

