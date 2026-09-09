import Image from "next/image";
import Link from "next/link";
import styles from "./Footer.module.css";

const columns = [
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
    title: "Legal",
    links: [
      { label: "Terms of Service", href: "/legal/terms" },
      { label: "Privacy Policy", href: "/legal/privacy" },
      { label: "Cookie Policy", href: "/legal/cookies" },
      { label: "Security", href: "/legal/security" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <div className={styles.topGrid}>
          <div className={styles.brand}>
            <Link href="/" aria-label="Shopy home" className={styles.logoLink}>
              <Image src="/images/brand/shopy-logo-v2.png" alt="Shopy" width={150} height={60} className={styles.logo} />
            </Link>
            <p className="text-[0.82rem] text-[#8892a4] leading-relaxed max-w-[220px]">
              AI-powered commerce. Smarter recommendations, faster delivery, better prices.
            </p>
          </div>

          {columns.map((col) => (
            <nav key={col.title} aria-label={col.title} className={styles.column}>
              <p>
                {col.title}
              </p>
              <ul>
                {col.links.map(({ label, href }) => (
                  <li key={label}>
                    <Link href={href}>{label}</Link>
                  </li>
                ))}
              </ul>
            </nav>
          ))}
        </div>

        <div className={styles.bottomBar}>
          <p>© {new Date().getFullYear()} Shopy. All rights reserved.</p>
          <p>Built for more thoughtful everyday shopping.</p>
        </div>
      </div>
    </footer>
  );
}
