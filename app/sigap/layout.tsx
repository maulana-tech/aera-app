// Token warna twenty-ui di-scope ke kelas `dark`. Dibungkus di sini supaya
// hanya bagian SIGAP yang memakainya — situs acara tidak ikut terpengaruh.
export default function LayoutSigap({ children }: { children: React.ReactNode }) {
  return <div className="dark">{children}</div>;
}
