from clinic_siting.analysis.competition import classify_place


def test_western_general_clinic():
    assert classify_place("樂安診所(內兒科、減重、健檢)", ["medical_clinic"]) == "western"
    assert classify_place("微笑親子耳鼻喉科診所", ["doctor"]) == "western"


def test_dental_excluded():
    assert classify_place("長春藤牙醫診所", ["dental_clinic"]) == "dental"
    assert classify_place("○○牙科", ["medical_clinic"]) == "dental"


def test_tcm_excluded():
    assert classify_place("龜山文學風澤中醫診所", ["medical_clinic"]) == "tcm"


def test_aesthetic_by_name():
    assert classify_place("順風美醫診所 林口旗艦館 醫美", ["medical_clinic"]) == "aesthetic"
    assert classify_place("晴光皮膚專科診所", ["doctor"]) == "aesthetic"
    assert classify_place("曼森美 做臉/痘痘", ["medical_clinic"]) == "aesthetic"


def test_aesthetic_by_type_without_clinic_name():
    assert classify_place("沐晨美學SPA館", ["beauty_salon", "spa"]) == "aesthetic"
    assert classify_place("Meow2 美甲工作室", ["nail_salon"]) == "aesthetic"


def test_hospital_is_not_western_competition():
    # 醫院屬互補錨點，不算西醫一般診所競爭
    assert classify_place("長庚醫療財團法人林口長庚紀念醫院", ["hospital"]) == "other"


def test_unrelated_is_other():
    assert classify_place("瓦特健身工作室", ["gym"]) == "other"
    assert classify_place("全方位救護車事業股份有限公司", ["establishment"]) == "other"
