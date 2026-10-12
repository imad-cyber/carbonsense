const AUTHOR_CHECKED_PDF = false;
const PDF = "https://www.salesforce.com/en-us/wp-content/uploads/sites/4/documents/legal/misc/BEGES_Salesforce_2023.pdf";

const LOOKED_UP = [
  { line: "1.1 Fixed combustion, natural gas", input: "12,978 kWh PCI × 0.201 (combustion factor only)", ours: "2.61 t", filing: "2.61 t" },
  { line: "2.1 Electricity, operated sites", input: "5,357,920 kWh × 0.0338 (generation only)", ours: "181.10 t", filing: "181.10 t" },
];
const ARITHMETIC = [
  { line: "2.2 Steam", input: "529,437 kWh × 0.18", ours: "95.30 t", filing: "95.30 t" },
  { line: "6.1 Non-operated site electricity", input: "83,432 kWh × 0.05204 (full factor)", ours: "4.34 t", filing: "4.34 t" },
  { line: "1.4 Refrigerants", input: "63.261 kg × 4,800 + 18.483 kg × 1,920", ours: "339.14 t", filing: "339.14 t" },
];

function Rows({ rows }: { rows: typeof LOOKED_UP }) {
  return (
    <>
      {rows.map((r) => (
        <tr key={r.line}>
          <td>{r.line}</td>
          <td>{r.input}</td>
          <td className="n">{r.ours}</td>
          <td className="n">{r.filing}</td>
        </tr>
      ))}
    </>
  );
}

export default function Validation() {
  return (
    <section>
      <h2>Validation against a published filing</h2>
      <p>
        The public greenhouse-gas report (BEGES) of Salesforce.com France for financial year 2023 lists its
        activity data, emission factors and results.{" "}
        <a href={PDF}>Open the filing</a>. The figures below were transcribed from it.
      </p>
      {AUTHOR_CHECKED_PDF ? (
        <p className="callout">The author checked the transcription against the PDF.</p>
      ) : (
        <p className="warn">The author's own check of the transcription against the PDF is pending.</p>
      )}
      <div className="card">
        <h3>Reproduced with factors looked up in Base Carbone V23.6</h3>
        <table>
          <thead>
            <tr><th>Line</th><th>Activity × factor</th><th className="n">CarbonSense</th><th className="n">Filing</th></tr>
          </thead>
          <tbody><Rows rows={LOOKED_UP} /></tbody>
        </table>
        <h3>Checked by arithmetic only (factor as printed in the filing)</h3>
        <table>
          <tbody><Rows rows={ARITHMETIC} /></tbody>
        </table>
      </div>
      <h3>What this shows</h3>
      <ul>
        <li>Scope 1 books the combustion factor only and Scope 2 books generation only. Line 2.1 equals kWh × 0.0338, so upstream and grid losses are not in it.</li>
        <li>The loaded electricity factor has the same three parts as the filing (0.0338, 0.0135, 0.00474); the gas upstream part differs by -1.8%.</li>
      </ul>
      <h3>What it does not show</h3>
      <ul>
        <li>One filing is one example, not proof that the allocation policy is right in general.</li>
        <li>The purchases line (about 2,270 t) and the diesel line are not reproduced.</li>
        <li>Only location-based Scope 2 is supported. Sites outside operational control are not modelled.</li>
      </ul>
    </section>
  );
}
