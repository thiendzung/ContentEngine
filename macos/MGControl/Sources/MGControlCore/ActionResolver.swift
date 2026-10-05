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

        let actionable = candidates.filter { state in
            state.allowedIntents.contains(.start) ||
            state.allowedIntents.contains(.continueWork) ||
            state.allowedIntents.contains(.resume) ||
            state.allowedIntents.contains(.retry) ||
            state.allowedIntents.contains(.cancel)
        }

        let actionableCaseIDs = Set(actionable.map(\.contentCaseID))
        guard actionableCaseIDs.count <= 1 else {
            return OperatorActionTargets(
                continueTarget: nil,
                retryTarget: nil,
                cancelTarget: nil,
                isAmbiguous: true
            )
        }

        let continueCandidates = actionable.compactMap { state -> OperatorActionTarget? in
            let intent: OperatorIntent?
            if state.allowedIntents.contains(.start) {
                intent = .start
            } else if state.allowedIntents.contains(.continueWork) {
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

        let retryCandidates = actionable.compactMap { state -> OperatorActionTarget? in
            guard state.allowedIntents.contains(.retry) else { return nil }
            return OperatorActionTarget(
                caseID: state.contentCaseID,
                stateVersion: state.stateVersion,
                intent: .retry,
                title: titles[state.contentCaseID] ?? "Bài đang xử lý"
            )
        }

        let cancelCandidates = actionable.compactMap { state -> OperatorActionTarget? in
            guard state.allowedIntents.contains(.cancel) else { return nil }
            return OperatorActionTarget(
                caseID: state.contentCaseID,
                stateVersion: state.stateVersion,
                intent: .cancel,
                title: titles[state.contentCaseID] ?? "Bài đang xử lý"
            )
        }

        return OperatorActionTargets(
            continueTarget: continueCandidates.first,
            retryTarget: retryCandidates.first,
            cancelTarget: cancelCandidates.first,
            isAmbiguous: false
        )
    }
}
