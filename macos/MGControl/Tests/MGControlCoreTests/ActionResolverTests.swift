import XCTest
@testable import MGControlCore

final class ActionResolverTests: XCTestCase {
    func testResolvesOneContinueRetryAndCancelTarget() {
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

        XCTAssertEqual(result.continueTarget?.caseID, continueID)
        XCTAssertEqual(result.retryTarget?.caseID, retryID)
        XCTAssertEqual(result.cancelTarget?.caseID, cancelID)
        XCTAssertFalse(result.isAmbiguous)
    }

    func testResumeMapsToContinueButton() {
        let id = UUID()
        let result = ActionResolver.resolve(
            board: [boardCase(id: id, title: "Bài")],
            states: [
                id: state(id: id, allowed: [.resume])
            ]
        )

        XCTAssertEqual(result.continueTarget?.intent, .resume)
    }

    func testMultipleContinueCandidatesFailClosed() {
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

        XCTAssertNil(result.continueTarget)
        XCTAssertTrue(result.isAmbiguous)
    }

    func testCompletedCaseDoesNotExposeAction() {
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

        XCTAssertNil(result.continueTarget)
        XCTAssertNil(result.cancelTarget)
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
