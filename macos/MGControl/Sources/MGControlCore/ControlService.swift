import Foundation

public final class ControlService {
    private let client: ContentEngineClient

    public init(client: ContentEngineClient) {
        self.client = client
    }

    public func refresh() async -> ControlSnapshot {
        let summary: ControlCenterSummary
        do {
            summary = try await client.fetchSummary()
        } catch {
            return ControlSnapshot(
                engineStatus: ContentEngineClient.engineStatus(for: error),
                summary: nil,
                needsMe: [],
                actionTargets: .empty,
                message: Self.message(for: error)
            )
        }

        do {
            async let needsTask = client.fetchNeedsMe()
            async let boardTask = client.fetchProductionBoard()

            let needs = try await needsTask
            let board = try await boardTask
            let relevant = board.filter {
                $0.operatorManaged && $0.statusGroup != "COMPLETED"
            }

            var states: [UUID: OperatorState] = [:]
            for item in relevant {
                states[item.id] = try await client.fetchOperatorState(caseID: item.id)
            }

            let targets = ActionResolver.resolve(
                board: board,
                states: states
            )
            let message = targets.isAmbiguous
                ? "Có nhiều tác vụ có thể thao tác. Mở Sản xuất để chọn đúng bài."
                : nil

            return ControlSnapshot(
                engineStatus: .running,
                summary: summary,
                needsMe: needs,
                actionTargets: targets,
                message: message
            )
        } catch {
            return ControlSnapshot(
                engineStatus: .error,
                summary: summary,
                needsMe: [],
                actionTargets: .empty,
                message: Self.message(for: error)
            )
        }
    }

    public func perform(
        target: OperatorActionTarget
    ) async throws -> OperatorCommandResult {
        try await client.sendOperatorCommand(target: target)
    }

    private static func message(for error: Error) -> String {
        if let clientError = error as? ContentEngineClientError {
            switch clientError {
            case .httpStatus(let code):
                return "ContentEngine trả lỗi HTTP \(code)."
            case .invalidResponse:
                return "Phản hồi từ ContentEngine không hợp lệ."
            case .invalidURL:
                return "Địa chỉ ContentEngine không hợp lệ."
            }
        }
        if let urlError = error as? URLError {
            switch urlError.code {
            case .cannotConnectToHost, .cannotFindHost:
                return "Không kết nối được ContentEngine."
            case .timedOut:
                return "ContentEngine phản hồi quá chậm."
            default:
                return "Chưa xác định được trạng thái ContentEngine."
            }
        }
        return "Không đọc được trạng thái ContentEngine."
    }
}
