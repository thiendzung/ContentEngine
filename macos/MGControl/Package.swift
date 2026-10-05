// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "MGControl",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "MGControl", targets: ["MGControlApp"])
    ],
    targets: [
        .target(
            name: "MGControlCore"
        ),
        .executableTarget(
            name: "MGControlApp",
            dependencies: ["MGControlCore"]
        ),
        .testTarget(
            name: "MGControlCoreTests",
            dependencies: ["MGControlCore"]
        )
    ],
    swiftLanguageVersions: [.v5]
)
