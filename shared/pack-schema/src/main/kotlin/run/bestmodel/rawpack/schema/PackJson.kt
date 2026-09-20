package run.bestmodel.rawpack.schema

import kotlinx.serialization.json.Json

/** The one Json configuration every rawpack component uses: strict on the phone, strict on the server. */
object PackJson {
    val strict: Json = Json {
        ignoreUnknownKeys = false
        explicitNulls = false
        encodeDefaults = true
        prettyPrint = false
    }

    /** For capture.jsonl lines: the contract permits extra Camera2 keys, so unknown keys are tolerated here only. */
    val lenient: Json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        encodeDefaults = true
        prettyPrint = false
    }

    /** Loads the JSON Schema shipped in this module — the single source the Python/Bend stages also read. */
    fun schemaText(): String =
        PackJson::class.java.getResourceAsStream("/rawpack/pack.schema.json")
            ?.bufferedReader()?.use { it.readText() }
            ?: error("pack.schema.json missing from resources")
}
