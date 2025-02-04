import configparser
import json
import re
from pathlib import Path
from typing import Dict

import pytest
import yaml

from kedro.config import BadConfigException, ConfigLoader, MissingConfigException


def _get_local_logging_config():
    return {
        "version": 1,
        "formatters": {
            "simple": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"}
        },
        "root": {"level": "INFO", "handlers": ["console"]},
        "loggers": {
            "kedro": {"level": "INFO", "handlers": ["console"], "propagate": False}
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": "INFO",
                "formatter": "simple",
                "stream": "ext://sys.stdout",
            }
        },
    }


def _write_yaml(filepath: Path, config: Dict):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    yaml_str = yaml.dump(config)
    filepath.write_text(yaml_str)


def _write_json(filepath: Path, config: Dict):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    json_str = json.dumps(config)
    filepath.write_text(json_str)


def _write_dummy_ini(filepath: Path):
    filepath.parent.mkdir(parents=True, exist_ok=True)
    config = configparser.ConfigParser()
    config["prod"] = {"url": "postgresql://user:pass@url_prod/db"}
    config["staging"] = {"url": "postgresql://user:pass@url_staging/db"}
    with filepath.open("wt") as configfile:  # save
        config.write(configfile)


@pytest.fixture
def base_config(tmp_path):
    filepath = str(tmp_path / "cars.csv")
    return {
        "trains": {"type": "MemoryDataSet"},
        "cars": {
            "type": "pandas.CSVDataSet",
            "filepath": filepath,
            "save_args": {"index": True},
        },
    }


@pytest.fixture
def local_config(tmp_path):
    filepath = str(tmp_path / "cars.csv")
    return {
        "cars": {
            "type": "pandas.CSVDataSet",
            "filepath": filepath,
            "save_args": {"index": False},
        },
        "boats": {"type": "MemoryDataSet"},
    }


@pytest.fixture
def create_config_dir(tmp_path, base_config, local_config):
    proj_catalog = tmp_path / "base" / "catalog.yml"
    local_catalog = tmp_path / "local" / "catalog.yml"
    local_logging = tmp_path / "local" / "logging.yml"
    parameters = tmp_path / "base" / "parameters.json"
    db_config_path = tmp_path / "base" / "db.ini"
    project_parameters = dict(param1=1, param2=2)

    _write_yaml(proj_catalog, base_config)
    _write_yaml(local_catalog, local_config)
    _write_yaml(local_logging, _get_local_logging_config())
    _write_json(parameters, project_parameters)
    _write_dummy_ini(db_config_path)


@pytest.fixture
def conf_paths(tmp_path):
    return [str(tmp_path / "base"), str(tmp_path / "local")]


@pytest.fixture
def proj_catalog(tmp_path, base_config):
    proj_catalog = tmp_path / "base" / "catalog.yml"
    _write_yaml(proj_catalog, base_config)


@pytest.fixture
def proj_catalog_nested(tmp_path):
    path = tmp_path / "base" / "catalog" / "dir" / "nested.yml"
    _write_yaml(path, {"nested": {"type": "MemoryDataSet"}})


use_config_dir = pytest.mark.usefixtures("create_config_dir")
use_proj_catalog = pytest.mark.usefixtures("proj_catalog")


class TestConfigLoader:
    @use_config_dir
    def test_load_local_config(self, conf_paths):
        """Make sure that configs from `local/` override the ones
        from `base/`"""
        conf = ConfigLoader(conf_paths)
        params = conf.get("parameters*")
        db_conf = conf.get("db*")
        catalog = conf.get("catalog*")

        assert params["param1"] == 1
        assert db_conf["prod"]["url"] == "postgresql://user:pass@url_prod/db"

        assert catalog["trains"]["type"] == "MemoryDataSet"
        assert catalog["cars"]["type"] == "pandas.CSVDataSet"
        assert catalog["boats"]["type"] == "MemoryDataSet"
        assert not catalog["cars"]["save_args"]["index"]

    @use_proj_catalog
    def test_load_base_config(self, tmp_path, conf_paths, base_config):
        """Test config loading if `local/` directory is empty"""
        (tmp_path / "local").mkdir(exist_ok=True)
        catalog = ConfigLoader(conf_paths).get("catalog*.yml")
        assert catalog == base_config

    @use_proj_catalog
    def test_duplicate_patterns(self, tmp_path, conf_paths, base_config):
        """Test config loading if the glob patterns cover the same file"""
        (tmp_path / "local").mkdir(exist_ok=True)
        conf = ConfigLoader(conf_paths)
        catalog1 = conf.get("catalog*.yml", "catalog*.yml")
        catalog2 = conf.get("catalog*.yml", "catalog.yml")
        assert catalog1 == catalog2 == base_config

    def test_subdirs_dont_exist(self, tmp_path, conf_paths, base_config):
        """Check the error when config paths don't exist"""
        pattern = (
            r"Given configuration path either does not exist "
            r"or is not a valid directory\: {}"
        )
        with pytest.raises(ValueError, match=pattern.format(".*base")):
            ConfigLoader(conf_paths).get("catalog*")
        with pytest.raises(ValueError, match=pattern.format(".*local")):
            proj_catalog = tmp_path / "base" / "catalog.yml"
            _write_yaml(proj_catalog, base_config)
            ConfigLoader(conf_paths).get("catalog*")

    @pytest.mark.usefixtures("create_config_dir", "proj_catalog", "proj_catalog_nested")
    def test_nested(self, tmp_path):
        """Test loading the config from subdirectories"""
        catalog = ConfigLoader(str(tmp_path / "base")).get("catalog*", "catalog*/**")
        assert catalog.keys() == {"cars", "trains", "nested"}
        assert catalog["cars"]["type"] == "pandas.CSVDataSet"
        assert catalog["cars"]["save_args"]["index"] is True
        assert catalog["nested"]["type"] == "MemoryDataSet"

    @use_config_dir
    def test_nested_subdirs_duplicate(self, tmp_path, conf_paths, base_config):
        """Check the error when the configs from subdirectories contain
        duplicate keys"""
        nested = tmp_path / "base" / "catalog" / "dir" / "nested.yml"
        _write_yaml(nested, base_config)

        pattern = (
            r"Duplicate keys found in .*catalog\.yml "
            r"and\:\n\- .*nested\.yml\: cars, trains"
        )
        with pytest.raises(ValueError, match=pattern):
            ConfigLoader(conf_paths).get("catalog*", "catalog*/**")

    def test_ignore_hidden_keys(self, tmp_path):
        """Check that the config key starting with `_` are ignored and also
        don't cause a config merge error"""
        _write_yaml(tmp_path / "base" / "catalog1.yml", {"k1": "v1", "_k2": "v2"})
        _write_yaml(tmp_path / "base" / "catalog2.yml", {"k3": "v3", "_k2": "v4"})

        conf = ConfigLoader(str(tmp_path))
        catalog = conf.get("**/catalog*")
        assert catalog.keys() == {"k1", "k3"}

        _write_yaml(tmp_path / "base" / "catalog3.yml", {"k1": "dup", "_k2": "v5"})
        pattern = (
            r"^Duplicate keys found in .*catalog3\.yml and\:\n\- .*catalog1\.yml\: k1$"
        )
        with pytest.raises(ValueError, match=pattern):
            conf.get("**/catalog*")

    def test_bad_config_syntax(self, tmp_path):
        conf_path = tmp_path / "test"
        conf_path.mkdir(parents=True, exist_ok=True)
        (conf_path / "catalog.yml").write_text("bad;config")

        pattern = f"Couldn't load config file: {conf_path / 'catalog.yml'}"
        with pytest.raises(BadConfigException, match=re.escape(pattern)):
            ConfigLoader([str(conf_path)]).get("catalog*.yml")

    def test_lots_of_duplicates(self, tmp_path):
        """Check that the config key starting with `_` are ignored and also
        don't cause a config merge error"""
        data = {str(i): i for i in range(100)}
        _write_yaml(tmp_path / "base" / "catalog1.yml", data)
        _write_yaml(tmp_path / "base" / "catalog2.yml", data)

        conf = ConfigLoader(str(tmp_path))
        pattern = r"^Duplicate keys found in .*catalog2\.yml and\:\n\- .*catalog1\.yml\: .*\.\.\.$"
        with pytest.raises(ValueError, match=pattern):
            conf.get("**/catalog*")

    @use_config_dir
    def test_same_key_in_same_dir(self, tmp_path, conf_paths, base_config):
        """Check the error if 2 files in the same config dir contain
        the same top-level key"""
        dup_json = tmp_path / "base" / "catalog.json"
        _write_json(dup_json, base_config)

        pattern = (
            r"Duplicate keys found in .*catalog\.yml "
            r"and\:\n\- .*catalog\.json\: cars, trains"
        )
        with pytest.raises(ValueError, match=pattern):
            ConfigLoader(conf_paths).get("catalog*")

    def test_empty_conf_paths(self):
        """Check the error if config paths were not specified or are empty"""
        pattern = (
            r"`conf_paths` must contain at least one path to load "
            r"configuration files from"
        )
        with pytest.raises(ValueError, match=pattern):
            ConfigLoader([])
        with pytest.raises(ValueError, match=pattern):
            ConfigLoader("")

    @use_config_dir
    def test_empty_patterns(self, conf_paths):
        """Check the error if no config patterns were specified"""
        pattern = (
            r"`patterns` must contain at least one glob pattern "
            r"to match config filenames against"
        )
        with pytest.raises(ValueError, match=pattern):
            ConfigLoader(conf_paths).get()

    @use_config_dir
    def test_no_files_found(self, conf_paths):
        """Check the error if no config files satisfy a given pattern"""
        pattern = (
            r"No files found in "
            r"\[\'.*base\', "
            r"\'.*local\'\] "
            r"matching the glob pattern\(s\): "
            r"\[\'non\-existent\-pattern\'\]"
        )
        with pytest.raises(MissingConfigException, match=pattern):
            ConfigLoader(conf_paths).get("non-existent-pattern")

    def test_duplicate_paths(self, tmp_path, caplog):
        """Check that trying to load the same environment config multiple times logs a
        warning and skips the reload"""
        paths = [str(tmp_path / "base"), str(tmp_path / "base")]
        _write_yaml(tmp_path / "base" / "catalog.yml", {"env": "base", "a": "a"})

        with pytest.warns(UserWarning, match="Duplicate environment detected"):
            conf = ConfigLoader(paths)
        assert conf.conf_paths == paths[:1]

        conf.get("catalog*", "catalog*/**")
        log_messages = [record.getMessage() for record in caplog.records]
        assert not log_messages

    def test_overlapping_patterns(self, tmp_path, caplog):
        """Check that same configuration file is not loaded more than once."""
        paths = [
            str(tmp_path / "base"),
            str(tmp_path / "dev"),
            str(tmp_path / "dev" / "user1"),
        ]
        _write_yaml(
            tmp_path / "base" / "catalog0.yml", {"env": "base", "common": "common"}
        )
        _write_yaml(
            tmp_path / "dev" / "catalog1.yml", {"env": "dev", "dev_specific": "wiz"}
        )
        _write_yaml(tmp_path / "dev" / "user1" / "catalog2.yml", {"user1_c2": True})
        _write_yaml(tmp_path / "dev" / "user1" / "catalog3.yml", {"user1_c3": True})

        catalog = ConfigLoader(paths).get("catalog*", "catalog*/**", "user1/catalog2*")
        expected_catalog = {
            "env": "dev",
            "common": "common",
            "dev_specific": "wiz",
            "user1_c2": True,
            "user1_c3": True,
        }
        assert catalog == expected_catalog

        log_messages = [record.getMessage() for record in caplog.records]
        expected_path = (tmp_path / "dev" / "user1" / "catalog2.yml").resolve()
        expected_message = (
            f"Config file(s): {expected_path} already processed, skipping loading..."
        )
        assert expected_message in log_messages
