const pptxgen = require("pptxgenjs");

// ─── Design system ──────────────────────────────────────────────────────────
const C = {
  bg:     "0D1013",   // deep terminal charcoal — dominant
  bgAlt:  "11161B",
  card:   "191F26",
  cardHi: "1F272F",
  line:   "2C353F",
  text:   "E8ECEF",
  muted:  "8B95A3",
  dim:    "6B7683",
  green:  "00D084",   // sharp accent
  blue:   "4D9FFF",
  amber:  "F5A623",
  purple: "B06AFF",
  red:    "FF4466",
};

const F = { head: "Cambria", body: "Calibri" };
const M = 0.62;                 // page margin
const W = 13.33, H = 7.5;
const CW = W - 2 * M;           // content width = 12.09

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "Apex Capital Management";
pres.title = "Apex Capital — Investor Pitch";

// ─── Helpers ────────────────────────────────────────────────────────────────
const shadow = (o = {}) => ({
  type: "outer", angle: 90, blur: o.blur || 14, offset: o.offset || 2,
  color: "000000", opacity: o.opacity || 0.4,
});

function slide(bg) {
  const s = pres.addSlide();
  s.background = { color: bg || C.bg };
  return s;
}

function card(s, x, y, w, h, o = {}) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h,
    fill: { color: o.fill || C.card },
    line: { color: o.line || C.line, width: 0.75 },
    rectRadius: o.radius || 0.09,
    shadow: shadow({ blur: 12, offset: 2, opacity: 0.35 }),
  });
}

function dot(s, x, y, d, color, label, o = {}) {
  s.addShape(pres.ShapeType.ellipse, {
    x, y, w: d, h: d, fill: { color }, line: { color, width: 0 },
    shadow: shadow({ blur: 8, offset: 1, opacity: 0.3 }),
  });
  if (label !== undefined && label !== null) {
    s.addText(label, {
      x, y, w: d, h: d, align: "center", valign: "middle", margin: 0,
      fontFace: F.body, fontSize: o.size || 12, bold: true,
      color: o.labelColor || "0D1013",
    });
  }
}

// Slide header: kicker + title. Motif = small green dot preceding the kicker.
function head(s, kicker, title, o = {}) {
  const y = o.y !== undefined ? o.y : 0.46;
  s.addShape(pres.ShapeType.ellipse, {
    x: M, y: y + 0.075, w: 0.12, h: 0.12,
    fill: { color: o.kickerColor || C.green }, line: { width: 0 },
  });
  s.addText(kicker.toUpperCase(), {
    x: M + 0.22, y, w: CW - 0.22, h: 0.27, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 11, bold: true, charSpacing: 1.6,
    color: o.kickerColor || C.green,
  });
  s.addText(title, {
    x: M, y: y + 0.34, w: o.titleW || CW, h: 0.6, margin: 0, valign: "top",
    fontFace: F.head, fontSize: o.size || 32, bold: true, color: C.text,
  });
}

function body(s, x, y, w, h, text, o = {}) {
  s.addText(text, {
    x, y, w, h, margin: 0, valign: o.valign || "top",
    fontFace: F.body, fontSize: o.size || 14, color: o.color || C.muted,
    lineSpacing: o.lineSpacing || (o.size ? o.size * 1.35 : 19),
    align: o.align || "left", bold: o.bold || false, italic: o.italic || false,
  });
}

// Reusable stat tile
function stat(s, x, y, w, value, label, color) {
  s.addText(value, {
    x, y, w, h: 0.62, margin: 0, valign: "bottom", align: "left",
    fontFace: F.head, fontSize: 38, bold: true, color: color || C.green,
  });
  s.addText(label.toUpperCase(), {
    x, y: y + 0.66, w, h: 0.26, margin: 0, valign: "top", align: "left",
    fontFace: F.body, fontSize: 10, bold: true, charSpacing: 1.2, color: C.dim,
  });
}

function footer(s, n, text) {
  s.addText(text || "Apex Capital Management  ·  Autonomer KI-Hedgefonds  ·  Paper Trading", {
    x: M, y: H - 0.46, w: CW - 0.8, h: 0.25, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 9, color: "4A545F",
  });
  s.addText(String(n).padStart(2, "0"), {
    x: W - M - 0.7, y: H - 0.46, w: 0.7, h: 0.25, margin: 0, valign: "middle",
    align: "right", fontFace: F.body, fontSize: 9, bold: true, color: "4A545F",
  });
}

function arrow(s, x, y) {
  s.addShape(pres.ShapeType.rightArrow, {
    x, y, w: 0.22, h: 0.17, fill: { color: C.line }, line: { width: 0 },
  });
}

// ════════════════════════════════════════════════════════════════════════════
// 01 — Titel
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  // Ambient motif circles (very low contrast, purely decorative)
  s.addShape(pres.ShapeType.ellipse, {
    x: 9.4, y: -1.5, w: 5.6, h: 5.6, fill: { color: C.green, transparency: 93 }, line: { width: 0 },
  });
  s.addShape(pres.ShapeType.ellipse, {
    x: 11.0, y: 3.4, w: 3.4, h: 3.4, fill: { color: C.blue, transparency: 94 }, line: { width: 0 },
  });

  s.addShape(pres.ShapeType.ellipse, { x: M, y: 1.28, w: 0.14, h: 0.14, fill: { color: C.green }, line: { width: 0 } });
  s.addText("APEX CAPITAL MANAGEMENT", {
    x: M + 0.26, y: 1.2, w: 8, h: 0.3, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 12, bold: true, charSpacing: 2.4, color: C.green,
  });

  s.addText("Ein Hedgefonds,\nder sich selbst verwaltet.", {
    x: M, y: 1.72, w: 9.4, h: 1.9, margin: 0, valign: "top",
    fontFace: F.head, fontSize: 46, bold: true, color: C.text, lineSpacing: 54,
  });

  body(s, M, 3.74, 8.4, 1.0,
    "Zehn KI-Agenten mit eigenen Rollen und Charakteren recherchieren Aktien, streiten " +
    "über jede These und führen Trades vollautomatisch aus — mit echten Marktdaten, " +
    "aber ohne echtes Geld. 24 Stunden am Tag, ohne einen einzigen Klick.",
    { size: 15, color: C.muted, lineSpacing: 22 });

  // Stat strip
  const tiles = [
    ["10", "KI-Agenten", C.green],
    ["60", "Titel im Universum", C.blue],
    ["24/7", "Autonomer Betrieb", C.purple],
    ["0 €", "LLM-Kosten pro Monat", C.amber],
  ];
  const tw = 2.62, gap = 0.36;
  tiles.forEach(([v, l, col], i) => {
    const x = M + i * (tw + gap);
    stat(s, x, 5.18, tw, v, l, col);
  });

  s.addText("Investoren-Präsentation  ·  Stand August 2026", {
    x: M, y: H - 0.5, w: 8, h: 0.28, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 10, color: "4A545F",
  });
  s.addNotes(
    "Einstieg: Apex Capital ist kein Trading-Bot mit einer Formel, sondern ein " +
    "simuliertes Investmenthaus. Jede Entscheidung entsteht aus einer Debatte " +
    "zwischen spezialisierten Agenten und wird vollständig protokolliert. " +
    "Wichtig sofort klarstellen: Paper Trading, echtes Marktdaten-Feed, kein echtes Kapital."
  );
}

// ════════════════════════════════════════════════════════════════════════════
// 02 — Ausgangslage
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Ausgangslage", "Warum überhaupt ein Fonds aus Agenten?");

  const rows = [
    [C.amber, "1", "Research kostet, bevor es verdient",
      "Ein echtes Analystenteam — Makro, Charttechnik, Fundamentaldaten, Risiko — kostet sechsstellig pro Jahr, bevor die erste Order läuft."],
    [C.blue, "2", "Klassische KI-Modelle sind eine Blackbox",
      "Ein Modell sagt „kaufen“ und niemand weiß, warum. Ohne nachvollziehbare Begründung ist eine Entscheidung nicht prüfbar — und damit nicht investierbar."],
    [C.red, "3", "Menschen brechen ihre eigenen Regeln",
      "Stop-Loss verschieben, Verlierer aussitzen, Gewinner zu früh verkaufen. Diszipliniert ist eine Strategie nur, wenn niemand sie überstimmen kann."],
  ];

  const lw = 7.1;
  rows.forEach(([col, n, t, d], i) => {
    const y = 1.66 + i * 1.52;
    dot(s, M, y + 0.03, 0.44, col, n, { size: 14 });
    s.addText(t, {
      x: M + 0.66, y, w: lw - 0.66, h: 0.34, margin: 0, valign: "middle",
      fontFace: F.body, fontSize: 16, bold: true, color: C.text,
    });
    body(s, M + 0.66, y + 0.4, lw - 0.66, 0.9, d, { size: 13, lineSpacing: 18 });
  });

  // Answer card
  const cx = M + lw + 0.5, cwid = CW - lw - 0.5;
  card(s, cx, 1.58, cwid, 4.4, { fill: C.cardHi });
  s.addText("DIE ANTWORT VON APEX", {
    x: cx + 0.42, y: 1.9, w: cwid - 0.84, h: 0.28, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 10, bold: true, charSpacing: 1.6, color: C.green,
  });
  s.addText("Ein kompletter Investment-\nprozess als Software.", {
    x: cx + 0.42, y: 2.26, w: cwid - 0.84, h: 1.1, margin: 0, valign: "top",
    fontFace: F.head, fontSize: 19, bold: true, color: C.text, lineSpacing: 25,
  });
  body(s, cx + 0.42, 3.5, cwid - 0.84, 2.2,
    "Zehn Agenten übernehmen je eine Rolle des Investmentteams. Sie liefern " +
    "jeder ein eigenes Urteil, das Komitee streitet darüber, der Risikomanager " +
    "hat ein Vetorecht — und die Regeln lassen sich nicht überreden.\n\n" +
    "Jeder Schritt wird gespeichert und bleibt nachlesbar.",
    { size: 12.5, lineSpacing: 17.5 });

  footer(s, 2);
  s.addNotes("Der Kern: nicht Geschwindigkeit ist das Verkaufsargument, sondern Nachvollziehbarkeit plus Disziplin.");
}

// ════════════════════════════════════════════════════════════════════════════
// 03 — Was Apex heute ist
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Überblick", "Was heute läuft — nicht was geplant ist");

  body(s, M, 1.56, 11.4, 0.6,
    "Das System ist gebaut, deployed und handelt eigenständig. Was folgt, beschreibt den " +
    "tatsächlichen Betriebszustand.", { size: 14.5, color: C.muted });

  const tiles = [
    ["10.000 €", "Startkapital (simuliert)", C.green],
    ["15", "Positionen maximal parallel", C.blue],
    ["1 %", "Kapitalrisiko je Position", C.amber],
    ["6×", "Voll-Scans pro Handelstag", C.purple],
    ["60 s", "Takt der Überwachung", C.green],
    ["~5 €", "Serverkosten pro Monat", C.blue],
  ];
  const tw = 3.75, th = 1.56, gx = 0.42, gy = 0.4;
  tiles.forEach(([v, l, col], i) => {
    const x = M + (i % 3) * (tw + gx);
    const y = 2.44 + Math.floor(i / 3) * (th + gy);
    card(s, x, y, tw, th);
    s.addText(v, {
      x: x + 0.34, y: y + 0.2, w: tw - 0.68, h: 0.62, margin: 0, valign: "middle",
      fontFace: F.head, fontSize: 30, bold: true, color: col,
    });
    s.addText(l.toUpperCase(), {
      x: x + 0.34, y: y + 0.9, w: tw - 0.68, h: 0.3, margin: 0, valign: "middle",
      fontFace: F.body, fontSize: 10, bold: true, charSpacing: 1.1, color: C.dim,
    });
  });

  s.addText("Alle Zahlen sind fest im Code verankerte Regeln, keine Zielwerte.", {
    x: M, y: 6.44, w: CW, h: 0.3, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 12, italic: true, color: C.dim,
  });

  footer(s, 3);
}

// ════════════════════════════════════════════════════════════════════════════
// 04 — Das Team
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Das Team", "Zehn Agenten, zehn Zuständigkeiten");

  const team = [
    ["E", "Elena", "Makroökonomin", "Setzt das Marktregime für alle anderen", C.blue],
    ["K", "Kai", "Charttechniker", "„Der Chart lügt nie“ — reine Preisdaten", C.blue],
    ["S", "Sophie", "Fundamentalanalyse", "Buffett-Schule, Cashflow über alles", C.blue],
    ["A", "Alex", "Research", "Sucht Katalysatoren und Nachrichtenlage", C.blue],
    ["J", "Jordan", "Social Sentiment", "Liest Reddit und StockTwits", C.blue],
    ["V", "Viktor", "Risikomanager", "Sagt erst nein, dann vielleicht", C.amber],
    ["L", "Leo", "Bullen-Anwalt", "Findet immer ein Kaufargument", C.green],
    ["N", "Nina", "Bären-Anwältin", "Erinnert sich an 2008, 2001, 1987", C.red],
    ["M", "Marcus", "CIO — Letztes Wort", "Fällt das Urteil: kaufen, warten, ablehnen", C.purple],
    ["D", "Dante", "Advocatus Diaboli", "Sucht den Fehler in der fertigen These", C.purple],
  ];

  const cwid = 2.28, ch = 2.1, gx = 0.2, gy = 0.26;
  team.forEach(([ini, name, role, note, col], i) => {
    const x = M + (i % 5) * (cwid + gx);
    const y = 1.66 + Math.floor(i / 5) * (ch + gy);
    card(s, x, y, cwid, ch);
    dot(s, x + 0.28, y + 0.26, 0.46, col, ini, { size: 15 });
    s.addText(name, {
      x: x + 0.28, y: y + 0.8, w: cwid - 0.56, h: 0.3, margin: 0, valign: "middle",
      fontFace: F.head, fontSize: 16, bold: true, color: C.text,
    });
    s.addText(role.toUpperCase(), {
      x: x + 0.28, y: y + 1.09, w: cwid - 0.5, h: 0.24, margin: 0, valign: "middle",
      fontFace: F.body, fontSize: 8.5, bold: true, charSpacing: 0.8, color: col,
    });
    body(s, x + 0.28, y + 1.38, cwid - 0.5, 0.62, note, { size: 10, lineSpacing: 13, color: C.dim });
  });

  s.addText(
    "Jeder Agent hat einen eigenen Charakter — das erzeugt unterschiedliche Blickwinkel statt zehnmal derselben Antwort.", {
    x: M, y: 6.4, w: CW, h: 0.3, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 12, italic: true, color: C.dim,
  });

  footer(s, 4);
  s.addNotes("Elena läuft immer zuerst — ihr Makro-Regime geht als Kontext in jede weitere Analyse ein.");
}

// ════════════════════════════════════════════════════════════════════════════
// 05 — Die Pipeline (Prozess-Übersicht)
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Kernprozess", "Wie aus einem Kürzel eine Position wird");

  body(s, M, 1.5, 11.6, 0.32,
    "Jedes Wertpapier durchläuft dieselben acht Stufen — egal ob der Scanner es findet oder ein Mensch es anstößt.",
    { size: 13.5 });

  const steps = [
    ["1", "Makro-Kontext", "Elena bestimmt das Marktregime", C.blue],
    ["2", "Marktdaten", "6 Monate Kurse, 12 Indikatoren", C.blue],
    ["3", "Parallel-Analyse", "Kai, Sophie, Alex gleichzeitig", C.blue],
    ["4", "Social Sentiment", "Jordan liest die Masse", C.blue],
    ["5", "Risikoprüfung", "Viktor rechnet Größe und Stops", C.amber],
    ["6", "Komitee-Debatte", "Leo gegen Nina, Marcus urteilt", C.purple],
    ["7", "Gegenprüfung", "Dante sucht den fatalen Fehler", C.purple],
    ["8", "Ausführung", "Kauf ohne menschliche Freigabe", C.green],
  ];

  const bw = 2.79, bh = 1.62, gx = 0.31;
  steps.forEach(([n, t, d, col], i) => {
    const x = M + (i % 4) * (bw + gx);
    const y = 2.12 + Math.floor(i / 4) * (bh + 0.46);
    card(s, x, y, bw, bh, { fill: i === 7 ? C.cardHi : C.card });
    dot(s, x + 0.24, y + 0.22, 0.38, col, n, { size: 12 });
    s.addText(t, {
      x: x + 0.7, y: y + 0.22, w: bw - 0.94, h: 0.38, margin: 0, valign: "middle",
      fontFace: F.body, fontSize: 13.5, bold: true, color: C.text,
    });
    body(s, x + 0.24, y + 0.74, bw - 0.48, 0.7, d, { size: 11.5, lineSpacing: 15 });
    if (i % 4 !== 3) arrow(s, x + bw + 0.045, y + bh / 2 - 0.085);
  });

  card(s, M, 6.02, CW, 0.72, { fill: C.bgAlt });
  s.addText([
    { text: "Verzweigung:  ", options: { bold: true, color: C.text } },
    { text: "Nur ein ", options: { color: C.muted } },
    { text: "INVEST", options: { bold: true, color: C.green } },
    { text: "-Urteil erreicht Stufe 7 und 8. Bei ", options: { color: C.muted } },
    { text: "PASS", options: { bold: true, color: C.red } },
    { text: " oder ", options: { color: C.muted } },
    { text: "WAIT", options: { bold: true, color: C.amber } },
    { text: " endet der Vorgang ohne Trade — der Vorgang wird trotzdem vollständig archiviert.", options: { color: C.muted } },
  ], {
    x: M + 0.34, y: 6.02, w: CW - 0.68, h: 0.72, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 12.5,
  });

  footer(s, 5);
  s.addNotes("Stufe 1-4 sind Informationsbeschaffung, 5-7 sind Kontrolle, 8 ist Vollzug. Rund 8 LLM-Aufrufe pro Titel.");
}

// ════════════════════════════════════════════════════════════════════════════
// 06 — Stufen 1–3 im Detail
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Prozess im Detail  ·  Stufen 1 bis 3", "Erst der Markt, dann die Zahlen");

  const blocks = [
    ["1", C.blue, "Makro-Kontext (Elena)",
      "Fünf parallele Websuchen zu Zinspolitik, Volatilität, Sektorrotation und Rezessionsrisiko.\n\n" +
      "Ergebnis: Marktregime (Risk-On / Risk-Off / Übergang), Fed-Haltung, Sektorausblick, zwei Hauptrisiken.\n\n" +
      "Dieses Regime wird an alle folgenden Agenten weitergereicht — niemand analysiert im luftleeren Raum."],
    ["2", C.blue, "Marktdaten & Indikatoren",
      "Sechs Monate Tageskurse werden geladen und daraus zwölf Kennzahlen berechnet:\n\n" +
      "RSI · EMA 20/50 · Golden/Death Cross · MACD · ATR · Bollinger-Bänder · Volumenverhältnis · Unterstützung und Widerstand · Trendrichtung.\n\n" +
      "Reine Mathematik, kein Sprachmodell — die Zahlen sind reproduzierbar."],
    ["3", C.blue, "Drei Analysen gleichzeitig",
      "Kai (Chart), Sophie (Fundamentaldaten) und Alex (Research) laufen zeitgleich, nicht nacheinander.\n\n" +
      "Jeder liefert ein Signal von starkem Kauf bis starkem Verkauf, eine Überzeugung von 0 bis 10 und eine schriftliche These.\n\n" +
      "Kein Agent sieht das Urteil der anderen."],
  ];

  const bw = 3.78, gx = 0.38;
  blocks.forEach(([n, col, t, d], i) => {
    const x = M + i * (bw + gx);
    card(s, x, 1.66, bw, 4.4);
    dot(s, x + 0.32, 1.94, 0.42, col, n, { size: 13 });
    s.addText(t, {
      x: x + 0.32, y: 2.5, w: bw - 0.64, h: 0.62, margin: 0, valign: "top",
      fontFace: F.head, fontSize: 15.5, bold: true, color: C.text, lineSpacing: 19,
    });
    body(s, x + 0.32, 3.16, bw - 0.64, 2.6, d, { size: 11.5, lineSpacing: 15.5 });
  });

  s.addText("Zwischenstand nach Stufe 3: fünf voneinander unabhängige Einschätzungen desselben Titels.", {
    x: M, y: 6.3, w: CW, h: 0.3, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 12, italic: true, color: C.dim,
  });

  footer(s, 6);
}

// ════════════════════════════════════════════════════════════════════════════
// 07 — Stufen 4–5: Sentiment + Risiko (mit Chart)
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Prozess im Detail  ·  Stufen 4 und 5", "Die Masse lesen — und das Risiko rechnen");

  // Left: Jordan
  card(s, M, 1.64, 5.6, 4.42);
  dot(s, M + 0.34, 1.92, 0.42, C.blue, "4", { size: 13 });
  s.addText("Social Sentiment (Jordan)", {
    x: M + 0.34, y: 2.48, w: 4.9, h: 0.32, margin: 0, valign: "middle",
    fontFace: F.head, fontSize: 15.5, bold: true, color: C.text,
  });
  body(s, M + 0.34, 2.88, 4.94, 0.8,
    "Jordan zieht Reddit-Beiträge und StockTwits-Nachrichten und verdichtet sie zu einer Stimmungslage.",
    { size: 12, lineSpacing: 16 });

  const jrows = [
    ["Stimmungswert", "sehr bullisch bis sehr bärisch, plus Überzeugungsgrad"],
    ["Meme-Risiko", "über 10 Erwähnungen in Wallstreetbets → kleinere Position"],
    ["Contrarian-Flag", "Masse und Chartbild widersprechen sich → Vorsicht"],
  ];
  jrows.forEach(([t, d], i) => {
    const y = 3.76 + i * 0.8;
    s.addShape(pres.ShapeType.ellipse, { x: M + 0.36, y: y + 0.09, w: 0.11, h: 0.11, fill: { color: C.blue }, line: { width: 0 } });
    s.addText(t, {
      x: M + 0.6, y, w: 4.7, h: 0.28, margin: 0, valign: "middle",
      fontFace: F.body, fontSize: 12.5, bold: true, color: C.text,
    });
    body(s, M + 0.6, y + 0.28, 4.7, 0.42, d, { size: 11, lineSpacing: 14, color: C.dim });
  });

  // Right: Viktor
  const rx = M + 5.6 + 0.4, rw = CW - 5.6 - 0.4;
  card(s, rx, 1.64, rw, 4.42);
  dot(s, rx + 0.34, 1.92, 0.42, C.amber, "5", { size: 13 });
  s.addText("Risikoprüfung (Viktor)", {
    x: rx + 0.34, y: 2.48, w: rw - 0.68, h: 0.32, margin: 0, valign: "middle",
    fontFace: F.head, fontSize: 15.5, bold: true, color: C.text,
  });

  // Formula box
  s.addShape(pres.ShapeType.roundRect, {
    x: rx + 0.34, y: 2.88, w: rw - 0.68, h: 0.62,
    fill: { color: "0A0D10" }, line: { color: C.line, width: 0.75 }, rectRadius: 0.06,
  });
  s.addText("Positionsgröße  =  (Depotwert × 1 %) ÷ (1,5 × ATR)", {
    x: rx + 0.34, y: 2.88, w: rw - 0.68, h: 0.62, margin: 0, valign: "middle", align: "center",
    fontFace: "Courier New", fontSize: 12.5, bold: true, color: C.green,
  });
  body(s, rx + 0.34, 3.62, rw - 0.68, 0.5,
    "Nicht der Kurs bestimmt die Stückzahl, sondern die Schwankungsbreite (ATR).",
    { size: 11, lineSpacing: 14.5, color: C.dim });

  s.addText("MULTIPLIKATOR NACH VOLATILITÄTSREGIME (VIX)", {
    x: rx + 0.34, y: 4.14, w: rw - 0.68, h: 0.26, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 9.5, bold: true, charSpacing: 1, color: C.dim,
  });

  s.addChart(pres.ChartType.bar, [{
    name: "Positionsgröße",
    labels: ["Ruhig (<25)", "Erhöht (>25)", "Angst (>30)", "Panik (>40)"],
    values: [100, 75, 50, 25],
  }], {
    x: rx + 0.2, y: 4.44, w: rw - 0.4, h: 1.5,
    barDir: "col", barGapWidthPct: 55,
    chartColors: [C.green, C.amber, C.amber, C.red],
    showLegend: false, showTitle: false,
    showValue: true, dataLabelPosition: "outEnd", dataLabelColor: C.text,
    dataLabelFontFace: F.body, dataLabelFontSize: 10, dataLabelFormatCode: '0"%"',
    catAxisLabelColor: C.muted, catAxisLabelFontFace: F.body, catAxisLabelFontSize: 9.5,
    catAxisLineShow: false, catGridLine: { style: "none" },
    valAxisHidden: true, valGridLine: { style: "none" },
    valAxisMaxVal: 118, valAxisMinVal: 0,
    plotArea: { fill: { color: C.card } }, chartArea: { fill: { color: C.card } },
  });

  footer(s, 7);
  s.addNotes("Viktor kürzt zusätzlich bei Monatsverlust über 5 %, nach drei Verlusten in Folge, bei Meme-Risiko und vor Quartalszahlen.");
}

// ════════════════════════════════════════════════════════════════════════════
// 08 — Stufen 6–7: Komitee + Dante
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Prozess im Detail  ·  Stufen 6 und 7", "Die Entscheidung fällt im Streitgespräch");

  const trio = [
    [C.green, "L", "Leo — Bullenfall", "Baut das stärkste Kaufargument, nennt ein Kursziel nach oben und drei Belege aus den Berichten."],
    [C.red, "N", "Nina — Bärenfall", "Bekommt Leos Argument zu lesen und greift es direkt an. Nennt das Abwärtsziel und den schlechtesten Fall."],
    [C.purple, "M", "Marcus — Urteil", "Sieht beide Seiten plus Viktors Zahlen und entscheidet: INVEST, WAIT oder PASS — mit schriftlicher Begründung."],
  ];
  const bw = 3.78, gx = 0.38;
  trio.forEach(([col, ini, t, d], i) => {
    const x = M + i * (bw + gx);
    card(s, x, 1.64, bw, 2.32);
    dot(s, x + 0.32, 1.9, 0.42, col, ini, { size: 14 });
    s.addText(t, {
      x: x + 0.88, y: 1.9, w: bw - 1.2, h: 0.42, margin: 0, valign: "middle",
      fontFace: F.body, fontSize: 14, bold: true, color: C.text,
    });
    body(s, x + 0.32, 2.5, bw - 0.64, 1.3, d, { size: 11.5, lineSpacing: 15.5 });
    if (i < 2) arrow(s, x + bw + 0.075, 2.72);
  });

  // Hard rules
  s.addText("HARTE REGELN, DIE ÜBER DEM URTEIL STEHEN", {
    x: M, y: 4.16, w: CW, h: 0.28, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 10, bold: true, charSpacing: 1.4, color: C.green,
  });

  const rules = [
    [C.red, "Veto bei kritischem Risiko", "Stuft Viktor das Risiko als CRITICAL ein, wird das Urteil zwingend auf PASS gesetzt — unabhängig davon, wie überzeugt das Komitee war."],
    [C.amber, "Abschlag bei Uneinigkeit", "Liegen Leo und Nina in ihrer Überzeugung mehr als drei Punkte auseinander, wird die Positionsgröße auf 85 % gekürzt."],
    [C.purple, "Gegenprüfung (Stufe 7)", "Dante bekommt die fertige Entscheidung und sucht den einen übersehenen Fehler — mit Szenario, Wahrscheinlichkeit und Gegenmaßnahme."],
  ];
  rules.forEach(([col, t, d], i) => {
    const x = M + i * (bw + gx);
    card(s, x, 4.5, bw, 1.86, { fill: C.bgAlt });
    s.addShape(pres.ShapeType.ellipse, { x: x + 0.32, y: 4.83, w: 0.13, h: 0.13, fill: { color: col }, line: { width: 0 } });
    s.addText(t, {
      x: x + 0.56, y: 4.74, w: bw - 0.88, h: 0.3, margin: 0, valign: "middle",
      fontFace: F.body, fontSize: 12.5, bold: true, color: C.text,
    });
    body(s, x + 0.32, 5.1, bw - 0.64, 1.12, d, { size: 11, lineSpacing: 14.5 });
  });

  footer(s, 8);
  s.addNotes("Wichtig für Rückfragen: Dantes Einwand ist heute nur beratend, er kürzt die Position nicht automatisch. Das steht auf der Roadmap.");
}

// ════════════════════════════════════════════════════════════════════════════
// 09 — Risikoregeln
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Risikomanagement", "Sechs Regeln, die niemand überstimmen kann");

  const rules = [
    [C.green, "Einsatz je Position", "Höchstens 1 % des Depotwerts darf verloren gehen, wenn der Stop greift. Die Stückzahl ergibt sich daraus — nicht umgekehrt."],
    [C.amber, "Stop-Loss", "Einstieg minus 1,5 × ATR. Der Stop zieht mit steigendem Kurs nach, senkt sich aber niemals wieder."],
    [C.blue, "Gewinnmitnahme", "Bei Einstieg plus 2,5 × ATR werden 60 Prozent verkauft. Der Rest läuft mit Stop auf Einstandsniveau — ab da risikofrei."],
    [C.purple, "Depotgrenzen", "Maximal 15 Positionen gleichzeitig, mindestens 7 Prozent Barreserve, jeder Titel nur einmal."],
    [C.amber, "Verlustbremse", "Über 5 Prozent Monatsverlust oder drei Verluste in Folge halbieren jede neue Position automatisch."],
    [C.red, "Totes Kapital", "Wer nach 48 Stunden weniger als 1,5 Prozent im Plus liegt, wird verkauft — das Kapital arbeitet woanders weiter."],
  ];

  const cwid = 3.78, ch = 2.02, gx = 0.38, gy = 0.34;
  rules.forEach(([col, t, d], i) => {
    const x = M + (i % 3) * (cwid + gx);
    const y = 1.68 + Math.floor(i / 3) * (ch + gy);
    card(s, x, y, cwid, ch);
    s.addShape(pres.ShapeType.ellipse, {
      x: x + 0.32, y: y + 0.3, w: 0.34, h: 0.34, fill: { color: col, transparency: 78 }, line: { width: 0 },
    });
    s.addShape(pres.ShapeType.ellipse, {
      x: x + 0.42, y: y + 0.4, w: 0.14, h: 0.14, fill: { color: col }, line: { width: 0 },
    });
    s.addText(t, {
      x: x + 0.78, y: y + 0.28, w: cwid - 1.06, h: 0.38, margin: 0, valign: "middle",
      fontFace: F.head, fontSize: 15, bold: true, color: C.text,
    });
    body(s, x + 0.32, y + 0.82, cwid - 0.64, 1.06, d, { size: 11.5, lineSpacing: 15.5 });
  });

  s.addText("Diese Werte stehen im Quellcode, nicht in einem Prompt — ein Sprachmodell kann sie nicht verhandeln.", {
    x: M, y: 6.36, w: CW, h: 0.3, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 12, italic: true, color: C.dim,
  });

  footer(s, 9);
}

// ════════════════════════════════════════════════════════════════════════════
// 10 — Lebenszyklus einer Position
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Positionsführung", "Was nach dem Kauf passiert");

  body(s, M, 1.5, 11.6, 0.32,
    "Jede Minute zwischen 08:00 und 23:00 wird jede offene Position neu bewertet. Fünf Ereignisse können sie beenden.",
    { size: 13.5 });

  // Timeline
  const ty = 2.34;
  s.addShape(pres.ShapeType.rect, {
    x: M + 0.2, y: ty + 0.19, w: CW - 0.4, h: 0.025, fill: { color: C.line }, line: { width: 0 },
  });
  const phases = [
    [C.green, "Kauf", "Stop und Ziel werden beim Einstieg festgeschrieben"],
    [C.blue, "Überwachung", "Kurs, Gewinn und nachziehender Stop im Minutentakt"],
    [C.amber, "Teilverkauf", "60 Prozent am Kursziel, Rest läuft risikofrei weiter"],
    [C.red, "Schließung", "Fünf definierte Ausstiegsgründe"],
  ];
  const pw = (CW - 0.4) / 4;
  phases.forEach(([col, t, d], i) => {
    const cx = M + 0.2 + i * pw;
    s.addShape(pres.ShapeType.ellipse, {
      x: cx + pw / 2 - 0.11, y: ty + 0.09, w: 0.24, h: 0.24, fill: { color: col }, line: { color: C.bg, width: 2 },
    });
    s.addText(t, {
      x: cx, y: ty + 0.44, w: pw, h: 0.3, margin: 0, valign: "middle", align: "center",
      fontFace: F.body, fontSize: 14, bold: true, color: C.text,
    });
    body(s, cx + 0.15, ty + 0.76, pw - 0.3, 0.62, d, { size: 11, lineSpacing: 14.5, align: "center" });
  });

  // Exit reasons
  s.addText("DIE FÜNF AUSSTIEGSGRÜNDE", {
    x: M, y: 4.06, w: CW, h: 0.28, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 10, bold: true, charSpacing: 1.4, color: C.red,
  });

  const exits = [
    ["Trailing-Stop", "Kurs fällt unter den mitgezogenen Stop"],
    ["Fester Stop-Loss", "Ursprüngliches Verlustlimit erreicht"],
    ["Kursziel", "Teilverkauf, Rest mit Stop auf Einstand"],
    ["48-Stunden-Regel", "Position bewegt sich nicht — Kapital wird frei"],
    ["Umschichtung", "Schwächste Position weicht einer besseren Idee"],
  ];
  const ew = 2.24, egx = 0.22;
  exits.forEach(([t, d], i) => {
    const x = M + i * (ew + egx);
    card(s, x, 4.42, ew, 1.78, { fill: C.bgAlt });
    s.addText(String(i + 1).padStart(2, "0"), {
      x: x + 0.26, y: 4.6, w: ew - 0.52, h: 0.36, margin: 0, valign: "middle",
      fontFace: F.head, fontSize: 19, bold: true, color: C.red,
    });
    s.addText(t, {
      x: x + 0.26, y: 5.0, w: ew - 0.4, h: 0.28, margin: 0, valign: "middle",
      fontFace: F.body, fontSize: 11.5, bold: true, color: C.text,
    });
    body(s, x + 0.26, 5.34, ew - 0.44, 0.8, d, { size: 10.5, lineSpacing: 13.5 });
  });

  s.addText("Nach jedem Verkauf sucht das System selbsttätig nach einer neuen Verwendung für das frei gewordene Kapital.", {
    x: M, y: 6.46, w: CW, h: 0.3, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 12, italic: true, color: C.dim,
  });

  footer(s, 10);
}

// ════════════════════════════════════════════════════════════════════════════
// 11 — Der Handelstag
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Betrieb", "Ein Handelstag, vollständig getaktet");

  const schedule = [
    ["08:00", "Scan zur Eröffnung Europa", "Alle 60 Titel auf Signale prüfen", C.blue],
    ["08:01", "Morgenbericht", "Depotstand, offene Positionen, Stops, Ziele", C.green],
    ["13:45", "Tiefenscan vor US-Eröffnung", "Alle Titel bewertet, Top 10 vollanalysiert", C.purple],
    ["15:30", "Scan zur Eröffnung USA", "Reaktion auf den Handelsstart in New York", C.blue],
    ["17:30 / 19:30", "Zwei Zwischenscans", "Empfindlichere Schwelle für Volumenausschläge", C.blue],
    ["21:00", "Scan vor Handelsschluss", "Letzte Gelegenheiten des Tages", C.blue],
    ["21:30", "Tagesabschluss-Kontrolle", "Prüft, ob der Tag ohne Kauf geblieben ist", C.amber],
    ["Jede Minute", "Positionsüberwachung", "Kurse, Stops, Ziele, 48-Stunden-Regel", C.green],
  ];

  const rh = 0.5, gy = 0.08;
  schedule.forEach(([t, title, d, col], i) => {
    const y = 1.62 + i * (rh + gy);
    card(s, M, y, CW, rh, { fill: i % 2 === 0 ? C.card : C.bgAlt });
    s.addShape(pres.ShapeType.ellipse, { x: M + 0.28, y: y + rh / 2 - 0.065, w: 0.13, h: 0.13, fill: { color: col }, line: { width: 0 } });
    s.addText(t, {
      x: M + 0.54, y, w: 1.9, h: rh, margin: 0, valign: "middle",
      fontFace: "Courier New", fontSize: 12.5, bold: true, color: col,
    });
    s.addText(title, {
      x: M + 2.5, y, w: 3.9, h: rh, margin: 0, valign: "middle",
      fontFace: F.body, fontSize: 13, bold: true, color: C.text,
    });
    body(s, M + 6.5, y, CW - 6.9, rh, d, { size: 12, valign: "middle", lineSpacing: 15 });
  });

  s.addText("Zeiten in mitteleuropäischer Zeit, Montag bis Freitag. Zusätzlich läuft am ersten Montag im Monat der Monatsbericht.", {
    x: M, y: 6.48, w: CW, h: 0.3, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 11.5, italic: true, color: C.dim,
  });

  footer(s, 11);
}

// ════════════════════════════════════════════════════════════════════════════
// 12 — Architektur
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Technik", "Wie das System aufgebaut ist");

  const layers = [
    [C.green, "Oberfläche", "Zwei Dashboards, Live-Aktualisierung über WebSocket — jeder Agentenschritt erscheint in dem Moment, in dem er passiert."],
    [C.blue, "Anwendungsschicht", "FastAPI, vollständig asynchron. Zeitsteuerung über APScheduler. Analyse, Verkauf und Scan auch manuell auslösbar."],
    [C.purple, "Agentenschicht", "Zehn Agenten auf gemeinsamer Basis: Sprachmodell-Aufruf, Websuche, Antwortprüfung, Rückfallwerte bei Ausfall."],
    [C.amber, "Datenschicht", "Kurse über Yahoo Finance, Nachrichten über Tavily oder DuckDuckGo, Stimmung über Reddit und StockTwits."],
    [C.blue, "Speicherung", "SQLite auf eigenem Datenträger — ohne persistenten Speicher schaltet das System automatisch auf eine ferne Datenbank um."],
  ];

  const lh = 0.78, gy = 0.16;
  layers.forEach(([col, t, d], i) => {
    const y = 1.66 + i * (lh + gy);
    card(s, M, y, 8.4, lh);
    s.addShape(pres.ShapeType.ellipse, { x: M + 0.3, y: y + lh / 2 - 0.09, w: 0.18, h: 0.18, fill: { color: col }, line: { width: 0 } });
    s.addText(t, {
      x: M + 0.62, y, w: 2.5, h: lh, margin: 0, valign: "middle",
      fontFace: F.body, fontSize: 12.5, bold: true, color: C.text,
    });
    body(s, M + 3.2, y + 0.1, 4.9, lh - 0.2, d, { size: 11, lineSpacing: 14.5, valign: "middle" });
  });

  // Right column
  const rx = M + 8.4 + 0.42, rw = CW - 8.4 - 0.42;
  card(s, rx, 1.66, rw, 2.16, { fill: C.cardHi });
  s.addText("BETRIEB", {
    x: rx + 0.32, y: 1.92, w: rw - 0.64, h: 0.26, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 9.5, bold: true, charSpacing: 1.4, color: C.green,
  });
  body(s, rx + 0.32, 2.26, rw - 0.64, 1.4,
    "Ein Docker-Container, lauffähig auf jedem gängigen Anbieter. Neustart und " +
    "Aktualisierung ohne Datenverlust; die laufende Version steht im Dashboard.",
    { size: 11.5, lineSpacing: 15.5 });

  card(s, rx, 3.98, rw, 2.6, { fill: C.cardHi });
  s.addText("KOSTENSTRUKTUR", {
    x: rx + 0.32, y: 4.24, w: rw - 0.64, h: 0.26, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 9.5, bold: true, charSpacing: 1.4, color: C.amber,
  });
  const costs = [["Sprachmodelle", "0 €"], ["Marktdaten", "0 €"], ["Suche & Social", "0 €"], ["Server", "≈ 5 € / Monat"]];
  costs.forEach(([k, v], i) => {
    const y = 4.62 + i * 0.46;
    s.addText(k, {
      x: rx + 0.32, y, w: rw - 1.6, h: 0.34, margin: 0, valign: "middle",
      fontFace: F.body, fontSize: 12, color: C.muted,
    });
    s.addText(v, {
      x: rx + rw - 1.72, y, w: 1.4, h: 0.34, margin: 0, valign: "middle", align: "right",
      fontFace: F.body, fontSize: 12, bold: true, color: v === "0 €" ? C.green : C.text,
    });
  });

  footer(s, 12);
}

// ════════════════════════════════════════════════════════════════════════════
// 13 — Ausfallsicherheit
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Robustheit", "Jede Abhängigkeit hat einen Ersatz");

  body(s, M, 1.5, 11.6, 0.32,
    "Kostenlose Dienste fallen aus. Das System ist so gebaut, dass ein Ausfall es verlangsamt, aber nicht anhält.",
    { size: 13.5 });

  const chains = [
    [C.purple, "Sprachmodelle", ["Neun kostenlose Modelle,\nnacheinander durchprobiert", "Bis zu fünf Zugangsschlüssel\nim Wechsel", "Google Gemini als\nletzte Rückfallebene", "Vordefinierte Antwort,\nProzess läuft weiter"]],
    [C.blue, "Websuche", ["Tavily, sofern\nSchlüssel hinterlegt", "DuckDuckGo,\nohne Schlüssel nutzbar", "Leeres Ergebnis\nstatt Abbruch", "Agent arbeitet mit\nKursdaten weiter"]],
    [C.amber, "Speicherung", ["Lokale Datenbank\nauf eigenem Datenträger", "Ferne Datenbank,\nfalls kein Speicher da ist", "Automatischer\nNeuaufbau der Verbindung", "Vorgang wird wiederholt,\nkein Datenverlust"]],
  ];

  const cwid = 3.78, gx = 0.38;
  chains.forEach(([col, t, steps], i) => {
    const x = M + i * (cwid + gx);
    card(s, x, 2.06, cwid, 4.0);
    s.addText(t, {
      x: x + 0.32, y: 2.3, w: cwid - 0.64, h: 0.36, margin: 0, valign: "middle",
      fontFace: F.head, fontSize: 16, bold: true, color: col,
    });
    steps.filter(Boolean).forEach((st, j) => {
      const y = 2.82 + j * 0.78;
      s.addShape(pres.ShapeType.roundRect, {
        x: x + 0.32, y, w: cwid - 0.64, h: 0.6,
        fill: { color: C.bgAlt }, line: { color: C.line, width: 0.75 }, rectRadius: 0.05,
      });
      s.addText(String(j + 1), {
        x: x + 0.44, y, w: 0.3, h: 0.6, margin: 0, valign: "middle", align: "left",
        fontFace: F.body, fontSize: 11, bold: true, color: col,
      });
      body(s, x + 0.78, y + 0.06, cwid - 1.16, 0.5, st, { size: 10.5, lineSpacing: 13, color: C.muted, valign: "middle" });
      if (j < steps.filter(Boolean).length - 1) {
        s.addShape(pres.ShapeType.downArrow, {
          x: x + cwid / 2 - 0.07, y: y + 0.62, w: 0.14, h: 0.14, fill: { color: C.line }, line: { width: 0 },
        });
      }
    });
  });

  footer(s, 13);
  s.addNotes("Beleg aus der Praxis: der komplette Katalog kostenloser Modelle bei OpenRouter war einmal von heute auf morgen abgeschaltet. Die Kette hat den Betrieb aufrechterhalten.");
}

// ════════════════════════════════════════════════════════════════════════════
// 14 — Transparenz
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Nachvollziehbarkeit", "Jede Entscheidung bleibt prüfbar");

  const left = [
    ["Vollständiges Analyseprotokoll", "Zu jedem geprüften Titel werden alle acht Berichte gespeichert — Makrolage, Chartbild, Fundamentaldaten, Research, Stimmung, Risiko, Komiteedebatte und Dantes Einwand."],
    ["Signale am Trade", "Jeder Kauf trägt die vollständige Begründung mit sich. Auch Jahre später ist erkennbar, welcher Agent was gesagt hat."],
    ["Wertentwicklung im Zeitverlauf", "Nach jeder Veränderung wird der Depotwert festgehalten — daraus entsteht die Kurve, ohne Nachbearbeitung."],
  ];
  const lw = 6.9;
  left.forEach(([t, d], i) => {
    const y = 1.66 + i * 1.5;
    s.addShape(pres.ShapeType.ellipse, { x: M, y: y + 0.08, w: 0.15, h: 0.15, fill: { color: C.green }, line: { width: 0 } });
    s.addText(t, {
      x: M + 0.34, y, w: lw - 0.34, h: 0.32, margin: 0, valign: "middle",
      fontFace: F.head, fontSize: 16, bold: true, color: C.text,
    });
    body(s, M + 0.34, y + 0.4, lw - 0.34, 1.0, d, { size: 12.5, lineSpacing: 17 });
  });

  const rx = M + lw + 0.4, rw = CW - lw - 0.4;
  card(s, rx, 1.6, rw, 2.12, { fill: C.cardHi });
  s.addText("LIVE-EINBLICK", {
    x: rx + 0.34, y: 1.86, w: rw - 0.68, h: 0.26, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 9.5, bold: true, charSpacing: 1.4, color: C.green,
  });
  body(s, rx + 0.34, 2.2, rw - 0.68, 1.5,
    "Zwei Dashboards zeigen die Arbeit der Agenten in Echtzeit: welcher Agent " +
    "gerade rechnet, welches Signal er liefert, welcher Trade ausgelöst wurde.",
    { size: 12, lineSpacing: 16 });

  card(s, rx, 3.86, rw, 1.4, { fill: C.cardHi });
  s.addText("MONATSBERICHT", {
    x: rx + 0.34, y: 4.08, w: rw - 0.68, h: 0.26, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 9.5, bold: true, charSpacing: 1.4, color: C.purple,
  });
  body(s, rx + 0.34, 4.38, rw - 0.68, 0.76,
    "Automatisch am ersten Montag: Wertentwicklung, Trefferquote, bester und " +
    "schlechtester Trade, Einordnung des CIO.",
    { size: 12, lineSpacing: 16 });

  card(s, rx, 5.4, rw, 1.4, { fill: C.cardHi });
  s.addText("OFFENE SCHNITTSTELLE", {
    x: rx + 0.34, y: 5.62, w: rw - 0.68, h: 0.26, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 9.5, bold: true, charSpacing: 1.4, color: C.blue,
  });
  body(s, rx + 0.34, 5.92, rw - 0.68, 0.76,
    "Depot, Trades, Berichte und Kurse sind über Schnittstellen abrufbar — " +
    "prüfbar auch ohne Zugriff auf das Dashboard.",
    { size: 12, lineSpacing: 16 });

  footer(s, 14);
}

// ════════════════════════════════════════════════════════════════════════════
// 15 — Ehrliche Einordnung
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bgAlt);
  head(s, "Offene Punkte", "Was heute noch gegen das Konzept spricht", { kickerColor: C.red });

  body(s, M, 1.5, 11.6, 0.32,
    "Diese Punkte gehören auf den Tisch, bevor jemand die bisherige Wertentwicklung als Beleg für Modellqualität liest.",
    { size: 13.5 });

  const issues = [
    ["Handelszwang verzerrt die Bilanz", "Jeder Scan erzwingt einen Kauf; bleibt ein Tag ohne Trade, kauft um 21:30 eine Notlösung ohne Sprachmodell den Spitzenreiter der Rangliste."],
    ["Kein Vergleichsmaßstab", "Es fehlt die Gegenüberstellung mit einem einfachen Indexinvestment sowie Kennzahlen wie Sharpe-Quotient oder Trefferquote je Agent."],
    ["Währung und Handelskosten fehlen", "Das Depot rechnet in Euro, die Kurse notieren in US-Dollar — ohne Umrechnung. Gebühren, Spreads und Ausführungsabweichungen sind nicht berücksichtigt."],
    ["Keine Klumpenkontrolle", "Fünfzehn Positionen könnten sämtlich Halbleiterwerte sein. Ein Sektor- oder Korrelationslimit existiert nicht."],
    ["Bewertung der Agenten ist unscharf", "Die Monatsauswertung zählt jeden Agenten bei jedem Trade mit, unabhängig davon, ob er zum Kauf geraten hat. Die Trefferquoten sind dadurch für alle gleich."],
  ];

  const cwid = 5.86, ch = 1.4, gx = 0.37, gy = 0.2;
  issues.forEach(([t, d], i) => {
    const x = M + (i % 2) * (cwid + gx);
    const y = 2.1 + Math.floor(i / 2) * (ch + gy);
    const w = i === 4 ? CW : cwid;
    card(s, x, y, w, ch, { fill: C.card });
    s.addShape(pres.ShapeType.ellipse, { x: x + 0.3, y: y + 0.33, w: 0.14, h: 0.14, fill: { color: C.red }, line: { width: 0 } });
    s.addText(t, {
      x: x + 0.56, y: y + 0.22, w: w - 0.86, h: 0.34, margin: 0, valign: "middle",
      fontFace: F.body, fontSize: 14, bold: true, color: C.text,
    });
    body(s, x + 0.3, y + 0.62, w - 0.6, 0.72, d, { size: 11.5, lineSpacing: 15 });
  });

  footer(s, 15);
  s.addNotes("Diese Folie ist bewusst drin. Wer sie weglässt, verliert die Glaubwürdigkeit spätestens in der Due Diligence.");
}

// ════════════════════════════════════════════════════════════════════════════
// 16 — Roadmap
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Roadmap", "Drei Ausbaustufen, in dieser Reihenfolge");

  const phases = [
    [C.green, "Stufe 1", "Ehrliche Messung", [
      "Handelszwang abschalten oder getrennt verbuchen",
      "Vergleich gegen ein einfaches Indexinvestment",
      "Sharpe, Trefferquote, Verlustserien je Agent",
      "Rückrechnung über historische Zeiträume",
    ]],
    [C.amber, "Stufe 2", "Härtung", [
      "Währungsumrechnung, Gebühren, Ausführungsabschlag",
      "Sektor- und Korrelationsgrenzen im Depot",
      "Notabschaltung ab definiertem Gesamtverlust",
      "Sperre gegen gleichzeitige Depotänderungen",
    ]],
    [C.purple, "Stufe 3", "Qualität der Urteile", [
      "Dantes Einwand mit echter Wirkung auf die Größe",
      "Grundsatz „im Zweifel abwarten“ statt „im Zweifel kaufen“",
      "Verwendetes Modell je Entscheidung protokollieren",
      "Auswertung: welcher Agent liefert tatsächlich Mehrwert",
    ]],
  ];

  const cwid = 3.78, gx = 0.38;
  phases.forEach(([col, ph, t, items], i) => {
    const x = M + i * (cwid + gx);
    card(s, x, 1.66, cwid, 4.36);
    s.addShape(pres.ShapeType.roundRect, {
      x: x + 0.32, y: 1.94, w: 1.02, h: 0.34,
      fill: { color: col, transparency: 82 }, line: { width: 0 }, rectRadius: 0.06,
    });
    s.addText(ph.toUpperCase(), {
      x: x + 0.32, y: 1.94, w: 1.02, h: 0.34, margin: 0, valign: "middle", align: "center",
      fontFace: F.body, fontSize: 9.5, bold: true, charSpacing: 0.8, color: col,
    });
    s.addText(t, {
      x: x + 0.32, y: 2.42, w: cwid - 0.64, h: 0.4, margin: 0, valign: "middle",
      fontFace: F.head, fontSize: 18, bold: true, color: C.text,
    });
    items.forEach((it, j) => {
      const y = 2.98 + j * 0.76;
      s.addShape(pres.ShapeType.ellipse, { x: x + 0.34, y: y + 0.11, w: 0.1, h: 0.1, fill: { color: col }, line: { width: 0 } });
      body(s, x + 0.6, y, cwid - 0.92, 0.68, it, { size: 11.5, lineSpacing: 15 });
    });
  });

  s.addText("Reihenfolge ist Absicht: erst ehrlich messen, dann absichern, dann die Urteilsqualität steigern.", {
    x: M, y: 6.3, w: CW, h: 0.3, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 12, italic: true, color: C.dim,
  });

  footer(s, 16);
}

// ════════════════════════════════════════════════════════════════════════════
// 17 — Warum es zählt
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  head(s, "Einordnung", "Wozu das Ganze taugt");

  const points = [
    [C.green, "Ein Prüfstand für KI-Entscheidungen",
      "Nicht die Rendite ist das eigentliche Produkt, sondern ein Aufbau, in dem sich messen lässt, ob mehrere streitende Modelle bessere Urteile fällen als ein einzelnes."],
    [C.blue, "Der Prozess ist übertragbar",
      "Rollenverteilung, Debatte, Vetorecht und lückenlose Protokollierung funktionieren überall dort, wo Entscheidungen unter Unsicherheit begründet werden müssen — Kreditvergabe, Einkauf, Personalauswahl."],
    [C.amber, "Betrieb kostet fast nichts",
      "Rund fünf Euro im Monat für ein System, das durchgehend läuft. Die Skalierung scheitert nicht am Preis, sondern allein an der Qualität der Entscheidungen."],
  ];

  points.forEach(([col, t, d], i) => {
    const y = 1.72 + i * 1.52;
    dot(s, M, y + 0.02, 0.5, col, String(i + 1), { size: 15 });
    s.addText(t, {
      x: M + 0.78, y, w: 6.3, h: 0.36, margin: 0, valign: "middle",
      fontFace: F.head, fontSize: 19, bold: true, color: C.text,
    });
    body(s, M + 0.78, y + 0.44, 6.3, 1.0, d, { size: 12.5, lineSpacing: 17 });
  });

  const rx = M + 7.6, rw = CW - 7.6;
  card(s, rx, 1.66, rw, 4.5, { fill: C.cardHi });
  s.addText("„", {
    x: rx + 0.34, y: 1.86, w: 1, h: 0.8, margin: 0, valign: "top",
    fontFace: F.head, fontSize: 50, bold: true, color: C.green,
  });
  s.addText(
    "Der Wert liegt nicht darin, dass zehn Modelle handeln — sondern darin, " +
    "dass am Ende jeder Entscheidung nachlesbar bleibt, wer was gesagt hat.", {
    x: rx + 0.38, y: 2.72, w: rw - 0.76, h: 1.7, margin: 0, valign: "top",
    fontFace: F.head, fontSize: 15, italic: true, color: C.text, lineSpacing: 23,
  });
  s.addShape(pres.ShapeType.line, {
    x: rx + 0.38, y: 4.64, w: 0.7, h: 0, line: { color: C.line, width: 1 },
  });
  s.addText("Kernthese des Projekts", {
    x: rx + 0.38, y: 4.78, w: rw - 0.76, h: 0.3, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 11, color: C.dim,
  });

  footer(s, 17);
}

// ════════════════════════════════════════════════════════════════════════════
// 18 — Abschluss
// ════════════════════════════════════════════════════════════════════════════
{
  const s = slide(C.bg);
  s.addShape(pres.ShapeType.ellipse, {
    x: 9.8, y: 2.6, w: 5.2, h: 5.2, fill: { color: C.green, transparency: 94 }, line: { width: 0 },
  });
  s.addShape(pres.ShapeType.ellipse, { x: M, y: 1.66, w: 0.14, h: 0.14, fill: { color: C.green }, line: { width: 0 } });
  s.addText("NÄCHSTER SCHRITT", {
    x: M + 0.26, y: 1.58, w: 8, h: 0.3, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 11, bold: true, charSpacing: 2.2, color: C.green,
  });
  s.addText("Erst beweisen,\ndann skalieren.", {
    x: M, y: 2.06, w: 8.6, h: 1.5, margin: 0, valign: "top",
    fontFace: F.head, fontSize: 40, bold: true, color: C.text, lineSpacing: 48,
  });
  body(s, M, 3.72, 7.6, 1.2,
    "Das System läuft. Der nächste Meilenstein ist nicht mehr Funktionsumfang, sondern " +
    "Beweisführung: sechs Monate saubere Wertentwicklung ohne Handelszwang, gegen einen " +
    "Vergleichsindex gemessen, mit belastbaren Kennzahlen je Agent.",
    { size: 14.5, lineSpacing: 21 });

  const asks = [
    ["Sechs Monate", "Messzeitraum ohne erzwungene Trades"],
    ["Vergleichsindex", "Jede Kurve gegen ein Indexinvestment"],
    ["Danach", "Entscheidung über echtes Kapital"],
  ];
  const aw = 3.78, gx = 0.38;
  asks.forEach(([t, d], i) => {
    const x = M + i * (aw + gx);
    card(s, x, 5.24, aw, 1.24, { fill: C.cardHi });
    s.addText(t, {
      x: x + 0.3, y: 5.44, w: aw - 0.6, h: 0.32, margin: 0, valign: "middle",
      fontFace: F.head, fontSize: 16, bold: true, color: C.green,
    });
    body(s, x + 0.3, 5.78, aw - 0.6, 0.5, d, { size: 11.5, lineSpacing: 15 });
  });

  s.addText("Apex Capital Management  ·  github.com/Nikros07/Apex-Capital", {
    x: M, y: H - 0.52, w: 9, h: 0.3, margin: 0, valign: "middle",
    fontFace: F.body, fontSize: 10, color: "4A545F",
  });
  s.addNotes("Abschluss: keine Kapitalanfrage für echten Handel, sondern die Bitte um Zeit und um die Zustimmung zur Messmethodik.");
}

const out = process.argv[2] || "Apex-Capital-Investor-Pitch.pptx";
pres.writeFile({ fileName: out }).then(() => console.log("written:", out));
