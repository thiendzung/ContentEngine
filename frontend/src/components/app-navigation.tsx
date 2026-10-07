"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

type NavigationItem = {
  href: string;
  label: string;
  section: "work" | "intelligence" | "system";
  icon: ReactNode;
  isActive: (pathname: string) => boolean;
};

function Icon({
  children,
}: {
  children: ReactNode;
}) {
  return (
    <svg
      className="global-nav__icon"
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

const navigationItems: NavigationItem[] = [
  {
    href: "/overview",
    label: "Tổng quan",
    section: "work",
    icon: (
      <Icon>
        <path d="M4 4h6v6H4zM14 4h6v10h-6zM4 14h6v6H4zM14 18h6v2h-6z" />
      </Icon>
    ),
    isActive: (pathname) => pathname === "/overview",
  },
  {
    href: "/needs-me",
    label: "Cần tôi xử lý",
    section: "work",
    icon: (
      <Icon>
        <path d="M12 3 3.8 7.1v5.8c0 4.1 3.5 7.2 8.2 8.1 4.7-.9 8.2-4 8.2-8.1V7.1L12 3Zm0 4v6m0 4h.01" />
      </Icon>
    ),
    isActive: (pathname) => pathname === "/needs-me",
  },
  {
    href: "/production",
    label: "Sản xuất",
    section: "work",
    icon: (
      <Icon>
        <path d="M4 6h16M4 12h16M4 18h10M7 3v6M17 9v6M11 15v6" />
      </Icon>
    ),
    isActive: (pathname) =>
      pathname === "/" ||
      pathname === "/production" ||
      pathname.startsWith("/operator"),
  },
  {
    href: "/customers",
    label: "Khách hàng",
    section: "intelligence",
    icon: (
      <Icon>
        <path d="M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm7-2a3 3 0 1 0 0-6M2 21c.4-4.2 2.7-6.5 7-6.5s6.6 2.3 7 6.5m1.5-7c2.8.5 4.2 2.4 4.5 5" />
      </Icon>
    ),
    isActive: (pathname) => pathname === "/customers",
  },
  {
    href: "/content-map",
    label: "Bản đồ nội dung",
    section: "intelligence",
    icon: (
      <Icon>
        <path d="m4 5 5-2 6 2 5-2v16l-5 2-6-2-5 2V5Zm5-2v16m6-14v16" />
      </Icon>
    ),
    isActive: (pathname) => pathname.startsWith("/content-map"),
  },
  {
    href: "/learning",
    label: "Học từ dữ liệu",
    section: "intelligence",
    icon: (
      <Icon>
        <path d="m3 9 9-5 9 5-9 5-9-5Zm4 3v5c2.8 2.1 7.2 2.1 10 0v-5m4-3v6" />
      </Icon>
    ),
    isActive: (pathname) => pathname === "/learning",
  },
  {
    href: "/system",
    label: "Hệ thống",
    section: "system",
    icon: (
      <Icon>
        <path d="M12 3v3m0 12v3M3 12h3m12 0h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1m0-12.8-2.1 2.1m-8.6 8.6-2.1 2.1M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z" />
      </Icon>
    ),
    isActive: (pathname) =>
      pathname === "/system" || pathname === "/daily-digest",
  },
];

const sections: Array<{
  key: NavigationItem["section"];
  label: string;
}> = [
  { key: "work", label: "Điều hành" },
  { key: "intelligence", label: "Hiểu khách hàng & nội dung" },
  { key: "system", label: "Quản trị" },
];

export function AppNavigation() {
  const pathname = usePathname();

  return (
    <nav className="global-nav" aria-label="Điều hướng chính ContentEngine">
      <div className="global-nav__brand">
        <strong>MOTGU</strong>
        <span>ContentEngine</span>
      </div>

      <div className="global-nav__sections">
        {sections.map((section) => (
          <section className="global-nav__section" key={section.key}>
            <p className="global-nav__section-label">{section.label}</p>
            <div className="global-nav__list">
              {navigationItems
                .filter((item) => item.section === section.key)
                .map((item) => {
                  const active = item.isActive(pathname);
                  return (
                    <Link
                      className={
                        active
                          ? "global-nav__link global-nav__link--active"
                          : "global-nav__link"
                      }
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      key={item.href}
                    >
                      {item.icon}
                      <span>{item.label}</span>
                    </Link>
                  );
                })}
            </div>
          </section>
        ))}
      </div>
    </nav>
  );
}
