from __future__ import annotations

# 競爭對手分類：把 Google Places 點位分到互斥類別。
# 動機：台灣診所招牌字幾乎都含「診所」，是比 Google type 更可靠的訊號；
# 而醫美/美容/牙醫/中醫雖也被 Google 標為 medical_clinic，需用名稱再分流。

DENTAL_NAME = ("牙醫", "牙科")
TCM_NAME = ("中醫",)
# 醫療型醫美（醫美科真正同業）：醫美/醫學美容診所、整形外科、皮膚科——具醫療等級。
# 注意：用「皮膚科/皮膚專科」而非裸「皮膚」，因美容沙龍常以「皮膚管理」命名造成誤判。
MEDICAL_AESTHETIC_NAME = (
    "醫美", "醫學美容", "醫療美容", "整形", "整型", "微整", "皮膚科", "皮膚專科",
)
# 純美容業（非醫療，不列入醫美科競爭）：美甲/美髮/SPA/紋繡/做臉/按摩等。
BEAUTY_NAME = (
    "美容", "美學", "做臉", "美妍", "紋繡", "美睫", "美甲", "除毛", "除色",
    "沙龍", "髮廊", "髮藝", "美髮", "造型", "按摩", "指壓", "油壓",
    "養生", "護膚", "美體", "SPA", "spa",
)
BEAUTY_TYPES = {
    "skin_care_clinic", "beauty_salon", "spa", "massage_spa",
    "nail_salon", "hair_care", "wellness_center", "massage",
}


def classify_place(name: str, types) -> str:
    """把一個地點分到競爭類別之一：
    - dental：牙醫/牙科（兩池皆排除）
    - tcm：中醫（西醫一般診所池排除）
    - aesthetic：醫療型醫美（醫美/醫學美容診所、整形外科、皮膚科；醫美科競爭池）
    - western：西醫一般診所（家醫/功能/減重/精神競爭池；招牌含「診所/專科」且非「醫院」）
    - beauty：純美容業（美甲/美髮/SPA/紋繡 等；非醫療，不計入任何競爭池）
    - other：醫院（屬錨點）、健身、其他非診所
    """
    name = name or ""
    tset = set(types or ())

    if any(k in name for k in DENTAL_NAME):
        return "dental"
    if any(k in name for k in TCM_NAME):
        return "tcm"
    if any(k in name for k in MEDICAL_AESTHETIC_NAME):
        return "aesthetic"
    if ("診所" in name or "專科" in name) and "醫院" not in name:
        return "western"
    if any(k in name for k in BEAUTY_NAME) or (tset & BEAUTY_TYPES):
        return "beauty"
    return "other"
