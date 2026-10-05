import Foundation

public enum EngineStatus: Equatable, Sendable {
    case starting
    case running
    case external
    case stopped
    case error
    case unknown

    public var vietnameseLabel: String {
        switch self {
        case .starting:
            return "Đang khởi động"
        case .running:
            return "Đang chạy"
        case .external:
            return "Đang chạy ngoài MG"
        case .stopped:
            return "Đã dừng"
        case .error:
            return "Có lỗi"
        case .unknown:
            return "Không xác định"
        }
    }
}

public enum OperatorIntent: String, Codable, CaseIterable, Hashable, Sendable {
    case start
    case continueWork = "continue"
    case resume
    case retry
    case cancel
}

public struct ControlCenterCounts: Decodable, Equatable, Sendable {
    public let running: Int
    public let queued: Int
    public let blocked: Int
    public let needsHuman: Int
    public let completedToday: Int

    enum CodingKeys: String, CodingKey {
        case running
        case queued
        case blocked
        case needsHuman = "needs_human"
        case completedToday = "completed_today"
    }
}

public struct ControlCenterSummary: Decodable, Equatable, Sendable {
    public let counts: ControlCenterCounts
}

public struct NeedsMeDestination: Decodable, Equatable, Sendable {
    public let kind: String
    public let actionRef: String
    public let entityID: String
    public let href: String?

    enum CodingKeys: String, CodingKey {
        case kind
        case actionRef = "action_ref"
        case entityID = "entity_id"
        case href
    }
}

public struct NeedsMeItem: Decodable, Equatable, Identifiable, Sendable {
    public let id: String
    public let reason: String
    public let canonicalStatus: String
    public let destination: NeedsMeDestination

    enum CodingKeys: String, CodingKey {
        case id
        case reason
        case canonicalStatus = "canonical_status"
        case destination
    }
}

public struct ProductionBoardCase: Decodable, Equatable, Identifiable, Sendable {
    public let id: UUID
    public let title: String
    public let statusGroup: String
    public let operatorManaged: Bool
    public let nextAction: String

    enum CodingKeys: String, CodingKey {
        case id
        case title
        case statusGroup = "status_group"
        case operatorManaged = "operator_managed"
        case nextAction = "next_action"
    }
}

public struct OperatorState: Decodable, Equatable, Sendable {
    public let contentCaseID: UUID
    public let stateVersion: String
    public let status: String
    public let phase: String
    public let primaryIntent: OperatorIntent?
    public let allowedIntents: [OperatorIntent]
    public let blockerMessage: String?

    enum CodingKeys: String, CodingKey {
        case contentCaseID = "content_case_id"
        case stateVersion = "state_version"
        case status
        case phase
        case primaryIntent = "primary_intent"
        case allowedIntents = "allowed_intents"
        case blockerMessage = "blocker_message"
    }
}

public struct OperatorCommandResult: Decodable, Equatable, Sendable {
    public let contentCaseID: UUID
    public let intent: OperatorIntent
    public let status: String

    enum CodingKeys: String, CodingKey {
        case contentCaseID = "content_case_id"
        case intent
        case status
    }
}

public struct OperatorActionTarget: Equatable, Sendable {
    public let caseID: UUID
    public let stateVersion: String
    public let intent: OperatorIntent
    public let title: String

    public init(
        caseID: UUID,
        stateVersion: String,
        intent: OperatorIntent,
        title: String
    ) {
        self.caseID = caseID
        self.stateVersion = stateVersion
        self.intent = intent
        self.title = title
    }
}

public struct OperatorActionTargets: Equatable, Sendable {
    public let continueTarget: OperatorActionTarget?
    public let retryTarget: OperatorActionTarget?
    public let cancelTarget: OperatorActionTarget?
    public let isAmbiguous: Bool

    public init(
        continueTarget: OperatorActionTarget?,
        retryTarget: OperatorActionTarget?,
        cancelTarget: OperatorActionTarget?,
        isAmbiguous: Bool
    ) {
        self.continueTarget = continueTarget
        self.retryTarget = retryTarget
        self.cancelTarget = cancelTarget
        self.isAmbiguous = isAmbiguous
    }

    public static let empty = OperatorActionTargets(
        continueTarget: nil,
        retryTarget: nil,
        cancelTarget: nil,
        isAmbiguous: false
    )
}

public struct ControlSnapshot: Equatable, Sendable {
    public let engineStatus: EngineStatus
    public let summary: ControlCenterSummary?
    public let needsMe: [NeedsMeItem]
    public let actionTargets: OperatorActionTargets
    public let message: String?

    public init(
        engineStatus: EngineStatus,
        summary: ControlCenterSummary?,
        needsMe: [NeedsMeItem],
        actionTargets: OperatorActionTargets,
        message: String?
    ) {
        self.engineStatus = engineStatus
        self.summary = summary
        self.needsMe = needsMe
        self.actionTargets = actionTargets
        self.message = message
    }
}
