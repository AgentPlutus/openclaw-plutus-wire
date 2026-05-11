from plutus_wire_setup import parse_json_array


def test_parse_json_array_ignores_surrounding_text():
    payload = parse_json_array('noise\n[{"tabs": [{"slug": "ai"}]}]\nmore noise')
    assert payload[0]["tabs"][0]["slug"] == "ai"
