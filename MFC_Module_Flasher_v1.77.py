"""
MFC Module Updater (IskraIO) — настольное приложение для прошивки модулей МФК.

Назначение:
    Автоматизация процесса обновления прошивок модулей многофункционального
    контроллера (МФК) через SSH/SFTP-агента IskraIO_Util и HTTP-бэкенд устройства.

Возможности:
    - Внедрение агента и файлов прошивок на устройство с контролем формата
      и двумя режимами лога — кратким/подробным (операция 1);
    - Создание сценария прошивки MakePlan (операция 2);
    - Импорт/экспорт сценария plan.xml (операции 3, 4);
    - Запуск прошивки Update с анализом result.txt (операция 6);
    - Выгрузка дампа операции (операция 7);
    - Просмотр результата прошивки (операция 8);
    - Редактирование сценария прошивки (СП) с автозаполнением (операции 9, 11);
    - Получение информации о модулях через HTTP-бэкенд (операция 10).

Зависимости:
    pip install -r requirements.txt   # PyQt6, paramiko

Запуск:
    python MFC_Module_Flasher_v1.69.py

История изменений: см. CHANGELOG.md (при каждой доработке увеличивайте
версию APP_VERSION и добавляйте запись в историю).

Автор: Екимов Д.А. @ 2026
Версия: 1.69
"""
import glob
import html
import http.cookiejar
import json
import os
import re
import sys
import tempfile
import time
import traceback
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

import paramiko
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

# --- Версия приложения (единая точка изменения при доработках) ---
APP_VERSION = "1.77"
APP_TITLE = f"Прошивка модулей МФК версия {APP_VERSION}"

CONFIG_FILE = "mfc_flasher_config.json"
DEFAULT_CONFIG = {
    "ip": "",
    "password": "",
    "agent_dir": "",
    "firmware_dir": "",
    "plan_xml": "",
    "api_path": "/vx3/backend.fcgi",
    "format_control": True,
    "verbose_log": False,
}

STYLESHEET = """
QMainWindow { background-color: #f5f5f5; }
QWidget { color: #222222; font-family: 'Segoe UI', 'Arial', sans-serif; font-size: 14px; }
QLabel { color: #1a1a1a; }
QLineEdit, QTextEdit, QTableWidget, QComboBox { background-color: #ffffff; border: 1px solid #b0b0b0; border-radius: 4px; padding: 5px; color: #000000; }
QTableWidget::item { padding: 5px; color: #000000; }
QHeaderView::section { background-color: #e0e0e0; color: #000000; padding: 5px; border: 1px solid #b0b0b0; font-weight: bold; }
QPushButton { color: white; border: none; border-radius: 4px; padding: 8px 15px; font-weight: bold; }
QPushButton#browse_btn { background-color: #3a3a3a; color: #ffffff; border: 1px solid #1a1a1a; }
QPushButton#browse_btn:hover { background-color: #555555; }
QPushButton#col1_btn_1 { background-color: #0078d7; }
QPushButton#col1_btn_1:hover { background-color: #005a9e; }
QPushButton#col1_btn_10 { background-color: #d83b01; }
QPushButton#col1_btn_10:hover { background-color: #a52d00; }
QPushButton#col1_btn_6 { background-color: #107c10; }
QPushButton#col1_btn_6:hover { background-color: #0b5e0b; }
QPushButton#col1_btn_8 { background-color: #5c2d91; }
QPushButton#col1_btn_8:hover { background-color: #442073; }
QPushButton#col1_btn_7 { background-color: #008272; }
QPushButton#col1_btn_7:hover { background-color: #005f53; }
QPushButton#col2_btn_2 { background-color: #0063b1; }
QPushButton#col2_btn_2:hover { background-color: #004c87; }
QPushButton#col2_btn_3 { background-color: #0099bc; }
QPushButton#col2_btn_3:hover { background-color: #00728b; }
QPushButton#col2_btn_4 { background-color: #8e8cd8; }
QPushButton#col2_btn_4:hover { background-color: #6e6cbf; }
QPushButton#col2_btn_9 { background-color: #6b6956; }
QPushButton#col2_btn_9:hover { background-color: #504e3f; }
/* v1.76: «Удалить агента» и «Автопрошивка» — стиль как у остальных кнопок
   (раньше не имели фона в таблице стилей: белый текст на белом). */
QPushButton#col1_btn_12 { background-color: #b54708; }
QPushButton#col1_btn_12:hover { background-color: #8a3606; }
QPushButton#col2_btn_13 { background-color: #107c10; }
QPushButton#col2_btn_13:hover { background-color: #0b5e0b; }
QPushButton#dialog_btn_dump { background-color: #008272; color: white; padding: 6px 20px; }
QPushButton#dialog_btn_dump:hover { background-color: #005f53; }
QPushButton#clear_btn { background-color: #6c757d; }
QPushButton#clear_btn:hover { background-color: #5a6268; }
QPushButton#dialog_btn_ok { background-color: #0078d7; color: white; padding: 6px 20px; }
QPushButton#dialog_btn_ok:hover { background-color: #005a9e; }
QPushButton#dialog_btn_cancel { background-color: #555555; color: white; padding: 6px 20px; }
QPushButton#dialog_btn_cancel:hover { background-color: #3a3a3a; }
QPushButton#autofill_btn { background-color: #b8860b; color: white; padding: 6px 20px; }
QPushButton#autofill_btn:hover { background-color: #8b6508; }
QPushButton#type_select_btn { background-color: #4a6fa5; color: white; padding: 5px 14px; }
QPushButton#type_select_btn:hover { background-color: #38567f; }
QPushButton#browse_fw_btn { background-color: #2e7d32; color: white; padding: 2px 8px; font-size: 12px; }
QPushButton#browse_fw_btn:hover { background-color: #1b5e20; }
QGroupBox { border: 1px solid #b0b0b0; border-radius: 5px; margin-top: 10px; padding-top: 15px; font-weight: bold; color: #000000; }
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QProgressBar { border: 1px solid #b0b0b0; border-radius: 5px; text-align: center; background-color: #ffffff; height: 22px; color: #000000; font-weight: bold; }
QProgressBar::chunk { background-color: #0078d7; border-radius: 4px; }
QCheckBox { spacing: 8px; color: #000000; }
QMessageBox, QDialog { background-color: #f5f5f5; color: #000000; }
QMessageBox QLabel, QDialog QLabel { color: #000000; font-weight: bold; }
QMessageBox QPushButton { background-color: #0078d7; color: white; min-width: 80px; }
"""


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ И ФУНКЦИИ
# ============================================================

class SSHClient:
    """
    Класс-обертка для работы с SSH и SFTP.

    Примечание: используется AutoAddPolicy (доверяем неизвестным ключам хоста),
    что допустимо только в доверенной локальной сети устройства.
    Пароль root хранится в локальном конфиге mfc_flasher_config.json
    (файл добавлен в .gitignore).
    """
    def __init__(self, ip, password):
        self.ip = ip
        self.password = password
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    def connect(self):
        self.client.connect(self.ip, username='root', password=self.password, timeout=10)

    def exec_command(self, command):
        stdin, stdout, stderr = self.client.exec_command(command)
        return stdout.read().decode(), stderr.read().decode()

    def sftp_get(self, remote_path, local_path):
        sftp = self.client.open_sftp()
        sftp.get(remote_path, local_path)
        sftp.close()

    def sftp_put(self, local_path, remote_path):
        sftp = self.client.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.close()

    def sftp_chmod(self, path, mode):
        sftp = self.client.open_sftp()
        sftp.chmod(path, mode)
        sftp.close()

    def sftp_remove(self, path):
        sftp = self.client.open_sftp()
        try:
            sftp.remove(path)
        except OSError:
            pass
        sftp.close()

    def sftp_stat(self, path):
        sftp = self.client.open_sftp()
        try:
            stat = sftp.stat(path)
            sftp.close()
            return stat
        except OSError:
            sftp.close()
            return None

    def sftp_listdir(self, path):
        sftp = self.client.open_sftp()
        try:
            files = sftp.listdir(path)
            sftp.close()
            return files
        except OSError:
            sftp.close()
            return []

    def close(self):
        self.client.close()


class BackendClient:
    """
    Клиент для работы с HTTP-бэкендом устройства.
    Реализует двухшаговую авторизацию с защитой от бесконечной рекурсии.
    API-путь фиксирован (v1.71): /vx3/backend.fcgi — поле ввода убрано из UI.
    """
    # Детализация HTTP-протокола (v1.71): в кратком режиме операционного
    # лога эти строки не показываются (полные — в файле http_debug.log).
    _DETAIL_MARKERS = ("Payload:", "Заголовки ответа:", "Тело ответа",
                       "Статус: 200", "--- ШАГ", "URL:",
                       "Актуальный SID:", "Актуальный токен:")

    # Фиксированный API-путь бэкенда (v1.71: поле ввода убрано из UI)
    API_PATH = "/vx3/backend.fcgi"

    def __init__(self, ip, log_callback=None, verbose=False):
        self.verbose = verbose
        self.ip = ip
        self.api_path = self.API_PATH
        self.api_url = f"http://{ip}{self.api_path}"
        self.base_url = f"http://{ip}/vx3/"
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.token = None
        self.sid = None
        self.log_callback = log_callback
        self.log_file = "http_debug.log"
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                f.write("=== HTTP Debug Log ===\n")
                f.write(f"Создан BackendClient для {self.ip}\n")
                f.write(f"API URL: {self.api_url}\n\n")
        except Exception as e:
            self._log(f"Не удалось создать лог-файл: {e}")

    def _log(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {msg}"
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass
        # v1.71: детализация HTTP (Payload, заголовки/тело ответа, статусы,
        # шаги запросов) передается в операционный журнал только в подробном
        # режиме; в http_debug.log пишутся всегда.
        if self.log_callback and (self.verbose or
                                  not any(m in msg for m in
                                          self._DETAIL_MARKERS)):
            self.log_callback(msg)

    def _base_headers(self):
        return {
            'Accept': '*/*',
            'Content-Type': 'application/json',
            'Accept-Language': 'ru,en;q=0.9',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache',
            'Origin': f"http://{self.ip}",
            'Referer': self.base_url,
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0'
        }

    def _extract_sid(self, response):
        for cookie in self.cookie_jar:
            if cookie.name == 'SID':
                return cookie.value
        set_cookie = response.headers.get('Set-Cookie') or response.headers.get('set-cookie')
        if set_cookie:
            match = re.search(r'SID=(\d+)', set_cookie)
            if match:
                return match.group(1)
        return None

    def get_token(self):
        """Шаг 1: получение актуального токена и SID"""
        self._log("--- ШАГ 1: Запрос get_token ---")
        payload = {
            "req": "get_token",
            "token": 0,
            "params": {},
            "login_name": ""
        }
        payload_str = json.dumps(payload, separators=(',', ':'))
        self._log(f"URL: {self.api_url}")
        self._log(f"Payload: {payload_str}")

        req = urllib.request.Request(self.api_url, data=payload_str.encode('utf-8'),
                                     headers=self._base_headers(), method='POST')
        try:
            response = self.opener.open(req, timeout=10)
            raw = response.read().decode('utf-8', errors='ignore')
            self._log(f"Статус: {response.status}")
            self._log(f"Заголовки ответа: {dict(response.headers)}")
            self._log(f"Тело ответа: {raw}")

            data = json.loads(raw)
            if data.get("result") != 0:
                raise Exception(f"get_token вернул ошибку. Результат: {data.get('result')}")

            token_data = data.get("data")
            if isinstance(token_data, dict):
                self.token = token_data.get("token")
            else:
                self.token = token_data

            if self.token is None:
                raise Exception(f"Токен не найден в ответе get_token. Ответ: {raw}")

            self.sid = self._extract_sid(response)
            if not self.sid:
                raise Exception(f"SID не найден в ответе get_token. Cookie jar: {list(self.cookie_jar)}")

            self._log(f"✓ Получен токен: {self.token}, SID: {self.sid}")
            return self.token, self.sid

        except Exception as e:
            self._log(f"✗ Ошибка get_token: {e}")
            raise

    def request(self, req_name, params=None, login_name="", _retry_count=0, _retry106_count=0):
        """Шаг 2: выполнение запроса с актуальным токеном и SID"""
        # ИСПРАВЛЕНИЕ: ограничение рекурсии до 3 попыток во избежание переполнения стека
        if _retry_count >= 3:
            raise Exception(f"Превышено максимальное количество попыток обновления токена (3). Проверьте лог {self.log_file}")
        # Повтор при ошибке бэкенда result=106: ожидание 10 с, не более 3 попыток
        if _retry106_count >= 3:
            raise Exception(f"Бэкенд возвращает result=106 после 3 повторов (ожидание 10 с). "
                            f"Проверьте состояние устройства, лог {self.log_file}")

        if self.token is None or self.sid is None:
            self.get_token()

        payload = {
            "req": req_name,
            "token": self.token,
            "params": params or {},
            "login_name": login_name
        }
        payload_str = json.dumps(payload, separators=(',', ':'))

        headers = self._base_headers()
        # Cookie добавляется автоматически через cookie_jar в opener

        self._log(f"--- ШАГ 2: Запрос {req_name} (Попытка {_retry_count + 1}) ---")
        self._log(f"URL: {self.api_url}")
        self._log(f"Актуальный SID: {self.sid}")
        self._log(f"Актуальный токен: {self.token}")
        self._log(f"Payload: {payload_str}")

        req = urllib.request.Request(self.api_url, data=payload_str.encode('utf-8'),
                                     headers=headers, method='POST')
        try:
            response = self.opener.open(req, timeout=15)
            raw = response.read().decode('utf-8', errors='ignore')
            self._log(f"Статус: {response.status}")
            self._log(f"Тело ответа (первые 500 символов): {raw[:500]}")

            data = json.loads(raw)

            # Если сессия устарела или невалидна — сбрасываем и пробуем снова (но не более 3 раз)
            if data.get("result") == 2:
                self._log("⚠ Ошибка авторизации (result=2). Сбрасываем токен и пробуем снова...")
                self.token = None
                self.sid = None
                return self.request(req_name, params, login_name, _retry_count + 1)

            # Ошибка бэкенда result=106 — ждём 10 секунд и повторяем запрос (до 3 попыток)
            if data.get("result") == 106:
                self._log(f"⚠ Бэкенд вернул result=106. Ожидание 10 с, повтор "
                          f"{_retry106_count + 1}/3...")
                time.sleep(10)
                return self.request(req_name, params, login_name,
                                    _retry_count, _retry106_count + 1)

            return data

        except Exception as e:
            self._log(f"✗ Ошибка запроса {req_name}: {e}")
            raise


def normalize_img_type(value):
    """Приводит тип образа из plan.xml к внутреннему значению ('apply'/'boot').

    В файле сценария и в UI тип apply отображается/записывается как 'appl'
    (требование бэкенда),
    при чтении обратно значение восстанавливается.
    """
    v = (value or '').strip().lower()
    if v == 'appl':
        return 'apply'
    return v


def parse_plan_xml(xml_path):
    """Разбор plan.xml: список модулей сценария прошивки по элементам <Image>.

    Корневой тег сценария — всегда <Root> (по требованию бэкенда).
    Обратная совместимость с старым тегом <Plan> не поддерживается.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    if root.tag != 'Root':
        raise ValueError(
            f"Неверный корневой тег plan.xml: '{root.tag}' (ожидался 'Root')"
        )
    modules = []
    for img in root.iter('Image'):
        raw_slot = (img.get('module_slot') or '').strip()
        try:
            slot = str(int(raw_slot))
        except ValueError:
            # Не числовой/пустой module_slot — запись не относится ни к одному
            # слоту; пропускаем вместо падения редактора СП (v1.67).
            continue
        modules.append({
            'slot': slot,
            'type': img.get('module_type'),
            'path': img.get('path'),
            'img_type': normalize_img_type(img.get('type'))
        })
    return modules


def parse_result_txt(txt_content):
    """Разбор result.txt: {slot: статус} ('Complete' либо текст ошибки)."""
    results = {}
    pattern = re.compile(r'slot=(\d+)\s+"([^"]+)":\s+(.*)')
    for line in txt_content.splitlines():
        match = pattern.search(line)
        if match:
            slot = match.group(1)
            status = match.group(3).strip()
            results[slot] = status
    return results


# Строки-маркеры ошибок в operation.log (регистронезависимая проверка)
OP_LOG_ERROR_MARKERS = ("===ERROR===", "state[Error]", "Error]")


def analyze_operation_log(log_path):
    """Анализ operation.log после прошивки.

    Различает три состояния для каждого слота из файла сценария (plan.xml):
      'ok'               — есть запись 'slot=N ...: Complete';
      'error'            — в логе найдена ошибка по слоту
                           ('===ERROR===' или 'Update module slot=N "<тип>": <текст>');
      'no_information'   — ни успешной записи, ни ошибки (информации нет).

    Возвращает {slot(str): {'status': ..., 'detail': текст_ошибки}}.
    """
    analysis = {}
    try:
        with open(log_path, encoding='utf-8', errors='replace') as f:
            content = f.read()
    except OSError:
        return analysis
    lines = content.splitlines()

    # 1) Успешные завершения и явные строки результатов по слотам
    res_pat = re.compile(r'slot=(\d+)\s+"([^"]*)":\s*(.*)')
    for line in lines:
        m = res_pat.search(line)
        if not m:
            continue
        slot = m.group(1)
        text = m.group(3).strip()
        if "Complete" in text:
            analysis[slot] = {"status": "ok", "detail": ""}
        elif text:
            # непустой текст результата — считаем ошибкой
            analysis[slot] = {"status": "error", "detail": text}

    # 2) Ошибочные фреймы/состояния: привязываем к ближайшему slot=N выше по логу
    has_err_block = any(mark.lower() in line.lower() for line in lines
                        for mark in OP_LOG_ERROR_MARKERS)
    slot_pat = re.compile(r'slot=(\d+)')
    cur_slot = None
    err_pat = re.compile(r'===ERROR===|state\[Error\]', re.IGNORECASE)
    for line in lines:
        sm = slot_pat.search(line)
        if sm:
            cur_slot = sm.group(1)
        if err_pat.search(line) and cur_slot is not None:
            if analysis.get(cur_slot, {}).get("status") != "ok":
                analysis.setdefault(cur_slot, {"status": "error", "detail": ""})
    # 3) Финальные строки вида 'Update module slot=4 "DIR12": ' (даже пустые — это ошибка)
    upd_pat = re.compile(r'Update module slot=(\d+)\s+"([^"]*)":\s*(.*)')
    for line in lines:
        m = upd_pat.search(line)
        if not m:
            continue
        slot = m.group(1)
        text = m.group(3).strip()
        if has_err_block or text:
            prev = analysis.get(slot)
            if not prev or prev["status"] != "ok":
                analysis[slot] = {"status": "error", "detail": text or "ошибка (см. operation.log)"}
    return analysis


def find_latest_operation_log(agent_dir):
    """Последний выгруженный operation_log_*.log в директории агента."""
    if not agent_dir or not os.path.isdir(agent_dir):
        return None
    logs = sorted(glob.glob(os.path.join(agent_dir, "operation_log_*.log")))
    return logs[-1] if logs else None


# Директории (подпапки firmware_dir), в которых лежат файлы прошивок:
#   full/  — полный образ, можно прошить как appl, так и boot;
#   appl/  — только тип appl; boot/ — только тип boot.
# Внутреннее значение типа 'appl' исторически именуется 'apply'; наружу
# (в UI и plan.xml) всегда отображается/записывается 'appl'.
FW_SUBDIRS = ("full", "apply", "appl", "boot")

# Отображаемое имя внутреннего типа прошивки 'apply'
IMG_TYPE_DISPLAY = {"apply": "appl"}


def display_img_type(value):
    """Внутренний тип ('apply'/'boot') -> отображаемый ('appl'/'boot')."""
    return IMG_TYPE_DISPLAY.get(value, value)


def detect_fw_source(rel_path):
    """Определяет директорию-источник прошивки по относительному пути.

    Возвращает нормализованное имя подпапки firmware_dir ('full'/'apply'/
    'boot') либо None, если путь не содержит известную директорию.
    Подпапка 'appl' нормализуется к внутреннему значению 'apply'.
    """
    if not rel_path:
        return None
    parts = [p.lower() for p in re.split(r"[\\/]+", rel_path.strip()) if p]
    for seg in parts:
        if seg in FW_SUBDIRS:
            return "apply" if seg == "appl" else seg
    return None


def allowed_img_types(source):
    """Допустимые внутренние типы прошивки для директории-источника."""
    if source == "apply":
        return ["apply"]
    if source == "boot":
        return ["boot"]
    return ["apply", "boot"]  # full либо источник неизвестен — выбор сохраняется


def agent_work_dir(agent_path_value):
    """Каталог для локальных артефактов (логи, выгрузки) из пути к агенту.

    С v1.62 поле 'agent_dir' хранит полный путь к ФАЙЛУ агента; рабочие
    файлы складываются в каталог рядом с ним. Для обратной совместимости
    значение, являющееся существующей директорией, используется как есть.
    """
    if not agent_path_value:
        return ""
    if os.path.isdir(agent_path_value):
        return agent_path_value
    return os.path.dirname(agent_path_value) or "."


def agent_executable(agent_path_value):
    """Путь к исполняемому файлу агента из значения поля 'agent_dir'.

    Обратная совместимость: если пользователь указал директорию —
    возвращается <dir>/IskraIO_Util; если файл — этот файл.
    """
    if not agent_path_value:
        return ""
    if os.path.isdir(agent_path_value):
        return os.path.join(agent_path_value, "IskraIO_Util")
    return agent_path_value


def fw_name_format(filename, parsed=None):
    """Полный контроль формата имени файла прошивки.

    Правила (требования заказчика, v1.71):
      - допустимые префиксы: 'appl', 'boot', 'full' (регистронезависимо);
      - 'full' — формат пока не поддерживается;
      - имя без известного префикса — некорректное имя;
      - НЕКОРРЕКТНЫМ считается также имя, в котором парсер не может
        обнаружить тип модуля, версию или тип прошивки (например
        'appl_atb3500_ai8_r.bin' — нет версии и даты).

    parsed — результат parse_firmware_filename (или заполненный вручную
    словарь скана); если не передан, имя разбирается самостоятельно.

    Возвращает кортеж (fmt, ok, supported, warning):
      fmt       — распознанный префикс ('appl'/'boot'/'full'/None);
      ok        — префикс корректен (один из appl/boot/full);
      supported — прошивка/загрузка файлом разрешена при включённой опции
                  «Контроль формата прошивок» (полный контроль пройден и
                  не 'full');
      warning   — текст предупреждения или None.
    """
    base = os.path.basename((filename or '').replace('\\', '/')).lower()
    fmt = None
    for prefix in ("appl", "boot", "full"):
        if base.startswith(prefix):
            fmt = prefix
            break
    if fmt is None:
        return (None, False, False,
                f"Файл '{filename}' имеет некорректное имя: ожидается начало "
                "'appl', 'boot' или 'full'")
    if fmt == "full":
        return ("full", True, False,
                f"Файл '{filename}' имеет формат full — "
                "такой формат пока не поддерживается")

    # Полный контроль состава имени (v1.71, доработка v1.76).
    if parsed is None:
        parsed = parse_firmware_filename(os.path.basename(filename or ''))
    # v1.76: короткие имена без версии/даты ('appl_atb3500_dir12_r.bin')
    # считаются корректными — тип модуля и тип прошивки определяются из
    # имени; версия/дата в таких именах отсутствуют по формату.
    if parsed is None:
        short = _try_parse_short_fw_name(os.path.basename(filename or ''))
        if short is not None and short.get('module_type'):
            return (fmt, True, True, None)
    # Результат строгого контроля из скана firmware_dir (fmt_ok) имеет приоритет:
    # скан уже разобрал имя и заполнил поля минимально.
    if isinstance(parsed, dict) and 'fmt_ok' in parsed:
        if parsed['fmt_ok']:
            return (fmt, True, True, None)
        return (fmt, True, False,
                f"Файл '{filename}' имеет некорректное имя "
                "(парсер не обнаружил версию/тип модуля/тип прошивки)")
    mt = str((parsed or {}).get('module_type') or '').strip().upper()
    ver = normalize_fw_version((parsed or {}).get('version'))
    date_ = str((parsed or {}).get('date') or '').strip()
    ftpc = (parsed or {}).get('fw_type')
    problems = []
    if not mt or mt == "N/A":
        problems.append("тип модуля не определён")
    if ver == "N/A":
        problems.append("версия не обнаружена")
    if not date_ or date_ == "N/A":
        problems.append("дата не обнаружена")
    if ftpc not in ("apply", "boot"):
        problems.append("тип прошивки не определён")
    if problems:
        return (fmt, True, False,
                f"Файл '{filename}' имеет некорректное имя: "
                + ", ".join(problems) +
                " (ожидаются сегменты R<маж>.<мин> или R<маж>_<мин> "
                "и дата ДДММГГ)")
    return (fmt, True, True, None)


# Строгий шаблон полного имени прошивки (v1.72). Сегменты:
#   <appl|boot|full>_<маркер>_<тип>[_...]_R<маж>[._]<мин>_<ДДММГГ>[_...]
# Версия допускает три записи: R3_4 (старый формат), R3.4 (новая,
# точка внутри сегмента) и R34 (мажор+минор слитно, минор 1-2 цифры).
_FW_STRICT_RE = re.compile(
    r"^(?P<prefix>appl|boot|full)"
    r"_(?P<marker>[a-z0-9]+)"
    r"_(?P<mtype>[a-z0-9]+)"
    r"(?:_[a-z0-9]+)*?"
    r"(?:_R(?P<major>\d{1,3})[._](?P<minor>\d{1,2})"
    r"|_r(?P<rminor>\d{1,2}))"
    r"_(?P<date>\d{6})(?:_.*)?$",
    re.IGNORECASE,
)

# v1.76: «короткие» имена прошивок без версии/даты — например
# 'appl_atb3500_dir12_r.bin' (такие файлы реально используются в СП,
# которые генерирует MakePlan на контроллере). Сегменты:
#   <appl|boot|full>_<маркер>_<тип>[_...][_r]
_FW_SHORT_RE = re.compile(
    r"^(?P<prefix>appl|boot|full)"
    r"_(?P<marker>[a-z0-9]+)"
    r"_(?P<mtype>[a-z0-9]+)"
    r"(?:_[a-z0-9]+)*?"
    r"(?:_r)?$",
    re.IGNORECASE,
)


def _try_parse_fw_name(name_no_ext):
    """Разбор строгого шаблона полного имени прошивки.

    Возвращает dict с ключами prefix/marker/mtype/major/minor/date или
    None, если имя не соответствует шаблону.
    """
    m = _FW_STRICT_RE.match(name_no_ext)
    if not m:
        return None
    date_ = m.group("date")
    day, month = int(date_[0:2]), int(date_[2:4])
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None
    major = m.group("major")
    minor = m.group("minor")
    if major is None:
        # v1.76: сокращённая запись версии '_r<мин>' без мажора —
        # мажор по умолчанию 2 (исторические сборки МФК вида R2_x).
        major = "2"
        minor = m.group("rminor")
    return {"prefix": m.group("prefix").lower(),
            "marker": m.group("marker"),
            "mtype": m.group("mtype"),
            "major": major, "minor": minor,
            "date": date_}


def _try_parse_short_fw_name(filename):
    """v1.76: разбор короткого имени прошивки без версии/даты.

    Примеры: 'appl_atb3500_dir12_r.bin', 'boot_atb3500_psu_r.bin'.
    Тип модуля берётся из третьего сегмента ('psu' → POWER_UNIT);
    поля version/date остаются пустыми (их нет в имени). Возвращает
    dict совместимый с parse_firmware_filename или None.
    """
    name_no_ext = os.path.splitext(filename)[0]
    m = _FW_SHORT_RE.match(name_no_ext)
    if not m:
        return None
    marker = m.group("marker").upper()
    if marker.startswith('ATB'):
        marker = 'ATB ' + marker[3:]
    module_type = m.group("mtype").upper()
    if module_type == 'PSU':
        module_type = 'POWER_UNIT'
    prefix = m.group("prefix").lower()
    fw_type = 'apply' if prefix == 'appl' else prefix
    return {"filename": filename,
            "fw_type": fw_type,
            "marker": marker,
            "module_type": module_type,
            "version": "",
            "date": ""}


def parse_firmware_filename(filename):
    """Парсинг имени файла прошивки согласно правилам из Excel.

    Поддерживаемые форматы версии (v1.72): R3_4, R3.4 и R34 — версия
    нормализуется к виду 'R 3.4'; дата — 6 цифр ДДММГГ (191026 →
    10/19/26). Разрешены имена как со старыми 7 сегментами
    ('full_<маркер>_<тип>_..._R<маж>_<мин>_<дата>'), так и с версией в
    одном сегменте ('appl_atb3500_ai8_R3.4_191026.bin').
    """
    name_no_ext = os.path.splitext(filename)[0]
    parts = name_no_ext.split('_')

    if len(parts) < 5:
        return None
    if parts[0] not in ('full', 'appl', 'boot'):
        return None

    # v1.72: сначала пробуем строгий шаблон (покрывает R3.4/R34 внутри
    # одного сегмента); при неудаче — старый позиционный разбор.
    strict = _try_parse_fw_name(name_no_ext)

    if strict:
        name_prefix = strict["prefix"]
        marker_raw = strict["marker"]
        type_raw = strict["mtype"]
        ver_major_raw = "R" + strict["major"]
        ver_minor = strict["minor"]
        date_raw = strict["date"]
    else:
        if len(parts) < 7:
            return None
        name_prefix = parts[0]
        marker_raw = parts[1]
        type_raw = parts[2]
        ver_major_raw = parts[4]
        ver_minor = parts[5]
        date_raw = parts[6]
        # v1.76: поддержка сокращённой записи версии '_r<мин>' без мажора
        # (например 'appl_atb3500_dir12_r_191026.bin'): в позиционном
        # разборе это parts[4]='r', parts[5]=минор; мажор по умолчанию 2.
        if not ver_major_raw.upper().startswith('R'):
            if (ver_major_raw.lower() == 'r' and ver_minor.isdigit()
                    and len(ver_minor) <= 2):
                ver_major_raw = 'R2'
                ver_minor = parts[5]
            else:
                return None

    marker = marker_raw.upper()
    if marker.startswith('ATB'):
        marker = 'ATB ' + marker[3:]

    module_type = type_raw.upper()
    if module_type == 'PSU':
        module_type = 'POWER_UNIT'

    major = ver_major_raw[1:]
    version = f"R {major}.{ver_minor}"

    date_str = "N/A"
    if len(date_raw) == 6 and date_raw.isdigit():
        try:
            day = int(date_raw[0:2])
            month = int(date_raw[2:4])
            year = date_raw[4:6]
            if 1 <= day <= 31 and 1 <= month <= 12:
                date_str = f"{month}/{day}/{year}"
        except ValueError:
            pass

    return {
        "module_type": module_type,
        "version": version,
        "date": date_str,
        "fw_type": "apply" if name_prefix != "boot" else "boot",
        "name_prefix": name_prefix,
        "marker": marker,
        "manufacturer": marker,
        "filename": filename
    }


def normalize_fw_version(ver):
    """Нормализация версии прошивки для сравнения. 'R2.7' → 'R 2.7'"""
    if not ver or ver in ('N/A', ''):
        return 'N/A'
    ver = ver.strip()
    m = re.match(r'^R\s*(.+)$', ver, re.IGNORECASE)
    if m:
        return f"R {m.group(1)}"
    return ver



def _resolve_module_type(info):
    """Определяет тип модуля по записи module_info_arr.

    Если module_type пустой или 'NA' (модуль не распознан по ID),
    используется module_type_config из конфигурации креста.
    """
    module_type = (info.get("module_type") or "").strip() or "NA"
    if module_type.upper() in ("NA", ""):
        cfg = (info.get("module_type_config") or "").strip()
        if cfg and cfg.upper() != "NA":
            module_type = cfg
    return module_type


# ============================================================
# ПОТОК ВЫПОЛНЕНИЯ ОПЕРАЦИЙ
# ============================================================
class OperationWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str, dict)

    # Сообщения операционного лога, подавляемые в кратком режиме
    # (детализация дублируется сводными строками; включается опцией
    # «Подробный операционный лог», по умолчанию выключена).
    _VERBOSE_ONLY_MARKERS = (
        "Соответствие слот/тип:",
        "Проверка: тип ",
        "Внимание: отвечающих модулей",
        "Слот ",  # + ': тип модуля не определён' / ': резерв' — ниже точнее
        "Запись index=",
        "Хвостовых артефактных записей",
        "Сопоставление слот/тип:",
        "Строк сценария в plan.xml:",
        "Разбор plan.xml (",
        "Некорректные имена (без префикса",
        "Файлы формата full:",
    )

    def __init__(self, op_id, config, quiet=False, on_log=None):
        super().__init__()
        self.op_id = op_id
        self.config = config
        # v1.75: необязательный колбэк записи в операционный лог — позволяет
        # писать события из GUI-компонентов (например, «Сохранение СП на
        # устройство» из редактора), у которых нет собственного log_signal.
        self._on_log = on_log
        # v1.70: два режима операционного лога — краткий (по умолчанию) и
        # подробный (с детализацией). Флаг читается из конфига.
        self.verbose_log = bool(config.get('verbose_log', False))
        # v1.73: «тихий» режим для Автопрошивки — подавляет диалоговые окна
        # (автозаполнение, предупреждения формата) в EditSPDialog.
        self.quiet = quiet
        # v1.77: маркер «finished уже эмитирован» внутри операции. Операции,
        # завершающиеся собственным finished_signal.emit (с данными для
        # диалога), ставят его перед emit; run() по нему пропускает свой
        # итоговый emit — иначе сигнал processed дважды и строки/диалоги
        # дублировались (например «Просмотр результата завершена» x2).
        self._finished_emitted = False

    def _is_verbose_only(self, msg):
        """Относит ли сообщение к детализации, скрытой в кратком режиме."""
        if any(msg.startswith(m) or m in msg for m in self._VERBOSE_ONLY_MARKERS
               if m != "Слот "):
            return True
        # Пер-слотовые отладочные строки парсера (их много при 21+ слотах)
        if msg.startswith("Слот ") and (": тип модуля не определён" in msg
                                        or ": резерв" in msg):
            return True
        return False

    def log(self, msg):
        # Краткий режим: пропускаем только детализирующие сообщения;
        # ошибки, предупреждения ВНИМАНИЕ и итоги всегда видны.
        if not self.verbose_log and self._is_verbose_only(msg):
            return
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_signal.emit(f"[{timestamp}] {msg}")

    @staticmethod
    def log_via(callback, msg):
        """v1.75: запись события в операционный лог через колбэк (для
        GUI-компонентов без собственного сигнала — редактор СП)."""
        if callback is None:
            return
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            callback(f"[{timestamp}] {msg}")
        except Exception:
            pass

    def run(self):
        ssh = None
        try:
            if self.op_id == 10:
                self._op10_get_module_info()
                return
            if self.op_id in (9, 11):
                # v1.66: «Редактировать СП» не держит SSH-соединение во время
                # открытия диалога — раньше это приводило к падению после
                # надписи "Загрузка plan.xml с устройства...".
                self._op11_prepare_edit_plan()
                return
            if self.op_id == 13 and not self.config.get('_auto_update'):
                # v1.73: шаг тихого сохранения СП (без SSH-потока)
                self._op13_quiet_save()
                # v1.77: _op13_quiet_save сам эмитит finished ('_auto_saved')
                # — возврат обязателен, иначе run() доходит до конца и
                # эмитит ВТОРОЙ finished («Операция завершена успешно»),
                # из-за чего цепочка Автопрошивки переходила к следующему
                # шагу дважды (дублирование операций и строк в логе).
                return
            ssh = SSHClient(self.config['ip'], self.config['password'])
            ssh.connect()
            self.log("Подключение к устройству установлено")

            if self.op_id == 1:
                self._op1_upload_agent(ssh)
            elif self.op_id == 2:
                self._op2_make_plan(ssh)
            elif self.op_id == 3:
                self._op3_import_plan(ssh)
            elif self.op_id == 4:
                self._op4_export_plan(ssh)
            elif self.op_id == 6:
                self._op6_update(ssh)
            elif self.op_id == 7:
                self._op7_download_dump(ssh)
            elif self.op_id == 8:
                self._op8_view_result(ssh)
            elif self.op_id == 12:
                # v1.73: удаление директории агента и прошивок с контроллера
                ssh.close()
                ssh = None
                self._cleanup_remote_agent()
            elif self.op_id == 13:
                # v1.73: цепочка Автопрошивки — шаг сохранения СП + Update
                self._op13_auto_flash_tail(ssh)

            if ssh is not None:
                ssh.close()
                ssh = None
            # v1.77: операции, завершившиеся собственным emit finished
            # (_op8_view_result — «Просмотр результата»), не должны эмитить
            # второй раз отсюда: двойной finished давал двойное открытие
            # диалога и дублирующую строку «Операция ... завершена» в логе.
            if getattr(self, "_finished_emitted", False):
                return
            self.finished_signal.emit(True, "Операция завершена успешно", {})
        except Exception as e:
            self.log(f"Критическая ошибка: {e!s}")
            self.finished_signal.emit(False, f"Ошибка: {e!s}", {})
        finally:
            if ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass

    def _check_service_status(self, ssh, service_name):
        out, _ = ssh.exec_command(f"systemctl is-active {service_name}")
        return out.strip()

    def _upload_rows_firmwares(self, ssh, rows):
        """v1.76: проверка наличия и дозагрузка файлов прошивок на устройство
        по строкам сценария (rows — из редактора/тихого режима).

        Логика та же, что у _upload_selected_firmwares (для plan.xml), но
        источник данных — сами строки СП, а не файл на диске. Используется
        в цепочке Автопрошивки, где локального plan_xml может не быть или он
        устарел."""
        if not rows:
            self.log("Сценарий прошивки пуст — проверка файлов пропускается")
            return []
        fw_by_rel = {}
        for fw in self._scan_firmware_dir():
            fw_by_rel[fw['rel_path']] = fw
        uploaded = 0
        present = 0
        for mod in rows:
            path = (mod.get('path') or '').replace('\\', '/')
            rel = re.sub(r'^images/', '', path)
            remote = f"/home/user/fw_update/images/{rel}"
            if ssh.sftp_stat(remote):
                present += 1
                continue
            fw = fw_by_rel.get(rel)
            if fw is None:
                fname = os.path.basename(path)
                fw = next((f for f in fw_by_rel.values()
                           if f['filename'] == fname), None)
            if fw is None:
                raise Exception(
                    f"Файл прошивки '{path}' из сценария не найден ни на "
                    f"устройстве, ни в директории "
                    f"'{self.config.get('firmware_dir', '')}'")
            _fmt, _ok, _supported, warning = fw_name_format(
                fw['filename'], parsed=fw)
            if not _supported:
                if bool(self.config.get('format_control', True)):
                    raise Exception(
                        f"Файл прошивки '{fw['filename']}' из сценария не "
                        f"прошёл контроль формата ({warning or 'формат недопустим'}). "
                        f"Отключите опцию «Контроль формата прошивок», чтобы "
                        f"разрешить загрузку")
                if warning:
                    self.log(f"Предупреждение: {warning}")
            sub = os.path.dirname(fw['rel_path'])
            ssh.exec_command(f"mkdir -p /home/user/fw_update/images/{sub}"
                             if sub else "true")
            ssh.sftp_put(fw['local_path'], remote)
            uploaded += 1
        self.log(f"Файлы прошивок из СП: на устройстве {present}, "
                 f"дозагружено {uploaded}")
        return [m['slot'] for m in rows]

    def _upload_selected_firmwares(self, ssh):
        """Доказательная загрузка на устройство прошивок, выбранных в СП.

        Для каждой строки plan.xml проверяется наличие файла на устройстве
        (/home/user/fw_update/images/<rel_path>); отсутствующий локальный
        файл (по rel_path из скана firmware_dir) копируется туда. Если файла
        нет ни на устройстве, ни локально — ошибка операции.
        """
        # v1.77: если локального файла plan.xml нет (СП сохранён только на
        # устройстве через редактор), читаем план с контроллера — раньше
        # Update брал старый/несуществующий локальный файл и падал на
        # именах прошивок из предыдущего сценария.
        local_plan = self.config.get('plan_xml', '')
        if local_plan and os.path.isfile(local_plan):
            plan_modules = parse_plan_xml(local_plan)
        else:
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
                    tmp_path = tmp.name
                ssh.sftp_get("/home/user/fw_update/plan.xml", tmp_path)
                plan_modules = parse_plan_xml(tmp_path)
                self.log(f"plan.xml загружен с устройства для проверки "
                         f"файлов (строк сценария: {len(plan_modules)})")
            except Exception:
                plan_modules = []
            finally:
                if tmp_path:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
        if not plan_modules:
            self.log("Сценарий прошивки (plan.xml) пуст или отсутствует — "
                     "проверка файлов пропускается")
            return []
        fw_by_rel = {}
        by_name = {}
        for fw in self._scan_firmware_dir():
            fw_by_rel[fw['rel_path']] = fw
            # v1.77: сопоставление по имени файла (basename) — plan.xml может
            # содержать 'images/<file>' без подпапок скана firmware_dir
            by_name.setdefault(fw['filename'], fw)
        uploaded = 0
        present = 0
        for mod in plan_modules:
            path = (mod.get('path') or '').replace('\\', '/')
            rel = re.sub(r'^images/', '', path)
            remote = f"/home/user/fw_update/images/{rel}"
            if ssh.sftp_stat(remote):
                present += 1
                continue
            fw = fw_by_rel.get(rel)
            if fw is None:
                # совместимость со старыми plan.xml без подпапок
                fname = os.path.basename(path)
                fw = by_name.get(fname) or next(
                    (f for f in fw_by_rel.values()
                     if f['filename'] == fname), None)
            if fw is None:
                raise Exception(
                    f"Файл прошивки '{path}' из сценария не найден ни на "
                    f"устройстве, ни в директории "
                    f"'{self.config.get('firmware_dir', '')}'")
            # Контроль формата прошивок (по умолчанию включён): файлы, не
            # прошедшие проверку, на устройство не дозагружаются; при
            # отключённом контроле — только предупреждение, дозагрузка
            # выполняется (включая формат full).
            _fmt, _ok, _supported, warning = fw_name_format(
                fw['filename'], parsed=fw)
            if not _supported:
                if bool(self.config.get('format_control', True)):
                    raise Exception(
                        f"Файл прошивки '{fw['filename']}' из сценария не "
                        f"прошёл контроль формата ({warning or 'формат недопустим'}). "
                        f"Отключите опцию «Контроль формата прошивок», чтобы "
                        f"разрешить загрузку")
                if warning:
                    self.log(f"Предупреждение: {warning}")
            sub = os.path.dirname(fw['rel_path'])
            ssh.exec_command(f"mkdir -p /home/user/fw_update/images/{sub}"
                             if sub else "true")
            ssh.sftp_put(fw['local_path'], remote)
            uploaded += 1
        self.log(f"Файлы прошивок из СП: на устройстве {present}, "
                 f"дозагружено {uploaded}")
        # Возвращаем слоты из сценария — нужны для анализа operation.log
        return [m['slot'] for m in plan_modules]

    def _remote_get_text(self, ssh, remote_path):
        """Чтение текстового файла с устройства (exec cat).

        v1.71: отсутствующий файл больше не критическая ошибка — пустой
        ответ трактуется как «файл ещё не создан» (решает оператор).
        """
        stdin, stdout, stderr = ssh.client.exec_command(f"cat {remote_path}")
        content = stdout.read().decode('utf-8', errors='ignore')
        if not content.strip():
            self.log(f"Файл {remote_path} на устройстве отсутствует "
                     "или пуст — возможно, операция ещё не выполнялась")
        return content

    def _ensure_remote_file(self, ssh, remote_path, what):
        """Проверка существования файла на устройстве (v1.71).

        Вместо падения с 'No such file' — понятное сообщение о том, что
        файл ещё не создан, и корректное завершение операции.
        """
        if ssh.sftp_stat(remote_path):
            return True
        self.log(f"{what} ({remote_path}) ещё не создан на устройстве — "
                 "сначала выполните соответствующую операцию "
                 "(Внедрить агента и прошивки / Создать СП / Прошивка)")
        return False

    def _stop_services(self, ssh):
        self.log("Остановка PrjA.service...")
        ssh.exec_command("systemctl stop PrjA.service")
        status = self._check_service_status(ssh, "PrjA.service")
        self.log(f"PrjA.service статус после остановки: {status}")
        QThread.msleep(1000)

        self.log("Остановка PrjA-tele.service...")
        ssh.exec_command("systemctl stop PrjA-tele.service")
        status = self._check_service_status(ssh, "PrjA-tele.service")
        self.log(f"PrjA-tele.service статус после остановки: {status}")
        QThread.msleep(1000)

    def _start_services(self, ssh):
        self.log("Запуск PrjA-tele.service...")
        ssh.exec_command("systemctl start PrjA-tele.service")
        status = self._check_service_status(ssh, "PrjA-tele.service")
        self.log(f"PrjA-tele.service статус после запуска: {status}")
        QThread.msleep(1000)

        self.log("Запуск PrjA.service...")
        ssh.exec_command("systemctl start PrjA.service")
        status = self._check_service_status(ssh, "PrjA.service")
        self.log(f"PrjA.service статус после запуска: {status}")


    @staticmethod
    def _canon_type(t):
        """Канонический вид типа модуля для сравнений ('' -> '')."""
        t = (t or "").strip().upper()
        if t == "PSU":
            t = "POWER_UNIT"
        return t

    @staticmethod
    def _sn_of(mod):
        """Серийный номер модуля из module_arr (поддержка синонимов).

        Бэкенд в разных прошивках отдаёт поле как 'serial_num' либо
        'serial_number'; пустое/нулевое значение не считается SN.
        """
        for key in ("serial_num", "serial_number"):
            val = str((mod or {}).get(key) or "").strip()
            if val and val.upper() not in ("NA", "N/A", "NONE", "0"):
                return val
        return ""

    def _fetch_module_info(self):
        """Запрос IskraIOGetAll и построение списка установленных модулей.

        Семантика поля 'index' в module_info_arr (подтверждена на реальном
        устройстве, см. CHANGELOG v1.58): это НОМЕР ФИЗИЧЕСКОГО СЛОТА
        (1-базируемый), т.е. slot = index БЕЗ смещений:
            {"index": 1, "module_type": "CPU", slot_count: 2} — CPU в слоте 1
            занимает слоты 1 и 2 (следующая запись index=2 — NA-заглушка
            резерва); index=3 — пустой слот; index=4 — DIR12 и т.д.
        Широкие модули (slot_count > 1) описываются ОДНОЙ записью; соседние
        слоты резерва помечаются тем же типом, но прошивка на них запрещена
        (flashable=False), даже если формально есть серийный номер.
        В конце массива бэкенд печатает «хвост» — повторную последовательность
        индексов (32 записи при crate_slot_count=21, хвост index 0..10);
        хвост отрезается по нарушению монотонности индексов.
        Данные отвечающих модулей (serial_num, версии) берутся из module_arr
        по полю 'slot_num' (1-базируемый). Модули без серийного номера
        недоступны для прошивки (см. EditSPDialog).
        """
        self.log("Получение информации о модулях через HTTP...")
        client = BackendClient(
            self.config['ip'],
            log_callback=self.log,
            verbose=self.verbose_log
        )
        data = client.request("IskraIOGetAll")
        if data.get("result") != 0:
            raise Exception(f"Бэкенд вернул ошибку: result={data.get('result')}")

        resp_data = data.get("data") or {}
        module_arr = resp_data.get("module_arr") or []
        module_info_arr = resp_data.get("module_info_arr") or []
        try:
            crate_slot_count = int(resp_data.get("crate_slot_count"))
        except (TypeError, ValueError):
            crate_slot_count = None

        # --- module_arr: slot_num -> данные модуля ------------------------
        # При дублях записей одного слота приоритет у записи с непустым
        # serial_num (молчащий/повреждённый дубль не должен затирать данные).
        mod_by_slot = {}
        for _mod in module_arr:
            if not isinstance(_mod, dict):
                continue
            try:
                _s = int(_mod.get("slot_num"))
            except (TypeError, ValueError):
                continue
            _prev = mod_by_slot.get(_s)
            if _prev is None or (not self._sn_of(_prev) and self._sn_of(_mod)):
                mod_by_slot[_s] = _mod

        # --- module_info_arr: index -> тип слота --------------------------
        # Формат записи (реальное устройство):
        #   {"index": 1, "module_type": "CPU", "module_type_config": "CPU",
        #    "slot_count": 2}
        # 'index' — НОМЕР ФИЗИЧЕСКОГО СЛОТА (1-базируемый): slot = index.
        # Запись index=0 с пустым/NA типом — артефакт бэкенда («нулевой»
        # элемент до реальных слотов), игнорируется; если осмысленных
        # индексов >=1 нет вовсе, применяется позиционный порядок записей.
        # Широкие модули (slot_count > 1) занимают несколько соседних слотов,
        # но описываются ОДНОЙ записью: CPU(index=1, sc=2) — это слоты 1 и 2
        # (следующая запись index=2 — NA-заглушка резерва). Соседний слот
        # резерва помечается тем же типом, но прошивка на нём запрещена.
        # В конце массива бэкенд печатает «хвост» — повторную последовательность
        # индексов (на реальном устройстве: 32 записи при crate_slot_count=21,
        # хвост index 0..10). Хвост отрезается по нарушению монотонности
        # индексов; если хвостовые записи несут известные типы, они не
        # перетирают голову.
        entries = [info for info in module_info_arr if isinstance(info, dict)]

        def _parse_idx(info):
            raw = info.get("index")
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                return None   # индекс отсутствует/пустой — не задаёт слот
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None

        parsed_idx = [_parse_idx(info) for info in entries]

        def _known_type(info):
            return self._canon_type(_resolve_module_type(info)) not in ("", "NA")

        def _slot_count_of(info):
            try:
                sc = int(info.get("slot_count") or 1)
            except (TypeError, ValueError):
                sc = 1
            return max(sc, 1)

        distinct = {i for i in parsed_idx if i is not None and i >= 1}
        positional = len(distinct) <= 1 and len(entries) > 1

        def _head_len():
            """Длина головной части массива: записи идут в порядке слотов,
            индексы строго возрастают с шагом 1 (на реальном устройстве
            резерв ширины широких модулей заполнен NA-заглушками).
            Первый случай, когда следующий осмысленный индекс (>=1) меньше
            или равен предыдущему — начало «хвоста»-артефакта (повторная
            печать счётчика от 0). Промежуточные нулевые индексы внутри
            головы игнорируются; выход индекса за границы креста тоже
            означает хвост."""
            end, p = 0, None
            for pos, idx in enumerate(parsed_idx):
                if idx is None:
                    continue   # пустой/отсутствующий index не задаёт слот
                if crate_slot_count is not None and idx > crate_slot_count:
                    break      # индекс за границами креста — это хвост
                if idx == 0:
                    if p is not None:
                        break  # нулевой индекс ПОСЛЕ реальных — повтор счётчика
                    end = pos + 1
                    continue   # «нулевая» запись перед головой — артефакт
                if p is not None and idx <= p:
                    break      # нарушение возрастания — начало хвоста
                p = idx
                end = pos + 1
            return end

        head_end = _head_len()

        # --- Маппинг index -> физический слот ------------------------------
        type_by_slot = {}
        reserved_slots = set()   # резерв широких модулей (прошивать нельзя)
        if positional:
            # поле 'index' полностью повреждено — позиция записи = слот
            self.log("Индексы module_info_arr неубедительны — сопоставление "
                     "слот/тип построено по порядку записей в ответе")
            for rank, info in enumerate(entries):
                type_by_slot[rank + 1] = _resolve_module_type(info)
        else:
            tail_skipped = len(entries) - head_end
            if tail_skipped:
                self.log(f"Хвостовых артефактных записей module_info_arr "
                         f"проигнорировано: {tail_skipped} "
                         f"(голова: {head_end} записей)")

            # slot = index (1-базируемый номер слота). На реальном кресте:
            #   index=0 (NA) — артефакт, пропускается;
            #   CPU(idx=1, sc=2) -> слоты 1..2 (слот 2 — резерв);
            #   NA(idx=3) -> слот 3 пуст; DIR12(idx=4) -> слот 4; ...
            #   POWER_UNIT(idx=20) -> слот 20.
            zero_skipped = False
            for pos in range(head_end):
                info = entries[pos]
                idx = parsed_idx[pos]
                if idx is None:
                    continue          # артефактная запись без индекса
                if idx == 0:
                    # «нулевая» запись перед реальными слотами — артефакт
                    # бэкенда (на реальном устройстве index=0 это NA);
                    # осмысленные типы из нулевой записи не отображаются
                    if not _known_type(info):
                        zero_skipped = True
                        continue
                sc = _slot_count_of(info)
                stype = _resolve_module_type(info)
                newt = self._canon_type(stype)
                slot = idx
                if crate_slot_count is not None and slot > crate_slot_count:
                    break             # дальше записи только за границами креста
                known = self._canon_type(type_by_slot.get(slot, ""))
                if not (known not in ("", "NA") and newt in ("", "NA")):
                    type_by_slot[slot] = stype
                if sc > 1:
                    # резерв ширины: следующие sc-1 физических слотов
                    for inner in range(slot + 1, slot + sc):
                        if crate_slot_count is not None \
                                and inner > crate_slot_count:
                            continue
                        reserved_slots.add(inner)
                        # не затираем слот, уже описанный собственной
                        # осмысленной записью (чужой модуль)
                        cur = self._canon_type(type_by_slot.get(inner, ""))
                        if cur in ("", "NA"):
                            type_by_slot[inner] = stype
            if zero_skipped:
                self.log("Запись index=0 (NA) в module_info_arr распознана "
                         "как артефакт бэкенда и пропущена")

            self.log("Сопоставление слот/тип: slot = index (1-базируемый "
                     "номер слота из module_info_arr)")

        self.log(f"Слотов креста: {crate_slot_count if crate_slot_count is not None else 'н/д'}, "
                 f"записей module_info_arr: {len(module_info_arr)}, "
                 f"записей module_arr: {len(module_arr)}")

        # --- Доопределение типов по отвечающим модулям --------------------
        # Если конфигурация креста молчит о слоте (нет записи или тип NA/пусто),
        # а модуль в этом слоте отвечает — берём тип из module_arr
        # (module_type / type / model). Это лечит расхождение количества
        # записей module_info_arr и реальных слотов.
        inferred = 0
        for slot, mod in mod_by_slot.items():
            known = self._canon_type(type_by_slot.get(slot, ""))
            if known not in ("", "NA"):
                continue
            mtype = (self._canon_type(mod.get("module_type"))
                     or self._canon_type(mod.get("type"))
                     or self._canon_type(mod.get("model")))
            if mtype and mtype != "NA":
                type_by_slot[slot] = mtype
                inferred += 1
                self.log(f"Слот {slot}: тип '{mtype}' доопределён по "
                         f"ответу модуля (конфигурация креста — NA)")
        if inferred:
            self.log(f"Типов, доопределённых по module_arr: {inferred}")

        # --- Диагностика сопоставления -------------------------------------
        # 1) Модули с серийным номером на слотах, которые конфигурация креста
        #    не описала (тип NA) — потенциальное смещение. Резервные слоты
        #    широких модулей в проверку не входят (там тип известен).
        mismatch_serial_na = [slot for slot, mod in sorted(mod_by_slot.items())
                              if self._sn_of(mod)
                              and slot not in reserved_slots
                              and self._canon_type(type_by_slot.get(slot, ""))
                              in ("", "NA")]
        if mismatch_serial_na:
            self.log(f"Внимание: {len(mismatch_serial_na)} отвечающих модулей "
                     f"стоят на слотах с типом NA "
                     f"(слоты: {', '.join(map(str, mismatch_serial_na))}) — "
                     "проверьте соответствие слотов")
        # 2) Типы из конфигурации креста, которым не отвечает ни один модуль
        #    (если module_arr вообще заполнен).
        if mod_by_slot:
            silent_types = {}
            for slot, t in type_by_slot.items():
                ct = self._canon_type(t)
                if ct in ("", "NA") or slot in mod_by_slot:
                    continue
                silent_types.setdefault(ct, []).append(slot)
            for ct, slots in sorted(silent_types.items()):
                self.log(f"Проверка: тип '{ct}' в конфигурации креста "
                         f"(слоты {', '.join(map(str, slots))}), но модули "
                         "такого типа не отвечают")

        # --- Итоговые строки ------------------------------------------------
        # Только реальные слоты креста (1..crate_slot_count), плюс слоты с
        # ответами модулей за его пределами (если данные противоречивы).
        max_slot = crate_slot_count
        if max_slot is None:
            max_slot = max([*type_by_slot.keys(), *mod_by_slot.keys()],
                           default=len(entries))
        # не обрезаем известные ответы модулей за границами креста
        if mod_by_slot:
            max_slot = max(max_slot, max(mod_by_slot.keys()))
        result = []
        for slot in range(1, max_slot + 1):
            mod = mod_by_slot.get(slot, {})
            module_type = type_by_slot.get(slot, "NA")
            source = "module_arr" if slot in mod_by_slot else "module_info_arr"
            serial_num = self._sn_of(mod) or "N/A"
            reserved = slot in reserved_slots
            if reserved:
                self.log(f"Слот {slot}: резерв '{module_type}' — прошивка запрещена")
            result.append({
                "slot_num": str(slot),
                "module_type": module_type,
                "reserved": reserved,
                "serial_num": serial_num,
                "manufacture_date": mod.get("manufacture_date") or "N/A",
                "hardware_version": mod.get("hardware_version") or "N/A",
                "firmware_version": mod.get("firmware_version") or "N/A",
                "source": source,
                # Модуль доступен для прошивки только если имеет серийный
                # номер И не является резервом широкого модуля (slot_count>1)
                "flashable": serial_num != "N/A" and not reserved,
            })

        for r in result:
            if self._canon_type(r["module_type"]) in ("", "NA"):
                self.log(f"Слот {r['slot_num']}: тип модуля не определён (NA)")

        return result

    def _scan_firmware_dir(self):
        """Скан директории прошивок с учётом подпапок full/apply/appl/boot.

        Файлы ищутся рекурсивно в firmware_dir (включая подпапки). Формат
        имени проверяется по префиксу ('appl', 'boot', 'full') — см.
        fw_name_format; строгий разбор полного имени (версия/дата) не
        требуется для загрузки и потому не блокирует файл: если разбился
        parse_firmware_filename, поля заполняются из имени минимально.
        Для каждой прошивки заполняется 'source' (директория-источник) и
        'rel_path' (путь относительно firmware_dir, например 'full/xxx.bin').
        """
        fw_dir = self.config.get('firmware_dir', '')
        firmwares = []
        if not fw_dir or not os.path.isdir(fw_dir):
            return firmwares
        for root, _dirs, files in os.walk(fw_dir):
            rel_dir = os.path.relpath(root, fw_dir).replace("\\", "/")
            subdir = "" if rel_dir == "." else rel_dir
            for filename in sorted(files):
                full_path = os.path.join(root, filename)
                fmt, ok, supported, warning = fw_name_format(filename)
                if not ok:
                    # Файлы без префикса appl/boot/full в скан не попадают;
                    # для .bin — предупреждение, остальные файлы (конфиги,
                    # readme и т.п.) пропускаются молча.
                    if filename.lower().endswith(".bin"):
                        self.log(f"Предупреждение: {warning}")
                    continue
                # v1.71: строгий контроль формата — supported=False означает,
                # что парсер не обнаружил версию/тип модуля/тип прошивки
                # (или это full). Такие файлы остаются в скане (их можно
                # выбрать вручную), но при включённом контроле формата они
                # не загружаются на устройство и не прошиваются.
                parsed = parse_firmware_filename(filename)
                if parsed is None:
                    # Имя корректного формата, но не проходит строгий шаблон
                    # (например appl_atb3500_ai8_r.bin) — берём тип из префикса,
                    # остальное определяем по возможности.
                    parts = os.path.splitext(filename)[0].split("_")
                    module_type = parts[2].upper() if len(parts) > 2 else "N/A"
                    if module_type == "PSU":
                        module_type = "POWER_UNIT"
                    # v1.72: версия может быть в одном сегменте
                    # (R3.4 / R34) или в двух (R3_4), дата — ДДММГГ.
                    ver = "N/A"
                    for p_ in parts[3:]:
                        mv = re.match(r"^R(\d+)[._](\d{1,2})$", p_, re.I)
                        if not mv:
                            mv = re.match(r"^R(\d+)(\d{1,2})$", p_, re.I)
                        if mv:
                            ver = f"R {mv.group(1)}.{mv.group(2)}"
                            break
                        if re.match(r"^R\d+$", p_, re.I):
                            idx = parts.index(p_)
                            if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                                ver = f"R {p_[1:]}.{parts[idx + 1]}"
                            break
                    parsed = {
                        "module_type": module_type,
                        "version": ver,
                        "date": "N/A",
                        "fw_type": "boot" if fmt == "boot" else "apply",
                        "name_prefix": fmt,
                        "marker": parts[1].upper() if len(parts) > 1 else "N/A",
                        "manufacturer": parts[1].upper() if len(parts) > 1 else "N/A",
                        "filename": filename,
                    }
                parsed["local_path"] = full_path
                # v1.71: флаг строгого контроля формата — результат ПОЛНОГО
                # контроля имени (fw_name_format), а не только префикса:
                # supported=False, если парсер не обнаружил версию/тип
                # модуля/тип прошивки/дату или это 'full'. При включённом
                # контроле такие файлы не загружаются и не прошиваются.
                _fmt, _ok, _supported, _warn = fw_name_format(filename, parsed=parsed)
                parsed["fmt_ok"] = bool(_supported)
                if not _supported and _warn:
                    self.log(f"Предупреждение: {_warn}")
                parsed["source"] = detect_fw_source(subdir) or \
                    detect_fw_source(filename) or ("full" if fmt == "full" else
                                                   ("boot" if fmt == "boot" else "apply"))
                parsed["rel_path"] = f"{subdir}/{filename}" if subdir else filename
                firmwares.append(parsed)
        return firmwares

    def _op10_get_module_info(self):
        modules_data = self._fetch_module_info()
        self.progress_signal.emit(100)
        # Отладочная сводка: слот -> тип (помогает выявить смещение индексов)
        summary = ", ".join(f"{m['slot_num']}:{m['module_type']}" for m in modules_data)
        self.log(f"Соответствие слот/тип: {summary}")
        self.log(f"Найдено модулей: {len(modules_data)}")
        # v1.77: маркер «finished уже эмитирован» — run() не эмитит второй
        # finished (иначе диалог открывался дважды, дублировались строки лога).
        self._finished_emitted = True
        self.finished_signal.emit(True, "Информация получена",
                                  {"modules": modules_data, "action": "module_info"})

    def _op11_prepare_edit_plan(self):
        modules_info = self._fetch_module_info()
        firmwares = self._scan_firmware_dir()
        plan_modules = []
        if not self.quiet:
            ssh = SSHClient(self.config['ip'], self.config['password'])
            ssh.connect()
            tmp_path = None
            try:
                self.log("Загрузка plan.xml с устройства...")
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
                    tmp_path = tmp.name
                ssh.sftp_get("/home/user/fw_update/plan.xml", tmp_path)
                self.log(f"Разбор plan.xml ({os.path.getsize(tmp_path)} байт)...")
                try:
                    plan_modules = parse_plan_xml(tmp_path)
                except FileNotFoundError:
                    # v1.69: пустой СП (<Root/>) — парсер отдаёт ошибку; редактор
                    # открывается без строк сценария (все пути подхватятся
                    # автозаполнением).
                    self.log("План прошивки пуст — открываю редактор без строк СП")
                    plan_modules = []
                self.log(f"Строк сценария в plan.xml: {len(plan_modules)}")
                self._log_plan_skipped(tmp_path, plan_modules)
            except Exception as e:
                raise Exception(f"Не удалось загрузить plan.xml: {e}") from e
            finally:
                # v1.66: соединение и временный файл закрываются/удаляются ДО
                # открытия диалога редактора — закрытие SSH после exec() диалога
                # приводило к аварийному завершению приложения.
                try:
                    ssh.close()
                except Exception:
                    pass
                if tmp_path:
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
        else:
            # v1.73: тихий режим (Автопрошивка) — план только что создан
            # MakePlan'ом, но для сборки СП достаточно информации о модулях;
            # пути заполнит автозаполнение appl.
            self.log("Тихий режим: plan.xml не выгружается — "
                     "сценарий будет собран автозаполнением")
        self.progress_signal.emit(100)
        if self.op_id == 11 and self.config.get('_auto_after_prepare'):
            # v1.76: цепочка Автопрошивки, шаг 3 — данные подготовлены,
            # строки сценария (_auto_rows) уже собраны GUI (этап A).
            # Тихое сохранение plan.xml выполняется СЕЙЧАС ЖЕ внутри этого
            # же воркера op 11 (метод _op13_quiet_save с SSH-соединением),
            # а не отдельным запуском op 13 из обработчика finished-сигнала.
            # Раньше новый воркер стартовал до завершения текущего потока
            # (run() ещё не вернулся, isRunning()==True) — start_operation
            # отвечал «Уже выполняется другая операция» и цепочка зависала.
            # v1.77: этап A (сборка строк СП тихим автозаполнением appl)
            # выполняется ЗДЕСЬ, в фоновом потоке — раньше он делался в
            # GUI-обработке finished-сигнала и требовал запуска ЕЩЁ одного
            # воркера для сохранения; новый воркер стартовал до возврата
            # run() текущего потока (isRunning()==True), start_operation
            # отвечал «Уже выполняется другая операция» и цепочка зависала
            # на шаге 2/6 → 3. Теперь весь шаг 3 — один воркер op 11.
            built_rows = []
            try:
                dialog = EditSPDialog(
                    modules_info, plan_modules, firmwares, self.config,
                    None, quiet=True)
                dialog.autofill("apply")
                for i, r in enumerate(dialog.rows):
                    row = dict(r)
                    row['path'] = dialog.path_edits[i].text().strip()
                    row['img_type'] = dialog.type_combos[i].currentData()
                    built_rows.append(row)
                del dialog
            except Exception as e:
                raise Exception(
                    f"Ошибка тихого редактирования СП: {e}") from e
            if not any(r.get('path') and r.get('flashable', True)
                       for r in built_rows):
                raise Exception("Автопрошивка: автозаполнение appl не "
                                "выбрало ни одного модуля — прошивать нечего")
            self.config['_auto_built_rows'] = built_rows
            ssh = None
            try:
                ssh = SSHClient(self.config['ip'], self.config['password'])
                ssh.connect()
                self._op13_quiet_save(ssh=ssh)
            finally:
                if ssh is not None:
                    try:
                        ssh.close()
                    except Exception:
                        pass
            self.log(f"Данные для редактора подготовлены. Модулей: "
                     f"{len(modules_info)}, прошивок: {len(firmwares)}")
            # v1.77: маркер «finished уже эмитирован» — см. выше.
            self._finished_emitted = True
            self.finished_signal.emit(True, "СП сохранён (тихий режим)", {
                "modules_info": modules_info,
                "plan_modules": plan_modules,
                "firmwares": firmwares,
                "action": "edit",
                "_auto_saved": True,
                # v1.77: собранные строки СП — цепочке не нужно пересобирать
                # их в GUI и запускать дополнительный воркер сохранения
                "_auto_rows": built_rows,
            })
            return
        self.log(f"Данные для редактора подготовлены. Модулей: {len(modules_info)}, прошивок: {len(firmwares)}")
        # v1.77: маркер «finished уже эмитирован» — см. выше.
        self._finished_emitted = True
        self.finished_signal.emit(True, "Данные получены", {
            "modules_info": modules_info,
            "plan_modules": plan_modules,
            "firmwares": firmwares,
            "action": "edit"
        })

    def _log_plan_skipped(self, xml_path, parsed_modules):
        """Логирует <Image>-записи plan.xml, пропущенные парсером (v1.67).

        Пропуск случается при нечисловом/пустом module_slot — раньше такие
        файлы приводили к падению редактора СП; теперь запись игнорируется,
        поле 'Путь к файлу' у соответствующей строки остаётся пустым (N/A),
        а в журнал выводится предупреждение.
        """
        try:
            root = ET.parse(xml_path).getroot()
            total = len(list(root.iter('Image')))
        except Exception:
            return
        skipped = total - len(parsed_modules)
        if skipped > 0:
            self.log(f"ВНИМАНИЕ: пропущено записей plan.xml с некорректным "
                     f"module_slot: {skipped} (из {total}) — их пути не будут "
                     f"подхвачены редактором")

    def _cleanup_remote_agent(self):
        """v1.73: удаление директории агента и прошивок с контроллера.

        Используется операцией «Удалить агента» (op 12) и Автопрошивкой на
        финальном этапе / при ошибке. Ошибки подключения не считаются
        критичными — операция считается выполненной best-effort.
        """
        ssh = SSHClient(self.config['ip'], self.config['password'])
        ssh.connect()
        try:
            self.log("Удаление каталога /home/user/fw_update/...")
            ssh.exec_command("rm -rf /home/user/fw_update")
            if ssh.sftp_stat("/home/user/fw_update"):
                raise Exception("Каталог /home/user/fw_update не удалён")
            self.progress_signal.emit(100)
            self.log("Директория агента и прошивок удалена с контроллера")
        finally:
            try:
                ssh.close()
            except Exception:
                pass

    def _op1_upload_agent(self, ssh):
        self.log("Очистка и создание каталогов...")
        ssh.exec_command("rm -rf /home/user/fw_update")
        ssh.exec_command("mkdir -p /home/user/fw_update/images")
        self.log("Загрузка агента IskraIO_Util...")
        agent_path = agent_executable(self.config['agent_dir'])
        if not os.path.exists(agent_path):
            raise FileNotFoundError(f"Файл агента не найден: {agent_path}")
        ssh.sftp_put(agent_path, "/home/user/fw_update/IskraIO_Util")
        ssh.sftp_chmod("/home/user/fw_update/IskraIO_Util", 0o755)
        self.log("Копирование файлов прошивок...")
        firmwares = self._scan_firmware_dir()
        total = len(firmwares)
        if total == 0:
            raise Exception(
                f"В директории '{self.config['firmware_dir']}' не найдено "
                "файлов прошивок (ожидаются имена с префиксом appl_/boot_/full_)")
        # Контроль формата прошивок (опция «Контроль формата прошивок»,
        # по умолчанию включена): не прошедшие контроль файлы на устройство
        # не загружаются; при отключённой — только предупреждения, загрузка
        # выполняется (включая формат full).
        # v1.70: создание СП с некорректными именами и/или форматом full
        # возможно только при ОТКЛЮЧЁННОМ контроле формата — при включённом
        # full-файлы на устройство не загружаются и в сценарий не попадут.
        fc_on = bool(self.config.get('format_control', True))
        all_count = len(firmwares)
        self.log(f"Найдено файлов прошивок в директории: {all_count}"
                 + (" (контроль формата включен)" if fc_on else
                    " (контроль формата отключен)"))
        bad_names = []
        full_names = []
        kept = []
        for fw in firmwares:
            fmt, ok, supported, warning = fw_name_format(
                fw['filename'], parsed=fw)
            if fmt == 'full':
                full_names.append(fw['filename'])
            elif not supported:
                bad_names.append(fw['filename'])
            if fc_on and not supported:
                continue
            kept.append(fw)
        skipped = len(firmwares) - len(kept)
        if bad_names or full_names:
            # v1.70: без дублей — предупреждение выводится одной сводной
            # строкой (списки имён — только в подробном режиме лога).
            parts = []
            if bad_names:
                parts.append(f"некорректных имён: {len(bad_names)}")
            if full_names:
                parts.append(f"формат full (не поддерживается): "
                             f"{len(full_names)}")
            detail = "; ".join(parts)
            if fc_on:
                self.log(f"ВНИМАНИЕ: файлов с проблемами формата — {detail}. "
                         f"Контроль формата ВКЛЮЧЕН: они НЕ загружаются на "
                         f"устройство (пропущено: {skipped}), создание СП "
                         f"такими прошивками невозможно.")
            else:
                self.log(f"ВНИМАНИЕ: файлов с проблемами формата — {detail}. "
                         f"Контроль формата ОТКЛЮЧЕН: загрузка на устройство "
                         f"будет выполнена; создание СП с такими файлами "
                         f"допускается (с предупреждением).")
            if self.verbose_log:
                if bad_names:
                    self.log("Некорректные имена (парсер не обнаруживает "
                             "версию/тип модуля/тип прошивки): "
                             + ", ".join(bad_names))
                if full_names:
                    self.log("Файлы формата full: " + ", ".join(full_names))
        # v1.71: при включённой детализации показываем имена ВСЕХ
        # загружаемых прошивок
        if self.verbose_log:
            self.log("Загружаются прошивки: " +
                     ", ".join(fw['filename'] for fw in firmwares))
        firmwares = kept
        total = len(firmwares)
        if total == 0:
            raise Exception(
                "После контроля формата не осталось допустимых файлов "
                "прошивок для загрузки (отключите опцию «Контроль формата "
                "прошивок», если загрузка таких файлов необходима)")
        loaded = 0
        for i, fw in enumerate(firmwares):
            ssh.exec_command("mkdir -p /home/user/fw_update/images/" + os.path.dirname(fw["rel_path"]).replace("\\", "/"))
            ssh.sftp_put(fw["local_path"], f"/home/user/fw_update/images/{fw['rel_path']}")
            loaded += 1
            progress = int((i + 1) / total * 100)
            self.progress_signal.emit(progress)
        skipped_note = f", пропущено контролем формата: {skipped}" if skipped else ""
        self.log(f"Загружено прошивок: {loaded} из {all_count}{skipped_note}")
        self.log("Агент и прошивки успешно загружены")

    def _op2_make_plan(self, ssh):
        try:
            self._stop_services(ssh)
            self.log("Создание сценария прошивки (MakePlan)...")
            self.progress_signal.emit(50)
            out, err = ssh.exec_command("cd /home/user/fw_update && ./IskraIO_Util MakePlan")
            if err:
                self.log(f"MakePlan stderr: {err}")
            # v1.71: stdout MakePlan — только в режиме детализации
            if self.verbose_log:
                self.log(f"MakePlan stdout: {out}")
            self.log("MakePlan завершён")
        except Exception as e:
            self.log(f"Ошибка во время MakePlan: {e}")
            raise
        finally:
            self._start_services(ssh)
            # Требование v1.69: после контроля запуска сервисов подождать
            # 15 секунд и сообщить о завершении операции создания СП.
            self.log("Ожидание 15 сек после запуска сервисов...")
            QThread.msleep(15000)
            self.progress_signal.emit(100)
            self.log("Операция создания СП завершена")

    def _op3_import_plan(self, ssh):
        # v1.71: отсутствующий локальный plan.xml — не критическая ошибка
        local_plan = self.config.get('plan_xml', '')
        if not local_plan or not os.path.isfile(local_plan):
            self.log(f"Файл сценария прошивки ещё не создан "
                     f"(путь: '{local_plan or 'не задан'}') — сначала "
                     "выполните 'Создать СП' или 'Редактировать СП'")
            return
        self.log("Проверка наличия текущего plan.xml...")
        if ssh.sftp_stat("/home/user/fw_update/plan.xml"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"/home/user/fw_update/plan.xml.bak_{timestamp}"
            self.log(f"Создание бэкапа: {backup_name}")
            ssh.exec_command(f"cp /home/user/fw_update/plan.xml {backup_name}")
            ssh.sftp_remove("/home/user/fw_update/plan.xml")
        self.log("Загрузка нового plan.xml...")
        ssh.sftp_put(self.config['plan_xml'], "/home/user/fw_update/plan.xml")
        self.progress_signal.emit(100)
        self.log("Сценарий успешно импортирован")

    def _op4_export_plan(self, ssh):
        # v1.71: отсутствующий plan.xml на устройстве — не критическая ошибка
        if not self._ensure_remote_file(ssh, "/home/user/fw_update/plan.xml",
                                        "Сценарий прошивки (plan.xml)"):
            return
        self.log("Выгрузка plan.xml...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_path = os.path.join(agent_work_dir(self.config['agent_dir']), f"plan_export_{timestamp}.xml")
        ssh.sftp_get("/home/user/fw_update/plan.xml", local_path)
        self.progress_signal.emit(100)
        self.log(f"Сценарий выгружен в: {local_path}")

    def _op6_update(self, ssh, plan_rows=None):
        """Update: проверка/дозагрузка файлов СП и запуск агента.

        v1.76: plan_rows — строки сценария из тихого режима Автопрошивки;
        если переданы, проверка файлов и контроль типов образов выполняются
        по ним, а не по локальному файлу plan_xml (который может отсутствовать
        или содержать имена из предыдущего сценария)."""
        self.log("Проверка наличия агента и файлов прошивок на устройстве...")
        if not ssh.sftp_stat("/home/user/fw_update/IskraIO_Util"):
            raise Exception("Агент IskraIO_Util отсутствует. Сначала выполните 'Внедрить агента и прошивки'.")
        # Доказательная проверка/дозагрузка файлов из СП перед Update
        if plan_rows is not None:
            plan_slots = self._upload_rows_firmwares(ssh, plan_rows)
        else:
            plan_slots = self._upload_selected_firmwares(ssh)
        remote_images = ssh.sftp_listdir("/home/user/fw_update/images")
        if not remote_images:
            raise Exception("Директория /home/user/fw_update/images/ пуста. Сначала выполните 'Внедрить агента и прошивки'.")
        self.log(f"Найдено файлов прошивок на устройстве: {len(remote_images)}")

        # v1.76: контроль типа образов в СП — при включённом контроле
        # формата запрещена прошивка full-файлами (агенты с планом, где
        # type="full", на Update не запускаются).
        if bool(self.config.get('format_control', True)):
            if plan_rows is not None:
                plan_modules = plan_rows
            elif (self.config.get('plan_xml')
                  and os.path.isfile(self.config['plan_xml'])):
                plan_modules = parse_plan_xml(self.config['plan_xml'])
            else:
                # v1.77: локального плана нет — читаем тип образов из
                # plan.xml на устройстве (его и исполнит IskraIO_Util)
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
                        tmp_path = tmp.name
                    ssh.sftp_get("/home/user/fw_update/plan.xml", tmp_path)
                    plan_modules = parse_plan_xml(tmp_path)
                except Exception:
                    plan_modules = []
                finally:
                    if tmp_path:
                        try:
                            os.remove(tmp_path)
                        except OSError:
                            pass
            bad_types = [m for m in plan_modules
                         if normalize_img_type(m.get('img_type')) not in
                         ('apply', 'boot')]
            if bad_types:
                raise Exception(
                    "В сценарии прошивки есть недопустимые типы образов "
                    "(прошивается только appl/boot): " +
                    ", ".join(f"слот {m['slot']} ({m.get('img_type')})"
                              for m in bad_types) +
                    ". Отредактируйте СП или отключите «Контроль формата "
                    "прошивок».")
        try:
            self._stop_services(ssh)
            self.log("Запуск прошивки (Update)...")
            stdin, stdout, stderr = ssh.client.exec_command("cd /home/user/fw_update && ./IskraIO_Util Update")
            for i in range(1, 100):
                if stdout.channel.exit_status_ready():
                    break
                self.progress_signal.emit(i)
                QThread.msleep(100)
            exit_status = stdout.channel.recv_exit_status()
            self.progress_signal.emit(100)
            self.log(f"Update завершён с кодом: {exit_status}")

            self.log("Выгрузка operation.log...")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            local_log = os.path.join(agent_work_dir(self.config['agent_dir']), f"operation_log_{timestamp}.log")
            ssh.sftp_get("/home/user/fw_update/operation.log", local_log)

            self.log("Анализ result.txt...")
            stdin, stdout, stderr = ssh.client.exec_command("cat /home/user/fw_update/result.txt")
            result_content = stdout.read().decode()
            results = parse_result_txt(result_content)
            ok_slots = [s for s, st in results.items() if "Complete" in st]
            err_slots = {s: st for s, st in results.items()
                         if "Complete" not in st}
            # v1.70: пер-слотовые строки — только в подробном режиме;
            # в кратком остаётся сводка ниже (и ошибки operation.log).
            if self.verbose_log:
                for slot, status in sorted(results.items(), key=lambda x: int(x[0])):
                    if "Complete" in status:
                        self.log(f"Слот {slot}: Успешно")
                    else:
                        self.log(f"Слот {slot}: Ошибка - {status}")
            summary = f"Итог result.txt: успешно {len(ok_slots)}"
            if err_slots:
                summary += (", с ошибками " + str(len(err_slots)) + " (слоты: "
                            + ", ".join(sorted(err_slots, key=int)) + ")")
            self.log(summary)
            # Анализ operation.log: различаем 'нет информации' и 'ошибка'
            try:
                op_analysis = analyze_operation_log(local_log)
                for slot in sorted(op_analysis, key=int):
                    st = op_analysis[slot]
                    if st["status"] == "ok":
                        continue
                    if st["status"] == "error":
                        detail = st.get("detail") or "ошибка (см. operation.log)"
                        self.log(f"operation.log, слот {slot}: ОШИБКА - {detail}")
                    else:
                        self.log(f"operation.log, слот {slot}: нет информации")
                analyzed_slots = set(op_analysis)
                for mod_slot in plan_slots:
                    if mod_slot not in analyzed_slots:
                        self.log(f"operation.log, слот {mod_slot}: нет информации")
            except Exception as e:
                self.log(f"Не удалось проанализировать operation.log: {e}")
        except Exception as e:
            self.log(f"Ошибка во время прошивки: {e}")
            raise
        finally:
            self._start_services(ssh)

    def _op7_download_dump(self, ssh):
        # v1.71: отсутствующий дамп — не критическая ошибка
        if not self._ensure_remote_file(ssh, "/home/user/fw_update/io.can.box2.csv",
                                        "Дамп операции (io.can.box2.csv)"):
            return
        self.log("Выгрузка дампа операции...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_dump = os.path.join(agent_work_dir(self.config['agent_dir']), f"io_can_box2_{timestamp}.csv")
        ssh.sftp_get("/home/user/fw_update/io.can.box2.csv", local_dump)
        self.progress_signal.emit(100)
        self.log(f"Дамп выгружен в: {local_dump}")

    def _op8_view_result(self, ssh):
        self.log("Чтение данных для анализа результата...")
        # v1.71: отсутствующие plan.xml / result.txt / operation.log — не
        # критическая ошибка: показываем то, что есть, с пометкой 'нет информации'
        if not self._ensure_remote_file(ssh, "/home/user/fw_update/plan.xml",
                                        "Сценарий прошивки (plan.xml)"):
            modules = []
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
                tmp_plan = tmp.name
            try:
                ssh.sftp_get("/home/user/fw_update/plan.xml", tmp_plan)
                modules = parse_plan_xml(tmp_plan)
            finally:
                self._safe_remove(tmp_plan)
        result_content = self._remote_get_text(ssh, "/home/user/fw_update/result.txt")
        results = parse_result_txt(result_content)
        # Анализ operation.log (локального выгруженного или с устройства):
        # различаем 'нет информации' и 'ошибка'
        log_path = find_latest_operation_log(agent_work_dir(self.config.get('agent_dir', '')))
        if log_path is None:
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".log") as tmp:
                    log_path = tmp.name
                ssh.sftp_get("/home/user/fw_update/operation.log", log_path)
            except Exception as e:
                self.log(f"Не удалось получить operation.log: {e}")
                log_path = None
        op_analysis = analyze_operation_log(log_path) if log_path else {}
        for slot, st in sorted(op_analysis.items(), key=lambda x: int(x[0])):
            if st["status"] == "error":
                self.log(f"operation.log, слот {slot}: ОШИБКА - "
                         f"{st.get('detail') or 'см. operation.log'}")
        # Дополняем результат по слотам из СП: нет записи -> 'нет информации'
        for mod in modules:
            slot = mod['slot']
            st = op_analysis.get(slot)
            if st and st["status"] == "error":
                results[slot] = f"Ошибка: {st.get('detail') or 'см. operation.log'}"
            elif st and st["status"] == "ok":
                results.setdefault(slot, "Complete")
            elif slot not in results:
                results[slot] = "__NO_INFO__"
        self.progress_signal.emit(100)
        # v1.77: ставим маркер «finished уже эмитирован» — run() не должен
        # эмитить второй finished («Операция завершена успешно»), иначе
        # диалог результата открывался дважды и строка «--- Операция:
        # Просмотр результата завершена ---» писалась в лог дважды.
        self._finished_emitted = True
        self.finished_signal.emit(True, "Просмотр результата", {"modules": modules, "results": results, "action": "result"})

    def _op9_edit_plan(self, ssh):
        # Требование v1.66: операция «Редактировать СП» выполняется через
        # _op11_prepare_edit_plan (без SSH-потока в момент открытия диалога).
        self._op11_prepare_edit_plan()

    # ---------------------------------------------------------------
    # v1.73: Автопрошивка — шаг 6 цепочки (сохранение СП + Update)
    # ---------------------------------------------------------------

    def _op13_auto_flash_tail(self, ssh):
        """v1.76: шаг 4 цепочки Автопрошивки — запись собранного тихим
        редактором СП (rows) как plan.xml на устройство и запуск Update.

        Строки сценария (с заполненными путями appl/boot и типами) приходят
        из GUI-шага тихого редактора через config['_auto_rows']. Путь к
        локальному plan_xml в конфиге при этом не используется — проверка/
        дозагрузка файлов выполняется прямо по строкам сценария
        (_upload_rows_firmwares), что устраняет ошибку «файл прошивки
        boot_... не найден» (раньше Update читал старый plan.xml с диска,
        где могли оставаться имена из предыдущего сценария)."""
        rows = self.config.get('_auto_rows') or []
        selected = [r for r in rows if r.get('path')]
        if not selected:
            raise Exception("Автопрошивка: сценарий пуст — нет строк "
                            "с указанными путями прошивок")

        # Контроль формата имён (включённый блокирует невалидные имена/full).
        # v1.76: контроль — через fw_name_format с результатом разбора имени
        # (короткие 'appl_..._r.bin' корректны; некорректны имена, в которых
        # парсер не обнаружил тип модуля/версию/тип прошивки, и full).
        format_control = bool(self.config.get('format_control', True))
        for row in selected:
            fname = os.path.basename(row['path'])
            info = parse_firmware_filename(fname)
            if info is None:
                info = _try_parse_short_fw_name(fname)
            src = detect_fw_source(row['path'])
            _, _ok, supported, warning = fw_name_format(fname, parsed=info)
            if src == 'full':
                supported = False
            if format_control and not supported:
                raise Exception(
                    f"Автопрошивка: файл '{fname}' не прошёл контроль "
                    f"формата ({warning or 'имя некорректно или формат full'})")
            if not supported and warning:
                self.log(f"ВНИМАНИЕ: {warning} — прошивается при "
                         "отключённом контроле формата")

        # Запись plan.xml (<Root>, type="appl") на устройство
        xml_lines = ['<Root>']
        for row in selected:
            img_type = row.get('img_type', 'apply')
            xml_lines.append(
                f'  <Image module_slot="{row["slot"]}" '
                f'module_type="{row["module_type"]}" '
                f'path="{row["path"]}" '
                f'type="{"boot" if img_type == "boot" else "appl"}" />')
        xml_lines.append('</Root>')
        with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', delete=False,
                suffix='.xml') as tmp:
            tmp.write('\n'.join(xml_lines))
            local_plan = tmp.name
        try:
            self.log(f"Запись plan.xml на устройство "
                     f"(строк сценария: {len(selected)})...")
            ssh.sftp_put(local_plan, "/home/user/fw_update/plan.xml")
            ssh.exec_command("chmod 644 /home/user/fw_update/plan.xml")
        finally:
            self._safe_remove(local_plan)
        self.progress_signal.emit(20)

        # Прошивка (Update). v1.76: проверка/дозагрузка файлов выполняется
        # по строкам сценария (_auto_rows), а не по локальному plan_xml —
        # иначе Update читал старый файл СП с диска и выдавал «файл
        # прошивки boot_... не найден», хотя редактор сохранил другие имена.
        self.log("--- Автопрошивка: запуск прошивки (Update) ---")
        self._op6_update(ssh, plan_rows=selected)
        self.progress_signal.emit(100)

    def _op13_quiet_save(self, ssh=None):
        """v1.73: тихое сохранение собранного СП на устройство.

        v1.76: вызывается из воркера op 11 (цепочка Автопрошивки, шаг 3)
        с уже открытым SSH-соединением — сохранение plan.xml выполняется в
        том же потоке до emit finished, чтобы GUI не запускал новый воркер
        из обработчика сигнала (это приводило к зависанию цепочки на шаге
        2/6: «Уже выполняется другая операция»). Вызов без ssh создаёт своё
        соединение (обратная совместимость)."""
        # v1.77: строки сценария берутся из config['_auto_rows'] (этап A),
        # если они ещё не были подготовлены воркером op 11 на этапе
        # подготовки данных ('_auto_built_rows').
        rows = self.config.get('_auto_rows') or \
            self.config.get('_auto_built_rows') or []
        selected = [r for r in rows if r.get('path')]
        if not selected:
            raise Exception("Автопрошивка: автозаполнение appl не выбрало ни "
                            "одного модуля — прошивать нечего")
        root = ET.Element("Root")
        for row in selected:
            img_type = row.get('img_type', 'apply')
            ET.SubElement(root, "Image", {
                "module_slot": str(row['slot']),
                "module_type": str(row['module_type']),
                "path": str(row['path']),
                "type": "appl" if img_type != "boot" else "boot",
            })
        tree = ET.ElementTree(root)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            tmp_path = tmp.name
        own_conn = ssh is None
        try:
            tree.write(tmp_path, encoding='utf-8', xml_declaration=True)
            if own_conn:
                ssh = SSHClient(self.config['ip'], self.config['password'])
                ssh.connect()
            self.log(f"Тихое сохранение plan.xml "
                     f"(строк сценария: {len(selected)})...")
            ssh.sftp_put(tmp_path, "/home/user/fw_update/plan.xml")
            # v1.75: запись о сохранении СП на устройство в операционном логе
            self.log(f"Сохранение СП на устройство выполнено "
                     f"(/home/user/fw_update/plan.xml, строк: {len(selected)})")
        finally:
            if own_conn and ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        self.progress_signal.emit(100)
        # v1.76: '_auto_saved' — маркер для цепочки Автопрошивки; emit
        # выполняется только когда метод вызван как самостоятельный воркер
        # op 13 (обратная совместимость). При вызове из воркера op 11
        # ('_auto_after_prepare') finished эмитит сам op 11 после метода.
        if own_conn:
            # v1.77: маркер «finished уже эмитирован» — см. выше.
            self._finished_emitted = True
            self.finished_signal.emit(True, "СП сохранён (тихий режим)", {
                "_auto_saved": True,
                # v1.77: строки СП возвращаются цепочке в data — GUI не
                # пересобирает их и не запускает дополнительный воркер
                "_auto_rows": rows,
            })

    @staticmethod
    def _safe_remove(path):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass


# ============================================================
# ДИАЛОГИ
# ============================================================

class ModuleInfoDialog(QDialog):
    def __init__(self, modules_data, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Информация о модулях")
        self.resize(1000, 550)
        layout = QVBoxLayout(self)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Номер слота", "Тип модуля", "Серийный номер",
            "Дата производства", "Версия оборудования", "Версия прошивки"
        ])
        table.setRowCount(len(modules_data))

        for i, mod in enumerate(modules_data):
            table.setItem(i, 0, QTableWidgetItem(mod['slot_num']))
            table.setItem(i, 1, QTableWidgetItem(mod.get('module_type', 'N/A')))
            serial_item = QTableWidgetItem(mod['serial_num'])
            if not mod.get('flashable', True):
                # Нет SN или резерв широкого модуля — недоступен для прошивки
                mtype = (mod.get('module_type') or '').strip().upper()
                if mod.get("reserved"):
                    reason = "резерв"
                elif mtype in ("", "NA"):
                    reason = "слот пуст"
                else:
                    reason = "модуль отсутствует"
                # Вместо 'N/A (прошивка невозможна: ...)' — короткая причина
                serial_item.setText(reason)
                serial_item.setForeground(QColor("#b30000"))
            table.setItem(i, 2, serial_item)
            table.setItem(i, 3, QTableWidgetItem(mod['manufacture_date']))
            table.setItem(i, 4, QTableWidgetItem(mod['hardware_version']))
            table.setItem(i, 5, QTableWidgetItem(mod['firmware_version']))

        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        for col in range(6):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.resizeRowsToContents()
        layout.addWidget(table)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        for btn in btn_box.buttons():
            btn.setObjectName("dialog_btn_ok")
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)


class ViewResultDialog(QDialog):
    # v1.75: кнопка «Выгрузить дамп» перенесена из главной формы в этот
    # диалог (требование заказчика). Запуск операции выполняет колбэк,
    # переданный главным окном (worker-операция 7).
    def __init__(self, modules, results, parent=None, on_dump=None):
        super().__init__(parent)
        self.setWindowTitle("Результат прошивки")
        self.resize(750, 450)
        layout = QVBoxLayout(self)
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Номер слота", "Тип модуля", "Путь к файлу", "Тип прошивки", "Результат"])
        table.setRowCount(len(modules))
        for i, mod in enumerate(modules):
            table.setItem(i, 0, QTableWidgetItem(mod['slot']))
            table.setItem(i, 1, QTableWidgetItem(mod['type']))
            table.setItem(i, 2, QTableWidgetItem(mod['path']))
            # Внутренний тип 'apply' отображается как 'appl' (как в plan.xml)
            img_type_item = "appl" if mod['img_type'] == "apply" else mod['img_type']
            table.setItem(i, 3, QTableWidgetItem(img_type_item))
            res_raw = results.get(mod['slot'], "__NO_INFO__")
            if res_raw == "__NO_INFO__":
                res = "Нет информации"
            elif "Complete" in res_raw:
                res = res_raw
            else:
                res = res_raw if res_raw.startswith("Ошибка") else f"Ошибка: {res_raw}"
            item = QTableWidgetItem(res)
            if res_raw == "__NO_INFO__":
                item.setForeground(QColor("#666666"))
            elif "Complete" not in res_raw:
                item.setForeground(QColor("#b30000"))
            else:
                item.setForeground(QColor("#006600"))
            table.setItem(i, 4, item)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        table.resizeRowsToContents()
        layout.addWidget(table)
        # v1.75: кнопка «Выгрузить дамп» — перенесена в диалог из главной формы
        self.dump_btn = QPushButton("Выгрузить дамп")
        self.dump_btn.setObjectName("dialog_btn_dump")
        if on_dump is not None:
            self.dump_btn.clicked.connect(
                lambda checked=False: on_dump(self))
        else:
            self.dump_btn.setEnabled(False)
        layout.addWidget(self.dump_btn, alignment=Qt.AlignmentFlag.AlignLeft)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        for btn in btn_box.buttons():
            btn.setObjectName("dialog_btn_ok")
        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)


class EditSPDialog(QDialog):
    COL_CHECK = 0
    COL_SLOT = 1
    COL_TYPE = 2
    COL_PATH = 3
    COL_FWTYPE = 4
    COL_DEV_VER = 5
    COL_FW_VER = 6
    COL_DATE = 7
    COL_COUNT = 8

    def __init__(self, modules_info, plan_modules, firmwares, config,
                 parent=None, quiet=False, on_log=None):
        super().__init__(parent)
        # v1.73: тихий режим (Автопрошивка) — без диалоговых окон
        self.quiet = quiet
        # v1.75: колбэк записи в операционный лог главного окна
        # (сохранение СП на устройство фиксируется в журнале)
        self._log_cb = on_log
        self.setWindowTitle("Редактирование сценария прошивки")
        self.resize(1600, 820)
        self.config = config
        # v1.70: предупреждения при сохранении СП без контроля формата
        # (некорректные имена / формат full) — выводятся одним окном.
        self.warnings = []
        self.firmwares = firmwares
        self.fw_by_type = {}
        for fw in firmwares:
            mt = fw.get("module_type", "").upper()
            if mt:
                self.fw_by_type.setdefault(mt, []).append(fw)

        def _norm_slot(v):
            try:
                return str(int(str(v).strip()))
            except (TypeError, ValueError):
                return ''
        plan_by_slot = {_norm_slot(m['slot']): m for m in plan_modules}
        self.rows = []
        for info in modules_info:
            slot = info['slot_num']
            plan = plan_by_slot.get(slot, {})
            # Модуль без серийного номера прошить нельзя (не идентифицирован);
            # резерв широкого модуля (slot_count>1) — тоже нельзя
            flashable = info.get('flashable', info.get('serial_num', 'N/A') != 'N/A')
            unflash_reason = ""
            if not flashable:
                # Тексты причин: 'резерв' (широкий модуль), 'слот пуст' (тип NA),
                # 'модуль отсутствует' (тип известен, но SN нет)
                if info.get("reserved"):
                    unflash_reason = "резерв"
                elif str(info.get('module_type', 'NA')).upper() in ("NA", ""):
                    unflash_reason = "слот пуст"
                else:
                    unflash_reason = "модуль отсутствует"
            self.rows.append({
                "slot": slot,
                "module_type": info.get('module_type', 'NA'),
                "device_fw_version": info.get('firmware_version', 'N/A'),
                "path": plan.get('path', ''),
                "img_type": normalize_img_type(plan.get('img_type')) or 'apply',
                "local_fw": None,
                "flashable": flashable,
                "unflash_reason": unflash_reason,
            })

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(self.COL_COUNT)
        self.table.setHorizontalHeaderLabels([
            "Выбор", "Слот", "Тип модуля", "Путь к файлу", "Тип прошивки",
            "Версия на устройстве", "Версия в директории", "Дата"
        ])
        self.table.setRowCount(len(self.rows))

        self.checkboxes = []
        self.path_edits = []
        self.type_combos = []
        self.browse_btns = []

        for i, row in enumerate(self.rows):
            cb = QCheckBox()
            if row.get("flashable", True):
                cb.setChecked(True)
            else:
                # Нет серийного номера / резерв широкого модуля — прошивка запрещена
                cb.setEnabled(False)
                reason = row.get("unflash_reason") or "прошивка невозможна"
                cb.setToolTip(f"Прошивка невозможна: {reason}")
            cb.stateChanged.connect(lambda state, idx=i: self._on_checkbox_changed(idx))
            self.checkboxes.append(cb)
            self.table.setCellWidget(i, self.COL_CHECK, cb)

            slot_item = QTableWidgetItem(row['slot'])
            type_item = QTableWidgetItem(row['module_type'])
            if not row.get("flashable", True):
                red = QColor("#b30000")
                slot_item.setForeground(red)
                type_item.setForeground(red)
                reason = row.get("unflash_reason") or "прошивка невозможна"
                type_item.setText(f"{row['module_type']} ({reason})")
            self.table.setItem(i, self.COL_SLOT, slot_item)
            self.table.setItem(i, self.COL_TYPE, type_item)

            path_widget = QWidget()
            path_layout = QHBoxLayout(path_widget)
            path_layout.setContentsMargins(0, 0, 0, 0)
            path_layout.setSpacing(2)
            path_edit = QLineEdit(row['path'])
            path_edit.editingFinished.connect(lambda idx=i: self._on_path_changed(idx))
            # v1.71: пустой путь — выбор снят и неактивен; реагируем и на
            # ввод текста (не только editingFinished), чтобы чекбокс сразу
            # активировался при непустом пути
            path_edit.textChanged.connect(
                lambda _t, idx=i: self._update_row(idx))
            browse_btn = QPushButton("...")
            browse_btn.setObjectName("browse_fw_btn")
            browse_btn.setToolTip("Выбрать файл прошивки")
            browse_btn.clicked.connect(lambda checked, idx=i: self._browse_firmware(idx))
            if not row.get("flashable", True):
                # Резерв широкого модуля / нет SN — путь пуст и неактивен
                path_edit.setText("")
                path_edit.setEnabled(False)
                path_edit.setPlaceholderText("недоступно")
                browse_btn.setEnabled(False)
                row['path'] = ""
            path_layout.addWidget(path_edit)
            path_layout.addWidget(browse_btn)
            self.path_edits.append(path_edit)
            self.browse_btns.append(browse_btn)
            self.table.setCellWidget(i, self.COL_PATH, path_widget)

            combo = QComboBox()
            # Внутренние значения ('apply'/'boot'), отображаемые — 'appl'/'boot'
            combo.addItem(display_img_type("apply"), "apply")
            combo.addItem(display_img_type("boot"), "boot")
            combo.setCurrentIndex(0 if row['img_type'] == "apply" else 1)
            combo.currentIndexChanged.connect(lambda _idx, i=i: self._update_row(i))
            self.type_combos.append(combo)
            self.table.setCellWidget(i, self.COL_FWTYPE, combo)

            self.table.setItem(i, self.COL_DEV_VER, QTableWidgetItem(row['device_fw_version']))

            for col in range(self.COL_FW_VER, self.COL_COUNT):
                self.table.setItem(i, col, QTableWidgetItem("N/A"))

            if row['path']:
                self._find_local_fw(i)
            self._update_row(i)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_CHECK, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().resizeSection(self.COL_CHECK, 70)
        for col in [self.COL_SLOT, self.COL_TYPE, self.COL_FWTYPE, self.COL_DEV_VER,
                    self.COL_FW_VER, self.COL_DATE]:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(self.COL_PATH, QHeaderView.ResizeMode.Stretch)
        self.table.resizeRowsToContents()
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        # v1.69: одна «Автозаполнение» разделена на две — по типу прошивки
        # (appl / boot). Формат full автозаполнением не выбирается.
        self.autofill_appl_btn = QPushButton("Автозаполнение appl")
        self.autofill_appl_btn.setObjectName("autofill_btn")
        self.autofill_appl_btn.setToolTip(
            "Подобрать файлы типа appl по типам модулей и выставить тип 'appl'")
        self.autofill_appl_btn.clicked.connect(
            lambda: self.autofill("apply"))
        btn_layout.addWidget(self.autofill_appl_btn)

        self.autofill_boot_btn = QPushButton("Автозаполнение boot")
        self.autofill_boot_btn.setObjectName("autofill_btn")
        self.autofill_boot_btn.setToolTip(
            "Подобрать файлы типа boot по типам модулей и выставить тип 'boot'")
        self.autofill_boot_btn.clicked.connect(
            lambda: self.autofill("boot"))
        btn_layout.addWidget(self.autofill_boot_btn)

        self.select_all_btn = QPushButton("Выбрать все")
        self.select_all_btn.setObjectName("dialog_btn_ok")
        self.select_all_btn.clicked.connect(self.select_all)
        btn_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Снять все")
        self.deselect_all_btn.setObjectName("dialog_btn_cancel")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        btn_layout.addWidget(self.deselect_all_btn)

        # v1.69: кнопки массового выбора типов модулей, присутствующих в
        # устройстве (создаются динамически в _build_type_select_buttons)
        self.type_group = QGroupBox("Выбор модулей по типу")
        self.type_group.setObjectName("type_select_group")
        self.type_group_layout = QHBoxLayout(self.type_group)
        self.type_group_layout.setContentsMargins(6, 4, 6, 4)
        self.type_group_layout.setSpacing(6)
        self._type_btns = []
        self._build_type_select_buttons()
        layout.addWidget(self.type_group)

        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Отмена")
        self.cancel_btn.setObjectName("dialog_btn_cancel")
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.edit_btn = QPushButton("Сохранить")
        self.edit_btn.setObjectName("dialog_btn_ok")
        self.edit_btn.clicked.connect(self.apply_edit)
        btn_layout.addWidget(self.edit_btn)

        layout.addLayout(btn_layout)

    def _find_local_fw(self, idx):
        """Находит запись прошивки в self.firmwares по текущему пути строки.

        Совпадение сначала по rel_path (полный относительный путь, различает
        одноимённые файлы из разных подпапок), затем по имени файла.
        Заполняет row['local_fw'] и row['source'].
        """
        row = self.rows[idx]
        path = row.get('path', '')
        filename = os.path.basename(path) if path else ""
        found_fw = None
        if filename:
            # путь вида 'images/<file>' или 'images/<subdir>/<file>' — снимаем префикс images/
            rel = re.sub(r'^images/', '', path.replace('\\', '/'))
            for fw in self.firmwares:
                if fw.get('rel_path') == rel:
                    found_fw = fw
                    break
            if found_fw is None:
                for fw in self.firmwares:
                    if fw['filename'] == filename:
                        found_fw = fw
                        break
            if found_fw is None:
                found_fw = parse_firmware_filename(filename)
                if found_fw:
                    found_fw['filename'] = filename
                    found_fw['source'] = detect_fw_source(path)
                    # v1.71: для файлов вне скана firmware_dir (например,
                    # выбранных через «Обзор») fmt_ok не задан — вычисляем
                    # полный контроль формата по имени сразу, чтобы
                    # «Выбрать все» и загрузка корректно учитывали опцию
                    # «Контроль формата прошивок».
                    _f, _ok, _sup, _w = fw_name_format(filename, parsed=found_fw)
                    found_fw['fmt_ok'] = bool(_sup)
                else:
                    # Имя с корректным префиксом, но не проходит строгий
                    # шаблон (например appl_atb3500_dir12_r.bin из плана без
                    # версии/даты) — формируем минимальную запись, иначе
                    # путь остался бы без local_fw и модуль нельзя было бы
                    # выбрать даже при отключённом контроле формата.
                    prefix_fmt, pfx_ok, sup, _warn = fw_name_format(filename)
                    if pfx_ok:
                        parts = os.path.splitext(filename)[0].split("_")
                        mt = parts[2].upper() if len(parts) > 2 else "N/A"
                        if mt == "PSU":
                            mt = "POWER_UNIT"
                        found_fw = {
                            "module_type": mt,
                            "version": "N/A",
                            "date": "N/A",
                            "fw_type": "boot" if prefix_fmt == "boot" else "apply",
                            "name_prefix": prefix_fmt,
                            "marker": parts[1].upper() if len(parts) > 1 else "N/A",
                            "manufacturer": parts[1].upper() if len(parts) > 1 else "N/A",
                            "filename": filename,
                            "local_path": "",
                            "rel_path": re.sub(r'^images/', '', path.replace('\\', '/')),
                            "fmt_ok": bool(sup),
                        }
                        # источник: по пути (подпапка full/apply/boot), иначе
                        # из префикса имени ('appl' -> внутренний 'apply')
                        found_fw["source"] = detect_fw_source(path) or \
                            ("apply" if prefix_fmt == "appl" else prefix_fmt)
        row['local_fw'] = found_fw
        row['source'] = (found_fw.get('source') if found_fw else None) \
            or detect_fw_source(path)
        return found_fw

    def _browse_firmware(self, idx):
        fw_dir = self.config.get('firmware_dir', '')
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл прошивки",
            fw_dir, "BIN файлы (*.bin);;Все файлы (*.*)"
        )
        if not file_path:
            return
        try:
            rel = os.path.relpath(file_path, fw_dir).replace("\\", "/")
        except ValueError:
            rel = os.path.basename(file_path)
        if rel.startswith(".."):
            rel = os.path.basename(file_path)
        rel_path = f"images/{rel}"
        self.path_edits[idx].setText(rel_path)
        self.rows[idx]['path'] = rel_path
        self._find_local_fw(idx)
        self._update_row(idx)

    def _on_checkbox_changed(self, idx):
        self._update_row(idx)

    def _on_path_changed(self, idx):
        path = self.path_edits[idx].text().strip()
        self.rows[idx]['path'] = path
        self._find_local_fw(idx)
        self._update_row(idx)

    def _apply_combo_for_source(self, idx):
        """Ограничивает выбор 'Тип прошивки' в зависимости от директории-источника.

        full  → доступны appl и boot (выбор сохраняется);
        appl → только appl; boot → только boot;
        пустой путь / неflashable → combo неактивен.
        """
        row = self.rows[idx]
        combo = self.type_combos[idx]
        model = self._combo_model(combo)
        path = self.path_edits[idx].text().strip()
        if not path or not row.get("flashable", True):
            combo.setEnabled(False)
            return
        combo.setEnabled(True)
        allowed = allowed_img_types(row.get('source'))
        cur = combo.currentData()
        combo.blockSignals(True)
        # В PyQt6 у QComboBox нет метода setItemEnabled (он есть только в
        # C++ Qt >= 6.7); доступность отдельных пунктов управляется через
        # флаги элементов модели — QStandardItem.setFlags (v1.68, фикс
        # падения редактора СП на плане с appl-путями).
        for i in range(combo.count()):
            item = model.item(i) if hasattr(model, "item") else None
            if item is None:
                continue
            if combo.itemData(i) in allowed:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled
                              | Qt.ItemFlag.ItemIsSelectable)
            else:
                item.setFlags((item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                              & ~Qt.ItemFlag.ItemIsSelectable)
        target = cur if cur in allowed else allowed[0]
        combo.setCurrentIndex(combo.findData(target))
        row['img_type'] = target
        combo.blockSignals(False)

    @staticmethod
    def _combo_model(combo):
        """Модель QComboBox (для управления доступностью отдельных пунктов)."""
        return combo.model()

    def _update_row(self, idx):
        row = self.rows[idx]
        fw = row.get('local_fw')

        # v1.70: пустой путь к файлу — выбор модуля снят И чекбокс
        # неактивен (нельзя выбрать модуль без файла прошивки).
        cb = self.checkboxes[idx]
        path_empty = not self.path_edits[idx].text().strip()
        if row.get("flashable", True):
            wants_checked = self._is_selectable(idx)
            # v1.71: пустой путь — выбор снят и чекбокс неактивен
            cb.setEnabled(not path_empty)
            if cb.isChecked() != wants_checked:
                cb.blockSignals(True)
                cb.setChecked(wants_checked)
                cb.blockSignals(False)
            if path_empty:
                cb.setToolTip("Путь к файлу прошивки не указан — выбор недоступен")
            else:
                cb.setToolTip("")

        if fw:
            self.table.item(idx, self.COL_FW_VER).setText(fw.get('version', 'N/A'))
            self.table.item(idx, self.COL_DATE).setText(fw.get('date', 'N/A'))
        else:
            for col in [self.COL_FW_VER, self.COL_DATE]:
                self.table.item(idx, col).setText("N/A")

        self._apply_combo_for_source(idx)

        checked = self.checkboxes[idx].isChecked()
        device_ver = normalize_fw_version(row.get('device_fw_version'))
        local_ver = normalize_fw_version(fw.get('version') if fw else None)
        versions_match = (fw is not None and device_ver != 'N/A' and local_ver != 'N/A'
                          and device_ver == local_ver)

        bg_color = None
        if not checked:
            bg_color = "#e0e0e0"
        elif versions_match:
            # Совпадение версий — только подсветка (перепрошивка той же
            # версией разрешена, выбор не снимается — требование v1.71)
            bg_color = "#c8e6c9"

        for col in range(self.COL_COUNT):
            item = self.table.item(idx, col)
            if item is not None:
                if bg_color:
                    item.setBackground(QColor(bg_color))
                else:
                    item.setBackground(QColor("#ffffff"))

        path_widget = self.table.cellWidget(idx, self.COL_PATH)
        combo_widget = self.table.cellWidget(idx, self.COL_FWTYPE)
        for w in [path_widget, combo_widget]:
            if w:
                if bg_color:
                    w.setStyleSheet(f"background-color: {bg_color};")
                else:
                    w.setStyleSheet("")

    def _fw_matches_type(self, fw, want_type):
        """Относит ли файл прошивки к запрошенному типу образа (appl/boot).

        Приоритет: директория-источник ('source' из скана firmware_dir),
        затем префикс имени файла ('name_prefix'), затем 'fw_type'.
        Файлы формата full (префикс/источник 'full') не относятся ни к
        appl, ни к boot — автозаполнение их не выбирает.
        """
        src = (fw.get('source') or '').lower()
        if src in ('apply', 'appl'):
            return want_type == 'apply'
        if src == 'boot':
            return want_type == 'boot'
        if src == 'full':
            return False
        prefix = (fw.get('name_prefix') or '').lower()
        if prefix == 'appl':
            return want_type == 'apply'
        if prefix == 'boot':
            return want_type == 'boot'
        if prefix == 'full':
            return False
        # fallback: внутренний тип образа из разбора имени
        return (fw.get('fw_type') or '') == want_type

    def autofill(self, want_type="apply"):
        """Автозаполнение путей и типа прошивки по всем прошиваемым строкам.

        want_type: 'apply' (кнопка «Автозаполнение appl») или 'boot'.
        Подбираются только файлы соответствующего типа; формат full не
        выбирается. Тип образа в combo выставляется в want_type (для
        appl-/boot-директорий он и так единственный допустимый). После
        заполнения — «Снять все», затем «Выбрать все».
        """
        filled = 0
        for i, row in enumerate(self.rows):
            # Резервы широких модулей и недоступные для прошивки слоты
            # автозаполнением не обрабатываются (их пути должны оставаться пустыми)
            if not row.get("flashable", True):
                continue
            mt = row['module_type'].upper()
            if mt in ("NA", ""):
                continue
            candidates = [fw for fw in self.fw_by_type.get(mt, [])
                          if self._fw_matches_type(fw, want_type)]
            if not candidates:
                continue

            def ver_key(fw):
                v = fw.get('version', '0')
                m = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', v)
                if m:
                    return tuple(int(x or 0) for x in m.groups())
                return (0, 0, 0)

            best = max(candidates, key=ver_key)
            rel_path = f"images/{best.get('rel_path', best['filename'])}"
            self.path_edits[i].setText(rel_path)
            row['path'] = rel_path
            row['local_fw'] = best
            row['source'] = best.get('source') or detect_fw_source(rel_path)
            # Выставляем запрошенный тип образа (combo сам ограничит выбор
            # допустимым для источника значением)
            combo = self.type_combos[i]
            idx_t = combo.findData(want_type)
            if idx_t >= 0:
                combo.setCurrentIndex(idx_t)
            row['img_type'] = want_type
            self._update_row(i)
            filled += 1
        # После автозаполнения: сначала снять весь выбор, затем выбрать все
        # подходящие строки (flashable + непустой путь)
        self.deselect_all()
        self.select_all()
        if not self.quiet and not os.environ.get("MFC_TESTS_NO_MSGBOX"):
            QMessageBox.information(
                self, "Автозаполнение",
                f"Тип прошивки: {display_img_type(want_type)}. "
                f"Заполнено путей: {filled}")

    def _is_selectable(self, idx):
        """Строка подлежит выбору: модуль прошивается, путь к файлу указан и
        (при включённом контроле формата) файл прошёл проверку формата."""
        row = self.rows[idx]
        if not row.get("flashable", True):
            return False
        path = self.path_edits[idx].text().strip()
        if not path:
            return False
        if not self._format_ok(path):
            return False
        return True

    def _format_ok(self, path):
        """Прохождение контроля формата имени файла прошивки.

        Использует результат скана firmware_dir (row['local_fw']), если он
        есть; иначе — префикс имени файла. При отключённой опции
        «Контроль формата прошивок» всегда возвращает True.
        """
        if bool(self.config.get('format_control', True)):
            return bool(self.fw_format_supported(path))
        return True

    def fw_format_supported(self, path):
        """supported-флаг строгого контроля формата имени файла прошивки.

        v1.71: контроль касается НЕ только full — файл считается
        некорректным, если парсер не может обнаружить в имени версию, тип
        модуля или тип прошивки (например 'appl_atb3500_ai8_r.bin'). При
        включённом контроле формата такие файлы не загружаются на устройство
        и не прошиваются; при отключённом — только предупреждения.
        """
        fw = None
        for row in self.rows:
            cand = row.get('local_fw')
            if cand and (cand.get('rel_path') == re.sub(r'^images/', '', path)
                        or cand.get('filename') == os.path.basename(path)):
                fw = cand
                break
        filename = os.path.basename((fw or {}).get('filename') or path)
        _, _, supported, _warning = fw_name_format(filename, parsed=fw)
        return supported

    def select_all(self):
        """Выбирает все модули, для которых разрешена прошивка.

        Условия (v1.71): модуль доступен (есть SN, не резерв широкого
        модуля), путь к файлу прошивки непустой, файл прошёл контроль
        формата (при включённой опции); совпадение версии прошивки с версией
        на устройстве выбор НЕ снимает (модуль можно перепрошить той же
        версией)."""
        for i, cb in enumerate(self.checkboxes):
            ok = self._is_selectable(i)
            cb.blockSignals(True)
            if self.rows[i].get("flashable", True):
                # чекбокс прошиваемого модуля всегда активен; для строк с
                # пустым путём/некорректным форматом выбор просто снят
                cb.setEnabled(True)
            cb.setChecked(bool(ok))
            cb.blockSignals(False)
            self._update_row(i)

    def deselect_all(self):
        for i, cb in enumerate(self.checkboxes):
            cb.blockSignals(True)
            cb.setChecked(False)
            cb.blockSignals(False)
            self._update_row(i)

    def _present_module_types(self):
        """Типы модулей, реально присутствующие в устройстве (в порядке слотов).

        Берутся только прошиваемые строки (есть SN, не резерв) с известным
        типом; NA/пустые типы исключаются. PSU нормализуется к POWER_UNIT.
        """
        seen = []
        for row in self.rows:
            if not row.get("flashable", True):
                continue
            mt = str(row.get("module_type") or "").strip().upper()
            if mt in ("", "NA"):
                continue
            if mt == "PSU":
                mt = "POWER_UNIT"
            if mt not in seen:
                seen.append(mt)
        return seen

    def _build_type_select_buttons(self):
        """Кнопки выбора всех модулей конкретного типа (v1.69).

        Создаются по типам модулей, присутствующим в устройстве. Нажатие
        включает выбор во всех подходящих строках данного типа (условия
        selectable соблюдаются); строки других типов не меняются.
        """
        for b in self._type_btns:
            b.setParent(None)
            b.deleteLater()
        self._type_btns = []
        types = self._present_module_types()
        if not types:
            self.type_group.setVisible(False)
            return
        self.type_group.setVisible(True)
        self.type_group.setTitle(
            "Выбор модулей по типу (присутствуют в устройстве)")
        for mt in types:
            btn = QPushButton(mt)
            btn.setObjectName("type_select_btn")
            btn.setToolTip(f"Выбрать все модули типа {mt}")
            btn.clicked.connect(lambda checked, t=mt: self.select_by_type(t))
            self.type_group_layout.addWidget(btn)
            self._type_btns.append(btn)

    def select_by_type(self, module_type):
        """Включает выбор во всех строках указанного типа модуля."""
        want = (module_type or "").upper()
        changed = 0
        for i, cb in enumerate(self.checkboxes):
            row = self.rows[i]
            rt = str(row.get("module_type") or "").strip().upper()
            if rt == "PSU":
                rt = "POWER_UNIT"
            if rt != want:
                continue
            if not self._is_selectable(i):
                # путь пуст / формат не прошёл контроль — выбрать нельзя
                continue
            if not cb.isChecked():
                cb.setChecked(True)
                changed += 1
            self._update_row(i)
        if changed == 0 and not self.quiet and not any(
                self._is_selectable(i) and
                (str(self.rows[i].get("module_type") or "").strip().upper()
                 in (want, "PSU" if want == "POWER_UNIT" else want))
                for i in range(len(self.rows))):
            QMessageBox.information(
                self, "Выбор по типу",
                f"Нет доступных для прошивки модулей типа {want} "
                "(не заполнены пути или не пройден контроль формата)")

    def _validate_row(self, idx):
        row = self.rows[idx]
        if not row.get("flashable", True):
            reason = row.get("unflash_reason") or "прошивка невозможна"
            return False, f"Слот {row['slot']}: {reason} — прошивка модуля запрещена"
        path = self.path_edits[idx].text().strip()
        if not path:
            return False, f"Слот {row['slot']}: путь к файлу не указан"
        filename = os.path.basename(path)
        # Контроль формата прошивок (по умолчанию включён): запрещает
        # сохранение в СП файлов с некорректными именами и формат full.
        if bool(self.config.get('format_control', True)) \
                and not self._format_ok(path):
            _fmt, ok_prefix, _sup, warning = fw_name_format(filename)
            return False, (f"Слот {row['slot']}: "
                           f"{warning or 'файл не прошёл контроль формата'}")
        parsed = parse_firmware_filename(filename)
        if parsed is None and not bool(self.config.get('format_control', True)):
            # v1.70: без контроля формата создание СП допускается с
            # НЕКОРРЕКТНЫМИ именами и форматом full — только предупреждение
            # (пользователь осознанно отключил контроль).
            _fmt, _okp, _sup, warning = fw_name_format(filename)
            if warning:
                self.warnings.append(f"Слот {row['slot']}: {warning}")
            return True, ""
        if parsed is None:
            return False, f"Слот {row['slot']}: файл '{filename}' не соответствует формату имени прошивки"
        if parsed['module_type'] != row['module_type'].upper():
            return False, (f"Слот {row['slot']}: прошивка '{filename}' (тип {parsed['module_type']}) "
                           f"не соответствует типу модуля {row['module_type']}")
        # Тип прошивки должен быть допустим для директории-источника:
        # apply/ -> только apply, boot/ -> только boot, full/ -> apply или boot.
        source = row.get('source') or detect_fw_source(path)
        img_type = self.type_combos[idx].currentData()
        if img_type not in allowed_img_types(source):
            return False, (f"Слот {row['slot']}: тип '{display_img_type(img_type)}' недопустим для прошивки из "
                           f"директории '{source or 'неизвестна'}' "
                           f"(допустимо: {', '.join(display_img_type(t) for t in allowed_img_types(source))})")
        return True, ""

    def apply_edit(self):
        # v1.73: метод сохранён как алиас — кнопка «Сохранить» вызывает его;
        # цепочка Автопрошивки использует apply_edits().
        self.apply_edits()

    def apply_edits(self):
        selected = []
        for i, row in enumerate(self.rows):
            if not self.checkboxes[i].isChecked():
                continue
            if not row.get("flashable", True):
                # Защита от программной установки галочки — такой модуль не прошивается
                reason = row.get("unflash_reason") or "прошивка невозможна"
                msg = f"Слот {row['slot']}: {reason} — прошивка невозможна"
                if self.quiet:
                    raise Exception(msg)
                QMessageBox.critical(self, "Ошибка валидации", msg)
                return
            row['path'] = self.path_edits[i].text().strip()
            row['img_type'] = self.type_combos[i].currentData()
            ok, err = self._validate_row(i)
            if not ok:
                if self.quiet:
                    raise Exception(err)
                QMessageBox.critical(self, "Ошибка валидации", err)
                return
            selected.append(row)

        # v1.70: накопленные предупреждения (СП с некорректными именами /
        # форматом full при отключённом контроле) — показываем одним окном,
        # сохранение при этом возможно.
        if self.warnings:
            if self.quiet:
                # v1.73 (Автопрошивка): диалогов нет — предупреждения
                # подтверждаются автоматически, сохранение выполняется.
                self.warnings = []
            else:
                ret = QMessageBox.warning(
                    self, "Предупреждения формата прошивок",
                    "Контроль формата отключен, в сценарий попадают файлы:\n"
                    + "\n".join(self.warnings[:20])
                    + ("\n..." if len(self.warnings) > 20 else "")
                    + "\n\nСохранить сценарий?")
                self.warnings = []
                if ret != QMessageBox.StandardButton.Yes:
                    return

        if not selected and not self.quiet:
            # v1.69: пустой сценарий сохраняется по требованию заказчика —
            # предупреждение показывается, но запись plan.xml выполняется
            # (создаётся пустой <Root/>).
            ret = QMessageBox.warning(
                self, "Внимание",
                "Не выбрано ни одного модуля для прошивки.\n"
                "Сохранить пустой сценарий прошивки?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret != QMessageBox.StandardButton.Yes:
                return
        elif not selected and self.quiet:
            # v1.73: в тихом режиме пустой СП — ошибка Автопрошивки
            raise Exception("Автопрошивка: автозаполнение appl не выбрало ни "
                            "одного модуля — прошивать нечего")

        # Корень сценария прошивки — <Root> (по требованию бэкенда; раньше был <Plan>)
        # Тип образа 'apply' записывается в файл как 'appl' (требование бэкенда).
        root = ET.Element("Root")
        for row in selected:
            xml_type = "appl" if row['img_type'] == "apply" else row['img_type']
            ET.SubElement(root, "Image", {
                "module_slot": row['slot'],
                "module_type": row['module_type'],
                "path": row['path'],
                "type": xml_type
            })
        tree = ET.ElementTree(root)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            tmp_path = tmp.name
        tree.write(tmp_path, encoding='utf-8', xml_declaration=True)

        try:
            ssh = SSHClient(self.config['ip'], self.config['password'])
            ssh.connect()
            ssh.sftp_put(tmp_path, "/home/user/fw_update/plan.xml")
            ssh.close()
            os.remove(tmp_path)
            # v1.75: сохранение СП на устройство фиксируется в операционном логе
            OperationWorker.log_via(
                self._log_cb,
                f"Сохранение СП на устройство выполнено "
                f"(/home/user/fw_update/plan.xml, строк сценария: {len(selected)})")
            QMessageBox.information(self, "Успех", "Сценарий успешно сохранён на устройстве")
            self.accept()
        except Exception as e:
            # v1.66: cleanup-safe — временный файл удаляется в любом случае
            try:
                ssh.close()
            except Exception:
                pass
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить сценарий: {e}")


# ============================================================
# ГЛАВНОЕ ОКНО
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None  # v1.66: текущий воркер операции (защита от параллельного запуска)
        # v1.75: инициализация состояния цепочки «Автопрошивка» — раньше
        # атрибут _auto_step создавался лениво, и start_operation(13)
        # обращался к нему напрямую (self._auto_step == 0), что давало
        # AttributeError: 'MainWindow' object has no attribute '_auto_step'
        self._auto_step = 0
        self._auto_failed = False
        self._auto_failed_step = None
        self._auto_rows = None
        # v1.75: данные для повторного открытия диалога «Просмотр результата»
        # после выгрузки дампа (None — обычный режим, не возврат из дампа)
        self._dump_reopen_data = None
        self._ops_busy = False
        self.setWindowTitle(APP_TITLE)
        self.resize(1000, 800)
        self.config = self.load_config()
        self.init_ui()
        self.load_settings_to_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        conn_group = QGroupBox("Подключение и пути")
        conn_layout = QGridLayout()
        conn_layout.addWidget(QLabel("IP-адрес МФК:"), 0, 0)
        self.ip_edit = QLineEdit()
        conn_layout.addWidget(self.ip_edit, 0, 1)
        conn_layout.addWidget(QLabel("Пароль root:"), 0, 2)
        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        conn_layout.addWidget(self.pass_edit, 0, 3)
        conn_layout.addWidget(QLabel("Файл агента:"), 1, 0)
        self.agent_edit = QLineEdit()
        self.agent_edit.setPlaceholderText("Полный путь к файлу IskraIO_Util")
        conn_layout.addWidget(self.agent_edit, 1, 1, 1, 2)
        self.agent_btn = QPushButton("Обзор...")
        self.agent_btn.setObjectName("browse_btn")
        self.agent_btn.clicked.connect(self.browse_agent_file)
        conn_layout.addWidget(self.agent_btn, 1, 3)
        conn_layout.addWidget(QLabel("Директория прошивок:"), 2, 0)
        self.fw_edit = QLineEdit()
        conn_layout.addWidget(self.fw_edit, 2, 1, 1, 2)
        self.fw_btn = QPushButton("Обзор...")
        self.fw_btn.setObjectName("browse_btn")
        self.fw_btn.clicked.connect(lambda: self.browse_dir(self.fw_edit))
        conn_layout.addWidget(self.fw_btn, 2, 3)
        conn_layout.addWidget(QLabel("Файл сценария (plan.xml):"), 3, 0)
        self.plan_edit = QLineEdit()
        conn_layout.addWidget(self.plan_edit, 3, 1, 1, 2)
        self.plan_btn = QPushButton("Обзор...")
        self.plan_btn.setObjectName("browse_btn")
        self.plan_btn.clicked.connect(lambda: self.browse_file(self.plan_edit))
        conn_layout.addWidget(self.plan_btn, 3, 3)
        # v1.71: поле ввода «API путь» убрано — путь фиксирован
        # (/vx3/backend.fcgi, см. BackendClient.API_PATH).
        # Опция «Контроль формата прошивок» (по умолчанию включена):
        # при включённой прошивки, не прошедшие контроль формата имени,
        # на устройство не загружаются и модули ими не прошиваются;
        # при отключённой выводятся предупреждения, но загрузка/прошивка
        # выполняются (включая формат full).
        self.format_control_cb = QCheckBox(
            "Контроль формата прошивок (не загружать и не прошивать"
            " файлы с некорректными именами и формат full)")
        self.format_control_cb.setToolTip(
            "По умолчанию включена: файлы, имена которых не начинаются\n"
            "с 'appl' или 'boot' (а также неподдерживаемый формат 'full'),\n"
            "на устройство не загружаются и прошивка ими запрещена.\n"
            "При отключении ограничения снимаются: выводятся только\n"
            "предупреждения, загрузка и прошивка выполняются.")
        conn_layout.addWidget(self.format_control_cb, 4, 0, 1, 4)
        conn_group.setLayout(conn_layout)
        main_layout.addWidget(conn_group)

        ops_group = QGroupBox("Операции")
        ops_layout = QGridLayout()
        col1_ops = [
            (1, "Внедрить агента и прошивки", "col1_btn_1"),
            (10, "Информация о модулях", "col1_btn_10"),
            (6, "Запустить прошивку", "col1_btn_6"),
            # v1.75: «Выгрузить дамп» перенесена в диалог «Просмотр результата»
            (8, "Просмотр результата", "col1_btn_8"),
            # v1.76: «Удалить агента» перенесена из правой колонки в левую
            (12, "Удалить агента", "col1_btn_12"),
        ]
        for i, (op_id, text, obj_name) in enumerate(col1_ops):
            btn = QPushButton(text)
            btn.setObjectName(obj_name)
            btn.clicked.connect(lambda checked, oid=op_id: self.start_operation(oid))
            ops_layout.addWidget(btn, i, 0)
        col2_ops = [
            (2, "Создать СП", "col2_btn_2"),
            (3, "Импортировать СП", "col2_btn_3"),
            (4, "Экспортировать СП", "col2_btn_4"),
            (9, "Редактировать СП", "col2_btn_9"),
            # v1.76: «Удалить агента» перенесена в левую колонку; в правой
            # осталась только «Автопрошивка» (занимает 2 строки).
            # v1.73: последовательная цепочка «под ключ» в тихом режиме
            (13, "Автопрошивка", "col2_btn_13")
        ]
        for i, (op_id, text, obj_name) in enumerate(col2_ops):
            btn = QPushButton(text)
            btn.setObjectName(obj_name)
            btn.clicked.connect(lambda checked, oid=op_id: self.start_operation(oid))
            if op_id == 13:
                ops_layout.addWidget(btn, i, 1, 2, 1)
            else:
                ops_layout.addWidget(btn, i, 1)
        # v1.76: стиль кнопки «Автопрошивка» — как у остальных кнопок
        # (фон задаётся таблицей стилей по objectName); оставлены только
        # жирный шрифт и увеличенная высота для заметности.
        auto_btn = self.findChild(QPushButton, "col2_btn_13")
        if auto_btn is not None:
            f = auto_btn.font()
            f.setBold(True)
            f.setPointSize(f.pointSize() + 2)
            auto_btn.setFont(f)
            auto_btn.setMinimumHeight(48)
        ops_group.setLayout(ops_layout)
        main_layout.addWidget(ops_group)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        main_layout.addWidget(self.progress_bar)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 10))
        main_layout.addWidget(self.log_text)

        bottom_layout = QHBoxLayout()
        dev_label = QLabel("Разработчик: Екимов Д.А @ 2026г.")
        dev_label.setStyleSheet("color: #333333; font-style: italic; font-size: 12px; font-weight: bold;")
        bottom_layout.addWidget(dev_label)
        bottom_layout.addStretch()
        # v1.71: чекбокс «Детализация» — слева от кнопки «Очистить лог».
        # По умолчанию выключен: в журнале только ключевые события, сводки,
        # предупреждения и ошибки. При включении показываются имена всех
        # загружаемых/игнорируемых прошивок, HTTP-детализация (Payload,
        # заголовки/тело ответа, статусы), MakePlan stdout и т.п.
        self.verbose_log_cb = QCheckBox("Детализация")
        self.verbose_log_cb.setToolTip(
            "По умолчанию выключена: в журнале только ключевые события,\n"
            "итоговые сводки, предупреждения и ошибки.\n"
            "Включите для отладки: добавятся имена всех загружаемых и\n"
            "игнорируемых прошивок, HTTP-детализация (Payload, заголовки\n"
            "и тело ответа, статусы), MakePlan stdout, пер-слотовые строки.")
        bottom_layout.addWidget(self.verbose_log_cb)
        self.clear_log_btn = QPushButton("Очистить лог")
        self.clear_log_btn.setObjectName("clear_btn")
        self.clear_log_btn.clicked.connect(self.log_text.clear)
        bottom_layout.addWidget(self.clear_log_btn)
        main_layout.addLayout(bottom_layout)

        self.all_ops = [(op_id, text) for op_id, text, _ in col1_ops + col2_ops]
        # v1.75: «Выгрузить дамп» перенесена из главной формы в диалог
        # «Просмотр результата»; операцию (op 7) по-прежнему можно запускать
        # — регистрируем её в списке операций отдельно от кнопок формы.
        self.all_ops.append((7, "Выгрузить дамп"))
        # v.66: кнопки операций для блокировки на время выполнения
        self.op_buttons = {}
        for i, (op_id, _text, _obj_name) in enumerate(col1_ops):
            self.op_buttons[op_id] = ops_layout.itemAtPosition(i, 0).widget()
        for i, (op_id, _text, _obj_name) in enumerate(col2_ops):
            self.op_buttons[op_id] = ops_layout.itemAtPosition(i, 1).widget()
        self._ops_busy = False

    def browse_dir(self, line_edit):
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите директорию")
        if dir_path:
            line_edit.setText(dir_path)
            self.save_config()

    def browse_agent_file(self):
        """Выбор файла агента (не директории) — требование v1.62."""
        start_dir = ""
        cur = self.agent_edit.text().strip()
        if cur:
            start_dir = os.path.dirname(cur) or cur
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите файл агента IskraIO_Util", start_dir, "")
        if file_path:
            self.agent_edit.setText(file_path)
            self.save_config()

    def browse_file(self, line_edit):
        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите файл", "", "XML Files (*.xml)")
        if file_path:
            line_edit.setText(file_path)
            self.save_config()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, encoding='utf-8') as f:
                return json.load(f)
        return DEFAULT_CONFIG.copy()

    def save_config(self):
        config = {
            "ip": self.ip_edit.text(),
            "password": self.pass_edit.text(),
            "agent_dir": self.agent_edit.text(),
            "firmware_dir": self.fw_edit.text(),
            "plan_xml": self.plan_edit.text(),
            "format_control": self.format_control_cb.isChecked(),
            "verbose_log": self.verbose_log_cb.isChecked()
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

    def load_settings_to_ui(self):
        self.ip_edit.setText(self.config.get("ip", ""))
        self.pass_edit.setText(self.config.get("password", ""))
        self.agent_edit.setText(self.config.get("agent_dir", ""))
        self.fw_edit.setText(self.config.get("firmware_dir", ""))
        self.plan_edit.setText(self.config.get("plan_xml", ""))
        self.format_control_cb.setChecked(bool(self.config.get("format_control", True)))
        self.verbose_log_cb.setChecked(bool(self.config.get("verbose_log", False)))

    def append_log(self, msg):
        color = "#000000"
        font_weight = "normal"
        msg_lower = msg.lower()
        if "ошибка" in msg_lower or "critical" in msg_lower or "error" in msg_lower:
            color = "#b30000"
            font_weight = "bold"
        elif "успешно" in msg_lower or "complete" in msg_lower:
            color = "#006600"
            font_weight = "bold"
        elif "предупреждение" in msg_lower or "warning" in msg_lower:
            color = "#b35900"
            font_weight = "bold"
        elif "--- запущена" in msg_lower or "--- завершена" in msg_lower:
            color = "#003399"
            font_weight = "bold"
        elif "остановка" in msg_lower or "запуск" in msg_lower:
            color = "#444444"
        safe_msg = html.escape(msg)
        self.log_text.append(f'<span style="color:{color}; font-weight:{font_weight}; font-family: Consolas, monospace;">{safe_msg}</span>')

    def get_current_config(self):
        return {
            "ip": self.ip_edit.text(),
            "password": self.pass_edit.text(),
            "agent_dir": self.agent_edit.text(),
            "firmware_dir": self.fw_edit.text(),
            "plan_xml": self.plan_edit.text(),
            "format_control": self.format_control_cb.isChecked(),
            "verbose_log": self.verbose_log_cb.isChecked()
        }

    def check_remote_dir_exists(self, path):
        try:
            ssh = SSHClient(self.ip_edit.text(), self.pass_edit.text())
            ssh.connect()
            stat = ssh.sftp_stat(path)
            ssh.close()
            return stat is not None
        except Exception as e:
            self.append_log(f"Ошибка проверки каталога: {e}")
            return False

    def check_agent_exists(self):
        try:
            ssh = SSHClient(self.ip_edit.text(), self.pass_edit.text())
            ssh.connect()
            stat = ssh.sftp_stat("/home/user/fw_update/IskraIO_Util")
            ssh.close()
            return stat is not None
        except Exception as e:
            self.append_log(f"Ошибка проверки агента: {e}")
            return False

    def _set_ops_enabled(self, enabled):
        """v1.66: блокировка кнопок операций на время выполнения другой операции."""
        self._ops_busy = not enabled
        for btn in self.op_buttons.values():
            if btn is not None:
                btn.setEnabled(enabled)

    def start_operation(self, op_id):
        # v1.77: параллельный запуск операций запрещён. В цепочке
        # Автопрошивки следующий шаг стартует из обработчика finished-сигнала
        # текущего воркера — поток ещё может числиться запущенным
        # (isRunning()==True), поэтому для шагов цепочки (_auto_step > 0)
        # эта проверка пропускается: параллельных операций в цепочке нет по
        # построению, а ложная блокировка раньше «вешала» Автопрошивку на
        # шаге 2/6 («Создать СП») с окном «Уже выполняется другая операция»
        # (шаг MakePlan выполняется долго — остановка сервисов + пауза ~15 c,
        # и завершающий его поток ещё не освободился).
        if not getattr(self, "_auto_step", 0):
            if getattr(self, "_ops_busy", False) or (
                    hasattr(self, "worker") and self.worker is not None
                    and self.worker.isRunning()):
                QMessageBox.warning(self, "Внимание",
                                    "Уже выполняется другая операция. "
                                    "Дождитесь её завершения.")
                return
        # v1.76: цепочка Автопрошивки — интерактивные проверки пропускаются
        in_auto_chain_pre = getattr(self, "_auto_step", 0) > 0
        config = self.get_current_config()
        if not config['ip'] or not config['password']:
            QMessageBox.critical(self, "Ошибка", "Укажите IP-адрес и пароль!")
            return

        if op_id == 1:
            if not config['agent_dir'] or not config['firmware_dir']:
                QMessageBox.critical(self, "Ошибка", "Укажите директории агента и прошивок!")
                return
            if self.check_remote_dir_exists("/home/user/fw_update"):
                reply = QMessageBox.warning(self, "Предупреждение",
                                            "Каталог /home/user/fw_update/ уже существует. Удалить его?",
                                            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
                if reply == QMessageBox.StandardButton.Cancel:
                    return
        elif op_id == 2:
            # v1.76: в цепочке Автопрошивки (тихий режим) интерактивные
            # проверки не выполняются — агент проверяется на устройстве
            # внутри операции MakePlan, остановка телемеханики подтверждена
            # самим пользователем запуском цепочки.
            if not in_auto_chain_pre:
                if not self.check_agent_exists():
                    QMessageBox.critical(self, "Ошибка",
                                         "Агент IskraIO_Util отсутствует. Сначала выполните 'Внедрить агента и прошивки'.")
                    return
                reply = QMessageBox.warning(self, "Предупреждение",
                                            "Телемеханика будет остановлена. Продолжить?",
                                            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
                if reply == QMessageBox.StandardButton.Cancel:
                    return
        elif op_id == 6:
            reply = QMessageBox.warning(self, "Предупреждение",
                                        "Телемеханика будет остановлена. Продолжить?",
                                        QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                return
        elif op_id == 3:
            if not config['plan_xml']:
                QMessageBox.critical(self, "Ошибка", "Укажите файл сценария!")
                return
        elif op_id == 12 and getattr(self, "_auto_step", 0) == 0:
            # В цепочке Автопрошивки (шаг 6) подтверждение не запрашивается
            reply = QMessageBox.warning(
                self, "Предупреждение",
                "Директория /home/user/fw_update/ будет удалена с "
                "контроллера. Продолжить?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel)
            if reply == QMessageBox.StandardButton.Cancel:
                self._auto_finish(getattr(self, "_auto_failed_step", None)) \
                    if getattr(self, "_auto_step", 0) else None
                return
        elif op_id == 13:
            # v1.73: Автопрошивка — предварительная проверка конфигурации
            if not config['agent_dir'] or not config['firmware_dir']:
                QMessageBox.critical(self, "Ошибка",
                                     "Укажите файлы/директории агента и прошивок!")
                return
            if self._auto_step == 0:
                # Старт цепочки (кнопка «Автопрошивка»)
                self._auto_failed = False
                self._auto_rows = None
                self.append_log("=== АВТОПРОШИВКА: запуск цепочки операций ===")

        # v1.73: при старте цепочки сразу запускаем шаг 1 (воркер не
        # создаётся — реальную работу выполняют шаги 1..6)
        if op_id == 13 and getattr(self, "_auto_step", 0) <= 1:
            self._auto_step = 1
            self._auto_run_step()
            return

        # v1.73: шаги 4..6 выполняются внутри цепочки (_auto_step > 0) без
        # интерактивных подтверждений (тихий режим Автопрошивки).
        in_auto_chain = getattr(self, "_auto_step", 0) > 0

        self.progress_bar.setValue(0)
        op_name = next((name for oid, name in self.all_ops if oid == op_id), f"ID {op_id}")
        if not in_auto_chain:
            self.append_log(f"--- Запущена операция: {op_name} ---")

        # v1.73: цепочка шагов запускается напрямую воркером соответствующей
        # операции; для шага записи СП+Update используется op 13 с данными
        # тихого редактора (_auto_rows).
        cfg = dict(config)
        quiet = in_auto_chain
        worker_op = op_id
        if op_id == 13 and in_auto_chain:
            cfg['_auto_rows'] = getattr(self, "_auto_rows", None) or []
            # Шаг 4 цепочки — запись plan.xml + Update; шаг 3 — тихое
            # сохранение СП без SSH-потока (данные подготовлены на шаге 3).
            cfg['_auto_update'] = (self._auto_step == 4)
        # v1.75/v1.76: шаг 3 цепочки (тихий редактор) выполняется в два
        # этапа — A: подготовка данных (воркер op 11), сборка строк СП GUI;
        # B: тихое сохранение plan.xml на устройство. В v1.76 этап B
        # выполняется ВНУТРИ того же воркера op 11 (_op13_quiet_save с SSH),
        # поэтому новый воркер из обработчика finished-сигнала не запускается
        # и цепочка не зависает на «Уже выполняется другая операция».
        # Строки СП передаются воркеру заранее через cfg['_auto_rows'].
        if op_id == 13 and in_auto_chain and self._auto_step == 3:
            worker_op = 11
            cfg['_auto_after_prepare'] = True
        # Шаг 2 цепочки (MakePlan): локальная проверка агента заменена на
        # удалённую проверку состояния сервисов PrjA/PrjA-tele — агент лежит
        # на контроллере, а не на диске ПК, и раньше шаг 2 падал сразу после
        # старта цепочки («зависание» наблюдалось именно здесь).
        if op_id == 2 and in_auto_chain:
            cfg['_skip_local_checks'] = True
        self.worker = OperationWorker(worker_op, cfg, quiet=quiet,
                                      on_log=self.append_log)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.on_operation_finished)
        # v1.66: на время выполнения операции остальные кнопки блокируются
        self._set_ops_enabled(False)
        self.worker.start()

    # ---------------------------------------------------------------
    # v1.73: Автопрошивка — последовательная цепочка операций (кнопка
    #   «Автопрошивка», op_id 13 как точка входа):
    #   1. Внедрение агента и прошивок (тихий режим, без диалогов)
    #   2. Создать СП (MakePlan)
    #   3. Подготовка данных редактора + тихий редактор: автозаполнение
    #      appl и сохранение СП в памяти
    #   4. Запись собранного СП (plan.xml) и прошивка (Update) — op 13
    #   5. Просмотр результата (диалог показывается)
    #   6. Удалить директорию агента и прошивок с контроллера
    # На любом сбое — причина в оперативном логе и попытка удалить
    # директорию агента (шаг 6 выполняется даже при ошибке).
    # ---------------------------------------------------------------
    AUTO_STEPS = {
        1: "Внедрить агента и прошивки",
        2: "Создать СП",
        3: "Редактировать СП (тихий режим)",
        4: "Запустить прошивку",
        5: "Просмотр результата",
        6: "Удалить агента и прошивки",
    }

    def _auto_run_step(self):
        """Запускает очередной шаг цепочки Автопрошивки через start_operation."""
        step = self._auto_step
        name = self.AUTO_STEPS.get(step, "")
        self.append_log(f"[Автопрошивка] Шаг {step}/6: {name}")
        op_map = {1: 1, 2: 2, 3: 13, 4: 13, 5: 8, 6: 12}
        # Шаг 3 (тихий редактор) запускается как op 13 — внутри
        # start_operation он перенаправляется на воркер op 11 с флагом
        # '_auto_after_prepare' (подготовка данных без открытия диалога).
        self.start_operation(op_map[step])

    def _auto_finish(self, reason=None):
        """Завершение цепочки: разблокировка кнопок и итоговое сообщение."""
        self._auto_step = 0
        self._auto_rows = None
        self._set_ops_enabled(True)
        if reason:
            self.append_log(f"=== АВТОПРОШИВКА ПРЕРВАНА: {reason} ===")
        else:
            self.append_log("=== АВТОПРОШИВКА ЗАВЕРШЕНА УСПЕШНО ===")

    def _auto_abort(self, reason):
        """Сбой шага: фиксируем причину и пытаемся удалить директорию агента."""
        self._auto_failed = True
        self.append_log(f"[Автопрошивка] СБОЙ: {reason}")
        QMessageBox.critical(self, "Автопрошивка", f"Сбой: {reason}")
        self._auto_step = 6  # попытка очистки best-effort
        self._auto_failed_step = reason
        try:
            self._auto_run_step()
        except Exception as e:
            self._auto_finish(f"{reason} (очистка не выполнена: {e})")

    def _auto_flash_step_done(self, success, message, data):
        """Обработка завершения одного шага Автопрошивки."""
        step = self._auto_step
        if not success and step != 6:
            self._auto_abort(message or f"ошибка на шаге {step}")
            return
        if step == 6:
            # Очистка — финальный шаг цепочки (успех или best-effort)
            if self._auto_failed:
                self._auto_finish(getattr(self, "_auto_failed_step", None))
            else:
                if not success:
                    self.append_log("[Автопрошивка] ВНИМАНИЕ: директорию "
                                    "агента удалить не удалось — выполните "
                                    "«Удалить агента» вручную")
                self._auto_finish()
            return
        if step == 3:
            # v1.77: весь шаг 3 (тихий редактор) выполняется ОДНИМ воркером
            # op 11: подготовка данных + сборка строк СП автозаполнением
            # appl + сохранение plan.xml на устройство — внутри фонового
            # потока, до возврата run(). Раньше этап A делался в GUI и для
            # сохранения запускался второй воркер из обработчика
            # finished-сигнала — он стартовал, пока первый поток ещё был
            # запущен (isRunning()==True), start_operation отвечал «Уже
            # выполняется другая операция» и цепочка зависала на шаге 2/6→3.
            if data.get("_auto_saved"):
                self._auto_rows = data.get("_auto_rows") or []
                self._auto_step += 1
                self._auto_run_step()
                return
            try:
                dialog = EditSPDialog(
                    data["modules_info"], data["plan_modules"],
                    data["firmwares"], self.get_current_config(), self,
                    quiet=True)
                dialog.autofill("apply")
                rows = [dict(r) for r in dialog.rows]
                for i, r in enumerate(rows):
                    r['path'] = dialog.path_edits[i].text().strip()
                    r['img_type'] = dialog.type_combos[i].currentData()
                del dialog
                if not any(r.get('path') and r.get('flashable', True)
                           for r in rows):
                    raise Exception("Автопрошивка: автозаполнение appl не "
                                    "выбрало ни одного модуля — "
                                    "прошивать нечего")
                self._auto_rows = rows
            except Exception as e:
                self._auto_abort(f"Ошибка тихого редактирования СП: {e}")
                return
            # Ветка больше не используется (v1.77): сохранение СП выполняется
            # тем же воркером op 11; оставлен безопасный выход — если по
            # какой-то причине '_auto_saved' не проставлен, цепочка
            # продолжает работу без зависания.
            self._auto_step += 1
            self._auto_run_step()
            return
        # Шаги 1, 2, 4, 5 — переход к следующему
        if step == 5 and success:
            # результат показан в диалоге — затем очистка
            pass
        self._auto_step += 1
        self._auto_run_step()

    def on_operation_finished(self, success, message, data):
        # v1.75: завершение любой операции отображается в оперативном логе;
        # выгрузка дампа из диалога результата — без дублирующей строки
        # («завершена» напишется один раз при возврате в диалог).
        try:
            if getattr(self, "_auto_step", 0) == 0 and not data.get("_silent"):
                op_name = next((name for oid, name in self.all_ops
                                if oid == getattr(self.worker, "op_id", None)),
                               "")
                dump_reopen = (getattr(self, "_dump_reopen_data", None)
                               is not None)
                if op_name and not (dump_reopen and success):
                    if success:
                        self.append_log(f"--- Операция: {op_name} завершена ---")
                    else:
                        self.append_log(f"--- Операция: {op_name} "
                                        f"завершена с ошибкой ---")
        except Exception:
            pass
        # v1.66: разблокировка кнопок выполняется в любом случае (finally),
        # чтобы исключение при открытии диалога не «замораживало» интерфейс.
        try:
            # v1.73: обработка шагов цепочки «Автопрошивка»
            if getattr(self, "_auto_step", 0) > 0:
                self._auto_flash_step_done(success, message, data)
                return
            self._handle_operation_result(success, message, data)
        finally:
            if getattr(self, "_auto_step", 0) == 0:
                self._set_ops_enabled(True)

    def _start_dump_from_dialog(self, dialog, modules, results):
        """v1.75: запуск операции «Выгрузить дамп» (op 7) из диалога
        «Просмотр результата». Диалог закрывается на время выгрузки —
        иначе модальный exec() блокирует главный поток и сигнал
        завершения воркера не будет обработан."""
        if getattr(self, "_ops_busy", False) or (
                self.worker is not None and self.worker.isRunning()):
            QMessageBox.warning(self, "Внимание",
                                "Уже выполняется другая операция. "
                                "Дождитесь её завершения.")
            return
        config = self.get_current_config()
        if not config['ip'] or not config['password']:
            QMessageBox.critical(self, "Ошибка", "Укажите IP-адрес и пароль!")
            return
        self._dump_reopen_data = (modules, results)
        dialog.reject()
        self.start_operation(7)

    def _handle_operation_result(self, success, message, data):
        # v1.75: после успешной выгрузки дампа из диалога «Просмотр
        # результата» — возвращаемся в тот же диалог (он открывался на
        # время операции и закрывался, чтобы не блокировать главный поток).
        reopen = getattr(self, "_dump_reopen_data", None)
        if reopen is not None and success:
            self._dump_reopen_data = None
            modules, results = reopen
            dialog = ViewResultDialog(
                modules, results, self,
                on_dump=lambda d, m=modules, r=results:
                self._start_dump_from_dialog(d, m, r))
            dialog.exec()
            return
        if reopen is not None and not success:
            # дамп не выгружен — данные больше не нужны, ошибка ниже
            self._dump_reopen_data = None

        if not success:
            QMessageBox.critical(self, "Ошибка", message)
            return
        action = data.get("action")

        # v1.77: завершение цепочки Автопрошивки (шаг 6 — очистка) пишется в
        # операционный лог ровно один раз (_auto_finish), без дублирующей
        # строки «Операция: Удалить агента завершена».
        chain_finished = getattr(self, "_auto_step", 0) > 0 and \
            getattr(self, "_auto_failed", False) and data == {}
        if not success or action is None:
            if not chain_finished:
                op_name = next((name for oid, name in self.all_ops
                                if oid == getattr(self.worker, "op_id", None)),
                               "")
                if op_name and not getattr(self, "_dump_reopen_data", None):
                    if success:
                        self.append_log(f"--- Операция: {op_name} завершена ---")
                    else:
                        self.append_log(f"--- Операция: {op_name} "
                                        f"завершена с ошибкой ---")
            return
        if action == "result":
            # v1.75: «Выгрузить дамп» перенесена в этот диалог (op 7).
            # Диалог закрывается на время выгрузки (иначе модальный exec()
            # заблокирует главный поток и воркер не сможет завершиться);
            # после успешной выгрузки он открывается повторно.
            dialog = ViewResultDialog(
                data["modules"], data["results"], self,
                on_dump=lambda d, m=data["modules"], r=data["results"]:
                self._start_dump_from_dialog(d, m, r))
            dialog.exec()
        elif action == "edit":
            # v1.76: шаг 3 цепочки Автопрошивки — данные подготовлены и СП
            # уже сохранён на устройство воркером op 11 ('_auto_saved');
            # обработка перехода к прошивке выполняется в
            # _auto_flash_step_done, диалог редактора НЕ открывается.
            if getattr(self, "_auto_step", 0) > 0 and data.get("_auto_saved"):
                return
            # v1.77: если редактирование СП было запущено сразу после
            # «Создать СП» (_pending_make_plan), открываем редактор без
            # повторного запуска операции (второй запуск давал двойные
            # строки «Запущена/завершена» и лишний цикл загрузки plan.xml).
            pending = getattr(self, "_pending_make_plan", False)
            dialog = EditSPDialog(
                data["modules_info"],
                data["plan_modules"],
                data["firmwares"],
                self.get_current_config(),
                self,
                # v1.73: тихий режим для Автопрошивки (без диалогов)
                quiet=getattr(self, "_auto_step", 0) > 0,
                # v1.75: сохранение СП на устройство пишется в операционный лог
                on_log=self.append_log
            )
            self._auto_edit_dialog = dialog
            dialog.exec()
            # v1.77: данные для редактора уже загружены воркером op 11 —
            # повторный запуск операции 9 (загрузка plan.xml ещё раз) не
            # выполняется; флаг сбрасывается, чтобы следующий «Создать СП»
            # снова предложил открыть редактор автоматически.
            if pending:
                self._pending_make_plan = False
        elif action == "module_info":
            dialog = ModuleInfoDialog(data["modules"], self)
            dialog.exec()


def _install_excepthook(window_ref):
    """Глобальный перехват необработанных исключений (v1.67).

    Исключение Python внутри Qt-слота раньше приводило к аварийному
    завершению процесса без сообщения (приложение «просто закрывалось»).
    Теперь ошибка показывается в диалоге и пишется в журнал приложения;
    для SystemExit KeyboardInterrupt не перехватываются.
    """
    def hook(exc_type, exc, tb):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            sys.__excepthook__(exc_type, exc, tb)
            return
        text = "".join(traceback.format_exception(exc_type, exc, tb)).strip()
        try:
            if window_ref[0] is not None:
                window_ref[0].append_log(f"Критическая ошибка: {text}")
                QMessageBox.critical(window_ref[0], "Критическая ошибка",
                                     text[-2000:])
        except Exception:
            pass
        sys.stderr.write(text + "\n")
    sys.excepthook = hook


def _install_app_icon(app):
    """Устанавливает иконку приложения (окно + панель задач).

    Ищет MFC_moduleUpd.ico рядом со скриптом; в собранном PyInstaller exe —
    во временной директории бандла (_MEIPASS, файл добавляется через --add-data).
    Отсутствие иконки не является ошибкой.
    """
    import os

    from PyQt6.QtGui import QIcon
    candidates = [os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "MFC_moduleUpd.ico")]
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(os.path.join(meipass, "MFC_moduleUpd.ico"))
    for path in candidates:
        if os.path.isfile(path):
            app.setWindowIcon(QIcon(path))
            return True
    return False


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    _install_app_icon(app)
    window = MainWindow()
    _win_ref = [window]
    _install_excepthook(_win_ref)
    window.show()
    sys.exit(app.exec())
