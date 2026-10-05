import XCTest
@testable import MGControlCore

final class QuickRouteTests: XCTestCase {
    func testQuickRoutesUseExpectedPaths() {
        XCTAssertEqual(QuickRoute.needsMe.path, "/needs-me")
        XCTAssertEqual(QuickRoute.newJournal.path, "/operator/journal/new")
        XCTAssertEqual(QuickRoute.production.path, "/production")
        XCTAssertEqual(QuickRoute.contentMap.path, "/content-map")
        XCTAssertEqual(QuickRoute.system.path, "/system")
        XCTAssertEqual(QuickRoute.dashboard.path, "/")
    }

    func testRouteBuildsFromConfiguredWebBase() {
        let base = URL(string: "http://127.0.0.1:3000")!
        XCTAssertEqual(
            QuickRoute.production.url(baseURL: base).absoluteString,
            "http://127.0.0.1:3000/production"
        )
    }

    func testIdempotencyKeyIsBoundedAndIntentSpecific() {
        let id = UUID(uuidString: "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE")!
        let nonce = UUID(uuidString: "11111111-2222-3333-4444-555555555555")!

        let key = ContentEngineClient.idempotencyKey(
            intent: .retry,
            caseID: id,
            nonce: nonce
        )

        XCTAssertTrue(key.hasPrefix("mgctrl-retry-"))
        XCTAssertLessThanOrEqual(key.count, 200)
    }
}
