"""Тест парсера _fetch_module_info v1.58 на копии ответа реального устройства."""
import sys
import types


# --- стабы PyQt6/paramiko (не нужны для теста worker-логики) ---
class _Sig:
    def __init__(self, *a, **k): pass
    def emit(self, *a): pass
    def connect(self, *a): pass
class _QThread:
    @staticmethod
    def msleep(x): pass
qtcore = types.ModuleType("PyQt6.QtCore")
for n in ("pyqtSignal", "Qt"):
    setattr(qtcore, n, _Sig)
qtcore.QThread = _QThread

class _AnyAttrModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return type(name, (), {"__init__": lambda self, *a, **k: None})

qtwidgets = _AnyAttrModule("PyQt6.QtWidgets")
qtgui = _AnyAttrModule("PyQt6.QtGui")
pyqt6 = types.ModuleType("PyQt6")
pyqt6.QtCore = qtcore
pyqt6.QtWidgets = qtwidgets
pyqt6.QtGui = qtgui
sys.modules["PyQt6"] = pyqt6
sys.modules["PyQt6.QtCore"] = qtcore
sys.modules["PyQt6.QtWidgets"] = qtwidgets
sys.modules["PyQt6.QtGui"] = qtgui
paramiko = types.ModuleType("paramiko")
paramiko.SSHClient = object
paramiko.AutoAddPolicy = object
sys.modules["paramiko"] = paramiko

import glob  # noqa: E402
import importlib.util  # noqa: E402
import os  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

_srcs = sorted(glob.glob(os.path.join(ROOT, "MFC_Module_Flasher_v*.py")))
assert _srcs, "Исходник приложения не найден"
_spec = importlib.util.spec_from_file_location("mfc_updater", _srcs[-1])
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

# --- копия module_info_arr реального устройства (голова 21 + хвост 11) ---
def mk(idx, mt, cfg, sc):
    return {"index": idx, "module_type": mt, "module_type_config": cfg, "slot_count": sc}

head = [
    mk(0,"NA","",1),          # артефакт бэкенда (не слот)
    mk(1,"CPU","CPU",2),      # CPU в слоте 1, занимает слоты 1..2
    mk(2,"NA","",1),          # резерв CPU
    mk(3,"NA","",1),          # пустой слот 3
    mk(4,"DIR12","DIR12",1), mk(5,"DIR12","DIR12",1), mk(6,"DIR12","DIR12",1),
    mk(7,"DIR12","DIR12",1), mk(8,"DIR12","DIR12",1), mk(9,"DIR12","DIR12",1),
    mk(10,"DIR12","DIR12",1), mk(11,"DIR12","DIR12",1),
    mk(12,"DOR12","DOR12",1), mk(13,"DOR12","DOR12",1), mk(14,"NA","",1),
    mk(15,"DIU20","DIU20",1), mk(16,"NA","",1), mk(17,"NA","",1),
    mk(18,"NA","",1), mk(19,"NA","",1),
    mk(20,"POWER_UNIT","PSU",1),   # БП в слоте 20
    mk(21,"NA","",1),               # последний слот креста пуст
]

tail = [mk(i,"NA","",1) for i in range(0,11)]   # хвост-артефакт: повтор 0..10
info_arr = head + tail

# module_arr: отвечающие модули (slot_num 1-базируемый = физический слот)
def mmod(slot, sn, mt="NA"):
    return {"slot_num": slot, "serial_num": sn, "module_type": mt,
            "manufacture_date": "2024", "hardware_version": "R1", "firmware_version": "R2.2"}
module_arr = [mmod(1,"SN-CPU-01"), mmod(4,"SN-DIR-04"), mmod(5,"SN-DIR-05"),
              mmod(6,"SN-DIR-06"), mmod(7,"SN-DIR-07"), mmod(8,"SN-DIR-08"),
              mmod(9,"SN-DIR-09"), mmod(10,"SN-DIR-10"), mmod(11,"SN-DIR-11"),
              mmod(12,"SN-DOR-12"), mmod(13,"SN-DOR-13"), mmod(15,"SN-DIU-15"),
              mmod(20,"SN-PSU-20")]

resp = {"result": 0, "data": {"crate_slot_count": 21,
                              "module_info_arr": info_arr, "module_arr": module_arr}}

logs = []
w = mod.OperationWorker.__new__(mod.OperationWorker)
w.config = {"ip": "1.2.3.4", "api_path": "/x"}
w.log = lambda msg: logs.append(msg)

# перехват HTTP
orig_req = mod.BackendClient.request
mod.BackendClient.request = lambda self, req, params=None: resp
try:
    rows = w._fetch_module_info()
finally:
    mod.BackendClient.request = orig_req

mapping = {r["slot_num"]: r["module_type"] for r in rows}
summary = ", ".join(f"{r['slot_num']}:{r['module_type']}" for r in rows)
print("Соответствие слот/тип:", summary)
print("Строк:", len(rows))
for line in logs:
    print("LOG:", line)

fails = []


def chk(cond, msg):
    if not cond:
        fails.append(msg)

chk(len(rows) == 21, f"ожидалось 21 строку, получено {len(rows)}")
chk(mapping.get("1") == "CPU", f"слот 1 должен быть CPU, а {mapping.get('1')!r}")
chk(mapping.get("2") == "CPU", f"слот 2 (резерв CPU) должен быть CPU, а {mapping.get('2')!r}")
chk(mapping.get("3") == "NA", f"слот 3 должен быть NA, а {mapping.get('3')!r}")
chk(mapping.get("4") == "DIR12", f"слот 4 должен быть DIR12, а {mapping.get('4')!r}")
chk(mapping.get("12") == "DOR12", f"слот 12 DOR12, а {mapping.get('12')!r}")
chk(mapping.get("13") == "DOR12", f"слот 13 DOR12, а {mapping.get('13')!r}")
chk(mapping.get("14") == "NA", f"слот 14 NA, а {mapping.get('14')!r}")
chk(mapping.get("15") == "DIU20", f"слот 15 DIU20, а {mapping.get('15')!r}")
chk(mapping.get("20") == "POWER_UNIT", f"слот 20 POWER_UNIT, а {mapping.get('20')!r}")
by_slot = {r["slot_num"]: r for r in rows}
chk(by_slot["1"]["flashable"] is True, "слот 1: flashable должен быть True (есть SN)")
chk(by_slot["2"]["reserved"] is True, "слот 2: должен быть помечен как резерв")
chk(by_slot["2"]["flashable"] is False, "слот 2: прошивка запрещена (резерв)")
chk(by_slot["3"]["flashable"] is False, "слот 3: нет SN — прошивка запрещена")
chk(by_slot["4"]["flashable"] is True, "слот 4: DIR12 с SN — flashable True")
chk(not any(r["slot_num"] in ("22", "23", "24", "25", "26", "27", "28",
                              "29", "30", "31", "32") for r in rows),
    "мнимые слоты 22-32 присутствуют!")
chk(any("Хвостовых артефактных записей" in line and "11" in line for line in logs),
    "нет лога об отсечении хвоста (11)")
chk(any("slot = index" in line for line in logs), "нет лога о правиле slot = index")

# --- кейс 2: бэкенд НЕ печатает заглушки (шаг = slot_count) ---
head2 = [mk(1, "CPU", "CPU", 2), mk(3, "DIR12", "DIR12", 1),
         mk(4, "POWER_UNIT", "PSU", 1)]
resp2 = {"result": 0, "data": {"crate_slot_count": 4,
                               "module_info_arr": head2, "module_arr": [mmod(1, "S1")]}}
mod.BackendClient.request = lambda self, req, params=None: resp2
logs2 = []
w.log = lambda msg: logs2.append(msg)
rows2 = w._fetch_module_info()
map2 = {r["slot_num"]: r["module_type"] for r in rows2}
chk(map2.get("1")=="CPU" and map2.get("2")=="CPU" and map2.get("3")=="DIR12"
    and map2.get("4")=="POWER_UNIT", f"кейс2: неверный маппинг {map2}")
chk(rows2[1]["reserved"] is True and rows2[1]["flashable"] is False,
    "кейс2: резерв CPU не заблокирован")

# --- кейс 3: пустой ответ ---
resp3 = {"result": 0, "data": {"crate_slot_count": 0, "module_info_arr": [], "module_arr": []}}
mod.BackendClient.request = lambda self, req, params=None: resp3
w.log = lambda msg: None
rows3 = w._fetch_module_info()
chk(rows3 == [], f"кейс3: ожидался пустой список, получено {rows3}")

if fails:
    print("\nFAIL:")
    for f in fails:
        print(" -", f)
    sys.exit(1)
print("\nALL PASS")
