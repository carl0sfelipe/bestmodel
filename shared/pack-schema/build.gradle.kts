plugins {
    kotlin("jvm")
    kotlin("plugin.serialization")
}

kotlin {
    jvmToolchain(21)
}

dependencies {
    api("org.jetbrains.kotlinx:kotlinx-serialization-json:1.9.0")

    testImplementation(kotlin("test"))
    testImplementation("org.junit.jupiter:junit-jupiter:5.11.4")
    // JSON Schema validation is a TEST concern here: the schema file is the
    // contract shared with the Python/Bend stages; the Kotlin models must
    // never drift from it (the bestmodel D1 lesson: no hand-restated shapes).
    testImplementation("com.networknt:json-schema-validator:1.5.6")
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

tasks.test {
    useJUnitPlatform()
    testLogging {
        events("passed", "failed", "skipped")
        showStandardStreams = false
    }
}
