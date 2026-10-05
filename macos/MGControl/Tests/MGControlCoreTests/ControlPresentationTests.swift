import Testing
@testable import MGControlCore

struct ControlPresentationTests {
    @Test func startUsesDistinctStartPresentation() {
        let value = ControlPresentation.primaryWorkflow(for: .start)
        #expect(value.systemImage == "play.circle.fill")
        #expect(value.title == "Bắt đầu bài")
    }

    @Test func continueUsesForwardPresentation() {
        let value = ControlPresentation.primaryWorkflow(for: .continueWork)
        #expect(value.systemImage == "forward.fill")
        #expect(value.title == "Tiếp tục bài")
    }

    @Test func resumeUsesResumePresentation() {
        let value = ControlPresentation.primaryWorkflow(for: .resume)
        #expect(value.systemImage == "playpause.fill")
        #expect(value.title == "Tiếp tục lại")
    }

    @Test func unavailablePrimaryActionExplainsDisabledState() {
        let value = ControlPresentation.primaryWorkflow(for: nil)
        #expect(value.systemImage == "forward.fill")
        #expect(value.title == "Chưa có bước tiếp tục")
    }
}
