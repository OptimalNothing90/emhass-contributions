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
