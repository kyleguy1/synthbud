from pathlib import Path

from app.ingestion.presets.serum_parser import parse_serum_preset


def test_parse_serum_preset_extracts_macro_names(tmp_path: Path):
    preset_path = tmp_path / "Lead 01.fxp"
    preset_path.write_bytes(
        b"HeaderData Macro 1 Macro 2 Filter FX OSC A OSC B TailData"
    )

    parsed = parse_serum_preset(preset_path)

    assert parsed.synth_name == "Serum"
    assert parsed.parse_status.value in {"success", "partial"}
    assert "Macro 1" in parsed.macro_names

