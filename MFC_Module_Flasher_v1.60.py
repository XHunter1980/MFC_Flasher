"""
MFC Module Updater (IskraIO) — настольное приложение для прошивки модулей МФК.

Назначение:
    Автоматизация процесса обновления прошивок модулей многофункционального
    контроллера (МФК) через SSH/SFTP-агента IskraIO_Util и HTTP-бэкенд устройства.

Возможности:
    - Загрузка агента и файлов прошивок на устройство (операция 1);
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
    python MFC_Module_Updater_v1.58.py

История изменений: см. CHANGELOG.md (при каждой доработке увеличивайте
версию APP_VERSION и добавляйте запись в историю).

Автор: Екимов Д.А. @ 2026
Версия: 1.58
"""
import html
import http.cookiejar
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

import paramiko
from PyQt6.QtCore import QThread, pyqtSignal
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
APP_VERSION = "1.60.1"
APP_TITLE = f"Прошивка модулей МФК версия {APP_VERSION}"

CONFIG_FILE = "mfc_flasher_config.json"
DEFAULT_CONFIG = {
    "ip": "",
    "password": "",
    "agent_dir": "",
    "firmware_dir": "",
    "plan_xml": "",
    "api_path": "/vx3/backend.fcgi"
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
QPushButton#clear_btn { background-color: #6c757d; }
QPushButton#clear_btn:hover { background-color: #5a6268; }
QPushButton#dialog_btn_ok { background-color: #0078d7; color: white; padding: 6px 20px; }
QPushButton#dialog_btn_ok:hover { background-color: #005a9e; }
QPushButton#dialog_btn_cancel { background-color: #555555; color: white; padding: 6px 20px; }
QPushButton#dialog_btn_cancel:hover { background-color: #3a3a3a; }
QPushButton#autofill_btn { background-color: #b8860b; color: white; padding: 6px 20px; }
QPushButton#autofill_btn:hover { background-color: #8b6508; }
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
    """
    def __init__(self, ip, api_path="/vx3/backend.fcgi", log_callback=None):
        self.ip = ip
        self.api_path = api_path if api_path.startswith('/') else '/' + api_path
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
        if self.log_callback:
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


def parse_plan_xml(xml_path):
    """Разбор plan.xml: список модулей сценария прошивки по элементам <Image>."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    modules = []
    for img in root.iter('Image'):
        modules.append({
            'slot': img.get('module_slot'),
            'type': img.get('module_type'),
            'path': img.get('path'),
            'img_type': img.get('type')
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


# Директории (подпапки firmware_dir), в которых лежат файлы прошивок:
#   full/  — полный образ, можно прошить как apply, так и boot;
#   apply/ — только тип apply; boot/ — только тип boot.
FW_SUBDIRS = ("full", "apply", "boot")


def detect_fw_source(rel_path):
    """Определяет директорию-источник прошивки по относительному пути.

    Возвращает нормализованное имя подпапки firmware_dir ('full'/'apply'/
    'boot') либо None, если путь не содержит известную директорию.
    """
    if not rel_path:
        return None
    parts = [p.lower() for p in re.split(r"[\\/]+", rel_path.strip()) if p]
    for seg in parts:
        if seg in FW_SUBDIRS:
            return seg
    return None


def allowed_img_types(source):
    """Допустимые типы прошивки для директории-источника."""
    if source == "apply":
        return ["apply"]
    if source == "boot":
        return ["boot"]
    return ["apply", "boot"]  # full либо источник неизвестен — выбор сохраняется


def parse_firmware_filename(filename):
    """Парсинг имени файла прошивки согласно правилам из Excel."""
    name_no_ext = os.path.splitext(filename)[0]
    parts = name_no_ext.split('_')

    if len(parts) != 7 or parts[0] != 'full':
        return None

    marker_raw = parts[1]
    type_raw = parts[2]
    ver_major_raw = parts[4]
    ver_minor = parts[5]
    date_raw = parts[6]

    if not ver_major_raw.upper().startswith('R'):
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
        "fw_type": "apply",
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

    def __init__(self, op_id, config):
        super().__init__()
        self.op_id = op_id
        self.config = config

    def log(self, msg):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_signal.emit(f"[{timestamp}] {msg}")

    def run(self):
        try:
            if self.op_id == 10:
                self._op10_get_module_info()
                return
            if self.op_id == 11:
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
            elif self.op_id == 7:
                self._op7_download_dump(ssh)
            elif self.op_id == 8:
                self._op8_view_result(ssh)
            elif self.op_id == 9:
                self._op9_edit_plan(ssh)

            ssh.close()
            self.finished_signal.emit(True, "Операция завершена успешно", {})
        except Exception as e:
            self.log(f"Критическая ошибка: {e!s}")
            self.finished_signal.emit(False, f"Ошибка: {e!s}", {})

    def _check_service_status(self, ssh, service_name):
        out, _ = ssh.exec_command(f"systemctl is-active {service_name}")
        return out.strip()

    def _upload_selected_firmwares(self, ssh):
        """Доказательная загрузка на устройство прошивок, выбранных в СП.

        Для каждой строки plan.xml проверяется наличие файла на устройстве
        (/home/user/fw_update/images/<rel_path>); отсутствующий локальный
        файл (по rel_path из скана firmware_dir) копируется туда. Если файла
        нет ни на устройстве, ни локально — ошибка операции.
        """
        plan_modules = parse_plan_xml(self.config['plan_xml']) \
            if os.path.isfile(self.config.get('plan_xml', '')) else []
        if not plan_modules:
            self.log("Сценарий прошивки (plan.xml) пуст или отсутствует — "
                     "проверка файлов пропускается")
            return
        fw_by_rel = {}
        for fw in self._scan_firmware_dir():
            fw_by_rel[fw['rel_path']] = fw
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
                fw = next((f for f in fw_by_rel.values()
                           if f['filename'] == fname), None)
            if fw is None:
                raise Exception(
                    f"Файл прошивки '{path}' из сценария не найден ни на "
                    f"устройстве, ни в директории "
                    f"'{self.config.get('firmware_dir', '')}'")
            sub = os.path.dirname(fw['rel_path'])
            ssh.exec_command(f"mkdir -p /home/user/fw_update/images/{sub}"
                             if sub else "true")
            ssh.sftp_put(fw['local_path'], remote)
            uploaded += 1
        self.log(f"Файлы прошивок из СП: на устройстве {present}, "
                 f"дозагружено {uploaded}")

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
            self.config.get('api_path', '/vx3/backend.fcgi'),
            log_callback=self.log
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
            if _prev is None or (not (_prev.get("serial_num") or "")
                                 and (_mod.get("serial_num") or "")):
                mod_by_slot[_s] = _mod

        def _has_serial(mod):
            """Есть ли у модуля серийный номер (критерий доступности прошивки)."""
            return bool((mod or {}).get("serial_num"))

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
                              if (mod.get("serial_num") or "")
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
            serial_num = mod.get("serial_num") or "N/A"
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
        """Скан директории прошивок с учётом подпапок full/apply/boot.

        Файлы ищутся в корне firmware_dir и в подпапках FW_SUBDIRS. Для каждой
        прошивки заполняется 'source' (директория-источник) и 'rel_path'
        (путь относительно firmware_dir, например 'full/xxx.bin').
        """
        fw_dir = self.config.get('firmware_dir', '')
        firmwares = []
        if not fw_dir or not os.path.isdir(fw_dir):
            return firmwares
        search_dirs = [("", fw_dir)] + [
            (sub, os.path.join(fw_dir, sub)) for sub in FW_SUBDIRS
            if os.path.isdir(os.path.join(fw_dir, sub))
        ]
        for subdir, dirpath in search_dirs:
            for filename in sorted(os.listdir(dirpath)):
                full_path = os.path.join(dirpath, filename)
                if not os.path.isfile(full_path):
                    continue
                parsed = parse_firmware_filename(filename)
                if parsed:
                    parsed["local_path"] = full_path
                    parsed["source"] = subdir if subdir else detect_fw_source(filename)
                    parsed["rel_path"] = f"{subdir}/{filename}" if subdir else filename
                    firmwares.append(parsed)
                elif not subdir:
                    self.log(f"Предупреждение: файл '{filename}' не соответствует ожидаемому формату")
        return firmwares

    def _op10_get_module_info(self):
        modules_data = self._fetch_module_info()
        self.progress_signal.emit(100)
        # Отладочная сводка: слот -> тип (помогает выявить смещение индексов)
        summary = ", ".join(f"{m['slot_num']}:{m['module_type']}" for m in modules_data)
        self.log(f"Соответствие слот/тип: {summary}")
        self.log(f"Найдено модулей: {len(modules_data)}")
        self.finished_signal.emit(True, "Информация получена",
                                  {"modules": modules_data, "action": "module_info"})

    def _op11_prepare_edit_plan(self):
        modules_info = self._fetch_module_info()
        firmwares = self._scan_firmware_dir()
        ssh = SSHClient(self.config['ip'], self.config['password'])
        ssh.connect()
        self.log("Загрузка plan.xml с устройства...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            tmp_path = tmp.name
        try:
            ssh.sftp_get("/home/user/fw_update/plan.xml", tmp_path)
            plan_modules = parse_plan_xml(tmp_path)
        except Exception as e:
            os.remove(tmp_path)
            ssh.close()
            raise Exception(f"Не удалось загрузить plan.xml: {e}") from e
        finally:
            ssh.close()
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        self.progress_signal.emit(100)
        self.log(f"Данные для редактора подготовлены. Модулей: {len(modules_info)}, прошивок: {len(firmwares)}")
        self.finished_signal.emit(True, "Данные получены", {
            "modules_info": modules_info,
            "plan_modules": plan_modules,
            "firmwares": firmwares,
            "action": "edit"
        })

    def _op1_upload_agent(self, ssh):
        self.log("Очистка и создание каталогов...")
        ssh.exec_command("rm -rf /home/user/fw_update")
        ssh.exec_command("mkdir -p /home/user/fw_update/images")
        self.log("Загрузка агента IskraIO_Util...")
        agent_path = os.path.join(self.config['agent_dir'], "IskraIO_Util")
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
                "файлов прошивок корректного формата (full_*.bin)")
        for i, fw in enumerate(firmwares):
            ssh.exec_command("mkdir -p /home/user/fw_update/images/" + os.path.dirname(fw["rel_path"]).replace("\\", "/"))
            ssh.sftp_put(fw["local_path"], f"/home/user/fw_update/images/{fw['rel_path']}")
            progress = int((i + 1) / total * 100)
            self.progress_signal.emit(progress)
        self.log(f"Загружено прошивок: {total}")
        self.log("Агент и прошивки успешно загружены")

    def _op2_make_plan(self, ssh):
        try:
            self._stop_services(ssh)
            self.log("Создание сценария прошивки (MakePlan)...")
            self.progress_signal.emit(50)
            out, err = ssh.exec_command("cd /home/user/fw_update && ./IskraIO_Util MakePlan")
            if err:
                self.log(f"MakePlan stderr: {err}")
            self.log(f"MakePlan stdout: {out}")
            self.progress_signal.emit(100)
            self.log("MakePlan завершён")
        except Exception as e:
            self.log(f"Ошибка во время MakePlan: {e}")
            raise
        finally:
            self._start_services(ssh)

    def _op3_import_plan(self, ssh):
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
        self.log("Выгрузка plan.xml...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_path = os.path.join(self.config['agent_dir'], f"plan_export_{timestamp}.xml")
        ssh.sftp_get("/home/user/fw_update/plan.xml", local_path)
        self.progress_signal.emit(100)
        self.log(f"Сценарий выгружен в: {local_path}")

    def _op6_update(self, ssh):
        self.log("Проверка наличия агента и файлов прошивок на устройстве...")
        if not ssh.sftp_stat("/home/user/fw_update/IskraIO_Util"):
            raise Exception("Агент IskraIO_Util отсутствует. Сначала выполните 'Загрузить агента'.")
        # Доказательная проверка/дозагрузка файлов из СП (plan.xml) перед Update
        self._upload_selected_firmwares(ssh)
        remote_images = ssh.sftp_listdir("/home/user/fw_update/images")
        if not remote_images:
            raise Exception("Директория /home/user/fw_update/images/ пуста. Сначала выполните 'Загрузить агента'.")
        self.log(f"Найдено файлов прошивок на устройстве: {len(remote_images)}")

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
            local_log = os.path.join(self.config['agent_dir'], f"operation_log_{timestamp}.log")
            ssh.sftp_get("/home/user/fw_update/operation.log", local_log)

            self.log("Анализ result.txt...")
            stdin, stdout, stderr = ssh.client.exec_command("cat /home/user/fw_update/result.txt")
            result_content = stdout.read().decode()
            results = parse_result_txt(result_content)
            for slot, status in results.items():
                if "Complete" in status:
                    self.log(f"Слот {slot}: Успешно")
                else:
                    self.log(f"Слот {slot}: Ошибка - {status}")
        except Exception as e:
            self.log(f"Ошибка во время прошивки: {e}")
            raise
        finally:
            self._start_services(ssh)

    def _op7_download_dump(self, ssh):
        self.log("Выгрузка дампа операции...")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        local_dump = os.path.join(self.config['agent_dir'], f"io_can_box2_{timestamp}.csv")
        ssh.sftp_get("/home/user/fw_update/io.can.box2.csv", local_dump)
        self.progress_signal.emit(100)
        self.log(f"Дамп выгружен в: {local_dump}")

    def _op8_view_result(self, ssh):
        self.log("Чтение данных для анализа результата...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            tmp_plan = tmp.name
        ssh.sftp_get("/home/user/fw_update/plan.xml", tmp_plan)
        modules = parse_plan_xml(tmp_plan)
        os.remove(tmp_plan)
        stdin, stdout, stderr = ssh.client.exec_command("cat /home/user/fw_update/result.txt")
        result_content = stdout.read().decode()
        results = parse_result_txt(result_content)
        self.progress_signal.emit(100)
        self.finished_signal.emit(True, "Просмотр результата", {"modules": modules, "results": results, "action": "result"})

    def _op9_edit_plan(self, ssh):
        self.log("Получение актуальной информации о модулях...")
        modules_info = self._fetch_module_info()
        firmwares = self._scan_firmware_dir()
        self.log("Загрузка plan.xml с устройства...")
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xml") as tmp:
            tmp_path = tmp.name
        try:
            ssh.sftp_get("/home/user/fw_update/plan.xml", tmp_path)
            plan_modules = parse_plan_xml(tmp_path)
        except Exception as e:
            os.remove(tmp_path)
            raise Exception(f"Не удалось загрузить plan.xml: {e}") from e
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass
        self.progress_signal.emit(100)
        self.finished_signal.emit(True, "Редактирование СП", {
            "modules_info": modules_info,
            "plan_modules": plan_modules,
            "firmwares": firmwares,
            "action": "edit"
        })


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
                serial_item.setText(f"{mod['serial_num']} (прошивка невозможна: {reason})")
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
    def __init__(self, modules, results, parent=None):
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
            table.setItem(i, 3, QTableWidgetItem(mod['img_type']))
            res = results.get(mod['slot'], "Нет данных / Ошибка")
            item = QTableWidgetItem(res)
            if "Complete" not in res:
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

    def __init__(self, modules_info, plan_modules, firmwares, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Редактирование сценария прошивки")
        self.resize(1600, 820)
        self.config = config
        self.firmwares = firmwares
        self.fw_by_type = {}
        for fw in firmwares:
            mt = fw.get("module_type", "").upper()
            if mt:
                self.fw_by_type.setdefault(mt, []).append(fw)

        plan_by_slot = {m['slot']: m for m in plan_modules}
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
                "img_type": plan.get('img_type', 'apply') or 'apply',
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
            combo.addItems(["apply", "boot"])
            combo.setCurrentText(row['img_type'])
            combo.currentTextChanged.connect(lambda text, idx=i: self._update_row(idx))
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
        self.autofill_btn = QPushButton("Автозаполнение")
        self.autofill_btn.setObjectName("autofill_btn")
        self.autofill_btn.clicked.connect(self.autofill)
        btn_layout.addWidget(self.autofill_btn)

        self.select_all_btn = QPushButton("Выбрать все")
        self.select_all_btn.setObjectName("dialog_btn_ok")
        self.select_all_btn.clicked.connect(self.select_all)
        btn_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Снять все")
        self.deselect_all_btn.setObjectName("dialog_btn_cancel")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        btn_layout.addWidget(self.deselect_all_btn)

        # Массовая установка типа прошивки по всем строкам (для full-прошивок;
        # для apply-/boot-директорий combo остаётся в допустимом состоянии)
        self.set_apply_btn = QPushButton("apply")
        self.set_apply_btn.setObjectName("dialog_btn_cancel")
        self.set_apply_btn.setToolTip("Выставить тип прошивки 'apply' во всех строках")
        self.set_apply_btn.clicked.connect(lambda: self.set_all_img_types("apply"))
        btn_layout.addWidget(self.set_apply_btn)

        self.set_boot_btn = QPushButton("boot")
        self.set_boot_btn.setObjectName("dialog_btn_cancel")
        self.set_boot_btn.setToolTip("Выставить тип прошивки 'boot' во всех строках")
        self.set_boot_btn.clicked.connect(lambda: self.set_all_img_types("boot"))
        btn_layout.addWidget(self.set_boot_btn)

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

        full  → доступны apply и boot (выбор сохраняется);
        apply → только apply; boot → только boot;
        пустой путь / неflashable → combo неактивен.
        """
        row = self.rows[idx]
        combo = self.type_combos[idx]
        path = self.path_edits[idx].text().strip()
        if not path or not row.get("flashable", True):
            combo.setEnabled(False)
            return
        combo.setEnabled(True)
        allowed = allowed_img_types(row.get('source'))
        cur = combo.currentText()
        combo.blockSignals(True)
        items = ["apply", "boot"]
        combo.clear()
        combo.addItems(items)
        for it in items:
            combo.model().item(combo.findText(it)).setEnabled(it in allowed)
        target = cur if cur in allowed else allowed[0]
        combo.setCurrentText(target)
        row['img_type'] = target
        combo.blockSignals(False)

    def _update_row(self, idx):
        row = self.rows[idx]
        fw = row.get('local_fw')

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
            bg_color = "#c8e6c9"
            if self.checkboxes[idx].isChecked():
                self.checkboxes[idx].blockSignals(True)
                self.checkboxes[idx].setChecked(False)
                self.checkboxes[idx].blockSignals(False)
                bg_color = "#e0e0e0"

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

    def autofill(self):
        filled = 0
        for i, row in enumerate(self.rows):
            # Резервы широких модулей и недоступные для прошивки слоты
            # автозаполнением не обрабатываются (их пути должны оставаться пустыми)
            if not row.get("flashable", True):
                continue
            mt = row['module_type'].upper()
            if mt in ("NA", ""):
                continue
            candidates = self.fw_by_type.get(mt, [])
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
            self._update_row(i)
            filled += 1
        # После автозаполнения: сначала снять весь выбор, затем выбрать все
        # подходящие строки (flashable + непустой путь)
        self.deselect_all()
        self.select_all()
        QMessageBox.information(self, "Автозаполнение", f"Заполнено путей: {filled}")

    def _is_selectable(self, idx):
        """Строка подлежит выбору: модуль прошивается и путь к файлу указан."""
        row = self.rows[idx]
        if not row.get("flashable", True):
            return False
        return bool(self.path_edits[idx].text().strip())

    def select_all(self):
        """Выбирает только строки, удовлетворяющие условиям прошивки:
        модуль доступен (есть SN, не резерв широкого модуля) и заполнен путь
        к файлу прошивки; при совпадении версий выбор тоже снимается."""
        for i, cb in enumerate(self.checkboxes):
            if self._is_selectable(i):
                cb.setChecked(True)
            else:
                cb.blockSignals(True)
                cb.setChecked(False)
                cb.blockSignals(False)
            self._update_row(i)

    def deselect_all(self):
        for i, cb in enumerate(self.checkboxes):
            cb.setChecked(False)
            self._update_row(i)

    def set_all_img_types(self, img_type):
        """Кнопки 'apply'/'boot': выставляют тип прошивки во всех строках.

        Для строк с путём из директории apply/ или boot/ значение остаётся
        допустимым (только своим) — _apply_combo_for_source сам вернёт
        разрешённый тип; для full-строк устанавливается выбранный тип.
        """
        for i in range(len(self.rows)):
            combo = self.type_combos[i]
            if combo.isEnabled():
                combo.setCurrentText(img_type)
            self._update_row(i)

    def _validate_row(self, idx):
        row = self.rows[idx]
        if not row.get("flashable", True):
            reason = row.get("unflash_reason") or "прошивка невозможна"
            return False, f"Слот {row['slot']}: {reason} — прошивка модуля запрещена"
        path = self.path_edits[idx].text().strip()
        if not path:
            return False, f"Слот {row['slot']}: путь к файлу не указан"
        filename = os.path.basename(path)
        parsed = parse_firmware_filename(filename)
        if parsed is None:
            return False, f"Слот {row['slot']}: файл '{filename}' не соответствует формату имени прошивки"
        if parsed['module_type'] != row['module_type'].upper():
            return False, (f"Слот {row['slot']}: прошивка '{filename}' (тип {parsed['module_type']}) "
                           f"не соответствует типу модуля {row['module_type']}")
        # Тип прошивки должен быть допустим для директории-источника:
        # apply/ -> только apply, boot/ -> только boot, full/ -> apply или boot.
        source = row.get('source') or detect_fw_source(path)
        img_type = self.type_combos[idx].currentText()
        if img_type not in allowed_img_types(source):
            return False, (f"Слот {row['slot']}: тип '{img_type}' недопустим для прошивки из "
                           f"директории '{source or 'неизвестна'}' "
                           f"(допустимо: {', '.join(allowed_img_types(source))})")
        return True, ""

    def apply_edit(self):
        selected = []
        for i, row in enumerate(self.rows):
            if not self.checkboxes[i].isChecked():
                continue
            if not row.get("flashable", True):
                # Защита от программной установки галочки — такой модуль не прошивается
                reason = row.get("unflash_reason") or "прошивка невозможна"
                QMessageBox.critical(
                    self, "Ошибка валидации",
                    f"Слот {row['slot']}: {reason} — прошивка невозможна")
                return
            row['path'] = self.path_edits[i].text().strip()
            row['img_type'] = self.type_combos[i].currentText()
            ok, err = self._validate_row(i)
            if not ok:
                QMessageBox.critical(self, "Ошибка валидации", err)
                return
            selected.append(row)

        if not selected:
            QMessageBox.warning(self, "Внимание", "Не выбрано ни одного модуля для прошивки")
            return

        # Корень сценария прошивки — <Root> (по требованию бэкенда; раньше был <Plan>)
        root = ET.Element("Root")
        for row in selected:
            ET.SubElement(root, "Image", {
                "module_slot": row['slot'],
                "module_type": row['module_type'],
                "path": row['path'],
                "type": row['img_type']
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
            QMessageBox.information(self, "Успех", "Сценарий успешно сохранён на устройстве")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить сценарий: {e}")


# ============================================================
# ГЛАВНОЕ ОКНО
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
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
        conn_layout.addWidget(QLabel("Директория агента:"), 1, 0)
        self.agent_edit = QLineEdit()
        conn_layout.addWidget(self.agent_edit, 1, 1, 1, 2)
        self.agent_btn = QPushButton("Обзор...")
        self.agent_btn.setObjectName("browse_btn")
        self.agent_btn.clicked.connect(lambda: self.browse_dir(self.agent_edit))
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
        conn_layout.addWidget(QLabel("API путь:"), 4, 0)
        self.api_path_edit = QLineEdit()
        self.api_path_edit.setPlaceholderText("/vx3/backend.fcgi")
        conn_layout.addWidget(self.api_path_edit, 4, 1, 1, 2)
        conn_group.setLayout(conn_layout)
        main_layout.addWidget(conn_group)

        ops_group = QGroupBox("Операции")
        ops_layout = QGridLayout()
        col1_ops = [
            (1, "Загрузить агента", "col1_btn_1"),
            (10, "Информация о модулях", "col1_btn_10"),
            (6, "Запустить прошивку", "col1_btn_6"),
            (8, "Просмотр результата", "col1_btn_8"),
            (7, "Выгрузить дамп", "col1_btn_7")
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
            (9, "Редактировать СП", "col2_btn_9")
        ]
        for i, (op_id, text, obj_name) in enumerate(col2_ops):
            btn = QPushButton(text)
            btn.setObjectName(obj_name)
            btn.clicked.connect(lambda checked, oid=op_id: self.start_operation(oid))
            ops_layout.addWidget(btn, i, 1)
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
        self.clear_log_btn = QPushButton("Очистить лог")
        self.clear_log_btn.setObjectName("clear_btn")
        self.clear_log_btn.clicked.connect(self.log_text.clear)
        bottom_layout.addWidget(self.clear_log_btn)
        main_layout.addLayout(bottom_layout)

        self.all_ops = [(op_id, text) for op_id, text, _ in col1_ops + col2_ops]

    def browse_dir(self, line_edit):
        dir_path = QFileDialog.getExistingDirectory(self, "Выберите директорию")
        if dir_path:
            line_edit.setText(dir_path)
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
            "api_path": self.api_path_edit.text()
        }
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)

    def load_settings_to_ui(self):
        self.ip_edit.setText(self.config.get("ip", ""))
        self.pass_edit.setText(self.config.get("password", ""))
        self.agent_edit.setText(self.config.get("agent_dir", ""))
        self.fw_edit.setText(self.config.get("firmware_dir", ""))
        self.plan_edit.setText(self.config.get("plan_xml", ""))
        self.api_path_edit.setText(self.config.get("api_path", "/vx3/backend.fcgi"))

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
            "api_path": self.api_path_edit.text()
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

    def start_operation(self, op_id):
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
            if not self.check_agent_exists():
                QMessageBox.critical(self, "Ошибка",
                                     "Агент IskraIO_Util отсутствует. Сначала выполните 'Загрузить агента'.")
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

        self.progress_bar.setValue(0)
        op_name = next((name for oid, name in self.all_ops if oid == op_id), f"ID {op_id}")
        self.append_log(f"--- Запущена операция: {op_name} ---")

        self.worker = OperationWorker(op_id, config)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.progress_bar.setValue)
        self.worker.finished_signal.connect(self.on_operation_finished)
        self.worker.start()

    def on_operation_finished(self, success, message, data):
        if not success:
            QMessageBox.critical(self, "Ошибка", message)
            return
        action = data.get("action")

        if action == "result":
            dialog = ViewResultDialog(data["modules"], data["results"], self)
            dialog.exec()
        elif action == "edit":
            dialog = EditSPDialog(
                data["modules_info"],
                data["plan_modules"],
                data["firmwares"],
                self.get_current_config(),
                self
            )
            result = dialog.exec()
            if hasattr(self, '_pending_make_plan') and self._pending_make_plan:
                self._pending_make_plan = False
                if result == QDialog.DialogCode.Accepted:
                    self.append_log("--- Запуск редактора СП после создания сценария ---")
                    self.start_operation(9)
        elif action == "module_info":
            dialog = ModuleInfoDialog(data["modules"], self)
            dialog.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
