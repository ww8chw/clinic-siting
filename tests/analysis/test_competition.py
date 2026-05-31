from clinic_siting.analysis.competition import classify_place


def test_western_general_clinic():
    assert classify_place("樂安診所(內兒科、減重、健檢)", ["medical_clinic"]) == "western"
    assert classify_place("微笑親子耳鼻喉科診所", ["doctor"]) == "western"


def test_dental_excluded():
    assert classify_place("長春藤牙醫診所", ["dental_clinic"]) == "dental"
    assert classify_place("○○牙科", ["medical_clinic"]) == "dental"


def test_tcm_excluded():
    assert classify_place("龜山文學風澤中醫診所", ["medical_clinic"]) == "tcm"


def test_medical_aesthetic_by_name():
    # 醫療等級醫美：醫美/醫學美容診所、整形、皮膚科 → 醫美科競爭
    assert classify_place("順風美醫診所 林口旗艦館 醫美", ["medical_clinic"]) == "aesthetic"
    assert classify_place("晴光皮膚專科診所", ["doctor"]) == "aesthetic"
    assert classify_place("○○醫學美容診所", ["medical_clinic"]) == "aesthetic"
    assert classify_place("林口整形外科診所", ["doctor"]) == "aesthetic"


def test_pure_beauty_is_not_aesthetic_competition():
    # 選項2：純美容業（美甲/美髮/SPA/做臉/紋繡）非醫療，不列入醫美科競爭
    assert classify_place("曼森美 做臉/痘痘", ["medical_clinic"]) == "beauty"
    assert classify_place("沐晨美學SPA館", ["beauty_salon", "spa"]) == "beauty"
    assert classify_place("Meow2 美甲工作室", ["nail_salon"]) == "beauty"
    assert classify_place("琍都造型沙龍", ["hair_care"]) == "beauty"
    assert classify_place("A7 樂誠輕盈美學中心 海菲秀 電波", ["beauty_salon"]) == "beauty"
    # 美容沙龍常掛「皮膚管理」（韓式美容詞），不可誤判為醫療皮膚科
    assert classify_place("靚湲 A7美髮salon｜皮膚管理｜做臉", ["hair_care"]) == "beauty"
    assert classify_place("星姿態紋繡龜山店｜皮膚管理淡化細紋", ["beauty_salon"]) == "beauty"


def test_hospital_is_not_western_competition():
    # 醫院屬互補錨點，不算西醫一般診所競爭
    assert classify_place("長庚醫療財團法人林口長庚紀念醫院", ["hospital"]) == "other"


def test_unrelated_is_other():
    assert classify_place("瓦特健身工作室", ["gym"]) == "other"
    assert classify_place("全方位救護車事業股份有限公司", ["establishment"]) == "other"
