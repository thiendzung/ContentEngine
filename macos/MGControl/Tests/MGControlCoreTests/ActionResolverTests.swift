import Foundation
import Testing
@testable import MGControlCore

struct ActionResolverTests {
    @Test func resolvesActionsForOneActionableCase() {
        let id = UUID()

        let result = ActionResolver.resolve(
            board: [boardCase(id: id, title: "Pillar")],
            states: [
                id: state(
                    id: id,
                    allowed: [.continueWork, .retry, .cancel]
                )
            ]
        )

        #expect(result.continueTarget?.caseID == id)
        #expect(result.retryTarget?.caseID == id)
        #expect(result.cancelTarget?.caseID == id)
        #expect(!result.isAmbiguous)
    }

    @Test func startMapsToPrimaryWorkflowButton() {
        let id = UUID()
        let result = ActionResolver.resolve(
            board: [boardCase(id: id, title: "Bài mới")],
            states: [
                id: state(id: id, allowed: [.start])
            ]
        )

        #expect(result.continueTarget?.intent == .start)
    }

    @Test func resumeMapsToContinueButton() {
        let id = UUID()
        let result = ActionResolver.resolve(
            board: [boardCase(id: id, title: "Bài")],
            states: [
                id: state(id: id, allowed: [.resume])
            ]
        )

        #expect(result.continueTarget?.intent == .resume)
    }

    @Test func multipleContinueCandidatesFailClosed() {
        let first = UUID()
        let second = UUID()
        let result = ActionResolver.resolve(
            board: [
                boardCase(id: first, title: "Một"),
                boardCase(id: second, title: "Hai"),
            ],
            states: [
                first: state(id: first, allowed: [.continueWork]),
                second: state(id: second, allowed: [.continueWork]),
            ]
        )

        #expect(result.continueTarget == nil)
        #expect(result.isAmbiguous)
    }

    @Test func differentActionsAcrossDifferentCasesFailClosed() {
        let continueID = UUID()
        let cancelID = UUID()
        let result = ActionResolver.resolve(
            board: [
                boardCase(id: continueID, title: "Tiếp tục bài A"),
                boardCase(id: cancelID, title: "Hủy bài B"),
            ],
            states: [
                continueID: state(id: continueID, allowed: [.continueWork]),
                cancelID: state(
                    id: cancelID,
                    status: "RUNNING",
                    allowed: [.cancel]
                ),
            ]
        )

        #expect(result.continueTarget == nil)
        #expect(result.cancelTarget == nil)
        #expect(result.isAmbiguous)
    }

    @Test func completedCaseDoesNotExposeAction() {
        let id = UUID()
        let result = ActionResolver.resolve(
            board: [boardCase(id: id, title: "Xong")],
            states: [
                id: state(
                    id: id,
                    status: "COMPLETE",
                    allowed: [.continueWork, .cancel]
                )
            ]
        )

        #expect(result.continueTarget == nil)
        #expect(result.cancelTarget == nil)
    }

    private func boardCase(
        id: UUID,
        title: String
    ) -> ProductionBoardCase {
        ProductionBoardCase(
            id: id,
            title: title,
            statusGroup: "QUEUED",
            operatorManaged: true,
            nextAction: "CONTINUE"
        )
    }

    private func state(
        id: UUID,
        status: String = "READY",
        allowed: [OperatorIntent]
    ) -> OperatorState {
        OperatorState(
            contentCaseID: id,
            stateVersion: String(repeating: "a", count: 64),
            status: status,
            phase: "Dàn ý",
            primaryIntent: allowed.first,
            allowedIntents: allowed,
            blockerMessage: nil
        )
    }
}
