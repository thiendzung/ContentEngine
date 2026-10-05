import Foundation

public enum QuickRoute: String, CaseIterable, Identifiable, Sendable {
    case needsMe
    case newJournal
    case production
    case contentMap
    case system
    case dashboard

    public var id: String { rawValue }

    public var title: String {
        switch self {
        case .needsMe:
            return "Việc cần tôi"
        case .newJournal:
            return "Tạo bài mới"
        case .production:
            return "Sản xuất"
        case .contentMap:
            return "Bản đồ nội dung"
        case .system:
            return "Hệ thống"
        case .dashboard:
            return "Mở ContentEngine"
        }
    }

    public var systemImage: String {
        switch self {
        case .needsMe:
            return "exclamationmark.triangle"
        case .newJournal:
            return "plus"
        case .production:
            return "rectangle.stack"
        case .contentMap:
            return "square.grid.2x2"
        case .system:
            return "gearshape"
        case .dashboard:
            return "arrow.up.forward.app"
        }
    }

    public var path: String {
        switch self {
        case .needsMe:
            return "/needs-me"
        case .newJournal:
            return "/operator/journal/new"
        case .production:
            return "/production"
        case .contentMap:
            return "/content-map"
        case .system:
            return "/system"
        case .dashboard:
            return "/"
        }
    }

    public func url(baseURL: URL) -> URL {
        if path == "/" {
            return baseURL
        }
        return baseURL.appending(path: String(path.dropFirst()))
    }
}
