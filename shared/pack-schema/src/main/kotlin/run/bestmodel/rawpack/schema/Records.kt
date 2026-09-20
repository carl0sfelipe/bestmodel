package run.bestmodel.rawpack.schema

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/**
 * One line of capture.jsonl (`$defs/CaptureRecord`). The schema allows extra Camera2 keys
 * (additionalProperties: true) so the phone never drops information; decode these lines with
 * [PackJson.lenient] — the file on disk stays complete, the model reads the contract fields.
 */
@Serializable
data class CaptureRecord(
    @SerialName("frame_index") val frameIndex: Int,
    @SerialName("timestamp_ns") val timestampNs: Long,
    @SerialName("exposure_ns") val exposureNs: Long,
    val iso: Int,
    @SerialName("frame_duration_ns") val frameDurationNs: Long,
    @SerialName("focus_distance_diopters") val focusDistanceDiopters: Double? = null,
    val aperture: Double? = null,
    @SerialName("rolling_shutter_skew_ns") val rollingShutterSkewNs: Long? = null,
    @SerialName("ois_samples") val oisSamples: List<OisSample> = emptyList(),
    @SerialName("noise_profile") val noiseProfile: List<List<Double>>? = null,
    @SerialName("black_level") val blackLevel: List<Double>? = null,
    @SerialName("white_level") val whiteLevel: Int? = null,
    @SerialName("color_correction_gains") val colorCorrectionGains: List<Double>? = null,
    val faces: List<List<Int>> = emptyList(),
    @SerialName("scene_flicker") val sceneFlicker: String? = null,
)

@Serializable
data class OisSample(
    @SerialName("t_ns") val tNs: Long,
    val x: Double,
    val y: Double,
)

/** One line of imu.jsonl (`$defs/ImuRecord`). */
@Serializable
data class ImuRecord(
    @SerialName("t_ns") val tNs: Long,
    val kind: ImuKind,
    val x: Double,
    val y: Double,
    val z: Double,
)

@Serializable
enum class ImuKind {
    @SerialName("gyro") GYRO,
    @SerialName("accel") ACCEL,
}

/** result.json of any stage implementation (`$defs/StageResult`). */
@Serializable
data class StageResult(
    val schema: String = SCHEMA_ID,
    val stage: String,
    val impl: String,
    val version: String,
    @SerialName("inputs_sha256") val inputsSha256: String,
    val ok: Boolean,
    val outputs: List<StageOutput>,
    val metrics: StageMetrics,
    val notes: String? = null,
) {
    companion object {
        const val SCHEMA_ID = "rawpack/stage-result@1"
    }
}

@Serializable
data class StageOutput(
    val path: String,
    val kind: String,
    val sha256: String,
)

@Serializable
data class StageMetrics(
    @SerialName("wall_s") val wallS: Double,
    @SerialName("gpu_s") val gpuS: Double? = null,
)
