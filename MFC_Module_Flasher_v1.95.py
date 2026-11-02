"""
MFC Module Updater (IskraIO) — настольное приложение для прошивки модулей МФК.

Назначение:
Автоматизация процесса обновления прошивок модулей многофункционального
контроллера (МФК) через SSH/SFTP-агента IskraIO_Util и HTTP-бэкенд устройства.

Возможности:
Внедрение агента и файлов прошивок на устройство с контролем формата
и двумя режимами лога — кратким/подробным (операция 1);
Создание сценария прошивки MakePlan (операция 2);
Импорт/экспорт сценария plan.xml (операции 3, 4);
Запуск прошивки Update с анализом result.txt (операция 6);
Выгрузка дампа операции (операция 7);
Просмотр результата прошивки (операция 8);
Редактирование сценария прошивки (СП) с автозаполнением (операции 9, 11);
Получение информации о модулях через HTTP-бэкенд (операция 10).

Зависимости:
pip install -r requirements.txt   # PyQt6, paramiko

Запуск:
python MFC_Module_Flasher_v1.94.py

Автор: Екимов Д.А. @ 2026
Версия: 1.94
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
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QProgressBar, QPushButton,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
)

APP_VERSION = "1.94"
APP_TITLE = f"Прошивка модулей МФК версия {APP_VERSION}"
CONFIG_FILE = "mfc_flasher_config.json"

DEFAULT_CONFIG = {
    "ip": "", "password": "", "agent_dir": "", "firmware_dir": "",
    "plan_xml": "", "api_path": "/vx3/backend.fcgi",
    "format_control": True, "skip_same_version": True, "verbose_log": False,
}

STYLESHEET = """
QMainWindow { background-color: #f5f5f5; }
QWidget { color: #222222; font-family: 'Segoe UI', 'Arial', sans-serif; font-size: 14px; }
QLabel { color: #1a1a1a; }
QLineEdit, QTextEdit, QTableWidget, QComboBox {
    background-color: #ffffff; border: 1px solid #b0b0b0; border-radius: 4px;
    padding: 5px; color: #000000;
}
QTableWidget::item { padding: 5px; color: #000000; }
QHeaderView::section {
    background-color: #e0e0e0; color: #000000; padding: 5px;
    border: 1px solid #b0b0b0; font-weight: bold;
}
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
QPushButton#col1_btn_12 { background-color: #b54708; }
QPushButton#col1_btn_12:hover { background-color: #8a3606; }
QPushButton#col2_btn_13 { background-color: #ff8c00; }
QPushButton#col2_btn_13:hover { background-color: #e67300; }
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
QGroupBox {
    border: 1px solid #b0b0b0; border-radius: 5px; margin-top: 10px;
    padding-top: 15px; font-weight: bold; color: #000000;
}
QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
QProgressBar {
    border: 1px solid #b0b0b0; border-radius: 5px; text-align: center;
    background-color: #ffffff; height: 22px; color: #000000; font-weight: bold;
}
QProgressBar::chunk { background-color: #0078d7; border-radius: 4px; }
QCheckBox { spacing: 8px; color: #000000; }
QMessageBox, QDialog { background-color: #f5f5f5; color: #000000; }
QMessageBox QLabel, QDialog QLabel { color: #000000; font-weight: bold; }
QMessageBox QPushButton { background-color: #0078d7; color: white; min-width: 80px; }
"""

"""
============================================================
ВСПОМОГАТЕЛЬНЫЕ КЛАССЫ И ФУНКЦИИ
============================================================
"""
class SSHClient:
    """Обёртка для работы с SSH и SFTP."""

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
    """Клиент для работы с HTTP-бэкендом устройства."""

    _DETAIL_MARKERS = (
        "Payload: ", "Заголовки ответа: ", "Тело ответа",
        "Статус: 200", "--- ШАГ", "URL: ",
        "Актуальный SID: ", "Актуальный токен: "
    )
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

        if self.log_callback and (self.verbose or not any(m in msg for m in self._DETAIL_MARKERS)):
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
            'User-Agent': ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                           '(KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36 Edg/154.0.0.0')
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
        self._log("--- ШАГ 1: Запрос get_token ---")
        payload = {"req": "get_token", "token": 0, "params": {}, "login_name": ""}
        payload_str = json.dumps(payload, separators=(',', ':'))

        self._log(f"URL: {self.api_url}")
        self._log(f"Payload: {payload_str}")

        req = urllib.request.Request(
            self.api_url,
            data=payload_str.encode('utf-8'),
            headers=self._base_headers(),
            method='POST'
        )

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
            self.token = token_data.get("token") if isinstance(token_data, dict) else token_data
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
        if _retry_count >= 3:
            raise Exception(
                f"Превышено максимальное количество попыток обновления токена (3). "
                f"Проверьте лог {self.log_file}"
            )

        if _retry106_count >= 3:
            raise Exception(
                f"Бэкенд возвращает result=106 после 3 повторов (ожидание 10 с). "
                f"Проверьте состояние устройства, лог {self.log_file}"
            )

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

        self._log(f"--- ШАГ 2: Запрос {req_name} (Попытка {_retry_count + 1}) ---")
        self._log(f"URL: {self.api_url}")
        self._log(f"Актуальный SID: {self.sid}")
        self._log(f"Актуальный токен: {self.token}")
        self._log(f"Payload: {payload_str}")

        req = urllib.request.Request(
            self.api_url,
            data=payload_str.encode('utf-8'),
            headers=headers,
            method='POST'
        )

        try:
            response = self.opener.open(req, timeout=15)
            raw = response.read().decode('utf-8', errors='ignore')

            self._log(f"Статус: {response.status}")
            self._log(f"Тело ответа (первые 500 символов): {raw[:500]}")

            data = json.loads(raw)

            if data.get("result") == 2:
                self._log("⚠ Ошибка авторизации (result=2). Сбрасываем токен и пробуем снова...")
                self.token = None
                self.sid = None
                return self.request(req_name, params, login_name, _retry_count + 1)

            if data.get("result") == 106:
                self._log(f"⚠ Бэкенд вернул result=106. Ожидание 10 с, повтор {_retry106_count + 1}/3...")
                time.sleep(10)
                return self.request(req_name, params, login_name, _retry_count, _retry106_count + 1)

            return data
        except Exception as e:
            self._log(f"✗ Ошибка запроса {req_name}: {e}")
            raise


def normalize_img_type(value):
    v = (value or '').strip().lower()
    if v == 'appl':
        return 'apply'
    return v


def parse_plan_xml(xml_path):
    tree = ET.parse(xml_path)
    root = tree.getroot()

    if root.tag != 'Root':
        raise ValueError(f"Неверный корневой тег plan.xml: '{root.tag}' (ожидался 'Root')")

    modules = []
    for img in root.iter('Image'):
        raw_slot = (img.get('module_slot') or '').strip()
        try:
            slot = str(int(raw_slot))
        except ValueError:
            continue

        modules.append({
            'slot': slot,
            'type': img.get('module_type'),
            'path': img.get('path'),
            'img_type': normalize_img_type(img.get('type'))
        })

    return modules


def parse_result_txt(txt_content):
    results = {}
    pattern = re.compile(r'slot=(\d+)\s+"([^"]+)":\s+(.*)')

    for line in txt_content.splitlines():
        match = pattern.search(line)
        if match:
            results[match.group(1)] = match.group(3).strip()

    return results


OP_LOG_ERROR_MARKERS = ("===ERROR===", "state[Error]", "Error]")


def analyze_operation_log(log_path):
    analysis = {}

    try:
        with open(log_path, encoding='utf-8', errors='replace') as f:
            content = f.read()
    except OSError:
        return analysis

    lines = content.splitlines()

    res_pat = re.compile(r'slot=(\d+)\s+"([^"]+)":\s+(.*)')
    for line in lines:
        m = res_pat.search(line)
        if not m:
            continue

        slot = m.group(1)
        text = m.group(3).strip()

        if "Complete" in text:
            analysis[slot] = {"status": "ok", "detail": ""}
        elif text:
            analysis[slot] = {"status": "error", "detail": text}

    has_err_block = any(mark.lower() in line.lower() for line in lines for mark in OP_LOG_ERROR_MARKERS)

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

    upd_pat = re.compile(r'Update module slot=(\d+)\s+"([^"]+)":\s*(.*)')
    for line in lines:
        m = upd_pat.search(line)
        if not m:
            continue

        slot = m.group(1)
        text = m.group(3).strip()

        if has_err_block or text:
            prev = analysis.get(slot)
            if not prev or prev["status"] != "ok":
                analysis[slot] = {
                    "status": "error",
                    "detail": text or "ошибка (см. operation.log)"
                }

    return analysis


def find_latest_operation_log(agent_dir):
    if not agent_dir or not os.path.isdir(agent_dir):
        return None

    logs = sorted(glob.glob(os.path.join(agent_dir, "operation_log_*.log")))
    return logs[-1] if logs else None


def find_latest_result_copy(agent_dir):
    if not agent_dir or not os.path.isdir(agent_dir):
        return None

    copies = sorted(glob.glob(os.path.join(agent_dir, "result_*.txt")))
    return copies[-1] if copies else None


def _short_fw_ver(ver):
    v = str(ver or "").strip()
    if not v or v.upper() == "N/A":
        return "N/A"

    m = re.match(r'^R\s*(.+)$', v, re.IGNORECASE)
    if m:
        return "R" + re.sub(r'\s+', '', m.group(1))

    return v


def hide_column_if_all_na(table, col):
    if table.rowCount() == 0:
        return

    for row in range(table.rowCount()):
        item = table.item(row, col)
        text = (item.text().strip() if item else "")
        if text and text.upper() not in ("N/A", "NA"):
            return

    table.hideColumn(col)


FW_SUBDIRS = ("full", "apply", "appl", "boot")
IMG_TYPE_DISPLAY = {"apply": "appl"}


def display_img_type(value):
    return IMG_TYPE_DISPLAY.get(value, value)


def detect_fw_source(rel_path):
    if not rel_path:
        return None

    parts = [p.lower() for p in re.split(r"[\\/]+", rel_path.strip()) if p]
    for seg in parts:
        if seg in FW_SUBDIRS:
            return "apply" if seg == "appl" else seg

    return None


def allowed_img_types(source):
    if source == "apply":
        return ["apply"]
    if source == "boot":
        return ["boot"]
    return ["apply", "boot"]


def agent_work_dir(agent_path_value):
    if not agent_path_value:
        return ""

    if os.path.isdir(agent_path_value):
        return agent_path_value

    return os.path.dirname(agent_path_value) or "."


def agent_executable(agent_path_value):
    if not agent_path_value:
        return ""

    if os.path.isdir(agent_path_value):
        return os.path.join(agent_path_value, "IskraIO_Util")

    return agent_path_value


def fw_name_format(filename, parsed=None):
    base = os.path.basename((filename or '').replace('\\', '/')).lower()

    fmt = None
    for prefix in ("appl", "boot", "full"):
        if base.startswith(prefix):
            fmt = prefix
            break

    if fmt is None:
        return (
            None, False, False,
            f"Файл '{filename}' имеет некорректное имя: ожидается начало 'appl', 'boot' или 'full'"
        )

    if fmt == "full":
        return (
            "full", True, False,
            f"Файл '{filename}' имеет формат full — такой формат пока не поддерживается"
        )

    if parsed is None:
        parsed = parse_firmware_filename(os.path.basename(filename or ''))

    if parsed is None:
        short = _try_parse_short_hw_name(os.path.basename(filename or ''))
        if short is not None and short.get('module_type'):
            return (fmt, True, True, None)

    if isinstance(parsed, dict) and 'fmt_ok' in parsed:
        if parsed['fmt_ok']:
            return (fmt, True, True, None)

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
        return (
            fmt, True, False,
            f"Файл '{filename}' имеет некорректное имя: " + ", ".join(problems) +
            " (ожидаются сегменты R<маж>.<мин> или R<маж>_<мин> и дата ДДММГГ)"
        )

    return (fmt, True, True, None)


FW_STRICT_RE = re.compile(
    r"^(?P<prefix>appl|boot|full)"
    r"_(?P<marker>[a-z0-9]+)"
    r"_(?P<mtype>[a-z0-9]+)"
    r"(?:_[a-z0-9]+)*"
    r"(?:_R(?P<major>\d{1,3})[._](?P<minor>\d{1,2})"
    r"|_r(?P<rminor>\d{1,2}))"
    r"_(?P<date>\d{6})(?:_.+)?$",
    re.IGNORECASE,
)

FW_SHORT_RE = re.compile(
    r"^(?P<prefix>appl|boot|full)"
    r"_(?P<marker>[a-z0-9]+)"
    r"_(?P<mtype>[a-z0-9]+)"
    r"(?:_[a-z0-9]+)*?"
    r"(?:_r)?$",
    re.IGNORECASE,
)


def _try_parse_fw_name(name_no_ext):
    m = FW_STRICT_RE.match(name_no_ext)
    if not m:
        return None

    date_ = m.group("date")
    day, month = int(date_[0:2]), int(date_[2:4])
    if not (1 <= day <= 31 and 1 <= month <= 12):
        return None

    major = m.group("major")
    minor = m.group("minor")
    if major is None:
        major = "2"
        minor = m.group("rminor")

    return {
        "prefix": m.group("prefix").lower(),
        "marker": m.group("marker"),
        "mtype": m.group("mtype"),
        "major": major,
        "minor": minor,
        "date": date_
    }


def _try_parse_short_hw_name(filename):
    name_no_ext = os.path.splitext(filename)[0]
    m = FW_SHORT_RE.match(name_no_ext)
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

    return {
        "filename": filename,
        "fw_type": fw_type,
        "marker": marker,
        "module_type": module_type,
        "version": "",
        "date": "",
        "fmt_ok": True
    }


def parse_firmware_filename(filename):
    name_no_ext = os.path.splitext(filename)[0]
    parts = name_no_ext.split('_')

    if len(parts) < 5:
        return None

    if parts[0] not in ('full', 'appl', 'boot'):
        return None

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

        if not ver_major_raw.upper().startswith('R'):
            if ver_major_raw.lower() == 'r' and ver_minor.isdigit() and len(ver_minor) <= 2:
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
    version = f"R{major}.{ver_minor}"

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
    if not ver or ver in ('N/A', ''):
        return 'N/A'

    ver = ver.strip()
    m = re.match(r'^R\s*(.+)$', ver, re.IGNORECASE)
    if m:
        return "R" + re.sub(r'\s+', '', m.group(1))

    return ver


def _resolve_module_type(info):
    module_type = (info.get("module_type") or "").strip() or "NA"
    if module_type.upper() in ("NA", ""):
        cfg = (info.get("module_type_config") or "").strip()
        if cfg and cfg.upper() != "NA":
            module_type = cfg
    return module_type

"""
============================================================
ПОТОК ВЫПОЛНЕНИЯ ОПЕРАЦИЙ
============================================================
"""
class OperationWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str, dict)

    _VERBOSE_ONLY_MARKERS = (
        "Соответствие слот/тип:", "Проверка: тип", "Внимание: отвечающих модулей",
        "Слот", "Запись index=", "Хвостовых артефактных записей",
        "Сопоставление слот/тип:", "Строк сценария в plan.xml:",
        "Разбор plan.xml (", "Некорректные имена (без префикса", "Файлы формата full:",
        "Сценарий прошивки пуст", "Сценарий прошивки (plan.xml) пуст",
        "Прошивка не произведена", "Файлы прошивок из СП:", "plan.xml загружен с устройства",
        "Тихий режим:", "Данные для редактора подготовлены", "Тихое сохранение plan.xml",
        "Сохранение СП на устройство выполнено", "Автосохранение СП на устройство выполнено",
        "Найдено модулей с СН:", "Бэкенд не вернул модулей", "статус после остановки",
        "статус после запуска"
    )

    def __init__(self, op_id, config, quiet=False, on_log=None):
        super().__init__()
        self.op_id = op_id
        self.config = config
        self._on_log = on_log
        self.verbose_log = bool(config.get('verbose_log', False))
        self._old_versions = dict(config.get('_old_versions') or {})
        self.quiet = quiet
        self.last_report_lines = []
        self.last_result_payload = None
        self.auto_rows_out = None
        self._finished_emitted = False
        self._update_skipped = False

    def _emit_finished(self, success, message, data=None):
        if self._finished_emitted:
            return

        self._finished_emitted = True
        payload = dict(data) if data else {}
        payload['_op_id'] = self.op_id
        self.finished_signal.emit(success, message, payload)

    def _is_verbose_only(self, msg):
        if any(msg.startswith(m) or m in msg for m in self._VERBOSE_ONLY_MARKERS if m != "Слот"):
            return True

        if msg.startswith("Слот") and (": тип модуля не определён" in msg or ": резерв" in msg):
            return True

        if msg.startswith("Слот") and (": ПРОШИТ УСПЕШНО" in msg or ": пропущен —" in msg):
            return False

        return False

    def log(self, msg):
        if not self.verbose_log and self._is_verbose_only(msg):
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_signal.emit(f"[{timestamp}] {msg}")

    @staticmethod
    def log_via(callback, msg):
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
                self._op11_prepare_edit_plan()
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
                self._op13_auto_flash_tail(ssh)
            elif self.op_id == 7:
                self._op7_download_dump(ssh)
            elif self.op_id == 8:
                self._op8_view_result(ssh)
            elif self.op_id == 12:
                ssh.close()
                ssh = None
                self._cleanup_remote_agent()
            elif self.op_id == 13:
                raise Exception("Некорректный запуск операции Автопрошивки (op 13).")

            if ssh is not None:
                ssh.close()
                ssh = None

            if getattr(self, "_finished_emitted", False):
                return

            self._emit_finished(True, "Операция завершена успешно")
        except Exception as e:
            self.log(f"Критическая ошибка: {e!s}")
            self._emit_finished(False, f"Ошибка: {e!s}")
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
        if not rows:
            self.log("Сценарий прошивки пуст — проверка файлов пропускается")
            return []

        fw_by_rel = {}
        by_name = {}

        for fw in self._scan_firmware_dir():
            fw_by_rel[fw['rel_path']] = fw
            by_name.setdefault(fw['filename'], fw)

        device_names = self._remote_image_names(ssh)
        uploaded = 0
        present = 0
        missing = []

        for mod in rows:
            path = (mod.get('path') or '').replace('\\', '/')
            rel = re.sub(r'^images/', '', path)
            remote = f"/home/user/fw_update/images/{rel}"

            if ssh.sftp_stat(remote):
                present += 1
                continue

            fname = os.path.basename(path)
            fw = fw_by_rel.get(rel) or by_name.get(fname)

            if fw is None:
                fw = next((f for f in fw_by_rel.values() if f['filename'] == fname), None)

            if fw is None:
                if fname in device_names:
                    present += 1
                    continue
                missing.append(fname)
                continue

            _fmt, _ok, _supported, warning = fw_name_format(fw['filename'], parsed=fw)
            if not _supported:
                if bool(self.config.get('format_control', True)):
                    raise Exception(
                        f"Файл прошивки '{fw['filename']}' из сценария не прошёл контроль формата "
                        f"({warning or 'формат недопустим'}). Отключите опцию «Контроль формата прошивок», "
                        f"чтобы разрешить загрузку"
                    )
                if warning:
                    self.log(f"Предупреждение: {warning}")

            sub = os.path.dirname(fw['rel_path'])
            ssh.exec_command(f"mkdir -p /home/user/fw_update/images/{sub}" if sub else "true")
            ssh.sftp_put(fw['local_path'], remote)
            uploaded += 1

        if missing:
            raise Exception(
                f"Файлы прошивок из сценария не найдены ни на устройстве, "
                f"ни в директории '{self.config.get('firmware_dir', '')}': " + ", ".join(sorted(set(missing)))
            )

        self.log(f"Файлы прошивок из СП: на устройстве {present}, дозагружено {uploaded}")
        return [m['slot'] for m in rows]

    def _remote_image_names(self, ssh):
        names = set()

        try:
            entries = ssh.exec_command("find /home/user/fw_update/images -type f 2>/dev/null")[0]
            for line in entries.splitlines():
                line = line.strip()
                if line:
                    names.add(os.path.basename(line))
        except Exception:
            pass

        return names

    def _upload_selected_firmwares(self, ssh):
        tmp_path = None

        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
                tmp_path = tmp.name

            ssh.sftp_get("/home/user/fw_update/plan.xml", tmp_path)
            plan_modules = parse_plan_xml(tmp_path)
            self._last_plan_modules = plan_modules
            self.log(f"plan.xml загружен с устройства для проверки файлов (строк сценария: {len(plan_modules)})")
        except Exception as e:
            raise Exception(
                f"Не удалось получить plan.xml с устройства для проверки файлов прошивок: {e}. "
                f"Сначала выполните 'Создать СП' или сохраните сценарий через 'Редактировать СП'."
            ) from e
        finally:
            if tmp_path:
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

        if not plan_modules:
            self.log("Сценарий прошивки (plan.xml) пуст — проверка файлов пропускается")
            return []

        fw_by_rel = {}
        by_name = {}

        for fw in self._scan_firmware_dir():
            fw_by_rel[fw['rel_path']] = fw
            by_name.setdefault(fw['filename'], fw)

        device_names = self._remote_image_names(ssh)
        uploaded = 0
        present = 0
        missing = []

        for mod in plan_modules:
            path = (mod.get('path') or '').replace('\\', '/')
            rel = re.sub(r'^images/', '', path)
            remote = f"/home/user/fw_update/images/{rel}"

            if ssh.sftp_stat(remote):
                present += 1
                continue

            fname = os.path.basename(path)
            fw = fw_by_rel.get(rel) or by_name.get(fname)

            if fw is None:
                fw = next((f for f in fw_by_rel.values() if f['filename'] == fname), None)

            if fw is None:
                if fname in device_names:
                    present += 1
                    continue
                missing.append(fname)
                continue

            _fmt, _ok, _supported, warning = fw_name_format(fw['filename'], parsed=fw)
            if not _supported:
                if bool(self.config.get('format_control', True)):
                    raise Exception(
                        f"Файл прошивки '{fw['filename']}' из сценария не прошёл контроль формата "
                        f"({warning or 'формат недопустим'}). Отключите опцию «Контроль формата прошивок», "
                        f"чтобы разрешить загрузку"
                    )
                if warning:
                    self.log(f"Предупреждение: {warning}")

            sub = os.path.dirname(fw['rel_path'])
            ssh.exec_command(f"mkdir -p /home/user/fw_update/images/{sub}" if sub else "true")
            ssh.sftp_put(fw['local_path'], remote)
            uploaded += 1

        if missing:
            raise Exception(
                "Файлы прошивок из plan.xml не найдены ни на устройстве, ни в локальной директории "
                f"'{self.config.get('firmware_dir', '')}': " + ", ".join(sorted(set(missing)))
            )

        self.log(f"Файлы прошивок из СП: на устройстве {present}, дозагружено {uploaded}")
        return [m['slot'] for m in plan_modules]

    def _remote_get_text(self, ssh, remote_path):
        stdin, stdout, stderr = ssh.client.exec_command(f"cat {remote_path}")
        content = stdout.read().decode('utf-8', errors='ignore')

        if not content.strip():
            self.log(f"Файл {remote_path} на устройстве отсутствует или пуст — "
                     "возможно, операция ещё не выполнялась")

        return content

    def _ensure_remote_file(self, ssh, remote_path, what):
        if ssh.sftp_stat(remote_path):
            return True

        self.log(f"{what} ({remote_path}) ещё не создан на устройстве — "
                 "сначала выполните соответствующую операцию "
                 "(Внедрить агента и прошивки / Создать СП / Прошивка)")
        return False

    def _stop_services(self, ssh):
        self.log("Остановка PrjA.service...")
        ssh.exec_command("systemctl stop PrjA.service")
        status = self._check_service_status(ssh, 'PrjA.service')
        if self.verbose_log:
            self.log(f"PrjA.service статус после остановки: {status}")

        QThread.msleep(1000)

        self.log("Остановка PrjA-tele.service...")
        ssh.exec_command("systemctl stop PrjA-tele.service")
        status = self._check_service_status(ssh, 'PrjA-tele.service')
        if self.verbose_log:
            self.log(f"PrjA-tele.service статус после остановки: {status}")

        QThread.msleep(1000)

    def _start_services(self, ssh):
        self.log("Запуск PrjA-tele.service...")
        ssh.exec_command("systemctl start PrjA-tele.service")
        status = self._check_service_status(ssh, 'PrjA-tele.service')
        if self.verbose_log:
            self.log(f"PrjA-tele.service статус после запуска: {status}")

        QThread.msleep(1000)

        self.log("Запуск PrjA.service...")
        ssh.exec_command("systemctl start PrjA.service")
        status = self._check_service_status(ssh, 'PrjA.service')
        if self.verbose_log:
            self.log(f"PrjA.service статус после запуска: {status}")

    @staticmethod
    def _canon_type(t):
        t = (t or "").strip().upper()
        if t == "PSU":
            t = "POWER_UNIT"
        return t

    @staticmethod
    def _sn_of(mod):
        for key in ("serial_num", "serial_number"):
            val = str((mod or {}).get(key) or "").strip()
            if val and val.upper() not in ("NA", "N/A", "NONE", "0"):
                return val
        return ""

    def _fetch_module_info(self):
        """Запрос IskraIOGetAll и построение списка установленных модулей."""

        max_attempts = 3
        retry_delay_ms = 10000

        module_arr = []
        module_info_arr = []
        crate_slot_count = None

        client = BackendClient(self.config['ip'], log_callback=self.log, verbose=self.verbose_log)

        for attempt in range(1, max_attempts + 1):
            self.log("Получение информации о модулях через HTTP...")

            try:
                data = client.request("IskraIOGetAll")
            except Exception as e:
                if attempt >= max_attempts:
                    raise
                self.log(f"Бэкенд недоступен: {e}. Повтор через "
                         f"{retry_delay_ms // 1000} с (попытка {attempt + 1} из {max_attempts})...")
                QThread.msleep(retry_delay_ms)
                continue

            if data.get("result") != 0:
                raise Exception(f"Бэкенд вернул ошибку: result={data.get('result')}")

            resp_data = data.get("data") or {}
            module_arr = resp_data.get("module_arr") or []
            module_info_arr = resp_data.get("module_info_arr") or []

            try:
                crate_slot_count = int(resp_data.get("crate_slot_count"))
            except (TypeError, ValueError):
                crate_slot_count = None

            mod_by_slot_probe = {}
            for _mod in module_arr:
                if not isinstance(_mod, dict):
                    continue

                try:
                    _s = int(_mod.get("slot_num"))
                except (TypeError, ValueError):
                    continue

                _prev = mod_by_slot_probe.get(_s)
                if _prev is None or (not self._sn_of(_prev) and self._sn_of(_mod)):
                    mod_by_slot_probe[_s] = _mod

            has_valid_modules = any(self._sn_of(m) for m in mod_by_slot_probe.values())

            if has_valid_modules or attempt >= max_attempts:
                if not has_valid_modules:
                    self.log("Внимание: бэкенд даже после повторов не вернул модули "
                             "с серийными номерами и корректными slot_num — работаем с полученными данными")
                else:
                    self.log(f"Найдено модулей с СН: {len(mod_by_slot_probe)}")
                break

            self.log(f"Бэкенд не вернул модулей с СН и корректными slot_num "
                     f"(вероятно, сервисы ещё не опросили устройства по CAN). "
                     f"Повтор через {retry_delay_ms // 1000} с (попытка {attempt + 1} из {max_attempts})...")
            QThread.msleep(retry_delay_ms)

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

        entries = [info for info in module_info_arr if isinstance(info, dict)]

        def _parse_idx(info):
            raw = info.get("index")
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                return None

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
            end, p = 0, None

            for pos, idx in enumerate(parsed_idx):
                if idx is None:
                    continue

                if crate_slot_count is not None and idx > crate_slot_count:
                    break

                if idx == 0:
                    if p is not None:
                        break
                    end = pos + 1
                    continue

                if p is not None and idx <= p:
                    break

                p = idx
                end = pos + 1

            return end

        head_end = _head_len()

        type_by_slot = {}
        reserved_slots = set()

        if positional:
            self.log("Индексы module_info_arr неубедительны — "
                     "сопоставление слот/тип построено по порядку записей в ответе")

            for rank, info in enumerate(entries):
                type_by_slot[rank + 1] = _resolve_module_type(info)
        else:
            tail_skipped = len(entries) - head_end
            if tail_skipped:
                self.log(f"Хвостовых артефактных записей module_info_arr проигнорировано: "
                         f"{tail_skipped} (голова: {head_end} записей)")

            zero_skipped = False

            for pos in range(head_end):
                info = entries[pos]
                idx = parsed_idx[pos]

                if idx is None:
                    continue

                if idx == 0:
                    if not _known_type(info):
                        zero_skipped = True
                        continue

                sc = _slot_count_of(info)
                stype = _resolve_module_type(info)
                newt = self._canon_type(stype)
                slot = idx

                if crate_slot_count is not None and slot > crate_slot_count:
                    break

                known = self._canon_type(type_by_slot.get(slot, ""))
                if not (known not in ("", "NA") and newt in ("", "NA")):
                    type_by_slot[slot] = stype

                if sc > 1:
                    for inner in range(slot + 1, slot + sc):
                        if crate_slot_count is not None and inner > crate_slot_count:
                            continue

                        reserved_slots.add(inner)
                        cur = self._canon_type(type_by_slot.get(inner, ""))
                        if cur in ("", "NA"):
                            type_by_slot[inner] = stype

            if zero_skipped:
                self.log("Запись index=0 (NA) в module_info_arr распознана как артефакт бэкенда и пропущена")

            self.log("Сопоставление слот/тип: slot = index (1-базируемый номер слота из module_info_arr)")

        self.log(f"Слотов креста: {crate_slot_count if crate_slot_count is not None else 'н/д'}, "
                 f"записей module_info_arr: {len(module_info_arr)}, записей module_arr: {len(module_arr)}")

        inferred = 0
        for slot, mod in mod_by_slot.items():
            known = self._canon_type(type_by_slot.get(slot, ""))
            if known not in ("", "NA"):
                continue

            mtype = (
                self._canon_type(mod.get("module_type"))
                or self._canon_type(mod.get("type"))
                or self._canon_type(mod.get("model"))
            )

            if mtype and mtype != "NA":
                type_by_slot[slot] = mtype
                inferred += 1
                self.log(f"Слот {slot}: тип '{mtype}' доопределён по ответу модуля (конфигурация креста — NA)")

        if inferred:
            self.log(f"Типов, доопределённых по module_arr: {inferred}")

        mismatch_serial_na = [
            slot for slot, mod in sorted(mod_by_slot.items())
            if self._sn_of(mod) and slot not in reserved_slots
            and self._canon_type(type_by_slot.get(slot, "")) in ("", "NA")
        ]

        if mismatch_serial_na:
            self.log(f"Внимание: {len(mismatch_serial_na)} отвечающих модулей стоят на слотах с типом NA "
                     f"(слоты: {', '.join(map(str, mismatch_serial_na))}) — проверьте соответствие слотов")

        if mod_by_slot:
            silent_types = {}

            for slot, t in type_by_slot.items():
                ct = self._canon_type(t)
                if ct in ("", "NA") or slot in mod_by_slot:
                    continue
                silent_types.setdefault(ct, []).append(slot)

            for ct, slots in sorted(silent_types.items()):
                self.log(f"Проверка: тип '{ct}' в конфигурации креста (слоты {', '.join(map(str, slots))}), "
                         "но модули такого типа не отвечают")

        max_slot = crate_slot_count
        if max_slot is None:
            max_slot = max([*type_by_slot.keys(), *mod_by_slot.keys()], default=len(entries))

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

            row = {
                "slot_num": str(slot),
                "module_type": module_type,
                "reserved": reserved,
                "serial_num": serial_num,
                "manufacture_date": mod.get("manufacture_date") or "N/A",
                "hardware_version": mod.get("hardware_version") or "N/A",
                "firmware_version": mod.get("firmware_version") or "N/A",
                "source": source,
                "flashable": serial_num != "N/A" and not reserved,
            }

            if crate_slot_count is not None:
                row["_crate_slots"] = crate_slot_count

            result.append(row)

        for r in result:
            if self._canon_type(r["module_type"]) in ("", "NA"):
                self.log(f"Слот {r['slot_num']}: тип модуля не определён (NA)")

        return result

    def _scan_firmware_dir(self):
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
                    if filename.lower().endswith(".bin"):
                        self.log(f"Предупреждение: {warning}")
                    continue

                parsed = parse_firmware_filename(filename)

                if parsed is None:
                    parts = os.path.splitext(filename)[0].split("_")
                    module_type = parts[2].upper() if len(parts) > 2 else "N/A"
                    if module_type == "PSU":
                        module_type = "POWER_UNIT"

                    ver = "N/A"
                    for p_ in parts[3:]:
                        mv = re.match(r"^R(\d+)[._](\d{1,2})$", p_, re.I)
                        if not mv:
                            mv = re.match(r"^R(\d+)(\d{1,2})$", p_, re.I)

                        if mv:
                            ver = f"R{mv.group(1)}.{mv.group(2)}"
                            break

                        if re.match(r"^R\d+$", p_, re.I):
                            idx = parts.index(p_)
                            if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                                ver = f"R{p_[1:]}.{parts[idx + 1]}"
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

                _fmt, _ok, _supported, _warn = fw_name_format(filename, parsed=parsed)
                parsed["fmt_ok"] = bool(_supported)

                if not _supported and _warn:
                    self.log(f"Предупреждение: {_warn}")

                parsed["source"] = detect_fw_source(subdir) or detect_fw_source(filename) or (
                    "full" if fmt == "full" else ("boot" if fmt == "boot" else "apply")
                )
                parsed["rel_path"] = f"{subdir}/{filename}" if subdir else filename

                firmwares.append(parsed)

        return firmwares

    def _op10_get_module_info(self):
        modules_data = self._fetch_module_info()
        MainWindow.cache_old_versions(self, modules_data)

        self.progress_signal.emit(100)

        summary = ", ".join(f"{m['slot_num']}:{m['module_type']}" for m in modules_data)
        self.log(f"Соответствие слот/тип: {summary}")
        self.log(f"Найдено модулей: {len(modules_data)}")

        self._finished_emitted = True
        self.finished_signal.emit(True, "Информация получена", {"modules": modules_data, "action": "module_info"})

    def _op11_prepare_edit_plan(self):
        modules_info = self._fetch_module_info()
        MainWindow.cache_old_versions(self, modules_info)

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
                    self.log("План прошивки пуст — открываю редактор без строк СП")
                    plan_modules = []

                self.log(f"Строк сценария в plan.xml: {len(plan_modules)}")
                self._log_plan_skipped(tmp_path, plan_modules)
            except Exception as e:
                raise Exception(f"Не удалось загрузить plan.xml: {e}") from e
            finally:
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
            self.log("Тихий режим: plan.xml не выгружается — сценарий будет собран автозаполнением")

        self.progress_signal.emit(100)

        if self.op_id == 11 and self.config.get('_auto_after_prepare') and self.quiet:
            rows = self._auto_build_rows(modules_info, plan_modules, firmwares)
            selected = self._op13_quiet_save(rows=rows)

            self._emit_finished(True, "СП сохранён (тихий режим)", {
                "_auto_saved": True,
                "_auto_rows": selected or [],
                "_auto_rows_cfg": selected or [],
            })
            return

        self.log(f"Данные для редактора подготовлены. Модулей: {len(modules_info)}, прошивок: {len(firmwares)}")

        self._finished_emitted = True
        self.finished_signal.emit(True, "Данные получены", {
            "modules_info": modules_info,
            "plan_modules": plan_modules,
            "firmwares": firmwares,
            "action": "edit"
        })

    def _log_plan_skipped(self, xml_path, parsed_modules):
        try:
            root = ET.parse(xml_path).getroot()
            total = len(list(root.iter('Image')))
        except Exception:
            return

        skipped = total - len(parsed_modules)
        if skipped > 0:
            self.log(f"ВНИМАНИЕ: пропущено записей plan.xml с некорректным module_slot: {skipped} (из {total})")

    def _cleanup_remote_agent(self):
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
                f"В директории '{self.config['firmware_dir']}' не найдено файлов прошивок "
                "(ожидаются имена с префиксом appl_/boot_/full_)"
            )

        fc_on = bool(self.config.get('format_control', True))
        all_count = len(firmwares)

        self.log(f"Найдено файлов прошивок в директории: {all_count}"
                 + (" (контроль формата включен)" if fc_on else " (контроль формата отключен)"))

        bad_names = []
        full_names = []
        kept = []

        for fw in firmwares:
            fmt, ok, supported, warning = fw_name_format(fw['filename'], parsed=fw)

            if fmt == 'full':
                full_names.append(fw['filename'])
            elif not supported:
                bad_names.append(fw['filename'])

            if fc_on and not supported:
                continue

            kept.append(fw)

        skipped = len(firmwares) - len(kept)

        if bad_names or full_names:
            parts = []

            if bad_names:
                parts.append(f"некорректных имён: {len(bad_names)}")
            if full_names:
                parts.append(f"формат full (не поддерживается): {len(full_names)}")

            detail = "; ".join(parts)

            if fc_on:
                self.log(f"ВНИМАНИЕ: файлов с проблемами формата — {detail}. "
                         f"Контроль формата ВКЛЮЧЕН: они НЕ загружаются на устройство (пропущено: {skipped})")
            else:
                self.log(f"ВНИМАНИЕ: файлов с проблемами формата — {detail}. "
                         f"Контроль формата ОТКЛЮЧЕН: загрузка на устройство будет выполнена")

            if self.verbose_log:
                if bad_names:
                    self.log("Некорректные имена: " + ", ".join(bad_names))
                if full_names:
                    self.log("Файлы формата full: " + ", ".join(full_names))

        if self.verbose_log:
            self.log("Загружаются прошивки: " + ", ".join(fw['filename'] for fw in kept))

        firmwares = kept
        total = len(firmwares)

        if total == 0:
            raise Exception(
                "После контроля формата не осталось допустимых файлов прошивок для загрузки "
                "(отключите опцию «Контроль формата прошивок», если загрузка таких файлов необходима)"
            )

        loaded = 0
        for i, fw in enumerate(firmwares):
            ssh.exec_command("mkdir -p /home/user/fw_update/images/" + os.path.dirname(fw["rel_path"]).replace("\\", "/"))
            ssh.sftp_put(fw["local_path"], f"/home/user/fw_update/images/{fw['rel_path']}")
            loaded += 1
            self.progress_signal.emit(int((i + 1) / total * 100))

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

            if self.verbose_log:
                self.log(f"MakePlan stdout: {out}")

            self.log("MakePlan завершён")
        except Exception as e:
            self.log(f"Ошибка во время MakePlan: {e}")
            raise
        finally:
            self._start_services(ssh)
            self.log("Ожидание 25 сек после запуска сервисов...")
            QThread.msleep(25000)
            self.progress_signal.emit(100)
            self.log("Операция создания СП завершена")

    def _op3_import_plan(self, ssh):
        local_plan = self.config.get('plan_xml', '')

        if not local_plan or not os.path.isfile(local_plan):
            self.log(f"Файл сценария прошивки ещё не создан (путь: '{local_plan or 'не задан'}') — "
                     "сначала выполните 'Создать СП' или 'Редактировать СП'")
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
        if not self._ensure_remote_file(ssh, "/home/user/fw_update/plan.xml", "Сценарий прошивки (plan.xml)"):
            return

        self.log("Выгрузка plan.xml...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_path = os.path.join(agent_work_dir(self.config['agent_dir']), f"plan_export_{timestamp}.xml")

        ssh.sftp_get("/home/user/fw_update/plan.xml", local_path)

        self.progress_signal.emit(100)
        self.log(f"Сценарий выгружен в: {local_path}")

    def _op6_update(self, ssh, plan_rows=None):
        self.log("Проверка наличия агента и файлов прошивок на устройстве...")

        if not ssh.sftp_stat("/home/user/fw_update/IskraIO_Util"):
            raise Exception("Агент IskraIO_Util отсутствует. Сначала выполните 'Внедрить агента и прошивки'.")

        if plan_rows is not None:
            plan_slots = self._upload_rows_firmwares(ssh, plan_rows)
        else:
            plan_slots = self._upload_selected_firmwares(ssh)

        if not plan_slots:
            self.log("Прошивка не произведена: нет подходящих модулей для прошивки")
            self._update_skipped = True
            return

        remote_images = ssh.sftp_listdir("/home/user/fw_update/images")
        if not remote_images:
            raise Exception(
                "Директория /home/user/fw_update/images/ пуста. "
                "Сначала выполните 'Внедрить агента и прошивки'."
            )

        self.log(f"Найдено файлов прошивок на устройстве: {len(remote_images)}")

        if bool(self.config.get('format_control', True)):
            if plan_rows is not None:
                plan_modules = plan_rows
            elif getattr(self, "_last_plan_modules", None) is not None:
                plan_modules = self._last_plan_modules
            elif self.config.get('plan_xml') and os.path.isfile(self.config['plan_xml']):
                plan_modules = parse_plan_xml(self.config['plan_xml'])
            else:
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

            bad_types = [
                m for m in plan_modules
                if normalize_img_type(m.get('img_type')) not in ('apply', 'boot')
            ]

            if bad_types:
                raise Exception(
                    "В сценарии прошивки есть недопустимые типы образов (прошивается только appl/boot): " +
                    ", ".join(f"слот {m['slot']} ({m.get('img_type')})" for m in bad_types) +
                    ". Отредактируйте СП или отключите «Контроль формата прошивок»."
                )

        try:
            self._stop_services(ssh)

            if not getattr(self, "_old_versions", None):
                self.log("Версии до прошивки будут взяты из последнего успешного запроса информации о модулях")

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

            update_finished_ts = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

            try:
                ts_cp = datetime.now().strftime("%Y%m%d_%H%M%S")
                local_result = os.path.join(agent_work_dir(self.config['agent_dir']), f"result_{ts_cp}.txt")

                with open(local_result, "w", encoding="utf-8") as f_res:
                    f_res.write(result_content)

                self.log(f"Копия result.txt сохранена локально: {local_result}")
            except OSError as e_cp:
                self.log(f"Не удалось сохранить локальную копию result.txt: {e_cp}")

            ok_slots = [s for s, st in results.items() if "Complete" in st]
            err_slots = {s: st for s, st in results.items() if "Complete" not in st}

            fw_names_by_slot = {}

            try:
                src_rows = self._last_plan_modules or self.config.get('_auto_rows') or []

                for m in (src_rows or []):
                    p_ = (m.get('path') or '')
                    if p_:
                        fw_names_by_slot[str(m.get('slot'))] = os.path.basename(p_.replace('\\', '/'))
            except Exception:
                fw_names_by_slot = {}

            old_versions = (
                getattr(self, "_old_versions", None)
                or getattr(MainWindow, "_old_versions_cache", None)
                or {}
            )

            for slot, status in sorted(results.items(), key=lambda x: int(x[0])):
                fname = fw_names_by_slot.get(slot, "")
                parsed_fw = parse_firmware_filename(fname) if fname else None
                to_ver = ((parsed_fw or {}).get('version') or "N/A")
                from_ver = old_versions.get(slot) or "N/A"

                if "Complete" in status:
                    self.log(f"Слот {slot}: ПРОШИТ УСПЕШНО (версия {_short_fw_ver(from_ver)} → {_short_fw_ver(to_ver)})")
                else:
                    self.log(f"Слот {slot}: ОШИБКА ПРОШИВКИ - {status}")

            dialog_modules = []

            for mod_slot in plan_slots:
                mrow = next((m for m in (self._last_plan_modules or []) if str(m.get('slot')) == str(mod_slot)), None)

                dialog_modules.append({
                    "slot": str(mod_slot),
                    "type": (mrow or {}).get('module_type', 'N/A'),
                    "path": (mrow or {}).get('path', ''),
                    "img_type": (mrow or {}).get('img_type', 'apply'),
                })

            upd_versions = {}

            for s in map(str, plan_slots):
                to_v = (parse_firmware_filename(fw_names_by_slot.get(s, "")) or {}).get('version')
                upd_versions[s] = (old_versions.get(s) or "N/A", to_v or "N/A")

            summary = f"Итог result.txt: успешно {len(ok_slots)}"

            if err_slots:
                summary += (
                    ", с ошибками " + str(len(err_slots)) + " (слоты: " +
                    ", ".join(sorted(err_slots, key=int)) + ")"
                )

            self.log(summary)

            try:
                op_analysis = analyze_operation_log(local_log)

                for slot in sorted(op_analysis, key=int):
                    st = op_analysis[slot]

                    if st["status"] == "ok":
                        continue

                    if st["status"] == "error":
                        self.log(f"operation.log, слот {slot}: ОШИБКА - {st.get('detail') or 'ошибка (см. operation.log)'}")
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

        self._update_finish_payload = {
            "modules": dialog_modules,
            "results": results,
            "versions": upd_versions,
            "flash_dt": update_finished_ts,
        }

    def _op7_download_dump(self, ssh):
        if not self._ensure_remote_file(ssh, "/home/user/fw_update/io_can_box2.csv", "Дамп операции (io_can_box2.csv)"):
            return

        self.log("Выгрузка дампа операции...")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_dump = os.path.join(agent_work_dir(self.config['agent_dir']), f"io_can_box2_{timestamp}.csv")

        ssh.sftp_get("/home/user/fw_update/io_can_box2.csv", local_dump)

        self.progress_signal.emit(100)
        self.log(f"Дамп выгружен в: {local_dump}")

    def _op8_view_result(self, ssh):
        self.log("Чтение данных для анализа результата...")

        flash_dt = ""

        try:
            out_dt, _ = ssh.exec_command("date -r /home/user/fw_update/result.txt '+%d.%m.%Y %H:%M:%S'")
            if out_dt and "No such file" not in out_dt:
                flash_dt = out_dt.strip()
        except Exception:
            flash_dt = ""

        if not flash_dt:
            latest_local = find_latest_result_copy(agent_work_dir(self.config.get('agent_dir', '')))
            if latest_local:
                flash_dt = datetime.fromtimestamp(os.path.getmtime(latest_local)).strftime("%d.%m.%Y %H:%M:%S")

        if not self._ensure_remote_file(ssh, "/home/user/fw_update/plan.xml", "Сценарий прошивки (plan.xml)"):
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
                self.log(f"operation.log, слот {slot}: ОШИБКА - {st.get('detail') or 'см. operation.log'}")

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

        versions = {}
        old_cache = MainWindow._old_versions_cache or {}

        for mod in modules:
            slot = str(mod.get("slot"))
            to_ver = parse_firmware_filename(os.path.basename(mod.get("path", "") or "")) or {}
            versions[slot] = (old_cache.get(slot) or "N/A", to_ver.get("version") or "N/A")

        self._emit_finished(True, "Просмотр результата", {
            "modules": modules,
            "results": results,
            "action": "result",
            "flash_dt": flash_dt,
            "versions": versions
        })

    def _op9_edit_plan(self, ssh):
        self._op11_prepare_edit_plan()

    def _auto_build_rows(self, modules_info, plan_modules, firmwares):
        """Сборка строк СП тихим автозаполнением appl (без GUI)."""

        fw_by_type = {}

        for fw in firmwares or []:
            mt = (fw.get("module_type") or "").upper()
            if mt:
                fw_by_type.setdefault(mt, []).append(fw)

        plan_by_slot = {}

        for m in plan_modules or []:
            try:
                plan_by_slot[str(int(str(m.get('slot', '')).strip()))] = m
            except (TypeError, ValueError):
                continue

        def ver_key(fw):
            v = fw.get('version', '0') or '0'
            m = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', v)

            if m:
                return tuple(int(x or 0) for x in m.groups())

            return (0, 0, 0)

        skip_same = bool(self.config.get('skip_same_version', True))
        rows = []

        for info in modules_info:
            slot = str(info['slot_num'])
            plan = plan_by_slot.get(slot, {})
            flashable = info.get('flashable', info.get('serial_num', 'N/A') != 'N/A')

            row = {
                "slot": info['slot_num'],
                "module_type": info.get('module_type', 'NA'),
                "device_fw_version": info.get('firmware_version', 'N/A'),
                "path": plan.get('path', ''),
                "img_type": normalize_img_type(plan.get('img_type')) or 'apply',
                "local_fw": None,
                "flashable": flashable,
                "unflash_reason": "",
            }

            if not flashable:
                row['path'] = ''
                rows.append(row)
                continue

            mt = str(row['module_type']).upper()
            candidates = [fw for fw in fw_by_type.get(mt, []) if self._fw_row_matches(fw, 'apply')]

            if candidates:
                best = max(candidates, key=ver_key)
                dev_ver = normalize_fw_version(row.get('device_fw_version'))
                loc_ver = normalize_fw_version(best.get('version'))

                if skip_same and dev_ver != 'N/A' and loc_ver != 'N/A' and dev_ver == loc_ver:
                    self.log(f"Слот {slot}: пропущен — версия на модуле совпадает с версией СП ({dev_ver})")
                else:
                    rel_path = f"images/{best.get('rel_path', best['filename'])}"
                    row['path'] = rel_path
                    row['local_fw'] = best
                    row['source'] = best.get('source') or detect_fw_source(rel_path)
                    row['img_type'] = 'apply'

            rows.append(row)

        return rows

    @staticmethod
    def _fw_row_matches(fw, want_type):
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

        fw_type = (fw.get('fw_type') or '').lower()

        if fw_type in ('apply', 'appl'):
            return want_type == 'apply'
        if fw_type == 'boot':
            return want_type == 'boot'

        return False

    def _op13_quiet_save(self, ssh=None, rows=None):
        if rows is None:
            rows = self.config.get('_auto_rows') or self.config.get('_auto_built_rows') or []

        selected = [r for r in rows if r.get('path')]

        if not selected:
            self.log("Прошивка не произведена: нет подходящих модулей для прошивки (сохраняется пустой план)")

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

            self.log(f"Тихое сохранение plan.xml (строк сценария: {len(selected)})...")
            ssh.sftp_put(tmp_path, "/home/user/fw_update/plan.xml")
            self.log(f"Сохранение СП на устройство выполнено (/home/user/fw_update/plan.xml, строк: {len(selected)})")
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
        self._last_plan_modules = selected

        return selected

    def _op13_auto_flash_tail(self, ssh):
        if getattr(self, "_update_skipped", False):
            self._emit_finished(True, "Прошивка не произведена: нет подходящих модулей для прошивки", {
                "action": "result",
                "modules": [],
                "results": {},
                "versions": {},
                "flash_dt": ""
            })
            return

        payload = getattr(self, "_update_finish_payload", None) or {}

        data = {
            "action": "result",
            "flash_dt": "",
            "versions": {},
            "modules": [],
            "results": {}
        }
        data.update(payload)

        self._emit_finished(True, "Прошивка выполнена", data)

    @staticmethod
    def _safe_remove(path):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

"""
============================================================
ДИАЛОГИ
============================================================
"""
class ModuleInfoDialog(QDialog):
    def __init__(self, modules_data, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Информация о модулях")
        self.resize(1000, 550)

        layout = QVBoxLayout(self)

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Номер слота", "Тип модуля", "Версия прошивки",
            "Серийный номер", "Дата производства", "Версия оборудования"
        ])
        table.setRowCount(len(modules_data))

        for i, mod in enumerate(modules_data):
            table.setItem(i, 0, QTableWidgetItem(mod['slot_num']))
            table.setItem(i, 1, QTableWidgetItem(mod.get('module_type', 'N/A')))
            table.setItem(i, 2, QTableWidgetItem(_short_fw_ver(mod['firmware_version'])))

            serial_item = QTableWidgetItem(mod['serial_num'])

            if not mod.get('flashable', True):
                mtype = (mod.get('module_type') or '').strip().upper()

                if mod.get("reserved"):
                    reason = "резерв"
                elif mtype in ("", "NA"):
                    reason = "слот пуст"
                else:
                    reason = "модуль отсутствует"

                serial_item.setText(reason)
                serial_item.setForeground(QColor("#b30000"))

            table.setItem(i, 3, serial_item)
            table.setItem(i, 4, QTableWidgetItem(mod['manufacture_date']))
            table.setItem(i, 5, QTableWidgetItem(mod['hardware_version']))

        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hide_column_if_all_na(table, 5)

        header = table.horizontalHeader()
        for col in range(6):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)

        table.resizeRowsToContents()
        layout.addWidget(table)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        for btn in btn_box.buttons():
            btn.setObjectName("dialog_btn_ok")

        btn_box.accepted.connect(self.accept)
        layout.addWidget(btn_box)


class ViewResultDialog(QDialog):
    def __init__(self, modules, results, parent=None, on_dump=None, flash_dt="", versions=None):
        super().__init__(parent)

        self.setWindowTitle("Результат прошивки")

        layout = QVBoxLayout(self)

        dt_label = QLabel(f"Дата/время прошивки: {flash_dt or 'не определена'}")
        dt_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(dt_label)

        self.flash_dt = flash_dt
        self.versions = dict(versions or {})

        table = QTableWidget()
        table.setColumnCount(6)
        table.setHorizontalHeaderLabels([
            "Номер слота", "Тип модуля", "Путь к файлу",
            "Тип прошивки", "Версии (до → после)", "Результат"
        ])
        table.setRowCount(len(modules))

        table.setWordWrap(False)
        table.setTextElideMode(Qt.TextElideMode.ElideRight)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.verticalHeader().setDefaultSectionSize(30)

        fm = table.fontMetrics()
        max_path_width = 0

        for i, mod in enumerate(modules):
            slot = str(mod.get('slot'))
            path = mod.get('path', '') or ''
            max_path_width = max(max_path_width, fm.horizontalAdvance(path))

            table.setItem(i, 0, QTableWidgetItem(slot))
            table.setItem(i, 1, QTableWidgetItem(mod.get('type') or 'N/A'))

            path_item = QTableWidgetItem(path)
            path_item.setToolTip(path)
            table.setItem(i, 2, path_item)

            img_type_item = QTableWidgetItem(display_img_type(mod.get('img_type', 'apply')))
            table.setItem(i, 3, img_type_item)

            ver_pair = (versions or {}).get(slot)
            if ver_pair:
                ver_text = f"{_short_fw_ver(ver_pair[0])} → {_short_fw_ver(ver_pair[1])}"
            else:
                ver_text = "N/A → N/A"

            table.setItem(i, 4, QTableWidgetItem(ver_text))

            res_raw = results.get(slot, "NO_INFO")

            if res_raw in ("NO_INFO", "__NO_INFO__"):
                res = "Нет информации"
                color = QColor("#0033cc")
            elif "Complete" in res_raw:
                res = "Выполнено"
                color = QColor("#006600")
            else:
                res = res_raw if res_raw.startswith("Ошибка") else f"Ошибка: {res_raw}"
                color = QColor("#b30000")

            item = QTableWidgetItem(res)
            item.setForeground(color)
            table.setItem(i, 5, item)

        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)

        path_width = max(420, min(max_path_width + 30, 900))
        table.setColumnWidth(2, path_width)

        hide_column_if_all_na(table, 1)
        table.resizeRowsToContents()

        for r in range(table.rowCount()):
            table.setRowHeight(r, 30)

        content_w = table.verticalHeader().width()
        for c in range(table.columnCount()):
            if not table.isColumnHidden(c):
                content_w += table.columnWidth(c)

        content_h = table.horizontalHeader().height()
        for r in range(table.rowCount()):
            content_h += table.rowHeight(r)

        frame = 2 * table.frameWidth()

        dlg_w = content_w + frame + 60
        dlg_h = content_h + frame + 180

        dlg_w = max(700, min(int(dlg_w), 1500))
        dlg_h = max(340, min(int(dlg_h), 950))

        self.resize(dlg_w, dlg_h)
        layout.addWidget(table)

        self.dump_btn = QPushButton("Выгрузить дамп")
        self.dump_btn.setObjectName("dialog_btn_dump")

        if on_dump is not None:
            self.dump_btn.clicked.connect(lambda checked=False: on_dump(self))
        else:
            self.dump_btn.setEnabled(False)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.dump_btn)
        btn_row.addStretch()

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        for btn in btn_box.buttons():
            btn.setObjectName("dialog_btn_ok")

        btn_box.accepted.connect(self.accept)
        btn_row.addWidget(btn_box)

        layout.addLayout(btn_row)


class EditSPDialog(QDialog):
    COL_CHECK = 0
    COL_SLOT = 1
    COL_TYPE = 2
    COL_INFO = 3
    COL_PATH = 4
    COL_DEV_VER = 5
    COL_FW_VER = 6
    COL_DATE = 7
    COL_FWTYPE = 8
    COL_COUNT = 9

    def __init__(self, modules_info, plan_modules, firmwares, config, parent=None, quiet=False, on_log=None):
        super().__init__(parent)

        self.quiet = quiet
        self._log_cb = on_log

        self.setWindowTitle("Редактирование сценария прошивки")

        self.config = config
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

        plan_by_slot = {}

        for m in plan_modules or []:
            if not isinstance(m, dict):
                continue

            key = _norm_slot(m.get('slot'))
            if not key:
                continue

            plan_by_slot[key] = m

        try:
            _max_slots = int(modules_info[0].get("_crate_slots")) if modules_info else None
        except (TypeError, ValueError, AttributeError):
            _max_slots = None

        if _max_slots is not None and _max_slots > 0:
            _skipped = [
                mi.get("slot_num") for mi in modules_info
                if str(mi.get("slot_num", "")).isdigit() and int(mi["slot_num"]) > _max_slots
            ]

            if _skipped:
                EditSPDialog.log_via(
                    self._log_cb,
                    f"Внимание: записи модулей вне слотов креста (crate_slot_count={_max_slots}) "
                    f"исключены из редактора: слоты {', '.join(map(str, _skipped))}"
                )

            modules_info = [
                mi for mi in modules_info
                if str(mi.get("slot_num", "")).isdigit() and int(mi["slot_num"]) <= _max_slots
            ]

        self.rows = []

        for info in modules_info:
            slot = info['slot_num']
            plan = plan_by_slot.get(slot, {})
            flashable = info.get('flashable', info.get('serial_num', 'N/A') != 'N/A')

            unflash_reason = ""
            if not flashable:
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
            "Выбор", "Слот", "Тип модуля", "Инфо", "Путь к файлу",
            "в.МФК", "в.СП", "Дата", "Тип прошивки"
        ])
        self.table.setRowCount(len(self.rows))

        self.checkboxes = []
        self.path_edits = []
        self.type_combos = []
        self.browse_btns = []

        for i, row in enumerate(self.rows):
            cb = QCheckBox()

            if row.get("flashable", True):
                cb.setChecked(bool(self._is_selectable(i)))
            else:
                cb.setEnabled(False)
                reason = row.get("unflash_reason") or "прошивка невозможна"
                cb.setToolTip(f"Прошивка невозможна: {reason}")

            cb.stateChanged.connect(lambda state, idx=i: self._on_checkbox_changed(idx))
            self.checkboxes.append(cb)
            self.table.setCellWidget(i, self.COL_CHECK, cb)

            slot_item = QTableWidgetItem(row['slot'])
            type_item = QTableWidgetItem(row['module_type'])

            info_text = ""
            if not row.get("flashable", True):
                info_text = row.get("unflash_reason") or "прошивка невозможна"

            info_item = QTableWidgetItem(info_text)

            if not row.get("flashable", True):
                red = QColor("#b30000")
                info_item.setForeground(red)

            self.table.setItem(i, self.COL_SLOT, slot_item)
            self.table.setItem(i, self.COL_TYPE, type_item)
            self.table.setItem(i, self.COL_INFO, info_item)

            path_widget = QWidget()
            path_layout = QHBoxLayout(path_widget)
            path_layout.setContentsMargins(0, 0, 0, 0)
            path_layout.setSpacing(2)

            path_edit = QLineEdit(row['path'])
            path_edit.editingFinished.connect(lambda idx=i: self._on_path_changed(idx))
            path_edit.textChanged.connect(lambda _t, idx=i: self._update_row(idx))

            browse_btn = QPushButton("...")
            browse_btn.setObjectName("browse_fw_btn")
            browse_btn.setToolTip("Выбрать файл прошивки")
            browse_btn.clicked.connect(lambda checked, idx=i: self._browse_firmware(idx))

            if not row.get("flashable", True):
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
            combo.addItem(display_img_type("apply"), "apply")
            combo.addItem(display_img_type("boot"), "boot")
            combo.setCurrentIndex(0 if row['img_type'] == "apply" else 1)
            combo.currentIndexChanged.connect(lambda _idx, i=i: self._update_row(i))

            self.type_combos.append(combo)
            self.table.setCellWidget(i, self.COL_FWTYPE, combo)

            self.table.setItem(i, self.COL_DEV_VER, QTableWidgetItem(_short_fw_ver(row['device_fw_version'])))

            for col in (self.COL_FW_VER, self.COL_DATE):
                self.table.setItem(i, col, QTableWidgetItem("N/A"))

            if row['path']:
                self._find_local_fw(i)

            self._update_row(i)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(self.COL_CHECK, QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().resizeSection(self.COL_CHECK, 70)

        for col in [self.COL_SLOT, self.COL_TYPE, self.COL_INFO, self.COL_FWTYPE,
                    self.COL_DEV_VER, self.COL_FW_VER, self.COL_DATE]:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)

        header.setSectionResizeMode(self.COL_PATH, QHeaderView.ResizeMode.Interactive)

        self.table.resizeRowsToContents()
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        self._resize_path_column_to_content()
        hide_column_if_all_na(self.table, self.COL_DEV_VER)

        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()

        self.autofill_appl_btn = QPushButton("Автозаполнение appl")
        self.autofill_appl_btn.setObjectName("autofill_btn")
        self.autofill_appl_btn.setToolTip("Подобрать файлы типа appl по типам модулей и выставить тип 'appl'")
        self.autofill_appl_btn.clicked.connect(lambda: self.autofill("apply"))
        btn_layout.addWidget(self.autofill_appl_btn)

        self.autofill_boot_btn = QPushButton("Автозаполнение boot")
        self.autofill_boot_btn.setObjectName("autofill_btn")
        self.autofill_boot_btn.setToolTip("Подобрать файлы типа boot по типам модулей и выставить тип 'boot'")
        self.autofill_boot_btn.clicked.connect(lambda: self.autofill("boot"))
        btn_layout.addWidget(self.autofill_boot_btn)

        self.select_all_btn = QPushButton("Выбрать все")
        self.select_all_btn.setObjectName("dialog_btn_ok")
        self.select_all_btn.clicked.connect(self.select_all)
        btn_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Снять все")
        self.deselect_all_btn.setObjectName("dialog_btn_cancel")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        btn_layout.addWidget(self.deselect_all_btn)

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

        self._fit_dialog_size()

    @staticmethod
    def log_via(callback, msg):
        OperationWorker.log_via(callback, msg)

    def _fit_dialog_size(self):
        table = self.table

        content_w = table.verticalHeader().width()
        for c in range(table.columnCount()):
            if not table.isColumnHidden(c):
                content_w += table.columnWidth(c)

        frame = 2 * table.frameWidth()
        width = content_w + frame + 36

        header_h = table.horizontalHeader().height()
        rows_h = sum(table.rowHeight(r) for r in range(table.rowCount()))
        height = header_h + rows_h + frame + 150

        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableSize()
            width = min(width, avail.width() - 30)
            height = min(height, avail.height() - 40)

        width = max(int(width), 900)
        height = max(int(height), 380)

        self.resize(width, height)

    def _resize_path_column_to_content(self):
        if not self.path_edits:
            return

        fm = self.path_edits[0].fontMetrics()
        max_w = 0

        for pe in self.path_edits:
            txt = pe.text().strip()
            if txt:
                max_w = max(max_w, fm.horizontalAdvance(txt))

        if max_w <= 0:
            return

        browse_w = self.browse_btns[0].sizeHint().width() if self.browse_btns else 24
        self.table.setColumnWidth(self.COL_PATH, max_w + browse_w + 34)

    def _find_local_fw(self, idx):
        if not (0 <= idx < len(self.rows)):
            return

        row = self.rows[idx]
        path = row.get('path', '')
        filename = os.path.basename(path) if path else ""
        found_fw = None

        if filename:
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

                    _f, _ok, _sup, _w = fw_name_format(filename, parsed=found_fw)
                    found_fw['fmt_ok'] = bool(_sup)
                else:
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

                        found_fw["source"] = detect_fw_source(path) or (
                            "apply" if prefix_fmt == "appl" else prefix_fmt
                        )

        row['local_fw'] = found_fw
        row['source'] = (found_fw.get('source') if found_fw else None) or detect_fw_source(path)

        return found_fw

    def _browse_firmware(self, idx):
        fw_dir = self.config.get('firmware_dir', '')

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите файл прошивки",
            fw_dir,
            "BIN файлы (*.bin);;Все файлы (*.*)"
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
        self._resize_path_column_to_content()

    def _on_checkbox_changed(self, idx):
        self._update_row(idx)

    def _on_path_changed(self, idx):
        path = self.path_edits[idx].text().strip()

        self.rows[idx]['path'] = path

        self._find_local_fw(idx)
        self._update_row(idx)
        self._resize_path_column_to_content()

    def _apply_combo_for_source(self, idx):
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

        for i in range(combo.count()):
            item = model.item(i) if hasattr(model, "item") else None

            if item is None:
                continue

            if combo.itemData(i) in allowed:
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            else:
                item.setFlags((item.flags() & ~Qt.ItemFlag.ItemIsEnabled) & ~Qt.ItemFlag.ItemIsSelectable)

        target = cur if cur in allowed else allowed[0]
        combo.setCurrentIndex(combo.findData(target))
        row['img_type'] = target

        combo.blockSignals(False)

    @staticmethod
    def _combo_model(combo):
        return combo.model()

    def _update_row(self, idx):
        if not (0 <= idx < len(self.rows)) or idx >= len(self.checkboxes) or idx >= len(self.path_edits):
            return

        row = self.rows[idx]
        fw = row.get('local_fw')

        cb = self.checkboxes[idx]
        path_empty = not self.path_edits[idx].text().strip()

        if row.get("flashable", True):
            if getattr(self, "_mass_update", False):
                wants_checked = cb.isChecked()
            else:
                wants_checked = self._is_selectable(idx)

            cb.setEnabled(True)

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

        versions_match = (
            fw is not None and device_ver != 'N/A' and local_ver != 'N/A' and device_ver == local_ver
        )

        bg_color = None

        if not checked:
            bg_color = "#e0e0e0"
        elif versions_match:
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

        return (fw.get('fw_type') or '') == want_type

    def autofill(self, want_type="apply"):
        filled = 0

        for i, row in enumerate(self.rows):
            if not row.get("flashable", True):
                continue

            mt = row['module_type'].upper()
            if mt in ("NA", ""):
                continue

            candidates = [fw for fw in self.fw_by_type.get(mt, []) if self._fw_matches_type(fw, want_type)]

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

            combo = self.type_combos[i]
            idx_t = combo.findData(want_type)

            if idx_t >= 0:
                combo.setCurrentIndex(idx_t)

            row['img_type'] = want_type

            self._update_row(i)
            filled += 1

        self.deselect_all()
        self.select_all()

        self._resize_path_column_to_content()
        self._fit_dialog_size()

    def _recheck_selection(self):
        try:
            self.select_all()
        except Exception:
            pass

    def _is_selectable(self, idx):
        if not (0 <= idx < len(self.rows)) or idx >= len(self.path_edits):
            return False

        row = self.rows[idx]

        if not row.get("flashable", True):
            return False

        mt = str(row.get("module_type") or "").strip().upper()
        if mt in ("", "NA"):
            return False

        cur = self.path_edits[idx].text().strip()

        if cur != row.get('path', ''):
            row['path'] = cur
            self._find_local_fw(idx)

        path = cur

        if not path:
            return False

        if not self._format_ok(path):
            return False

        if bool(self.config.get('skip_same_version', True)) and self._versions_match(row):
            return False

        return True

    @staticmethod
    def _versions_match(row):
        fw = row.get('local_fw') or {}

        device_ver = normalize_fw_version(row.get('device_fw_version'))
        local_ver = normalize_fw_version(fw.get('version'))

        return bool(fw) and device_ver != 'N/A' and local_ver != 'N/A' and device_ver == local_ver

    def _format_ok(self, path):
        if bool(self.config.get('format_control', True)):
            return bool(self.fw_format_supported(path))
        return True

    def fw_format_supported(self, path):
        fw = None

        for row in self.rows:
            cand = row.get('local_fw')

            if cand and (cand.get('rel_path') == re.sub(r'^images/', '', path)
                         or cand.get('filename') == os.path.basename(path)):
                fw = cand
                break

        filename = os.path.basename((fw or {}).get('filename') or path)

        _, _, supported, _warning = fw_name_format(filename, parsed=fw)

        if not supported:
            alt = parse_firmware_filename(filename) or _try_parse_short_hw_name(filename)

            if alt is not None:
                supported = fw_name_format(filename, parsed=alt)[2]

        return supported

    def _sync_paths_from_edits(self):
        for i in range(len(self.rows)):
            cur = self.path_edits[i].text().strip()

            if cur != self.rows[i].get('path', ''):
                self.rows[i]['path'] = cur
                self._find_local_fw(i)

    def select_all(self):
        self._sync_paths_from_edits()

        prev_guard = getattr(self, "_mass_update", False)
        self._mass_update = True

        try:
            for i, cb in enumerate(self.checkboxes):
                ok = self._is_selectable(i)

                cb.blockSignals(True)

                if self.rows[i].get("flashable", True):
                    cb.setEnabled(True)

                cb.setChecked(bool(ok))
                cb.blockSignals(False)

                self._update_row(i)
        finally:
            self._mass_update = prev_guard

    def deselect_all(self):
        self._sync_paths_from_edits()

        prev_guard = getattr(self, "_mass_update", False)
        self._mass_update = True

        try:
            for i, cb in enumerate(self.checkboxes):
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.setEnabled(True)
                cb.blockSignals(False)

                self._update_row(i)
        finally:
            self._mass_update = prev_guard

    def _present_module_types(self):
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
        for b in self._type_btns:
            b.setParent(None)
            b.deleteLater()

        self._type_btns = []

        types = self._present_module_types()

        if not types:
            self.type_group.setVisible(False)
            return

        self.type_group.setVisible(True)
        self.type_group.setTitle("Выбор модулей по типу (присутствуют в устройстве)")

        for mt in types:
            btn = QPushButton(mt)
            btn.setObjectName("type_select_btn")
            btn.setToolTip(f"Выбрать все модули типа {mt}")
            btn.clicked.connect(lambda checked, t=mt: self.select_by_type(t))

            self.type_group_layout.addWidget(btn)
            self._type_btns.append(btn)

    def select_by_type(self, module_type):
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
                self,
                "Выбор по типу",
                f"Нет доступных для прошивки модулей типа {want} "
                "(не заполнены пути или не пройден контроль формата)"
            )

    def _validate_row(self, idx):
        row = self.rows[idx]

        if not row.get("flashable", True):
            reason = row.get("unflash_reason") or "прошивка невозможна"
            return False, f"Слот {row['slot']}: {reason} — прошивка модуля запрещена"

        path = self.path_edits[idx].text().strip()

        if not path:
            return False, f"Слот {row['slot']}: путь к файлу не указан"

        filename = os.path.basename(path)

        if bool(self.config.get('format_control', True)) and not self._format_ok(path):
            _fmt, ok_prefix, _sup, warning = fw_name_format(filename)
            return False, f"Слот {row['slot']}: {warning or 'файл не прошёл контроль формата'}"

        parsed = parse_firmware_filename(filename)

        if parsed is None and not bool(self.config.get('format_control', True)):
            _fmt, _okp, _sup, warning = fw_name_format(filename)

            if warning:
                self.warnings.append(f"Слот {row['slot']}: {warning}")

            return True, ""

        if parsed is None:
            return False, f"Слот {row['slot']}: файл '{filename}' не соответствует формату имени прошивки"

        if parsed['module_type'] != row['module_type'].upper():
            return False, (
                f"Слот {row['slot']}: прошивка '{filename}' (тип {parsed['module_type']}) "
                f"не соответствует типу модуля {row['module_type']}"
            )

        source = row.get('source') or detect_fw_source(path)
        img_type = self.type_combos[idx].currentData()

        if img_type not in allowed_img_types(source):
            return False, (
                f"Слот {row['slot']}: тип '{display_img_type(img_type)}' недопустим для прошивки из "
                f"директории '{source or 'неизвестна'}' "
                f"(допустимо: {', '.join(display_img_type(t) for t in allowed_img_types(source))})"
            )

        return True, ""

    def apply_edit(self):
        self.apply_edits()

    def auto_save_to_device(self):
        """Автосохранение собранного плана на устройство без закрытия редактора."""

        selected = []

        for i, row in enumerate(self.rows):
            if not self.checkboxes[i].isChecked():
                continue

            row['path'] = self.path_edits[i].text().strip()
            row['img_type'] = self.type_combos[i].currentData()
            selected.append(row)

        if not selected:
            OperationWorker.log_via(self._log_cb, "Автосохранение СП: нет выбранных модулей — сохраняется пустой план")

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

        ssh = None

        try:
            ssh = SSHClient(self.config['ip'], self.config['password'])
            ssh.connect()
            ssh.sftp_put(tmp_path, "/home/user/fw_update/plan.xml")

            OperationWorker.log_via(
                self._log_cb,
                f"Автосохранение СП на устройство выполнено "
                f"(/home/user/fw_update/plan.xml, строк сценария: {len(selected)})"
            )
        except Exception as e:
            OperationWorker.log_via(self._log_cb, f"Ошибка автосохранения СП: {e}")
        finally:
            if ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass

            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass

    def apply_edits(self):
        selected = []

        for i, row in enumerate(self.rows):
            if not self.checkboxes[i].isChecked():
                continue

            if not row.get("flashable", True):
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

        if self.warnings:
            if self.quiet:
                self.warnings = []
            else:
                ret = QMessageBox.warning(
                    self,
                    "Предупреждения формата прошивок",
                    "Контроль формата отключен, в сценарий попадают файлы:\n"
                    + "\n".join(self.warnings[:20]) + ("\n..." if len(self.warnings) > 20 else "")
                    + "\n\nСохранить сценарий?"
                )

                self.warnings = []

                if ret != QMessageBox.StandardButton.Yes:
                    return

        if not selected and not self.quiet:
            ret = QMessageBox.warning(
                self,
                "Внимание",
                "Не выбрано ни одного модуля для прошивки.\nСохранить пустой сценарий прошивки?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if ret != QMessageBox.StandardButton.Yes:
                return
        elif not selected and self.quiet:
            raise Exception("Автопрошивка: автозаполнение appl не выбрало ни одного модуля — прошивать нечего")

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

        ssh = None

        try:
            ssh = SSHClient(self.config['ip'], self.config['password'])
            ssh.connect()
            ssh.sftp_put(tmp_path, "/home/user/fw_update/plan.xml")

            OperationWorker.log_via(
                self._log_cb,
                f"Сохранение СП на устройство выполнено (/home/user/fw_update/plan.xml, строк сценария: {len(selected)})"
            )

            if not self.quiet:
                QMessageBox.information(self, "Успех", "Сценарий успешно сохранён на устройстве")

            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить сценарий: {e}")
        finally:
            if ssh is not None:
                try:
                    ssh.close()
                except Exception:
                    pass

            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass

"""
============================================================
ГЛАВНОЕ ОКНО
============================================================
"""
class MainWindow(QMainWindow):
    _old_versions_cache = {}

    @staticmethod
    def cache_old_versions(worker, modules_data):
        try:
            cache = {str(m["slot_num"]): m.get("firmware_version", "") for m in modules_data}
        except Exception:
            return

        if cache:
            MainWindow._old_versions_cache = cache

            try:
                worker._old_versions = cache
            except Exception:
                pass

    def _recheck_selection(self):
        dlg = getattr(self, "_auto_edit_dialog", None)

        if dlg is not None:
            try:
                if dlg.isVisible():
                    dlg._recheck_selection()
            except (RuntimeError, AttributeError):
                pass

    def __init__(self):
        super().__init__()

        self.worker = None

        self._auto_step = 0
        self._auto_failed = False
        self._auto_failed_step = None
        self._auto_rows = None
        self._auto_data = None
        self._auto_pass_data_to_next = False
        self._pending_make_plan = False
        self._dump_reopen_data = None
        self._result_reopen_data = None
        self._auto_edit_dialog = None
        self._ops_busy = False

        self.setWindowTitle(APP_TITLE)
        self.resize(1000, 800)

        self.config = self.load_config()
        self.plan_xml_path = self.config.get("plan_xml", "")

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

        self.format_control_cb = QCheckBox(
            "Контроль формата прошивок (не загружать и не прошивать файлы с некорректными именами и формат full)"
        )
        self.format_control_cb.setToolTip(
            "По умолчанию включена: файлы, имена которых не начинаются\n"
            "с 'appl' или 'boot' (а также неподдерживаемый формат 'full'),\n"
            "на устройство не загружаются и прошивка ими запрещена.\n"
            "При отключении ограничения снимаются: выводятся только предупреждения."
        )
        conn_layout.addWidget(self.format_control_cb, 3, 0, 1, 4)

        self.skip_same_version_cb = QCheckBox("Не прошивать при совпадении версий")
        self.skip_same_version_cb.setToolTip(
            "По умолчанию включено: у модулей, на которых уже стоит та же версия прошивки,\n"
            "флаги выбора снимаются автоматически.\n"
            "При отключении совпадение версий не влияет на выбор."
        )
        self.skip_same_version_cb.toggled.connect(lambda _checked: self._recheck_selection())
        conn_layout.addWidget(self.skip_same_version_cb, 4, 0, 1, 4)

        conn_group.setLayout(conn_layout)
        main_layout.addWidget(conn_group)

        ops_group = QGroupBox("Операции")
        ops_layout = QGridLayout()

        col1_ops = [
            (13, "АВТОПРОШИВКА", "col2_btn_13"),
            (1, "Внедрить агента и прошивки", "col1_btn_1"),
            (6, "Запустить прошивку", "col1_btn_6"),
            (8, "Просмотр результата", "col1_btn_8"),
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
            (10, "Информация о модулях", "col1_btn_10"),
        ]

        for i, (op_id, text, obj_name) in enumerate(col2_ops):
            btn = QPushButton(text)
            btn.setObjectName(obj_name)
            btn.clicked.connect(lambda checked, oid=op_id: self.start_operation(oid))
            ops_layout.addWidget(btn, i, 1)

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

        self.verbose_log_cb = QCheckBox("Детализация")
        self.verbose_log_cb.setToolTip(
            "По умолчанию выключена: в журнале только ключевые события.\n"
            "Включите для отладки: добавится полная детализация."
        )
        bottom_layout.addWidget(self.verbose_log_cb)

        self.clear_log_btn = QPushButton("Очистить лог")
        self.clear_log_btn.setObjectName("clear_btn")
        self.clear_log_btn.clicked.connect(self.log_text.clear)
        bottom_layout.addWidget(self.clear_log_btn)

        main_layout.addLayout(bottom_layout)

        self.all_ops = [(op_id, text) for op_id, text, _ in col1_ops + col2_ops]
        self.all_ops.append((7, "Выгрузить дамп"))

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
        start_dir = ""

        cur = self.agent_edit.text().strip()
        if cur:
            start_dir = os.path.dirname(cur) or cur

        file_path, _ = QFileDialog.getOpenFileName(self, "Выберите файл агента IskraIO_Util", start_dir, "")

        if file_path:
            self.agent_edit.setText(file_path)
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
            "plan_xml": self.plan_xml_path,
            "format_control": self.format_control_cb.isChecked(),
            "skip_same_version": self.skip_same_version_cb.isChecked(),
            "verbose_log": self.verbose_log_cb.isChecked()
        }

        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

        self.config.update(config)

    def load_settings_to_ui(self):
        self.ip_edit.setText(self.config.get("ip", ""))
        self.pass_edit.setText(self.config.get("password", ""))
        self.agent_edit.setText(self.config.get("agent_dir", ""))
        self.fw_edit.setText(self.config.get("firmware_dir", ""))

        self.format_control_cb.setChecked(bool(self.config.get("format_control", True)))
        self.skip_same_version_cb.setChecked(bool(self.config.get("skip_same_version", True)))
        self.verbose_log_cb.setChecked(bool(self.config.get("verbose_log", False)))

    def append_log(self, msg):
        color = "#000000"
        font_weight = "normal"

        msg_lower = msg.lower()

        if ("--- запущена" in msg_lower or "--- операция" in msg_lower
                or "=== автопрошивка" in msg_lower):
            color = "#003399"
            font_weight = "bold"
        elif "ошибка" in msg_lower or "critical" in msg_lower or "error" in msg_lower:
            color = "#b30000"
            font_weight = "bold"
        elif "успешно" in msg_lower or "complete" in msg_lower:
            color = "#006600"
            font_weight = "bold"
        elif "предупреждение" in msg_lower or "warning" in msg_lower or "не произведена" in msg_lower:
            color = "#b35900"
            font_weight = "bold"
        elif "остановка" in msg_lower or "запуск" in msg_lower:
            color = "#444444"

        safe_msg = html.escape(msg)
        self.log_text.append(
            f'<span style="color:{color}; font-weight:{font_weight}; '
            f'font-family: Consolas, monospace;">{safe_msg}</span>'
        )

    def get_current_config(self):
        return {
            "ip": self.ip_edit.text(),
            "password": self.pass_edit.text(),
            "agent_dir": self.agent_edit.text(),
            "firmware_dir": self.fw_edit.text(),
            "plan_xml": self.plan_xml_path,
            "format_control": self.format_control_cb.isChecked(),
            "skip_same_version": self.skip_same_version_cb.isChecked(),
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
        self._ops_busy = not enabled

        for btn in self.op_buttons.values():
            if btn is not None:
                btn.setEnabled(enabled)

    def start_operation(self, op_id):
        prev_worker_done = False

        if hasattr(self, "worker") and self.worker is not None and self.worker.isRunning():
            prev_worker_done = bool(getattr(self.worker, "_finished_emitted", False))

        if not getattr(self, "_auto_step", 0) and not getattr(self, "_force_op", False):
            if (getattr(self, "_ops_busy", False) or (
                    hasattr(self, "worker") and self.worker is not None
                    and self.worker.isRunning() and not prev_worker_done)):
                QMessageBox.warning(self, "Внимание", "Уже выполняется другая операция. Дождитесь её завершения.")
                return

        self._force_op = False

        in_auto_chain_pre = getattr(self, "_auto_step", 0) > 0
        config = self.get_current_config()

        if not config['ip'] or not config['password']:
            QMessageBox.critical(self, "Ошибка", "Укажите IP-адрес и пароль!")
            return

        if op_id == 3 and not in_auto_chain_pre:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "Выберите файл сценария (plan.xml)",
                self.plan_xml_path or "",
                "XML Files (*.xml)"
            )

            if not file_path:
                return

            self.plan_xml_path = file_path
            self.save_config()
            config['plan_xml'] = file_path

        if op_id == 1:
            if not config['agent_dir'] or not config['firmware_dir']:
                QMessageBox.critical(self, "Ошибка", "Укажите директории агента и прошивок!")
                return

            if self.check_remote_dir_exists("/home/user/fw_update"):
                reply = QMessageBox.warning(
                    self,
                    "Предупреждение",
                    "Каталог /home/user/fw_update/ уже существует. Удалить его?",
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
                )

                if reply == QMessageBox.StandardButton.Cancel:
                    return
        elif op_id == 2:
            if not in_auto_chain_pre:
                if not self.check_agent_exists():
                    QMessageBox.critical(
                        self,
                        "Ошибка",
                        "Агент IskraIO_Util отсутствует. Сначала выполните 'Внедрить агента и прошивки'."
                    )
                    return

                reply = QMessageBox.warning(
                    self,
                    "Предупреждение",
                    "Телемеханика будет остановлена. Продолжить?",
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
                )

                if reply == QMessageBox.StandardButton.Cancel:
                    return
        elif op_id == 6:
            if not in_auto_chain_pre:
                reply = QMessageBox.warning(
                    self,
                    "Предупреждение",
                    "Телемеханика будет остановлена. Продолжить?",
                    QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
                )

                if reply == QMessageBox.StandardButton.Cancel:
                    return
        elif op_id == 3:
            if not config['plan_xml']:
                QMessageBox.critical(self, "Ошибка", "Укажите файл сценария!")
                return
        elif op_id == 12 and getattr(self, "_auto_step", 0) == 0:
            reply = QMessageBox.warning(
                self,
                "Предупреждение",
                "Директория /home/user/fw_update/ будет удалена с контроллера. Продолжить?",
                QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
            )

            if reply == QMessageBox.StandardButton.Cancel:
                return
        elif op_id == 13:
            if not config['agent_dir'] or not config['firmware_dir']:
                QMessageBox.critical(self, "Ошибка", "Укажите файлы/директории агента и прошивок!")
                return

            if self._auto_step == 0:
                self._auto_failed = False
                self._auto_rows = None
                self._auto_data = None
                self._auto_pass_data_to_next = False
                self._dump_reopen_data = None
                self._pending_make_plan = False

                self.append_log("=== АВТОПРОШИВКА: запуск цепочки операций ===")

        if op_id == 13 and getattr(self, "_auto_step", 0) <= 1:
            self._auto_failed = False
            self._auto_failed_step = None
            self._auto_rows = None
            self._auto_step = 1
            self._auto_run_step()
            return

        in_auto_chain = getattr(self, "_auto_step", 0) > 0

        self.progress_bar.setValue(0)

        op_name = next((name for oid, name in self.all_ops if oid == op_id), f"ID {op_id}")

        if not in_auto_chain:
            self.append_log(f"--- Запущена операция: {op_name} ---")

        cfg = dict(config)
        quiet = in_auto_chain
        worker_op = op_id

        if op_id == 6 and MainWindow._old_versions_cache:
            cfg['_old_versions'] = dict(MainWindow._old_versions_cache)

        if getattr(self, "_auto_step", 0) == 3:
            worker_op = 11
            cfg['_auto_after_prepare'] = True

        if op_id == 2 and in_auto_chain:
            cfg['_skip_local_checks'] = True

        self._set_ops_enabled(False)

        self.worker = OperationWorker(worker_op, cfg, quiet=quiet, on_log=self.append_log)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.on_operation_finished)

        self._set_ops_enabled(False)
        self.worker.start()

    AUTO_STEPS = {
        1: "Внедрить агента и прошивки",
        2: "Создать СП",
        3: "Редактор СП (тихое автозаполнение appl)",
        4: "Запустить прошивку",
    }

    def _auto_run_step(self):
        step = self._auto_step
        name = self.AUTO_STEPS.get(step, "")

        self.append_log(f"[Автопрошивка] Шаг {step}/{len(self.AUTO_STEPS)}: {name}")

        op_map = {1: 1, 2: 2, 3: 11, 4: 6}
        self.start_operation(op_map[step])

    def _auto_finish(self, reason=None):
        self._auto_step = 0
        self._auto_rows = None

        self._set_ops_enabled(True)

        if reason:
            self.append_log(f"=== АВТОПРОШИВКА ПРЕРВАНА: {reason} ===")
        else:
            self.append_log("=== АВТОПРОШИВКА ЗАВЕРШЕНА УСПЕШНО ===")

    def _auto_abort(self, reason):
        self._auto_failed = True

        self.append_log(f"[Автопрошивка] СБОЙ: {reason}")
        QMessageBox.critical(self, "Автопрошивка", f"Сбой: {reason}")

        self._auto_finish(reason)

    def _auto_flash_step_done(self, success, message, data):
        step = self._auto_step

        if not success:
            self._auto_abort(message or f"ошибка на шаге {step}")
            return

        if step >= 4:
            self._auto_finish()
            return

        if step == 3:
            if data.get("_auto_saved"):
                self._auto_rows = data.get("_auto_rows") or []
                self._auto_data = None

                if isinstance(getattr(self, "config", None), dict):
                    self.config["_auto_rows"] = list(self._auto_rows)

                if not self._auto_rows:
                    self._auto_finish()
                    return

                self._auto_step += 1
                QTimer.singleShot(300, self._auto_run_step)
                return

            self._auto_abort("Автопрошивка: шаг 3 не вернул данные редактора СП")
            return

        if data.get("_auto_saved"):
            self._auto_rows = data.get("_auto_rows") or []

        self._auto_step += 1
        QTimer.singleShot(300, self._auto_run_step)

    def _log_op_finish_once(self, op_id, success, force=False):
        wkr = getattr(self, "worker", None)

        if not force and wkr is not None and getattr(wkr, "_gui_fin_logged", False):
            return

        if wkr is not None:
            wkr._gui_fin_logged = True

        op_name = next((name for oid, name in self.all_ops if oid == op_id), "")

        if not op_name:
            return

        if success:
            self.append_log(f"--- Операция: {op_name} завершена ---")
        else:
            self.append_log(f"--- Операция: {op_name} завершена с ошибкой ---")

    def on_operation_finished(self, success, message, data):
        try:
            op_id = data.get("_op_id") if isinstance(data, dict) else None

            if op_id is None:
                op_id = getattr(self.worker, "op_id", None)

            if getattr(self, "_auto_step", 0) == 0 and not data.get("_silent"):
                dump_reopen = (getattr(self, "_dump_reopen_data", None) is not None)

                if not (dump_reopen and success):
                    self._log_op_finish_once(op_id, success)
        except Exception:
            pass

        try:
            if getattr(self, "_auto_step", 0) > 0:
                self._auto_flash_step_done(success, message, data)
                return

            self._handle_operation_result(success, message, data)
        finally:
            if getattr(self, "_auto_step", 0) == 0:
                self._set_ops_enabled(True)

    def _start_dump_from_dialog(self, dialog, modules, results):
        config = self.get_current_config()

        if not config['ip'] or not config['password']:
            QMessageBox.critical(self, "Ошибка", "Укажите IP-адрес и пароль!")
            return

        self._ops_busy = False

        if self.worker is not None and self.worker.isRunning():
            try:
                self.worker.finished_signal.disconnect(self.on_operation_finished)
            except (TypeError, RuntimeError):
                pass

            self.worker.wait(5000)

        self._force_op = True

        self._result_reopen_data = {
            "modules": modules,
            "results": results,
            "flash_dt": getattr(dialog, "flash_dt", ""),
            "versions": getattr(dialog, "versions", {}),
        }

        dialog.reject()
        self.start_operation(7)

    def _handle_operation_result(self, success, message, data):
        if isinstance(data, dict) and data.get("action") == "result":
            self._last_result_data = {
                "modules": data.get("modules", []),
                "results": data.get("results", {}),
                "flash_dt": data.get("flash_dt", ""),
                "versions": data.get("versions", {}),
            }

        try:
            self._handle_operation_result_impl(success, message, data)
        except Exception as e:
            text = "".join(traceback.format_exc()).strip()

            self.append_log(f"Критическая ошибка: {text}")

            try:
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    f"Не удалось обработать результат операции: {e}\n\n{text[:1200]}"
                )
            except Exception:
                pass
        finally:
            if getattr(self, "_auto_step", 0) == 0:
                self._set_ops_enabled(True)

    def _handle_operation_result_impl(self, success, message, data):
        reopen = getattr(self, "_result_reopen_data", None)

        if reopen is not None:
            self._result_reopen_data = None

            def _reopen_after_msgbox():
                dlg = ViewResultDialog(
                    reopen["modules"],
                    reopen["results"],
                    self,
                    on_dump=lambda d, m=reopen["modules"], r=reopen["results"]: self._start_dump_from_dialog(d, m, r),
                    flash_dt=reopen.get("flash_dt", ""),
                    versions=reopen.get("versions") or {}
                )
                dlg.exec()

            if not success:
                QTimer.singleShot(0, _reopen_after_msgbox)
            else:
                _reopen_after_msgbox()
                return

        reopen = getattr(self, "_dump_reopen_data", None)

        if reopen is not None and success:
            self._dump_reopen_data = None

            modules, results = reopen

            dialog = ViewResultDialog(
                modules,
                results,
                self,
                on_dump=lambda d, m=modules, r=results: self._start_dump_from_dialog(d, m, r),
                versions=data.get("versions") or {}
            )

            dialog.exec()
            return

        if reopen is not None and not success:
            self._dump_reopen_data = None

        if not success:
            QMessageBox.critical(self, "Ошибка", message)
            return

        if data.get("_op_id") == 2 and not getattr(self, "_auto_step", 0):
            self._pending_make_plan = True
            QTimer.singleShot(300, lambda: self.start_operation(9))
            return

        action = data.get("action")

        if action is None:
            return

        if action == "result":
            if not data.get("modules"):
                if self.verbose_log_cb.isChecked():
                    self.append_log("Просмотр результата: нет данных для отображения — диалог не открывается")
                return

            dialog = ViewResultDialog(
                data["modules"],
                data["results"],
                self,
                on_dump=lambda d, m=data["modules"], r=data["results"]: self._start_dump_from_dialog(d, m, r),
                flash_dt=data.get("flash_dt", ""),
                versions=data.get("versions") or {}
            )

            dialog.exec()
        elif action == "edit":
            if getattr(self, "_auto_step", 0) > 0 and data.get("_auto_saved"):
                return

            pending = getattr(self, "_pending_make_plan", False)

            dialog = EditSPDialog(
                data["modules_info"],
                data["plan_modules"],
                data["firmwares"],
                self.get_current_config(),
                self,
                quiet=getattr(self, "_auto_step", 0) > 0,
                on_log=self.append_log
            )

            self._auto_edit_dialog = dialog

            if getattr(self, "_auto_step", 0) == 0:
                dialog.autofill("apply")

            if pending:
                dialog.auto_save_to_device()
                self._pending_make_plan = False

            dialog.exec()
        elif action == "module_info":
            dialog = ModuleInfoDialog(data["modules"], self)
            dialog.exec()


def _install_excepthook(window_ref):
    def hook(exc_type, exc, tb):
        if issubclass(exc_type, (KeyboardInterrupt, SystemExit)):
            sys.excepthook(exc_type, exc, tb)
            return

        text = "".join(traceback.format_exception(exc_type, exc, tb)).strip()

        try:
            if window_ref[0] is not None:
                window_ref[0].append_log(f"Критическая ошибка: {text}")
                QMessageBox.critical(window_ref[0], "Критическая ошибка", text[-2000:])
        except Exception:
            pass

        sys.stderr.write(text + "\n")

    sys.excepthook = hook


def _install_app_icon(app):
    from PyQt6.QtGui import QIcon

    candidates = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "MFC_moduleUpd.ico")]

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