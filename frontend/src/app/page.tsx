const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function Home() {
  return (
    <main>
      <p className="eyebrow">CE01 · Walking Skeleton</p>
      <h1>MOTGU Content Engine</h1>
      <p>
        Repository foundation is ready for the first Research → Keyword Plan → Golden Journal path.
      </p>
      <dl>
        <div>
          <dt>Backend</dt>
          <dd>{apiBaseUrl}</dd>
        </div>
        <div>
          <dt>Current phase</dt>
          <dd>CE01</dd>
        </div>
      </dl>
    </main>
  );
}
