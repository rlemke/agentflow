package afl.agent

import afl.agent.model.{AttributeValue, StepAttributes}
import org.mongodb.scala.bson.{BsonDocument, BsonInt32, BsonString, Document}
import org.scalatest.flatspec.AnyFlatSpec
import org.scalatest.matchers.should.Matchers

class AgentPollerSpec extends AnyFlatSpec with Matchers:

  // Unit tests that don't require a live MongoDB connection

  "AgentPoller" should "register handlers" in {
    val poller = AgentPoller(
      AgentPollerConfig(mongoUrl = "mongodb://localhost:27017")
    )
    poller.register("ns.MyEvent") { params => Map("result" -> "ok") }
    poller.register("ns.OtherEvent") { params => Map("value" -> 42) }

    poller.registeredNames should contain allOf ("ns.MyEvent", "ns.OtherEvent")
  }

  it should "have a unique server ID" in {
    val poller1 = AgentPoller(
      AgentPollerConfig(mongoUrl = "mongodb://localhost:27017")
    )
    val poller2 = AgentPoller(
      AgentPollerConfig(mongoUrl = "mongodb://localhost:27017")
    )
    poller1.serverId should not be poller2.serverId
  }

  it should "start as not running" in {
    val poller = AgentPoller(
      AgentPollerConfig(mongoUrl = "mongodb://localhost:27017")
    )
    poller.isRunning shouldBe false
  }

  it should "reject start with no handlers" in {
    val poller = AgentPoller(
      AgentPollerConfig(mongoUrl = "mongodb://localhost:27017")
    )
    an[IllegalStateException] should be thrownBy poller.start()
  }

  // --- StepAttributes extraction tests ---

  "StepAttributes.extractParams" should "extract params from a step document" in {
    val doc = Document(
      "attributes" -> Document(
        "params" -> Document(
          "query" -> Document(
            "name" -> "query",
            "value" -> "London",
            "type_hint" -> "String"
          ),
          "limit" -> Document(
            "name" -> "limit",
            "value" -> 10,
            "type_hint" -> "Long"
          )
        ),
        "returns" -> Document()
      )
    )

    val params = StepAttributes.extractParams(doc)
    params should have size 2
    params("query") shouldBe AttributeValue("query", "London", "String")
    params("limit") shouldBe AttributeValue("limit", 10, "Long")
  }

  "StepAttributes.extractReturns" should "extract returns from a step document" in {
    val doc = Document(
      "attributes" -> Document(
        "params" -> Document(),
        "returns" -> Document(
          "result" -> Document(
            "name" -> "result",
            "value" -> "success",
            "type_hint" -> "String"
          )
        )
      )
    )

    val returns = StepAttributes.extractReturns(doc)
    returns should have size 1
    returns("result") shouldBe AttributeValue("result", "success", "String")
  }

  "StepAttributes" should "handle empty attributes" in {
    val doc = Document("attributes" -> Document("params" -> Document(), "returns" -> Document()))
    StepAttributes.extractParams(doc) shouldBe empty
    StepAttributes.extractReturns(doc) shouldBe empty
  }

  it should "handle missing attributes section" in {
    val doc = Document()
    StepAttributes.extractParams(doc) shouldBe empty
    StepAttributes.extractReturns(doc) shouldBe empty
  }

  // --- AgentPollerConfig tests ---

  "AgentPollerConfig" should "have sensible defaults" in {
    val config = AgentPollerConfig(mongoUrl = "mongodb://localhost:27017")
    config.serviceName shouldBe "afl-agent"
    config.serverGroup shouldBe "default"
    config.taskList shouldBe "default"
    config.pollIntervalMs shouldBe 2000
    config.maxConcurrent shouldBe 5
    config.heartbeatIntervalMs shouldBe 10000
    config.database shouldBe "afl"
  }

  "AgentPollerConfig.fromJsonString" should "parse mongodb fields" in {
    val json =
      """{
        |  "mongodb": {
        |    "url": "mongodb://myhost:27017",
        |    "database": "afl_test"
        |  }
        |}""".stripMargin
    val config = AgentPollerConfig.fromJsonString(json)
    config.mongoUrl shouldBe "mongodb://myhost:27017"
    config.database shouldBe "afl_test"
  }

  "AgentPollerConfig.extractField" should "extract quoted values" in {
    AgentPollerConfig.extractField("""{"url": "mongodb://host"}""", "url") shouldBe
      Some("mongodb://host")
  }

  it should "return None for missing fields" in {
    AgentPollerConfig.extractField("""{"url": "x"}""", "missing") shouldBe None
  }

  // --- Protocol constant values ---

  "Protocol constants" should "have correct resume task name" in {
    Protocol.ResumeTaskName shouldBe "afl:resume"
  }

  it should "have correct execute task name" in {
    Protocol.ExecuteTaskName shouldBe "afl:execute"
  }

  it should "have correct EventTransmit state" in {
    Protocol.StepState.EventTransmit shouldBe "state.facet.execution.EventTransmit"
  }
