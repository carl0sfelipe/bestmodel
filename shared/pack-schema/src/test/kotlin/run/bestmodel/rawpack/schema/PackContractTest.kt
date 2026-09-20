package run.bestmodel.rawpack.schema

import com.fasterxml.jackson.databind.ObjectMapper
import com.networknt.schema.JsonSchema
import com.networknt.schema.JsonSchemaFactory
import com.networknt.schema.SchemaValidatorsConfig
import com.networknt.schema.SpecVersion
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.jsonObject
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.Paths
import kotlin.io.path.readLines
import kotlin.io.path.readText
import kotlin.io.path.writeText
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.fail

/**
 * The contract test: the JSON Schema is the single definition of a pack; the Kotlin models must
 * (1) accept the fixture, (2) round-trip it byte-for-byte at the JSON tree level, and (3) never
 * accept something the schema rejects. Fixture: fixtures/pack-minimal (frames are placeholders).
 */
class PackContractTest {
    private val repoRoot: Path = generateSequence(Paths.get("").toAbsolutePath()) { it.parent }
        .first { Files.exists(it.resolve("fixtures/pack-minimal/manifest.json")) }
    private val fixture: Path = repoRoot.resolve("fixtures/pack-minimal")

    private val factory = JsonSchemaFactory.getInstance(SpecVersion.VersionFlag.V202012)
    private val mapper = ObjectMapper()
    private val schemaRoot: JsonObject = Json.parseToJsonElement(PackJson.schemaText()).jsonObject

    /** The root schema with a top-level `$ref` into one `$defs` entry — validates an instance against that definition only. */
    private fun def(name: String): JsonSchema {
        if (!schemaRoot["\$defs"]!!.jsonObject.containsKey(name)) fail("no \$defs/$name in pack.schema.json")
        val wrapped = JsonObject(schemaRoot + ("\$ref" to JsonPrimitive("#/\$defs/$name")))
        val config = SchemaValidatorsConfig.builder().build()
        return factory.getSchema(wrapped.toString(), config)
    }

    private fun assertValid(defName: String, json: String) {
        val errors = def(defName).validate(mapper.readTree(json))
        assertTrue(errors.isEmpty(), "$defName invalid: $errors")
    }

    private fun assertInvalid(defName: String, json: String) {
        val errors = def(defName).validate(mapper.readTree(json))
        assertTrue(errors.isNotEmpty(), "$defName should have been rejected: $json")
    }

    @Test
    fun `fixture manifest validates against the schema and round-trips through the Kotlin model`() {
        val text = fixture.resolve("manifest.json").readText()
        assertValid("Manifest", text)
        val model = PackJson.strict.decodeFromString(Manifest.serializer(), text)
        assertEquals("20260920T180411Z_SM-S938B_0001", model.packId)
        assertEquals(3, model.frames.size)
        val reencoded = PackJson.strict.encodeToString(Manifest.serializer(), model)
        assertEquals(canonical(text), canonical(reencoded), "Kotlin model drifted from the JSON on disk")
        assertValid("Manifest", reencoded)
    }

    @Test
    fun `every capture record parses and validates, extra vendor keys tolerated`() {
        val lines = fixture.resolve("capture.jsonl").readLines().filter { it.isNotBlank() }
        assertEquals(3, lines.size)
        for (line in lines) {
            assertValid("CaptureRecord", line)
            val rec = PackJson.lenient.decodeFromString(CaptureRecord.serializer(), line)
            assertTrue(rec.exposureNs > 0)
        }
        val first = PackJson.lenient.decodeFromString(CaptureRecord.serializer(), lines[0])
        assertEquals(1, first.oisSamples.size)
        assertEquals(4, first.noiseProfile?.size)
    }

    @Test
    fun `every imu record parses and validates`() {
        val lines = fixture.resolve("imu.jsonl").readLines().filter { it.isNotBlank() }
        assertEquals(3, lines.size)
        val kinds = lines.map {
            assertValid("ImuRecord", it)
            PackJson.strict.decodeFromString(ImuRecord.serializer(), it).kind
        }
        assertEquals(setOf(ImuKind.GYRO, ImuKind.ACCEL), kinds.toSet())
    }

    @Test
    fun `stage result fixture validates and its inputs_sha256 is the fixture manifest`() {
        val text = repoRoot.resolve("fixtures/stage-result/identity.result.json").readText()
        assertValid("StageResult", text)
        val result = PackJson.strict.decodeFromString(StageResult.serializer(), text)
        assertEquals("s0-identity", result.stage)
        assertEquals(PackVerifier.sha256Hex(fixture.resolve("manifest.json")), result.inputsSha256)
    }

    @Test
    fun `verifier accepts the fixture and names the tampered file`() {
        val report = PackVerifier.verify(fixture)
        assertTrue(report.ok, "fixture should verify clean: ${report.problems}")

        val copy = Files.createTempDirectory("rawpack-tamper")
        Files.walk(fixture).forEach { src ->
            val dst = copy.resolve(fixture.relativize(src).toString())
            if (Files.isDirectory(src)) Files.createDirectories(dst) else Files.copy(src, dst)
        }
        copy.resolve("frames/001.dng").writeText("tampered\n")
        val tampered = PackVerifier.verify(copy)
        assertTrue(!tampered.ok)
        val paths = tampered.problems.map { it.path }.toSet()
        assertEquals(setOf("frames/001.dng"), paths)
        assertTrue(tampered.problems.any { it is PackVerifier.Problem.ShaMismatch })
    }

    @Test
    fun `schema and verifier both refuse a file path that escapes the pack`() {
        val text = fixture.resolve("manifest.json").readText()
        val escaped = text.replace("\"path\": \"calib.json\"", "\"path\": \"../calib.json\"")
        assertTrue(escaped != text, "fixture must list calib.json for this test to mean anything")
        assertInvalid("Manifest", escaped)

        // Belt and braces: even if a manifest slipped past the schema, the verifier refuses it.
        val copy = Files.createTempDirectory("rawpack-escape")
        Files.walk(fixture).forEach { src ->
            val dst = copy.resolve(fixture.relativize(src).toString())
            if (Files.isDirectory(src)) Files.createDirectories(dst) else Files.copy(src, dst)
        }
        copy.resolve("manifest.json").writeText(escaped)
        val report = PackVerifier.verify(copy)
        assertTrue(report.problems.any { it is PackVerifier.Problem.Escapes && it.path == "../calib.json" }, "$report")
    }

    @Test
    fun `schema rejects what the model must never accept`() {
        assertInvalid("Manifest", """{"schema":"rawpack/manifest@2"}""")
        assertInvalid("ImuRecord", """{"t_ns":1,"kind":"magnetometer","x":0,"y":0,"z":0}""")
        assertInvalid("StageResult", """{"schema":"rawpack/stage-result@1","stage":"fuse","impl":"x","version":"1","inputs_sha256":"00","ok":true,"outputs":[],"metrics":{"wall_s":1}}""")
        assertInvalid("FileEntry", """{"path":"/abs/path.dng","kind":"raw_dng","bytes":1,"sha256":"${"a".repeat(64)}"}""")
    }

    private fun canonical(text: String): JsonElement {
        val element = Json.parseToJsonElement(text)
        return sort(element)
    }

    /** Sorted keys, explicit nulls dropped: `"x": null` and an absent `x` are the same fact under this contract. */
    private fun sort(element: JsonElement): JsonElement = when (element) {
        is JsonObject -> JsonObject(
            element.jsonObject.filterValues { it !is JsonNull }.toSortedMap().mapValues { sort(it.value) },
        )
        is kotlinx.serialization.json.JsonArray -> kotlinx.serialization.json.JsonArray(element.map { sort(it) })
        else -> element
    }
}
