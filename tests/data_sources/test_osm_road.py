from clinic_siting.data_sources.osm_road import (
    build_nearest_road_query,
    parse_roads,
)


def test_build_nearest_road_query_has_filters():
    q = build_nearest_road_query(25.0461974, 121.3918275, 150)
    assert "around:150" in q
    assert "highway" in q
    assert "[out:json]" in q
    # 只要具名道路（排除無名巷弄/人行道）
    assert "name" in q


def test_parse_roads_extracts_class_and_lanes():
    raw = {"elements": [
        {"type": "way", "tags": {"highway": "tertiary", "name": "文桃路",
                                  "lanes": "4"}},
        {"type": "way", "tags": {"highway": "unclassified", "name": "樂善二路",
                                  "lanes": "4"}},
        {"type": "way", "tags": {"highway": "residential", "name": "郵園路"}},
        # 無 highway → 略過
        {"type": "way", "tags": {"name": "某建物"}},
    ]}
    roads = parse_roads(raw)
    names = {r["name"] for r in roads}
    assert names == {"文桃路", "樂善二路", "郵園路"}
    by_name = {r["name"]: r for r in roads}
    assert by_name["文桃路"]["highway"] == "tertiary"
    assert by_name["文桃路"]["lanes"] == 4
    assert by_name["郵園路"]["lanes"] is None


def test_parse_roads_empty():
    assert parse_roads({"elements": []}) == []
