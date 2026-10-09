#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
==========================================================================================
DZ_KILL_Switch.py — аварийная кнопка терминала «Атлас», v1.0 (2026-09-28)

  flatten   записать в папку incoming NinjaTrader команду FLATTENEVERYTHING — закрыть все
            позиции. Синтаксис сверен с руководством: FLATTENEVERYTHING;;;;;;;;;;;;
  alarm     ЭКСПЕРИМЕНТ: проверить пульс выгрузки баров (DZ_IND_BarExporter_S021);
            поток остановился — код возврата 3 и предупреждение. Позицию НЕ закрывает.
  drill     ЭКСПЕРИМЕНТ: учебная тревога — та же запись в песочницу вместо incoming.

ПРАВИЛА РУКОВОДСТВА NinjaTrader: файл в папке «<NinjaTrader>\\incoming», имя oif*.txt,
  уникальное для каждой команды — одинаковое имя при частой записи блокирует файл, и он
  не обрабатывается.

ГАРАНТИИ
  • Запись под временным именем, затем переименование — терминал не прочтёт полуфайл.
  • Подтверждение словом FLATTEN; ключ --yes — только для сценариев.
  • Проверка приёма: терминал удаляет обработанный файл. Не удалил за --wait секунд —
    интерфейс автоматической торговли в настройках NinjaTrader, вероятно, выключен.
  • Журнал kill_switch.log — каждое нажатие со временем и исходом.
==========================================================================================
"""
import argparse, datetime as dt, json, os, sys, time

VERSION = "DZ_KILL_Switch-v1.0 (2026-09-28)"
NT = os.path.join(os.path.expanduser("~"), "Documents", "NinjaTrader 8")
COMMAND = "FLATTENEVERYTHING;;;;;;;;;;;;"


def log(text):
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "kill_switch.log"), "a", encoding="utf-8") as f:
        f.write(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {text}\n")


def write_oif(folder, line):
    os.makedirs(folder, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    tmp = os.path.join(folder, f"~dz_{stamp}.tmp")          # не подходит под oif*.txt
    final = os.path.join(folder, f"oif_dz_{stamp}.txt")
    with open(tmp, "w", encoding="ascii") as f:
        f.write(line + "\n")
    os.replace(tmp, final)
    return final


def flatten(a):
    if not a.yes:
        ans = input("Закрыть ВСЕ позиции во ВСЕХ счетах NinjaTrader? Наберите FLATTEN: ").strip()
        if ans != "FLATTEN":
            print("Отменено."); log("ОТМЕНЕНО оператором"); return 1
    path = write_oif(a.incoming, COMMAND)
    log(f"ЗАПИСАНО {path}")
    t0 = time.time()
    while time.time() - t0 < a.wait:
        if not os.path.exists(path):
            print(f"✓ Команда принята терминалом за {time.time() - t0:.1f} с."); log("ПРИНЯТО терминалом"); return 0
        time.sleep(0.2)
    print(f"✗ Файл не обработан за {a.wait} с: {path}\n  Проверьте, что NinjaTrader запущен и интерфейс автоматической "
          f"торговли включён в его настройках. Позиции закройте вручную!")
    log("НЕ ОБРАБОТАНО терминалом"); return 2


def alarm(a):
    m = json.load(open(a.manifest, encoding="utf-8"))
    last = dt.datetime.strptime(m["last_write_utc"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=dt.timezone.utc)
    age = (dt.datetime.now(dt.timezone.utc) - last).total_seconds() / 60
    if age > a.max_age_min:
        print(f"⚠ ТРЕВОГА: поток баров {m.get('instrument')} молчит {age:.0f} мин (порог {a.max_age_min}). "
              f"Проверьте терминал; при открытой позиции решите вопрос аварийной кнопкой.")
        log(f"ТРЕВОГА пульса: {age:.0f} мин"); return 3
    print(f"✓ Пульс в норме: последний бар записан {age:.1f} мин назад."); return 0


def main():
    ap = argparse.ArgumentParser(description=VERSION); sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("flatten"); f.add_argument("--incoming", default=os.path.join(NT, "incoming"))
    f.add_argument("--wait", type=float, default=10.0); f.add_argument("--yes", action="store_true")
    d = sub.add_parser("drill"); d.add_argument("--sandbox", default="kill_switch_drill")
    al = sub.add_parser("alarm"); al.add_argument("--manifest", required=True); al.add_argument("--max-age-min", type=float, default=5.0)
    a = ap.parse_args()
    if a.cmd == "flatten": sys.exit(flatten(a))
    if a.cmd == "alarm": sys.exit(alarm(a))
    p = write_oif(a.sandbox, COMMAND)
    print(f"Учебная тревога: записан {p}\n  содержимое: {open(p, encoding='ascii').read().strip()}"); log(f"УЧЕНИЯ {p}")


if __name__ == "__main__":
    main()
