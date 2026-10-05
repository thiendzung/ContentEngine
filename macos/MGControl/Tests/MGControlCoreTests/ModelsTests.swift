import Foundation
import Testing
@testable import MGControlCore

struct ModelsTests {
    @Test func operatorCommandResultRetainsJobIdentity() throws {
        let payload = """
        {
          "content_case_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
          "intent": "continue",
          "status": "accepted",
          "job_id": "11111111-2222-3333-4444-555555555555"
        }
        """.data(using: .utf8)!

        let result = try JSONDecoder().decode(
            OperatorCommandResult.self,
            from: payload
        )

        #expect(
            result.contentCaseID ==
                UUID(uuidString: "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE")
        )
        #expect(result.intent == .continueWork)
        #expect(
            result.jobID ==
                UUID(uuidString: "11111111-2222-3333-4444-555555555555")
        )
    }
}
