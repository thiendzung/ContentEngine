import Foundation
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public enum ContentEngineClientError: Error, Equatable {
    case invalidURL
    case invalidResponse
    case httpStatus(Int)
}

private struct OperatorCommandRequest: Encodable {
    let intent: String
    let expectedStateVersion: String
    let idempotencyKey: String

    enum CodingKeys: String, CodingKey {
        case intent
        case expectedStateVersion = "expected_state_version"
        case idempotencyKey = "idempotency_key"
    }
}

public final class ContentEngineClient {
    public let config: AppConfig
    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    public init(
        config: AppConfig,
        session: URLSession = .shared
    ) {
        self.config = config
        self.session = session
        self.decoder = JSONDecoder()
        self.encoder = JSONEncoder()
    }

    public func fetchSummary() async throws -> ControlCenterSummary {
        try await get(
            path: "/control-center/summary",
            queryItems: projectQueryItems,
            as: ControlCenterSummary.self
        )
    }

    public func fetchNeedsMe() async throws -> [NeedsMeItem] {
        try await get(
            path: "/control-center/needs-me",
            queryItems: projectQueryItems,
            as: [NeedsMeItem].self
        )
    }

    public func fetchProductionBoard() async throws -> [ProductionBoardCase] {
        try await get(
            path: "/journal/production-board",
            as: [ProductionBoardCase].self
        )
    }

    public func fetchOperatorState(caseID: UUID) async throws -> OperatorState {
        try await get(
            path: "/journal/operator/cases/\(caseID.uuidString)",
            as: OperatorState.self
        )
    }

    @discardableResult
    public func sendOperatorCommand(
        target: OperatorActionTarget
    ) async throws -> OperatorCommandResult {
        let payload = OperatorCommandRequest(
            intent: target.intent.rawValue,
            expectedStateVersion: target.stateVersion,
            idempotencyKey: Self.idempotencyKey(
                intent: target.intent,
                caseID: target.caseID
            )
        )
        return try await post(
            path: "/journal/operator/cases/\(target.caseID.uuidString)/commands",
            body: payload,
            as: OperatorCommandResult.self
        )
    }

    private var projectQueryItems: [URLQueryItem] {
        [
            URLQueryItem(name: "project_slug", value: config.projectSlug),
            URLQueryItem(name: "timezone", value: config.timezone),
        ]
    }

    private func get<T: Decodable>(
        path: String,
        queryItems: [URLQueryItem] = [],
        as type: T.Type
    ) async throws -> T {
        guard let url = makeURL(path: path, queryItems: queryItems) else {
            throw ContentEngineClientError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 4
        return try await perform(request, as: type)
    }

    private func post<Body: Encodable, T: Decodable>(
        path: String,
        body: Body,
        as type: T.Type
    ) async throws -> T {
        guard let url = makeURL(path: path, queryItems: []) else {
            throw ContentEngineClientError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 8
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)
        return try await perform(request, as: type)
    }

    private func perform<T: Decodable>(
        _ request: URLRequest,
        as type: T.Type
    ) async throws -> T {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw ContentEngineClientError.invalidResponse
        }
        guard (200..<300).contains(http.statusCode) else {
            throw ContentEngineClientError.httpStatus(http.statusCode)
        }
        return try decoder.decode(type, from: data)
    }

    private func makeURL(
        path: String,
        queryItems: [URLQueryItem]
    ) -> URL? {
        let normalized = path.hasPrefix("/") ? String(path.dropFirst()) : path
        let base = config.apiBaseURL.appending(path: normalized)
        guard !queryItems.isEmpty else { return base }

        var components = URLComponents(
            url: base,
            resolvingAgainstBaseURL: false
        )
        components?.queryItems = queryItems
        return components?.url
    }

    public static func idempotencyKey(
        intent: OperatorIntent,
        caseID: UUID,
        nonce: UUID = UUID()
    ) -> String {
        "mgctrl-\(intent.rawValue)-\(caseID.uuidString.lowercased())-\(nonce.uuidString.lowercased())"
    }

    public static func engineStatus(for error: Error) -> EngineStatus {
        if let urlError = error as? URLError {
            switch urlError.code {
            case .cannotConnectToHost, .cannotFindHost:
                return .stopped
            case .timedOut, .networkConnectionLost, .notConnectedToInternet:
                return .unknown
            default:
                return .unknown
            }
        }
        if let clientError = error as? ContentEngineClientError {
            switch clientError {
            case .httpStatus:
                return .error
            case .invalidResponse, .invalidURL:
                return .error
            }
        }
        return .error
    }
}
