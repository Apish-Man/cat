"""Shared product catalog. Prices are cat coins, never real currency."""
from datetime import date

ITEMS = {
    "fish": dict(name="小鱼干", icon="🐟", price=12, kind="food", desc="酥酥香香，奖励今天认真工作的你。", hunger=15, joy=5),
    "freeze": dict(name="冻干", icon="🥩", price=18, kind="food", desc="一口满足，挑食的小猫也会心动。", hunger=22, joy=7),
    "puree": dict(name="猫条", icon="🍥", price=25, kind="food", desc="无法抗拒的快乐，亲密度也会增加。", hunger=18, joy=16),
    "kibble": dict(name="猫粮", icon="🥣", price=10, kind="food", desc="好好吃饭，才有力气探索桌面。", hunger=32, joy=3),
    "yarn": dict(name="毛线球", icon="🧶", price=35, kind="toy", desc="抛出去试试。捡到了，也不一定还给你。"),
    "wand": dict(name="逗猫棒", icon="🪶", price=65, kind="toy", desc="羽毛跟随光标，小猫会伏低、扑过去。"),
    "laser": dict(name="激光笔", icon="🔴", price=90, kind="toy", desc="追逐光标的小红点，激活捕猎本能。"),
    "birthday": dict(name="生日奶油", icon="🎂", price=120, kind="outfit", index=0, desc="奶油花边、粉彩围兜和一顶小尖帽。"),
    "blue": dict(name="蓝莓蝴蝶结", icon="🎀", price=100, kind="outfit", index=1, desc="蓝黄针织花边，点缀一枚红色蝴蝶结。"),
    "daisy": dict(name="小雏菊", icon="🌼", price=100, kind="outfit", index=2, desc="戴上一朵小花，桌面也有了好天气。"),
    "christmas": dict(name="圣诞暖绒", icon="🎄", price=150, kind="outfit", index=3, desc="红白针织圣诞装，12 月 24–26 日可免费领取。"),
    "newyear": dict(name="招财小猫", icon="🧧", price=150, kind="outfit", index=4, desc="红围兜和金元宝，元旦及春节期间可领取。"),
    "pig": dict(name="粉绒小猪", icon="🐷", price=110, kind="outfit", index=5, desc="软软的粉色小猪帽，今天也要懒洋洋。"),
}

# Published Chinese lunar new-year dates; unknown years still include Jan 1–3.
LUNAR_NEW_YEAR = {2026: date(2026, 2, 17), 2027: date(2027, 2, 6),
                  2028: date(2028, 1, 26), 2029: date(2029, 2, 13), 2030: date(2030, 2, 3)}

def gifts_today(today: date, birthday: str) -> list[str]:
    result = []
    if today.strftime("%m-%d") == birthday:
        result.append("birthday")
    if today.month == 12 and 24 <= today.day <= 26:
        result.append("christmas")
    lunar = LUNAR_NEW_YEAR.get(today.year)
    if (today.month == 1 and today.day <= 3) or (lunar and 0 <= (today - lunar).days <= 6):
        result.append("newyear")
    return result
