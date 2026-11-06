# Copyright (c) 2025 Mortal004
# All rights reserved.
# This software is provided for non-commercial use only.
# For more information, see the LICENSE file in the root directory of this project.

import os
import time
import traceback

from core import paths


def send_error(txt):
    """把错误堆栈追加写入用户数据目录下的 error.log。

    不能用 logging.basicConfig —— 打包后 start.py 在导入阶段已经配置过 root logger，
    basicConfig 变成空操作，error.log 永远不生成。这里直接写文件，
    并且用追加模式，避免多账号并发时互相覆盖。
    路径必须用 paths.root_data()：打包后 exe 旁边可能是只读目录。
    """
    try:
        path = paths.root_data('error.log')
        os.makedirs(paths.DATA_ROOT, exist_ok=True)
        with open(path, 'a', encoding='utf-8') as f:
            f.write('%s - ERROR\n%s\n\n' % (time.strftime('%Y-%m-%d %H:%M:%S'), txt))
    except Exception:
        pass


if __name__ == '__main__':
    try:
        你好
    except Exception:
        send_error(traceback.format_exc())
