import Foundation

public struct AppConfig: Equatable, Sendable {
    public let apiBaseURL: URL
    public let webBaseURL: URL
    public let projectSlug: String
    public let timezone: String

    public init(
        apiBaseURL: URL,
        webBaseURL: URL,
        projectSlug: String,
        timezone: String
    ) {
        self.apiBaseURL = apiBaseURL
        self.webBaseURL = webBaseURL
        self.projectSlug = projectSlug
        self.timezone = timezone
    }

    public static func load(
        environment: [String: String] = ProcessInfo.processInfo.environment,
        timezoneIdentifier: String = TimeZone.current.identifier
    ) -> AppConfig {
        let api = URL(
            string: environment["CONTENTENGINE_API_URL"] ?? "http://127.0.0.1:8000"
        )!
        let web = URL(
            string: environment["CONTENTENGINE_WEB_URL"] ?? "http://127.0.0.1:3000"
        )!
        let project = environment["CONTENTENGINE_PROJECT_SLUG"] ?? "motgu"
        let timezone = environment["CONTENTENGINE_TIMEZONE"] ?? timezoneIdentifier

        return AppConfig(
            apiBaseURL: api,
            webBaseURL: web,
            projectSlug: project,
            timezone: timezone
        )
    }
}
