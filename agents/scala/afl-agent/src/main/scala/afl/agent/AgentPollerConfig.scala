package afl.agent

import java.net.InetAddress
import scala.io.Source
import scala.util.{Try, Using}

/** Configuration for the AFL agent poller.
  *
  * @param serviceName  Service identifier for server registration
  * @param serverGroup  Logical group name
  * @param serverName   Hostname (defaults to local hostname)
  * @param taskList     Task list name for routing
  * @param pollIntervalMs  Polling interval in milliseconds
  * @param maxConcurrent   Maximum concurrent event handlers
  * @param heartbeatIntervalMs  Heartbeat interval in milliseconds
  * @param mongoUrl    MongoDB connection string (required)
  * @param database    MongoDB database name
  */
case class AgentPollerConfig(
    serviceName: String = "afl-agent",
    serverGroup: String = "default",
    serverName: String = AgentPollerConfig.defaultHostname,
    taskList: String = "default",
    pollIntervalMs: Long = 2000,
    maxConcurrent: Int = 5,
    heartbeatIntervalMs: Long = 10000,
    mongoUrl: String,
    database: String = "afl"
)

object AgentPollerConfig:
  private[agent] def defaultHostname: String =
    Try(InetAddress.getLocalHost.getHostName).getOrElse("unknown")

  /** Load config from an afl.config.json file.
    *
    * Reads the mongodb.url and mongodb.database fields. Falls back to
    * environment variables and then built-in defaults.
    */
  def fromConfig(path: String): AgentPollerConfig =
    val content = Using(Source.fromFile(path))(_.mkString).getOrElse(
      throw new IllegalArgumentException(s"Cannot read config file: $path")
    )
    fromJsonString(content)

  /** Parse config from a JSON string (afl.config.json content). */
  def fromJsonString(json: String): AgentPollerConfig =
    // Minimal JSON parsing — extract mongodb fields without a JSON library dependency.
    val url = extractField(json, "url")
      .orElse(sys.env.get("AFL_MONGODB_URL"))
      .getOrElse("mongodb://localhost:27017")
    val database = extractField(json, "database")
      .orElse(sys.env.get("AFL_MONGODB_DATABASE"))
      .getOrElse("afl")
    AgentPollerConfig(mongoUrl = url, database = database)

  /** Resolve config using the standard search order from the protocol spec. */
  def resolve(explicitPath: Option[String] = None): AgentPollerConfig =
    val path = explicitPath
      .orElse(sys.env.get("AFL_CONFIG"))
      .orElse(findConfigFile())
    path match
      case Some(p) => fromConfig(p)
      case None    => fromEnvironment()

  /** Build config purely from environment variables. */
  def fromEnvironment(): AgentPollerConfig =
    AgentPollerConfig(
      mongoUrl = sys.env.getOrElse(
        "AFL_MONGODB_URL",
        "mongodb://localhost:27017"
      ),
      database = sys.env.getOrElse("AFL_MONGODB_DATABASE", "afl")
    )

  private def findConfigFile(): Option[String] =
    val candidates = Seq(
      "afl.config.json",
      sys.props.get("user.home").map(_ + "/.afl/afl.config.json").getOrElse(""),
      "/etc/afl/afl.config.json"
    ).filter(_.nonEmpty)
    candidates.find(p => new java.io.File(p).isFile)

  private[agent] def extractField(json: String, field: String): Option[String] =
    val pattern = s""""$field"\\s*:\\s*"([^"]+)"""".r
    pattern.findFirstMatchIn(json).map(_.group(1))
