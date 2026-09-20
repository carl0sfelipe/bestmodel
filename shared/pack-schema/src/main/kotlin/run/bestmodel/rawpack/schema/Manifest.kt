package run.bestmodel.rawpack.schema

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

/** Mirrors `$defs/Manifest` in pack.schema.json. The JSON Schema is the contract; the test suite fails if these drift. */
@Serializable
data class Manifest(
    val schema: String = SCHEMA_ID,
    @SerialName("pack_id") val packId: String,
    @SerialName("captured_at") val capturedAt: String,
    val device: Device,
    @SerialName("sensor_mode") val sensorMode: SensorMode,
    val frames: List<FrameEntry>,
    val files: List<FileEntry>,
    val notes: String? = null,
) {
    companion object {
        const val SCHEMA_ID = "rawpack/manifest@1"
    }
}

@Serializable
data class Device(
    val model: String,
    val soc: String? = null,
    val os: String,
    @SerialName("app_version") val appVersion: String,
)

@Serializable
enum class Binning {
    @SerialName("none") NONE,
    @SerialName("2x2") TWO_BY_TWO,
    @SerialName("4x4") FOUR_BY_FOUR,
}

@Serializable
data class SensorMode(
    @SerialName("camera_id") val cameraId: String,
    @SerialName("physical_camera_id") val physicalCameraId: String? = null,
    @SerialName("raw_width") val rawWidth: Int,
    @SerialName("raw_height") val rawHeight: Int,
    val binning: Binning,
    val reason: String,
)

@Serializable
enum class FrameRole {
    @SerialName("reference") REFERENCE,
    @SerialName("burst") BURST,
    @SerialName("underexposed") UNDEREXPOSED,
    @SerialName("bracket") BRACKET,
}

@Serializable
data class FrameEntry(
    val index: Int,
    val path: String,
    val role: FrameRole,
    @SerialName("timestamp_ns") val timestampNs: Long,
    @SerialName("exposure_ns") val exposureNs: Long,
    val iso: Int,
)

@Serializable
enum class FileKind {
    @SerialName("raw_dng") RAW_DNG,
    @SerialName("jpeg") JPEG,
    @SerialName("jpeg_ultrahdr") JPEG_ULTRAHDR,
    @SerialName("capture_jsonl") CAPTURE_JSONL,
    @SerialName("imu_jsonl") IMU_JSONL,
    @SerialName("calib_json") CALIB_JSON,
    @SerialName("vendor_jpeg") VENDOR_JPEG,
    @SerialName("vendor_dng") VENDOR_DNG,
    @SerialName("derived") DERIVED,
    @SerialName("other") OTHER,
}

@Serializable
data class FileEntry(
    val path: String,
    val kind: FileKind,
    val bytes: Long,
    val sha256: String,
    val derivable: Boolean? = null,
)
