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

package afl.agent;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.io.File;
import java.net.InetAddress;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Optional;

/**
 * Configuration for AgentPoller.
 */
public record AgentPollerConfig(
        String serviceName,
        String serverGroup,
        String serverName,
        String taskList,
        long pollIntervalMs,
        int maxConcurrent,
        long heartbeatIntervalMs,
        String mongoUrl,
        String database
) {

    /**
     * Returns a configuration with default values.
     */
    public static AgentPollerConfig defaults() {
        String hostname;
        try {
            hostname = InetAddress.getLocalHost().getHostName();
        } catch (Exception e) {
            hostname = "unknown";
        }

        return new AgentPollerConfig(
                "afl-agent",
                "default",
                hostname,
                "default",
                2000,
                5,
                10000,
                "mongodb://localhost:27017",
                "afl"
        );
    }

    /**
     * Loads configuration from a JSON file.
     */
    public static AgentPollerConfig fromFile(String path) {
        AgentPollerConfig cfg = defaults();

        try {
            ObjectMapper mapper = new ObjectMapper();
            JsonNode root = mapper.readTree(new File(path));

            JsonNode mongodb = root.get("mongodb");
            if (mongodb != null) {
                String url = Optional.ofNullable(mongodb.get("url"))
                        .map(JsonNode::asText)
                        .filter(s -> !s.isEmpty())
                        .orElse(cfg.mongoUrl());
                String database = Optional.ofNullable(mongodb.get("database"))
                        .map(JsonNode::asText)
                        .filter(s -> !s.isEmpty())
                        .orElse(cfg.database());

                cfg = new AgentPollerConfig(
                        cfg.serviceName(),
                        cfg.serverGroup(),
                        cfg.serverName(),
                        cfg.taskList(),
                        cfg.pollIntervalMs(),
                        cfg.maxConcurrent(),
                        cfg.heartbeatIntervalMs(),
                        url,
                        database
                );
            }
        } catch (Exception e) {
            // Ignore file read/parse errors, use defaults
        }

        return applyEnvOverrides(cfg);
    }

    /**
     * Resolves configuration using the standard search order:
     * 1. Explicit path argument
     * 2. AFL_CONFIG environment variable
     * 3. afl.config.json in current directory
     * 4. ~/.afl/afl.config.json
     * 5. /etc/afl/afl.config.json
     * 6. Environment variables
     * 7. Built-in defaults
     */
    public static AgentPollerConfig resolve(String explicitPath) {
        if (explicitPath != null && !explicitPath.isEmpty()) {
            if (Files.exists(Path.of(explicitPath))) {
                return fromFile(explicitPath);
            }
        }

        String envPath = System.getenv("AFL_CONFIG");
        if (envPath != null && !envPath.isEmpty() && Files.exists(Path.of(envPath))) {
            return fromFile(envPath);
        }

        String[] searchPaths = {
                "afl.config.json",
                System.getProperty("user.home") + "/.afl/afl.config.json",
                "/etc/afl/afl.config.json"
        };

        for (String path : searchPaths) {
            if (Files.exists(Path.of(path))) {
                return fromFile(path);
            }
        }

        return fromEnvironment();
    }

    /**
     * Creates a configuration from environment variables.
     */
    public static AgentPollerConfig fromEnvironment() {
        return applyEnvOverrides(defaults());
    }

    private static AgentPollerConfig applyEnvOverrides(AgentPollerConfig cfg) {
        String mongoUrl = Optional.ofNullable(System.getenv("AFL_MONGODB_URL"))
                .filter(s -> !s.isEmpty())
                .orElse(cfg.mongoUrl());
        String database = Optional.ofNullable(System.getenv("AFL_MONGODB_DATABASE"))
                .filter(s -> !s.isEmpty())
                .orElse(cfg.database());

        if (!mongoUrl.equals(cfg.mongoUrl()) || !database.equals(cfg.database())) {
            return new AgentPollerConfig(
                    cfg.serviceName(),
                    cfg.serverGroup(),
                    cfg.serverName(),
                    cfg.taskList(),
                    cfg.pollIntervalMs(),
                    cfg.maxConcurrent(),
                    cfg.heartbeatIntervalMs(),
                    mongoUrl,
                    database
            );
        }
        return cfg;
    }

    /**
     * Creates a new config with a different service name.
     */
    public AgentPollerConfig withServiceName(String serviceName) {
        return new AgentPollerConfig(
                serviceName, serverGroup, serverName, taskList,
                pollIntervalMs, maxConcurrent, heartbeatIntervalMs, mongoUrl, database
        );
    }

    /**
     * Creates a new config with a different server group.
     */
    public AgentPollerConfig withServerGroup(String serverGroup) {
        return new AgentPollerConfig(
                serviceName, serverGroup, serverName, taskList,
                pollIntervalMs, maxConcurrent, heartbeatIntervalMs, mongoUrl, database
        );
    }

    /**
     * Creates a new config with a different task list.
     */
    public AgentPollerConfig withTaskList(String taskList) {
        return new AgentPollerConfig(
                serviceName, serverGroup, serverName, taskList,
                pollIntervalMs, maxConcurrent, heartbeatIntervalMs, mongoUrl, database
        );
    }

    /**
     * Creates a new config with a different max concurrent setting.
     */
    public AgentPollerConfig withMaxConcurrent(int maxConcurrent) {
        return new AgentPollerConfig(
                serviceName, serverGroup, serverName, taskList,
                pollIntervalMs, maxConcurrent, heartbeatIntervalMs, mongoUrl, database
        );
    }
}
