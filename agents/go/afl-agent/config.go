// Copyright 2025 Ralph Lemke
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

package aflagent

import (
	"encoding/json"
	"io/ioutil"
	"os"
	"path/filepath"
	"time"
)

// Config holds the configuration for an AgentPoller.
type Config struct {
	// ServiceName is the service identifier for server registration.
	ServiceName string

	// ServerGroup is the logical group name.
	ServerGroup string

	// ServerName is the hostname (defaults to os.Hostname()).
	ServerName string

	// TaskList is the task list name for routing.
	TaskList string

	// PollInterval is the polling interval.
	PollInterval time.Duration

	// MaxConcurrent is the maximum number of concurrent event handlers.
	MaxConcurrent int

	// HeartbeatInterval is the heartbeat interval.
	HeartbeatInterval time.Duration

	// MongoURL is the MongoDB connection string.
	MongoURL string

	// Database is the MongoDB database name.
	Database string
}

// DefaultConfig returns a Config with default values.
func DefaultConfig() Config {
	hostname, _ := os.Hostname()
	if hostname == "" {
		hostname = "unknown"
	}

	return Config{
		ServiceName:       "afl-agent",
		ServerGroup:       "default",
		ServerName:        hostname,
		TaskList:          "default",
		PollInterval:      2 * time.Second,
		MaxConcurrent:     5,
		HeartbeatInterval: 10 * time.Second,
		MongoURL:          "mongodb://localhost:27017",
		Database:          "afl",
	}
}

// mongoConfig represents the mongodb section of afl.config.json.
type mongoConfig struct {
	URL      string `json:"url"`
	Database string `json:"database"`
}

// aflConfig represents the structure of afl.config.json.
type aflConfig struct {
	MongoDB mongoConfig `json:"mongodb"`
}

// LoadConfig loads configuration from a file path.
// Falls back to environment variables and defaults for missing fields.
func LoadConfig(path string) (Config, error) {
	cfg := DefaultConfig()

	data, err := ioutil.ReadFile(path)
	if err != nil {
		return cfg, err
	}

	var fileCfg aflConfig
	if err := json.Unmarshal(data, &fileCfg); err != nil {
		return cfg, err
	}

	if fileCfg.MongoDB.URL != "" {
		cfg.MongoURL = fileCfg.MongoDB.URL
	}
	if fileCfg.MongoDB.Database != "" {
		cfg.Database = fileCfg.MongoDB.Database
	}

	// Override with environment variables if set
	applyEnvOverrides(&cfg)

	return cfg, nil
}

// ResolveConfig resolves configuration using the standard search order:
// 1. Explicit path argument
// 2. AFL_CONFIG environment variable
// 3. afl.config.json in current directory
// 4. ~/.afl/afl.config.json
// 5. /etc/afl/afl.config.json
// 6. Environment variables
// 7. Built-in defaults
func ResolveConfig(explicitPath string) Config {
	if explicitPath != "" {
		if cfg, err := LoadConfig(explicitPath); err == nil {
			return cfg
		}
	}

	if envPath := os.Getenv("AFL_CONFIG"); envPath != "" {
		if cfg, err := LoadConfig(envPath); err == nil {
			return cfg
		}
	}

	searchPaths := []string{
		"afl.config.json",
	}

	if home, err := os.UserHomeDir(); err == nil {
		searchPaths = append(searchPaths, filepath.Join(home, ".afl", "afl.config.json"))
	}

	searchPaths = append(searchPaths, "/etc/afl/afl.config.json")

	for _, path := range searchPaths {
		if _, err := os.Stat(path); err == nil {
			if cfg, err := LoadConfig(path); err == nil {
				return cfg
			}
		}
	}

	// Fall back to environment variables and defaults
	return FromEnvironment()
}

// FromEnvironment creates a Config from environment variables.
func FromEnvironment() Config {
	cfg := DefaultConfig()
	applyEnvOverrides(&cfg)
	return cfg
}

func applyEnvOverrides(cfg *Config) {
	if url := os.Getenv("AFL_MONGODB_URL"); url != "" {
		cfg.MongoURL = url
	}
	if db := os.Getenv("AFL_MONGODB_DATABASE"); db != "" {
		cfg.Database = db
	}
}
