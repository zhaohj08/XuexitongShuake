"""统一视觉层：语义化色板 / 间距 / 圆角 / 字号。

GUI 模块统一从这里取色，不再各自硬编码 hex。
每个主题提供同一组语义 key，控件按"角色"取色，而不是按"第几个颜色"取色。
主题名与原 color_value_dict 保持一致，避免 account_info.json 里的历史配置失效。
"""

DEFAULT_THEME = '海洋蓝'

# ---------------- 主题色板 ----------------
# accent       主色（按钮填充、进度条、选中文字）
# accent_hover 主色悬停
# accent_soft  主色浅底（导航选中、标签底）
# bg           页面底色
# surface      卡片 / 输入框 / 导航栏底色
# surface_alt  次级填充（表头、代码块）
# border       分隔线与卡片描边
# text / text_muted / text_faint  三级文字
PALETTES = {
    '海洋蓝': dict(
        accent='#2563EB', accent_hover='#1D4ED8', accent_soft='#EFF4FF',
        bg='#F5F7FA', surface='#FFFFFF', surface_alt='#F8FAFC',
        border='#E3E8EF', text='#111827', text_muted='#4B5563', text_faint='#9CA3AF'),
    '清新绿': dict(
        accent='#15803D', accent_hover='#166534', accent_soft='#F0FDF4',
        bg='#F6F9F6', surface='#FFFFFF', surface_alt='#F8FAF8',
        border='#E2EBE3', text='#111827', text_muted='#4B5563', text_faint='#9CA3AF'),
    '暖阳橙': dict(
        accent='#C2410C', accent_hover='#9A3412', accent_soft='#FFF7ED',
        bg='#FAF7F4', surface='#FFFFFF', surface_alt='#FBF8F5',
        border='#EDE4DC', text='#111827', text_muted='#57534E', text_faint='#A8A29E'),
    '淡雅灰': dict(
        accent='#475569', accent_hover='#334155', accent_soft='#F1F5F9',
        bg='#F6F7F9', surface='#FFFFFF', surface_alt='#F8F9FB',
        border='#E2E5EA', text='#111827', text_muted='#4B5563', text_faint='#9CA3AF'),
    '天空湖': dict(
        accent='#0E7490', accent_hover='#155E75', accent_soft='#ECFEFF',
        bg='#F5FAFB', surface='#FFFFFF', surface_alt='#F7FBFC',
        border='#DDE8EA', text='#111827', text_muted='#4B5563', text_faint='#9CA3AF'),
    '深邃夜': dict(
        accent='#1E293B', accent_hover='#0F172A', accent_soft='#F1F5F9',
        bg='#F4F5F7', surface='#FFFFFF', surface_alt='#F7F8FA',
        border='#DFE3E8', text='#111827', text_muted='#4B5563', text_faint='#9CA3AF'),
    '紫罗兰': dict(
        accent='#6D28D9', accent_hover='#5B21B6', accent_soft='#F5F3FF',
        bg='#F8F7FB', surface='#FFFFFF', surface_alt='#FAF9FC',
        border='#E7E4F0', text='#111827', text_muted='#4B5563', text_faint='#9CA3AF'),
}

# 语义色（跨主题共用）
DANGER = '#DC2626'
DANGER_HOVER = '#B91C1C'
DANGER_SOFT = '#FEF2F2'
SUCCESS = '#15803D'
WARNING = '#B45309'

# ---------------- 尺度 ----------------
SPACE = {'xs': 4, 'sm': 8, 'md': 12, 'lg': 16, 'xl': 24}
RADIUS = {'sm': 6, 'md': 8, 'lg': 12}

FONT_FAMILY = 'Microsoft YaHei UI'

_current = DEFAULT_THEME


def set_current(name: str) -> None:
    """由主窗口在切换主题时调用，供没有回调参数的模块取当前色板。"""
    global _current
    if name in PALETTES:
        _current = name


def current_name() -> str:
    return _current


def palette(name: str = None) -> dict:
    """取语义色板；未知主题回落到默认主题。"""
    return PALETTES.get(name or _current, PALETTES[DEFAULT_THEME])


def theme_names() -> list:
    return list(PALETTES.keys())


def legacy_colors(name: str = None) -> list:
    """兼容旧接口：返回 [主色, 卡片色, 悬停色]，供只按索引取色的旧面板使用。"""
    p = palette(name)
    return [p['accent'], p['surface'], p['accent_hover']]


def legacy_dict() -> dict:
    """兼容旧 color_value_dict 结构。"""
    return {k: legacy_colors(k) for k in PALETTES}


def font(size: int = 12, weight: str = None) -> tuple:
    """统一字体元组，避免各模块各写一套 ("Helvetica", 13)。"""
    return (FONT_FAMILY, size) if weight is None else (FONT_FAMILY, size, weight)
