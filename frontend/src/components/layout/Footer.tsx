"use client";

import Image from "next/image";
import Link from "next/link";

const COLS = [
  {
    title: "Platform",
    links: [
      { label: "Home", href: "/" },
      { label: "Shop", href: "/shop" },
      { label: "Cart", href: "/cart" },
      { label: "Account", href: "/profile" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About", href: "#" },
      { label: "Blog", href: "#" },
      { label: "Careers", href: "#" },
      { label: "Press", href: "#" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Terms", href: "#" },
      { label: "Privacy", href: "#" },
      { label: "Cookies", href: "#" },
      { label: "Security", href: "#" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="bg-black" style={{ marginTop: "clamp(6rem, 11vw, 12rem)" }}>
      <div className="container mx-auto max-w-[1280px] px-6 pt-20 pb-16 lg:px-8">
        {/* Top grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-10 mb-14">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1">
            <Image
              src="/images/brand/shopy-logo-v2.png"
              alt="Shopy"
              width={150}
              height={60}
              className="mb-3 h-12 w-auto object-contain"
              style={{ width: "auto" }}
            />
            <p className="text-[0.82rem] text-[#8892a4] leading-relaxed max-w-[220px]">
              AI-powered commerce. Smarter recommendations, faster delivery, better prices.
            </p>
          </div>

          {/* Link columns */}
          {COLS.map((col) => (
            <div key={col.title}>
              <p className="text-[0.68rem] font-semibold tracking-[0.15em] uppercase text-[#5a6478] mb-4">
                {col.title}
              </p>
              <ul className="flex flex-col gap-3">
                {col.links.map(({ label, href }) => (
                  <li key={label}>
                    <Link
                      href={href}
                      className="text-[0.82rem] text-[#8892a4] transition duration-300 ease-out hover:text-white hover:translate-x-1 hover:font-semibold"
                    >
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div className="pt-8 flex flex-col sm:flex-row items-center justify-between gap-4 text-[0.75rem] text-[#5a6478]">
          <p>© {new Date().getFullYear()} SHOPY. All rights reserved.</p>
          <div className="flex gap-6">
            {["Twitter", "GitHub", "LinkedIn", "Instagram"].map((s) => (
              <a
                key={s}
                href="#"
                className="transition-colors duration-200 hover:text-indigo-300"
              >
                {s}
              </a>
            ))}
          </div>
        </div>
      </div>
    </footer>
  );
}
