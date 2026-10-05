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
            runAtLoad: true,
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

    @Test func onDemandWorkerPlistDoesNotRunAtLoad() {
        let plist = LifecycleController.launchAgentPlist(
            label: LifecycleController.workerLabel,
            programArguments: ["/usr/bin/python3", "-m", "scripts.run_operator_worker"],
            workingDirectory: "/tmp/backend",
            environment: ["PATH": "/usr/bin:/bin"],
            runAtLoad: false,
            stdoutPath: "/tmp/worker.log",
            stderrPath: "/tmp/worker-error.log"
        )

        #expect(plist["RunAtLoad"] as? Bool == false)
        #expect(plist["KeepAlive"] as? Bool == false)
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

    @Test func lifecycleEnvironmentIsSecretFreeByConstruction() {
        let environment = LifecycleController.safeEnvironment(
            home: "/Users/tester",
            lang: "vi_VN.UTF-8",
            tmpdir: "/tmp/"
        )

        #expect(environment["HOME"] == "/Users/tester")
        #expect(environment["LANG"] == "vi_VN.UTF-8")
        #expect(environment["TMPDIR"] == "/tmp/")
        #expect(environment["PYTHONUNBUFFERED"] == "1")
        #expect(environment["DATABASE_URL"] == nil)
        #expect(environment["OPENAI_API_KEY"] == nil)
        #expect(environment["WORDPRESS_APPLICATION_PASSWORD"] == nil)
    }
}
