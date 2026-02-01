# Copyright 2025 Ralph Lemke
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for AFL configuration."""

import json

from afl.config import AFLConfig, MongoDBConfig, load_config


class TestMongoDBConfig:
    """Tests for MongoDBConfig."""

    def test_defaults(self):
        cfg = MongoDBConfig()
        assert cfg.url == "mongodb://localhost:27017"
        assert cfg.username == ""
        assert cfg.password == ""
        assert cfg.auth_source == "admin"
        assert cfg.database == "afl"

    def test_connection_string(self):
        cfg = MongoDBConfig()
        assert cfg.connection_string() == cfg.url

    def test_to_dict(self):
        cfg = MongoDBConfig()
        d = cfg.to_dict()
        assert d == {
            "url": "mongodb://localhost:27017",
            "username": "",
            "password": "",
            "auth_source": "admin",
            "database": "afl",
        }

    def test_from_dict(self):
        data = {
            "url": "mongodb://localhost:27017",
            "username": "user1",
            "password": "pass1",
            "auth_source": "mydb",
            "database": "custom_db",
        }
        cfg = MongoDBConfig.from_dict(data)
        assert cfg.url == "mongodb://localhost:27017"
        assert cfg.username == "user1"
        assert cfg.password == "pass1"
        assert cfg.auth_source == "mydb"
        assert cfg.database == "custom_db"

    def test_from_dict_camel_case_auth_source(self):
        data = {"authSource": "other_db"}
        cfg = MongoDBConfig.from_dict(data)
        assert cfg.auth_source == "other_db"

    def test_from_dict_partial(self):
        cfg = MongoDBConfig.from_dict({"username": "custom"})
        assert cfg.username == "custom"
        assert cfg.url == MongoDBConfig.url  # default

    def test_from_dict_database_defaults(self):
        cfg = MongoDBConfig.from_dict({"username": "x"})
        assert cfg.database == "afl"

    def test_from_env(self, monkeypatch):
        monkeypatch.setenv("AFL_MONGODB_URL", "mongodb://envhost:9999")
        monkeypatch.setenv("AFL_MONGODB_USERNAME", "envuser")
        monkeypatch.setenv("AFL_MONGODB_PASSWORD", "envpass")
        monkeypatch.setenv("AFL_MONGODB_AUTH_SOURCE", "envdb")
        monkeypatch.setenv("AFL_MONGODB_DATABASE", "envdbname")
        cfg = MongoDBConfig.from_env()
        assert cfg.url == "mongodb://envhost:9999"
        assert cfg.username == "envuser"
        assert cfg.password == "envpass"
        assert cfg.auth_source == "envdb"
        assert cfg.database == "envdbname"

    def test_from_env_defaults(self, monkeypatch):
        monkeypatch.delenv("AFL_MONGODB_URL", raising=False)
        monkeypatch.delenv("AFL_MONGODB_USERNAME", raising=False)
        monkeypatch.delenv("AFL_MONGODB_PASSWORD", raising=False)
        monkeypatch.delenv("AFL_MONGODB_AUTH_SOURCE", raising=False)
        monkeypatch.delenv("AFL_MONGODB_DATABASE", raising=False)
        cfg = MongoDBConfig.from_env()
        assert cfg.url == MongoDBConfig.url
        assert cfg.database == "afl"


class TestAFLConfig:
    """Tests for AFLConfig."""

    def test_defaults(self):
        cfg = AFLConfig()
        assert isinstance(cfg.mongodb, MongoDBConfig)

    def test_to_dict(self):
        cfg = AFLConfig()
        d = cfg.to_dict()
        assert "mongodb" in d
        assert d["mongodb"]["username"] == ""

    def test_from_dict(self):
        data = {"mongodb": {"url": "mongodb://custom:1234"}}
        cfg = AFLConfig.from_dict(data)
        assert cfg.mongodb.url == "mongodb://custom:1234"

    def test_from_dict_empty(self):
        cfg = AFLConfig.from_dict({})
        assert cfg.mongodb.url == MongoDBConfig.url


class TestLoadConfig:
    """Tests for load_config."""

    def test_load_from_explicit_path(self, tmp_path):
        config_file = tmp_path / "test.json"
        config_file.write_text(
            json.dumps(
                {
                    "mongodb": {
                        "url": "mongodb://filehost:5555",
                        "username": "fileuser",
                        "password": "filepass",
                        "authSource": "filedb",
                    }
                }
            )
        )
        cfg = load_config(str(config_file))
        assert cfg.mongodb.url == "mongodb://filehost:5555"
        assert cfg.mongodb.username == "fileuser"
        assert cfg.mongodb.auth_source == "filedb"

    def test_load_defaults_when_no_file(self, monkeypatch):
        monkeypatch.delenv("AFL_CONFIG", raising=False)
        monkeypatch.delenv("AFL_MONGODB_URL", raising=False)
        cfg = load_config()
        assert cfg.mongodb.url == MongoDBConfig.url

    def test_load_from_env_variable_path(self, tmp_path, monkeypatch):
        config_file = tmp_path / "env.json"
        config_file.write_text(json.dumps({"mongodb": {"url": "mongodb://envpath:7777"}}))
        monkeypatch.setenv("AFL_CONFIG", str(config_file))
        cfg = load_config()
        assert cfg.mongodb.url == "mongodb://envpath:7777"
