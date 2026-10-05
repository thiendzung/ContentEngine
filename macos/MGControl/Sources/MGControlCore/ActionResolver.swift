import Foundation

public enum ActionResolver {
    public static func resolve(
        board: [ProductionBoardCase],
        states: [UUID: OperatorState]
    ) -> OperatorActionTargets {
        let titles = Dictionary(uniqueKeysWithValues: board.map { ($0.id, $0.title) })

        let candidates = states.values.filter {
            $0.status != "COMPLETE"
        }

        let continueCandidates = candidates.compactMap { state -> OperatorActionTarget? in
            let intent: OperatorIntent?
            if state.allowedIntents.contains(.continueWork) {
                intent = .continueWork
            } else if state.allowedIntents.contains(.resume) {
                intent = .resume
            } else {
                intent = nil
            }
            guard let intent else { return nil }
            return OperatorActionTarget(
                caseID: state.contentCaseID,
                stateVersion: state.stateVersion,
                intent: intent,
                title: titles[state.contentCaseID] ?? "Bài đang xử lý"
            )
        }

        let retryCandidates = candidates.compactMap { state -> OperatorActionTarget? in
            guard state.allowedIntents.contains(.retry) else { return nil }
            return OperatorActionTarget(
                caseID: state.contentCaseID,
                stateVersion: state.stateVersion,
                intent: .retry,
                title: titles[state.contentCaseID] ?? "Bài đang xử lý"
            )
        }

        let cancelCandidates = candidates.compactMap { state -> OperatorActionTarget? in
            guard state.allowedIntents.contains(.cancel) else { return nil }
            return OperatorActionTarget(
                caseID: state.contentCaseID,
                stateVersion: state.stateVersion,
                intent: .cancel,
                title: titles[state.contentCaseID] ?? "Bài đang xử lý"
            )
        }

        let ambiguous =
            continueCandidates.count > 1 ||
            retryCandidates.count > 1 ||
            cancelCandidates.count > 1

        return OperatorActionTargets(
            continueTarget: continueCandidates.count == 1 ? continueCandidates[0] : nil,
            retryTarget: retryCandidates.count == 1 ? retryCandidates[0] : nil,
            cancelTarget: cancelCandidates.count == 1 ? cancelCandidates[0] : nil,
            isAmbiguous: ambiguous
        )
    }
}
