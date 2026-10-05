import Foundation
import Darwin
#if canImport(FoundationNetworking)
import FoundationNetworking
#endif

public enum ManagedRuntimeState: Equatable, Sendable {
    case stopped
    case starting
    case running
    case partial
}

public struct ManagedRuntimeStatus: Equatable, Sendable {
    public let state: ManagedRuntimeState
    public let registeredJobs: Int
    public let runningJobs: Int

    public init(
        state: ManagedRuntimeState,
        registeredJobs: Int,
        runningJobs: Int
    ) {
        self.state = state
        self.registeredJobs = registeredJobs
        self.runningJobs = runningJobs
    }

    public var ownsRuntime: Bool {
        registeredJobs > 0
    }

    public static let stopped = ManagedRuntimeStatus(
        state: .stopped,
        registeredJobs: 0,
        runningJobs: 0
    )
}

public struct CommandResult: Equatable, Sendable {
    public let exitCode: Int32
    public let output: String

    public init(exitCode: Int32, output: String) {
        self.exitCode = exitCode
        self.output = output
    }
}

public protocol CommandRunning: Sendable {
    func run(
        executable: URL,
        arguments: [String],
        currentDirectory: URL?,
        environment: [String: String]?
    ) async throws -> CommandResult
}

public struct FoundationCommandRunner: CommandRunning {
    public init() {}

    public func run(
        executable: URL,
        arguments: [String],
        currentDirectory: URL?,
        environment: [String: String]?
    ) async throws -> CommandResult {
        try await Task.detached(priority: .userInitiated) {
            let fileManager = FileManager.default
            let outputURL = fileManager.temporaryDirectory.appending(
                path: "mgcontrol-command-\(UUID().uuidString).log"
            )
            guard fileManager.createFile(
                atPath: outputURL.path,
                contents: nil
            ) else {
                throw LifecycleError.commandOutputUnavailable
            }

            defer {
                try? fileManager.removeItem(at: outputURL)
            }

            let handle = try FileHandle(forWritingTo: outputURL)
            let process = Process()
            process.executableURL = executable
            process.arguments = arguments
            process.currentDirectoryURL = currentDirectory
            process.standardOutput = handle
            process.standardError = handle
            if let environment {
                process.environment = environment
            }

            do {
                try process.run()
                process.waitUntilExit()
                try handle.close()
            } catch {
                try? handle.close()
                throw error
            }

            let data = try Data(contentsOf: outputURL)
            let output = String(data: data, encoding: .utf8) ?? ""
            return CommandResult(
                exitCode: process.terminationStatus,
                output: output
            )
        }.value
    }
}

public enum LifecycleError: Error, LocalizedError, Equatable {
    case repoRootInvalid
    case prerequisiteMissing(String)
    case externalRuntimeActive
    case partialManagedRuntime
    case commandFailed(String)
    case preflightBlocked(String)
    case launchdFailed(String)
    case commandOutputUnavailable

    public var errorDescription: String? {
        switch self {
        case .repoRootInvalid:
            return "Không xác định được thư mục ContentEngine."
        case .prerequisiteMissing(let value):
            return value
        case .externalRuntimeActive:
            return "ContentEngine đang chạy ngoài MG Control. Không tự giành quyền quản lý."
        case .partialManagedRuntime:
            return "Runtime do MG quản lý đang ở trạng thái không đầy đủ. Hãy bấm Dừng rồi thử lại."
        case .commandFailed(let value):
            return value
        case .preflightBlocked(let value):
            return "Không thể khởi động: \(value)"
        case .launchdFailed(let value):
            return "Không thể điều khiển dịch vụ: \(value)"
        case .commandOutputUnavailable:
            return "Không thể tạo file log tạm cho tác vụ."
        }
    }
}

public final class LifecycleController: @unchecked Sendable {
    public static let backendLabel = "com.motgu.contentengine.mg.backend"
    public static let frontendLabel = "com.motgu.contentengine.mg.frontend"
    public static let workerLabel = "com.motgu.contentengine.mg.worker"

    private let config: AppConfig
    private let runner: any CommandRunning
    private let fileManager: FileManager
    private let session: URLSession

    public init(
        config: AppConfig,
        runner: any CommandRunning = FoundationCommandRunner(),
        fileManager: FileManager = .default,
        session: URLSession = .shared
    ) {
        self.config = config
        self.runner = runner
        self.fileManager = fileManager
        self.session = session
    }

    public func status() async -> ManagedRuntimeStatus {
        let checks = await withTaskGroup(
            of: LaunchdJobState.self,
            returning: [LaunchdJobState].self
        ) { group in
            for label in Self.labels {
                group.addTask {
                    await self.launchdState(label: label)
                }
            }

            var values: [LaunchdJobState] = []
            for await value in group {
                values.append(value)
            }
            return values
        }

        let registered = checks.filter(\.registered).count
        let running = checks.filter(\.running).count
        let byLabel = Dictionary(
            uniqueKeysWithValues: checks.map { ($0.label, $0) }
        )

        if registered == 0 {
            return .stopped
        }

        let coreRegistered = Self.coreLabels.allSatisfy {
            byLabel[$0]?.registered == true
        }
        let coreRunning = Self.coreLabels.allSatisfy {
            byLabel[$0]?.running == true
        }
        let workerRegistered = byLabel[Self.workerLabel]?.registered == true

        if coreRegistered && coreRunning && workerRegistered {
            return ManagedRuntimeStatus(
                state: .running,
                registeredJobs: registered,
                runningJobs: running
            )
        }

        return ManagedRuntimeStatus(
            state: .partial,
            registeredJobs: registered,
            runningJobs: running
        )
    }

    public func start() async throws -> ManagedRuntimeStatus {
        let current = await status()
        switch current.state {
        case .running, .starting:
            return current
        case .partial:
            throw LifecycleError.partialManagedRuntime
        case .stopped:
            break
        }

        guard isRepoRootValid else {
            throw LifecycleError.repoRootInvalid
        }

        if await externalRuntimeResponds() {
            throw LifecycleError.externalRuntimeActive
        }

        try validatePrerequisites()
        try await ensurePostgres()
        try await requireReleasePreflight()
        try writeLaunchAgentPlists()

        var bootstrapped: [String] = []
        do {
            for label in Self.labels {
                let result = try await runner.run(
                    executable: URL(fileURLWithPath: "/bin/launchctl"),
                    arguments: [
                        "bootstrap",
                        launchdDomain,
                        try plistURL(for: label).path,
                    ],
                    currentDirectory: nil,
                    environment: nil
                )
                guard result.exitCode == 0 else {
                    throw LifecycleError.launchdFailed(
                        concise(result.output, fallback: label)
                    )
                }
                bootstrapped.append(label)
            }

            for label in Self.coreLabels {
                let result = try await runner.run(
                    executable: URL(fileURLWithPath: "/bin/launchctl"),
                    arguments: [
                        "kickstart",
                        "-p",
                        "\(launchdDomain)/\(label)",
                    ],
                    currentDirectory: nil,
                    environment: nil
                )
                guard result.exitCode == 0 else {
                    throw LifecycleError.launchdFailed(
                        concise(result.output, fallback: label)
                    )
                }
            }
        } catch {
            await rollback(labels: bootstrapped)
            throw error
        }

        let launched = await status()
        if launched.state == .running {
            return launched
        }
        return ManagedRuntimeStatus(
            state: .starting,
            registeredJobs: launched.registeredJobs,
            runningJobs: launched.runningJobs
        )
    }

    public func triggerWorkerOnce() async throws {
        let worker = await launchdState(label: Self.workerLabel)
        guard worker.registered else {
            throw LifecycleError.partialManagedRuntime
        }
        if worker.running {
            return
        }

        let result = try await runner.run(
            executable: URL(fileURLWithPath: "/bin/launchctl"),
            arguments: [
                "kickstart",
                "-p",
                "\(launchdDomain)/\(Self.workerLabel)",
            ],
            currentDirectory: nil,
            environment: nil
        )
        guard result.exitCode == 0 else {
            throw LifecycleError.launchdFailed(
                concise(result.output, fallback: Self.workerLabel)
            )
        }
    }

    public func stop() async throws -> ManagedRuntimeStatus {
        var failures: [String] = []

        for label in Self.labels.reversed() {
            let state = await launchdState(label: label)
            guard state.registered else {
                continue
            }

            do {
                let result = try await runner.run(
                    executable: URL(fileURLWithPath: "/bin/launchctl"),
                    arguments: [
                        "bootout",
                        "\(launchdDomain)/\(label)",
                    ],
                    currentDirectory: nil,
                    environment: nil
                )
                if result.exitCode != 0 {
                    failures.append(
                        concise(result.output, fallback: label)
                    )
                }
            } catch {
                failures.append(label)
            }
        }

        removeLaunchAgentPlists()

        let finalStatus = await status()
        if !failures.isEmpty || finalStatus.ownsRuntime {
            throw LifecycleError.launchdFailed(
                failures.joined(separator: " · ")
            )
        }
        return finalStatus
    }

    public static func launchAgentPlist(
        label: String,
        programArguments: [String],
        workingDirectory: String,
        environment: [String: String],
        runAtLoad: Bool,
        stdoutPath: String,
        stderrPath: String
    ) -> [String: Any] {
        [
            "Label": label,
            "ProgramArguments": programArguments,
            "WorkingDirectory": workingDirectory,
            "EnvironmentVariables": environment,
            "RunAtLoad": runAtLoad,
            "KeepAlive": false,
            "ProcessType": "Background",
            "StandardOutPath": stdoutPath,
            "StandardErrorPath": stderrPath,
        ]
    }

    private static let coreLabels = [
        backendLabel,
        frontendLabel,
    ]

    private static let labels = [
        backendLabel,
        frontendLabel,
        workerLabel,
    ]

    private struct LaunchdJobState: Sendable {
        let label: String
        let registered: Bool
        let running: Bool
    }

    private var launchdDomain: String {
        "gui/\(getuid())"
    }

    private var backendRoot: URL {
        config.repoRoot.appending(path: "backend", directoryHint: .isDirectory)
    }

    private var frontendRoot: URL {
        config.repoRoot.appending(path: "frontend", directoryHint: .isDirectory)
    }

    private var backendPython: URL {
        backendRoot.appending(path: ".venv/bin/python")
    }

    private var nextExecutable: URL {
        frontendRoot.appending(path: "node_modules/.bin/next")
    }

    private var logDirectory: URL {
        config.repoRoot.appending(
            path: "artifacts/mgcontrol",
            directoryHint: .isDirectory
        )
    }

    private var launchAgentDirectory: URL {
        let base = fileManager.urls(
            for: .applicationSupportDirectory,
            in: .userDomainMask
        ).first ?? fileManager.homeDirectoryForCurrentUser
            .appending(path: "Library/Application Support", directoryHint: .isDirectory)
        return base.appending(
            path: "MGControl/LaunchAgents",
            directoryHint: .isDirectory
        )
    }

    private var isRepoRootValid: Bool {
        fileManager.fileExists(
            atPath: config.repoRoot.appending(path: "backend").path
        ) &&
        fileManager.fileExists(
            atPath: config.repoRoot.appending(path: "frontend").path
        )
    }

    private func validatePrerequisites() throws {
        guard fileManager.isExecutableFile(atPath: backendPython.path) else {
            throw LifecycleError.prerequisiteMissing(
                "Thiếu backend/.venv. Chạy setup ContentEngine trước."
            )
        }
        guard fileManager.isExecutableFile(atPath: nextExecutable.path) else {
            throw LifecycleError.prerequisiteMissing(
                "Thiếu frontend/node_modules. Chạy setup ContentEngine trước."
            )
        }
        guard fileManager.fileExists(
            atPath: frontendRoot.appending(path: ".next/BUILD_ID").path
        ) else {
            throw LifecycleError.prerequisiteMissing(
                "Chưa có bản build frontend production. Chạy npm run build trước."
            )
        }
    }

    private func ensurePostgres() async throws {
        let result = try await runner.run(
            executable: URL(fileURLWithPath: "/usr/bin/env"),
            arguments: [
                "docker",
                "compose",
                "-p",
                "contentengine",
                "up",
                "-d",
                "--wait",
                "postgres",
            ],
            currentDirectory: config.repoRoot,
            environment: commandEnvironment
        )
        guard result.exitCode == 0 else {
            throw LifecycleError.commandFailed(
                "Không khởi động được PostgreSQL: " +
                concise(result.output, fallback: "docker compose thất bại")
            )
        }
    }

    private func requireReleasePreflight() async throws {
        let result = try await runner.run(
            executable: backendPython,
            arguments: [
                "-m",
                "scripts.ops_release_preflight",
            ],
            currentDirectory: backendRoot,
            environment: commandEnvironment
        )
        guard result.exitCode == 0 else {
            throw LifecycleError.preflightBlocked(
                concise(result.output, fallback: "release preflight bị chặn")
            )
        }
    }

    private func writeLaunchAgentPlists() throws {
        try fileManager.createDirectory(
            at: launchAgentDirectory,
            withIntermediateDirectories: true
        )
        try fileManager.createDirectory(
            at: logDirectory,
            withIntermediateDirectories: true
        )

        let environment = commandEnvironment
        let jobs: [(String, [String], URL, Bool)] = [
            (
                Self.backendLabel,
                [
                    backendPython.path,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    "8000",
                    "--no-access-log",
                ],
                backendRoot,
                true
            ),
            (
                Self.frontendLabel,
                [
                    nextExecutable.path,
                    "start",
                    "--hostname",
                    "127.0.0.1",
                    "--port",
                    "3000",
                ],
                frontendRoot,
                true
            ),
            (
                Self.workerLabel,
                [
                    backendPython.path,
                    "-m",
                    "scripts.run_operator_worker",
                ],
                backendRoot,
                false
            ),
        ]

        for (label, arguments, workingDirectory, runAtLoad) in jobs {
            let safeName = label.replacingOccurrences(of: ".", with: "-")
            let plist = Self.launchAgentPlist(
                label: label,
                programArguments: arguments,
                workingDirectory: workingDirectory.path,
                environment: environment,
                runAtLoad: runAtLoad,
                stdoutPath: logDirectory
                    .appending(path: "\(safeName).log").path,
                stderrPath: logDirectory
                    .appending(path: "\(safeName)-error.log").path
            )
            let data = try PropertyListSerialization.data(
                fromPropertyList: plist,
                format: .xml,
                options: 0
            )
            try data.write(
                to: try plistURL(for: label),
                options: .atomic
            )
        }
    }

    private func plistURL(for label: String) throws -> URL {
        guard !label.isEmpty else {
            throw LifecycleError.launchdFailed("LaunchAgent label rỗng.")
        }
        return launchAgentDirectory.appending(path: "\(label).plist")
    }

    private func removeLaunchAgentPlists() {
        for label in Self.labels {
            if let url = try? plistURL(for: label) {
                try? fileManager.removeItem(at: url)
            }
        }
    }

    private func rollback(labels: [String]) async {
        for label in labels.reversed() {
            _ = try? await runner.run(
                executable: URL(fileURLWithPath: "/bin/launchctl"),
                arguments: [
                    "bootout",
                    "\(launchdDomain)/\(label)",
                ],
                currentDirectory: nil,
                environment: nil
            )
        }
        removeLaunchAgentPlists()
    }

    private func launchdState(label: String) async -> LaunchdJobState {
        guard let result = try? await runner.run(
            executable: URL(fileURLWithPath: "/bin/launchctl"),
            arguments: [
                "print",
                "\(launchdDomain)/\(label)",
            ],
            currentDirectory: nil,
            environment: nil
        ), result.exitCode == 0 else {
            return LaunchdJobState(
                label: label,
                registered: false,
                running: false
            )
        }

        return LaunchdJobState(
            label: label,
            registered: true,
            running: result.output.contains("state = running")
        )
    }

    private func externalRuntimeResponds() async -> Bool {
        await withTaskGroup(of: Bool.self, returning: Bool.self) { group in
            let urls = [
                config.apiBaseURL.appending(path: "health"),
                config.webBaseURL,
            ]
            for url in urls {
                group.addTask {
                    await self.endpointResponds(url)
                }
            }

            var any = false
            for await responds in group {
                any = any || responds
            }
            return any
        }
    }

    private func endpointResponds(_ url: URL) async -> Bool {
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        request.timeoutInterval = 0.8
        do {
            let (_, response) = try await session.data(for: request)
            return response is HTTPURLResponse
        } catch {
            return false
        }
    }

    static func safeEnvironment(
        home: String,
        lang: String?,
        tmpdir: String?
    ) -> [String: String] {
        let path = [
            "\(home)/.local/bin",
            "/opt/homebrew/bin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
        ].joined(separator: ":")

        var environment = [
            "PATH": path,
            "HOME": home,
            "PYTHONUNBUFFERED": "1",
        ]
        if let lang, !lang.isEmpty {
            environment["LANG"] = lang
        }
        if let tmpdir, !tmpdir.isEmpty {
            environment["TMPDIR"] = tmpdir
        }
        return environment
    }

    private var commandEnvironment: [String: String] {
        Self.safeEnvironment(
            home: fileManager.homeDirectoryForCurrentUser.path,
            lang: ProcessInfo.processInfo.environment["LANG"],
            tmpdir: ProcessInfo.processInfo.environment["TMPDIR"]
        )
    }

    private func concise(
        _ value: String,
        fallback: String
    ) -> String {
        let normalized = value
            .split(whereSeparator: \.isNewline)
            .suffix(6)
            .joined(separator: " · ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        if normalized.isEmpty {
            return fallback
        }
        return String(normalized.suffix(1200))
    }
}
