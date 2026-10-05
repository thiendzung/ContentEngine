import Foundation
import Testing
@testable import MGControlCore

struct LifecycleControllerTests {
    @Test func launchAgentPlistIsBoundedAndNotKeepAlive() {
        let plist = LifecycleController.launchAgentPlist(
            label: "com.motgu.test",
            programArguments: ["/bin/echo", "ok"],
            workingDirectory: "/tmp",
            environment: ["PATH": "/usr/bin:/bin"],
            stdoutPath: "/tmp/out.log",
            stderrPath: "/tmp/err.log"
        )

        #expect(plist["Label"] as? String == "com.motgu.test")
        #expect(plist["RunAtLoad"] as? Bool == true)
        #expect(plist["KeepAlive"] as? Bool == false)
        #expect(
            plist["ProgramArguments"] as? [String] ==
                ["/bin/echo", "ok"]
        )
    }

    @Test func lifecycleLabelsAreDedicatedToMGControl() {
        #expect(
            LifecycleController.backendLabel ==
                "com.motgu.contentengine.mg.backend"
        )
        #expect(
            LifecycleController.frontendLabel ==
                "com.motgu.contentengine.mg.frontend"
        )
        #expect(
            LifecycleController.workerLabel ==
                "com.motgu.contentengine.mg.worker"
        )
    }

    @Test func explicitRepoRootWinsWithoutGuessing() {
        let root = AppConfig.resolveRepoRoot(
            environment: [
                "CONTENTENGINE_REPO_ROOT": "/tmp/contentengine-root"
            ],
            bundleURL: URL(fileURLWithPath: "/Applications/MG Control.app")
        )

        #expect(root.path == "/tmp/contentengine-root")
    }
}
