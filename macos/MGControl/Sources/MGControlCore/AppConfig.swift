import Foundation

public struct AppConfig: Equatable, Sendable {
    public let apiBaseURL: URL
    public let webBaseURL: URL
    public let projectSlug: String
    public let timezone: String
    public let repoRoot: URL

    public init(
        apiBaseURL: URL,
        webBaseURL: URL,
        projectSlug: String,
        timezone: String,
        repoRoot: URL
    ) {
        self.apiBaseURL = apiBaseURL
        self.webBaseURL = webBaseURL
        self.projectSlug = projectSlug
        self.timezone = timezone
        self.repoRoot = repoRoot
    }

    public static func load(
        environment: [String: String] = ProcessInfo.processInfo.environment,
        timezoneIdentifier: String = TimeZone.current.identifier,
        fileManager: FileManager = .default,
        bundleURL: URL = Bundle.main.bundleURL
    ) -> AppConfig {
        let api = URL(
            string: environment["CONTENTENGINE_API_URL"] ?? "http://127.0.0.1:8000"
        )!
        let web = URL(
            string: environment["CONTENTENGINE_WEB_URL"] ?? "http://127.0.0.1:3000"
        )!
        let project = environment["CONTENTENGINE_PROJECT_SLUG"] ?? "motgu"
        let timezone = environment["CONTENTENGINE_TIMEZONE"] ?? timezoneIdentifier
        let repoRoot = resolveRepoRoot(
            environment: environment,
            fileManager: fileManager,
            bundleURL: bundleURL
        )

        return AppConfig(
            apiBaseURL: api,
            webBaseURL: web,
            projectSlug: project,
            timezone: timezone,
            repoRoot: repoRoot
        )
    }

    public static func resolveRepoRoot(
        environment: [String: String],
        fileManager: FileManager = .default,
        bundleURL: URL = Bundle.main.bundleURL
    ) -> URL {
        if let explicit = environment["CONTENTENGINE_REPO_ROOT"]?.trimmingCharacters(
            in: .whitespacesAndNewlines
        ), !explicit.isEmpty {
            return URL(fileURLWithPath: explicit, isDirectory: true)
                .standardizedFileURL
        }

        if bundleURL.pathExtension == "app" {
            return bundleURL.deletingLastPathComponent().standardizedFileURL
        }

        let cwd = URL(
            fileURLWithPath: fileManager.currentDirectoryPath,
            isDirectory: true
        )
        if let found = findRepoRoot(from: cwd, fileManager: fileManager) {
            return found
        }

        let executableDirectory = bundleURL.deletingLastPathComponent()
        if let found = findRepoRoot(
            from: executableDirectory,
            fileManager: fileManager
        ) {
            return found
        }

        return cwd.standardizedFileURL
    }

    private static func findRepoRoot(
        from start: URL,
        fileManager: FileManager
    ) -> URL? {
        var candidate = start.standardizedFileURL

        for _ in 0..<10 {
            let backend = candidate.appending(path: "backend")
            let frontend = candidate.appending(path: "frontend")
            let package = candidate.appending(path: "macos/MGControl/Package.swift")

            if fileManager.fileExists(atPath: backend.path),
               fileManager.fileExists(atPath: frontend.path),
               fileManager.fileExists(atPath: package.path) {
                return candidate
            }

            let parent = candidate.deletingLastPathComponent()
            if parent.path == candidate.path {
                break
            }
            candidate = parent
        }

        return nil
    }
}
