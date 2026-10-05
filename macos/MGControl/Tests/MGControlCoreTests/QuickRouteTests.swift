import Foundation
import Testing
@testable import MGControlCore

struct QuickRouteTests {
    @Test func quickRoutesUseExpectedPaths() {
        #expect(QuickRoute.needsMe.path == "/needs-me")
        #expect(QuickRoute.newJournal.path == "/operator/journal/new")
        #expect(QuickRoute.production.path == "/production")
        #expect(QuickRoute.contentMap.path == "/content-map")
        #expect(QuickRoute.system.path == "/system")
        #expect(QuickRoute.dashboard.path == "/")
    }

    @Test func routeBuildsFromConfiguredWebBase() {
        let base = URL(string: "http://127.0.0.1:3000")!
        #expect(
            QuickRoute.production.url(baseURL: base).absoluteString ==
                "http://127.0.0.1:3000/production"
        )
    }

    @Test func idempotencyKeyIsBoundedAndIntentSpecific() {
        let id = UUID(uuidString: "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE")!
        let nonce = UUID(uuidString: "11111111-2222-3333-4444-555555555555")!

        let key = ContentEngineClient.idempotencyKey(
            intent: .retry,
            caseID: id,
            nonce: nonce
        )

        #expect(key.hasPrefix("mgctrl-retry-"))
        #expect(key.count <= 200)
    }
}
