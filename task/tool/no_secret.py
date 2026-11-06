import base64
import hashlib
import re
import os
import tempfile
import uuid
from xml.dom.minidom import parse

import unicodedata
# 自定义包

# 第三方包
from selenium.webdriver.common.by import By
from fontTools.ttLib import TTFont

from task.tool import file
from core import paths


class DecodeSecret:
    # 参数 statusCode 表示是否开启加密字符解密
    # statusCode 可取三个值分别是 0、1、2
    #   0 表示不启用解密
    #   1 表示启用解密
    #   2 表示程序自动判断是否解密
    def __init__(self, statusCode):
        if statusCode not in (0, 1, 2):
            raise Exception("实例化 DecodeSecret 对象时传入错误参数 " + str(statusCode) + ",可传入数据有：0, 1, 2")
        self._statusCode = statusCode
        self.font_dict_name = paths.asset('tool', 'font_dict.txt')
        self._secret_dict = {}
        self._font_dict = {}
        self._setFontDict()

    # 获取页面 font_face 的值
    def getFontFace(self, driver):
        if self._statusCode == 0:
            return
        fontFaceItem = driver.find_element(By.TAG_NAME, "head").find_elements(By.CSS_SELECTOR, '[type="text/css"]')
        fontFaceStr = ""
        for i in fontFaceItem:
            strData = i.get_attribute('innerHTML')
            if strData == "":
                continue
            else:
                try:
                    fontFaceStr = re.findall(";base64,(.*)'[)] format", strData)[0]
                    break
                except Exception as e:
                    print("当前 fontFace 无法解析：" + str(e), flush=True)
                    print('当前题目中含有字母或数学特殊符号，无法识别，请选择其他科目进行答题', flush=True)
                    continue
        if self._statusCode == 1:
            if fontFaceStr == "":
                # raise Exception("当前任务点无法获取 font_face 值")
                print('英语题', flush=True)
                return
        elif self._statusCode == 2:
            if fontFaceStr == "":
                self._statusCode = 0
                return
            else:
                self._statusCode = 1
        self._setSecretDict(fontFaceStr)

    """
    函数功能：解析加密后的字体数据，将字形信息和字体编码映射到 self._secret_dict 中

    参数：
        :fontFace: 页面的 @font_face 中 base64 编码的值
    """

    def _setSecretDict(self, fontFace):
        # 临时文件名必须唯一：多账号并发时两个进程同时写 .temp.ttf 会互相截断，
        # 解析出坏字形后 decoding 全错，严重时直接抛异常把整场测验打断。
        stem = 'xxxt_font_%s_%s' % (os.getpid(), uuid.uuid4().hex)
        ttf_temp_path = os.path.join(tempfile.gettempdir(), stem + '.ttf')
        xml_temp_path = os.path.join(tempfile.gettempdir(), stem + '.xml')

        try:
            # 将 fontFace 解析为临时 ttf，再转成临时 xml
            b = base64.b64decode(fontFace)
            with open(ttf_temp_path, "wb") as f:
                f.write(b)
            font = TTFont(ttf_temp_path)
            font.saveXML(xml_temp_path)

            # 将字的十进制code和字形信息映射在 self._secret_dict 中
            domTree = parse(xml_temp_path)
            rootNode = domTree.documentElement
            ttglyph_list = rootNode.getElementsByTagName("TTGlyph")
            for ttglyph in ttglyph_list:
                name = ttglyph.getAttribute('name')
                if name == ".notdef":
                    continue
                code = int(re.findall("uni(.*)", name)[0], 16)  # 10进制的值
                ttglyphStr = ""
                contour_list = ttglyph.getElementsByTagName("contour")
                for contour in contour_list:
                    ttglyphStr += contour.toxml()
                value = hashlib.md5(ttglyphStr.encode(encoding="utf-8")).hexdigest()
                self._secret_dict[code] = value
        finally:
            # 无论解析成功与否都清掉临时文件
            for path in (ttf_temp_path, xml_temp_path):
                try:
                    os.remove(path)
                except OSError:
                    pass

    """
    函数功能：读取 font_dict.txt 中的数据
        font_dict.txt 中存放的是学习平台字体加密前，字形信息的md5值和字体编码的映射
    """

    def _setFontDict(self):
        if self._statusCode == 0:
            return
        self._font_dict = file.get_json_data(self.font_dict_name)

    """
    函数功能：将加密字符串解密
    :string: 被加密的字符串
    :return: 返回解密后的字符串
    """

    def decode(self, string: str):
        # 如果不开启解密则直接返回原字符串
        if self._statusCode == 0:
            return string
        trueStr = ""
        for word in string:
            wordMD5 = self._secret_dict.get(ord(word), None)
            if wordMD5 is None:
                trueStr += word
                continue
            trueWordCode = self._font_dict.get(wordMD5, None)
            trueWor = unicodedata.normalize('NFKC', chr(trueWordCode))
            trueStr += trueWor
        return trueStr


if __name__ == '__main__':
    print(ord('长'))