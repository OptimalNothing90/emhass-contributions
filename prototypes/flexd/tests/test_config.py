import pytest

from flexd.config import load_config

YAML = """
emhass_url: http://emhass:5000
timestep_min: 30
horizon_steps: 48
timezone: Europe/Berlin
data_dir: /data
stale_after_cycles: 2
mqtt:
  enabled: true
  host: mosquitto
  port: 1883
  base_topic: flexd
extra_runtime_params:
  soc_init: 0.5
standing_demands:
  - id: waterheater
    type: generic
    nominal_power_w: 3000
    daily_hours: 5
    window: "06:00-22:00"
"""


def test_load_yaml(tmp_path):
    p = tmp_path / "flexd.yaml"
    p.write_text(YAML, encoding="utf-8")
    cfg = load_config(p)
    assert cfg.emhass_url == "http://emhass:5000"
    assert cfg.mqtt.enabled is True
    assert cfg.standing_demands[0].daily_hours == 5
    assert cfg.standing_demands[0].window == ("06:00", "22:00")
    assert cfg.extra_runtime_params == {"soc_init": 0.5}


def test_env_override(tmp_path, monkeypatch):
    p = tmp_path / "flexd.yaml"
    p.write_text(YAML, encoding="utf-8")
    monkeypatch.setenv("FLEXD_EMHASS_URL", "http://other:5000")
    monkeypatch.setenv("FLEXD_MQTT_HOST", "broker2")
    cfg = load_config(p)
    assert cfg.emhass_url == "http://other:5000"
    assert cfg.mqtt.host == "broker2"


def test_standing_daily_energy_precedence(tmp_path):
    yaml_text = YAML.replace(
        "daily_hours: 5", "daily_hours: 5\n    daily_energy_wh: 9000"
    )
    p = tmp_path / "flexd.yaml"
    p.write_text(yaml_text, encoding="utf-8")
    cfg = load_config(p)
    # energy wins (spec precedence rule); hours derived: 9000/3000 = 3
    assert cfg.standing_demands[0].effective_daily_hours == 3.0


def test_bad_window_rejected(tmp_path):
    p = tmp_path / "flexd.yaml"
    p.write_text(YAML.replace("06:00-22:00", "22:00-06:00"), encoding="utf-8")
    with pytest.raises(ValueError, match="window"):
        load_config(p)


def test_bad_timezone_rejected(tmp_path):
    p = tmp_path / "flexd.yaml"
    p.write_text(YAML.replace("Europe/Berlin", "Not/A_Real_Zone"), encoding="utf-8")
    with pytest.raises(ValueError, match="timezone"):
        load_config(p)


def test_missing_file_boot_error(tmp_path):
    with pytest.raises(SystemExit, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_non_dict_root_boot_error(tmp_path):
    p = tmp_path / "flexd.yaml"
    p.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="mapping"):
        load_config(p)


def test_duplicate_standing_ids_rejected(tmp_path):
    dup = (
        YAML
        + '  - id: waterheater\n    nominal_power_w: 1000\n    daily_hours: 2\n    window: "08:00-20:00"\n'
    )
    p = tmp_path / "flexd.yaml"
    p.write_text(dup, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_config(p)


def test_duplicate_template_ids_rejected(tmp_path):
    dup = YAML + (
        "templates:\n"
        "  - id: dishwasher\n    nominal_power_w: 2000\n    energy_wh: 1400\n"
        "  - id: dishwasher\n    nominal_power_w: 1000\n    energy_wh: 700\n"
    )
    p = tmp_path / "flexd.yaml"
    p.write_text(dup, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate template"):
        load_config(p)


def test_template_id_collides_with_standing_rejected(tmp_path):
    collide = YAML + (
        "templates:\n"
        "  - id: waterheater\n    nominal_power_w: 2000\n    energy_wh: 1400\n"
    )
    p = tmp_path / "flexd.yaml"
    p.write_text(collide, encoding="utf-8")
    with pytest.raises(ValueError, match="collide"):
        load_config(p)
