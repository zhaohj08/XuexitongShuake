"""多账号配置管理。

存储结构 accounts.json：
    {
      "version": 2,
      "global":   { 浏览器、驱动、API Key、字体、并发数、定时 ... },
      "accounts": [ { 手机号、密码、课程、倍速、答题策略 ... }, ... ]
    }

对外仍保留旧的扁平接口（load_account / save_account / get_account），
把「global + 当前账号」合并成一个 dict，这样 GUI 侧几乎不用改。
"""
import json
import os
import uuid

from core import paths


GLOBAL_KEYS = {
    'browser', 'driver_path', 'API', 'font_type', 'font_size', 'user_notice',
    'max_concurrency', 'timer_active', 'timer_start', 'timer_end',
    'file_name', 'current_account',
}

ACCOUNT_KEYS = {
    'alias', 'enabled', 'phone_number', 'password', 'cour', 'choice',
    'after_finish_question', 'video_title_choice', 'discussion_choice',
    'homework', 'task_type', 'speed', 'pass_face', 'pass_vido',
    'lock_screen', 'multi_device', 'radio_var',
}

DEFAULT_GLOBAL = {
    'browser': '不指定浏览器',
    'driver_path': '',
    'API': '',
    'font_type': 'Microsoft YaHei UI',
    'font_size': '12',
    'user_notice': 'True',
    'max_concurrency': 2,
    'timer_active': 0,
    'timer_start': '04:00:00',
    'timer_end': '03:00:00',
    'file_name': ['python', 'main.py'],
    'current_account': '',
}

DEFAULT_ACCOUNT = {
    'alias': '',
    'enabled': 1,
    'phone_number': '',
    'password': '',
    'cour': [''],
    'choice': '',
    'after_finish_question': '',
    'video_title_choice': '',
    'discussion_choice': '',
    'homework': '',
    'task_type': '章节',
    'speed': '',
    'pass_face': 0,
    'pass_vido': 0,
    'lock_screen': 0,
    'multi_device': 0,
    'radio_var': 1,
}

MAX_CONCURRENCY_LIMIT = 5


def _read_json(path, default):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def _write_json(path, data):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def new_account_id() -> str:
    return 'acc_' + uuid.uuid4().hex[:8]


class ConfigManager:
    def __init__(self):
        self._account_info = {}
        self._data = None
        paths.ensure_data_dirs()

    # ================= 路径（延迟求值，保证 XXT_HOME 生效后再算） =================
    @property
    def accounts_path(self) -> str:
        return paths.data('tool', 'accounts.json')

    @property
    def legacy_account_path(self) -> str:
        return paths.data('tool', 'account_info.json')

    @property
    def course_path(self) -> str:
        return paths.data('tool', 'course_name.json')

    @property
    def version_path(self) -> str:
        return paths.asset('tool', 'version_info')

    @property
    def help_path(self) -> str:
        return paths.asset('tool', 'Help.txt')

    @property
    def course_process_path(self) -> str:
        return paths.data('tool', 'course_process.json')

    # ================= 账号集合 =================
    def load_accounts(self) -> dict:
        """读取 accounts.json；不存在时从旧 account_info.json 迁移。"""
        if self._data is not None:
            return self._data

        data = _read_json(self.accounts_path, None)
        if not isinstance(data, dict) or 'accounts' not in data:
            data = self._migrate_legacy()

        data.setdefault('version', 2)
        data.setdefault('global', {})
        data.setdefault('accounts', [])
        for k, v in DEFAULT_GLOBAL.items():
            data['global'].setdefault(k, v)
        for acc in data['accounts']:
            for k, v in DEFAULT_ACCOUNT.items():
                acc.setdefault(k, v)
            acc.setdefault('id', new_account_id())

        if not data['accounts']:
            data['accounts'].append(self._blank_account('账号1'))

        cur = data['global'].get('current_account')
        if not cur or not any(a['id'] == cur for a in data['accounts']):
            data['global']['current_account'] = data['accounts'][0]['id']

        self._data = data
        # 首次运行（或迁移后）立即落盘，否则每次启动都会重新生成账号 id，
        # 导致 task/run/ 下堆积一堆空的账号工作目录
        if not os.path.exists(self.accounts_path):
            self.save_accounts(data)
        return data

    def save_accounts(self, data: dict = None) -> bool:
        data = data or self._data
        if not data:
            return False
        try:
            _write_json(self.accounts_path, data)
            self._data = data
            return True
        except OSError:
            return False

    def _blank_account(self, alias='') -> dict:
        acc = dict(DEFAULT_ACCOUNT)
        acc['id'] = new_account_id()
        acc['alias'] = alias
        acc['cour'] = ['']
        return acc

    def _migrate_legacy(self) -> dict:
        """把旧的单账号 account_info.json 迁移成新结构，旧文件保留不删。"""
        legacy = _read_json(self.legacy_account_path, {}) or {}
        g = {}
        for k in GLOBAL_KEYS:
            if k in legacy:
                g[k] = legacy[k]
        acc = self._blank_account(legacy.get('phone_number') or '账号1')
        for k in ACCOUNT_KEYS:
            if k in legacy:
                acc[k] = legacy[k]
        if not acc.get('alias'):
            acc['alias'] = acc.get('phone_number') or '账号1'
        g['current_account'] = acc['id']
        return {'version': 2, 'global': g, 'accounts': [acc]}

    # ================= 当前账号 =================
    def list_accounts(self) -> list:
        """给 GUI 用的精简列表。"""
        data = self.load_accounts()
        out = []
        for acc in data['accounts']:
            out.append({
                'id': acc['id'],
                'alias': acc.get('alias') or acc.get('phone_number') or '未命名',
                'phone': acc.get('phone_number', ''),
                'enabled': int(acc.get('enabled', 1)),
                'course_count': len([c for c in acc.get('cour', []) if c]),
            })
        return out

    def current_id(self) -> str:
        return self.load_accounts()['global'].get('current_account', '')

    def set_current(self, account_id: str) -> None:
        data = self.load_accounts()
        if any(a['id'] == account_id for a in data['accounts']):
            data['global']['current_account'] = account_id
            self.save_accounts(data)
            self._account_info = {}

    def get_account_by_id(self, account_id: str) -> dict:
        for acc in self.load_accounts()['accounts']:
            if acc['id'] == account_id:
                return acc
        return {}

    def add_account(self, alias='', phone='', password='') -> dict:
        data = self.load_accounts()
        acc = self._blank_account(alias or phone or f'账号{len(data["accounts"]) + 1}')
        acc['phone_number'] = phone
        acc['password'] = password
        data['accounts'].append(acc)
        data['global']['current_account'] = acc['id']
        self.save_accounts(data)
        self._account_info = {}
        return acc

    def remove_account(self, account_id: str) -> bool:
        data = self.load_accounts()
        if len(data['accounts']) <= 1:
            return False
        data['accounts'] = [a for a in data['accounts'] if a['id'] != account_id]
        if data['global'].get('current_account') == account_id:
            data['global']['current_account'] = data['accounts'][0]['id']
        self.save_accounts(data)
        self._account_info = {}
        return True

    # ================= 扁平接口（兼容旧调用） =================
    def load_account(self) -> dict:
        data = self.load_accounts()
        acc = self.get_account_by_id(data['global']['current_account'])
        flat = {}
        flat.update(data['global'])
        flat.update(acc)
        flat['account_id'] = acc.get('id', '')
        self._account_info = flat
        return flat

    def save_account(self, account_info: dict) -> bool:
        data = self.load_accounts()
        acc_id = account_info.get('account_id') or data['global']['current_account']
        acc = self.get_account_by_id(acc_id)
        if not acc:
            return False
        for k, v in account_info.items():
            if k in GLOBAL_KEYS:
                data['global'][k] = v
            elif k in ACCOUNT_KEYS:
                acc[k] = v
        data['global']['current_account'] = acc_id
        ok = self.save_accounts(data)
        if ok:
            self._account_info = account_info
        return ok

    def get_account(self) -> dict:
        if not self._account_info:
            self.load_account()
        return self._account_info

    # ================= 课程 =================
    def load_courses(self, phone_number: str) -> list:
        """当前账号配置里的课程 + 子进程学习过程中新发现的课程。"""
        acc = self.get_account_by_id(self.current_id())
        courses = [c for c in acc.get('cour', []) if c]
        discovered = _read_json(self.course_path, {}) or {}
        for name in discovered.get(phone_number, []) or []:
            if name and name not in courses:
                courses.append(name)
        return courses

    def save_courses(self, phone_number: str, courses: list) -> None:
        data = self.load_accounts()
        acc = self.get_account_by_id(data['global']['current_account'])
        merged = []
        for name in list(courses) + list(acc.get('cour', [])):
            if name and name not in merged:
                merged.append(name)
        acc['cour'] = merged or ['']
        self.save_accounts(data)

    # ================= 便捷读取 =================
    def get_version(self) -> str:
        try:
            with open(self.version_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except OSError:
            return '0.0.0'

    def get_help_text(self) -> str:
        try:
            with open(self.help_path, 'r', encoding='utf-8') as f:
                return f.read()
        except OSError:
            return '帮助文档未找到'

    def get_course_process(self) -> dict:
        """当前账号的课程进度；账号工作目录没有时回落到共享目录。"""
        acc_id = self.current_id()
        candidates = [
            os.path.join(paths.account_home(acc_id), 'tool', 'course_process.json'),
            self.course_process_path,
        ]
        for path in candidates:
            data = _read_json(path, None)
            if isinstance(data, dict):
                return data
        return {}

    def count_video_records(self) -> int:
        record_dir = paths.record()
        if not os.path.isdir(record_dir):
            return 0
        total = 0
        for fname in os.listdir(record_dir):
            # 兼容旧版本留下的记录文件名（转义写法）
            if fname.endswith('.txt') and ('学习记录' in fname or '\u5237\u8bfe\u8bb0\u5f55' in fname):
                try:
                    with open(os.path.join(record_dir, fname), 'r', encoding='utf-8') as f:
                        total += f.read().count('视频')
                except OSError:
                    pass
        return total

    def get_popup_count(self) -> int:
        return self.load_account().get('popup_count', 0)

    def increment_popup_count(self, video_count: int):
        account = self.load_account()
        account['popup_count'] = video_count
        self.save_account(account)

    # ================= 子进程配置 =================
    def write_account_runtime(self, account_id: str) -> str:
        """把某个账号扁平化成旧格式 account_info.json，写进它的工作目录。

        子进程通过 XXT_HOME 指向该目录，main.py 的读取逻辑无需改动。
        """
        data = self.load_accounts()
        acc = self.get_account_by_id(account_id)
        if not acc:
            return ''

        home = paths.account_home(account_id)
        tool_dir = os.path.join(home, 'tool')
        os.makedirs(tool_dir, exist_ok=True)
        os.makedirs(os.path.join(home, 'record'), exist_ok=True)

        flat = {}
        flat.update(data['global'])
        flat.update(acc)
        flat.pop('id', None)
        flat.pop('alias', None)
        flat['account_id'] = account_id
        # 多账号模式下多端学习会叠乘浏览器数量，强制关闭
        if len(data['accounts']) > 1:
            flat['multi_device'] = 0

        target = os.path.join(tool_dir, 'account_info.json')
        _write_json(target, flat)

        # 首次运行时补一份默认课程进度文件，避免子进程读不到而报错
        process_file = os.path.join(tool_dir, 'course_process.json')
        if not os.path.exists(process_file):
            _write_json(process_file, {})

        return home
