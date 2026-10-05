import Foundation
import Testing
@testable import MGControlCore

struct ActionResolverTests {
    @Test func resolvesOneContinueRetryAndCancelTarget() {
        let continueID = UUID()
        let retryID = UUID()
        let cancelID = UUID()

        let board = [
            boardCase(id: continueID, title: "Pillar"),
            boardCase(id: retryID, title: "Cluster"),
            boardCase(id: cancelID, title: "Đang chạy"),
        ]
        let states = [
            continueID: state(
                id: continueID,
                allowed: [.continueWork]
            ),
            retryID: state(
                id: retryID,
                status: "BLOCKED",
                allowed: [.retry]
            ),
            cancelID: state(
                id: cancelID,
                status: "RUNNING",
                allowed: [.cancel]
            ),
        ]

        let result = ActionResolver.resolve(
            board: board,
            states: states
        )

        #expect(result.continueTarget?.caseID == continueID)
        #expect(result.retryTarget?.caseID == retryID)
        #expect(result.cancelTarget?.caseID == cancelID)
        #expect(!result.isAmbiguous)
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
