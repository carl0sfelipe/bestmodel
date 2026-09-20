package run.bestmodel.rawpack.schema

import java.nio.file.Files
import java.nio.file.Path
import java.security.MessageDigest

/**
 * Verifies a pack directory against its manifest: every listed file exists, has the declared size
 * and sha256, every frame path is a listed file, and nothing escapes the pack directory.
 * Used by the orchestrator's ingest (R03) and by the capture app's self-check before upload (R02).
 */
object PackVerifier {
    sealed interface Problem {
        val path: String

        data class Missing(override val path: String) : Problem
        data class SizeMismatch(override val path: String, val declared: Long, val actual: Long) : Problem
        data class ShaMismatch(override val path: String, val declared: String, val actual: String) : Problem
        data class Escapes(override val path: String) : Problem
        data class FrameNotListed(override val path: String) : Problem
    }

    data class Report(val packId: String, val problems: List<Problem>) {
        val ok: Boolean get() = problems.isEmpty()
    }

    fun readManifest(packDir: Path): Manifest =
        PackJson.strict.decodeFromString(Manifest.serializer(), Files.readString(packDir.resolve("manifest.json")))

    fun verify(packDir: Path, manifest: Manifest = readManifest(packDir)): Report {
        val root = packDir.toAbsolutePath().normalize()
        val problems = mutableListOf<Problem>()
        val listed = manifest.files.map { it.path }.toSet()

        for (entry in manifest.files) {
            val target = root.resolve(entry.path).normalize()
            if (!target.startsWith(root)) {
                problems += Problem.Escapes(entry.path)
                continue
            }
            if (!Files.isRegularFile(target)) {
                problems += Problem.Missing(entry.path)
                continue
            }
            val size = Files.size(target)
            if (size != entry.bytes) problems += Problem.SizeMismatch(entry.path, entry.bytes, size)
            val digest = sha256Hex(target)
            if (digest != entry.sha256) problems += Problem.ShaMismatch(entry.path, entry.sha256, digest)
        }
        for (frame in manifest.frames) {
            if (frame.path !in listed) problems += Problem.FrameNotListed(frame.path)
        }
        return Report(manifest.packId, problems)
    }

    fun sha256Hex(file: Path): String {
        val md = MessageDigest.getInstance("SHA-256")
        Files.newInputStream(file).use { input ->
            val buf = ByteArray(1 shl 16)
            while (true) {
                val n = input.read(buf)
                if (n < 0) break
                md.update(buf, 0, n)
            }
        }
        return md.digest().joinToString("") { "%02x".format(it) }
    }
}
