import json

from asteroid.core import settings as st


def test_new_settings_need_first_launch(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "en_US")
    s = st.load_settings()
    assert not s.configured and s.language == "en"
    assert s.paraview_command == "paraview --script={script}"


def test_existing_settings_kept_in_french(monkeypatch):
    monkeypatch.setenv("LANGUAGE", "en_US")
    path = st.settings_path()
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"paraview_command": "/opt/pv/bin/paraview --script={script}"}))
    s = st.load_settings()
    assert s.configured and s.language == "fr" and s.paraview_command.startswith("/opt/pv")


def test_portable_home(tmp_path, monkeypatch):
    monkeypatch.delenv("ASTEROID_CONFIG_DIR")
    monkeypatch.setenv("ASTEROID_HOME", str(tmp_path))
    assert st.config_dir() == tmp_path / "config"
    assert st.user_dir("materiaux") == tmp_path / "materiaux"
