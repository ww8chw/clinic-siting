from __future__ import annotations

# 競爭對手分類：把 Google Places 點位分到互斥類別。
# 動機：台灣診所招牌字幾乎都含「診所」，是比 Google type 更可靠的訊號；
# 而醫美/美容/牙醫/中醫雖也被 Google 標為 medical_clinic，需用名稱再分流。

DENTAL_NAME = ("牙醫", "牙科")
TCM_NAME = ("中醫",)
# 醫美與美容（醫美科的競爭池）：醫療美容診所 + 皮膚科 + 美容/SPA/美甲/紋繡 等
AESTHETIC_NAME = (
    "醫美", "醫學美容", "醫療美容", "整形", "微整", "皮膚",
    "美容", "美學", "做臉", "美妍", "紋繡", "美睫", "美甲", "除毛", "除色",
)
AESTHETIC_TYPES = {
    "skin_care_clinic", "beauty_salon", "spa", "massage_spa",
    "nail_salon", "hair_care", "wellness_center", "massage",
}


def classify_place(name: str, types) -> str:
    """把一個地點分到競爭類別之一：
    - dental：牙醫/牙科（兩池皆排除）
    - tcm：中醫（西醫一般診所池排除）
    - aesthetic：醫美/美容/SPA 等（醫美科競爭池）
    - western：西醫一般診所（家醫/功能/減重/精神競爭池；招牌含「診所/專科」且非「醫院」）
    - other：醫院（屬錨點）、健身、其他非診所
    """
    name = name or ""
    tset = set(types or ())

    if any(k in name for k in DENTAL_NAME):
        return "dental"
    if any(k in name for k in TCM_NAME):
        return "tcm"
    if any(k in name for k in AESTHETIC_NAME):
        return "aesthetic"
    if ("診所" in name or "專科" in name) and "醫院" not in name:
        return "western"
    if tset & AESTHETIC_TYPES:
        return "aesthetic"
    return "other"
