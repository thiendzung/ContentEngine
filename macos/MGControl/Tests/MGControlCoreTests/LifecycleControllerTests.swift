import Foundation
import Testing
@testable import MGControlCore

private struct OfflineRuntimeProbe: RuntimeProbing {
    func responds(to url: URL) async -> Bool {
        false
    }
}

private actor MockLifecycleCommandRunner: CommandRunning {
    private var jobs: [String: Bool] = [:]
    private var invocations: [[String]] = []

    func run(
        executable: URL,
        arguments: [String],
        currentDirectory: URL?,
        environment: [String: String]?
    ) async throws -> CommandResult {
        invocations.append([executable.path] + arguments)

        if executable.path == "/bin/launchctl" {
            guard let command = arguments.first else {
                return CommandResult(exitCode: 2, output: "missing command")
            }

            switch command {
            case "print":
                guard let target = arguments.last else {
                    return CommandResult(exitCode: 2, output: "missing target")
                }
                let label = target.split(separator: "/").last.map(String.init) ?? ""
                guard let running = jobs[label] else {
                    return CommandResult(exitCode: 3, output: "not registered")
                }
                return CommandResult(
                    exitCode: 0,
                    output: running ? "state = running" : "state = exited"
                )

            case "bootstrap":
                guard let path = arguments.last else {
                    return CommandResult(exitCode: 2, output: "missing plist")
                }
                let data = try Data(contentsOf: URL(fileURLWithPath: path))
                guard
                    let plist = try PropertyListSerialization.propertyList(
                        from: data,
                        options: [],
                        format: nil
                    ) as? [String: Any],
                    let label = plist["Label"] as? String,
                    let runAtLoad = plist["RunAtLoad"] as? Bool
                else {
                    return CommandResult(exitCode: 2, output: "invalid plist")
                }
                jobs[label] = runAtLoad
                return CommandResult(exitCode: 0, output: "")

            case "kickstart":
                guard let target = arguments.last else {
                    return CommandResult(exitCode: 2, output: "missing target")
                }
                let label = target.split(separator: "/").last.map(String.init) ?? ""
                guard jobs[label] != nil else {
                    return CommandResult(exitCode: 3, output: "not registered")
                }
                jobs[label] = true
                return CommandResult(exitCode: 0, output: "12345")

            case "bootout":
                guard let target = arguments.last else {
                    return CommandResult(exitCode: 2, output: "missing target")
                }
                let label = target.split(separator: "/").last.map(String.init) ?? ""
                jobs.removeValue(forKey: label)
                return CommandResult(exitCode: 0, output: "")

            default:
                return CommandResult(exitCode: 2, output: "unsupported launchctl")
            }
        }

        if executable.path == "/usr/bin/env",
           arguments.starts(with: ["docker", "compose"]) {
            return CommandResult(exitCode: 0, output: "postgres ready")
        }

        if arguments == ["-m", "scripts.ops_release_preflight"] {
            return CommandResult(exitCode: 0, output: "RELEASE PREFLIGHT: READY")
        }

        return CommandResult(exitCode: 0, output: "")
    }

    func finishWorker() {
        jobs[LifecycleController.workerLabel] = false
    }

    func recordedInvocations() -> [[String]] {
        invocations
    }
}

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

    @Test func managedLifecycleUsesOnDemandWorkerAndOwnedStop() async throws {
        let fileManager = FileManager.default
        let root = fileManager.temporaryDirectory.appending(
            path: "mgcontrol-lifecycle-\(UUID().uuidString)",
            directoryHint: .isDirectory
        )
        let launchd = root.appending(
            path: "launchd",
            directoryHint: .isDirectory
        )
        defer {
            try? fileManager.removeItem(at: root)
        }

        try makeExecutable(
            root.appending(path: "backend/.venv/bin/python"),
            fileManager: fileManager
        )
        try makeExecutable(
            root.appending(path: "frontend/node_modules/.bin/next"),
            fileManager: fileManager
        )
        let buildID = root.appending(path: "frontend/.next/BUILD_ID")
        try fileManager.createDirectory(
            at: buildID.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try Data("test-build".utf8).write(to: buildID)

        let config = AppConfig(
            apiBaseURL: URL(string: "http://127.0.0.1:18000")!,
            webBaseURL: URL(string: "http://127.0.0.1:18001")!,
            projectSlug: "motgu",
            timezone: "Asia/Ho_Chi_Minh",
            repoRoot: root
        )
        let runner = MockLifecycleCommandRunner()
        let lifecycle = LifecycleController(
            config: config,
            runner: runner,
            probe: OfflineRuntimeProbe(),
            fileManager: fileManager,
            launchAgentDirectory: launchd
        )

        let started = try await lifecycle.start()
        #expect(started.state == .running)
        #expect(started.registeredJobs == 3)
        #expect(started.runningJobs == 2)

        let workerPlistURL = launchd.appending(
            path: "\(LifecycleController.workerLabel).plist"
        )
        let workerData = try Data(contentsOf: workerPlistURL)
        let workerPlist = try #require(
            PropertyListSerialization.propertyList(
                from: workerData,
                options: [],
                format: nil
            ) as? [String: Any]
        )
        #expect(workerPlist["RunAtLoad"] as? Bool == false)
        let workerArguments = try #require(
            workerPlist["ProgramArguments"] as? [String]
        )
        #expect(workerArguments.contains("scripts.run_operator_worker"))
        #expect(!workerArguments.contains("scripts.run_operator_worker_loop"))

        try await lifecycle.triggerWorkerOnce()

        var stopBlocked = false
        do {
            _ = try await lifecycle.stop()
        } catch let error as LifecycleError {
            stopBlocked = error == .workerBusy
        }
        #expect(stopBlocked)

        await runner.finishWorker()
        let stopped = try await lifecycle.stop()
        #expect(stopped.state == .stopped)
        #expect(stopped.registeredJobs == 0)

        let invocations = await runner.recordedInvocations()
        #expect(
            !invocations.flatMap { $0 }.contains("scripts.run_operator_worker_loop")
        )
    }

    private func makeExecutable(
        _ url: URL,
        fileManager: FileManager
    ) throws {
        try fileManager.createDirectory(
            at: url.deletingLastPathComponent(),
            withIntermediateDirectories: true
        )
        try Data("#!/bin/sh\nexit 0\n".utf8).write(to: url)
        try fileManager.setAttributes(
            [.posixPermissions: 0o755],
            ofItemAtPath: url.path
        )
    }
}
